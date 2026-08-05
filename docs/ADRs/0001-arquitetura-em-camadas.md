# ADR-0001: Adotar arquitetura em camadas com inversão de dependência

| | |
|---|---|
| **Status** | **Aceito** |
| **Data** | 05/08/2026 |
| **Decisor** | Luiz Cutrim |
| **Tags** | `arquitetura`, `estrutura`, `acoplamento` |
| **Relacionados** | [ADR-0002](0002-stack-python-fastapi.md), [ADR-0003](0003-persistencia-sqlite-repository.md), [ADR-0009](0009-estrategia-de-testes.md) |

## Contexto

O AgendaLab precisa adotar um padrão arquitetural explícito, e o enunciado é claro sobre o que será
avaliado: **alta coesão, baixo acoplamento e respeito às responsabilidades**. Não basta escolher um
padrão de nome conhecido — é preciso que a escolha produza essas três propriedades de forma
verificável.

As forças em jogo:

- **O domínio tem regra de negócio real.** Detecção de conflito de horário, políticas distintas por
  tipo de espaço e um ciclo de vida com transições proibidas. Não é um CRUD.
- **Prazo de seis dias e uma pessoa.** Qualquer arquitetura que exija muita cerimônia por operação
  vai consumir o tempo que deveria ir para a qualidade das regras.
- **A defesa precisa de argumentos verificáveis.** Afirmar "temos baixo acoplamento" sem evidência é
  fraco. A arquitetura escolhida precisa permitir que essa afirmação seja demonstrada.
- **A persistência é um detalhe.** SQLite foi escolhido por conveniência de demonstração
  ([ADR-0003](0003-persistencia-sqlite-repository.md)), não porque o domínio dependa dele.

## Alternativas consideradas

### A) MVC clássico

Controllers recebem a requisição, Models carregam dados e comportamento, Views renderizam.

**Prós:** é o primeiro padrão citado pelo enunciado; vocabulário universalmente conhecido; menos
arquivos; caminho mais curto da requisição ao banco.
**Contras:** o sistema não tem View — a interface é uma API REST ([ADR-0002](0002-stack-python-fastapi.md)),
então um dos três componentes do padrão ficaria vazio ou seria forçado a significar "serializador
JSON". Pior: na prática do MVC em frameworks web, a regra de negócio migra para os controllers ou
para models que herdam do ORM, e ambos os casos acoplam a regra à infraestrutura. Isso é
exatamente o oposto do que está sendo avaliado.
**Veredito:** rejeitada. Adotar MVC aqui seria escolher o rótulo mais reconhecível ao custo da
propriedade que a disciplina avalia.

### B) Microsserviços

Serviços independentes — catálogo de espaços, reservas, notificações — comunicando por rede.

**Prós:** escalabilidade independente; isolamento de falhas; é um dos padrões citados no enunciado.
**Contras:** desproporcional em todas as dimensões. O sistema tem duas entidades e sete casos de uso;
não há requisito de escala, nem times separados, nem necessidade de deploy independente. Introduziria
consistência eventual, comunicação em rede, orquestração e observabilidade distribuída — problemas
inteiramente criados pela própria escolha. Com seis dias e uma pessoa, o custo é proibitivo.
**Veredito:** rejeitada. Microsserviços resolvem um problema organizacional e de escala que este
projeto não tem.

### C) Hexagonal (Ports & Adapters)

Domínio ao centro, com portas de entrada e saída explícitas e adaptadores em volta.

**Prós:** o mais rigoroso em isolamento do domínio; simetria elegante entre entrada e saída; a
inversão de dependência é intrínseca ao padrão.
**Contras:** exige defender mais vocabulário (porta primária, porta secundária, adaptador condutor,
adaptador conduzido) e produz mais artefatos de adaptação. Boa parte desse rigor extra, neste
sistema, resultaria em portas de entrada que são invocadas por um único adaptador HTTP.
**Veredito:** rejeitada por proporção, não por mérito. A alternativa escolhida incorpora o que há de
essencial nela — a inversão na fronteira de saída — sem o vocabulário adicional.

### D) Arquitetura em camadas com inversão de dependência — **escolhida**

Quatro camadas, com a regra de dependência apontando para dentro e a interface do repositório
declarada no domínio.

**Prós:** as fronteiras são óbvias e mapeiam diretamente em diretórios, o que torna a coesão visível
na estrutura de arquivos. O domínio fica sem nenhuma dependência externa, o que torna o baixo
acoplamento demonstrável por teste, e não apenas afirmável. É um padrão explicitamente citado pelo
enunciado. O custo de cerimônia é proporcional ao tamanho do sistema.
**Contras:** ver a seção de trade-offs.
**Veredito:** escolhida.

## Decisão

Adotamos **arquitetura em camadas com inversão de dependência**, organizada em quatro camadas:

