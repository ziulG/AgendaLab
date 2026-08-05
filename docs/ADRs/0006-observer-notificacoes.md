# ADR-0006: Aplicar o padrão Observer à notificação de eventos de reserva

| | |
|---|---|
| **Status** | **Aceito** |
| **Data** | 05/08/2026 |
| **Decisor** | Luiz Cutrim |
| **Tags** | `design-pattern`, `observer`, `domínio`, `eventos` |
| **Relacionados** | [ADR-0001](0001-arquitetura-em-camadas.md), [ADR-0005](0005-state-ciclo-de-vida-da-reserva.md), [ADR-0007](0007-autenticacao-fora-de-escopo.md) |

## Contexto

Quando uma reserva muda de situação, outras coisas precisam acontecer. O solicitante quer saber que
seu pedido foi aprovado. O gestor quer saber que há solicitação pendente. A instituição quer trilha
de auditoria. Nada disso é a operação de negócio em si — são **reações** a ela.

O sistema tem quatro momentos em que isso ocorre, correspondentes às transições de
[ADR-0005](0005-state-ciclo-de-vida-da-reserva.md): solicitação, aprovação, rejeição e cancelamento.

Duas restrições moldam a decisão:

1. **Envio real de mensagem está fora de escopo.** Não há servidor de e-mail, e configurar um
   consumiria tempo em algo que o enunciado não avalia. Mas a notificação precisa ser **visível**,
   porque o documento de defesa depende de capturas de tela que mostrem o efeito acontecendo.
2. **O canal é o que mais deve mudar.** Hoje é log. Amanhã pode ser e-mail, push ou webhook. O que
   não muda é o fato de que a reserva foi aprovada.

## Alternativas consideradas

### A) Chamar o notificador diretamente do caso de uso

```python
booking.approve(actor)
repository.save(booking)
notifier.send(f"Reserva {booking.id} aprovada")
```

**Prós:** o mais simples e o mais fácil de depurar — o fluxo inteiro está numa tela. Com um único
canal de notificação, é objetivamente a melhor escolha.
**Contras:** o número de pontos a editar cresce por multiplicação, não por soma: são 4 transições ×
N canais. Acrescentar e-mail significaria editar quatro casos de uso já testados. Além disso, o caso
de uso passaria a ter duas responsabilidades — orquestrar a regra de negócio e decidir quem é
avisado.
**Veredito:** rejeitada. O ponto de virada é o segundo canal, e o MVP já nasce com dois (log e caixa
de entrada), com e-mail previsto na evolução.

### B) Fila ou broker externo (RabbitMQ, Redis Streams)

**Prós:** desacoplamento real entre produção e consumo; entrega durável; consumidores independentes.
**Contras:** exige serviço externo rodando na máquina do avaliador — o mesmo argumento que rejeitou
PostgreSQL em [ADR-0003](0003-persistencia-sqlite-repository.md). Introduz entrega assíncrona,
reprocessamento e ordenação: problemas criados pela própria escolha, num sistema com dois
observadores em processo.
**Veredito:** rejeitada por desproporção.

### C) Observer com despacho assíncrono

Publicar em uma fila em memória consumida por tarefas de segundo plano.

**Prós:** a transação de negócio não espera pelo notificador.
**Contras:** introduz concorrência — e com ela, ordem de execução não determinística e testes mais
frágeis. O ganho de latência é irrelevante para um observador que escreve em log.
**Veredito:** rejeitada. Publicamos de forma síncrona; o isolamento de falhas (ver Decisão) resolve
a preocupação real por trás dessa alternativa.

### D) Observer síncrono, com o publicador no domínio — **escolhida**

**Veredito:** escolhida.

## Decisão

Aplicamos o padrão **Observer** às notificações de mudança de situação da reserva.

**Eventos** (`domain/events/booking_events.py`), nomeados no particípio porque descrevem algo que já
aconteceu: `BookingRequested`, `BookingApproved`, `BookingRejected`, `BookingCancelled`. São objetos
imutáveis carregando o identificador da reserva, o espaço, o solicitante e o instante.

**Sujeito e observador** (`domain/events/publisher.py`):

```python
class EventObserver(Protocol):
    def handle(self, event: BookingEvent) -> None: ...


class EventPublisher:
    def subscribe(self, observer: EventObserver) -> None: ...
    def publish(self, event: BookingEvent) -> None: ...
```

**Observadores concretos**, na infraestrutura:

| Observador | Papel |
|---|---|
| `LogNotifier` | Registra o evento no log da aplicação |
| `NotificationInbox` | Acumula notificações consultáveis em `GET /notifications` |

A `NotificationInbox` existe por uma razão explícita: **tornar o efeito do Observer visível numa
captura de tela**. Sem ela, a única evidência de que o padrão funciona estaria no log do servidor.
Com ela, a defesa mostra a relação de causa e efeito — aprovar uma reserva, consultar a caixa, ver a
notificação. É uma decisão de projeto tomada em favor da demonstrabilidade, e isso está registrado
aqui em vez de disfarçado.

