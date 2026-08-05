# Visões Arquiteturais — AgendaLab

| | |
|---|---|
| **Sistema** | AgendaLab — reserva de salas e laboratórios |
| **Autor** | Luiz Cutrim — Ciência da Computação — UFMA |
| **Data** | 05/08/2026 |
| **Notação** | C4 Model (Níveis 1 a 3) e UML, escritos em Mermaid.js |

Todos os diagramas deste documento são **gerados a partir de código-fonte** versionado junto com o
projeto — não há imagem binária a manter em sincronia. A decisão e seus trade-offs estão em
[ADR-0008](ADRs/0008-documentacao-e-diagramas-como-codigo.md).

> **Nota sobre a notação C4.** Os diagramas C4 abaixo usam `flowchart` com a paleta e a convenção
> visual do C4 Model, e não as diretivas `C4Context`/`C4Container`/`C4Component` nativas do Mermaid.
> A escolha foi tomada após teste: as diretivas nativas são marcadas como experimentais e seu
> auto-layout produziu sobreposição de rótulos sobre as caixas, comprometendo a legibilidade. O
> registro completo está em [ADR-0008](ADRs/0008-documentacao-e-diagramas-como-codigo.md).

**Legenda de cores** (padrão C4): azul-escuro = pessoa · azul = sistema em foco · cinza = sistema
externo · azul-claro = componente · verde = componente da camada de domínio.

---

## 1. C4 Nível 1 — Contexto

Quem usa o AgendaLab e com o que ele conversa. Nenhum detalhe interno aparece aqui — é a visão que
um coordenador de curso entenderia.

```mermaid
flowchart TB
    requester["Solicitante<br>[Pessoa]<br><br>Aluno ou professor que<br>precisa usar um espaço"]
    manager["Gestor de espaços<br>[Pessoa]<br><br>Responsável que cadastra espaços<br>e decide sobre as solicitações"]

    sistema["AgendaLab<br>[Sistema de software]<br><br>Registra espaços, recebe solicitações de reserva,<br>detecta conflitos de horário e aplica a política<br>de admissão de cada tipo de espaço"]

    canal["Canal de notificação<br>[Sistema externo]<br><br>Log da aplicação e caixa de entrada<br>consultável; substitui o e-mail no MVP"]

    requester -->|"Solicita, consulta e cancela reservas<br>[HTTP/JSON]"| sistema
    manager -->|"Cadastra espaços; aprova<br>ou rejeita solicitações<br>[HTTP/JSON]"| sistema
    sistema -->|"Publica eventos de reserva<br>[chamada em processo]"| canal

    classDef pessoa fill:#08427B,stroke:#052E56,color:#FFFFFF
    classDef foco fill:#1168BD,stroke:#0B4884,color:#FFFFFF
    classDef externo fill:#999999,stroke:#6B6B6B,color:#FFFFFF

    class requester,manager pessoa
    class sistema foco
    class canal externo
```

O "canal de notificação" é desenhado como sistema externo por honestidade de modelagem: no MVP ele é
implementado dentro do processo (log e caixa de entrada em memória), mas ocupa a posição
arquitetural de um serviço externo de mensageria. Trocá-lo por e-mail real não altera nenhuma outra
caixa deste diagrama — é justamente o que o padrão Observer preserva
([ADR-0006](ADRs/0006-observer-notificacoes.md)).

## 2. C4 Nível 2 — Container

As unidades executáveis e de armazenamento do sistema.

```mermaid
flowchart TB
    requester["Solicitante<br>[Pessoa]"]
    manager["Gestor de espaços<br>[Pessoa]"]

    subgraph sistema["Sistema AgendaLab"]
        api["API AgendaLab<br>[Container: Python 3.12 + FastAPI]<br><br>Expõe os sete casos de uso por HTTP<br>e publica a documentação interativa em /docs"]
        notif["Notificadores<br>[Container: componentes em processo]<br><br>Observadores alimentados pelos eventos<br>de domínio: log e caixa de entrada consultável"]
        db[("Banco de reservas<br>[Container: SQLite via SQLAlchemy]<br><br>Persiste espaços e reservas<br>em arquivo local")]
    end

    requester -->|"Solicita, cancela e consulta<br>reservas e notificações<br>[HTTP/JSON]"| api
    manager -->|"Cadastra espaços;<br>aprova ou rejeita<br>[HTTP/JSON]"| api
    api -->|"Lê e grava<br>[SQL]"| db
    api -->|"Publica eventos de reserva<br>[chamada em processo]"| notif

    classDef pessoa fill:#08427B,stroke:#052E56,color:#FFFFFF
    classDef container fill:#438DD5,stroke:#2E6295,color:#FFFFFF
    classDef limite fill:#FFFFFF,stroke:#444444,stroke-dasharray:6 4,color:#444444

    class requester,manager pessoa
    class api,notif,db container
    class sistema limite
```

