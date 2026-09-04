"""Fit the forward model to measured current-density–voltage data with lmfit."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import lmfit

from model import run_simulation_terminal, terminal_iv
from model.analysis import voc_zero_crossing
from model.parameters import VALID_FIELDS
from config import CALIBRATION, MODEL_PARAMS


_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _resolve(path: str) -> Path:
    """Resolve relative data paths from the project root."""
    p = Path(path)
    return p if p.is_absolute() else _PROJECT_ROOT / p


_FIT_SPEC = CALIBRATION.get("params", {})


RESIDUAL_MODE = CALIBRATION.get("residual_mode", "absolute")
_REL_FLOOR_FRAC = 0.05


def make_params() -> lmfit.Parameters:
    """Create bounded lmfit parameters from the calibration configuration."""
    params = lmfit.Parameters()
    for name, spec in _FIT_SPEC.items():
        if name not in VALID_FIELDS:
            raise ValueError(
                f"CALIBRATION['params'] contains unknown parameter '{name}'; "
                f"valid fields: {sorted(VALID_FIELDS)}")
        options = dict(spec)


        if not options.get("vary", True) and name in MODEL_PARAMS:
            options["value"] = MODEL_PARAMS[name]
        if name == "shunt_resistance" and options.get("vary", False) \
                and float(options.get("min", 0.0)) <= 0:
            raise ValueError(
                "When fitting shunt_resistance, min must be > 0 "
                "(recommended: >= 10 Ω·cm²). This project uses 0 to represent "
                "ideal infinite Rsh, so 0 cannot be a continuous fit boundary.")
        params.add(name, **options)
    return params


def residual_denominator(j_meas, mode: str = RESIDUAL_MODE) -> np.ndarray:
    """Return per-point normalization for absolute or relative residuals."""
    j_meas = np.asarray(j_meas, dtype=float)
    if j_meas.ndim != 1 or j_meas.size == 0 or not np.all(np.isfinite(j_meas)):
        raise ValueError("j_meas must be a non-empty one-dimensional array of finite values")
    jsc = max(float(np.max(np.abs(j_meas))), 1e-12)
    if mode == "relative":
        return np.abs(j_meas) + _REL_FLOOR_FRAC * jsc
    if mode != "absolute":
        raise ValueError(f"Unknown residual mode {mode!r}; choose 'absolute' or 'relative'")
    return np.full_like(j_meas, jsc)


def residual_vector(j_sim, j_meas, mode: str = RESIDUAL_MODE) -> np.ndarray:
    """Calculate the normalized residual vector shared by fitting and tracing."""
    j_sim = np.asarray(j_sim, dtype=float)
    j_meas = np.asarray(j_meas, dtype=float)
    if j_sim.ndim != 1 or j_meas.ndim != 1 or j_sim.shape != j_meas.shape \
            or j_sim.size == 0:
        raise ValueError("j_sim and j_meas must be non-empty one-dimensional arrays of equal length")
    if not np.all(np.isfinite(j_sim)) or not np.all(np.isfinite(j_meas)):
        raise ValueError("j_sim and j_meas must contain only finite values")
    return (j_sim - j_meas) / residual_denominator(j_meas, mode)


def residual(pars: lmfit.Parameters,
             v_meas: np.ndarray, j_meas: np.ndarray,
             mode: str | None = None) -> np.ndarray:
    """Evaluate the forward model residual for lmfit."""
    base = dict(MODEL_PARAMS)
    base.update(pars.valuesdict())


    j_sim = run_simulation_terminal(params=base, voltages=v_meas, j_meas=j_meas)
    return residual_vector(j_sim, j_meas, mode or RESIDUAL_MODE)


def fit(v_meas: np.ndarray, j_meas: np.ndarray,
        params: lmfit.Parameters | None = None,
        method: str = "least_squares",
        mode: str | None = None,
        **fit_kws) -> lmfit.MinimizerResult:
    """Fit model parameters to a validated measured J-V curve."""
    v_meas, j_meas = validate_iv_data(v_meas, j_meas)
    if params is None:
        params = make_params()
    kws = dict(fit_kws)


    if method == "least_squares" and CALIBRATION.get("diff_step") is not None:
        kws.setdefault("diff_step", CALIBRATION["diff_step"])
    return lmfit.minimize(residual, params, args=(v_meas, j_meas, mode or RESIDUAL_MODE),
                          method=method, **kws)


def load_iv_csv(path: str,
                v_col: str = "V", j_col: str = "J",
                kind: str = "light") -> tuple[np.ndarray, np.ndarray]:
    """Load and validate voltage/current-density columns from a CSV file."""
    resolved = _resolve(path)
    df = pd.read_csv(resolved)
    missing = [c for c in (v_col, j_col) if c not in df.columns]
    if missing:
        raise ValueError(f"{resolved} is missing columns {missing}; found {list(df.columns)}")
    try:
        v = df[v_col].to_numpy(dtype=float)
        j = df[j_col].to_numpy(dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"The V and J columns in {resolved} must be numeric") from exc
    if kind == "light":
        return validate_iv_data(v, j)
    if kind == "dark":
        return validate_dark_iv_data(v, j)
    raise ValueError(f"Unknown J-V kind {kind!r}; choose 'light' or 'dark'")


def _validate_iv_arrays(v_meas, j_meas) -> tuple[np.ndarray, np.ndarray]:
    """Validate the shape, finiteness, and voltage order shared by J-V datasets."""
    v = np.asarray(v_meas, dtype=float)
    j = np.asarray(j_meas, dtype=float)
    if v.ndim != 1 or j.ndim != 1 or v.size != j.size or v.size < 3:
        raise ValueError("J-V data must be equal-length one-dimensional arrays with at least 3 points")
    if not np.all(np.isfinite(v)) or not np.all(np.isfinite(j)):
        raise ValueError("J-V data must contain only finite values")
    if np.any(np.diff(v) <= 0):
        raise ValueError("Voltage V must be strictly increasing with no duplicates; run prepare_data.py first")
    if float(np.min(np.abs(v))) > 0.03:
        raise ValueError("Data lack a point near 0 V (required: |V| <= 0.03 V)")
    return v, j


def validate_iv_data(v_meas, j_meas) -> tuple[np.ndarray, np.ndarray]:
    """Enforce the generation-positive illuminated J-V calibration contract."""
    v, j = _validate_iv_arrays(v_meas, j_meas)
    i0 = int(np.argmin(np.abs(v)))
    if j[i0] <= 0:
        raise ValueError("Short-circuit current must be positive; check the generation-positive sign convention")
    if not np.isfinite(voc_zero_crossing(v, j)):
        raise ValueError(
            "Data do not reach Voc (no positive-to-nonpositive current crossing at V >= 0); "
            "check polarity or extend the forward-voltage sweep"
        )
    return v, j


def validate_dark_iv_data(v_meas, j_meas) -> tuple[np.ndarray, np.ndarray]:
    """Validate a dark J-V sweep without imposing an illuminated-current sign at 0 V."""
    v, j = _validate_iv_arrays(v_meas, j_meas)
    if not np.any((v > 0.0) & (j < 0.0)):
        raise ValueError(
            "Dark J-V data do not contain negative forward current under the "
            "generation-positive convention; check wiring and sign conversion"
        )
    return v, j


def fit_from_csv(path: str | None = None,
                 method: str | None = None,
                 mode: str | None = None,
                 **fit_kws) -> lmfit.MinimizerResult:
    """Load a J-V CSV and fit it using configured defaults."""
    if path is None:
        path = CALIBRATION.get("data_file", "data/synthetic/iv.csv")
    if method is None:
        method = CALIBRATION.get("method", "least_squares")
    v, i = load_iv_csv(path)
    return fit(v, i, method=method, mode=mode, **fit_kws)


@dataclass
class JointData:
    """Validated observables used by the optional one-cell joint calibration."""

    sample: str
    light_v: np.ndarray
    light_j: np.ndarray
    dark_v: np.ndarray
    dark_j: np.ndarray
    light_voc: float
    light_ishort: dict[str, float]
    dark_open_circuit_offset: float | None
    dark_ishort: dict[str, float] | None
    weights: dict[str, float]
    iv_sigma_fraction: float
    ishort_sigma_floor: float
    voc_sigma: float
    paths: dict[str, str]


def _summary_row(path: str, sample: str, condition: str,
                 required: tuple[str, ...], optional: bool = False) -> pd.Series | None:
    """Load one sample/condition row from a processed summary table."""
    resolved = _resolve(path)
    if not resolved.is_file():
        raise FileNotFoundError(f"Processed summary file not found: {resolved}")
    df = pd.read_csv(resolved)
    missing = [c for c in ("sample", "condition", *required) if c not in df.columns]
    if missing:
        raise ValueError(f"{resolved} is missing columns {missing}; found {list(df.columns)}")
    mask = (df["sample"].astype(str).str.strip() == str(sample)) \
        & (df["condition"].astype(str).str.strip().str.lower() == condition.lower())
    rows = df.loc[mask]
    if len(rows) == 0 and optional:
        return None
    if len(rows) != 1:
        raise ValueError(
            f"{resolved} must contain exactly one row for sample={sample}, "
            f"condition={condition}; found {len(rows)}")
    row = rows.iloc[0]
    for name in required:
        try:
            value = float(row[name])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{resolved} column {name!r} must be numeric") from exc
        if not np.isfinite(value):
            raise ValueError(f"{resolved} column {name!r} contains a non-finite value")
    return row


def _joint_weight(weights: dict, name: str) -> float:
    """Return and validate one non-negative joint-objective weight."""
    try:
        value = float(weights.get(name, 0.0))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Joint calibration weight {name!r} must be numeric") from exc
    if not np.isfinite(value) or value < 0:
        raise ValueError(f"Joint calibration weight {name!r} must be finite and >= 0")
    return value


def load_joint_data(
    sample: int | str | None = None,
    paths_override: dict[str, str] | None = None,
) -> JointData:
    """Load one cell's joint observables, optionally from recorded fit paths."""
    cfg = CALIBRATION.get("joint", {})
    sample_value = cfg.get("default_sample", 3) if sample is None else sample
    sample_label = str(sample_value).strip()
    if not sample_label:
        raise ValueError("sample must not be empty")

    default_paths = {
        "light_iv": "data/processed/light_iv_sample{sample}.csv",
        "dark_iv": "data/processed/dark_iv_sample{sample}.csv",
        "ishort_summary": "data/processed/ishort_summary.csv",
        "voc_summary": "data/processed/voc_summary.csv",
    }
    paths = dict(default_paths)
    paths.update(cfg.get("paths", {}))
    if paths_override is not None:
        unknown = set(paths_override) - set(default_paths)
        if unknown:
            raise ValueError(f"Unknown joint-data path keys: {sorted(unknown)}")
        paths.update(paths_override)
    paths = {name: str(value).format(sample=sample_label) for name, value in paths.items()}

    light_v, light_j = load_iv_csv(paths["light_iv"])
    dark_v, dark_j = load_iv_csv(paths["dark_iv"], kind="dark")
    voc_row = _summary_row(paths["voc_summary"], sample_label, "light", ("V_at_I0_V",))
    dark_offset_row = _summary_row(
        paths["voc_summary"], sample_label, "dark", ("V_at_I0_V",), optional=True)
    short_row = _summary_row(
        paths["ishort_summary"], sample_label, "light",
        ("J_mean_A_cm2", "J_std_A_cm2", "V_mean_V", "V_std_V", "n_points"),
    )
    short = {name: float(short_row[name]) for name in (
        "J_mean_A_cm2", "J_std_A_cm2", "V_mean_V", "V_std_V", "n_points")}
    dark_short_row = _summary_row(
        paths["ishort_summary"], sample_label, "dark",
        ("J_mean_A_cm2", "J_std_A_cm2", "V_mean_V", "V_std_V", "n_points"),
        optional=True,
    )
    dark_short = None if dark_short_row is None else {
        name: float(dark_short_row[name]) for name in (
            "J_mean_A_cm2", "J_std_A_cm2", "V_mean_V", "V_std_V", "n_points")
    }
    blocks = [("light", short)]
    if dark_short is not None:
        blocks.append(("dark", dark_short))
    for label, block in blocks:
        if block["n_points"] < 3 or not block["n_points"].is_integer():
            raise ValueError(
                f"The {label} ishort summary must report an integer n_points >= 3")
        if block["J_std_A_cm2"] < 0 or block["V_std_V"] < 0:
            raise ValueError(f"The {label} ishort standard deviations must be non-negative")
        if abs(block["V_mean_V"]) > 0.03:
            raise ValueError(
                f"The {label} ishort mean voltage must satisfy |V_mean_V| <= 0.03 V")
    if short["J_mean_A_cm2"] <= 0:
        raise ValueError(
            "The light ishort mean current must be positive under the generation-positive convention")
    if float(voc_row["V_at_I0_V"]) <= 0:
        raise ValueError("The measured light Voc must be positive")
    if not light_v[0] <= float(voc_row["V_at_I0_V"]) <= light_v[-1]:
        raise ValueError(
            "The independent light Voc must lie inside the illuminated J-V voltage range"
        )

    weights_cfg = cfg.get("weights", {})
    weights = {name: _joint_weight(weights_cfg, name) for name in (
        "light_iv", "dark_iv", "light_ishort", "light_voc")}
    if weights["light_iv"] == 0 and weights["dark_iv"] == 0 \
            and weights["light_ishort"] == 0 and weights["light_voc"] == 0:
        raise ValueError("At least one joint calibration weight must be > 0")

    try:
        iv_sigma_fraction = float(cfg.get("iv_sigma_fraction", 0.025))
        short_floor = float(cfg.get("ishort_sigma_floor", 5e-4))
        voc_sigma = float(cfg.get("voc_sigma", 0.010))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Joint iv_sigma_fraction, ishort_sigma_floor, and voc_sigma must be numeric"
        ) from exc
    if not np.isfinite(iv_sigma_fraction) or iv_sigma_fraction <= 0:
        raise ValueError("joint.iv_sigma_fraction must be finite and > 0")
    if not np.isfinite(short_floor) or short_floor <= 0:
        raise ValueError("joint.ishort_sigma_floor must be finite and > 0")
    if not np.isfinite(voc_sigma) or voc_sigma <= 0:
        raise ValueError("joint.voc_sigma must be finite and > 0")

    return JointData(
        sample=sample_label,
        light_v=light_v,
        light_j=light_j,
        dark_v=dark_v,
        dark_j=dark_j,
        light_voc=float(voc_row["V_at_I0_V"]),
        light_ishort=short,
        dark_open_circuit_offset=(
            None if dark_offset_row is None else float(dark_offset_row["V_at_I0_V"])
        ),
        dark_ishort=dark_short,
        weights=weights,
        iv_sigma_fraction=iv_sigma_fraction,
        ishort_sigma_floor=short_floor,
        voc_sigma=voc_sigma,
        paths=paths,
    )


