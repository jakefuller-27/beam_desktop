"""One-page PDF calculation sheet generation."""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
from matplotlib.patches import Polygon

from beam_calculations import (
    AnalysisResult,
    MaterialKey,
    PointLoad,
    Section,
    SupportType,
    UniformLoad,
)


def _draw_beam(
    axis,
    span_ft: float,
    support: SupportType,
    point_loads: tuple[PointLoad, ...],
    uniform_loads: tuple[UniformLoad, ...],
    include_self_weight: bool,
    result: AnalysisResult,
) -> None:
    axis.plot((0, span_ft), (0, 0), color="#263747", linewidth=4)
    if support == "Simply supported":
        for x in (0, span_ft):
            axis.add_patch(
                Polygon(
                    (
                        (x, -0.08),
                        (x - span_ft * 0.025, -0.48),
                        (x + span_ft * 0.025, -0.48),
                    ),
                    closed=True,
                    facecolor="#d9e3ec",
                    edgecolor="#263747",
                )
            )
    else:
        axis.plot((0, 0), (-0.55, 0.75), color="#263747", linewidth=3)
        axis.vlines(0, -0.55, 0.75, color="#263747", linewidth=1)

    for load_index, load in enumerate(uniform_loads):
        y = 0.72 + 0.32 * load_index
        axis.plot((load.start_ft, load.end_ft), (y, y), color="#4b6f91", linewidth=1)
        for x in _arrow_positions(load.start_ft, load.end_ft):
            _arrow(axis, x, y, load.magnitude_kip_ft, "#4b6f91")
        axis.text(
            (load.start_ft + load.end_ft) / 2,
            y + 0.12,
            f"{load.magnitude_kip_ft:g} kip/ft",
            ha="center",
            fontsize=7,
            color="#385773",
        )
    if include_self_weight:
        weight_load = result.effective_uniform_loads[-1]
        y = 0.72 + 0.32 * len(uniform_loads)
        axis.plot((0, span_ft), (y, y), color="#d78a28", linestyle="--")
        for x in _arrow_positions(0, span_ft):
            _arrow(axis, x, y, weight_load.magnitude_kip_ft, "#d78a28")
        axis.text(
            span_ft / 2, y + 0.12,
            f"Self-weight {weight_load.magnitude_kip_ft:.3f} kip/ft",
            ha="center", fontsize=7, color="#a36719",
        )

    for load in point_loads:
        _arrow(axis, load.position_ft, 1.15, load.magnitude_kip, "#305f86")
        axis.text(
            load.position_ft,
            1.28 if load.magnitude_kip >= 0 else 0.68,
            f"{load.magnitude_kip:g} k",
            ha="center",
            fontsize=7,
            color="#305f86",
        )
    axis.annotate(
        f"R_A = {result.left_reaction_kip:.2f} k",
        xy=(0, -0.45),
        xytext=(span_ft * 0.06, -0.78),
        fontsize=7,
        arrowprops={"arrowstyle": "->", "color": "#a34d4d"},
        color="#8f3d3d",
    )
    if result.right_reaction_kip is not None:
        axis.annotate(
            f"R_B = {result.right_reaction_kip:.2f} k",
            xy=(span_ft, -0.45),
            xytext=(span_ft * 0.78, -0.78),
            fontsize=7,
            arrowprops={"arrowstyle": "->", "color": "#a34d4d"},
            color="#8f3d3d",
        )
    else:
        axis.text(
            span_ft * 0.04, -0.75,
            f"M_A = {result.fixed_end_moment_kip_ft:.2f} kip-ft",
            fontsize=7, color="#8f3d3d",
        )
    axis.set_xlim(-span_ft * 0.08, span_ft * 1.08)
    axis.set_ylim(-0.9, 1.65 + 0.32 * (len(uniform_loads) + int(include_self_weight)))
    axis.set_yticks([])
    axis.set_xticks((0, span_ft))
    axis.set_xticklabels(("0 ft", f"{span_ft:g} ft"), fontsize=7)
    axis.set_title("Beam and applied loads", fontsize=8, loc="left")
    for spine in ("left", "right", "top"):
        axis.spines[spine].set_visible(False)


