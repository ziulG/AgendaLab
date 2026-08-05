# Glossário — AgendaLab

A documentação deste projeto é escrita em português e o código em inglês
([ADR-0002](ADRs/0002-stack-python-fastapi.md)). Este documento é a ponte entre os dois: cada termo
do domínio tem exatamente **um** identificador correspondente no código, e nenhum identificador do
código existe sem um termo aqui.

Sinônimos importam. Se durante a implementação surgir a tentação de chamar a mesma coisa de
`Reservation` num arquivo e `Booking` noutro, a resposta está aqui — e o termo vencedor é o desta
tabela.

## Entidades e conceitos centrais

| Termo (PT-BR) | Identificador (código) | Definição |
|---|---|---|
| Espaço | `Space` | Recurso físico reservável: sala de aula, laboratório ou auditório |
| Reserva | `Booking` | Solicitação de uso de um espaço num intervalo determinado |
| Intervalo | `TimeSlot` | Par início/fim de uma reserva; objeto de valor imutável |
| Tipo de espaço | `SpaceKind` | Classificação que determina a política aplicável |
| Situação da reserva | `BookingStatus` | Em qual dos quatro estados a reserva se encontra |
| Solicitante | `requester` / `REQUESTER` | Quem pede o uso do espaço |
| Gestor | `manager` / `MANAGER` | Quem cadastra espaços e decide sobre solicitações |
| Ator | `Actor` | Quem age sobre uma reserva: par identificador + papel, lido dos cabeçalhos de identidade |
| Papel | `Role` | `REQUESTER` ou `MANAGER` — o que o ator tem permissão de fazer (RN-11, RN-12) |
| Capacidade | `capacity` | Número máximo de ocupantes de um espaço |
| Participantes | `attendees` | Número de pessoas previstas para uma reserva |
| Finalidade | `purpose` | Justificativa declarada no pedido de reserva |
| Motivo da rejeição | `rejection_reason` | Texto obrigatório ao rejeitar (RN-14) |
| Trilha de decisão | `decided_by` / `decided_at` | Quem decidiu sobre a reserva e quando |

**Nota sobre `Booking` e não `Reservation`.** Ambos traduzem "reserva". `Booking` venceu por ser mais
curto, por `book` funcionar como verbo natural nos casos de uso, e para evitar a colisão visual com
`reserved`, que em programação carrega outro sentido.

## Tipos de espaço

| Termo (PT-BR) | Identificador | Política associada |
|---|---|---|
| Sala de aula | `CLASSROOM` | `OpenAccessPolicy` — RN-08 |
| Laboratório | `LAB` | `ManagedAccessPolicy` — RN-09 |
| Auditório | `AUDITORIUM` | `RestrictedAccessPolicy` — RN-10 |

## Estados da reserva

| Termo (PT-BR) | Identificador | Terminal? |
|---|---|---|
| Pendente | `PENDING` | não |
| Aprovada | `APPROVED` | não — ainda pode ser cancelada |
| Rejeitada | `REJECTED` | **sim** |
| Cancelada | `CANCELLED` | **sim** |

Grafia: `CANCELLED` com dois `L`, conforme o inglês britânico predominante em vocabulário técnico.
A escolha é arbitrária, mas fixá-la aqui evita a divergência `CANCELED`/`CANCELLED` no código.

## Padrões de projeto e seus papéis

| Termo (PT-BR) | Identificador | Papel no padrão |
|---|---|---|
| Política de reserva | `BookingPolicy` | Interface do **Strategy** |
| Contexto da política | `PolicyContext` | Dados que a política precisa para decidir (hora atual, reservas do solicitante) |
| Estado da reserva | `BookingState` | Interface do **State** |
| Evento de reserva | `BookingEvent` | Mensagem publicada a cada transição |
| Publicador de eventos | `EventPublisher` | Sujeito do **Observer** |
| Observador | `EventObserver` | Interface do observador |
| Caixa de entrada | `NotificationInbox` | Observador que acumula notificações consultáveis |

## Camadas da arquitetura

| Termo (PT-BR) | Pacote | Responsabilidade |
|---|---|---|
| Domínio | `domain` | Regras de negócio puras; não conhece I/O |
| Aplicação | `application` | Orquestra o domínio em casos de uso |
| Infraestrutura | `infrastructure` | Implementa as interfaces declaradas no domínio |
| Apresentação | `presentation` | Expõe a API HTTP e faz a composição das dependências |
| Caso de uso | `use case` | Uma operação completa do sistema, do ponto de vista do ator |
| Repositório | `Repository` | Abstração de coleção que esconde a persistência |

## Erros de domínio

| Situação | Identificador | Regra violada |
|---|---|---|
| Conflito de horário | `ScheduleConflict` | RN-01, RN-02 |
| Intervalo inválido | `InvalidTimeSlot` | RN-03, RN-04 |
| Espaço inativo | `InactiveSpace` | RN-05 |
| Capacidade excedida | `CapacityExceeded` | RN-06 |
| Violação de política | `PolicyViolation` | RN-08, RN-09, RN-10 |
| Transição inválida | `InvalidStateTransition` | RN-13 |
| Motivo ausente | `MissingRejectionReason` | RN-14 |
| Código duplicado | `DuplicateSpaceCode` | RN-16 |
| Permissão negada | `PermissionDenied` | RN-11, RN-12 |
| Espaço inexistente | `SpaceNotFound` | — |
| Reserva inexistente | `BookingNotFound` | — |

## Convenções de nomenclatura

- **Classes:** `PascalCase` — `BookingPolicy`, `TimeSlot`
- **Funções, métodos, variáveis:** `snake_case` — `request_booking`, `start_at`
- **Constantes e membros de enumeração:** `SCREAMING_SNAKE_CASE` — `CLASSROOM`, `PENDING`
- **Arquivos e pacotes:** `snake_case` — `booking_policy.py`
- **Casos de uso:** verbo no imperativo + substantivo — `RequestBooking`, `ApproveBooking`
- **Políticas concretas:** adjetivo + `Access` + `Policy` — `OpenAccessPolicy`
- **Eventos:** substantivo + particípio passado, porque descrevem algo que **já aconteceu** —
  `BookingRequested`, `BookingApproved`
- **Testes:** `test_<comportamento_esperado>` em português quando descrever regra de negócio, para
  que a saída do `pytest` seja legível na defesa — ex.: `test_reserva_com_horario_sobreposto_e_recusada`
