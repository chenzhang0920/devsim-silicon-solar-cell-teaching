"""Validated physical parameters for the silicon solar-cell model."""

from dataclasses import dataclass, fields
import math
from numbers import Real


@dataclass
class SolarCellParams:
    """Physical and terminal parameters for the p+-on-n teaching cell."""

    # Geometry (cm)
    thickness: float = 250e-4
    emitter_depth: float = 0.5e-4

    # Abrupt doping profile (cm⁻³)
    emitter_doping: float = 1e19
    base_doping: float = 1e17

    # Constant transport parameters
    electron_mobility: float = 1417.0
    hole_mobility: float = 471.0
    electron_lifetime: float = 1e-5
    hole_lifetime: float = 1e-5

    # Auger coefficients (cm⁶/s)
    auger_n: float = 2.8e-31
    auger_p: float = 9.9e-32

    # Effective surface-recombination velocities (cm/s)
    front_srv: float = 1e4
    back_srv: float = 1e6

    # Illumination, optics, and temperature
    photon_flux: float = 1.0
    front_reflectance: float = 0.0
    temperature: float = 300.0

    # Terminal parasitics (Ω·cm²); Rsh=0 represents infinity
    series_resistance: float = 0.0
    shunt_resistance: float = 0.0


VALID_FIELDS = {field.name for field in fields(SolarCellParams)}

_POSITIVE = {
    "thickness", "emitter_depth", "emitter_doping", "base_doping",
    "electron_mobility", "hole_mobility", "electron_lifetime",
    "hole_lifetime", "temperature",
}
_NONNEGATIVE = {
    "front_srv", "back_srv", "photon_flux", "series_resistance",
    "shunt_resistance", "auger_n", "auger_p",
}


def check_params(params: dict) -> SolarCellParams:
    """Merge values into the dataclass and reject invalid physical inputs."""

    unknown = set(params) - VALID_FIELDS
    if unknown:
        raise ValueError(
            f"Unknown device parameters: {sorted(unknown)}.\n"
            f"Valid fields: {sorted(VALID_FIELDS)}.\n"
            "Check that config.py MODEL_PARAMS and CALIBRATION['params'] "
            "match the SolarCellParams field names."
        )

    parsed = SolarCellParams(**params)
    values = {field.name: getattr(parsed, field.name) for field in fields(parsed)}
    for name, value in values.items():
        if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(float(value)):
            raise ValueError(f"Parameter {name} must be finite; received {value!r}")
    for name in _POSITIVE:
        if values[name] <= 0:
            raise ValueError(f"Parameter {name} must be > 0; received {values[name]!r}")
    for name in _NONNEGATIVE:
        if values[name] < 0:
            raise ValueError(f"Parameter {name} must be non-negative; received {values[name]!r}")

    if parsed.emitter_depth >= parsed.thickness:
        raise ValueError(
            f"emitter_depth ({parsed.emitter_depth}) must be smaller than thickness "
            f"({parsed.thickness})"
        )
    if parsed.emitter_doping < 10.0 * parsed.base_doping:
        raise ValueError(
            "A p+-on-n teaching structure requires emitter_doping >= "
            f"10*base_doping; received {parsed.emitter_doping!r} and "
            f"{parsed.base_doping!r} cm^-3"
        )
    if not 0.0 <= parsed.front_reflectance <= 1.0:
        raise ValueError(
            f"front_reflectance must be in [0, 1]; received {parsed.front_reflectance!r}"
        )
    if not math.isclose(parsed.temperature, 300.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError(
            "This teaching model currently supports only temperature=300 K; "
            "intrinsic concentration and optical parameters are not yet temperature-consistent. "
            "Temperature sweeps are an extension exercise."
        )
    return parsed
