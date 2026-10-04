# Lisbon CAOP2025 reference

`freguesias.geojson` archives the 24-parish reference used by the 2026-10-01 source audit. Coordinates are longitude/latitude in EPSG:4326. It contains administrative polygons and names, with no establishment locations or personal records.

**Attribution:** Direção-Geral do Território (DGT), CAOP2025. Lisbon subset and canonical property names by Lisbon Spatial Dynamics. **Data licence:** [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/), separate from the repository's MIT software licence. The [DGT open-data policy](https://www.dgterritorio.gov.pt/dados-abertos) and [DGT CAOP catalogue entry](https://dados.gov.pt/en/datasets/unidades-administrativas) identify CC BY 4.0; checked 2026-10-04. Version information is on the [official CAOP page](https://www.dgterritorio.gov.pt/atividades/cartografia/cartografia-tematica/caop).

The acquisition requested Lisbon features from DGT's `Hosted/FreguesiaCAOP2025/FeatureServer/7` service with `outSR=4326` on 2026-10-01. The project transformed field names and sorted features to create its canonical reference. `provenance.json` preserves the original acquisition metadata, canonical-reference fingerprint, parent audit and this archive's fingerprint.

The archive is a compact serialization of the original canonical GeoJSON (`ef186f413e10c264761ad4701d0c90aa636a77c88535554644f9d876cbecacf3`, 769,748 bytes): `json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'`, encoded as UTF-8. The parsed documents were checked for exact equality. No coordinates, feature order or properties were changed; no simplification, snapping or geometric repair was applied. Compact serialization produces 306,358 bytes with SHA-256 `e17f542ac4f876e08b97d5a7f0565583a76786f07cafa91ae68eb011fe353dcd`.

This is the **CAOP2025 reference geography** used for comparison. It does not establish that every historical source used identical boundaries. The national raw source and the original raw acquisition files are not included here; this small canonical subset is sufficient to reproduce the housing spatial analysis from a fresh checkout.