São três containers, e essa contagem é deliberadamente baixa. O sistema é um **monólito modular**:
um único processo, um único banco em arquivo. A alternativa de microsserviços foi avaliada e
rejeitada — o argumento está em [ADR-0001](ADRs/0001-arquitetura-em-camadas.md). Os "Notificadores"
aparecem como container separado porque são um ponto de extensão previsto, ainda que hoje rodem no
mesmo processo.

## 3. C4 Nível 3 — Componentes

O interior da API, agrupado pelas quatro camadas. Este nível vai além do que o enunciado exige, mas
é onde a arquitetura fica de fato verificável.

```mermaid
flowchart TB
    externo["Solicitante / Gestor<br>[Pessoa]"]

    subgraph api["Container: API AgendaLab"]
        direction TB

        subgraph capaP["Camada de Apresentação"]
            routers["Routers HTTP<br>[Componente]<br>spaces, bookings, notifications"]
            errors["Tradutor de erros<br>[Componente]<br>erro de domínio para código HTTP"]
            wiring["Composição de dependências<br>[Componente]<br>monta os casos de uso"]
        end

        subgraph capaA["Camada de Aplicação"]
            usecases["Casos de uso<br>[Componente]<br>UC-01 a UC-07"]
        end

        subgraph capaD["Camada de Domínio"]
            entities["Entidades e objetos de valor<br>[Componente]<br>Space, Booking, TimeSlot"]
            policies["Políticas de reserva<br>[Componente — Strategy]<br>OpenAccess, ManagedAccess, RestrictedAccess"]
            states["Estados da reserva<br>[Componente — State]<br>Pending, Approved, Rejected, Cancelled"]
            events["Publicador de eventos<br>[Componente — Observer]<br>EventPublisher e EventObserver"]
            ports["Interfaces de repositório<br>[Componente]<br>SpaceRepository, BookingRepository"]
        end

        subgraph capaI["Camada de Infraestrutura"]
            repos["Repositórios SQLAlchemy<br>[Componente]<br>implementam as interfaces do domínio"]
            notifiers["Observadores concretos<br>[Componente]<br>LogNotifier, NotificationInbox"]
        end
    end

    db[("Banco de reservas<br>[Container: SQLite]")]

    externo -->|"HTTP/JSON"| routers
    routers --> errors
    routers --> usecases
    wiring -.->|"injeta implementações"| routers
    usecases --> entities
    usecases --> policies
    usecases --> ports
    usecases --> events
    entities --> states
    repos -.->|"implementa"| ports
    notifiers -.->|"assina"| events
    repos -->|"SQL"| db

    classDef pessoa fill:#08427B,stroke:#052E56,color:#FFFFFF
    classDef componente fill:#85BBF0,stroke:#5D82A8,color:#000000
    classDef dominio fill:#1f6f4a,stroke:#0d3b27,color:#FFFFFF
    classDef banco fill:#438DD5,stroke:#2E6295,color:#FFFFFF
    classDef camada fill:#FAFAFA,stroke:#AAAAAA,color:#333333
    classDef limite fill:#FFFFFF,stroke:#444444,stroke-dasharray:6 4,color:#444444

    class externo pessoa
    class routers,errors,wiring,usecases,repos,notifiers componente
    class entities,policies,states,events,ports dominio
    class db banco
    class capaP,capaA,capaD,capaI camada
    class api limite
```

Duas setas merecem atenção porque são o coração da arquitetura, e ambas estão **tracejadas e
apontando para dentro**:

- `Repositórios SQLAlchemy ⇢ Interfaces de repositório` — a infraestrutura depende do domínio, e não
  o contrário.
- `Observadores concretos ⇢ Publicador de eventos` — o notificador assina; o domínio não conhece
  quem escuta.

