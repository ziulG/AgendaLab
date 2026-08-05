# Documento de Defesa — AgendaLab

**Sistema de reserva de salas e laboratórios universitários**

| | |
|---|---|
| **Disciplina** | Arquitetura de Software |
| **Professor** | MSc. Lucas Reis |
| **Autor** | Luiz Cutrim |
| **Curso** | Ciência da Computação |
| **Instituição** | Universidade Federal do Maranhão — UFMA |
| **Repositório** | `> A PREENCHER: URL do repositório no GitHub` |
| **Data de entrega** | 11/08/2026 |

> Este documento corresponde à **Opção B** do material explicativo previsto no enunciado: documento
> textual formal com o passo a passo da explicação do projeto, capturas de tela do sistema rodando,
> trechos do código onde os padrões foram aplicados e a justificativa técnica completa.

> **ESTADO DESTE DOCUMENTO — remover antes da entrega.** O esqueleto e todas as seções de
> justificativa técnica estão escritos. As seções marcadas com `> A PREENCHER` dependem do código
> existir e serão completadas na fase de implementação: trechos de código reais com caminho e linha,
> capturas de tela e saída dos testes.

---

## Sumário

1. [O problema e a solução](#1-o-problema-e-a-solução)
2. [Como executar o sistema](#2-como-executar-o-sistema)
3. [Visões arquiteturais](#3-visões-arquiteturais)
4. [O padrão arquitetural adotado](#4-o-padrão-arquitetural-adotado)
5. [Design pattern 1 — Strategy](#5-design-pattern-1--strategy)
6. [Design pattern 2 — State](#6-design-pattern-2--state)
7. [Design pattern 3 — Observer](#7-design-pattern-3--observer)
8. [Princípios de projeto: as evidências](#8-princípios-de-projeto-as-evidências)
9. [Demonstração do sistema em funcionamento](#9-demonstração-do-sistema-em-funcionamento)
10. [Testes e resultados](#10-testes-e-resultados)
11. [Trade-offs assumidos e o que ficou fora](#11-trade-offs-assumidos-e-o-que-ficou-fora)
12. [Limitações conhecidas e evolução](#12-limitações-conhecidas-e-evolução)
13. [Índice de decisões arquiteturais](#13-índice-de-decisões-arquiteturais)

---

## 1. O problema e a solução

Espaços compartilhados numa universidade — salas de aula, laboratórios, auditório — são disputados.
Sem sistema, a alocação acontece por planilha, grupo de mensagens ou caderno na portaria, e três
problemas decorrem disso: reservas duplicadas descobertas só na hora do uso, regras de liberação que
existem apenas na cabeça de quem controla, e ausência de qualquer rastro de quem pediu e quem
autorizou.

O **AgendaLab** é um MVP que ataca os três: detecta conflito de horário no ato da solicitação, aplica
políticas de admissão distintas por tipo de espaço e mantém a trilha de decisão de cada reserva.

O escopo é deliberadamente estreito — sete casos de uso, listados em
[ESPECIFICACAO §6](ESPECIFICACAO.md#6-casos-de-uso). O que ficou de fora está em
[§11](#11-trade-offs-assumidos-e-o-que-ficou-fora), por decisão registrada e não por omissão.

## 2. Como executar o sistema

> A PREENCHER na implementação: comandos verificados de ponta a ponta, com a saída real de cada um.
> O conteúdo abaixo é a estrutura prevista e será confirmado antes da entrega.

```bash
git clone <URL do repositório>
cd FinalProjectAS
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn agendalab.presentation.main:app --reload
```

Com a aplicação no ar, a documentação interativa fica em `http://127.0.0.1:8000/docs`.

Requisitos: Python 3.12 ou superior. Nenhum serviço externo — o banco é um arquivo SQLite criado na
primeira execução ([ADR-0003](ADRs/0003-persistencia-sqlite-repository.md)).

## 3. Visões arquiteturais

O sistema é documentado pelo **C4 Model** nos níveis 1 (Contexto), 2 (Container) e 3 (Componentes).
Todos os diagramas são gerados por código Mermaid versionado — não há imagem binária a manter em
sincronia ([ADR-0008](ADRs/0008-documentacao-e-diagramas-como-codigo.md)).

Os diagramas completos, com a narrativa de cada visão, estão em
**[ARQUITETURA.md](ARQUITETURA.md)**:

| Visão | Pergunta que responde |
|---|---|
| [Nível 1 — Contexto](ARQUITETURA.md#1-c4-nível-1--contexto) | Quem usa o sistema e com o que ele conversa |
| [Nível 2 — Container](ARQUITETURA.md#2-c4-nível-2--container) | Quais são as unidades executáveis e de armazenamento |
| [Nível 3 — Componentes](ARQUITETURA.md#3-c4-nível-3--componentes) | Como a API se organiza por dentro |
| [Camadas](ARQUITETURA.md#4-camadas-e-regra-de-dependência) | Quem pode depender de quem |

Uma nota metodológica: as diretivas `C4Context`/`C4Container` nativas do Mermaid foram testadas e
descartadas — seu auto-layout sobrepõe os rótulos das relações às caixas, comprometendo a
legibilidade. Os diagramas usam `flowchart` com a paleta e a convenção do C4 Model. O registro do
teste e da decisão está em [ADR-0008](ADRs/0008-documentacao-e-diagramas-como-codigo.md).

## 4. O padrão arquitetural adotado

O AgendaLab adota **arquitetura em camadas com inversão de dependência**, em quatro camadas:

| Camada | Responsabilidade | Pode depender de |
|---|---|---|
| Apresentação | Expor HTTP, traduzir erros, compor as dependências | todas |
| Aplicação | Orquestrar o domínio em casos de uso | domínio |
| Domínio | Regras de negócio e **as interfaces de repositório** | nada |
| Infraestrutura | Implementar as interfaces do domínio | domínio |

### Por que não MVC

MVC é o primeiro padrão citado pelo enunciado e o de vocabulário mais reconhecível. Foi rejeitado por
uma razão concreta: **o sistema não tem View**. A interface é uma API REST, e um dos três componentes
do padrão ficaria vazio ou seria forçado a significar "serializador JSON". O risco maior é conhecido:
na prática do MVC em frameworks web, a regra de negócio migra para os controllers ou para models que
herdam do ORM — e ambos acoplam a regra à infraestrutura, que é exatamente o oposto do que a
disciplina avalia.

### Por que não microsserviços

Duas entidades e sete casos de uso. Não há requisito de escala, times separados ou deploy
independente. Microsserviços introduziriam consistência eventual, comunicação em rede e orquestração
— problemas inteiramente criados pela própria escolha.

### A decisão que sustenta tudo

O detalhe que torna esta arquitetura defensável, e não apenas uma organização de pastas:

> **As interfaces `SpaceRepository` e `BookingRepository` são declaradas em
> `domain/repositories.py`, não na infraestrutura.**

O domínio declara o que precisa; a infraestrutura obedece. A seta de dependência da infraestrutura
aponta *para dentro*. A consequência prática está em [§8](#8-princípios-de-projeto-as-evidências).

Análise completa das alternativas em [ADR-0001](ADRs/0001-arquitetura-em-camadas.md).

## 5. Design pattern 1 — Strategy

**Onde:** `src/agendalab/domain/policies/` · **ADR:** [0004](ADRs/0004-strategy-politicas-de-reserva.md)

### O problema

Cada tipo de espaço tem regras próprias de admissão:

| Tipo | Aprovação | Antecedência mínima | Regra adicional |
|---|---|---|---|
| `CLASSROOM` | automática | — | teto de 8h por solicitante na semana |
| `LAB` | gestor | 24h | duração máxima de 4h |
| `AUDITORIUM` | gestor | 72h | mínimo de 20 participantes |

Essas regras não diferem apenas em parâmetros — diferem em estrutura. "Teto de horas na semana" e
"mínimo de participantes" são verificações de naturezas distintas, sobre dados distintos.

Sem o padrão, o caso de uso `RequestBooking` teria uma condicional por tipo, e passaria a ter três
razões diferentes para mudar. Um quarto tipo de espaço exigiria editar um arquivo já testado.

### A solução

> A PREENCHER: trecho real de `domain/policies/booking_policy.py` com a interface, e de uma política
> concreta, com caminho e linha.

### Diagrama

[ARQUITETURA §6 — Classes, Strategy das políticas](ARQUITETURA.md#6-classes--strategy-das-políticas)

### A evidência

`RequestBooking` não menciona `CLASSROOM`, `LAB` nem `AUDITORIUM` em lugar algum — conversa apenas
com a abstração `BookingPolicy`. Acrescentar um quarto tipo de espaço é criar uma classe; nenhum
arquivo existente muda. É o princípio aberto/fechado com demonstração concreta.

> A PREENCHER: saída dos testes de `tests/unit/policies/`.

### Uma nota sobre honestidade na contagem

A resolução de tipo para política é um dicionário (`POLICY_BY_KIND`). **Não o chamamos de Factory
Method.** É um `dict`, e rotulá-lo com nome de padrão para elevar a contagem de patterns do trabalho
seria inflar o que existe. Os três padrões declarados resolvem problemas reais deste domínio; este
não é um quarto.

## 6. Design pattern 2 — State

**Onde:** `src/agendalab/domain/states/` · **ADR:** [0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md)

### O problema

Uma reserva passa por quatro situações, e nem toda operação é válida em todas elas:

| Estado atual | `approve` | `reject` | `cancel` |
|---|---|---|---|
| `PENDING` | ✅ → `APPROVED` | ✅ → `REJECTED` | ✅ → `CANCELLED` |
| `APPROVED` | ❌ | ❌ | ✅ → `CANCELLED` |
| `REJECTED` | ❌ | ❌ | ❌ |
| `CANCELLED` | ❌ | ❌ | ❌ |

O estado governa mais do que a transição: só reservas `PENDING` e `APPROVED` ocupam o horário para
efeito da detecção de conflito, e só a rejeição exige motivo. A pergunta "esta transição é
permitida?" é apenas uma das perguntas que dependem do estado — e foi isso que descartou a
alternativa de uma tabela declarativa de transições.

### A solução

> A PREENCHER: trecho real de `domain/states/booking_state.py` mostrando que a **recusa é o
> comportamento padrão da classe base**, e de `PendingState` sobrescrevendo apenas o que permite.

O ônus da escrita é invertido: um estado novo é seguro por omissão. Se o autor esquecer de habilitar
uma transição, o sistema recusa — em vez de permitir indevidamente.

### Diagramas

[ARQUITETURA §5 — Máquina de estados](ARQUITETURA.md#5-máquina-de-estados-da-reserva) ·
[§7 — Classes, State](ARQUITETURA.md#7-classes--state-da-reserva)

### A evidência

Os casos de uso `ApproveBooking`, `RejectBooking` e `CancelBooking` não comparam `booking.status` para
decidir se prosseguem. `Booking` delega ao seu estado atual, e a regra de ciclo de vida existe em um
só lugar.

> A PREENCHER: saída de `tests/unit/states/test_transitions.py`, cobrindo as 12 células da tabela.

## 7. Design pattern 3 — Observer

**Onde:** `src/agendalab/domain/events/` e `infrastructure/notifications/` ·
**ADR:** [0006](ADRs/0006-observer-notificacoes.md)

### O problema

Quando uma reserva muda de situação, coisas precisam acontecer: avisar o solicitante, avisar o
gestor, registrar auditoria. Nada disso é a operação de negócio — são reações a ela. São quatro
momentos (solicitação, aprovação, rejeição, cancelamento) e o número de canais tende a crescer.

Chamar o notificador direto do caso de uso faria o número de pontos a editar crescer por
multiplicação: 4 transições × N canais.

### A solução

> A PREENCHER: trecho real de `domain/events/publisher.py` com `EventPublisher` e `EventObserver`, e
> do registro dos observadores em `presentation/dependencies.py`.

Um detalhe de projeto que merece destaque: **falha de observador não derruba a operação de negócio**.
O `publish` isola cada observador — uma reserva legitimamente aprovada não deve ser desfeita porque o
log falhou. Notificação é efeito colateral, e efeito colateral não invalida o fato.

### Diagrama

[ARQUITETURA §8 — Classes, Observer](ARQUITETURA.md#8-classes--observer-de-eventos)

### A evidência

O endpoint `GET /notifications` existe para tornar o padrão visível: aprovar uma reserva e consultar
a caixa de entrada mostra a relação de causa e efeito. Essa decisão — criar um endpoint em favor da
demonstrabilidade — está registrada no ADR em vez de disfarçada.

> A PREENCHER: capturas de tela da sequência aprovar → consultar `/notifications`.

## 8. Princípios de projeto: as evidências

O enunciado avalia **alta coesão, baixo acoplamento e respeito às responsabilidades**. Abaixo, o que
sustenta cada afirmação — evidência verificável, não alegação.

### Baixo acoplamento

> **O domínio inteiro roda em teste sem banco, sem FastAPI e sem rede.**

Não é afirmação de intenção: é propriedade verificável. Os testes de `tests/unit/` não criam arquivo
de banco algum. A camada de aplicação é testada com repositórios em memória que implementam as mesmas
interfaces — o que só é possível porque as interfaces pertencem ao domínio.

A regra de dependência não é convenção: é **restrição executável**.
`tests/architecture/test_dependency_rule.py` analisa os imports de cada módulo por árvore sintática e
falha a suíte se uma camada interna importar uma externa.

> A PREENCHER: saída do teste de arquitetura.

### Alta coesão

Cada unidade tem uma razão para mudar:

| Unidade | Muda quando |
|---|---|
| `ManagedAccessPolicy` | a regra de reserva de laboratórios muda |
| `PendingState` | as transições válidas a partir de "pendente" mudam |
| `TimeSlot` | a definição de sobreposição de intervalos muda |
| `SqlAlchemyBookingRepository` | a forma de persistir muda |

Nenhuma delas muda pelos motivos das outras. A coesão fica visível na própria estrutura de
diretórios: quem procura a regra de conflito de horário encontra em
`domain/value_objects/time_slot.py`, e não espalhada por controllers.

### Respeito às responsabilidades

| Responsabilidade | Onde vive | Onde **não** vive |
|---|---|---|
| Validar formato do JSON | schemas Pydantic, na apresentação | domínio |
| Validar regra de negócio | domínio | apresentação |
| Decidir código HTTP | `presentation/error_handlers.py` | domínio, aplicação |
| Decidir transição válida | classe de estado | casos de uso |
| Decidir admissão da reserva | classe de política | casos de uso |
| Saber SQL | `infrastructure/persistence/` | todo o resto |

O domínio levanta erros tipados próprios (`ScheduleConflict`, `PolicyViolation`); a tradução para
código HTTP acontece em um único arquivo. Nenhuma camada interna sabe o que é um `409`.

## 9. Demonstração do sistema em funcionamento

> A PREENCHER na implementação. Roteiro previsto, com captura de tela a cada passo:

1. Aplicação no ar e Swagger UI em `/docs` — visão geral dos endpoints
2. Cadastro de espaços dos três tipos (`MANAGER`)
3. Reserva de sala de aula — nasce **`APPROVED`** pela política de acesso aberto
4. Reserva de laboratório — nasce **`PENDING`**, exigindo aprovação
5. **Conflito de horário** — segunda reserva no mesmo intervalo recebe `409` (RN-01)
6. **Violação de política** — laboratório com menos de 24h de antecedência recebe `422` (RN-09)
7. **Autorização** — `REQUESTER` tentando aprovar recebe `403` (RN-11)
8. Aprovação pelo gestor — a reserva vai para `APPROVED`
9. **Transição inválida** — aprovar de novo recebe `409` (RN-13)
10. `GET /notifications` — as notificações dos eventos publicados ao longo do roteiro
11. Cancelamento e nova reserva no mesmo horário, agora aceita

Cada passo evidencia uma regra numerada da [especificação](ESPECIFICACAO.md#5-regras-de-negócio).

## 10. Testes e resultados

A suíte é organizada em pirâmide, com um nível a mais no alicerce
([ADR-0009](ADRs/0009-estrategia-de-testes.md)):

| Nível | O que cobre | Toca I/O? |
|---|---|---|
| Arquitetura | a regra de dependência entre camadas | não |
| Unidade | domínio puro: intervalos, políticas, estados, eventos | **não** |
| Integração | repositórios contra SQLite | sim |
| Ponta a ponta | fluxos completos pela API | sim |

O raciocínio por trás dessa escolha: se uma regra de negócio só pode ser testada subindo banco e
servidor HTTP, ela não está desacoplada deles. A dificuldade de testar é o sintoma; o acoplamento é a
doença. A suíte não é apenas rede de segurança — é a evidência da qualidade avaliada.

> A PREENCHER: saída de `pytest -v` e relatório de cobertura.

## 11. Trade-offs assumidos e o que ficou fora

Toda decisão arquitetural custa alguma coisa. Os custos assumidos, com seus registros:

| Trade-off aceito | Em troca de | Registro |
|---|---|---|
| Mais arquivos e indireção que um CRUD exigiria | domínio testável sem infraestrutura | [ADR-0001](ADRs/0001-arquitetura-em-camadas.md) |
| Código de mapeamento ORM ↔ domínio duplicado | domínio livre de SQLAlchemy | [ADR-0003](ADRs/0003-persistencia-sqlite-repository.md) |
| Quatro classes onde um dicionário resolveria as transições | comportamento por estado num só lugar | [ADR-0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md) |
| Fluxo menos rastreável estaticamente | domínio que não conhece canal de notificação | [ADR-0006](ADRs/0006-observer-notificacoes.md) |
| Sistema inseguro por construção | tempo investido no domínio, não em login | [ADR-0007](ADRs/0007-autenticacao-fora-de-escopo.md) |
| Layout de diagrama menos polido | diagrama que envelhece junto com o código | [ADR-0008](ADRs/0008-documentacao-e-diagramas-como-codigo.md) |

Fora de escopo, por decisão registrada: autenticação real, reservas recorrentes, fila de espera,
envio de e-mail, front-end e deploy. O detalhamento está em
[ESPECIFICACAO §2.2](ESPECIFICACAO.md#22-fora-do-escopo).

### Sobre a ausência de autenticação

Vale destacar, porque é a exclusão mais visível. A distinção é entre **autenticação** ("quem é
você?") e **autorização** ("o que você pode fazer?"). A autorização está implementada por inteiro:
RN-11 e RN-12 são aplicadas, e um `REQUESTER` que tente aprovar uma reserva recebe `403`. O que não
existe é verificação de credencial — a identidade é declarada em cabeçalho e o sistema confia nela.

O sistema é, portanto, **inseguro por construção e não deve ser exposto em rede**. Isso é fronteira
desenhada, não defeito descoberto depois.

## 12. Limitações conhecidas e evolução

Limitações que assumimos conscientemente:

- **Corrida de reserva dupla.** A verificação de conflito e a inserção são duas operações; entre
  elas, teoricamente, outra requisição poderia inserir uma sobreposição. Na prática o SQLite
  serializa escritas e a aplicação roda com um worker único, o que fecha a janela. A solução correta
  seria uma restrição de exclusão temporal no banco (disponível no PostgreSQL). Registrado em
  [ADR-0003](ADRs/0003-persistencia-sqlite-repository.md).
- **Evento publicado antes do commit.** Uma falha de persistência posterior à publicação geraria
  notificação de algo revertido. A solução conhecida é o padrão *outbox*. Registrado em
  [ADR-0006](ADRs/0006-observer-notificacoes.md).
- **Caixa de notificações volátil**, em memória. É instrumento de demonstração, não funcionalidade de
  produto.
- **Sem migrações de banco.** Alterar o esquema exige recriá-lo.

O desenho acomoda estas extensões sem reescrita:

| Extensão | Custo | Por quê |
|---|---|---|
| Novo tipo de espaço | uma classe de política | [ADR-0004](ADRs/0004-strategy-politicas-de-reserva.md) |
| Novo canal de notificação | uma classe de observador | [ADR-0006](ADRs/0006-observer-notificacoes.md) |
| Novo estado da reserva | uma classe de estado | [ADR-0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md) |
| Trocar SQLite por PostgreSQL | uma implementação de repositório | [ADR-0003](ADRs/0003-persistencia-sqlite-repository.md) |
| Autenticação real | uma dependência de apresentação | [ADR-0007](ADRs/0007-autenticacao-fora-de-escopo.md) |

Nenhuma dessas linhas toca a camada de domínio. É esse o resultado que a arquitetura foi escolhida
para produzir.

## 13. Índice de decisões arquiteturais

Nove ADRs, cada um com contexto, alternativas genuinamente avaliadas, decisão, consequências e uma
seção de **Conformidade** que aponta o arquivo e o teste que comprovam que a decisão está sendo
respeitada.

| # | Decisão |
|---|---|
| [0001](ADRs/0001-arquitetura-em-camadas.md) | Adotar arquitetura em camadas com inversão de dependência |
| [0002](ADRs/0002-stack-python-fastapi.md) | Implementar em Python com FastAPI e expor apenas API REST |
| [0003](ADRs/0003-persistencia-sqlite-repository.md) | Persistir em SQLite via SQLAlchemy, com Repository e modelos separados |
| [0004](ADRs/0004-strategy-politicas-de-reserva.md) | Aplicar Strategy às políticas de admissão de reserva |
| [0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md) | Aplicar State ao ciclo de vida da reserva |
| [0006](ADRs/0006-observer-notificacoes.md) | Aplicar Observer à notificação de eventos |
| [0007](ADRs/0007-autenticacao-fora-de-escopo.md) | Manter autenticação fora de escopo, implementando a autorização |
| [0008](ADRs/0008-documentacao-e-diagramas-como-codigo.md) | Manter documentação e diagramas como código |
| [0009](ADRs/0009-estrategia-de-testes.md) | Adotar TDD com pirâmide de testes e teste de arquitetura |

Visão das dependências entre as decisões: [índice dos ADRs](ADRs/README.md#como-as-decisões-se-sustentam).

---

## Checklist de preenchimento antes da entrega

- [ ] URL do repositório na capa
- [ ] §2 — comandos verificados de ponta a ponta, com saída real
- [ ] §5, §6, §7 — trechos de código reais, com caminho de arquivo e linha
- [ ] §5, §6, §8 — saída dos testes de políticas, estados e arquitetura
- [ ] §9 — capturas de tela dos 11 passos, salvas em `docs/imagens/`
- [ ] §10 — saída de `pytest -v` e relatório de cobertura
- [ ] Remover o aviso "ESTADO DESTE DOCUMENTO" do topo
- [ ] Remover este checklist
