"""JSON persistence for beam design inputs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import TypeAlias

from beam_calculations import (
    SECTIONS,
    MaterialKey,
    PointLoad,
    SupportType,
    UniformLoad,
    analyze_beam,
)

DesignLoad: TypeAlias = PointLoad | UniformLoad
_FORMAT = "beam_designer_design"
_VERSION = 1


@dataclass(frozen=True)
class BeamDesign:
    support_type: SupportType
    span_ft: float
    material: MaterialKey
    section_name: str
    deflection_limit: int
    include_self_weight: bool
    loads: tuple[DesignLoad, ...]


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"'{field}' must be a number.")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"'{field}' must be finite.") from error
    if not isfinite(number):
        raise ValueError(f"'{field}' must be finite.")
    return number


def validate_design(design: BeamDesign) -> None:
    if not isinstance(design.include_self_weight, bool):
        raise ValueError("'include_self_weight' must be true or false.")
    if design.material not in SECTIONS:
        raise ValueError(f"Unsupported material: {design.material}")
    section = next(
        (item for item in SECTIONS[design.material] if item.name == design.section_name),
        None,
    )
    if section is None:
        raise ValueError(
            f"Section '{design.section_name}' is not available for {design.material}."
        )
    point_loads = tuple(load for load in design.loads if isinstance(load, PointLoad))
    uniform_loads = tuple(
        load for load in design.loads if isinstance(load, UniformLoad)
    )
    if len(point_loads) + len(uniform_loads) != len(design.loads):
        raise ValueError("Design contains an unsupported load type.")
    analyze_beam(
        span_ft=design.span_ft,
        support=design.support_type,
        point_loads=point_loads,
        uniform_loads=uniform_loads,
        material=design.material,
        section=section,
        deflection_limit=design.deflection_limit,
        include_self_weight=design.include_self_weight,
    )


def save_design(path: str | Path, design: BeamDesign) -> Path:
    """Validate and save a beam design as a versioned JSON file."""
    validate_design(design)
    output_path = Path(path)
    data = {
        "format": _FORMAT,
        "version": _VERSION,
        "support_type": design.support_type,
        "span_ft": design.span_ft,
        "material": design.material,
        "section": design.section_name,
        "deflection_limit": design.deflection_limit,
        "include_self_weight": design.include_self_weight,
        "loads": [_serialize_load(load) for load in design.loads],
    }
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, allow_nan=False)
        file.write("\n")
    return output_path


def _serialize_load(load: DesignLoad) -> dict[str, float | str]:
    if isinstance(load, PointLoad):
        return {
            "type": "point",
            "magnitude_kip": load.magnitude_kip,
            "position_ft": load.position_ft,
        }
    return {
        "type": "uniform",
        "magnitude_kip_ft": load.magnitude_kip_ft,
        "start_ft": load.start_ft,
        "end_ft": load.end_ft,
    }


def load_design(path: str | Path) -> BeamDesign:
    """Read, parse, and validate a saved beam design."""
    input_path = Path(path)
    try:
        with input_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Invalid beam design JSON at line {error.lineno}, column {error.colno}."
        ) from error
    if not isinstance(data, dict):
        raise ValueError("Beam design file must contain a JSON object.")
    version = data.get("version")
    if (
        data.get("format") != _FORMAT
        or isinstance(version, bool)
        or not isinstance(version, int)
        or version != _VERSION
    ):
        raise ValueError("File is not a supported Beam Designer design.")

    support = data.get("support_type")
    material = data.get("material")
    section_name = data.get("section")
    limit = data.get("deflection_limit")
    include_self_weight = data.get("include_self_weight")
    loads_data = data.get("loads")
    if not isinstance(support, str):
        raise ValueError("'support_type' must be a string.")
    if not isinstance(material, str) or material not in SECTIONS:
        raise ValueError("'material' must identify a supported material.")
    if not isinstance(section_name, str):
        raise ValueError("'section' must be a string.")
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise ValueError("'deflection_limit' must be 240 or 360.")
    if not isinstance(include_self_weight, bool):
        raise ValueError("'include_self_weight' must be true or false.")
    if not isinstance(loads_data, list):
        raise ValueError("'loads' must be a list.")

    loads: list[DesignLoad] = []
    for index, load_data in enumerate(loads_data):
        if not isinstance(load_data, dict):
            raise ValueError(f"Load {index + 1} must be a JSON object.")
        load_type = load_data.get("type")
        if load_type == "point":
            loads.append(
                PointLoad(
                    magnitude_kip=_number(
                        load_data.get("magnitude_kip"), f"loads[{index}].magnitude_kip"
                    ),
                    position_ft=_number(
                        load_data.get("position_ft"), f"loads[{index}].position_ft"
                    ),
                )
            )
        elif load_type == "uniform":
            loads.append(
                UniformLoad(
                    magnitude_kip_ft=_number(
                        load_data.get("magnitude_kip_ft"),
                        f"loads[{index}].magnitude_kip_ft",
                    ),
                    start_ft=_number(
                        load_data.get("start_ft"), f"loads[{index}].start_ft"
                    ),
                    end_ft=_number(
                        load_data.get("end_ft"), f"loads[{index}].end_ft"
                    ),
                )
            )
        else:
            raise ValueError(f"Load {index + 1} has unsupported type '{load_type}'.")

    design = BeamDesign(
        support_type=support,  # type: ignore[arg-type]
        span_ft=_number(data.get("span_ft"), "span_ft"),
        material=material,  # type: ignore[arg-type]
        section_name=section_name,
        deflection_limit=limit,
        include_self_weight=include_self_weight,
        loads=tuple(loads),
    )
    validate_design(design)
    return design