def _arrow_positions(start: float, end: float) -> tuple[float, ...]:
    if end <= start:
        return (start,)
    return tuple(start + (end - start) * index / 7 for index in range(8))


def _arrow(axis, x: float, top: float, magnitude: float, color: str) -> None:
    if magnitude >= 0:
        axis.annotate(
            "", xy=(x, 0.08), xytext=(x, top),
            arrowprops={"arrowstyle": "-|>", "color": color, "lw": 0.8},
        )
    else:
        axis.annotate(
            "", xy=(x, top), xytext=(x, 0.08),
            arrowprops={"arrowstyle": "-|>", "color": color, "lw": 0.8},
        )


def export_calculation_sheet(
    path: str | Path,
    *,
    span_ft: float,
    support: SupportType,
    material: MaterialKey,
    section: Section,
    deflection_limit: int,
    include_self_weight: bool,
    point_loads: tuple[PointLoad, ...],
    uniform_loads: tuple[UniformLoad, ...],
    result: AnalysisResult,
    recommendation: Section | None,
) -> Path:
    """Write a single letter-size PDF page and return the resulting path."""
    output_path = Path(path)
    figure = Figure(figsize=(8.5, 11), dpi=150, facecolor="white")
    figure.text(
        0.5, 0.966, "Beam Calculation Sheet", ha="center",
        fontsize=16, fontweight="bold", color="#182532",
    )
    figure.text(
        0.5, 0.938, f"Date: {date.today().isoformat()}",
        ha="center", fontsize=8, color="#536473",
    )
    e_label = "steel" if material == "Steel W-shape" else "lumber"
    figure.text(
        0.08, 0.905,
        f"Support: {support}     Span: {span_ft:g} ft     "
        f"Material: {material}     Section: {section.name}",
        fontsize=8,
    )
    figure.text(
        0.08, 0.884,
        f"Deflection limit: L/{deflection_limit}     "
        f"Self-weight: {'included' if include_self_weight else 'ignored'}",
        fontsize=8,
    )

    table_axis = figure.add_axes((0.08, 0.79, 0.84, 0.075))
    table_axis.axis("off")
    rows = []
    rows.extend(
        ("Point", f"{load.magnitude_kip:g} k", f"{load.position_ft:g} ft")
        for load in point_loads
    )
    rows.extend(
        (
            "Uniform",
            f"{load.magnitude_kip_ft:g} k/ft",
            f"{load.start_ft:g} to {load.end_ft:g} ft",
        )
        for load in uniform_loads
    )
    if not rows:
        rows.append(("No editable loads", "", ""))
    table = table_axis.table(
        cellText=rows,
        colLabels=("Load", "Magnitude", "Position / range"),
        cellLoc="left",
        colLoc="left",
        loc="center",
        colWidths=(0.24, 0.22, 0.40),
    )
    table.auto_set_font_size(False)
    table.set_fontsize(7)
    table.scale(1, 1.12)
    figure.text(0.08, 0.87, "Editable loads", fontsize=8, fontweight="bold")

    beam_axis = figure.add_axes((0.09, 0.695, 0.82, 0.075))
    _draw_beam(
        beam_axis, span_ft, support, point_loads, uniform_loads,
        include_self_weight, result,
    )

    chart_specs = (
        ("Shear (kips)", result.shear_kip, "#4c84ad"),
        ("Moment (kip-ft)", result.moment_kip_ft, "#6d9d83"),
        ("Deflection (in)", result.deflection_in, "#bd8a4c"),
    )
    chart_bottoms = (0.575, 0.465, 0.355)
    for (title, values, color), bottom in zip(chart_specs, chart_bottoms):
        axis = figure.add_axes((0.12, bottom, 0.78, 0.085))
        axis.plot(result.x_ft, values, color=color, linewidth=1.1)
        axis.fill_between(result.x_ft, 0, values, color=color, alpha=0.16)
        axis.axhline(0, color="#7b858d", linewidth=0.55)
        axis.set_xlim(0, span_ft)
        axis.set_ylabel(title, fontsize=7)
        axis.tick_params(labelsize=6, length=2)
        axis.grid(axis="x", color="#e2e7eb", linewidth=0.5)
        if title == "Moment (kip-ft)":
            axis.text(
                result.max_moment_position_ft, result.max_moment_kip_ft,
                f" {result.max_moment_kip_ft:.2f}", fontsize=6,
                va="bottom" if result.max_moment_kip_ft >= 0 else "top",
            )
        elif title == "Deflection (in)":
            axis.text(
                result.max_deflection_position_ft, result.max_deflection_in,
                f" {result.max_deflection_in:.3f}", fontsize=6,
                va="bottom" if result.max_deflection_in >= 0 else "top",
            )

    checks = result.checks
    bending_status = "PASS" if checks.bending_passes else "FAIL"
    deflection_status = "PASS" if checks.deflection_passes else "FAIL"
    if not point_loads and not uniform_loads:
        bending_status = deflection_status = "Add a load"
    figure.text(0.08, 0.305, "Design checks", fontsize=9, fontweight="bold")
    figure.text(
        0.08, 0.278,
        f"Bending: {checks.bending_stress_ksi:.2f} ksi / "
        f"{checks.allowable_bending_ksi:g} ksi  —  {bending_status}",
        fontsize=8,
    )
    figure.text(
        0.08, 0.254,
        f"Deflection: {abs(checks.max_deflection_in):.3f} in / "
        f"{checks.allowable_deflection_in:.3f} in  —  {deflection_status}",
        fontsize=8,
    )
    figure.text(
        0.08, 0.221,
        f"Max shear: {result.max_shear_kip:.2f} k at "
        f"{result.max_shear_position_ft:.2f} ft     "
        f"Max moment: {result.max_moment_kip_ft:.2f} kip-ft at "
        f"{result.max_moment_position_ft:.2f} ft     "
        f"Max deflection: {result.max_deflection_in:.3f} in at "
        f"{result.max_deflection_position_ft:.2f} ft",
        fontsize=7,
    )
    weight_kip_ft = section.weight_lb_ft / 1000.0
    figure.text(
        0.08, 0.187,
        f"Section weight: {section.weight_lb_ft:.2f} lb/ft "
        f"({weight_kip_ft:.5f} kip/ft). "
        f"Self-weight is {'included' if include_self_weight else 'ignored'}.",
        fontsize=7,
    )
    figure.text(
        0.08, 0.163,
        f"Allowable bending stress: Fb = {checks.allowable_bending_ksi:g} ksi ({e_label}).",
        fontsize=7,
    )
    if recommendation is not None and (point_loads or uniform_loads):
        if recommendation.name == section.name:
            recommendation_text = f"{recommendation.name} is already the lightest passing section."
        else:
            recommendation_text = f"Suggested lightest passing section: {recommendation.name}."
    elif point_loads or uniform_loads:
        recommendation_text = "No section in this list passes."
    else:
        recommendation_text = ""
    if recommendation_text:
        figure.text(0.08, 0.123, recommendation_text, fontsize=8, fontweight="bold")
    figure.text(
        0.5, 0.06,
        "Units: kips, ft, kip-ft; deflection in inches. "
        "Analysis values are evaluated before display rounding.",
        ha="center", fontsize=6, color="#5e6871",
    )

    with PdfPages(output_path) as pdf:
        pdf.savefig(figure, facecolor="white")
    return output_path


def open_pdf(path: str | Path) -> None:
    """Open the generated PDF using the operating system's default application."""
    path_text = str(Path(path).resolve())
    if sys.platform == "darwin":
        subprocess.run(["open", path_text], check=True)
    elif sys.platform == "win32":
        subprocess.run(["cmd", "/c", "start", "", path_text], check=True)
    else:
        subprocess.run(["xdg-open", path_text], check=True)