## 4. Camadas e regra de dependência

A mesma informação da seção anterior, reduzida ao essencial: quem pode depender de quem.

```mermaid
flowchart TB
    subgraph P["Apresentação — presentation/"]
        P1["Routers FastAPI"]
        P2["Tradutor de erros HTTP"]
        P3["Composição de dependências"]
    end

    subgraph A["Aplicação — application/"]
        A1["Casos de uso UC-01 a UC-07"]
    end

    subgraph D["Domínio — domain/"]
        D1["Entidades e objetos de valor"]
        D2["Políticas — Strategy"]
        D3["Estados — State"]
        D4["Eventos — Observer"]
        D5["Interfaces de repositório"]
    end

    subgraph I["Infraestrutura — infrastructure/"]
        I1["Repositórios SQLAlchemy"]
        I2["Observadores concretos"]
        I3["Banco SQLite"]
    end

    P --> A
    A --> D
    I -. implementa .-> D5
    P -. injeta implementações .-> I

    classDef dominio fill:#1f6f4a,stroke:#0d3b27,color:#ffffff
    classDef externa fill:#2b4c7e,stroke:#16294a,color:#ffffff
    class D,D1,D2,D3,D4,D5 dominio
    class P,A,I,P1,P2,P3,A1,I1,I2,I3 externa
```

**A regra, em uma frase:** nenhuma seta sólida sai do domínio. Ele é o único pacote que não importa
ninguém — e é por isso que roda em teste sem banco, sem FastAPI e sem rede.

A camada de apresentação é o **composition root**: é o único lugar que conhece simultaneamente as
abstrações e as implementações concretas, porque é ela quem as conecta. Isso não viola a regra de
dependência; é o preço, concentrado num único ponto, de mantê-la em todo o resto do sistema.

