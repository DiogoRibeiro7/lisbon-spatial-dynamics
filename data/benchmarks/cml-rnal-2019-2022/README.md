# Published CML parish benchmarks, November 2019 and November 2022

`published_values.csv` transcribes 150 displayed numeric cells from two tables in Câmara Municipal de Lisboa's *Relatório de Caracterização e Monitorização do Alojamento Local* (December 2022):

| Table | Measure | Printed page | PDF page (one-based) |
| --- | --- | ---: | ---: |
| 18 | Capacity-weighted AL units | 93 | 105 |
| 19 | Reported user capacity | 95 | 107 |

The source is the [official report](https://www.lisboa.pt/fileadmin/portal/temas/economia/alojamento_local/RelatorioCaracterizacaoMonitorizacaoAlojamentoLocal.pdf), retained through an [Arquivo.pt capture](https://arquivo.pt/noFrame/replay/20260216185851id_/https://www.lisboa.pt/fileadmin/portal/temas/economia/alojamento_local/RelatorioCaracterizacaoMonitorizacaoAlojamentoLocal.pdf). Its SHA-256 is `1e446b0b71d55a3f0086b539278810f1875d5e4244174786295489b40fea8195`. Acquisition and source identity are pinned in [the audit configuration](../../../configs/cml_benchmarks_2026-10-03.toml).

Each table has 24 parish rows and one municipality total. Endpoint columns preserve the displayed integers, and `reported_change` preserves the source's variation column, including arithmetic discrepancies. `source_row` reproduces the numbered parish row; zero identifies the unnumbered municipality total. Parish identifiers are added by matching the published names to the canonical IDs in the previously audited Census table. `1106` identifies the municipality and must not be summed with its parish rows.

Table 18's weighting rule is capacity divided by five, with one unit for establishments below five users. These values are not raw establishment counts. Table 19's 2022 values match the total-user-capacity column of table 6. Neither measure establishes occupancy or actual operation. The tables identify reference **months**, without exact observation days; do not relabel them as quarter-end observations.

The transcription was checked visually against both rendered PDF pages on 2026-10-03. All 75 numbers in table 19 were additionally compared against independently extracted PDF text. Table 18's body is an embedded image and required visual reading. Preparation used `pdftoppm`/`pdftotext` 24.04.0; those tools are not required for arithmetic replay. For another visual review, restore the exact source PDF and render its pages, for example:

```bash
pdftoppm -f 105 -l 105 -r 120 -singlefile -png <report.pdf> <table18-output-prefix>
pdftoppm -f 107 -l 107 -r 120 -singlefile -png <report.pdf> <table19-output-prefix>
```

The audit checks file identity, canonical coverage and arithmetic; it does not automatically recover or verify the PDF cells. Review the source pages when changing this transcription. Keep any correction or different source vintage in a new versioned bundle. The PDF and its page images remain outside Git; the repository commits attributed aggregate facts, not the source document. No licence to redistribute the PDF is asserted.

See [the findings and replay instructions](../../../docs/cml-historical-benchmarks.md) for the discrepancy ledger and limitations.
