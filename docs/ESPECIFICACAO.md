# Especificação do MVP — AgendaLab

| | |
|---|---|
| **Sistema** | AgendaLab — reserva de salas e laboratórios |
| **Disciplina** | Arquitetura de Software |
| **Professor** | MSc. Lucas Reis |
| **Autor** | Luiz Cutrim — Ciência da Computação — UFMA |
| **Versão** | 1.0 |
| **Data** | 05/08/2026 |
| **Status** | Aprovada — base para a implementação |

> Este documento é a **fonte da verdade** do domínio. Os [ADRs](ADRs/README.md), os
> [diagramas](ARQUITETURA.md) e o código derivam dele. Divergência entre este documento e o
> código é defeito — de um lado ou do outro.

---

## 1. Problema

Espaços de uso compartilhado numa universidade — salas de aula, laboratórios, auditório — são
disputados. Na ausência de um sistema, a alocação acontece por planilha, grupo de mensagens ou
caderno na portaria. Três problemas decorrem disso:

1. **Reserva dupla.** Duas pessoas reservam o mesmo espaço no mesmo horário e o conflito só aparece
   na hora do uso.
2. **Regras não uniformes.** Um laboratório com equipamento caro não deveria ser liberado com a
   mesma facilidade de uma sala de aula comum, mas a regra existe apenas na cabeça de quem controla.
3. **Ausência de rastro.** Não se sabe quem pediu, quem autorizou, nem quando.

O AgendaLab resolve os três: detecta conflitos no ato da solicitação, aplica regras de admissão
distintas por tipo de espaço e mantém a trilha de decisão de cada reserva.

## 2. Escopo

### 2.1 Dentro do escopo

Sete casos de uso, detalhados na seção 6. Cadastro de espaços, consulta de agenda e
disponibilidade, solicitação de reserva com detecção de conflito, aprovação, rejeição e
cancelamento.

### 2.2 Fora do escopo

Cada exclusão abaixo é **decisão registrada**, não esquecimento.

| Excluído | Razão | Registro |
|---|---|---|
| Autenticação e gestão de usuários | Não é o objeto de avaliação e consumiria o prazo sem agregar valor arquitetural | [ADR-0007](ADRs/0007-autenticacao-fora-de-escopo.md) |
| Reservas recorrentes | Conflito em lote e cancelamento parcial de série multiplicam os casos de borda | §2.3 |
| Fila de espera | Exigiria novos estados e promoção automática | §2.3 |
| Envio real de e-mail/SMS | O Observer é demonstrado por log e por caixa de entrada consultável | [ADR-0006](ADRs/0006-observer-notificacoes.md) |
| Front-end | A avaliação é da arquitetura; o Swagger UI demonstra o sistema rodando | [ADR-0002](ADRs/0002-stack-python-fastapi.md) |
| Deploy / containerização | O avaliador roda localmente com um comando | [ADR-0002](ADRs/0002-stack-python-fastapi.md) |

### 2.3 Evolução prevista

O desenho acomoda estas extensões sem reescrita — o argumento está detalhado nos ADRs indicados:

- **Novo tipo de espaço** → uma nova classe de política, nenhum arquivo existente alterado
  ([ADR-0004](ADRs/0004-strategy-politicas-de-reserva.md)).
- **Novo canal de notificação** → um novo observador registrado no publicador
  ([ADR-0006](ADRs/0006-observer-notificacoes.md)).
- **Novo estado da reserva** (ex.: `EM_ANDAMENTO`, `CONCLUÍDA`) → uma nova classe de estado
  ([ADR-0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md)).
- **Troca de banco** → uma nova implementação do repositório
  ([ADR-0003](ADRs/0003-persistencia-sqlite-repository.md)).

## 3. Atores

| Ator | Descrição | Como é identificado |
|---|---|---|
| **Solicitante** (`REQUESTER`) | Aluno ou professor que pede uso de um espaço | Cabeçalhos `X-User-Id` e `X-User-Role` |
| **Gestor** (`MANAGER`) | Responsável que cadastra espaços e decide sobre solicitações | Cabeçalhos `X-User-Id` e `X-User-Role` |

