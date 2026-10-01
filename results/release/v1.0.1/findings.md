# Empirical results — v1.0.1 correction

This directory adds inspectable empirical results to the published v1 series. Version 1.0.0 contained the analysis pipeline and release machinery but did not commit derived data or generated study results.

The tables here are deliberately limited to values that can be tied to published sources and inspected directly in GitHub.

## Housing sale values: Q1 2019 → Q1 2026

Across the 24 Lisboa freguesias:

- median increase: **66.29%**;
- mean increase: **65.37%**;
- largest percentage increase: **Beato, +105.54%**;
- smallest percentage increase: **Santa Maria Maior, +12.33%**.

The largest absolute increase was Parque das Nações: **€3,096/m²**.

These are nominal published median sale values. No inflation adjustment is applied.

Source coverage is documented in `data/release/v1.0.1/README.md`.

## Weighted Local Accommodation: November 2019 → November 2022

The CML monitoring report publishes weighted AL counts by freguesia.

From the displayed parish rows:

- 20 freguesias increased;
- 4 decreased;
- displayed parish-row sum: **22,940 → 24,080**, an increase of **1,140**.

The source report publishes the Lisboa total as **22,941 in 2019** and **24,080 in 2022**. The one-unit 2019 discrepancy is preserved explicitly because the report notes that parish values are rounded while the city total is calculated by the source.

The largest absolute displayed increases were:

- Estrela: +178;
- Arroios: +143;
- Ajuda: +114;
- Alcântara: +113;
- Campo de Ourique: +111.

The largest displayed decreases were:

- Santa Maria Maior: −111;
- São Vicente: −56;
- Parque das Nações: −20;
- Santo António: −16.

## Same-period housing / AL association: June 2018

Using the published 24-freguesia cross-section:

- Pearson r = **0.638**, p = **0.000799**;
- Spearman rho = **0.796**, p = **0.00000337**.

This is a strong positive descriptive cross-sectional association: freguesias with more local-accommodation establishments tended also to have higher published housing values in the June-2018 table.

It is **not causal evidence**. The variables are strongly spatially and structurally confounded, and the AL measure is an establishment count rather than population-normalized pressure.

## 2021 AL pressure and population change

Using the CML/INE 2021 table:

- Pearson r between AL/AFC ratio and population change 2011→2021 = **−0.762**, p = **0.0000148**;
- Spearman rho = **−0.210**, p = **0.325**.

The large difference between Pearson and Spearman means the linear result should not be summarized as a general monotone relationship. The strongest negative population changes occur in central freguesias with exceptionally high AL/AFC ratios, especially Misericórdia and Santa Maria Maior.

This is descriptive evidence only.

## What these results are — and are not

These committed results are a **post-release empirical correction** to make the repository inspectable.

They are not a claim that every v1 pipeline output has now been reproduced from archived raw snapshots inside GitHub. The raw source snapshots remain outside version control.

The package pipeline remains the preferred path for full reproducible analysis when the archived source files are available. The committed release tables provide transparent empirical evidence while respecting raw-data size and redistribution constraints.
