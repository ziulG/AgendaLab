# ADR-0003: Persistir em SQLite via SQLAlchemy, com Repository e modelos separados do domínio

| | |
|---|---|
| **Status** | **Aceito** |
| **Data** | 05/08/2026 |
| **Decisor** | Luiz Cutrim |
| **Tags** | `persistência`, `banco-de-dados`, `repository` |
| **Relacionados** | [ADR-0001](0001-arquitetura-em-camadas.md), [ADR-0002](0002-stack-python-fastapi.md), [ADR-0009](0009-estrategia-de-testes.md) |

## Contexto

O sistema precisa persistir espaços e reservas entre execuções — o documento de defesa exige mostrar
o sistema rodando com dados reais, e um banco volátil não sustenta uma demonstração de ponta a ponta.

Ao mesmo tempo, o [ADR-0001](0001-arquitetura-em-camadas.md) estabeleceu que o domínio não pode
depender de infraestrutura. Persistência é o ponto onde essa regra é mais frequentemente violada, e
por um motivo compreensível: ORMs modernos oferecem muita produtividade justamente quando você deixa
o modelo de persistência ser também o modelo de domínio.

Restrições:

- O avaliador precisa rodar o projeto sem instalar serviço externo.
- Os testes precisam ser rápidos e isolados ([ADR-0009](0009-estrategia-de-testes.md)).
- O prazo não comporta infraestrutura de dados elaborada.

## Alternativas consideradas

### A) Repositórios apenas em memória, sem banco

**Prós:** o mais rápido de implementar; testes triviais; zero configuração.
**Contras:** os dados somem a cada reinício. A demonstração da defesa — cadastrar espaço, solicitar,
aprovar, mostrar o resultado — ficaria frágil, e o sistema pareceria um protótipo de laboratório em
vez de um MVP.
**Veredito:** rejeitada como solução de produção. **Adotada parcialmente**: as implementações em
memória existem como duplas de teste para a camada de aplicação, o que é possível justamente porque
a interface está no domínio.

### B) PostgreSQL com Docker Compose

**Prós:** banco de produção real; concorrência de verdade; restrições de exclusão temporal nativas
(`EXCLUDE USING gist`), que resolveriam a corrida de reserva dupla no nível do banco.
**Contras:** exige Docker instalado e funcionando na máquina do avaliador; adiciona um ponto de falha
justamente no momento da demonstração; overhead de configuração desproporcional a duas tabelas.
**Veredito:** rejeitada. O ganho técnico real (a restrição de exclusão) não compensa o risco de a
demonstração falhar na máquina de quem avalia.

### C) SQLAlchemy com as entidades de domínio herdando de `Base`

O caminho idiomático: `class Booking(Base)` com colunas e comportamento na mesma classe.

**Prós:** o menor volume de código; sem camada de mapeamento; abordagem mais comum em projetos
Python.
**Contras:** o domínio passaria a importar SQLAlchemy, violando diretamente a decisão do ADR-0001.
As entidades ganhariam estado implícito de sessão e carregamento preguiçoso — comportamento de
infraestrutura misturado a regra de negócio. Um teste unitário de política de reserva passaria a
exigir metadados de tabela.
**Veredito:** rejeitada. É exatamente o acoplamento que a arquitetura escolhida existe para evitar.

### D) SQLAlchemy com *imperative mapping*

O `registry.map_imperatively()` permite mapear classes Python puras para tabelas sem herança e sem
decoradores, mantendo o domínio limpo.

**Prós:** domínio 100% livre de SQLAlchemy **e** sem código de mapeamento manual; tecnicamente a
solução mais elegante das avaliadas.
**Contras:** é um recurso pouco conhecido, e o mapeamento fica declarado longe da classe que ele
afeta. Numa defesa oral ou escrita, exigiria explicar o mecanismo antes de explicar a arquitetura.
Além disso, as instâncias de domínio passariam a ser rastreadas pela sessão, reintroduzindo estado
implícito.
**Veredito:** rejeitada por legibilidade, não por mérito. É a alternativa que mais chegou perto.

### E) SQLAlchemy com modelos de persistência separados e mappers explícitos — **escolhida**

Duas famílias de classes: `domain/entities/` (puras) e `infrastructure/persistence/models.py`
(tabelas), com funções de conversão entre elas.

**Prós:** o domínio permanece verificavelmente livre de infraestrutura; o esquema do banco pode
evoluir sem arrastar o domínio junto; a conversão é código comum, explícito e testável.
**Contras:** ver trade-offs.
**Veredito:** escolhida.

## Decisão

Persistimos em **SQLite** através do **SQLAlchemy 2**, com três regras:

1. **As interfaces `SpaceRepository` e `BookingRepository` vivem em `domain/repositories.py`.** São
   contratos declarados pelo domínio, expressos em termos de entidades de domínio — nunca de linhas,
   sessões ou consultas.
2. **Os modelos de persistência são classes separadas**, em
   `infrastructure/persistence/models.py`. Nenhuma entidade de domínio herda de `Base`.