O sistema **não autentica** — confia no papel declarado na requisição. Isso é uma decisão consciente
e delimitada, registrada em [ADR-0007](ADRs/0007-autenticacao-fora-de-escopo.md).

## 4. Modelo de domínio

Os termos em português usados aqui e seus identificadores em inglês no código estão no
[Glossário](GLOSSARIO.md).

### 4.1 Entidades

**`Space` (Espaço)** — um recurso físico reservável.

| Campo | Tipo | Regra |
|---|---|---|
| `code` | texto | Identificador natural, único e imutável (ex.: `LAB-01`). É a chave usada nas rotas. |
| `name` | texto | Nome legível (ex.: "Laboratório de Redes") |
| `kind` | `SpaceKind` | `CLASSROOM`, `LAB` ou `AUDITORIUM` — determina a política aplicada |
| `capacity` | inteiro | Máximo de ocupantes; deve ser > 0 |
| `active` | booleano | Espaço inativo não aceita novas reservas |

**`Booking` (Reserva)** — a solicitação de uso de um espaço num intervalo.

| Campo | Tipo | Regra |
|---|---|---|
| `id` | UUID | Gerado na criação |
| `space_code` | texto | Referência ao espaço |
| `requester_id` | texto | Matrícula ou e-mail de quem solicitou |
| `slot` | `TimeSlot` | Intervalo pretendido |
| `purpose` | texto | Finalidade declarada |
| `attendees` | inteiro | Número de participantes previstos |
| `status` | `BookingStatus` | `PENDING`, `APPROVED`, `REJECTED` ou `CANCELLED` |
| `created_at` | data/hora | Momento da solicitação |
| `decided_by` | texto \| nulo | Quem aprovou, rejeitou ou cancelou |
| `decided_at` | data/hora \| nulo | Quando a decisão ocorreu |
| `rejection_reason` | texto \| nulo | Obrigatório na rejeição (RN-14) |

Não existe entidade `User`. O solicitante é um identificador opaco — ver
[ADR-0007](ADRs/0007-autenticacao-fora-de-escopo.md).

### 4.2 Objeto de valor

**`TimeSlot` (Intervalo)** — par `start_at` / `end_at`, imutável, com a operação `overlaps()`.

É aqui que nasce a detecção de conflito, e é por isso que ela é testável sem banco, sem framework
e sem rede. O teste de sobreposição é uma função pura sobre dois pares de datas.

### 4.3 Invariantes

Propriedades que o domínio nunca permite violar, em nenhum caminho de execução:

- Um `TimeSlot` sempre tem `start_at < end_at`.
- Uma `Booking` sempre está em exatamente um dos quatro estados.
- Uma `Booking` em estado terminal (`REJECTED`, `CANCELLED`) nunca volta a mudar.
- Uma `Booking` `REJECTED` sempre tem `rejection_reason` preenchido.
- Dois `Space` nunca compartilham o mesmo `code`.

## 5. Regras de negócio

Numeradas para permitir rastreabilidade direta entre especificação, ADR, código e teste.

### 5.1 Integridade do intervalo

| ID | Regra |
|---|---|
| **RN-01** | Um espaço não pode ter duas reservas **ativas** com sobreposição de horário. Consideram-se ativas as reservas em `PENDING` ou `APPROVED`. |
| **RN-02** | Dois intervalos se sobrepõem quando `início_a < fim_b ∧ início_b < fim_a`. Intervalos que apenas se tocam nas bordas (`fim_a == início_b`) **não** conflitam — uma reserva das 8h às 10h convive com outra das 10h às 12h. |
| **RN-03** | Todo intervalo deve ter `início < fim`. |
| **RN-04** | Todo intervalo solicitado deve começar no futuro. |

### 5.2 Admissão da reserva

| ID | Regra |
|---|---|
| **RN-05** | Espaço inativo não aceita novas reservas. |
| **RN-06** | O número de participantes não pode exceder a capacidade do espaço. |
| **RN-07** | A política associada ao tipo do espaço determina o **status inicial** da reserva e as restrições adicionais aplicáveis. |

### 5.3 Políticas por tipo de espaço

