"""Fit the forward model and save calibration diagnostics.

The default command keeps the beginner-friendly single illuminated-J-V smoke test.
Use ``--joint --sample 3`` for the measured-cell exercise: that objective uses
the illuminated and dark J-V sweeps plus independent illuminated short-circuit and Voc
measurements, with documented weights from ``config.py``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import lmfit
import matplotlib
import devsim

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from config import CALIBRATION, MODEL_PARAMS, SIMULATION
from calibration.fit import (
    evaluate_joint,
    fit_from_csv,
    fit_joint,
    joint_block_diagnostics,
    joint_block_score,
    load_iv_csv,
    load_joint_data,
)
from calibration.report import (
    comparison_figure,
    identifiability_figure,
    identifiability_summary,
    joint_comparison_figure,
    physical_warnings,
)

RESULTS_DIR = PROJECT_ROOT / "results"


def _clear_mode_outputs(joint: bool) -> None:
    """Remove the previous mode-specific products before publishing a new fit."""
    names = (
        (
            "joint_fitted_params.json",
            "joint_fit_metadata.json",
            "joint_metrics.json",
            "joint_observables.png",
            "joint_identifiability.png",
        )
        if joint
        else (
            "fitted_params.json",
            "fit_metadata.json",
            "fit_plot.png",
            "identifiability.png",
        )
    )
    for name in names:
        path = RESULTS_DIR / name
        if path.is_file():
            path.unlink()


def _project_path(path: str | Path) -> Path:
    """Resolve a project-relative path without depending on the launch directory."""
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def _sha256(path: str | Path) -> str:
    """Return a compact provenance hash for one calibration input."""
    return hashlib.sha256(_project_path(path).read_bytes()).hexdigest()


def _data_label(path: str | Path) -> str:
    """Distinguish bundled synthetic references from measured data in figures."""
    resolved = _project_path(path).resolve()
    synthetic = (PROJECT_ROOT / "data" / "synthetic").resolve()
    return "synthetic reference" if synthetic in resolved.parents else "measured data"


def _finite_or_none(value):
    """Convert a scalar to finite JSON or ``None``."""
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def _covariance_matrix(covar) -> list[list[float | None]]:
    """Serialize a covariance matrix without non-standard JSON NaN values."""
    array = np.asarray(covar, dtype=float)
    return [[_finite_or_none(value) for value in row] for row in array]


def parameter_payload(params: lmfit.Parameters) -> dict:
    """Return a strict, human-readable JSON representation of fit parameters."""

    return {
        "schema_version": 1,
        "parameters": {
            name: {
                "value": float(parameter.value),
                "vary": bool(parameter.vary),
                "min": _finite_or_none(parameter.min),
                "max": _finite_or_none(parameter.max),
                "stderr": _finite_or_none(parameter.stderr) if parameter.vary else None,
            }
            for name, parameter in params.items()
        },
    }


def _print_optimizer_summary(result: lmfit.MinimizerResult) -> None:
    """Print convergence and parameters without presenting a statistical chi-square."""
    print("\n-- Optimizer status --")
    print(f"  success: {bool(getattr(result, 'success', False))}")
    print(f"  evaluations: {int(getattr(result, 'nfev', 0))}")
    print(f"  message: {getattr(result, 'message', '')}")
    print("\n-- Fitted parameters --")
    print(f"  {'name':<22}{'value':>14}{'local stderr':>16}{'status':>10}")
    for name, parameter in result.params.items():
        status = "varied" if parameter.vary else "fixed"
        uncertainty = "n/a" if not parameter.vary or parameter.stderr is None \
            or not np.isfinite(parameter.stderr) else f"{parameter.stderr:.5g}"
        print(f"  {name:<22}{parameter.value:>14.6g}{uncertainty:>16}{status:>10}")


def _print_joint_blocks(blocks: dict[str, dict]) -> None:
    """Print how each observable contributes to the joint objective."""
    labels = {
        "light_iv": "illuminated J-V",
        "dark_iv": "dark J-V",
        "light_ishort": "independent Jsc",
        "light_voc": "independent Voc",
    }
    print("\n-- Joint objective by observable --")
    print(f"  {'block':<18}{'weight':>9}{'RMS / scale':>15}{'share':>10}")
    for name, values in blocks.items():
        rms = values["normalized_rms"]
        rms_text = "inactive" if rms is None else f"{rms:.3f}"
        print(
            f"  {labels[name]:<18}{values['weight']:>9.2f}"
            f"{rms_text:>15}{values['objective_share']:>9.1%}"
        )


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Calibrate the silicon solar-cell model")
    ap.add_argument(
        "data", nargs="?",
        help=(
            "Single illuminated-J-V CSV. Omit it for the configured synthetic "
            "smoke test."
        ),
    )
    ap.add_argument(
        "--joint", action="store_true",
        help=(
            "Fit one measured cell using illuminated/dark J-V, illuminated Jsc, "
            "and illuminated Voc."
        ),
    )
    ap.add_argument(
        "--sample",
        help="Cell label for --joint (default: config CALIBRATION['joint']['default_sample']).",
    )
    return ap


def _save_common(result: lmfit.MinimizerResult, data_path: str,
                 mode: str, extra_metadata: dict | None = None,
                 stem: str = "") -> tuple[object, list[str]]:
    """Save parameters, covariance and provenance shared by both fit modes."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    prefix = f"{stem}_" if stem else ""
    params_path = RESULTS_DIR / f"{prefix}fitted_params.json"
    metadata_path = RESULTS_DIR / f"{prefix}fit_metadata.json"
    params_path.write_text(
        json.dumps(parameter_payload(result.params), indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    var_names = getattr(result, "var_names", None) or [
        n for n, p in result.params.items() if getattr(p, "vary", True)
    ]
    covar = getattr(result, "covar", None)
    metadata = {
        "schema_version": 1,
        "mode": mode,
        "data_file": str(data_path),
        "data_sha256": _sha256(data_path),
        "command": " ".join(["python", "scripts/run_calibration.py", *sys.argv[1:]]),
        "residual_mode": CALIBRATION.get("residual_mode", "absolute"),
        "model_params": MODEL_PARAMS,
        "simulation_config": SIMULATION,
        "fit_configuration": {
            "method": CALIBRATION.get("method", "least_squares"),
            "diff_step": CALIBRATION.get("diff_step"),
            "parameters": CALIBRATION.get("params", {}),
        },
        "software_versions": {
            "python": platform.python_version(),
            "devsim": getattr(devsim, "__version__", "unknown"),
            "lmfit": lmfit.__version__,
            "numpy": np.__version__,
        },
        "optimizer_diagnostics": {
            "success": bool(getattr(result, "success", False)),
            "message": str(getattr(result, "message", "")),
            "nfev": int(getattr(result, "nfev", 0)),
            "sum_squared_scaled_residuals": _finite_or_none(
                getattr(result, "chisqr", None)
            ),
            "lmfit_redchi_internal": _finite_or_none(getattr(result, "redchi", None)),
            "interpretation": (
                "Internal optimizer diagnostics, not a statistical goodness-of-fit test. "
                "For joint mode use joint_objective.normalized_block_score."
            ),
        },
        "covariance_scaling": (
            "lmfit default: local Jacobian covariance scaled by its internal "
            "reduced chi-square. Residual normalization is a teaching scale, "
            "not an instrument-derived measurement uncertainty."
        ),
        "covariance": None if covar is None else {
            "variable_names": list(var_names),
            "matrix": _covariance_matrix(covar),
        },
    }
    if extra_metadata:
        metadata.update(extra_metadata)
    if "datasets" in metadata:
        metadata["dataset_sha256"] = {
            name: _sha256(path) for name, path in metadata["datasets"].items()
        }
    (metadata_path).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"Saved fitted parameters to {params_path}")
    print(f"Saved fit provenance to {metadata_path}")
    return covar, var_names


def main(argv: list[str] | None = None) -> None:
    args = _parser().parse_args(argv)
    if args.sample is not None and not args.joint:
        _parser().error("--sample is only valid together with --joint")
    if args.joint and args.data:
        _parser().error("--joint selects processed sample files; do not also pass a data CSV")

    if args.joint:
        data = load_joint_data(args.sample)
        result = fit_joint(data)
        block_score = joint_block_score(result.chisqr, data)
        block_diagnostics = joint_block_diagnostics(result.residual, data)
        quality_limit = float(CALIBRATION["joint"].get(
            "quality_warning_block_score", 4.0
        ))
        if not np.isfinite(quality_limit) or quality_limit <= 0:
            raise ValueError("joint quality_warning_block_score must be finite and > 0")
        data_path = data.paths["light_iv"]
        extra = {
            "sample": data.sample,
            "datasets": data.paths,
            "weights": data.weights,
            "iv_sigma_fraction": data.iv_sigma_fraction,
            "ishort_sigma_floor_A_cm2": data.ishort_sigma_floor,
            "voc_sigma_V": data.voc_sigma,
            "joint_objective": {
                "definition": "self_consistent_terminal_prediction",
                "normalized_block_score": block_score,
                "active_weight_sum": sum(
                    weight for weight in data.weights.values() if weight > 0
                ),
                "quality_warning_threshold": quality_limit,
                "quality_gate_passed": bool(block_score <= quality_limit),
                "blocks": block_diagnostics,
                "interpretation": (
                    "Weighted mean squared self-consistent terminal discrepancy across "
                    "active observable blocks; not a statistical reduced chi-square"
                ),
            },
            "covariance_scaling": (
                "Unscaled local Jacobian covariance using the stated discrepancy scales"
            ),
        }
        mode = "joint"
    else:
        data_path = args.data or CALIBRATION.get("data_file", "data/synthetic/iv.csv")
        result = fit_from_csv(args.data)
        data = None
        extra = None
        mode = "single"
        block_score = None
        block_diagnostics = None
        quality_limit = None

    _print_optimizer_summary(result)
    if not bool(getattr(result, "success", False)):
        raise RuntimeError(f"Calibration failed: {getattr(result, 'message', 'unknown error')}")
    # Avoid presenting new JSON beside stale figures if a later reporting step fails.
    _clear_mode_outputs(joint=data is not None)
    stem = "joint" if data is not None else ""
    covar, var_names = _save_common(
        result, data_path, mode, extra, stem=stem)

    full = dict(MODEL_PARAMS)
    full.update(result.params.valuesdict())
    if data is None:
        v_meas, j_meas = load_iv_csv(data_path)
        fig, _ = comparison_figure(
            v_meas, j_meas, full, data_label=_data_label(data_path)
        )
        fig_path = RESULTS_DIR / "fit_plot.png"
        fig.savefig(fig_path, dpi=150)
        plt.close(fig)
        print(f"Saved fit comparison figure to {fig_path}")
    else:
        metrics = evaluate_joint(result.params, data)
        metrics_payload = {
            "schema_version": 1,
            **metrics,
            "joint_objective": extra["joint_objective"],
        }
        (RESULTS_DIR / "joint_metrics.json").write_text(
            json.dumps(metrics_payload, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        joint_fig = joint_comparison_figure(data, full, block_diagnostics)
        joint_path = RESULTS_DIR / "joint_observables.png"
        joint_fig.savefig(joint_path, dpi=150)
        plt.close(joint_fig)
        print(f"Saved joint diagnostics to {RESULTS_DIR / 'joint_metrics.json'}")
        print(f"Saved joint comparison figure to {joint_path}")
        print("\n-- Joint-observable checks --")
        print(f"  illuminated J-V RMSE: {metrics['light_iv_rmse_A_cm2'] * 1e3:.3f} mA/cm^2")
        print(f"  dark J-V RMSE : {metrics['dark_iv_rmse_A_cm2'] * 1e3:.3f} mA/cm^2")
        print(
            f"  illuminated Jsc: {metrics['light_ishort_measured_A_cm2'] * 1e3:.3f} "
            f"measured vs {metrics['light_ishort_simulated_A_cm2'] * 1e3:.3f} mA/cm^2"
        )
        print(
            f"  illuminated Voc: {metrics['light_voc_measured_V']:.4f} "
            f"measured vs {metrics['light_voc_simulated_V']:.4f} V"
        )
        print(
            f"  block score   : {block_score:.3f} (weighted mean-square)"
        )
        print(f"  weighted RMS  : {np.sqrt(block_score):.3f} × stated scale")
        _print_joint_blocks(block_diagnostics)
        if np.isfinite(block_score) and block_score > quality_limit:
            print(
                "  [WARNING] The normalized block score exceeds the stated teaching "
                "discrepancy scales. Treat covariance as local optimizer sensitivity, "
                "not proof that the model or fitted parameters are physically adequate."
            )

    id_path = RESULTS_DIR / (
        "joint_identifiability.png" if data is not None else "identifiability.png"
    )
    context = f"joint Cell #{data.sample} data" if data is not None \
        else f"the {_data_label(data_path)} J–V curve"
    quality_note = None
    if data is not None and block_score > quality_limit:
        quality_note = (
            f"Quality gate failed: block score {block_score:.1f} > {quality_limit:g}; "
            "local sensitivity only"
        )
    fig = identifiability_figure(
        result.params, covar, var_names, context=context, quality_note=quality_note
    )
    fig.savefig(id_path, dpi=150)
    plt.close(fig)
    print(f"Saved identifiability figure to {id_path}")
    quality_adequate = data is None or not np.isfinite(block_score) \
        or block_score <= quality_limit
    heading = "Parameter identifiability" if quality_adequate \
        else "Local covariance sensitivity (quality gate failed)"
    print(f"\n-- {heading} --")
    for line in identifiability_summary(
        result.params,
        covar,
        var_names,
        quality_adequate=quality_adequate,
    ):
        print(f"  {line}")

    warns = physical_warnings(result.params)
    if warns:
        print("\nParameter plausibility warnings:")
        for warning in warns:
            print(f"  [WARNING] {warning}")


if __name__ == "__main__":
    main()
