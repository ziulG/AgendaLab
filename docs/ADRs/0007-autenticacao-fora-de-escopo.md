# ADR-0007: Manter autenticação fora de escopo, implementando apenas a autorização

| | |
|---|---|
| **Status** | **Aceito** |
| **Data** | 05/08/2026 |
| **Decisor** | Luiz Cutrim |
| **Tags** | `escopo`, `segurança`, `autorização` |
| **Relacionados** | [ADR-0002](0002-stack-python-fastapi.md), [ADR-0003](0003-persistencia-sqlite-repository.md) |

## Contexto

O AgendaLab tem regras que dependem de quem está agindo
([ESPECIFICACAO §5.4](../ESPECIFICACAO.md#54-ciclo-de-vida-e-autorização)):

- **RN-11:** somente o gestor aprova ou rejeita uma reserva.
- **RN-12:** o cancelamento cabe ao próprio solicitante da reserva ou a qualquer gestor.

Essas regras são parte do domínio — recusar que um aluno aprove a própria reserva é regra de
negócio, não configuração de infraestrutura. Elas precisam existir no sistema.

Mas há uma distinção que a decisão inteira depende de reconhecer:

- **Autenticação** responde "quem é você?" — envolve credencial, hash de senha, sessão, token.
- **Autorização** responde "o que você pode fazer?" — envolve papel, propriedade do recurso e regra
  de negócio.

Apenas a segunda é objeto de avaliação neste trabalho. A primeira é infraestrutura de segurança bem
compreendida, cuja implementação consumiria tempo do prazo de seis dias sem produzir nenhum argumento
arquitetural que já não tenhamos.

## Alternativas consideradas

### A) Autenticação completa com JWT

Cadastro de usuário, senha com hash (bcrypt/argon2), login emitindo token, middleware de verificação.

**Prós:** sistema realista e completo; o avaliador veria um fluxo de ponta a ponta.
**Contras:** exige entidade `User`, tabela, endpoints de cadastro e login, gestão de segredo e
expiração. Estimativa de um dia dos seis, em troca de zero pontos nos critérios declarados — que são
padrão arquitetural, design patterns e princípios de projeto. Pior: uma implementação apressada de
autenticação é uma implementação insegura, e entregar segurança mal feita é pior do que declarar que
ela não está no escopo.
**Veredito:** rejeitada.

### B) HTTP Basic

**Prós:** trivial de implementar; suportado pelo Swagger UI.
**Contras:** ainda exige armazenar credenciais, e resolve o problema errado — continuaríamos sem
distinguir papéis sem uma tabela de usuários. Ganha-se a aparência de segurança sem a substância.
**Veredito:** rejeitada. Segurança aparente é pior que ausência declarada de segurança.

### C) Nenhuma noção de identidade

Qualquer requisição pode fazer qualquer operação.

**Prós:** o mais simples possível.
**Contras:** RN-11 e RN-12 deixariam de existir, e com elas duas regras de negócio legítimas.
Empobreceria o domínio para economizar quase nada — a identidade em si é barata; a autenticação é que
não é.
**Veredito:** rejeitada.

### D) OAuth2 com provedor institucional

**Prós:** o que um sistema universitário real faria.
**Contras:** depende de provedor externo indisponível para o trabalho; impossível de demonstrar
offline.
**Veredito:** rejeitada.

### E) Identidade declarada na requisição, autorização plenamente implementada — **escolhida**

**Veredito:** escolhida.

## Decisão

**Implementamos a autorização por inteiro e não implementamos autenticação.**

A identidade chega por dois cabeçalhos HTTP em toda requisição:

| Cabeçalho | Conteúdo | Exemplo |
|---|---|---|
| `X-User-Id` | Matrícula ou e-mail do ator | `2019001234` |
| `X-User-Role` | `REQUESTER` ou `MANAGER` | `MANAGER` |

O sistema **confia** no que é declarado. Não há verificação de credencial, e não existe entidade
`User` nem tabela de usuários ([ADR-0003](0003-persistencia-sqlite-repository.md)): `requester_id` e
`decided_by` são identificadores opacos, sem integridade referencial.

Sobre isso, as regras RN-11 e RN-12 são aplicadas integralmente: um `REQUESTER` que tente aprovar uma
reserva recebe `403 Forbidden`; um `REQUESTER` que tente cancelar reserva de outra pessoa também. A
verificação de papel acontece na camada de apresentação (é uma preocupação de borda); a verificação
de propriedade — "esta reserva é sua?" — acontece no domínio, porque depende do estado da reserva.

**Esta configuração é insegura por construção e não deve ser exposta em rede.** O README traz esse
aviso em destaque.

## Consequências

### Positivas

- **As regras de negócio de autorização existem e são testáveis**, que é o que importa para a
  avaliação.
- **O tempo economizado foi para o domínio.** Políticas, estados e eventos ganharam o cuidado que a
  tela de login teria consumido.
- **O Swagger UI fica trivial de demonstrar.** Trocar de papel é editar um cabeçalho — a defesa
  mostra a mesma requisição sendo aceita e recusada conforme o papel, o que evidencia a regra melhor
  do que um fluxo de login evidenciaria.
- **Migrar para autenticação real seria localizado.** A identidade é produzida por uma dependência
  única em `presentation/dependencies.py`; trocá-la por decodificação de JWT não afetaria nem o
  domínio nem os casos de uso.

### Trade-offs aceitos

- **O sistema não é seguro.** Qualquer cliente pode se declarar `MANAGER`. Assumido e documentado —
  não é um defeito descoberto depois, é uma fronteira desenhada.
- **Sem entidade `User`, não há integridade referencial** sobre `requester_id`. Uma reserva pode
  apontar para uma matrícula inexistente, e o sistema não perceberá.
- **Sem trilha de auditoria confiável.** `decided_by` registra o que foi declarado, não o que foi
  verificado.

### Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **O avaliador interpretar a ausência de autenticação como descuido** e não como decisão | Média — é o risco mais relevante deste ADR | Aviso destacado no README, seção dedicada no [documento de defesa](../DEFESA.md), e este ADR referenciado nos dois. A distinção entre autenticação e autorização é apresentada explicitamente. |
| O sistema ser exposto em rede nesta configuração | Baixa (é trabalho acadêmico) | Aviso no README; a aplicação sobe em `localhost` por padrão. |
| A verificação de papel se espalhar por vários pontos e ficar inconsistente | Média | A verificação de papel fica em uma única dependência de apresentação, reutilizada por todas as rotas; a de propriedade fica no domínio. |

## Conformidade

- **`src/agendalab/presentation/dependencies.py`** — único ponto que lê `X-User-Id` e `X-User-Role` e
  constrói o `Actor`. Se outro arquivo ler esses cabeçalhos, a decisão foi violada.
- **Ausência de tabela de usuários** em `infrastructure/persistence/models.py` e no
  [diagrama ER](../ARQUITETURA.md#10-modelo-entidade-relacionamento).
- **Ausência de dependência de biblioteca de autenticação** (`python-jose`, `passlib`, `bcrypt`) no
  `pyproject.toml`.
- **`tests/e2e/test_autorizacao.py`** — verifica que `REQUESTER` recebe `403` ao aprovar, que
  `MANAGER` consegue, e que um `REQUESTER` não cancela reserva alheia.
- **Aviso presente no README**, seção de limitações.

## Referências

- [ESPECIFICACAO §3 — Atores](../ESPECIFICACAO.md#3-atores)
- [ESPECIFICACAO §5.4 — Ciclo de vida e autorização](../ESPECIFICACAO.md#54-ciclo-de-vida-e-autorização)
- [ADR-0003 — Persistência](0003-persistencia-sqlite-repository.md)