| Camada | Pacote | Responsabilidade | Pode depender de |
|---|---|---|---|
| Apresentação | `presentation` | Expor HTTP, traduzir erros, compor as dependências | todas |
| Aplicação | `application` | Orquestrar o domínio em casos de uso | domínio |
| Domínio | `domain` | Regras de negócio, entidades, políticas, estados, eventos e **as interfaces de repositório** | nada |
| Infraestrutura | `infrastructure` | Implementar as interfaces do domínio | domínio |

Duas regras governam a estrutura:

1. **Regra de dependência.** Uma camada só pode importar as que estão abaixo dela na tabela. O
   domínio não importa ninguém.
2. **Inversão na fronteira de saída.** As interfaces `SpaceRepository` e `BookingRepository` são
   declaradas em `domain/repositories.py` e implementadas em `infrastructure/persistence/`. A seta de
   dependência da infraestrutura aponta para dentro.

A camada de apresentação atua como **composition root**: é o único ponto que conhece
simultaneamente as abstrações e as implementações concretas, porque é ela quem as conecta. Essa
concessão é deliberada e está confinada a `presentation/dependencies.py`.

## Consequências

### Positivas

- **O domínio roda em teste sem banco, sem FastAPI e sem rede.** Isso não é uma afirmação de
  intenção: é uma propriedade verificável, e é a evidência concreta de baixo acoplamento que
  apresentamos na defesa.
- **Alta coesão fica visível na estrutura de diretórios.** Quem procura a regra de conflito de
  horário encontra em `domain/value_objects/time_slot.py`, e não espalhada por controllers.
- **Trocar a persistência é local.** Substituir SQLite por PostgreSQL, ou por repositórios em
  memória, significa uma nova implementação da interface — nenhuma linha de domínio ou de caso de uso
  muda.
- **Os três design patterns têm onde morar.** Políticas, estados e eventos ficam no domínio, que é o
  lugar conceitualmente correto para eles, porque são regra de negócio e não detalhe técnico.

### Trade-offs aceitos

- **Mais arquivos e mais indireção.** Um cadastro simples de espaço atravessa router → caso de uso →
  entidade → interface de repositório → implementação. Num CRUD puro isso seria cerimônia
  injustificada. Aceitamos porque o sistema tem regra de negócio suficiente para pagá-la — e
  reconhecemos que num sistema sem regra a mesma escolha seria over-engineering.
- **Mapeamento manual entre ORM e domínio.** Manter as entidades de domínio livres de SQLAlchemy
  exige funções de conversão que precisam ser mantidas em sincronia com ambos os lados
  ([ADR-0003](0003-persistencia-sqlite-repository.md)).
- **A camada de apresentação sabe de tudo.** O composition root conhece as classes concretas. Isso é
  inerente a qualquer injeção de dependência manual; o ganho é que essa dependência fica concentrada
  em um arquivo em vez de espalhada.

### Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **Domínio anêmico** — as entidades viram sacos de dados e a regra migra para os casos de uso, esvaziando o propósito da arquitetura | Alta, é o modo de falha mais comum | Os três patterns forçam comportamento para dentro do domínio: a política valida, o estado decide a transição, a entidade publica o evento. Os testes unitários exercitam regra de negócio sem passar por caso de uso algum. |
| **Erosão da regra de dependência** ao longo da implementação, por um import de conveniência | Média | `tests/architecture/test_dependency_rule.py` analisa os imports de cada módulo por AST e falha a suíte se uma camada interna importar uma externa. A regra vira teste, não convenção. |
| **Vazamento do ORM para o domínio** via objetos preguiçosos do SQLAlchemy | Média | Os repositórios devolvem entidades de domínio construídas pelos mappers, nunca instâncias do modelo ORM. |

## Conformidade

Esta decisão é verificável no repositório por:

- **`tests/architecture/test_dependency_rule.py`** — analisa a árvore sintática de cada módulo em
  `src/agendalab/` e afirma que: `domain` não importa `application`, `infrastructure` nem
  `presentation`; `application` não importa `infrastructure` nem `presentation`. Falha da suíte
  significa violação da decisão.
- **`src/agendalab/domain/repositories.py`** — a existência das interfaces de repositório *dentro* do
  pacote de domínio é a materialização da inversão de dependência. Se este arquivo migrar para
  `infrastructure/`, a decisão foi revertida.
- **Estrutura de diretórios** de `src/agendalab/`, conforme
  [ESPECIFICACAO §8](../ESPECIFICACAO.md#8-estrutura-de-código).
- **Ausência de `import sqlalchemy` e `import fastapi`** em qualquer arquivo sob `domain/` e
  `application/`.

## Referências

- [ESPECIFICACAO §8 — Estrutura de código](../ESPECIFICACAO.md#8-estrutura-de-código)
- [ARQUITETURA — C4 Nível 3, Componentes](../ARQUITETURA.md#3-c4-nível-3--componentes)
- [ARQUITETURA — Camadas e regra de dependência](../ARQUITETURA.md#4-camadas-e-regra-de-dependência)
- Robert C. Martin, *Clean Architecture* (2017) — regra de dependência
- Alistair Cockburn, *Hexagonal Architecture* (2005) — origem da inversão na fronteira