Esta regra é verificada automaticamente por `tests/architecture/test_dependency_rule.py`, que analisa
os imports de cada módulo por AST e falha se uma camada interna importar uma externa
([RNF-01, RNF-02](ESPECIFICACAO.md#9-requisitos-não-funcionais)).

## 5. Máquina de estados da reserva

Implementa a tabela de transições de
[ESPECIFICACAO §5.5](ESPECIFICACAO.md#55-tabela-de-transições-de-estado) e é a base do
[ADR-0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md).

```mermaid
stateDiagram-v2
    direction LR

    [*] --> PENDING: solicitar — política exige aprovação
    [*] --> APPROVED: solicitar — política de aprovação automática

    PENDING --> APPROVED: approve() por MANAGER
    PENDING --> REJECTED: reject() com motivo
    PENDING --> CANCELLED: cancel()

    APPROVED --> CANCELLED: cancel()

    REJECTED --> [*]
    CANCELLED --> [*]

    note right of REJECTED
        Estado terminal.
        Qualquer transição levanta
        InvalidStateTransition (RN-13)
    end note

    note right of CANCELLED
        Estado terminal.
        O intervalo volta a ficar livre
        para novas solicitações
    end note
```

Note as **duas setas de entrada**: uma reserva pode nascer `PENDING` ou já `APPROVED`, dependendo da
política do tipo de espaço. É o ponto exato em que o Strategy e o State se encontram — a estratégia
escolhe o estado inicial, e o estado governa o que acontece dali em diante.

## 6. Classes — Strategy das políticas

```mermaid
classDiagram
    direction LR

    class BookingPolicy {
        <<interface>>
        +initial_status() BookingStatus
        +validate(request, context) None
    }

    class OpenAccessPolicy {
        -WEEKLY_HOUR_CAP = 8
        +initial_status() APPROVED
        +validate(request, context) None
    }

    class ManagedAccessPolicy {
        -MIN_NOTICE_HOURS = 24
        -MAX_DURATION_HOURS = 4
        +initial_status() PENDING
        +validate(request, context) None
    }

    class RestrictedAccessPolicy {
        -MIN_NOTICE_HOURS = 72
        -MIN_ATTENDEES = 20
        +initial_status() PENDING
        +validate(request, context) None
    }

    class PolicyContext {
        +now datetime
        +space Space
        +requester_week_bookings list~Booking~
    }

    class RequestBooking {
        <<caso de uso>>
        +execute(command) Booking
    }

    BookingPolicy <|.. OpenAccessPolicy : CLASSROOM — RN-08
    BookingPolicy <|.. ManagedAccessPolicy : LAB — RN-09
    BookingPolicy <|.. RestrictedAccessPolicy : AUDITORIUM — RN-10
    RequestBooking ..> BookingPolicy : depende da abstração
    BookingPolicy ..> PolicyContext : recebe
```

`RequestBooking` conhece apenas `BookingPolicy`. Acrescentar um quarto tipo de espaço significa criar
uma classe nova — nenhum arquivo existente é editado. Detalhamento em
[ADR-0004](ADRs/0004-strategy-politicas-de-reserva.md).

## 7. Classes — State da reserva

```mermaid
classDiagram
    direction LR

    class Booking {
        +id UUID
        +space_code str
        +requester_id str
        +slot TimeSlot
        +status BookingStatus
        +approve(actor, now) None
        +reject(actor, reason, now) None
        +cancel(actor, now) None
    }

    class BookingState {
        <<interface>>
        +status() BookingStatus
        +approve(booking, actor, now) None
        +reject(booking, actor, reason, now) None
        +cancel(booking, actor, now) None
    }

    class PendingState {
        +approve() vai para APPROVED
        +reject() vai para REJECTED
        +cancel() vai para CANCELLED
    }

    class ApprovedState {
        +approve() InvalidStateTransition
        +reject() InvalidStateTransition
        +cancel() vai para CANCELLED
    }

    class RejectedState {
        +approve() InvalidStateTransition
        +reject() InvalidStateTransition
        +cancel() InvalidStateTransition
    }

    class CancelledState {
        +approve() InvalidStateTransition
        +reject() InvalidStateTransition
        +cancel() InvalidStateTransition
    }

    BookingState <|.. PendingState
    BookingState <|.. ApprovedState
    BookingState <|.. RejectedState : terminal
    BookingState <|.. CancelledState : terminal
    Booking o-- BookingState : delega a transição
```

`Booking` não decide se uma transição é válida — ela pergunta ao seu estado atual. É a diferença
entre um `if status == ...` replicado em cada caso de uso e uma regra que existe num lugar só.
Detalhamento em [ADR-0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md).

## 8. Classes — Observer de eventos

```mermaid
classDiagram
    direction LR

    class EventPublisher {
        -_observers list~EventObserver~
        +subscribe(observer) None
        +publish(event) None
    }

    class EventObserver {
        <<interface>>
        +handle(event) None
    }

    class BookingEvent {
        <<abstract>>
        +booking_id UUID
        +space_code str
        +requester_id str
        +occurred_at datetime
    }

    class BookingRequested
    class BookingApproved
    class BookingRejected
    class BookingCancelled

    class LogNotifier {
        +handle(event) None
    }

    class NotificationInbox {
        -_messages list
        +handle(event) None
        +all() list~Notification~
    }

    BookingEvent <|-- BookingRequested
    BookingEvent <|-- BookingApproved
    BookingEvent <|-- BookingRejected
    BookingEvent <|-- BookingCancelled

    EventObserver <|.. LogNotifier
    EventObserver <|.. NotificationInbox

    EventPublisher o-- EventObserver : notifica os inscritos
    EventPublisher ..> BookingEvent : distribui
```

O `EventPublisher` vive no domínio; `LogNotifier` e `NotificationInbox` vivem na infraestrutura e
apenas assinam. Um canal novo — e-mail, push, webhook — é uma classe a mais, sem tocar no domínio.
Detalhamento em [ADR-0006](ADRs/0006-observer-notificacoes.md).

## 9. Sequência — solicitar reserva

O fluxo do [UC-04](ESPECIFICACAO.md#uc-04--solicitar-reserva), onde os três padrões colaboram na
mesma operação.

```mermaid
sequenceDiagram
    autonumber
    actor SOL as Solicitante
    participant RT as Router — apresentação
    participant UC as RequestBooking — aplicação
    participant SR as SpaceRepository
    participant BR as BookingRepository
    participant PO as BookingPolicy — Strategy
    participant BK as Booking — State
    participant EP as EventPublisher — Observer
    participant OB as LogNotifier e Inbox

    SOL->>RT: POST /bookings
    RT->>UC: execute(command)

    UC->>SR: find_by_code(space_code)
    SR-->>UC: Space

    Note over UC: valida intervalo, espaço ativo<br/>e capacidade — RN-03 a RN-06

    UC->>BR: find_active_overlapping(space, slot)
    BR-->>UC: reservas conflitantes

    alt existe sobreposição
        UC-->>RT: ScheduleConflict — RN-01
        RT-->>SOL: 409 Conflict
    else intervalo livre
        UC->>PO: resolve a política pelo tipo do espaço
        UC->>PO: validate(request, context)

        alt política recusa
            PO-->>UC: PolicyViolation — RN-08 a RN-10
            UC-->>RT: PolicyViolation
            RT-->>SOL: 422 Unprocessable Entity
        else política aceita
            PO-->>UC: initial_status()
            UC->>BK: cria no estado inicial definido pela política
            UC->>BR: save(booking)
            UC->>EP: publish(BookingRequested)
            EP->>OB: handle(event)
            UC-->>RT: Booking
            RT-->>SOL: 201 Created
        end
    end
```

Observe que `RequestBooking` conversa apenas com **abstrações**: `SpaceRepository`,
`BookingRepository` e `BookingPolicy` são todos contratos declarados no domínio. Em nenhum passo o
caso de uso menciona SQLAlchemy, SQLite ou FastAPI. É por isso que ele é testável isoladamente com
repositórios em memória.

## 10. Modelo entidade-relacionamento

O esquema físico gerado pelos modelos SQLAlchemy — deliberadamente separado das entidades de
domínio, conforme [ADR-0003](ADRs/0003-persistencia-sqlite-repository.md).

```mermaid
erDiagram
    SPACES ||--o{ BOOKINGS : "recebe"

    SPACES {
        string code PK "identificador natural, ex. LAB-01"
        string name "nome legível do espaço"
        string kind "CLASSROOM, LAB ou AUDITORIUM"
        int capacity "máximo de ocupantes"
        bool active "espaço inativo não aceita reservas"
    }

    BOOKINGS {
        uuid id PK
        string space_code FK "referência a SPACES.code"
        string requester_id "matrícula ou e-mail do solicitante"
        datetime start_at "início do intervalo"
        datetime end_at "fim do intervalo"
        string purpose "finalidade declarada"
        int attendees "participantes previstos"
        string status "PENDING, APPROVED, REJECTED ou CANCELLED"
        datetime created_at "momento da solicitação"
        string decided_by "nulo até a decisão"
        datetime decided_at "nulo até a decisão"
        string rejection_reason "obrigatório na rejeição"
    }
```

Não há tabela de usuários — coerente com [ADR-0007](ADRs/0007-autenticacao-fora-de-escopo.md).
`requester_id` e `decided_by` são identificadores opacos, sem integridade referencial, porque não
existe entidade para referenciar.

---

## Índice de rastreabilidade

| Diagrama | Nível/Notação | Documento que o justifica |
|---|---|---|
| [1 — Contexto](#1-c4-nível-1--contexto) | C4 N1 | exigência do enunciado |
| [2 — Container](#2-c4-nível-2--container) | C4 N2 | exigência do enunciado |
| [3 — Componentes](#3-c4-nível-3--componentes) | C4 N3 | [ADR-0001](ADRs/0001-arquitetura-em-camadas.md) |
| [4 — Camadas](#4-camadas-e-regra-de-dependência) | UML informal | [ADR-0001](ADRs/0001-arquitetura-em-camadas.md) |
| [5 — Estados](#5-máquina-de-estados-da-reserva) | UML de estados | [ADR-0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md) |
| [6 — Strategy](#6-classes--strategy-das-políticas) | UML de classes | [ADR-0004](ADRs/0004-strategy-politicas-de-reserva.md) |
| [7 — State](#7-classes--state-da-reserva) | UML de classes | [ADR-0005](ADRs/0005-state-ciclo-de-vida-da-reserva.md) |
| [8 — Observer](#8-classes--observer-de-eventos) | UML de classes | [ADR-0006](ADRs/0006-observer-notificacoes.md) |
| [9 — Sequência](#9-sequência--solicitar-reserva) | UML de sequência | [ESPECIFICACAO UC-04](ESPECIFICACAO.md#uc-04--solicitar-reserva) |
| [10 — ER](#10-modelo-entidade-relacionamento) | Entidade-relacionamento | [ADR-0003](ADRs/0003-persistencia-sqlite-repository.md) |
