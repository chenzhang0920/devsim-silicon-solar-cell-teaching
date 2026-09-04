"""Public API for the silicon solar-cell forward model."""

from __future__ import annotations

import numpy as np

from config import MODEL_PARAMS, SIMULATION
from .parameters import SolarCellParams, check_params

__all__ = [
    "run_simulation", "run_simulation_terminal", "terminal_iv", "simulate",
    "profiles", "simulate_eqe", "sweep_light", "sweep_bias",
    "SolarCellParams", "check_params",
]


# Keep the package import lightweight.  In particular, data-cleaning utilities
# import ``model.analysis`` and ``model.style`` but do not need DEVSIM or its
# native solver libraries.  These small wrappers defer that dependency until a
# device calculation is actually requested.
def simulate(p: SolarCellParams,
             voltages: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Run the intrinsic DEVSIM voltage sweep."""

    from .device import simulate as _simulate

    return _simulate(p, voltages)


def profiles(p: SolarCellParams, bias: float = 0.0) -> dict:
    """Return equilibrium and illuminated internal profiles."""

    from .device import profiles as _profiles

    return _profiles(p, bias=bias)


def simulate_eqe(p: SolarCellParams, wavelength_index: int) -> float:
    """Return the monochromatic short-circuit current for one wavelength bin."""

    from .device import simulate_eqe as _simulate_eqe

    return _simulate_eqe(p, wavelength_index)


def sweep_light(p: SolarCellParams, n_steps: int | None = None) -> list[dict]:
    """Return profile frames while illumination is ramped."""

    from .device import sweep_light as _sweep_light

    return _sweep_light(p, n_steps=n_steps)


def sweep_bias(p: SolarCellParams, v_max: float,
               n_steps: int | None = None) -> list[dict]:
    """Return profile frames over an illuminated forward-bias ramp."""

    from .device import sweep_bias as _sweep_bias

    return _sweep_bias(p, v_max=v_max, n_steps=n_steps)


def _configured_params(overrides: dict | None) -> SolarCellParams:
    """Apply optional overrides to the shared configuration baseline."""

    merged = dict(MODEL_PARAMS)
    if overrides is not None:
        if not isinstance(overrides, dict):
            raise TypeError(f"params must be a dict or None; received {type(overrides).__name__}")
        merged.update(overrides)
    return check_params(merged)


def _intrinsic_dict(params: SolarCellParams) -> dict:
    """Return device parameters with terminal parasitics explicitly disabled."""

    intrinsic = {name: getattr(params, name) for name in params.__dataclass_fields__}
    intrinsic["series_resistance"] = 0.0
    intrinsic["shunt_resistance"] = 0.0
    return intrinsic


def run_simulation(
    params: dict | None = None,
    voltages: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Run the intrinsic DEVSIM model and return voltage and current density."""

    parsed = _configured_params(params)
    if voltages is None:
        config = SIMULATION.get("voltages", {})
        start = config.get("start", 0.0)
        stop = config.get("stop", 0.68)
        step = config.get("step", 0.02)
        if not all(np.isfinite([start, stop, step])) or step <= 0 or stop < start:
            raise ValueError(
                "SIMULATION.voltages requires finite start/stop values, "
                "step > 0, and stop >= start"
            )
        # linspace avoids artifacts such as 0.30000000000000004 from arange.
        intervals_float = (stop - start) / step
        intervals = int(round(intervals_float))
        if not np.isclose(intervals_float, intervals, rtol=0.0, atol=1e-9):
            raise ValueError(
                "SIMULATION.voltages requires (stop - start) to be an integer "
                "multiple of step; otherwise the requested step would be changed"
            )
        count = intervals + 1
        voltages = np.linspace(start, stop, count)

    voltages = np.asarray(voltages, dtype=float)
    if voltages.ndim != 1 or voltages.size == 0:
        raise ValueError("voltages must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(voltages)):
        raise ValueError("voltages must contain only finite values")
    if np.any(np.diff(voltages) < 0):
        raise ValueError(
            "DEVSIM voltage sweeps must be sorted in ascending order for stable continuation"
        )
    return simulate(parsed, voltages)


def run_simulation_terminal(
    params: dict | None,
    voltages: np.ndarray,
    j_meas: np.ndarray,
) -> np.ndarray:
    """Evaluate the terminal implicit equation at measured J-V points.

    The junction voltage is ``V_terminal + J_meas*Rs``. The intrinsic device is
    evaluated there, then the junction shunt current is subtracted. This inexpensive
    form is used inside calibration residuals.
    """

    parsed = _configured_params(params)
    voltages = np.asarray(voltages, dtype=float)
    j_meas = np.asarray(j_meas, dtype=float)
    if (
        voltages.ndim != 1
        or j_meas.ndim != 1
        or voltages.size != j_meas.size
        or voltages.size == 0
    ):
        raise ValueError(
            "voltages and j_meas must be non-empty one-dimensional arrays of equal length"
        )
    if not np.all(np.isfinite(voltages)) or not np.all(np.isfinite(j_meas)):
        raise ValueError("voltages and j_meas must contain only finite values")

    v_junction = voltages + j_meas * float(parsed.series_resistance)
    # Sorting preserves stable DEVSIM continuation even if the Rs transform reorders points.
    order = np.argsort(v_junction, kind="stable")
    inverse = np.empty_like(order)
    inverse[order] = np.arange(order.size)
    _, j_sorted = run_simulation(params=_intrinsic_dict(parsed), voltages=v_junction[order])
    j_device = j_sorted[inverse]
    rsh = float(parsed.shunt_resistance)
    j_shunt = 0.0 if rsh == 0.0 else v_junction / rsh
    return j_device - j_shunt


def terminal_iv(
    params: dict | None = None,
    v_junc: np.ndarray | None = None,
    n: int | None = None,
    v_max: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Return a self-consistent terminal J-V curve including Rs and Rsh.

    When neither ``v_junc`` nor ``n`` is supplied, the junction-voltage grid
    comes from ``SIMULATION['voltages']``. Passing ``n`` requests a dense grid
    from 0 to at least 0.8 V, which is useful for smooth reporting figures.
    """

    parsed = _configured_params(params)
    if v_junc is not None and n is not None:
        raise ValueError("v_junc and n are alternative grid specifications; provide only one")
    if v_max is not None and (not np.isfinite(v_max) or v_max < -0.05):
        raise ValueError(f"v_max must be finite and >= -0.05 V; received {v_max!r}")
    if v_junc is None:
        if n is None:
            config = SIMULATION.get("voltages", {})
            start = float(config.get("start", 0.0))
            stop = float(config.get("stop", 0.68))
            step = float(config.get("step", 0.02))
            intervals_float = (stop - start) / step if step > 0 else np.nan
            intervals = int(round(intervals_float)) if np.isfinite(intervals_float) else -1
            if not all(np.isfinite([start, stop, step])) or step <= 0 or stop < start \
                    or not np.isclose(intervals_float, intervals, rtol=0.0, atol=1e-9):
                raise ValueError(
                    "SIMULATION.voltages requires finite start/stop values, step > 0, "
                    "stop >= start, and an integer number of steps"
                )
            v_junc = np.linspace(start, stop, intervals + 1)
        else:
            if not isinstance(n, int) or isinstance(n, bool) or n < 2:
                raise ValueError("n must be an integer >= 2")
            upper = max(0.8, float(v_max)) if v_max is not None else 0.8
            v_junc = np.linspace(0.0, upper, n)
    v_junc = np.asarray(v_junc, dtype=float)

    _, j_device = run_simulation(params=_intrinsic_dict(parsed), voltages=v_junc)
    rsh = float(parsed.shunt_resistance)
    current = j_device if rsh == 0.0 else j_device - v_junc / rsh
    v_terminal = v_junc - current * float(parsed.series_resistance)
    order = np.argsort(v_terminal, kind="stable")
    v_terminal, current = v_terminal[order], current[order]
    if v_max is not None:
        keep = (v_terminal >= -0.05) & (v_terminal <= v_max)
        v_terminal, current = v_terminal[keep], current[keep]
    return v_terminal, current
