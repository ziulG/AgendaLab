# ADR-0008: Manter documentação e diagramas como código, em Markdown e Mermaid

| | |
|---|---|
| **Status** | **Aceito** |
| **Data** | 05/08/2026 |
| **Decisor** | Luiz Cutrim |
| **Tags** | `documentação`, `diagramas`, `processo` |
| **Relacionados** | [ADR-0001](0001-arquitetura-em-camadas.md), [ADR-0009](0009-estrategia-de-testes.md) |

## Contexto

O enunciado exige documentação em `/docs`, visões C4 de Nível 1 e Nível 2, e permite explicitamente
que os diagramas sejam gerados por código (Mermaid.js ou PlantUML). Exige também ADRs preenchidos e,
como material de defesa, um documento formal.

O problema real por trás desse requisito é conhecido: **documentação de arquitetura envelhece mais
rápido que o código**. Um diagrama exportado como PNG e anexado ao repositório está desatualizado na
primeira refatoração, e ninguém percebe, porque nada quebra. Com a implementação ainda por vir, é
certo que estes documentos serão editados várias vezes nos próximos dias.

## Alternativas consideradas

### A) Ferramenta gráfica com exportação de imagem (draw.io, Lucidchart)

**Prós:** controle total sobre o layout; resultado visualmente mais polido; sem limitações de
sintaxe.
**Contras:** o artefato versionado vira um binário — não é revisável em diff, e a fonte editável
tende a viver fora do repositório. Atualizar exige abrir a ferramenta, exportar e substituir o
arquivo, um atrito que na prática faz o diagrama parar de ser atualizado.
**Veredito:** rejeitada.

### B) PlantUML

**Prós:** o mais maduro para UML; suporte de primeira classe ao C4 pela biblioteca `C4-PlantUML`, com
layout melhor que o do Mermaid; cobre diagramas que o Mermaid não faz.
**Contras:** exige Java e o `plantuml.jar` para renderizar localmente, ou depender de servidor
externo. **O GitHub não renderiza PlantUML nativamente** — o diagrama apareceria como bloco de texto
para quem abrisse o repositório no navegador, que é exatamente como o trabalho será avaliado.
**Veredito:** rejeitada. A renderização nativa no GitHub é decisiva quando a entrega é um link de
repositório.

### C) Structurizr DSL

**Prós:** a ferramenta canônica do C4 Model, criada pelo autor da notação; um único modelo gera todos
os níveis com consistência garantida.
**Contras:** exige ferramenta própria para renderizar; não aparece no GitHub; curva de aprendizado
desproporcional para quatro diagramas C4.
**Veredito:** rejeitada.

### D) Markdown com Mermaid.js — **escolhida**

**Prós:** **o GitHub renderiza Mermaid nativamente** dentro de blocos de código em arquivos `.md`. O
diagrama é texto: aparece em diff, é revisável, e vive no mesmo commit da mudança que o motivou. Zero
dependência de ferramenta para o leitor.
**Contras:** menos controle de layout que uma ferramenta gráfica; suporte a C4 limitado (ver
sub-decisão).
**Veredito:** escolhida.

## Decisão

Toda a documentação vive em `/docs` como **Markdown**, e todos os diagramas são **Mermaid.js**
embutido em blocos de código, versionados junto com o projeto. Não há imagem binária de diagrama no
repositório.

### Sub-decisão: notação C4 por `flowchart`, não pelas diretivas nativas

O Mermaid oferece as diretivas `C4Context`, `C4Container` e `C4Component`. Elas foram **testadas
antes de decidir**, não descartadas por suposição.

Os três diagramas foram escritos com a sintaxe nativa e renderizados com o `mermaid-cli`. Resultado:
a sintaxe é aceita e produz saída, mas **o auto-layout posiciona os rótulos das relações sobre as
caixas**, tornando o texto ilegível em vários pontos. O ajuste via `UpdateLayoutConfig` não corrigiu
o problema. As diretivas C4 são marcadas como experimentais na documentação do Mermaid, e o
comportamento observado é coerente com isso.

Os mesmos diagramas foram então reescritos como `flowchart` aplicando a **convenção visual do C4
Model** — a paleta oficial (azul-escuro para pessoa, azul para o sistema em foco, cinza para sistema
externo, azul-claro para componente) e a rotulagem `Nome / [Tipo] / Descrição`. O resultado é legível
e o layout é controlável.

**Decidimos pelo `flowchart` com notação C4.** A semântica do C4 é preservada — os níveis, os tipos
de elemento e a paleta são os do modelo. O que se perde é a diretiva específica do Mermaid, que é
detalhe de ferramenta, não de notação. O ganho é um diagrama que a banca consegue ler.

### Verificação automatizada