| ID | Tipo | Política | Aprovação | Antecedência mínima | Regra adicional |
|---|---|---|---|---|---|
| **RN-08** | `CLASSROOM` | `OpenAccessPolicy` | automática | — | teto de 8h por solicitante na semana |
| **RN-09** | `LAB` | `ManagedAccessPolicy` | gestor | 24h | duração máxima de 4h |
| **RN-10** | `AUDITORIUM` | `RestrictedAccessPolicy` | gestor | 72h | mínimo de 20 participantes |

Detalhamento do teto semanal (RN-08): somam-se as horas das reservas **ativas** do mesmo solicitante
em espaços do tipo `CLASSROOM` cuja data de início cai na mesma **semana ISO** (segunda a domingo) da
reserva solicitada, incluindo a reserva em análise. Se a soma ultrapassar 8 horas, a solicitação é
recusada.

> **Racional das políticas.** Sala de aula é recurso abundante e de baixo risco — barreira mínima.
> Laboratório tem equipamento caro e precisa de preparo — exige aval humano e aviso prévio de um dia.
> Auditório é recurso único no campus — só se justifica para eventos de porte, com três dias de
> antecedência para logística. As regras são o que **varia**, e é essa variação que o padrão Strategy
> isola ([ADR-0004](ADRs/0004-strategy-politicas-de-reserva.md)).

### 5.4 Ciclo de vida e autorização

| ID | Regra |
|---|---|
| **RN-11** | Somente o `MANAGER` aprova ou rejeita uma reserva. |
| **RN-12** | O cancelamento é permitido ao próprio solicitante da reserva ou a qualquer `MANAGER`. |
| **RN-13** | As transições de estado obedecem estritamente à tabela da seção 5.5. Qualquer outra tentativa é rejeitada. |
| **RN-14** | A rejeição exige um motivo não vazio. |
| **RN-15** | Toda transição de estado bem-sucedida publica um evento de domínio. |
| **RN-16** | O `code` de um espaço é único no sistema. |

### 5.5 Tabela de transições de estado

| Estado atual | `approve` | `reject` | `cancel` |
|---|---|---|---|
| `PENDING` | ✅ → `APPROVED` | ✅ → `REJECTED` | ✅ → `CANCELLED` |
| `APPROVED` | ❌ | ❌ | ✅ → `CANCELLED` |
| `REJECTED` | ❌ | ❌ | ❌ |
| `CANCELLED` | ❌ | ❌ | ❌ |

Uma célula ❌ significa que o domínio levanta `InvalidStateTransition`, traduzido em `409 Conflict`
na borda HTTP. `REJECTED` e `CANCELLED` são **estados terminais**.

