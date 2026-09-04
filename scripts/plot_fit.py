"""Render fitted-model versus reference J-V diagnostics from saved metadata."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import lmfit
import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from calibration.fit import evaluate_joint, load_iv_csv, load_joint_data
from calibration.report import comparison_figure, joint_comparison_figure, physical_warnings
from config import SIMULATION

def _project_path(path: str | Path) -> Path:
    """Resolve a user-supplied relative path from the project root."""
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def _verify_hash(path: str | Path, expected: str | None) -> None:
    """Require and verify the SHA-256 recorded for one calibration input."""
    valid_hex = isinstance(expected, str) and len(expected) == 64 and all(
        character in "0123456789abcdefABCDEF" for character in expected
    )
    if not valid_hex:
        raise SystemExit(
            "Fit metadata contain a missing or invalid calibration-input SHA-256; "
            "rerun scripts/run_calibration.py before plotting saved parameters."
        )
    source = _project_path(path)
    if not source.is_file():
        raise SystemExit(f"Recorded calibration input is missing: {source}")
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != expected.lower():
        raise SystemExit(
            f"Calibration input changed since the fit: {source}. "
            "Rerun scripts/run_calibration.py before plotting saved parameters."
        )


def load_params_json(path: str) -> lmfit.Parameters:
    """Load the repository's explicit, versioned fitted-parameter schema."""
    source = _project_path(path)
    payload = json.loads(source.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError(
            f"Unsupported fitted-parameter schema in {source}; "
            "rerun scripts/run_calibration.py"
        )
    records = payload.get("parameters")
    if not isinstance(records, dict) or not records:
        raise ValueError(f"Invalid fitted-parameter JSON: {source}")
    params = lmfit.Parameters()
    for name, record in records.items():
        if not isinstance(record, dict) or "value" not in record:
            raise ValueError(f"Invalid parameter record for {name!r}: {source}")
        lower = -np.inf if record.get("min") is None else float(record["min"])
        upper = np.inf if record.get("max") is None else float(record["max"])
        params.add(
            name,
            value=float(record["value"]),
            vary=bool(record.get("vary", True)),
            min=lower,
            max=upper,
        )
        stderr = record.get("stderr")
        params[name].stderr = None if stderr is None else float(stderr)
    return params


def _metadata_for_params(path: str) -> Path:
    """Find provenance next to either standard or joint fit parameters."""
    param_path = _project_path(path).resolve()
    candidates = []
    if param_path.stem.endswith("fitted_params"):
        candidates.append(param_path.with_name(
            param_path.stem[:-len("fitted_params")] + "fit_metadata.json"))
    candidates.append(param_path.with_name("fit_metadata.json"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot calibration results")
    ap.add_argument(
        "--params", required=True,
        help="Saved fitted-parameter JSON created by scripts/run_calibration.py",
    )
    ap.add_argument("--data", help="Override the dataset recorded in fit metadata")
    ap.add_argument(
        "--out",
        help="Output PNG path; defaults to fit_plot.png or joint_observables.png",
    )
    args = ap.parse_args()

    metadata_path = _metadata_for_params(args.params)
    if not metadata_path.exists():
        raise SystemExit(
            "Saved parameters have no fit_metadata.json, so their dataset is unknown; "
            "rerun scripts/run_calibration.py or provide the matching metadata file.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("schema_version") != 1:
        raise SystemExit(
            f"Unsupported fit-metadata schema in {metadata_path}; "
            "rerun scripts/run_calibration.py"
        )
    fitted = load_params_json(args.params)
    print(f"[NOTE] Using saved fitted parameters: {args.params}")
    if "model_params" not in metadata:
        raise SystemExit(
            "fit metadata do not contain the fixed model parameters; "
            "rerun scripts/run_calibration.py"
        )
    if "simulation_config" not in metadata:
        raise SystemExit(
            "fit metadata do not contain the mesh and solver configuration; "
            "rerun scripts/run_calibration.py"
        )
    if metadata["simulation_config"] != SIMULATION:
        raise SystemExit(
            "config.py SIMULATION settings changed since the fit. "
            "Rerun scripts/run_calibration.py before plotting saved parameters."
        )
    full = dict(metadata["model_params"])
    full.update(fitted.valuesdict())

    mode = metadata.get("mode")
    if mode == "joint":
        if args.data:
            raise SystemExit("--data is not valid for a joint fit; its full dataset bundle is in metadata")
        sample = metadata.get("sample")
        if not sample:
            raise SystemExit("Joint fit metadata do not contain a sample label")
        recorded_paths = metadata.get("datasets")
        required_paths = {"light_iv", "dark_iv", "ishort_summary", "voc_summary"}
        if not isinstance(recorded_paths, dict) or not required_paths <= set(recorded_paths):
            raise SystemExit(
                "Joint fit metadata do not contain the complete recorded dataset bundle; "
                "rerun scripts/run_calibration.py"
            )
        data = load_joint_data(sample, paths_override=recorded_paths)
        expected_hashes = metadata.get("dataset_sha256")
        if not isinstance(expected_hashes, dict):
            raise SystemExit(
                "Joint fit metadata do not contain calibration-input SHA-256 values; "
                "rerun scripts/run_calibration.py"
            )
        for name, path in data.paths.items():
            _verify_hash(path, expected_hashes.get(name))
        print(f"[NOTE] Recreating the complete Cell #{sample} joint-observable figure")
        fig = joint_comparison_figure(data, full)
        compare = None
        # Replay both the figure and numerical diagnostics from the complete
        # parameter snapshot stored with the fit.  Passing only ``fitted`` here
        # would silently mix saved fitted values with today's config.py fixed
        # parameters whenever the teaching baseline changes.
        metrics = evaluate_joint(full, data)
        default_name = "joint_observables.png"
    elif mode == "single":
        data_path = args.data or metadata.get("data_file")
        if not data_path:
            raise SystemExit("fit_metadata.json has no data_file; provide --data explicitly.")
        if args.data:
            print(
                f"[WARNING] Overriding the fit-metadata dataset with: {data_path}; "
                "the original fit-input hash does not apply to this file"
            )
        else:
            print(f"[NOTE] Read the data file from fit metadata: {data_path}")
            _verify_hash(data_path, metadata.get("data_sha256"))
        v_meas, j_meas = load_iv_csv(data_path)
        resolved = _project_path(data_path).resolve()
        synthetic_root = (PROJECT_ROOT / "data" / "synthetic").resolve()
        data_label = "synthetic reference" if synthetic_root in resolved.parents else "measured data"
        print("Running the fitted model and creating the figure...")
        fig, compare = comparison_figure(v_meas, j_meas, full, data_label=data_label)
        default_name = "fit_plot.png"
    else:
        raise SystemExit(f"Unknown fit mode {mode!r} in {metadata_path}")

    out = _project_path(args.out or f"results/{default_name}")
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {out}")

    if compare is not None:
        m = compare["meas"]
        s = compare["sim"]
        print("\n-- Metric comparison (data vs simulation) --")
        print(f"  Jsc: {m['Jsc']*1e3:.2f}  vs  {s['Jsc']*1e3:.2f}  mA/cm^2")
        print(f"  Voc: {m['Voc']:.4f}  vs  {s['Voc']:.4f}  V")
        print(f"  FF : {m['FF']:.4f}  vs  {s['FF']:.4f}")
        print(f"  Pmax: {m['Pmax']*1e3:.2f}  vs  {s['Pmax']*1e3:.2f}  mW/cm^2")
        print("  Efficiency omitted: it requires an independently measured incident irradiance.")
    else:
        print("\n-- Joint-observable checks --")
        print(
            f"  illuminated J-V RMSE: "
            f"{metrics['light_iv_rmse_A_cm2'] * 1e3:.3f} mA/cm^2"
        )
        print(f"  dark J-V RMSE : {metrics['dark_iv_rmse_A_cm2'] * 1e3:.3f} mA/cm^2")
        print(
            f"  illuminated Jsc: "
            f"{metrics['light_ishort_measured_A_cm2'] * 1e3:.3f} measured vs "
            f"{metrics['light_ishort_simulated_A_cm2'] * 1e3:.3f} mA/cm^2"
        )
        print(
            f"  illuminated Voc: {metrics['light_voc_measured_V']:.4f} measured vs "
            f"{metrics['light_voc_simulated_V']:.4f} V"
        )
        objective = metadata.get("joint_objective", {})
        score = objective.get("normalized_block_score")
        threshold = objective.get("quality_warning_threshold")
        if score is not None:
            print(f"  block score   : {float(score):.3f} "
                  "(1 = stated scales; 4 = twice-scale weighted RMS)")
        if score is not None and threshold is not None \
                and float(score) > float(threshold):
            print(
                "  [WARNING] Quality gate failed; covariance describes local "
                "optimizer sensitivity, not physical adequacy."
            )

    warns = physical_warnings(fitted)
    if warns:
        print("\n-- Parameter plausibility warnings --")
        for w in warns:
            print(f"  [WARNING] {w}")
    else:
        print("\n(No obvious parameter plausibility issues.)")


if __name__ == "__main__":
    main()
