# ADR-0005: Aplicar o padrão State ao ciclo de vida da reserva

| | |
|---|---|
| **Status** | **Aceito** |
| **Data** | 05/08/2026 |
| **Decisor** | Luiz Cutrim |
| **Tags** | `design-pattern`, `state`, `domínio`, `ciclo-de-vida` |
| **Relacionados** | [ADR-0001](0001-arquitetura-em-camadas.md), [ADR-0004](0004-strategy-politicas-de-reserva.md), [ADR-0006](0006-observer-notificacoes.md) |

## Contexto

Uma reserva no AgendaLab passa por quatro situações, e nem toda operação é válida em todas elas
([ESPECIFICACAO §5.5](../ESPECIFICACAO.md#55-tabela-de-transições-de-estado)):

| Estado atual | `approve` | `reject` | `cancel` |
|---|---|---|---|
| `PENDING` | ✅ → `APPROVED` | ✅ → `REJECTED` | ✅ → `CANCELLED` |
| `APPROVED` | ❌ | ❌ | ✅ → `CANCELLED` |
| `REJECTED` | ❌ | ❌ | ❌ |
| `CANCELLED` | ❌ | ❌ | ❌ |

Aprovar uma reserva já rejeitada é um erro de negócio, não um caso de borda técnico — e o sistema
precisa recusá-lo com clareza, seja qual for o caminho pelo qual a chamada chegou.

Um detalhe que se revelou determinante para o desenho: **o estado governa mais do que a transição**.

- Só reservas `PENDING` e `APPROVED` ocupam o horário para efeito da detecção de conflito (RN-01).
  Uma reserva cancelada libera o intervalo.
- A rejeição exige um motivo (RN-14); a aprovação e o cancelamento, não.
- Cada transição registra `decided_by` e `decided_at`; cada uma publica um evento diferente
  ([ADR-0006](0006-observer-notificacoes.md)).

Ou seja: a pergunta "esta transição é permitida?" é apenas uma das perguntas que dependem do estado.

## Alternativas consideradas

### A) Enumeração com condicionais nos casos de uso

```python
if booking.status != BookingStatus.PENDING:
    raise InvalidStateTransition(...)
booking.status = BookingStatus.APPROVED
```

**Prós:** o caminho mais direto; nenhuma classe nova; o fluxo inteiro visível no caso de uso.
**Contras:** a mesma verificação se repete em `ApproveBooking`, `RejectBooking` e `CancelBooking`,
cada uma com sua variação — e nada impede que uma delas seja esquecida ou fique divergente. A regra
de ciclo de vida, que é uma só, ficaria distribuída por três arquivos da camada de aplicação, quando
pertence ao domínio. Um estado novo exigiria revisar todos os pontos.
**Veredito:** rejeitada. Espalha uma regra coesa por vários módulos, e na camada errada.

### B) Tabela de transições declarativa

```python
TRANSICOES = {
    (PENDING, "approve"): APPROVED,
    (PENDING, "reject"): REJECTED,
    ...
}
```

**Prós:** compacta, declarativa e legível — a tabela do Contexto vira código quase literalmente.
Fácil de testar exaustivamente. Honestamente, para responder *apenas* "esta transição é permitida?",
é a solução mais limpa das avaliadas.
**Contras:** resolve só a primeira das três perguntas que dependem do estado. Ela não expressa que
`REJECTED` não ocupa horário, nem que a rejeição exige motivo. Esses comportamentos voltariam como
condicionais sobre o estado, espalhadas fora da tabela — e o sistema acabaria com a regra de ciclo de
vida em dois lugares: a tabela para transições, e ifs para todo o resto.
**Veredito:** rejeitada, e é a alternativa mais próxima de ter sido escolhida. Seria a decisão certa
se transição fosse a única coisa que o estado determina.

### C) Biblioteca de máquina de estados (`transitions`, `python-statemachine`)

**Prós:** máquina de estados pronta e testada; sintaxe declarativa; recursos como *hooks* de entrada
e saída.
**Contras:** adiciona dependência externa para um problema de quatro estados e três eventos. O
domínio passaria a depender de biblioteca de terceiros, contrariando o
[ADR-0001](0001-arquitetura-em-camadas.md). E a defesa deslocaria o foco: em vez de explicar o
desenho, explicaríamos a configuração de uma biblioteca.
**Veredito:** rejeitada.

### D) State — **escolhida**

Uma classe por estado, cada uma respondendo pelas operações válidas naquele ponto do ciclo.

**Veredito:** escolhida.

## Decisão

Aplicamos o padrão **State** ao ciclo de vida da reserva.

A interface, em `domain/states/booking_state.py`:

```python
class BookingState(ABC):
    @abstractmethod
    def status(self) -> BookingStatus: ...

    def approve(self, booking: Booking, actor: Actor) -> None:
        raise InvalidStateTransition(self.status(), "approve")

    def reject(self, booking: Booking, actor: Actor, reason: str) -> None:
        raise InvalidStateTransition(self.status(), "reject")

    def cancel(self, booking: Booking, actor: Actor) -> None:
        raise InvalidStateTransition(self.status(), "cancel")
```

**A recusa é o comportamento padrão da classe base; cada estado concreto sobrescreve apenas as
transições que permite.** Isso inverte o ônus da escrita: `RejectedState` e `CancelledState` não
precisam declarar nada, e um estado novo é seguro por omissão — se o autor esquecer de habilitar uma
transição, o sistema recusa, em vez de permitir indevidamente.

Quatro implementações: `PendingState`, `ApprovedState`, `RejectedState` e `CancelledState`.

`Booking` delega — não decide:

```python
def approve(self, actor: Actor) -> None:
    self._state.approve(self, actor)
```

O `status` persistido continua sendo um `BookingStatus` simples ([ADR-0003](0003-persistencia-sqlite-repository.md));
o mapper reconstrói o objeto de estado correspondente ao carregar a reserva do banco. O padrão vive
no domínio, e não vaza para o esquema.

## Consequências

### Positivas

- **A regra de ciclo de vida existe em um só lugar.** A tabela do Contexto tem correspondência
  direta e completa em quatro classes pequenas.
- **Transição inválida é impossível de esquecer.** A recusa é o padrão herdado; permitir é que exige
  ação explícita.
- **Os casos de uso ficam magros.** `ApproveBooking` carrega a reserva, chama `booking.approve(actor)`
  e persiste. Não verifica estado, porque não é a sua responsabilidade.
- **Um estado novo é uma classe nova.** Acrescentar `CONCLUDED` (reserva já utilizada) não exige
  tocar em nenhum estado existente nem em nenhum caso de uso.
- **Cada estado é testável em isolamento**, sem construir reserva completa nem tocar em banco.

### Trade-offs aceitos

- **Mais classes do que a tabela declarativa exigiria.** Quatro arquivos onde um dicionário de sete
  linhas resolveria a questão das transições. Pagamos isso pelos outros comportamentos que dependem
  do estado — e reconhecemos que, se transição fosse tudo, a alternativa B seria a escolha melhor.
- **Indireção na leitura.** Quem lê `booking.approve()` não vê imediatamente o que acontece; precisa
  saber que existe um estado por trás. É o custo do polimorfismo, mitigado pelo diagrama de estados
  em [ARQUITETURA §5](../ARQUITETURA.md#5-máquina-de-estados-da-reserva).
- **Reconstrução do estado ao carregar do banco.** O mapper precisa converter `BookingStatus` em
  objeto de estado. Um estado novo exige lembrar de registrá-lo nessa conversão.

### Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **Estado novo esquecido no mapper**, quebrando o carregamento em tempo de execução | Média | Teste que percorre todos os membros de `BookingStatus` e afirma que cada um tem estado correspondente na conversão. |
| **Transições divergindo da especificação** ao longo da implementação | Média | `tests/unit/states/test_transitions.py` percorre o produto cartesiano de 4 estados × 3 operações — as 12 células da tabela — e afirma o resultado de cada uma. A tabela do Contexto vira teste, célula por célula. |
| **Estados acumulando responsabilidade alheia** (persistência, notificação) e virando classes gordas | Baixa | Os estados só transicionam e definem invariantes. A publicação de eventos é do `Booking` ([ADR-0006](0006-observer-notificacoes.md)); a persistência é do repositório. |

## Conformidade

- **`src/agendalab/domain/states/`** — a interface e as quatro implementações concretas.
- **`src/agendalab/application/use_cases/approve_booking.py`**, `reject_booking.py` e
  `cancel_booking.py` — nenhum deles deve comparar `booking.status` para decidir se prossegue. Se um
  `if booking.status == ...` aparecer nesses arquivos, a decisão foi violada.
- **`tests/unit/states/test_transitions.py`** — cobre as 12 células da tabela de transições: as 6
  permitidas e as 6 recusadas.
- **`tests/unit/states/test_estado_persistido.py`** — afirma que todo `BookingStatus` tem estado
  correspondente na reconstrução.
- **Diagramas:** [ARQUITETURA §5 — Máquina de estados](../ARQUITETURA.md#5-máquina-de-estados-da-reserva)
  e [§7 — Classes, State](../ARQUITETURA.md#7-classes--state-da-reserva).

## Referências

- [ESPECIFICACAO §5.5 — Tabela de transições de estado](../ESPECIFICACAO.md#55-tabela-de-transições-de-estado)
- [ARQUITETURA §5 — Máquina de estados da reserva](../ARQUITETURA.md#5-máquina-de-estados-da-reserva)
- Gamma, Helm, Johnson e Vlissides, *Design Patterns* (1994) — State
