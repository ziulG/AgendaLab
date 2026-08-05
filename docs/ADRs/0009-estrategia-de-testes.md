# ADR-0009: Adotar TDD com pirâmide de testes e um teste de arquitetura executável

| | |
|---|---|
| **Status** | **Aceito** |
| **Data** | 05/08/2026 |
| **Decisor** | Luiz Cutrim |
| **Tags** | `testes`, `qualidade`, `processo` |
| **Relacionados** | [ADR-0001](0001-arquitetura-em-camadas.md), [ADR-0003](0003-persistencia-sqlite-repository.md), [ADR-0008](0008-documentacao-e-diagramas-como-codigo.md) |

## Contexto

O enunciado não exige testes automatizados. Mas ele exige **alta coesão, baixo acoplamento e respeito
às responsabilidades** — e essas três propriedades têm uma relação direta com testabilidade:

> Se uma regra de negócio só pode ser testada subindo o banco e o servidor HTTP, ela não está
> desacoplada deles. A dificuldade de testar é o sintoma; o acoplamento é a doença.

Isso transforma a suíte de testes em algo além de uma rede de segurança. Ela vira **a evidência** da
qualidade que está sendo avaliada. Afirmar "o domínio não depende de infraestrutura" é uma alegação;
uma suíte de testes de domínio que roda sem banco é uma demonstração.

Há também uma restrição de prazo: seis dias, uma pessoa. A estratégia precisa caber nisso.

## Alternativas consideradas

### A) Sem testes automatizados

**Prós:** todo o tempo vai para funcionalidade e documentação.
**Contras:** perde-se a única evidência objetiva de baixo acoplamento. Sem testes, a arquitetura
inteira do [ADR-0001](0001-arquitetura-em-camadas.md) vira alegação não verificável — e a defesa
ficaria reduzida a "confie na estrutura de diretórios". Além disso, com refatoração acontecendo até o
último dia, ausência de testes é risco de regressão silenciosa às vésperas da entrega.
**Veredito:** rejeitada.

### B) Apenas testes de ponta a ponta pela API

**Prós:** poucos testes cobrem muito; testam o sistema como o usuário o experimenta; nenhum
conhecimento de estrutura interna.
**Contras:** lentos, e a falha aponta para "algo quebrou em algum lugar" em vez de para a regra
violada. Pior para este caso específico: um teste que sobe a API e o banco **não demonstra** que o
domínio é independente deles — demonstra o contrário do que queremos evidenciar. Casos de borda das
políticas (teto semanal, antecedência mínima) exigiriam montar cenários caros por HTTP.
**Veredito:** rejeitada como estratégia única. Adotada como o topo da pirâmide.

### C) Meta de 100% de cobertura

**Prós:** critério objetivo e fácil de verificar.
**Contras:** incentiva testar o que é fácil em vez do que importa — getters, configuração, wiring. Os
últimos pontos percentuais custam desproporcionalmente e produzem testes frágeis que travam
refatoração. Cobertura mede linhas executadas, não regras verificadas.
**Veredito:** rejeitada como meta. A cobertura é usada como indicador, não como objetivo.

### D) Pirâmide de testes com TDD, mais um teste de arquitetura — **escolhida**

**Veredito:** escolhida.

## Decisão

Adotamos **TDD** — teste primeiro, implementação depois, refatoração com a suíte verde — organizado
em quatro níveis:

| Nível | Diretório | O que cobre | Toca I/O? |
|---|---|---|---|
| **Arquitetura** | `tests/architecture/` | a regra de dependência entre camadas | não |
| **Unidade** | `tests/unit/` | domínio puro: `TimeSlot`, políticas, estados, eventos, entidades | **não** |
| **Integração** | `tests/integration/` | repositórios SQLAlchemy contra SQLite | sim, banco |
| **Ponta a ponta** | `tests/e2e/` | fluxos completos pela API, via `TestClient` | sim, API e banco |

A proporção segue a pirâmide clássica: a maior parte dos testes é unitária, e o topo é fino.

### O teste de arquitetura

É o nível menos convencional e o mais importante para esta entrega.
`tests/architecture/test_dependency_rule.py` percorre cada módulo de `src/agendalab/`, analisa seus
imports pela árvore sintática (`ast`) e afirma:

- `domain` não importa `application`, `infrastructure` nem `presentation`;
- `domain` não importa `fastapi`, `sqlalchemy` nem `pydantic`;
- `application` não importa `infrastructure` nem `presentation`.

Com ele, a regra de dependência do [ADR-0001](0001-arquitetura-em-camadas.md) deixa de ser convenção
que se erode por um import de conveniência e passa a ser **restrição executável**. Um import errado
quebra a suíte na mesma hora.

### Testes unitários sem I/O, por construção

A camada de aplicação é testada com **repositórios em memória** que implementam as mesmas interfaces
declaradas no domínio. Isso é possível justamente porque as interfaces pertencem ao domínio
([ADR-0003](0003-persistencia-sqlite-repository.md)) — e é a demonstração mais direta de que a
inversão de dependência não é decorativa: ela habilita algo concreto.

