"""Join audited housing changes to archived geography without inventing RNAL values."""

from __future__ import annotations

import csv
import json
import math
import re
from collections.abc import Mapping
from decimal import Context, Decimal, InvalidOperation, localcontext
from io import StringIO
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import transform
from shapely.plotting import patch_from_polygon

from lisbon_spatial_dynamics.analysis.local_spatial_autocorrelation import LocalMoranResult
from lisbon_spatial_dynamics.spatial.trajectory_choropleths import (
    TrajectoryMapData,
    TrajectoryMapFeature,
)

CHANGE_COLUMNS = (
    "freguesia_id",
    "freguesia_name",
    "baseline_year",
    "latest_year",
    "baseline_eur_m2",
    "latest_eur_m2",
    "change_eur_m2",
    "change_pct",
)


def build_housing_map(
    changes_csv: str,
    geometry_json: str,
    reference: Mapping[str, str],
    *,
    baseline_year: int,
    latest_year: int,
) -> TrajectoryMapData:
    """Validate complete identities, endpoint arithmetic and unsimplified polygons."""
    if not reference or not 1 <= baseline_year < latest_year <= 9999:
        raise ValueError("canonical reference and increasing years required")
    reader = csv.DictReader(StringIO(changes_csv, newline=""))
    if tuple(reader.fieldnames or ()) != CHANGE_COLUMNS:
        raise ValueError("unexpected housing change columns")
    changes = {}
    with localcontext(Context(prec=28)):
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError("malformed housing change row")
            code = row["freguesia_id"]
            if code in changes or code not in reference or row["freguesia_name"] != reference[code]:
                raise ValueError("duplicate or inconsistent housing parish")
            if row["baseline_year"] != str(baseline_year) or row["latest_year"] != str(latest_year):
                raise ValueError("housing comparison window differs")
            try:
                first, last, absolute, percent = (Decimal(row[key]) for key in CHANGE_COLUMNS[4:])
            except InvalidOperation as exc:
                raise ValueError("invalid housing value") from exc
            if not all(value.is_finite() for value in (first, last, absolute, percent)):
                raise ValueError("housing values must be finite")
            if first <= 0 or last <= 0 or absolute != last - first:
                raise ValueError("housing endpoint arithmetic differs")
            if percent != (last - first) / first * Decimal(100) or not math.isfinite(
                float(percent)
            ):
                raise ValueError("housing percentage arithmetic differs")
            changes[code] = float(percent)
    if set(changes) != set(reference):
        raise ValueError("housing changes do not cover the reference")
    document = json.loads(geometry_json)
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise ValueError("geometry must be a FeatureCollection")
    features = document.get("features")
    if not isinstance(features, list):
        raise ValueError("geometry features must be a list")
    mapped: dict[str, TrajectoryMapFeature] = {}
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("invalid geographic feature")
        properties, geometry = feature.get("properties"), feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise ValueError("missing feature properties or geometry")
        code = properties.get("freguesia_id")
        if (
            not isinstance(code, str)
            or not re.fullmatch(r"1106[0-9]{2}", code)
            or code not in reference
            or code in mapped
            or feature.get("id") != code
            or properties.get("name") != reference[code]
            or properties.get("municipality") != "Lisboa"
        ):
            raise ValueError("duplicate or inconsistent geographic parish")
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("parish geometry must be polygonal")
        polygon = shape(geometry)
        if polygon.is_empty or not polygon.is_valid:
            raise ValueError("empty or invalid parish polygon")
        mapped[code] = TrajectoryMapFeature(code, reference[code], changes[code], None, geometry)
    if set(mapped) != set(reference):
        raise ValueError("geometry does not cover the reference")
    return TrajectoryMapData(
        baseline_year, latest_year, tuple(mapped[code] for code in sorted(mapped))
    )