def _voc_current_sigma(data: JointData) -> float:
    """Translate the stated Voc discrepancy scale into current near the crossing."""
    n = min(4, data.light_v.size)
    nearest = np.argsort(
        np.abs(data.light_v - data.light_voc), kind="stable"
    )[:n]
    nearest.sort()
    slope = float(np.polyfit(data.light_v[nearest], data.light_j[nearest], 1)[0])
    j_floor = 0.01 * max(float(np.max(np.abs(data.light_j))), 1e-12)
    return max(abs(slope) * data.voc_sigma, j_floor, 1e-4)


def joint_residual(pars: lmfit.Parameters, data: JointData,
                   mode: str | None = None) -> np.ndarray:
    """Evaluate weighted residuals for one cell's multiple measurements.

    Each light/dark J-V curve contributes one RMS-normalized block using the
    configured model-data discrepancy fraction. The independent light-`ishort`
    and light-Voc observations each contribute one residual using their stated
    discrepancy scales. Block weights are applied only after those scalings.
    """
    base = dict(MODEL_PARAMS)
    base.update(pars.valuesdict())
    residuals: list[np.ndarray] = []
    mode = mode or RESIDUAL_MODE

    def add_iv(name: str, params: dict, voltage: np.ndarray, current: np.ndarray) -> None:
        weight = data.weights[name]
        if weight == 0:
            return
        simulated = run_simulation_terminal(params=params, voltages=voltage, j_meas=current)
        # ``residual_vector`` first supplies the selected current scale.  The
        # explicit fractional discrepancy then makes that scale comparable to
        # the Jsc and Voc uncertainty floors.  Dividing by sqrt(N) makes each
        # curve a block-level RMS contribution rather than weighting it merely
        # because it contains more sampled voltages.
        scaled = residual_vector(simulated, current, mode) / data.iv_sigma_fraction
        residuals.append(np.sqrt(weight / current.size) * scaled)

    add_iv("light_iv", base, data.light_v, data.light_j)
    dark_params = dict(base)
    dark_params["photon_flux"] = 0.0
    add_iv("dark_iv", dark_params, data.dark_v, data.dark_j)

    weight = data.weights["light_ishort"]
    if weight:
        j_mean = data.light_ishort["J_mean_A_cm2"]
        sigma = max(abs(data.light_ishort["J_std_A_cm2"]), data.ishort_sigma_floor)
        simulated = run_simulation_terminal(
            params=base,
            voltages=np.array([data.light_ishort["V_mean_V"]]),
            j_meas=np.array([j_mean]),
        )[0]
        residuals.append(np.array([np.sqrt(weight) * (simulated - j_mean) / sigma]))

    weight = data.weights["light_voc"]
    if weight:
        # A measured Voc is an I=0 condition. Evaluating the model current at
        # that voltage is equivalent to a local Voc anchor and avoids a costly
        # dense terminal-J-V solve at every optimizer iteration.
        simulated = run_simulation_terminal(
            params=base,
            voltages=np.array([data.light_voc]),
            j_meas=np.array([0.0]),
        )[0]
        residuals.append(np.array([
            np.sqrt(weight) * simulated / _voc_current_sigma(data)
        ]))

    if not residuals:
        raise ValueError("Joint calibration has no active observables")
    return np.concatenate(residuals)


