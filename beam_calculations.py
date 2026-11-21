"""Beam statics, section checks, and deflection calculations."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Literal

import numpy as np

SupportType = Literal["Simply supported", "Cantilever"]
MaterialKey = Literal["Steel W-shape", "Douglas Fir-Larch lumber"]


@dataclass(frozen=True)
class Section:
    name: str
    ix_in4: float
    sx_in3: float
    weight_lb_ft: float


@dataclass(frozen=True)
class PointLoad:
    magnitude_kip: float
    position_ft: float


@dataclass(frozen=True)
class UniformLoad:
    magnitude_kip_ft: float
    start_ft: float
    end_ft: float


@dataclass(frozen=True)
class SectionResult:
    bending_stress_ksi: float
    allowable_bending_ksi: float
    bending_passes: bool
    max_deflection_in: float
    allowable_deflection_in: float
    deflection_passes: bool

    @property
    def passes(self) -> bool:
        return self.bending_passes and self.deflection_passes


@dataclass(frozen=True)
class AnalysisResult:
    x_ft: np.ndarray
    shear_kip: np.ndarray
    moment_kip_ft: np.ndarray
    deflection_in: np.ndarray
    left_reaction_kip: float
    right_reaction_kip: float | None
    fixed_end_moment_kip_ft: float | None
    max_shear_kip: float
    max_shear_position_ft: float
    max_moment_kip_ft: float
    max_moment_position_ft: float
    max_deflection_in: float
    max_deflection_position_ft: float
    point_load_shear: tuple[tuple[float, float, float], ...]
    effective_uniform_loads: tuple[UniformLoad, ...]
    checks: SectionResult
    selected_section: Section


SECTIONS: dict[MaterialKey, tuple[Section, ...]] = {
    "Steel W-shape": (
        Section("W8x10", 30.8, 7.81, 10.0),
        Section("W10x12", 53.8, 10.9, 12.0),
        Section("W12x26", 204.0, 33.4, 26.0),
        Section("W14x22", 199.0, 29.0, 22.0),
        Section("W16x26", 301.0, 38.4, 26.0),
        Section("W18x35", 510.0, 57.6, 35.0),
        Section("W21x44", 843.0, 81.6, 44.0),
        Section("W24x55", 1350.0, 114.0, 55.0),
    ),
    "Douglas Fir-Larch lumber": (
        Section("2x8", 47.63, 13.14, 2.64),
        Section("2x10", 98.93, 21.39, 3.37),
        Section("2x12", 177.98, 31.64, 4.10),
    ),
}

MATERIAL_PROPERTIES: dict[MaterialKey, tuple[float, float]] = {
    "Steel W-shape": (29_000.0, 30.0),
    "Douglas Fir-Larch lumber": (1_600.0, 0.900),
}


def _validate_inputs(
    span_ft: float,
    support: SupportType,
    point_loads: tuple[PointLoad, ...],
    uniform_loads: tuple[UniformLoad, ...],
    deflection_limit: int,
) -> None:
    if not np.isfinite(span_ft) or not 4 <= span_ft <= 40:
        raise ValueError("Span must be between 4 and 40 ft.")
    if support not in ("Simply supported", "Cantilever"):
        raise ValueError(f"Unsupported support type: {support}")
    if deflection_limit not in (240, 360):
        raise ValueError("Deflection limit must be 240 or 360.")
    if len(point_loads) + len(uniform_loads) > 10:
        raise ValueError("A beam can have at most 10 editable loads.")
    for load in point_loads:
        if not np.isfinite(load.magnitude_kip) or not np.isfinite(load.position_ft):
            raise ValueError("Point load values must be finite.")
        if not -100 <= load.magnitude_kip <= 100:
            raise ValueError("Point load magnitude must be between -100 and 100 kips.")
        if not 0 <= load.position_ft <= span_ft:
            raise ValueError("Point load position must be within the beam span.")
    for load in uniform_loads:
        if not all(
            np.isfinite(value)
            for value in (load.magnitude_kip_ft, load.start_ft, load.end_ft)
        ):
            raise ValueError("Uniform load values must be finite.")
        if not -10 <= load.magnitude_kip_ft <= 10:
            raise ValueError("Uniform load magnitude must be between -10 and 10 kips/ft.")
        if not 0 <= load.start_ft <= load.end_ft <= span_ft:
            raise ValueError("Uniform load endpoints must be ordered within the span.")


def analyze_beam(
    span_ft: float,
    support: SupportType,
    point_loads: tuple[PointLoad, ...] | list[PointLoad],
    uniform_loads: tuple[UniformLoad, ...] | list[UniformLoad],
    material: MaterialKey,
    section: Section,
    deflection_limit: int = 360,
    include_self_weight: bool = False,
) -> AnalysisResult:
    """Analyze the beam and return sampled diagrams and unrounded checks."""
    points = tuple(point_loads)
    uniforms = tuple(uniform_loads)
    _validate_inputs(span_ft, support, points, uniforms, deflection_limit)
    if material not in MATERIAL_PROPERTIES or section not in SECTIONS[material]:
        raise ValueError("The selected section does not belong to the selected material.")

    effective_uniforms = list(uniforms)
    if include_self_weight:
        effective_uniforms.append(
            UniformLoad(section.weight_lb_ft / 1000.0, 0.0, span_ft)
        )

    total_load = sum(load.magnitude_kip for load in points)
    first_moment = sum(
        load.magnitude_kip * load.position_ft for load in points
    )
    for load in effective_uniforms:
        length = load.end_ft - load.start_ft
        total_load += load.magnitude_kip_ft * length
        first_moment += (
            load.magnitude_kip_ft * length * (load.start_ft + load.end_ft) / 2.0
        )

    if support == "Cantilever":
        left_reaction = total_load
        right_reaction = None
        fixed_end_moment = first_moment
    else:
        right_reaction = first_moment / span_ft
        left_reaction = total_load - right_reaction
        fixed_end_moment = None

    def uniform_total_to(x_ft: float) -> float:
        total = 0.0
        for load in effective_uniforms:
            length = min(max(x_ft - load.start_ft, 0.0), load.end_ft - load.start_ft)
            total += load.magnitude_kip_ft * length
        return total

    def shear_at(x_ft: float, side: Literal["left", "right"] = "right") -> float:
        if x_ft <= 0.0 and side == "left":
            return 0.0
        shear = left_reaction - uniform_total_to(x_ft)
        if side == "left":
            shear -= sum(
                load.magnitude_kip for load in points if load.position_ft < x_ft
            )
        else:
            shear -= sum(
                load.magnitude_kip
                for load in points
                if load.position_ft <= x_ft + 1e-12
            )
        if (
            support == "Simply supported"
            and x_ft >= span_ft
            and side == "right"
        ):
            shear += right_reaction or 0.0
        return shear

    def moment_at(x_ft: float) -> float:
        moment = left_reaction * x_ft
        if fixed_end_moment is not None:
            moment -= fixed_end_moment
        for load in points:
            if load.position_ft <= x_ft:
                moment -= load.magnitude_kip * (x_ft - load.position_ft)
        for load in effective_uniforms:
            loaded_end = min(x_ft, load.end_ft)
            if loaded_end > load.start_ft:
                length = loaded_end - load.start_ft
                moment -= load.magnitude_kip_ft * length * (
                    x_ft - (load.start_ft + loaded_end) / 2.0
                )
        return moment

    base_count = max(400, ceil(span_ft * 200.0))
    sample_points = list(np.linspace(0.0, span_ft, base_count + 1))
    for load in points:
        sample_points.append(load.position_ft)
    for load in effective_uniforms:
        sample_points.extend((load.start_ft, load.end_ft))
    x_ft = np.unique(np.asarray(sample_points, dtype=float))

    shear = np.asarray([shear_at(float(x)) for x in x_ft])
    moment = np.asarray([moment_at(float(x)) for x in x_ft])

    shear_candidates = [(abs(float(value)), float(x), float(value)) for x, value in zip(x_ft, shear)]
    for load in points:
        left_value = shear_at(load.position_ft, "left")
        right_value = shear_at(load.position_ft, "right")
        shear_candidates.extend(
            (
                (abs(left_value), load.position_ft, left_value),
                (abs(right_value), load.position_ft, right_value),
            )
        )
    max_shear_abs, max_shear_x, max_shear = max(shear_candidates)

    breakpoints = {0.0, span_ft}
    breakpoints.update(load.position_ft for load in points)
    for load in effective_uniforms:
        breakpoints.update((load.start_ft, load.end_ft))
    moment_candidates = set(float(x) for x in x_ft)
    sorted_breakpoints = sorted(breakpoints)
    for start, end in zip(sorted_breakpoints, sorted_breakpoints[1:]):
        if end - start <= 1e-12:
            continue
        middle = (start + end) / 2.0
        intensity = sum(
            load.magnitude_kip_ft
            for load in effective_uniforms
            if load.start_ft < middle < load.end_ft
        )
        if abs(intensity) <= 1e-15:
            continue
        zero = middle + shear_at(middle) / intensity
        if start + 1e-12 < zero < end - 1e-12:
            moment_candidates.add(zero)
    max_moment_x = max(moment_candidates, key=lambda x: abs(moment_at(x)))
    max_moment = moment_at(max_moment_x)

    x_in = x_ft * 12.0
    e_ksi, allowable_bending = MATERIAL_PROPERTIES[material]
    curvature_per_in = -np.asarray([moment_at(float(x)) for x in x_ft]) * 12.0 / (
        e_ksi * section.ix_in4
    )
    slope = np.concatenate(
        (
            np.array([0.0]),
            np.cumsum(
                (curvature_per_in[:-1] + curvature_per_in[1:])
                * 0.5
                * np.diff(x_in)
            ),
        )
    )
    raw_deflection = np.concatenate(
        (
            np.array([0.0]),
            np.cumsum((slope[:-1] + slope[1:]) * 0.5 * np.diff(x_in)),
        )
    )
    if support == "Simply supported":
        raw_deflection -= raw_deflection[-1] * x_in / x_in[-1]
    max_deflection_index = int(np.argmax(np.abs(raw_deflection)))
    max_deflection = float(raw_deflection[max_deflection_index])
    allowable_deflection = span_ft * 12.0 / deflection_limit
    stress = abs(max_moment) * 12.0 / section.sx_in3
    checks = SectionResult(
        bending_stress_ksi=stress,
        allowable_bending_ksi=allowable_bending,
        bending_passes=stress <= allowable_bending,
        max_deflection_in=max_deflection,
        allowable_deflection_in=allowable_deflection,
        deflection_passes=abs(max_deflection) <= allowable_deflection,
    )

    point_shear = tuple(
        (
            load.position_ft,
            shear_at(load.position_ft, "left"),
            shear_at(load.position_ft, "right"),
        )
        for load in points
    )
    return AnalysisResult(
        x_ft=x_ft,
        shear_kip=shear,
        moment_kip_ft=moment,
        deflection_in=raw_deflection,
        left_reaction_kip=left_reaction,
        right_reaction_kip=right_reaction,
        fixed_end_moment_kip_ft=fixed_end_moment,
        max_shear_kip=max_shear,
        max_shear_position_ft=max_shear_x,
        max_moment_kip_ft=max_moment,
        max_moment_position_ft=max_moment_x,
        max_deflection_in=max_deflection,
        max_deflection_position_ft=float(x_ft[max_deflection_index]),
        point_load_shear=point_shear,
        effective_uniform_loads=tuple(effective_uniforms),
        checks=checks,
        selected_section=section,
    )


def lightest_passing_section(
    span_ft: float,
    support: SupportType,
    point_loads: tuple[PointLoad, ...] | list[PointLoad],
    uniform_loads: tuple[UniformLoad, ...] | list[UniformLoad],
    material: MaterialKey,
    deflection_limit: int,
    include_self_weight: bool,
) -> Section | None:
    """Return the lightest passing section, testing each section's own weight."""
    passing = []
    for section in SECTIONS[material]:
        result = analyze_beam(
            span_ft=span_ft,
            support=support,
            point_loads=point_loads,
            uniform_loads=uniform_loads,
            material=material,
            section=section,
            deflection_limit=deflection_limit,
            include_self_weight=include_self_weight,
        )
        if result.checks.passes:
            passing.append(section)
    if not passing:
        return None
    if material == "Steel W-shape":
        return min(passing, key=lambda item: (item.weight_lb_ft, -item.ix_in4))
    return passing[0]
