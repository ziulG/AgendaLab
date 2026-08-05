# ADR-0002: Implementar em Python com FastAPI e expor apenas API REST

| | |
|---|---|
| **Status** | **Aceito** |
| **Data** | 05/08/2026 |
| **Decisor** | Luiz Cutrim |
| **Tags** | `stack`, `tecnologia`, `interface` |
| **Relacionados** | [ADR-0001](0001-arquitetura-em-camadas.md), [ADR-0003](0003-persistencia-sqlite-repository.md), [ADR-0009](0009-estrategia-de-testes.md) |

## Contexto

A entrega tem duas exigências que puxam em direções diferentes. De um lado, o prazo de seis dias com
uma pessoa recomenda a stack de menor atrito. De outro, a defesa foi definida como **documento
formal com capturas de tela do sistema rodando** (Opção B do enunciado), o que exige que o sistema
tenha uma interface demonstrável visualmente.

Restrições relevantes:

- O avaliador precisa conseguir rodar o projeto na própria máquina, sem serviço externo.
- A arquitetura escolhida ([ADR-0001](0001-arquitetura-em-camadas.md)) precisa de injeção de
  dependência para funcionar sem cerimônia excessiva.
- Construir um front-end consumiria aproximadamente um dos seis dias em algo que o enunciado não
  avalia — ele avalia arquitetura, patterns e princípios de projeto.

## Alternativas consideradas

### A) Java com Spring Boot

**Prós:** é a stack que a academia mais associa a arquitetura em camadas; injeção de dependência e
separação em camadas são idiomáticas; tipagem forte verificada em compilação.
**Contras:** o maior tempo de configuração e o maior volume de código por funcionalidade entre as
opções. Em seis dias, o boilerplate consumiria o orçamento que deveria ir para as regras de negócio.
**Veredito:** rejeitada por custo de tempo, não por mérito técnico.

### B) Node.js com TypeScript e NestJS

**Prós:** o NestJS impõe módulos, camadas e DI por construção; TypeScript dá tipagem forte.
**Contras:** volume de boilerplate próximo ao do Spring. Além disso, o NestJS impõe sua própria
estrutura de módulos, que competiria com a organização em camadas do
[ADR-0001](0001-arquitetura-em-camadas.md) — o risco é a arquitetura do framework substituir a
arquitetura do projeto, e ficar difícil defender qual é qual.
**Veredito:** rejeitada.

### C) Python com Django

**Prós:** ORM maduro, admin pronto, ecossistema completo.
**Contras:** o Django é opinativo em favor de Active Record — os models herdam de `models.Model` e
carregam persistência junto com comportamento. Isso é frontalmente incompatível com um domínio livre
de infraestrutura. Seria possível contornar, mas defender uma arquitetura que luta contra o
framework é uma posição frágil.
**Veredito:** rejeitada por conflito com o ADR-0001.

### D) Python com FastAPI — **escolhida**

**Prós:**
- **Swagger UI gerado automaticamente** a partir dos schemas Pydantic. Isso não é conveniência
  cosmética: é a solução direta para o requisito de capturas de tela da defesa, sem escrever
  front-end.
- **Injeção de dependência nativa** via `Depends`, que serve exatamente ao composition root do
  ADR-0001.
- **Validação de entrada declarativa** com Pydantic, que mantém a validação sintática na borda e
  deixa o domínio livre para cuidar apenas da validação semântica.
- Menor volume de código por funcionalidade entre as opções avaliadas.

**Contras:** ver trade-offs.
**Veredito:** escolhida.

### E) FastAPI com front-end web (Jinja2 + HTMX ou React)

Avaliada como extensão da opção D.

**Prós:** capturas de tela mais convincentes; camada de apresentação com View real, o que
fortaleceria uma leitura MVC.
**Contras:** custo estimado de um dia dos seis, em troca de nenhum ponto adicional nos critérios
declarados de avaliação. Aumenta a superfície de código e o risco de não entregar.
**Veredito:** rejeitada por proporção. Fica registrada como extensão natural caso haja tempo
sobrando após a documentação de defesa.