3. **A conversão acontece em `infrastructure/persistence/mappers.py`**, e os repositórios sempre
   devolvem entidades de domínio — jamais instâncias do modelo ORM.

O **limite transacional é a requisição HTTP**: a sessão é criada por uma dependência do FastAPI, com
`commit` em caso de sucesso e `rollback` em caso de exceção. Os casos de uso não conhecem transação.

**Não usamos ferramenta de migração** (Alembic). O esquema é criado a partir dos metadados na
inicialização. Justificativa: com o banco em arquivo local e um MVP sem histórico de produção a
preservar, migração seria infraestrutura sem propósito.

## Consequências

### Positivas

- **O domínio continua testável sem I/O.** É a mesma propriedade do ADR-0001, aqui preservada no
  ponto onde ela costuma ser perdida.
- **Os testes de aplicação usam repositórios em memória** que implementam a mesma interface. Rodam em
  milissegundos e não tocam disco. Isso só é possível porque a interface pertence ao domínio.
- **A demonstração da defesa é reprodutível.** O avaliador clona, roda um comando e tem um banco
  funcionando, sem instalar nada além do Python.
- **O esquema físico é livre para divergir do modelo de domínio.** `TimeSlot` é um objeto de valor
  no domínio e duas colunas na tabela, sem que nenhum dos lados precise ceder.

### Trade-offs aceitos

- **Código de mapeamento duplicado.** Cada campo aparece na entidade, no modelo e no mapper. Um campo
  novo exige tocar em três lugares. É o custo direto de manter o domínio puro, e o aceitamos com os
  olhos abertos: em um sistema com dezenas de entidades, este seria um argumento forte a favor do
  *imperative mapping* da alternativa D.
- **SQLite não suporta escrita concorrente de verdade.** Serializa escritas por bloqueio de arquivo.
  Para um MVP demonstrado localmente é irrelevante; para uso real, não serviria.
- **Sem migrações.** Alterar o esquema exige recriar o banco. Aceitável enquanto não há dados de
  produção.
- **Chave estrangeira por `code` em vez de `id` numérico.** `SPACES.code` é chave natural, o que
  torna as rotas e o banco legíveis (`/spaces/LAB-01/availability`), mas significa que renomear o
  código de um espaço seria uma operação cara. Assumimos que o código é imutável, e a especificação
  declara isso.

### Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **Reserva dupla por corrida.** A verificação de conflito (RN-01) e a inserção são duas operações; entre elas, outra requisição poderia inserir uma reserva sobreposta | Baixa no cenário demonstrado, **real em produção** | O SQLite serializa escritas e a aplicação roda com um único worker, o que fecha a janela na prática. **Este é um limite conhecido e assumido do MVP**, não um descuido: a solução correta seria uma restrição de exclusão temporal no banco (disponível no PostgreSQL) ou bloqueio pessimista do espaço. Registrado aqui para ser defendido como trade-off consciente. |
| Mapper e modelo saem de sincronia ao evoluir uma entidade | Média | Os testes de integração em `tests/integration/` gravam e releem cada entidade, comparando ida e volta. Um campo esquecido no mapper quebra a suíte. |
| Objeto ORM vazando para fora do repositório | Média | Os testes de integração verificam o tipo devolvido pelos repositórios: precisa ser a entidade de domínio. |

## Conformidade

- **`src/agendalab/domain/repositories.py`** — as interfaces existem no domínio, expressas em
  entidades de domínio. Nenhuma assinatura menciona `Session`, `Query` ou tipo do SQLAlchemy.
- **Ausência de `import sqlalchemy`** sob `domain/` e `application/`, verificada por
  `tests/architecture/test_dependency_rule.py`.
- **`src/agendalab/infrastructure/persistence/models.py`** — nenhuma classe aqui é importada pelo
  domínio.
- **`tests/integration/test_sqlalchemy_space_repository.py`** e
  **`test_sqlalchemy_booking_repository.py`** — afirmam que o tipo devolvido é a entidade de
  domínio, nunca o modelo ORM, e que o dado sobrevive ao fim da sessão. Os dois herdam a mesma
  bateria de `tests/contracts/` que a implementação em memória passa, o que impede as duas de
  divergirem.
- **`tests/integration/test_mappers.py`** — percorre os campos declarados nas dataclasses e exige
  que **todos** sobrevivam à ida e volta. Um campo esquecido no mapper quebra a suíte.
- **`tests/unit/`** — a suíte inteira roda sem criar arquivo de banco. Se algum teste unitário passar
  a exigir banco, a decisão foi violada.

## Referências

- [ESPECIFICACAO §4 — Modelo de domínio](../ESPECIFICACAO.md#4-modelo-de-domínio)
- [ARQUITETURA — Modelo entidade-relacionamento](../ARQUITETURA.md#10-modelo-entidade-relacionamento)
- [ADR-0001 — Arquitetura em camadas](0001-arquitetura-em-camadas.md)
- Eric Evans, *Domain-Driven Design* (2003) — padrão Repository
- Martin Fowler, *Patterns of Enterprise Application Architecture* (2002) — Repository e Data Mapper
