# Roadmap de implementação — AgendaLab

A base arquitetural está concluída: [especificação](ESPECIFICACAO.md), [9 ADRs](ADRs/README.md),
[10 diagramas](ARQUITETURA.md) e o esqueleto do [documento de defesa](DEFESA.md). Este documento
registra como a implementação foi fatiada e em que ordem.

O trabalho é dividido em **13 etapas**, entregues uma a uma. A ordem não é arbitrária: ela segue a
regra de dependência do [ADR-0001](ADRs/0001-arquitetura-em-camadas.md), construindo **de dentro para
fora**. O domínio vem primeiro porque não depende de nada; a apresentação vem por último porque
depende de tudo.

## Sequenciamento

| # | Etapa | Entrega | Camada |
|---|---|---|---|
| 01 | Esqueleto e regra de dependência | árvore de pacotes + teste de arquitetura funcionando | — |
| 02 | Intervalo, entidades e erros | `TimeSlot` (RN-02, RN-03), `Space`, `Booking`, `Actor`, erros tipados | domínio |
| 03 | Ciclo de vida da reserva | padrão State: as 12 células da [tabela de transições](ESPECIFICACAO.md#55-tabela-de-transições-de-estado) | domínio |
| 04 | Políticas de admissão | padrão Strategy: as três políticas por tipo de espaço (RN-08 a RN-10) | domínio |
| 05 | Eventos de reserva | padrão Observer: publicador com isolamento de falhas (RN-15) | domínio |
| 06 | Interfaces de repositório | contratos declarados no domínio + duplas de teste em memória | domínio |
| 07 | Casos de uso de espaço | UC-01, UC-02, UC-03 | aplicação |
| 08 | Solicitar reserva | UC-04 — onde os três padrões colaboram | aplicação |
| 09 | Decisões sobre a reserva | UC-05, UC-06, UC-07 | aplicação |
| 10 | Persistência e notificadores | SQLAlchemy, mappers, repositórios e observadores concretos | infraestrutura |
| 11 | API REST | routers, schemas, tradução de erros, composição de dependências | apresentação |
| 12 | Testes ponta a ponta | fluxos completos pela API e verificação da cobertura | — |
| 13 | Defesa e fechamento | preencher o documento de defesa e conferir a *Conformidade* dos ADRs | — |

**O teste de arquitetura vem na etapa 01, antes de qualquer regra de negócio.** É deliberado: a
restrição precisa existir antes do código que ela restringe, senão vira auditoria retrospectiva em
vez de guarda-corpo.

## Regras que valem para toda etapa

1. **TDD.** O teste vem primeiro ([ADR-0009](ADRs/0009-estrategia-de-testes.md)). Uma etapa entrega
   comportamento testado, não arquivos criados.
2. **Rastreabilidade.** Toda regra implementada cita a regra numerada correspondente da
   [especificação](ESPECIFICACAO.md#5-regras-de-negócio) no teste ou no código.
3. **A suíte fica verde.** Nenhuma etapa termina com teste quebrado.
4. **Um commit semântico por etapa**, no mínimo.
5. **Divergência é defeito.** Se a implementação revelar que a especificação ou um ADR estão errados,
   corrige-se o documento na mesma etapa — nunca se deixa o código e o documento discordando.

## Cronograma

Prazo de entrega: **11/08/2026, 23h59**.

| Dia | Marco |
|---|---|
| 05/08 | ✅ Base arquitetural: especificação, 9 ADRs, 10 diagramas, esqueleto da defesa |
| 06/08 | Etapas 01 a 05 — domínio completo, com os três padrões |
| 07/08 | Etapas 06 a 09 — repositórios e os sete casos de uso |
| 08/08 | Etapas 10 e 11 — persistência e API no ar |
| 09/08 | Etapas 12 e 13 — testes ponta a ponta e documento de defesa |
| 10–11/08 | Folga: revisão final e entrega no SIGAA |

Os dois dias finais são folga deliberada. Foi ela que tornou aceitável o escopo escolhido — sem
margem, o recomendável seria um domínio mais simples.
