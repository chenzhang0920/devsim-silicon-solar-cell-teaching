"""Plot the calibration optimization trajectory and optional GIF."""
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import CALIBRATION, MODEL_PARAMS
from calibration.fit import load_iv_csv, make_params
from calibration.trace import (
    fit_with_trace,
    plot_optimization_trace,
    save_optimization_gif,
)


def _validate_shunt_fit(params) -> None:
    """Reject the discontinuous Rsh=0 sentinel when Rsh is varied."""
    rsh = params["shunt_resistance"]
    if rsh.vary and (rsh.value <= 0 or rsh.min <= 0):
        raise SystemExit(
            "Rsh=0 represents ideal infinity and cannot be a continuous fit value; "
            "set a positive initial value and lower bound in config.py "
            "(10 ohm cm^2 or larger is recommended for this lesson)."
        )


def _gif_output_path(png_output: str, explicit_gif: str | None = None) -> Path:
    """Resolve the animation beside a custom PNG unless explicitly overridden."""
    output = Path(explicit_gif) if explicit_gif else Path(png_output).with_suffix(".gif")
    return output if output.is_absolute() else PROJECT_ROOT / output


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot the fit-optimization convergence trajectory")
    ap.add_argument("--data", help="Reference J-V CSV; defaults to config data_file")
    ap.add_argument("--params", default=None,
                    help="Comma-separated parameters to fit; defaults to all varied parameters")
    ap.add_argument("--init", default=None,
                    help="Override initial values as comma-separated name=value pairs")
    ap.add_argument("--max-nfev", type=int, default=None,
                    help="Maximum function evaluations")
    ap.add_argument("--method", default=CALIBRATION.get("method", "least_squares"),
                    help="lmfit optimization method; defaults to config.CALIBRATION['method']")
    ap.add_argument("--gif", action="store_true", help="Also generate an animated GIF")
    ap.add_argument("--out", default="results/optimization.png", help="Output PNG path")
    ap.add_argument(
        "--gif-out",
        help="Output GIF path; defaults to --out with its suffix replaced by .gif",
    )
    args = ap.parse_args()

    data_path = args.data or CALIBRATION["data_file"]
    v, j = load_iv_csv(data_path)


    params = make_params()
    if args.params:
        keep = {s.strip() for s in args.params.split(",")}
        keep.discard("")
        unknown = keep - set(params.keys())
        if unknown:
            raise SystemExit(f"Unknown parameters: {sorted(unknown)}; choices: {list(params.keys())}")
        for name in params:
            params[name].vary = name in keep
            if name not in keep:


                params[name].value = MODEL_PARAMS[name]
        if not keep:
            raise SystemExit("--params requires at least one parameter name")
    if args.init:
        for pair in args.init.split(","):
            name, _, val = pair.partition("=")
            name = name.strip()
            if not name or not val.strip():
                raise SystemExit(f"--init expects name=value; received {pair!r}")
            if name not in params:
                raise SystemExit(f"Unknown parameter: {name}; choices: {list(params.keys())}")
            value = float(val)
            if not np.isfinite(value) or value < params[name].min or value > params[name].max:
                raise SystemExit(
                    f"Initial {name} must be finite and in [{params[name].min}, {params[name].max}]")
            params[name].value = value
    _validate_shunt_fit(params)
    if args.gif_out and not args.gif:
        raise SystemExit("--gif-out requires --gif")
    if args.max_nfev is not None and args.max_nfev < 1:
        raise SystemExit("--max-nfev must be >= 1")

    vary = [n for n, p in params.items() if p.vary]
    print(f"Starting fit and recording trajectory (parameters: {vary})...")
    names, trace, result = fit_with_trace(
        v, j, params=params, method=args.method, max_nfev=args.max_nfev)

    print(f"Recorded {len(trace)} iterations; final objective sum(r^2) = {trace[-1]['chisq']:.4f}")
    print("Fitted parameters:", {n: f"{result.params[n].value:.3e}" for n in names})
    if not bool(getattr(result, "success", False)):
        raise RuntimeError(
            "Optimization did not converge; increase --max-nfev or inspect the initial "
            f"values. Solver message: {getattr(result, 'message', 'unknown')}"
        )

    fig = plot_optimization_trace(names, trace, v, j)
    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {out}")

    if args.gif:
        gif_path = _gif_output_path(args.out, args.gif_out)
        gif_path.parent.mkdir(parents=True, exist_ok=True)
        save_optimization_gif(trace, v, j, gif_path, names=names)
        print(f"Saved animation to {gif_path}")


if __name__ == "__main__":
    main()
