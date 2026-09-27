# Reproducibility

Reproducibility applies to data acquisition, transformation, analysis, and documentation.

## Data layers

The repository separates data into three stages:

- `data/raw/` — original source material;
- `data/interim/` — cleaned or harmonised intermediate data;
- `data/processed/` — analysis-ready derived datasets.

These directories are intentionally excluded from version control except for their placeholders.

## Provenance

Every generated dataset should be reproducible from:

1. a documented source;
2. a versioned acquisition or import step;
3. explicit transformations;
4. validation checks;
5. a deterministic output contract where the upstream data permit it.

## Configuration

Values that define an analysis run should live in configuration rather than being scattered through notebooks or source files. Examples include:

- study period;
- spatial reference;
- geographic level;
- source paths;
- output locations;
- variable selections.

## Notebooks

Notebooks may be used for exploratory analysis and communication, but reusable logic belongs in `src/lisbon_spatial_dynamics/`.

A notebook should be able to start from documented processed inputs rather than depending on hidden state from another notebook.

## Documentation validation

Documentation is part of the build. CI runs:

```bash
poetry run mkdocs build --strict
```

Warnings that break the documentation build should be treated as repository defects rather than ignored.
