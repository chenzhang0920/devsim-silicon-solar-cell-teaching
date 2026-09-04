"""Generate deterministic synthetic J-V data for the teaching workflow."""
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from config import MODEL_PARAMS, SIMULATION
from model import terminal_iv


def _project_path(path: str | Path) -> Path:
    """Resolve a project-relative output path."""
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def make_iv(seed: int, noise_frac: float, v_stop: float | None = None,
            v_step: float = 0.025):
    """Return a deterministic noisy J-V sample from the configured model."""
    if v_stop is None:
        v_stop = SIMULATION["voltages"]["stop"]
    if not np.isfinite(noise_frac) or noise_frac < 0:
        raise ValueError("noise_frac must be finite and >= 0")
    if not np.isfinite(v_stop) or v_stop <= 0:
        raise ValueError("v_stop must be finite and > 0")
    if not np.isfinite(v_step) or v_step <= 0:
        raise ValueError("v_step must be finite and > 0")
    n_points = int(round(v_stop / v_step)) + 1
    if n_points < 3:
        raise ValueError("v_stop and v_step must define at least three voltage points")
    V_sim, J_sim = terminal_iv(params=MODEL_PARAMS)


    V_meas = np.linspace(0.0, v_stop, n_points)
    J_meas = np.interp(V_meas, V_sim, J_sim)


    rng = np.random.default_rng(seed)
    jsc = abs(float(J_meas[0]))
    J_meas = J_meas + rng.normal(0.0, noise_frac * jsc, size=J_meas.shape)
    return V_meas, J_meas


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic J-V demonstration data")
    ap.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    ap.add_argument("--noise-frac", type=float, default=0.004,
                    help="J-V noise amplitude as a fraction of Jsc (default: 0.004)")
    ap.add_argument("--iv-out", default="data/synthetic/iv.csv",
                    help="Synthetic J-V output path (default: data/synthetic/iv.csv)")
    args = ap.parse_args()

    iv_path = _project_path(args.iv_out).resolve()
    synthetic_root = (PROJECT_ROOT / "data" / "synthetic").resolve()
    if synthetic_root not in iv_path.parents or iv_path.suffix.lower() != ".csv":
        raise SystemExit(
            "--iv-out must be a CSV file inside data/synthetic; synthetic demo data "
            "must not overwrite raw or processed measurements"
        )
    try:
        V, J = make_iv(args.seed, args.noise_frac)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    iv_path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(iv_path, np.column_stack([V, J]), delimiter=",",
               header="V,J", comments="", fmt="%.8g")
    print(f"Generated synthetic J-V data: {iv_path} ({len(V)} points, Jsc ~ {abs(J[0])*1e3:.2f} mA/cm^2)")

    print("\n[NOTE] This synthetic J-V table (forward model plus noise) exercises the workflow without hardware.")
    print("       Calibrating it effectively fits the model to itself; see this script's documentation.")


if __name__ == "__main__":
    main()
