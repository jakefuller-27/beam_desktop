"""CSV export of sampled beam results."""

from __future__ import annotations

import csv
from pathlib import Path

from beam_calculations import AnalysisResult

CSV_COLUMNS = (
    "x (ft)",
    "V (kips)",
    "M (kip-ft)",
    "Deflection (in)",
)


def export_results_csv(path: str | Path, result: AnalysisResult) -> Path:
    """Write sampled x, V, M, and deflection values to an Excel-friendly CSV."""
    output_path = Path(path)
    point_jumps = {
        position: (shear_left, shear_right)
        for position, shear_left, shear_right in result.point_load_shear
    }
    span_ft = float(result.x_ft[-1])

    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(CSV_COLUMNS)
        for index, position_value in enumerate(result.x_ft):
            position = float(position_value)
            shear = float(result.shear_kip[index])
            if position in point_jumps:
                shear_values = point_jumps[position]
            elif (
                result.right_reaction_kip is not None
                and abs(position - span_ft) < 1e-10
            ):
                shear_values = (
                    shear - result.right_reaction_kip,
                    shear,
                )
            else:
                shear_values = (shear,)
            moment = float(result.moment_kip_ft[index])
            deflection = float(result.deflection_in[index])
            for shear_value in shear_values:
                writer.writerow(
                    (
                        f"{position:.12g}",
                        f"{shear_value:.12g}",
                        f"{moment:.12g}",
                        f"{deflection:.12g}",
                    )
                )
    return output_path
