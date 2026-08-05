# ADR-0004: Aplicar o padrão Strategy às políticas de admissão de reserva

| | |
|---|---|
| **Status** | **Aceito** |
| **Data** | 05/08/2026 |
| **Decisor** | Luiz Cutrim |
| **Tags** | `design-pattern`, `strategy`, `domínio`, `regra-de-negócio` |
| **Relacionados** | [ADR-0001](0001-arquitetura-em-camadas.md), [ADR-0005](0005-state-ciclo-de-vida-da-reserva.md) |

## Contexto

Nem todo espaço deve ser liberado da mesma forma. Uma sala de aula comum é recurso abundante e de
baixo risco. Um laboratório tem equipamento caro e exige preparo. O auditório é único no campus e só
se justifica para eventos de porte. As regras que o AgendaLab precisa aplicar refletem isso
([ESPECIFICACAO §5.3](../ESPECIFICACAO.md#53-políticas-por-tipo-de-espaço)):

| Tipo | Aprovação | Antecedência mínima | Regra adicional |
|---|---|---|---|
| `CLASSROOM` | automática | — | teto de 8h por solicitante na semana |
| `LAB` | gestor | 24h | duração máxima de 4h |
| `AUDITORIUM` | gestor | 72h | mínimo de 20 participantes |

Duas observações sobre a natureza dessa variação, e são elas que determinam o desenho:

1. **As regras não diferem apenas em parâmetros, diferem em estrutura.** "Teto de horas na semana"
   e "mínimo de participantes" não são o mesmo cálculo com números diferentes — são verificações de
   naturezas distintas, sobre dados distintos.
2. **É o eixo que mais deve variar no futuro.** Novo tipo de espaço, ajuste de política por período
   letivo, exceção para um departamento: tudo isso mexe aqui. Já a detecção de conflito de horário
   (RN-01) é estável.

O que varia precisa ficar isolado do que não varia.

## Alternativas consideradas

### A) Condicional por tipo dentro do caso de uso

```python
if space.kind == SpaceKind.CLASSROOM:
    ...
elif space.kind == SpaceKind.LAB:
    ...
```

**Prós:** o caminho mais curto; todo o fluxo visível num arquivo; nenhuma indireção.
**Contras:** `RequestBooking` passaria a ter três razões distintas para mudar, uma por tipo de
espaço — violação direta de responsabilidade única. Um quarto tipo exigiria editar um arquivo já
testado e em uso. Pior: a mesma condicional tenderia a reaparecer em `ApproveBooking`, e a regra de
um tipo ficaria em dois lugares.
**Veredito:** rejeitada. É o acoplamento que a disciplina avalia negativamente, na sua forma mais
direta.

### B) Hierarquia de `Space` com método polimórfico

`Classroom`, `Lab` e `Auditorium` herdando de `Space`, cada uma sobrescrevendo `validate_booking()`.

**Prós:** polimorfismo genuíno, sem classe extra; o comportamento fica junto da entidade que o
determina.
**Contras:** mistura duas razões de mudança na mesma hierarquia — *o que o espaço é* (nome,
capacidade, situação) e *como ele é liberado* (política de admissão). São eixos independentes: a
política de laboratórios pode mudar sem que nada sobre laboratórios mude. Além disso, reclassificar
um espaço de `CLASSROOM` para `LAB` viraria uma troca de classe da entidade persistida, com todo o
atrito de identidade que isso implica.
**Veredito:** rejeitada. Herança para variar comportamento amarra o comportamento à identidade do
objeto, que aqui são coisas separadas.

### C) Regras como dados, em tabela de configuração

Uma tabela com colunas `min_notice_hours`, `max_duration_hours`, `weekly_cap`, `min_attendees`.

**Prós:** mudar uma regra viraria alteração de dado, sem deploy; um gestor poderia ajustar sozinho.
**Contras:** funcionaria se as políticas diferissem só em parâmetros — mas elas diferem em estrutura
(ver Contexto). Uma tabela genérica o bastante para expressar "teto semanal por solicitante" e
"mínimo de participantes" acabaria virando um pequeno interpretador de regras dentro do sistema:
mais complexo que as três classes que substituiria, e muito mais difícil de testar.
**Veredito:** rejeitada. É a solução certa para variação paramétrica, e a nossa não é paramétrica.

### D) Chain of Responsibility sobre as validações

Cada regra — conflito, capacidade, antecedência, teto semanal — como um elo de uma cadeia.

**Prós:** cada regra isolada em sua própria classe; ordem de avaliação explícita; muito coeso.
**Contras:** resolve um problema adjacente, não este. A cadeia organiza *quais* validações rodam,
mas ainda seria preciso decidir qual cadeia montar para cada tipo de espaço — ou seja, o Strategy
continuaria necessário, agora como fábrica de cadeias. E o enunciado limita a três patterns
implementados.
**Veredito:** rejeitada por escopo. Fica registrada como evolução natural caso o número de regras
por política cresça a ponto de a classe de política ficar grande demais.

### E) Strategy — **escolhida**

Uma interface `BookingPolicy` com três implementações, resolvidas pelo tipo do espaço.

**Veredito:** escolhida.

## Decisão

Aplicamos o padrão **Strategy** às políticas de admissão de reserva.

A interface, declarada em `domain/policies/booking_policy.py`:

```python
class BookingPolicy(Protocol):
    def initial_status(self) -> BookingStatus:
        """Estado em que a reserva nasce sob esta política."""

    def validate(self, request: BookingRequest, context: PolicyContext) -> None:
        """Levanta PolicyViolation se a solicitação for inadmissível."""
```

Três implementações, uma por tipo de espaço:

| Implementação | Tipo | Regra |
|---|---|---|
| `OpenAccessPolicy` | `CLASSROOM` | RN-08 |
| `ManagedAccessPolicy` | `LAB` | RN-09 |
| `RestrictedAccessPolicy` | `AUDITORIUM` | RN-10 |

O `PolicyContext` carrega o que a política precisa para decidir sem consultar nada: o instante atual,
o espaço e as reservas ativas do solicitante na semana. Passar o contexto pronto mantém as políticas
como **funções puras sobre os dados que recebem** — sem acesso a repositório, sem I/O, sem relógio
global. É o que as torna testáveis com dados construídos à mão.

A resolução de tipo para política é um **dicionário simples** em `domain/policies/registry.py`:

```python
POLICY_BY_KIND: dict[SpaceKind, BookingPolicy] = {
    SpaceKind.CLASSROOM: OpenAccessPolicy(),
    SpaceKind.LAB: ManagedAccessPolicy(),
    SpaceKind.AUDITORIUM: RestrictedAccessPolicy(),
}
```

**Chamamos isto de mapa, e não de Factory Method.** É um `dict`. Rotulá-lo com nome de padrão para
elevar a contagem de patterns do trabalho seria inflar o que existe — e a contenção aqui é
deliberada: os três patterns declarados resolvem problemas reais, e este não é um quarto.

## Consequências

### Positivas

- **`RequestBooking` conhece apenas `BookingPolicy`.** Não sabe que existem três tipos de espaço, e
  não muda quando surgir um quarto. É o princípio aberto/fechado com uma demonstração concreta.
- **Cada política é testável isoladamente**, com um `PolicyContext` montado à mão. Nenhum teste de
  política precisa de banco, HTTP ou caso de uso.
- **Cada política tem uma única razão para mudar:** a regra do seu tipo de espaço.
- **A regra fica legível.** `ManagedAccessPolicy` é um arquivo pequeno que responde à pergunta "como
  se reserva um laboratório?" sem que o leitor precise filtrar as regras dos outros tipos.

### Trade-offs aceitos

- **Mais arquivos para três regras.** Uma condicional resolveria hoje em menos linhas. Pagamos essa
  indireção apostando na variação futura — e se o sistema tivesse um único tipo de espaço, esta
  decisão seria over-engineering.
- **A regra fica distribuída.** Para responder "quais regras existem no sistema?" é preciso abrir
  quatro arquivos em vez de um. Mitigado pela tabela consolidada em
  [ESPECIFICACAO §5.3](../ESPECIFICACAO.md#53-políticas-por-tipo-de-espaço), que serve de índice.
- **O `PolicyContext` precisa ser montado antes de a política rodar.** O caso de uso carrega dados
  que uma política específica pode não usar — `OpenAccessPolicy` é a única que consulta as reservas
  da semana. É um custo de I/O ocasionalmente desnecessário, aceito em troca de manter as políticas
  livres de repositório.

### Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **Interface inadequada para uma quarta política.** Uma regra futura pode precisar de dados que o `PolicyContext` não carrega, forçando mudança na interface e em todas as implementações | Média | O `PolicyContext` é uma classe de dados, extensível por adição de campo. Acrescentar um campo opcional não quebra implementações existentes. |
| **Políticas vazias por obrigação de interface.** `OpenAccessPolicy` não tem antecedência mínima e poderia acabar com métodos que não fazem nada | Baixa | A interface tem apenas dois métodos, ambos com significado para toda política. Não há método que uma implementação precise ignorar. |
| **Um tipo de espaço sem política registrada** causaria `KeyError` em tempo de execução | Baixa | Teste que percorre todos os membros de `SpaceKind` e afirma que cada um tem entrada em `POLICY_BY_KIND`. Um tipo novo sem política quebra a suíte. |

## Conformidade

- **`src/agendalab/domain/policies/`** — a interface e as três implementações. Se uma condicional por
  `space.kind` aparecer fora deste diretório, a decisão foi violada.
- **`src/agendalab/application/use_cases/request_booking.py`** — não deve conter nenhuma referência a
  `SpaceKind.CLASSROOM`, `SpaceKind.LAB` ou `SpaceKind.AUDITORIUM`. O caso de uso fala com a
  abstração.
- **`tests/unit/policies/`** — um arquivo de teste por política, cobrindo aceitação e recusa, sem
  banco e sem HTTP.
- **`tests/unit/policies/test_registry.py`** — afirma que todo membro de `SpaceKind` tem política
  registrada.
- **Diagrama:** [ARQUITETURA §6 — Classes, Strategy das políticas](../ARQUITETURA.md#6-classes--strategy-das-políticas).

## Referências

- [ESPECIFICACAO §5.3 — Políticas por tipo de espaço](../ESPECIFICACAO.md#53-políticas-por-tipo-de-espaço)
- [ARQUITETURA §6 — Classes, Strategy](../ARQUITETURA.md#6-classes--strategy-das-políticas)
- Gamma, Helm, Johnson e Vlissides, *Design Patterns* (1994) — Strategy