Um bloco Mermaid com erro de sintaxe aparece no GitHub como bloco quebrado — falha silenciosa até
alguém abrir a página. Para evitar que isso chegue ao avaliador, `scripts/valida_diagramas.py`
extrai todo bloco ```mermaid dos arquivos de `/docs` e submete cada um ao `mermaid-cli`, falhando se
algum não renderizar.

### Organização

| Documento | Papel |
|---|---|
| [`ESPECIFICACAO.md`](../ESPECIFICACAO.md) | fonte da verdade do domínio: regras, casos de uso, contratos |
| [`ARQUITETURA.md`](../ARQUITETURA.md) | as visões e todos os diagramas |
| [`GLOSSARIO.md`](../GLOSSARIO.md) | linguagem ubíqua, PT-BR ↔ identificadores em inglês |
| [`ADRs/`](README.md) | uma decisão por arquivo, formato Nygard estendido |
| [`DEFESA.md`](../DEFESA.md) | documento de defesa (Opção B do enunciado) |

Os ADRs seguem o formato de Michael Nygard — Contexto, Decisão, Consequências, como o enunciado
exige — estendido com **Alternativas consideradas** e **Conformidade**. A segunda é o que diferencia
estes ADRs de prosa justificativa: cada decisão aponta o arquivo e o teste que comprovam que ela está
sendo respeitada.

**Idioma:** documentação em português; código em inglês. O [glossário](../GLOSSARIO.md) liga os dois.

## Consequências

### Positivas

- **O diagrama envelhece junto com o código, no mesmo commit.** Não há passo manual de exportação
  para esquecer.
- **A revisão funciona.** Mudança de arquitetura aparece como diff de texto legível.
- **O avaliador não instala nada.** Abre o repositório no GitHub e vê os diagramas renderizados.
- **Erro de sintaxe é detectado antes do commit**, pelo validador.
- **Os ADRs viram registro auditável**, e não justificativa retrospectiva.

### Trade-offs aceitos

- **Layout menos polido** que o de uma ferramenta gráfica. Diagramas grandes ficam à mercê do
  auto-layout do Mermaid, e a única forma de influenciá-lo é reordenar as declarações.
- **Perda das diretivas C4 nativas.** Ganha-se legibilidade e perde-se a semântica explícita que uma
  ferramenta C4 dedicada ofereceria. Registrado aqui para que a escolha não seja lida como
  desconhecimento da diretiva.
- **Nada garante que documento e código estejam de acordo.** O validador confere sintaxe de diagrama,
  não veracidade de conteúdo. Um diagrama sintaticamente válido pode descrever uma arquitetura que o
  código não implementa — por isso a seção Conformidade de cada ADR aponta testes, que essa sim é
  verificação real.
- **Informação duplicada entre documentos.** A tabela de transições de estado aparece na
  especificação, no [ADR-0005](0005-state-ciclo-de-vida-da-reserva.md) e no diagrama. A duplicação é
  deliberada — cada documento precisa ser legível por si — e o custo é mantê-las sincronizadas.

### Riscos e mitigação

| Risco | Probabilidade | Mitigação |
|---|---|---|
| **O GitHub renderizar diferente do `mermaid-cli`**, por diferença de versão do Mermaid | Baixa, após abandonar as diretivas experimentais | `flowchart`, `classDiagram`, `stateDiagram-v2`, `sequenceDiagram` e `erDiagram` são recursos estáveis, suportados há anos. Verificação visual no GitHub após o primeiro push, antes da entrega. |
| **Tabelas duplicadas saindo de sincronia** entre documentos | Média | Checagem explícita na revisão final; as tabelas duplicadas estão nomeadas e cruzadas por link em ambos os sentidos. |
| **Documentação divergir do código** durante a implementação | Alta — é o risco permanente de toda documentação | A seção Conformidade de cada ADR aponta testes concretos; a última task de implementação verifica que todo caminho citado em Conformidade existe de fato. |

## Conformidade

- **`docs/` contém apenas Markdown** e o PDF do enunciado; nenhuma imagem de diagrama versionada.
- **`scripts/valida_diagramas.py`** roda sem erro sobre `docs/`:
  ```bash
  python3 scripts/valida_diagramas.py
  ```
- **Nenhum bloco ```mermaid usa `C4Context`, `C4Container` ou `C4Component`** — coerência com a
  sub-decisão.
- **Todo ADR tem as seções obrigatórias:** Contexto, Alternativas consideradas, Decisão,
  Consequências (com trade-offs preenchidos), Conformidade.
- **Os diagramas renderizam no GitHub**, verificado visualmente após o push.

## Referências

- [ARQUITETURA.md](../ARQUITETURA.md) — todos os diagramas
- [Índice dos ADRs](README.md)
- Simon Brown — [C4 Model](https://c4model.com)
- Michael Nygard — *Documenting Architecture Decisions* (2011)
