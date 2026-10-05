# Historical RNAL data request

**Prepared 2026-10-04. Status: drafts only; neither request has been sent and no provider response has been received.**

The next v1.2 evidence step is to request the historical RNAL series from CML and Turismo de Portugal. The current official feeds and the assessed community archive cannot establish a complete 2019–2025 parish series. This package turns the [coverage requirements](rnal-coverage.md#required-extract) into two Portuguese messages, a shared [technical annex](requests/rnal-historical-data.md), and a [CSV of requested dates and parishes](requests/rnal-history-scope.csv).

The CSV contains **600 requested keys: 25 quarter ends × 24 parishes**, from 2019-12-31 to 2025-12-31. It contains no RNAL observations or placeholder zeros. Parish identifiers and names come from the [committed reference used in the source audit](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/33336c0091e3978d7f2fc358ae4555195015f6b5/results/source-audit/2026-10-01/census_context.csv). Its columns are `quarter` (`YYYYQn`), `reference_date` (ISO calendar date), `municipality_code` (`1106`), `freguesia_id` (six-character administrative code), and `freguesia_name` (UTF-8). Rows are ordered by date, then parish code.

The audited housing capture has an additional quarter, 2026 Q1. The requested RNAL window targets the seven annual Q4 observations for 2019–2025; those 168 parish-year keys are a subset of the 600 quarterly keys. A future integration must explicitly select the common window. This request does not change the existing housing capture, pipeline, or study designation.

## Public routing contacts

These addresses were checked against official public pages on 2026-10-04. They are routing contacts, not confirmed custodians of the requested archive. No delivery test has been made.

| Recipient | Address | Published purpose |
| --- | --- | --- |
| CML / Lisboa Aberta | `coord.dadosabertos@cm-lisboa.pt` | The [Lisboa Aberta FAQ](https://lisboaaberta.cm-lisboa.pt/index.php/pt/faqs) invites requests for datasets that are not available. Ask for referral to the municipal AL monitoring service where needed. |
| Turismo de Portugal / RNAL | `apoioaoempresario@turismodeportugal.pt` | The [RNAL portal](https://rnt.turismodeportugal.pt/RNT/RNAL.aspx) lists this general contact. Ask for referral to the team responsible for historical RNAL data. |

Turismo de Portugal's [contact page](https://www.turismodeportugal.pt/pt/quem_somos/Contactos/Paginas/default.aspx) requests a subject and a callback telephone number. No private telephone number is included in this public package; the sender can supply it separately if needed.

## Draft to CML / Lisboa Aberta

**Para:** coord.dadosabertos@cm-lisboa.pt

**Assunto:** Pedido de dados históricos de alojamento local por freguesia — Lisboa, 2019–2025

Exmos. Senhores,

No âmbito do projeto de investigação reprodutível [Lisbon Spatial Dynamics](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics), solicito informação sobre a disponibilidade de dados históricos do Registo Nacional do Alojamento Local para o município de Lisboa. O estudo compara valores de habitação e pressão do alojamento local nas 24 freguesias, sem pretender estabelecer relações causais.

Pretende-se obter, de preferência, agregados por freguesia no final de cada trimestre entre 2019 T4 e 2025 T4: número de registos abrangidos pela definição administrativa de stock e respetiva capacidade registada nessa data. O anexo técnico e o CSV identificam as 600 combinações de data e freguesia e as definições a esclarecer. Se existirem apenas ficheiros mensais ou outro formato de arquivo, agradeço a indicação dos ficheiros disponíveis e das respetivas datas de referência. Não são necessários nomes, NIF, contactos ou moradas dos titulares ou estabelecimentos.

O relatório municipal de caracterização e monitorização de dezembro de 2022 descreve transferências mensais de dados entre o Turismo de Portugal e os serviços municipais (páginas impressas 2 e 87). Poderão indicar se estes ficheiros, ou agregados históricos equivalentes, estão disponíveis para investigação?

Para validar a série, agradeço também a definição e, se disponível, a decomposição por freguesia dos 20 134 registos não ponderados publicados para o final de novembro de 2022 (página impressa 38). A reconstrução limitada aos registos conservados na consulta SOAP de 1 de outubro de 2026 contém apenas 11 525 registos para aquela data. Esta diferença não foi interpretada como número de encerramentos; procuramos esclarecer âmbito, estados e revisões.

Poderão informar quais os períodos disponíveis, as condições de acesso, citação e conservação dos ficheiros e a possibilidade de publicar agregados e disponibilizar uma versão arquivada para reprodução do estudo? Se necessário, agradeço o encaminhamento deste pedido ao serviço responsável pela monitorização do alojamento local.

Com os melhores cumprimentos,

Diogo Ribeiro

**Anexos preparados:** [especificação técnica](requests/rnal-historical-data.md) e [grelha de datas e freguesias](requests/rnal-history-scope.csv).

## Draft to Turismo de Portugal

**Para:** apoioaoempresario@turismodeportugal.pt

**Assunto:** RNAL — disponibilidade de histórico por freguesia de Lisboa, 2019–2025

Exmos. Senhores,

No âmbito do projeto de investigação reprodutível [Lisbon Spatial Dynamics](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics), solicito o encaminhamento deste pedido à equipa responsável pelos dados históricos do RNAL. Procuramos uma série para as 24 freguesias de Lisboa, com referência ao final de cada trimestre de 2019 T4 a 2025 T4, para estudar associações entre habitação e alojamento local.

A opção preferida é um ficheiro de agregados com o número de registos abrangidos pelo stock administrativo e a capacidade registada em cada data, acompanhado das definições de estado, datas e geografia. O anexo técnico e o CSV especificam as 600 combinações pretendidas. Caso apenas exista um arquivo de extratos ou de alterações, agradeço informação sobre a sua cobertura e possibilidade de acesso a campos mínimos, sem nomes, NIF, contactos ou moradas.

As consultas SOAP e GIS de 1 de outubro de 2026 não permitem confirmar a cobertura histórica: a consulta SOAP tem 11 865 registos e nenhuma data de cessação preenchida; existem 172 divergências de freguesia entre registos partilhados pelas duas interfaces. Ambas apresentam sete datas de registo anteriores a 2000. As consultas ocorreram em horas diferentes. Mantivemos os valores originais e não presumimos qual das interfaces está correta.

Agradeço esclarecimento sobre a conservação de registos cessados ou cancelados, eventuais reposições de estado, a distinção entre data de registo, início de atividade e efeito administrativo, o histórico da capacidade e o método de atribuição de freguesia. Existe um arquivo que permita reproduzir o stock em cada data, incluindo os registos já ausentes das consultas atuais?

Agradeço ainda informação sobre períodos disponíveis, revisões, condições de acesso e citação, conservação para reprodução científica e publicação de agregados. Se os dados ou a documentação já estiverem publicados, será suficiente indicar o respetivo endereço e versão.

Com os melhores cumprimentos,

Diogo Ribeiro

**Anexos preparados:** [especificação técnica](requests/rnal-historical-data.md) e [grelha de datas e freguesias](requests/rnal-history-scope.csv).

## Evidence supplied with either request

The annex links to the [archived municipal report](https://arquivo.pt/noFrame/replay/20260216185851id_/https://www.lisboa.pt/fileadmin/portal/temas/economia/alojamento_local/RelatorioCaracterizacaoMonitorizacaoAlojamentoLocal.pdf) and the repository's [official-feed comparison](rnal-coverage.md), [published parish benchmarks](cml-historical-benchmarks.md), and [community capture assessment](rnal-archive-coverage.md). The numerical statements in the drafts refer to those dated captures, not to a fresh registry query. The community capture gaps are evidence about those exports and are not attributed to a defect in the official service.

## How a reply would be assessed

Record the actual delivery date, channel and any case reference only after dispatch. Preserve any response and its attachments outside public Git, with retrieval time, original bytes, SHA-256 and the provider's access/reuse terms. Publish only the relevant methodological conclusions and permitted aggregates; do not publish private correspondence or contact details by default.

| Returned material | Next research action |
| --- | --- |
| Complete quarterly aggregates | Check all 600 keys, reference dates, duplicates, missingness, municipality totals and definitions. Reconcile the historical benchmarks and document boundary harmonisation before accepting the series. |
| Monthly snapshots or event history | Verify exact observation/effective dates, retained cancelled records, baseline coverage, event ordering and capacity history. Reconstruct quarter ends only where the source supports them. |
| Only annual Q4 observations | Preserve as a partial return: 168 keys can support an annual comparison after validation, but do not satisfy the requested quarterly stock/flow coverage. Record any study-design change explicitly. |
| Current export, incomplete periods, or unclear semantics | Retain as qualified evidence and identify the unresolved requirements. Do not fill missing quarters from current survivors or convert missing values to zero. |

A returned file is not automatically a study input. The current `build-study-v1` interface consumes registry records with registration/cessation dates; it has no historical-aggregate or multi-event importer. Integrating an accepted return will require a reviewed adapter and provenance checks, including an explicit common-window selection. Stock differences cannot supply separate registration, cessation, cancellation and reinstatement flows. A file with only stock and capacity may resolve the core annual exposure while leaving the full pipeline's flow fields or bed-capacity fields unavailable.

The request package therefore leaves v1.2 open until the evidence, integration and reproducible run satisfy the [roadmap](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/blob/main/ROADMAP.md).