def fit_joint(data: JointData, params: lmfit.Parameters | None = None,
              method: str | None = None, mode: str | None = None,
              **fit_kws) -> lmfit.MinimizerResult:
    """Fit the configured parameter subset to one cell's joint observables."""
    if not isinstance(data, JointData):
        raise TypeError("data must be a JointData instance")
    if params is None:
        params = make_params()
    method = method or CALIBRATION.get("method", "least_squares")
    kws = dict(fit_kws)
    # The joint residual already uses explicit model-data discrepancy scales.
    # Keep the local covariance on those stated scales instead of multiplying
    # it by lmfit's point-count-based reduced chi-square.
    kws.setdefault("scale_covar", False)
    if method == "least_squares" and CALIBRATION.get("diff_step") is not None:
        kws.setdefault("diff_step", CALIBRATION["diff_step"])
    return lmfit.minimize(joint_residual, params, args=(data, mode or RESIDUAL_MODE),
                          method=method, **kws)


def joint_block_score(chisqr: float, data: JointData) -> float:
    """Return the weighted mean squared discrepancy across active blocks.

    A score of 1 means that the weighted block RMS values match the stated
    discrepancy scales on average; a score above 4 means an average mismatch
    greater than twice those scales. This is a teaching diagnostic, not a
    statistical reduced chi-square.
    """
    value = float(chisqr)
    if not np.isfinite(value) or value < 0:
        raise ValueError(f"chisqr must be finite and non-negative; received {chisqr!r}")
    active_weight = sum(weight for weight in data.weights.values() if weight > 0)
    if active_weight <= 0:
        raise ValueError("Joint calibration has no positive observable-block weights")
    return value / active_weight


