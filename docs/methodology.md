# Methodology

The methodological objective is to build a consistent longitudinal spatial panel before estimating relationships between urban variables.

## Unit of analysis

The target representation is:

[
(i, t)
]

where (i) identifies a stable Lisbon spatial unit and (t) identifies a comparable time period.

A candidate panel may contain variables such as:

[
left(
P_{i,t},
M_{i,t},
D_{i,t},
T_{i,t},
I_{i,t}
ight),
]

where:

- (P) represents housing-market measures;
- (M) represents mobility measures;
- (D) represents demographic measures;
- (T) represents tourism-related measures;
- (I) represents infrastructure or accessibility measures.

## Spatial consistency

Administrative boundaries can change over time. Boundary consistency must therefore be established before comparing neighbourhood trajectories.

The preferred strategy is to use one stable reference geography and transform historical observations onto that geography only when the mapping is defensible.

## Temporal consistency

Series should be compared at a common frequency where possible. Higher-frequency data should not automatically be preferred if it creates large gaps across other variables.

Potential analysis frequencies include:

- annual panels for broad structural change;
- quarterly panels when housing and mobility coverage support them;
- event windows for specific infrastructure interventions.

## Descriptive analysis first

The first analytical stage should establish:

- spatial distributions;
- temporal trends;
- change maps;
- missingness patterns;
- coverage differences;
- outliers and discontinuities;
- correlations and spatial autocorrelation.

Only after these checks should multivariable models be introduced.

## Longitudinal models

A possible later-stage specification is:

[
log(P_{i,t}) =
alpha_i + gamma_t +
eta^	op X_{i,t} +
arepsilon_{i,t},
]

where (alpha_i) captures time-invariant spatial effects, (gamma_t) captures common period effects, and (X_{i,t}) contains observed time-varying neighbourhood characteristics.

This is a modelling framework, not a causal claim. Identification assumptions must be stated separately for any causal interpretation.

## Spatial dependence

Neighbouring areas are not statistically independent by default. Spatial autocorrelation should be diagnosed explicitly and, where necessary, incorporated into inference or modelling rather than ignored.