**Falha de observador não derruba a operação de negócio.** O `publish` isola cada observador: uma
exceção em um deles é registrada e não se propaga, e não impede que os demais recebam o evento. O
raciocínio: uma reserva legitimamente aprovada não deve ser desfeita porque o log falhou. Notificação
é efeito colateral, e efeito colateral não invalida o fato.

## Consequências

### Positivas

- **O domínio não conhece nenhum canal.** `EventPublisher` conhece a interface `EventObserver`; quem
  a implementa vive na infraestrutura. Trocar log por e-mail não toca em uma linha de domínio.
- **Um canal novo é uma classe nova mais uma linha de registro** no composition root. Nenhum caso de
  uso muda.
- **Os casos de uso ficam com uma responsabilidade só.** Orquestram a regra; não decidem quem é
  avisado.
- **O padrão é demonstrável.** `GET /notifications` transforma um mecanismo interno em algo que se
  fotografa.
- **Testável sem infraestrutura.** Um observador espião em memória verifica que o evento certo foi
  publicado, sem log, sem HTTP, sem banco.

### Trade-offs aceitos

- **Fluxo menos óbvio na leitura.** Quem lê `ApproveBooking` vê `publish(BookingApproved(...))` e não
  sabe, ali, quem vai reagir. É o custo inerente ao padrão: ganha-se desacoplamento e perde-se
  rastreabilidade estática. Mitigado pelo registro centralizado dos observadores em um único ponto.
- **Publicação síncrona significa que a requisição espera pelos observadores.** Irrelevante para log
  e memória; seria um problema real com e-mail. Registrado como ponto a revisitar se um observador
  com I/O de rede for adicionado.
- **A caixa de entrada é volátil.** Vive em memória e se perde no reinício — inconsistente com o
  resto do sistema, que persiste em SQLite. Aceito porque ela é instrumento de demonstração, não
  funcionalidade de produto. O README deixa isso explícito para não induzir o avaliador ao erro.
- **Falhas silenciosas.** O isolamento de exceções significa que um observador quebrado falha sem
  interromper nada. Mitigado por registrar a falha em log, mas é uma escolha consciente de
  disponibilidade sobre consistência de notificação.

### Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **Transição sem evento publicado.** Uma transição futura pode esquecer de publicar, e nada quebraria | Média | Os testes de cada caso de uso usam um observador espião e afirmam que o evento correspondente foi publicado. Um caso de uso silencioso quebra a suíte. |
| **Evento publicado antes da persistência confirmar.** Notificar uma aprovação que depois sofre rollback | Baixa | A publicação ocorre após a chamada ao repositório dentro do caso de uso; o commit acontece na borda ([ADR-0003](0003-persistencia-sqlite-repository.md)). A janela existe e é conhecida: uma falha de commit posterior à publicação geraria notificação de algo revertido. Para o MVP, aceito; a solução correta seria publicar após o commit (padrão *outbox*). |
| **Observador com efeito colateral pesado** degradando a resposta da API | Baixa hoje | Registrado como gatilho para revisitar o despacho assíncrono da alternativa C. |

## Conformidade

- **`src/agendalab/domain/events/`** — eventos e publicador, sem nenhum import de infraestrutura.
- **`src/agendalab/infrastructure/notifications/`** — `LogNotifier` e `NotificationInbox`, ambos
  implementando `EventObserver`. Nenhum deles é importado pelo domínio.
- **`src/agendalab/presentation/dependencies.py`** — único lugar onde os observadores concretos são
  registrados no publicador.
- **`tests/unit/events/test_publisher.py`** — verifica a distribuição a múltiplos observadores e o
  isolamento de falhas: um observador que levanta exceção não impede os demais de receberem o evento.
- **`tests/unit/use_cases/`** — cada caso de uso que transiciona uma reserva tem teste afirmando que
  publicou o evento correspondente.
- **`GET /notifications`** com a aplicação rodando — evidência funcional, capturada no
  [documento de defesa](../DEFESA.md).
- **Diagrama:** [ARQUITETURA §8 — Classes, Observer](../ARQUITETURA.md#8-classes--observer-de-eventos).

## Referências

- [ESPECIFICACAO RN-15](../ESPECIFICACAO.md#54-ciclo-de-vida-e-autorização)
- [ARQUITETURA §8 — Classes, Observer de eventos](../ARQUITETURA.md#8-classes--observer-de-eventos)
- [ARQUITETURA §9 — Sequência, solicitar reserva](../ARQUITETURA.md#9-sequência--solicitar-reserva)
- Gamma, Helm, Johnson e Vlissides, *Design Patterns* (1994) — Observer
