# v1.0.1 committed empirical results

This directory contains generated/derived result artifacts that can be inspected without running the package.

## Files

- `summary_metrics.csv` — compact descriptive metrics and correlation results.
- `association_results.csv` — the two committed correlation analyses.
- `findings.json` — machine-readable results summary.
- `findings.md` — human-readable interpretation and limitations.

The corresponding input tables are in:

```text
data/release/v1.0.1/
```

## Why this exists

The published v1.0.0 release shipped the reproducible pipeline but no committed empirical data/results. v1.0.1 corrects that release gap.

Large raw source snapshots remain outside Git. Their provenance and the exact scope of each curated table are documented alongside the committed data.

## Interpretation

All relationships in this correction are descriptive. No causal effect is claimed.
