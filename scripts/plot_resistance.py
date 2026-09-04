"""Illustrate series- and shunt-resistance effects on the terminal J-V curve."""
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import MODEL_PARAMS
from model import run_simulation
from model.analysis import solar_metrics
from model.style import C_BLUE, C_DARK, C_ORANGE


def _series(V, J_Acm2, Rs):
    """Map junction voltage to terminal voltage for area-normalized Rs."""
    return V - J_Acm2 * Rs


def _shunt(V, J_Acm2, Rsh):
    """Subtract junction shunt current from generation-positive current."""
    return J_Acm2 - V / Rsh


def main() -> None:
    ap = argparse.ArgumentParser(description="Effect of series and shunt resistance on J-V")
    ap.add_argument("--out", default="results/resistance.png", help="Output PNG path")
    args = ap.parse_args()

    # This figure deliberately starts from the intrinsic device so that each
    # illustrated parasitic is applied exactly once, independent of config.py.
    intrinsic = {**MODEL_PARAMS, "series_resistance": 0.0, "shunt_resistance": 0.0}
    V, J_A = run_simulation(params=intrinsic)
    V, J_A = np.asarray(V), np.asarray(J_A)

    J = J_A * 1e3  # A/cm² -> mA/cm²

    Rs_list = [0.0, 2.0, 5.0]      # Ω·cm²
    Rsh_list = [np.inf, 500.0, 200.0]  # Ω·cm²

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.3))


    line_styles = ["-", "--", ":"]
    for k, Rs in enumerate(Rs_list):
        Vs = _series(V, J_A, Rs)
        ff = solar_metrics(Vs, J * 1e-3)["FF"]
        label = (f"baseline: $R_s=0$ (FF = {ff:.3f})" if Rs == 0
                 else f"$R_s$ = {Rs:.0f} Ω·cm²  (FF = {ff:.3f})")
        ax1.plot(
            Vs, J, lw=2.2, ls=line_styles[k], label=label,
            color=(C_DARK, C_BLUE, "#6a3d9a")[k],
        )
    ax1.axhline(0, color="gray", lw=0.8)
    ax1.set_xlabel("Voltage V (V)"); ax1.set_ylabel("J (mA/cm²)")
    ax1.set_title("Series resistance reduces fill factor")
    ax1.legend(fontsize=11.5, frameon=False, loc="lower left")
    ax1.set_xlim(0.0, 0.66)
    ax1.set_ylim(-5.0, 32.0)
    ax1.grid(True)


    for k, Rsh in enumerate(Rsh_list):
        Jsh = _shunt(V, J_A, Rsh)            # A/cm²
        metrics = solar_metrics(V, Jsh)
        vs = metrics["Voc"]
        Jsh_mA = Jsh * 1e3                   # -> mA/cm²
        label = (f"baseline: $R_{{sh}}=\\infty$; $V_{{oc}}={vs:.3f}$ V; FF={metrics['FF']:.3f}" if np.isinf(Rsh)
                 else f"$R_{{sh}}={Rsh:.0f}$ Ω·cm²; $V_{{oc}}={vs:.3f}$ V; FF={metrics['FF']:.3f}")
        ax2.plot(
            V, Jsh_mA, lw=2.2, ls=line_styles[k], label=label,
            color=(C_DARK, C_ORANGE, "#b2182b")[k],
        )
    ax2.axhline(0, color="gray", lw=0.8)
    ax2.set_xlabel("Voltage V (V)"); ax2.set_ylabel("J (mA/cm²)")
    ax2.set_title("Shunt leakage reduces $V_{oc}$ and fill factor")
    ax2.legend(fontsize=11.5, frameon=False, loc="lower left")
    ax2.set_xlim(0.0, 0.66)
    ax2.set_ylim(-5.0, 32.0)
    ax2.grid(True)

    fig.tight_layout()
    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {out}")


if __name__ == "__main__":
    main()