def plot_housing_spatial(data: TrajectoryMapData, local: LocalMoranResult, path: Path) -> None:
    """Plot projected housing changes and FDR classifications using identical boundaries."""
    import matplotlib.pyplot as plt
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize
    from matplotlib.patches import Patch

    observations = {row.freguesia_id: row for row in local.observations}
    colors = {
        "HH": "#b63737",
        "LL": "#245994",
        "HL": "#e69191",
        "LH": "#81b6d9",
        "not_significant": "#e5e5e5",
        "not_evaluated": "#e5e5e5",
        "missing": "#f4f4f4",
        "island": "#f4f4f4",
        "constant": "#e5e5e5",
    }
    labels = {
        "HH": "High–high",
        "LL": "Low–low",
        "HL": "High–low",
        "LH": "Low–high",
        "not_significant": "Not significant",
        "not_evaluated": "Not evaluated",
        "missing": "Missing",
        "island": "No neighbours",
        "constant": "Constant values",
    }
    values = [
        float(feature.housing_change_pct)
        for feature in data.features
        if feature.housing_change_pct is not None
    ]
    normalizer = Normalize(vmin=min(values), vmax=max(values))
    projector = Transformer.from_crs("EPSG:4326", "EPSG:3763", always_xy=True)
    with plt.rc_context({"font.family": "DejaVu Sans", "font.size": 9}):
        figure, axes = plt.subplots(1, 2, figsize=(12, 10))
        try:
            cmap = plt.get_cmap("viridis")
            for index, feature in enumerate(data.features, start=1):
                polygon = transform(projector.transform, shape(dict(feature.geometry)))
                if not isinstance(polygon, Polygon | MultiPolygon):
                    raise ValueError("map geometry must be polygonal")
                value = feature.housing_change_pct
                if value is None:
                    raise ValueError("housing map requires complete change values")
                point = polygon.representative_point()
                for axis, color in zip(
                    axes,
                    (
                        cmap(normalizer(value)),
                        colors.get(observations[feature.freguesia_id].cluster_class, "#f4f4f4"),
                    ),
                    strict=True,
                ):
                    axis.add_patch(
                        patch_from_polygon(
                            polygon, facecolor=color, edgecolor="#777777", linewidth=0.6
                        )
                    )
                    axis.annotate(
                        str(index),
                        (point.x, point.y),
                        ha="center",
                        va="center",
                        fontsize=7,
                        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75, "pad": 0.6},
                    )
            for axis in axes:
                axis.autoscale_view()
                axis.set_aspect("equal")
                axis.axis("off")
            axes[0].set_title("Nominal housing change (%)")
            axes[1].set_title(f"Local Moran classifications · FDR q ≤ {local.alpha:g}")
            figure.colorbar(
                ScalarMappable(norm=normalizer, cmap=cmap),
                ax=axes[0],
                shrink=0.65,
                fraction=0.035,
                pad=0.02,
            )
            present = {row.cluster_class for row in local.observations}
            axes[1].legend(
                handles=[
                    Patch(facecolor=colors[key], label=label)
                    for key, label in labels.items()
                    if key in present
                ],
                loc="lower right",
                frameon=False,
                fontsize=8,
            )
            figure.suptitle(
                f"Lisbon housing patterns · {data.baseline_year} Q4 → {data.latest_year} Q4",
                fontsize=18,
                x=0.03,
                ha="left",
            )
            figure.subplots_adjust(left=0.025, right=0.98, top=0.90, bottom=0.28, wspace=0.10)
            for index, feature in enumerate(data.features):
                column, row = divmod(index, 6)
                figure.text(
                    0.035 + 0.245 * column,
                    0.21 - 0.023 * row,
                    f"{index + 1:2d}  {feature.name}",
                    fontsize=8.5,
                )
            figure.text(
                0.035,
                0.035,
                "Housing: INE 0012234, rolling 12-month sale medians. "
                "Boundaries: DGT CAOP2025, CC BY 4.0.\n"
                f"Queen neighbours · {local.permutations:,} permutations · seed {local.seed} "
                "· ETRS89 / Portugal TM06. Descriptive association, not RNAL effects.",
                fontsize=8,
                color="#444444",
            )
            figure.savefig(path, dpi=180, facecolor="white", metadata={"Software": "Matplotlib"})
        finally:
            plt.close(figure)