def evaluate_joint(params: lmfit.Parameters | dict, data: JointData) -> dict:
    """Return per-observable fit diagnostics for a completed joint fit."""
    base = dict(MODEL_PARAMS)
    values = params.valuesdict() if isinstance(params, lmfit.Parameters) else params
    base.update(values)
    # Compare against the *self-consistent terminal current*, not the implicit
    # equation residual used during optimization.  The latter is efficient but
    # is not itself a predicted J-V curve when the model/data mismatch is large.
    v_term, j_term = terminal_iv(
        base, n=max(320, 20 * data.light_v.size),
        v_max=max(0.85, float(data.light_v.max()) + 0.10),
    )
    light_sim = np.interp(data.light_v, v_term, j_term)
    dark_params = dict(base)
    dark_params["photon_flux"] = 0.0
    v_dark, j_dark = terminal_iv(
        dark_params, n=max(320, 20 * data.dark_v.size),
        v_max=max(0.85, float(data.dark_v.max()) + 0.10),
    )
    dark_sim = np.interp(data.dark_v, v_dark, j_dark)
    short_j = data.light_ishort["J_mean_A_cm2"]
    short_sim = float(np.interp(data.light_ishort["V_mean_V"], v_term, j_term))
    voc_sim = voc_zero_crossing(v_term, j_term)
    return {
        "sample": data.sample,
        "light_iv_points": int(data.light_v.size),
        "dark_iv_points": int(data.dark_v.size),
        "light_iv_rmse_A_cm2": float(np.sqrt(np.mean((light_sim - data.light_j) ** 2))),
        "dark_iv_rmse_A_cm2": float(np.sqrt(np.mean((dark_sim - data.dark_j) ** 2))),
        "light_ishort_measured_A_cm2": float(short_j),
        "light_ishort_simulated_A_cm2": float(short_sim),
        "light_ishort_error_A_cm2": float(short_sim - short_j),
        "light_voc_measured_V": float(data.light_voc),
        "light_voc_simulated_V": float(voc_sim),
        "light_voc_error_V": float(voc_sim - data.light_voc),
        "dark_zero_current_offset_V": (
            None if data.dark_open_circuit_offset is None
            else float(data.dark_open_circuit_offset)
        ),
        "dark_ishort_diagnostic_A_cm2": (
            None if data.dark_ishort is None
            else float(data.dark_ishort["J_mean_A_cm2"])
        ),
    }