Tempo depende de relógio, e relógio é I/O disfarçado. As políticas recebem o instante atual pelo
`PolicyContext` ([ADR-0004](0004-strategy-politicas-de-reserva.md)), o que permite testar
"antecedência mínima de 24h" com datas fixas, sem `freezegun` e sem teste que se comporta diferente
conforme a hora em que roda.

### Cobertura

Meta de **≥ 85% em `domain/` e `application/`** ([RNF-03](../ESPECIFICACAO.md#9-requisitos-não-funcionais)).
É indicador, não objetivo: nenhum teste será escrito com a finalidade de subir o número. Sem meta para
`infrastructure/` e `presentation/`, que são cobertas indiretamente pelos níveis de integração e
ponta a ponta.

### Nomes de teste em português

Os testes que descrevem regra de negócio são nomeados em português —
`test_reserva_com_horario_sobreposto_e_recusada`. A razão é prática: a saída do `pytest -v` entra
como captura de tela no [documento de defesa](../DEFESA.md), e uma lista de comportamentos legíveis
comunica as regras do sistema melhor do que qualquer parágrafo. Exceção declarada ao "código em
inglês" do [glossário](../GLOSSARIO.md), e registrada lá.

## Consequências

### Positivas

- **A suíte unitária roda em segundos**, porque não toca disco nem rede. Isso viabiliza o ciclo curto
  do TDD dentro do prazo.
- **Baixo acoplamento vira demonstração.** "O domínio não depende de infraestrutura" é comprovado por
  uma suíte que roda sem infraestrutura.
- **A regra de dependência é executável**, não aspiracional.
- **As tabelas da especificação viram testes.** As 12 células de transição de estado
  ([ADR-0005](0005-state-ciclo-de-vida-da-reserva.md)) e as regras de cada política
  ([ADR-0004](0004-strategy-politicas-de-reserva.md)) são verificadas uma a uma.
- **Material pronto para a defesa.** A saída do `pytest -v` e o relatório de cobertura são evidência
  direta, sem preparação adicional.

### Trade-offs aceitos

- **TDD é mais lento no início.** Escrever o teste antes custa tempo num prazo de seis dias. Apostamos
  que o tempo economizado em depuração compensa — e que, num sistema com regras entrelaçadas como
  estas, a alternativa custaria mais no fim.
- **Repositórios em memória são código a manter.** Duas implementações de cada interface, e elas
  podem divergir em comportamento da implementação real. Mitigado pelos testes de integração, que
  exercitam a implementação verdadeira.
- **Testes acoplam-se à estrutura interna.** Testar cada estado isoladamente significa que renomear
  uma classe de estado quebra testes. É o preço de testar unidades pequenas, e é aceitável porque
  essas unidades são estáveis por desenho.
- **Cobertura pode dar falsa segurança.** 85% de linhas executadas não é 85% de comportamentos
  corretos. Por isso a meta é indicador, e a verificação real são os casos derivados das regras
  numeradas.

### Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **TDD abandonado sob pressão de prazo** nos últimos dias | Média — é o risco realista | As tasks de implementação são fatiadas por comportamento, não por arquivo, e cada uma nasce com seus testes. O plano reserva 10 e 11/08 como folga justamente para que a pressão não recaia sobre a disciplina de teste. |
| Testes de ponta a ponta lentos desestimulando rodar a suíte | Baixa | Marcadores `pytest` (`unit`, `integration`, `e2e`) permitem rodar só a base da pirâmide durante o ciclo de desenvolvimento. |
| Repositório em memória divergindo do SQLAlchemy | Média | Os testes de integração exercitam a implementação real em cada operação da interface. |

## Conformidade

- **`pytest` verde** na raiz do projeto:
  ```bash
  pytest
  ```
- **`tests/architecture/test_dependency_rule.py`** existe e passa — a regra do ADR-0001 é verificável.
- **`tests/unit/` roda sem criar arquivo de banco.** Se um teste unitário passar a exigir SQLite, a
  decisão foi violada.
- **Cobertura de `domain/` e `application/` ≥ 85%**:
  ```bash
  pytest --cov --cov-report=term-missing
  ```
- **Marcadores declarados** em `pyproject.toml` (`unit`, `integration`, `e2e`) e aplicados nos testes.
- **A saída de `pytest -v`** consta do [documento de defesa](../DEFESA.md) como evidência.

## Referências

- [ESPECIFICACAO §9 — Requisitos não funcionais](../ESPECIFICACAO.md#9-requisitos-não-funcionais)
- [ADR-0001 — Arquitetura em camadas](0001-arquitetura-em-camadas.md)
- [ADR-0003 — Persistência e Repository](0003-persistencia-sqlite-repository.md)
- Kent Beck, *Test-Driven Development: By Example* (2002)
- Mike Cohn, *Succeeding with Agile* (2009) — pirâmide de testes