> Esta tabela aparece de forma idêntica em [ADR-0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md) e
> no diagrama de estados de [ARQUITETURA.md](ARQUITETURA.md#5-máquina-de-estados-da-reserva).
> As três representações precisam permanecer sincronizadas.

## 6. Casos de uso

### UC-01 — Cadastrar espaço
**Ator:** Gestor
**Fluxo principal:** o gestor informa código, nome, tipo e capacidade → o sistema valida a unicidade
do código (RN-16) e a capacidade positiva → o espaço é persistido como ativo.
**Alternativo:** código já existente → `409 Conflict`.

### UC-02 — Listar espaços
**Ator:** Solicitante ou Gestor
**Fluxo principal:** o sistema devolve os espaços cadastrados, com filtro opcional por tipo e por
situação (ativo/inativo).
**Variante:** informado um código, o sistema devolve aquele espaço; código inexistente → `404`.

### UC-03 — Consultar agenda e disponibilidade
**Ator:** Solicitante ou Gestor
**Fluxo principal:** informado um espaço e uma data, o sistema devolve as reservas ativas daquele
dia, permitindo identificar as faixas livres antes de solicitar.
**Variante:** informado o identificador de uma reserva, o sistema a devolve — é como o solicitante
acompanha a decisão do gestor. Identificador inexistente → `404`.

### UC-04 — Solicitar reserva
**Ator:** Solicitante
**Fluxo principal:**
1. O solicitante informa espaço, intervalo, finalidade e número de participantes.
2. O sistema valida o intervalo (RN-03, RN-04).
3. Verifica se o espaço existe e está ativo (RN-05).
4. Verifica a capacidade (RN-06).
5. Verifica conflito com reservas ativas do espaço (RN-01, RN-02).
6. Resolve a política do tipo do espaço e aplica suas restrições (RN-07 a RN-10).
7. Cria a reserva no status inicial definido pela política.
8. Publica `BookingRequested` (RN-15).

**Alternativos:** conflito de horário → `409`; violação de política → `422`; espaço inexistente →
`404`.

> Este é o fluxo em que os três design patterns atuam em conjunto. O diagrama de sequência em
> [ARQUITETURA.md](ARQUITETURA.md#9-sequência--solicitar-reserva) mostra a colaboração.

### UC-05 — Aprovar reserva
**Ator:** Gestor
**Fluxo principal:** o gestor aprova uma reserva `PENDING` → o sistema revalida o conflito (outra
reserva pode ter sido aprovada no intervalo desde a solicitação) → transiciona para `APPROVED` →
registra `decided_by` e `decided_at` → publica `BookingApproved`.
**Alternativos:** reserva não está `PENDING` → `409` (RN-13); papel não é gestor → `403` (RN-11);
surgiu conflito → `409`.

### UC-06 — Rejeitar reserva
**Ator:** Gestor
**Fluxo principal:** o gestor rejeita uma reserva `PENDING` informando o motivo (RN-14) → estado vai
para `REJECTED` → publica `BookingRejected`.
**Alternativos:** motivo vazio → `422`; reserva não está `PENDING` → `409`; papel não é gestor →
`403`.

### UC-07 — Cancelar reserva
**Ator:** Solicitante (a própria reserva) ou Gestor (qualquer)
**Fluxo principal:** reserva em `PENDING` ou `APPROVED` transiciona para `CANCELLED` → publica
`BookingCancelled` → o intervalo volta a ficar livre para novas solicitações.
**Alternativos:** solicitante tentando cancelar reserva alheia → `403` (RN-12); reserva em estado
terminal → `409` (RN-13).

## 7. Contratos da API REST

Todas as rotas aceitam os cabeçalhos de identidade `X-User-Id` e `X-User-Role`
(`REQUESTER` | `MANAGER`). Datas e horas trafegam em ISO 8601.

| Método | Rota | Papel exigido | Caso de uso |
|---|---|---|---|
| `POST` | `/spaces` | `MANAGER` | UC-01 |
| `GET` | `/spaces` | qualquer | UC-02 |
| `GET` | `/spaces/{code}` | qualquer | UC-02 |
| `GET` | `/spaces/{code}/availability?date=YYYY-MM-DD` | qualquer | UC-03 |
| `POST` | `/bookings` | qualquer | UC-04 |
| `GET` | `/bookings` | qualquer | UC-03 |
| `GET` | `/bookings/{id}` | qualquer | UC-03 |
| `POST` | `/bookings/{id}/approval` | `MANAGER` | UC-05 |
| `POST` | `/bookings/{id}/rejection` | `MANAGER` | UC-06 |
| `POST` | `/bookings/{id}/cancellation` | `REQUESTER` ou `MANAGER` | UC-07 |
| `GET` | `/notifications` | qualquer | demonstração do Observer |
| `GET` | `/health` | — | verificação operacional |

As transições de estado são modeladas como **sub-recursos criados por `POST`**
(`/approval`, `/rejection`, `/cancellation`) em vez de um `PATCH /bookings/{id}` com o novo status no
corpo. O motivo é semântico: aprovar não é editar um campo, é executar uma transição que o domínio
pode recusar. A rota nomeia a intenção, e o verbo `POST` comunica que a operação não é idempotente
nem um simples `set`.

### 7.1 Exemplo — solicitar reserva

```http
POST /bookings
X-User-Id: 2019001234
X-User-Role: REQUESTER
Content-Type: application/json

{
  "space_code": "LAB-01",
  "start_at": "2026-08-20T14:00:00",
  "end_at": "2026-08-20T16:00:00",
  "purpose": "Aula prática de Redes de Computadores",
  "attendees": 25
}
```

```http
201 Created

{
  "id": "8f3a1c22-5d4e-4b8a-9f01-2c6e7d8a9b10",
  "space_code": "LAB-01",
  "requester_id": "2019001234",
  "start_at": "2026-08-20T14:00:00",
  "end_at": "2026-08-20T16:00:00",
  "purpose": "Aula prática de Redes de Computadores",
  "attendees": 25,
  "status": "PENDING",
  "created_at": "2026-08-05T09:12:33"
}
```

### 7.2 Tradução de erros de domínio para HTTP

A camada de apresentação é a **única** que conhece códigos HTTP. O domínio levanta erros tipados; um
tratador central os traduz.

| Erro de domínio | HTTP | Origem |
|---|---|---|
| `SpaceNotFound`, `BookingNotFound` | `404` | identificador inexistente |
| `DuplicateSpaceCode` | `409` | RN-16 |
| `ScheduleConflict` | `409` | RN-01, RN-02 |
| `InvalidStateTransition` | `409` | RN-13 |
| `InactiveSpace` | `422` | RN-05 |
| `CapacityExceeded` | `422` | RN-06 |
| `PolicyViolation` | `422` | RN-08, RN-09, RN-10 |
| `InvalidTimeSlot` | `422` | RN-03, RN-04 |
| `MissingRejectionReason` | `422` | RN-14 |
| `PermissionDenied` | `403` | RN-11, RN-12 |

A distinção entre `409` e `422` é deliberada: **409** sinaliza conflito com o estado atual do
recurso — repetir a requisição depois pode funcionar. **422** sinaliza requisição bem formada porém
semanticamente inadmissível — repetir sem mudar os dados nunca vai funcionar.

Toda resposta de erro tem o mesmo formato:

```json
{
  "error": "ScheduleConflict",
  "message": "O espaço LAB-01 já possui reserva ativa entre 14:00 e 16:00 em 20/08/2026.",
  "rule": "RN-01"
}
```

O campo `rule` liga a resposta HTTP de volta à regra desta especificação — rastreabilidade que
funciona em tempo de execução.

## 8. Estrutura de código

A árvore abaixo materializa as quatro camadas do
[ADR-0001](ADRs/0001-arquitetura-em-camadas.md). É a estrutura-alvo; será criada pelas tasks de
implementação.

```
src/agendalab/
├── domain/                     ← regras de negócio puras; não importa nada externo
│   ├── entities/
│   │   ├── space.py            Space, SpaceKind
│   │   └── booking.py          Booking, BookingStatus
│   ├── value_objects/
│   │   └── time_slot.py        TimeSlot — RN-02, RN-03
│   ├── states/                 ← padrão State
│   │   ├── booking_state.py    BookingState (abstrata)
│   │   └── concrete_states.py  Pending, Approved, Rejected, Cancelled
│   ├── policies/               ← padrão Strategy
│   │   ├── booking_policy.py   BookingPolicy (interface) + PolicyContext
│   │   ├── open_access.py      OpenAccessPolicy — RN-08
│   │   ├── managed_access.py   ManagedAccessPolicy — RN-09
│   │   ├── restricted_access.py RestrictedAccessPolicy — RN-10
│   │   └── registry.py         mapa tipo → política
│   ├── events/                 ← padrão Observer
│   │   ├── booking_events.py   BookingRequested, BookingApproved, ...
│   │   └── publisher.py        EventPublisher (sujeito) + EventObserver (interface)
│   ├── actor.py                Actor, Role — quem age sobre uma reserva
│   ├── repositories.py         SpaceRepository, BookingRepository — INTERFACES
│   └── errors.py               hierarquia de erros de domínio
│
├── application/                ← orquestra o domínio; depende só dele
│   ├── dto.py
│   └── use_cases/
│       ├── register_space.py       UC-01
│       ├── list_spaces.py          UC-02
│       ├── get_space.py            UC-02 — variante por código
│       ├── check_availability.py   UC-03
│       ├── get_booking.py          UC-03 — variante por identificador
│       ├── request_booking.py      UC-04
│       ├── approve_booking.py      UC-05
│       ├── reject_booking.py       UC-06
│       └── cancel_booking.py       UC-07
│
├── infrastructure/             ← IMPLEMENTA as interfaces do domínio
│   ├── persistence/
│   │   ├── database.py         engine e sessão SQLAlchemy
│   │   ├── models.py           tabelas (separadas das entidades de domínio)
│   │   ├── mappers.py          conversão ORM ↔ domínio
│   │   └── sqlalchemy_repositories.py
│   └── notifications/
│       ├── notification.py     evento de domínio → mensagem legível, num lugar só
│       ├── log_notifier.py     observador que registra em log
│       └── inbox.py            caixa de entrada consultável em memória
│
└── presentation/               ← camada mais externa; faz o wiring de tudo
    ├── main.py                 cria a aplicação FastAPI
    ├── dependencies.py         injeção de dependências e identidade da requisição
    ├── error_handlers.py       erros de domínio → HTTP (seção 7.2)
    └── api/
        ├── schemas.py          contratos de requisição e resposta (Pydantic)
        ├── spaces.py
        ├── bookings.py
        └── notifications.py
```

```
tests/
├── architecture/
│   └── test_dependency_rule.py   verifica a regra de dependência por análise de imports
├── doubles/                       repositórios em memória — duplas de teste, não produção
├── unit/                          domínio puro, sem I/O
├── integration/                   repositórios contra SQLite
└── e2e/                           API completa via TestClient
```

O ponto que sustenta toda a arquitetura: **`repositories.py` fica em `domain/`, não em
`infrastructure/`**. O domínio declara o que precisa; a infraestrutura obedece. É por isso que a
seta de dependência da infraestrutura aponta para dentro, e é por isso que o domínio inteiro roda em
teste sem banco.

## 9. Requisitos não funcionais

| ID | Requisito | Como é verificado |
|---|---|---|
| **RNF-01** | O pacote `domain` não importa `application`, `infrastructure`, `presentation` nem bibliotecas de I/O | `tests/architecture/test_dependency_rule.py` |
| **RNF-02** | O pacote `application` não importa `infrastructure` nem `presentation` | mesmo teste |
| **RNF-03** | Cobertura de testes ≥ 85% em `domain/` e `application/` | `pytest --cov` |
| **RNF-04** | A aplicação sobe com um único comando, sem serviço externo | seção "Como executar" do [README](../README.md) |
| **RNF-05** | Toda resposta de erro segue o formato único da seção 7.2 | testes ponta a ponta |
| **RNF-06** | A documentação interativa da API fica disponível em `/docs` | inspeção manual, com captura na defesa |

## 10. Rastreabilidade

| Assunto | ADR | Diagrama | Verificação |
|---|---|---|---|
| Camadas e regra de dependência | [ADR-0001](ADRs/0001-arquitetura-em-camadas.md) | [C4 N3](ARQUITETURA.md#3-c4-nível-3--componentes), [Camadas](ARQUITETURA.md#4-camadas-e-regra-de-dependência) | `tests/architecture/` |
| Stack | [ADR-0002](ADRs/0002-stack-python-fastapi.md) | [C4 N2](ARQUITETURA.md#2-c4-nível-2--container) | — |
| Persistência e Repository | [ADR-0003](ADRs/0003-persistencia-sqlite-repository.md) | [ER](ARQUITETURA.md#10-modelo-entidade-relacionamento) | `tests/integration/` |
| RN-07 a RN-10 (Strategy) | [ADR-0004](ADRs/0004-strategy-politicas-de-reserva.md) | [Classes Strategy](ARQUITETURA.md#6-classes--strategy-das-políticas) | `tests/unit/policies/` |
| RN-13 (State) | [ADR-0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md) | [Estados](ARQUITETURA.md#5-máquina-de-estados-da-reserva), [Classes State](ARQUITETURA.md#7-classes--state-da-reserva) | `tests/unit/states/` |
| RN-15 (Observer) | [ADR-0006](ADRs/0006-observer-notificacoes.md) | [Classes Observer](ARQUITETURA.md#8-classes--observer-de-eventos) | `tests/unit/events/` |
| RN-11, RN-12 (autorização) | [ADR-0007](ADRs/0007-autenticacao-fora-de-escopo.md) | — | `tests/e2e/` |
| Documentação como código | [ADR-0008](ADRs/0008-documentacao-e-diagramas-como-codigo.md) | todos | renderização no GitHub |
| RNF-01 a RNF-03 | [ADR-0009](ADRs/0009-estrategia-de-testes.md) | — | `pytest --cov` |
