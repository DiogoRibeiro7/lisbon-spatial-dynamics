# Historical RNAL benchmarks from the municipal report

The retained December 2022 municipal report supplies **96 parish-level endpoint values**: two measures for all 24 Lisbon parishes in November 2019 and November 2022. Its capacity table reconciles exactly, showing an increase from **111,492 to 116,218 user-capacity places**, or **4,726**. Its capacity-weighted AL table contains one-unit differences between some displayed levels, changes and totals. Those differences are preserved and reported, not silently corrected.

The [transcribed facts](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/data/benchmarks/cml-rnal-2019-2022) and [generated audit bundle](https://github.com/DiogoRibeiro7/lisbon-spatial-dynamics/tree/main/results/cml-benchmarks/2026-10-03) make these observations inspectable. They supplement the [earlier municipality-level coverage benchmark](rnal-coverage.md).

The [historical capacity comparison](historical-capacity.md) builds on these audited values with population-reference ratios, fixed-group concentration and a parish figure. It reproduces this audit before calculating the additional descriptive outputs.

## Source and meaning

Both tables are from Câmara Municipal de Lisboa's *Relatório de Caracterização e Monitorização do Alojamento Local*, December 2022, attributing the underlying data to Turismo de Portugal/RNAL. The [official PDF URL](https://www.lisboa.pt/fileadmin/portal/temas/economia/alojamento_local/RelatorioCaracterizacaoMonitorizacaoAlojamentoLocal.pdf) returned 404; the exact PDF was retained from an [Arquivo.pt capture](https://arquivo.pt/noFrame/replay/20260216185851id_/https://www.lisboa.pt/fileadmin/portal/temas/economia/alojamento_local/RelatorioCaracterizacaoMonitorizacaoAlojamentoLocal.pdf). This analysis uses that previously acquired file, not a fresh registry reconstruction.

| Table | Printed / PDF page | Measure | Published November 2019 total | Published November 2022 total | Published change |
| --- | --- | --- | ---: | ---: | ---: |
| 18 | 93 / 105 | Capacity-weighted AL units | 22,941 | 24,080 | +1,138 |
| 19 | 95 / 107 | Reported user capacity | 111,492 | 116,218 | +4,726 |

PDF page numbers are one-based. The weighting note for table 18 assigns each establishment its user capacity divided by five, with one unit when capacity is below five. The displayed table values are integers; the underlying precision and rounding convention are unverified. Aggregate capacity alone is insufficient to reconstruct this weighting because the distribution of establishments below the threshold matters.

Table 19 is headed capacity; its 2022 values agree with table 6's total-user-capacity column. This denotes accommodation places as reported, not unique people, occupied places, overnight stays, or verified operation. The report also uses beds terminology in nearby prose; the committed metric retains the user-capacity interpretation supported by table 6.

The table titles and source lines identify **November 2019 and November 2022** but do not state exact observation days. Other report sections use more specific dates, including 1 November and end-November. Those dates are not transferred to these tables. The machine-readable observations retain `2019-11` and `2022-11`; they are not labelled 2019 Q4/2022 Q4, interpolated into intervening quarters, or substituted for quarter-end study observations.

In particular, table 18's 24,080 is a **weighted** total. It must not replace the **20,134 unweighted end-November 2022 registrations** used in the earlier coverage investigation. The measure and date precision differ.

## Arithmetic findings

The capacity table's 24 parish values sum exactly to both municipality totals; every displayed change equals its endpoint difference. Capacity increases in 20 parishes and decreases in four. The largest increases are Campo de Ourique (+638), Arroios (+588), Estrela (+576), Penha de França (+571), and Alcântara (+540). The decreases are Santa Maria Maior (−712), Santo António (−296), São Vicente (−197), and Parque das Nações (−1). These are descriptive changes in reported capacity, without causal attribution.

The following **table 18** rows have differences between the published variation and the difference of displayed endpoints:

| Geography | 2019 displayed | 2022 displayed | Published change | Calculated change | Calculated minus published |
| --- | ---: | ---: | ---: | ---: | ---: |
| Campo de Ourique | 478 | 589 | +112 | +111 | −1 |
| Parque das Nações | 497 | 477 | −21 | −20 | +1 |
| São Domingos de Benfica | 143 | 166 | +22 | +23 | +1 |
| Lisboa total | 22,941 | 24,080 | +1,138 | +1,139 | +1 |

Table 18's displayed parish levels sum to 22,940 for 2019, one less than the published municipality total of 22,941. The 2022 sum agrees at 24,080. Its published parish changes sum to 1,139, one greater than the municipality's published 1,138. The difference between summed parish endpoints is 1,140. These quantities have distinct definitions and are not forced to agree. Rounding of undisplayed values is a possible explanation, but is not established by the available source precision.

## What is committed

The source transcription has 50 rows: 24 parishes plus a municipality row for each table. It preserves both endpoint values and the published variation, with canonical parish identifiers added by exact name matching. The generated `published_observations.csv` has 100 rows: 96 parish observations and four municipality observations, each labelled with metric, unit, scope, reference month, table and page. Municipality rows must be excluded when summing parish observations.

`arithmetic_checks.csv` keeps each published change alongside its calculated counterpart and signed discrepancy. `audit.json` records the table-level sums, discrepancies, source identity, input/code/configuration/output hashes and transcription method. A successful audit establishes coverage and explicit diagnostics; it does not mean every source arithmetic check agrees.

Both source pages were reviewed visually. All 75 capacity-table numbers were also checked against separately extracted PDF text. Table 18's body is an image. Replay verifies the identity of the PDF and transcription, then recomputes the checks; it does not automatically validate manually read cells against the PDF. Source-page review remains necessary for transcription changes.

## Reproduce the audit

Restore the exact source PDF and acquisition manifest named in `configs/cml_benchmarks_2026-10-03.toml`; the transcription and canonical parish reference are already committed. From the repository root with locked dependencies:

```bash
poetry sync --with docs
poetry run python scripts/audit_cml_benchmarks.py --output data/processed/cml-benchmarks-recheck
```

This is an offline command and the output directory must be new. It verifies each input's captured bytes against its pinned hash and size, checks that the acquisition manifest identifies the PDF, and parses the captured CSV bytes. It rejects unknown/duplicate/missing parish rows, mismatched names, invalid numbers, missing municipality totals, and relabelled reference months. Published arithmetic discrepancies are recorded rather than rejected. Both CSVs and the report are published atomically; existing destinations are preserved. Compare CSV hashes and the numeric summary with the committed audit; paths and software/code provenance reflect the replay environment.

The original PDF SHA-256 is `1e446b0b71d55a3f0086b539278810f1875d5e4244174786295489b40fea8195`. It remains in the ignored local workspace; a hash is not a public archive. Only attributed aggregate facts are committed, and no source-document redistribution licence is asserted.

## Implication for v1.2

These are useful historical parish benchmarks, especially for capacity, and can constrain validation of a future monitoring extract. They do not resolve the seven early dates, historical registration membership, cancellations, capacity changes within the interval, or the later analysis endpoint. The definitive study still requires a compatible quarterly series, documented date/geography semantics, and durable input archiving. The existing models and their input-selection policy are unchanged.