## Decisão

Implementamos o AgendaLab em **Python 3.12+ com FastAPI**, expondo **exclusivamente uma API REST**.
A demonstração visual do sistema para o documento de defesa usa o **Swagger UI** publicado
automaticamente em `/docs`.

A pilha completa:

| Camada | Tecnologia | Papel |
|---|---|---|
| HTTP | FastAPI + Uvicorn | rotas, validação de entrada, documentação interativa |
| Validação de borda | Pydantic v2 | schemas de requisição e resposta |
| Persistência | SQLAlchemy 2 + SQLite | ver [ADR-0003](0003-persistencia-sqlite-repository.md) |
| Testes | pytest + httpx | ver [ADR-0009](0009-estrategia-de-testes.md) |
| Qualidade | ruff | linting e formatação |

**Não haverá front-end.** A ausência é decisão registrada, não omissão.

## Consequências

### Positivas

- **A demonstração da defesa sai de graça.** O Swagger UI permite executar cada endpoint no navegador
  e capturar requisição e resposta reais, sem uma linha de código de interface.
- **O `Depends` do FastAPI implementa o composition root** do ADR-0001 sem framework de DI adicional.
- **Pydantic separa naturalmente as duas validações.** Formato e tipo ficam na borda; regra de
  negócio fica no domínio. Essa divisão reforça o respeito às responsabilidades que está sendo
  avaliado.
- **Menos código para escrever, revisar e defender** dentro do prazo.

### Trade-offs aceitos

- **Tipagem gradual não é garantia em tempo de execução.** As anotações do Python não são verificadas
  como as de Java ou TypeScript compilado. Compensamos com Pydantic na borda e com a suíte de testes;
  ainda assim, é uma rede menos densa.
- **Swagger UI é menos impressionante que uma interface própria** num documento de defesa. Aceitamos
  porque o critério declarado de avaliação é arquitetural.
- **O `Depends` do FastAPI é um mecanismo do framework.** Usá-lo significa que a camada de
  apresentação está acoplada ao FastAPI — o que é aceitável, já que ela é a camada mais externa e o
  seu propósito é justamente falar HTTP.
- **Python 3.12+ como piso.** O avaliador precisa de uma versão recente. Mitigado por ser um
  requisito comum e documentado no README.

### Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| O avaliador não consegue rodar o projeto | Baixa | README com passo a passo verificado; SQLite dispensa serviço externo ([ADR-0003](0003-persistencia-sqlite-repository.md)); nenhuma dependência de sistema além do Python |
| O FastAPI vaza para as camadas internas por conveniência (ex.: `HTTPException` levantada no caso de uso) | Média | O domínio levanta erros tipados próprios; a tradução para HTTP acontece apenas em `presentation/error_handlers.py`. O teste de arquitetura barra o import de `fastapi` fora da apresentação. |
| Pydantic e domínio duplicam validação | Média | Divisão explícita: Pydantic valida formato e tipo, o domínio valida regra de negócio. As regras RN-01 a RN-16 pertencem ao domínio, sem exceção. |

## Conformidade

- **`pyproject.toml`** — declara `requires-python = ">=3.12"` e as dependências desta decisão.
- **Ausência de `import fastapi` e `import pydantic`** sob `domain/` e `application/`, verificada por
  `tests/architecture/test_dependency_rule.py`.
- **`src/agendalab/presentation/error_handlers.py`** — único arquivo do projeto que menciona códigos
  de status HTTP.
- **`/docs` acessível** com a aplicação rodando, conforme
  [RNF-06](../ESPECIFICACAO.md#9-requisitos-não-funcionais).
- **Ausência de qualquer diretório de front-end** no repositório — coerência com a decisão registrada.

## Referências

- [ESPECIFICACAO §7 — Contratos da API REST](../ESPECIFICACAO.md#7-contratos-da-api-rest)
- [ARQUITETURA — C4 Nível 2, Container](../ARQUITETURA.md#2-c4-nível-2--container)
- [ADR-0001 — Arquitetura em camadas](0001-arquitetura-em-camadas.md)
