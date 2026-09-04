"""Generate a one-parameter sensitivity sweep for the teaching model."""
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import MODEL_PARAMS, MODELED_INPUT_POWER_W_CM2
from model import terminal_iv
from model.analysis import solar_metrics
from model.style import C_BLUE, C_ORANGE, C_GRAY


PARAM_RANGES = {
    "electron_lifetime": (1e-7, 1e-3),
    "hole_lifetime": (1e-6, 1e-4),
    "front_srv": (1e2, 1e7),
    "back_srv": (1e2, 1e7),
    "emitter_doping": (1e18, 1e20),
    "base_doping": (1e14, 1e18),
    "thickness": (50e-4, 500e-4),
    "photon_flux": (0.1, 5.0),
}

PARAM_LABELS = {
    "electron_lifetime": "electron lifetime $\\tau_n$ (s)",
    "hole_lifetime": "hole lifetime $\\tau_p$ (s)",
    "front_srv": "front SRV (cm/s)",
    "back_srv": "back SRV (cm/s)",
    "emitter_doping": "p⁺ emitter doping N_A (cm⁻³)",
    "base_doping": "n-base doping N_D (cm⁻³)",
    "thickness": "thickness (µm)",
    "photon_flux": "generation scale (× baseline)",
}


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Parameter sweep with a projector-ready Jsc/Voc figure"
    )
    ap.add_argument("--param", required=True, help="Parameter to sweep; see PARAM_RANGES")
    ap.add_argument("--start", type=float, default=None, help="Sweep lower bound")
    ap.add_argument("--stop", type=float, default=None, help="Sweep upper bound")
    ap.add_argument("--n", type=int, default=5, help="Number of sweep points")
    ap.add_argument("--out", default="results/sweep.png", help="Output PNG path")
    args = ap.parse_args()

    if args.param not in PARAM_RANGES:
        print(f"Unknown parameter: {args.param}. Choices: {list(PARAM_RANGES)}")
        sys.exit(1)
    if args.n < 2:
        raise SystemExit(f"--n must be >= 2; received {args.n}")

    lo, hi = PARAM_RANGES[args.param]
    start = args.start if args.start is not None else lo
    stop = args.stop if args.stop is not None else hi
    if not np.all(np.isfinite([start, stop])) or start <= 0 or stop < start:
        raise SystemExit("Sweep bounds must be finite with start > 0 and stop >= start")
    values = np.geomspace(start, stop, args.n)


    metric_voltages = np.linspace(0.0, 0.72, 37)

    jscs, vocs = [], []
    for v in values:
        params = dict(MODEL_PARAMS)
        params[args.param] = float(v)
        V, J = terminal_iv(params=params, v_junc=metric_voltages)

        modeled_pin = MODELED_INPUT_POWER_W_CM2 * params["photon_flux"]
        m = solar_metrics(V, J, pin=modeled_pin)
        if not np.isfinite(m["Voc"]):
            raise RuntimeError(
                f"At {args.param}={v:.3e}, the 0.72 V sweep still does not cross Voc; extend the sweep")
        jsc = m["Jsc"] * 1e3                    # -> mA/cm^2
        jscs.append(jsc)
        vocs.append(m["Voc"])
        print(f"  {args.param}={v:.3e}: Jsc={jsc:.2f} mA/cm^2, Voc={m['Voc']:.4f} V, "
              f"FF={m['FF']:.3f}, η={m['eta']*100:.2f}%")

    values = np.asarray(values)
    jscs = np.asarray(jscs)
    vocs = np.asarray(vocs)
    xlabel = PARAM_LABELS[args.param]

    values_plot = values * 1e4 if args.param == "thickness" else values

    # Jsc and Voc are the two direct observables requested in the assessed
    # sensitivity task.  A 1x2 layout keeps their numerical trends readable on
    # a classroom projector; FF and eta remain in the terminal table above.
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.2, 4.2), sharex=True)

    baseline = MODEL_PARAMS.get(args.param)
    baseline_plot = baseline * 1e4 if (baseline is not None and args.param == "thickness") else baseline
    for ax in (ax1, ax2):
        if baseline_plot is not None and values_plot.min() <= baseline_plot <= values_plot.max():
            ax.axvline(baseline_plot, color=C_GRAY, ls="--", lw=1.0)
        ax.set_xscale("log")
        ax.set_xlabel(xlabel, fontsize=16)
        ax.tick_params(labelsize=15)
        ax.grid(True)

    ax1.plot(values_plot, vocs, "o-", color=C_BLUE, lw=1.5)
    ax1.set_ylabel("$V_{oc}$ (V)", fontsize=16)
    ax1.set_title("Open-circuit voltage", fontsize=18)
    if baseline_plot is not None and values_plot.min() <= baseline_plot <= values_plot.max():
        ax1.text(baseline_plot, ax1.get_ylim()[1], " baseline", color=C_GRAY,
                 fontsize=14, va="top", ha="left")

    ax2.plot(values_plot, jscs, "s-", color=C_ORANGE, lw=1.5)
    ax2.set_ylabel("$J_{sc}$ (mA/cm²)", fontsize=16)
    ax2.set_title("Short-circuit current density", fontsize=18)

    fig.tight_layout()
    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {out}")


if __name__ == "__main__":
    main()
