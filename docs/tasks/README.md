# Roadmap da implementação — AgendaLab

A implementação é fatiada em tasks entregues uma a uma. Cada task vira um arquivo `NN-nome.md` neste
diretório, com objetivo, arquivos afetados, critérios de aceite e os testes que a comprovam.

> **Estado:** as tasks ainda não foram detalhadas. Este documento registra o sequenciamento previsto
> e as regras que valem para todas elas. O detalhamento é a próxima etapa, feita em conversa
> separada.

## Sequenciamento previsto

A ordem segue a regra de dependência do [ADR-0001](../ADRs/0001-arquitetura-em-camadas.md): constrói
de dentro para fora. O domínio primeiro, porque não depende de nada; a apresentação por último,
porque depende de tudo.

| Fase | Escopo | Depende de |
|---|---|---|
| **1 — Esqueleto** | Árvore de pacotes, `tests/architecture/test_dependency_rule.py` funcionando sobre pacotes vazios | — |
| **2 — Domínio: base** | `TimeSlot` (RN-02, RN-03), `Space`, `Booking`, hierarquia de erros | fase 1 |
| **3 — Domínio: State** | `BookingState` e os quatro estados concretos; as 12 células da tabela de transições | fase 2 |
| **4 — Domínio: Strategy** | `BookingPolicy`, `PolicyContext`, as três políticas e o mapa de resolução | fase 2 |
| **5 — Domínio: Observer** | Eventos, `EventPublisher`, isolamento de falhas de observador | fase 2 |
| **6 — Interfaces de repositório** | `SpaceRepository`, `BookingRepository` e as implementações em memória | fase 2 |
| **7 — Aplicação** | Os sete casos de uso, testados contra os repositórios em memória | fases 3 a 6 |
| **8 — Infraestrutura** | Modelos SQLAlchemy, mappers, repositórios concretos, observadores concretos | fase 6 |
| **9 — Apresentação** | Routers, schemas Pydantic, tradução de erros, composição de dependências | fases 7 e 8 |
| **10 — Ponta a ponta** | Testes de fluxo completo pela API e verificação da cobertura | fase 9 |
| **11 — Defesa** | Preencher o [documento de defesa](../DEFESA.md): trechos reais, capturas de tela, saída dos testes | fase 10 |
| **12 — Fechamento** | Verificar que todo caminho citado nas seções *Conformidade* dos ADRs existe; revisão final; push | fase 11 |

**O teste de arquitetura vem na fase 1, antes de qualquer regra de negócio.** É deliberado: a
restrição precisa existir antes do código que ela restringe, senão ela vira auditoria retrospectiva
em vez de guarda-corpo.

## Regras que valem para toda task

1. **TDD.** O teste vem primeiro ([ADR-0009](../ADRs/0009-estrategia-de-testes.md)). Uma task entrega
   comportamento testado, não arquivos criados.
2. **Rastreabilidade.** Toda regra implementada cita a regra numerada correspondente da
   [especificação](../ESPECIFICACAO.md#5-regras-de-negócio) no teste ou no código.
3. **A suíte fica verde.** Nenhuma task termina com teste quebrado.
4. **Um commit semântico por task**, no mínimo.
5. **Divergência é defeito.** Se a implementação revelar que a especificação ou um ADR estão errados,
   corrige-se o documento na mesma task — nunca se deixa o código e o documento discordando.

## Cronograma até a entrega

Prazo: **11/08/2026, 23h59**.

| Dia | Marco |
|---|---|
| 05/08 | ✅ Base arquitetural: git, especificação, 9 ADRs, 10 diagramas, esqueleto da defesa |
| 06/08 | Detalhamento das tasks + fases 1 a 5 (domínio completo) |
| 07/08 | Fases 6 e 7 (repositórios e casos de uso) |
| 08/08 | Fases 8 a 10 (infraestrutura, API e testes ponta a ponta) |
| 09/08 | Fase 11 (documento de defesa preenchido) |
| 10–11/08 | Fase 12 e folga: revisão, push e entrega no SIGAA |

Os dois dias finais são folga deliberada. Foi ela que tornou aceitável o escopo escolhido — sem
margem, o recomendável seria um domínio mais simples.
