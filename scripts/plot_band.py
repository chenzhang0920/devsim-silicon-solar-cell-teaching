"""Generate the equilibrium and illuminated silicon band diagram."""
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
from model import profiles, check_params, run_simulation
from model.analysis import band_edges, solar_metrics
from model.style import C_BLUE, C_ORANGE, C_DARK


def _style(ax, title, *, show_ylabel=True):
    ax.set_title(title, fontsize=18, pad=8)
    ax.set_xlabel("Depth (µm) — front-junction zoom", fontsize=16)
    if show_ylabel:
        ax.set_ylabel("Energy (eV)", fontsize=16)
    ax.tick_params(labelsize=15)
    ax.grid(True, color="#dddddd", lw=0.6)
    ax.set_xlim(0, 2.0)
    ax.set_ylim(-1.4, 1.4)


def _intrinsic_params() -> dict:
    """Band profiles describe the device interior, before terminal parasitics."""
    return {**MODEL_PARAMS, "series_resistance": 0.0, "shunt_resistance": 0.0}


def _resolve_bias(value: str, params: dict) -> float:
    if value == "near-voc":
        voltage = np.linspace(0.0, 0.72, 37)
        v_sim, j_sim = run_simulation(params=params, voltages=voltage)
        voc = solar_metrics(v_sim, j_sim)["Voc"]
        if not np.isfinite(voc):
            raise SystemExit("The voltage sweep did not cross Voc; cannot select near-voc bias")
        bias = 0.98 * float(voc)
        print(f"[NOTE] Resolved near-voc bias to {bias:.4f} V (0.98 × Voc)")
        return bias
    try:
        bias = float(value)
    except ValueError as exc:
        raise SystemExit("--bias must be a voltage in V or 'near-voc'") from exc
    if not np.isfinite(bias):
        raise SystemExit("--bias must be finite")
    return bias


def main() -> None:
    ap = argparse.ArgumentParser(description="Band diagram: equilibrium versus illumination")
    ap.add_argument(
        "--bias", default="0.0",
        help="Illuminated junction bias in V, or 'near-voc' (default: 0.0)",
    )
    ap.add_argument("--out", default="results/band.png", help="Output PNG path")
    args = ap.parse_args()

    params = _intrinsic_params()
    p = check_params(params)
    bias = _resolve_bias(args.bias, params)
    d = profiles(p, bias=bias)
    x = d["x"] * 1e4
    junction = p.emitter_depth * 1e4

    Ec_eq, Ev_eq, _, _ = band_edges(d["potential"], d["electrons"], d["holes"], T=p.temperature)
    Ec_i, Ev_i, Efn_i, Efp_i = band_edges(
        d["ill_potential"], d["ill_electrons"], d["ill_holes"], T=p.temperature)


    i_p = int(np.argmin(np.abs(x - 0.1)))
    i_n = int(np.argmin(np.abs(x - 1.8)))
    vbi = float(Ec_eq[i_p] - Ec_eq[i_n])


    sample_x = junction + 1.0
    i_mid = int(np.argmin(np.abs(x - sample_x)))
    delta_ef = float(Efn_i[i_mid] - Efp_i[i_mid])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.5), sharey=True)


    ax1.plot(x, Ec_eq, color=C_BLUE, lw=1.8, label="$E_c$")
    ax1.plot(x, Ev_eq, color=C_ORANGE, lw=1.8, label="$E_v$")
    ax1.plot(x, np.zeros_like(x), color=C_DARK, lw=1.2, ls="--", label="$E_F$")
    ax1.axvline(junction, color="k", ls=":", lw=1)

    y_top = Ec_eq[i_p]
    ax1.annotate("", xy=(1.8, Ec_eq[i_n]), xytext=(1.8, y_top),
                 arrowprops=dict(arrowstyle="<->", color=C_DARK, lw=1.2))
    ax1.text(1.86, (Ec_eq[i_n] + y_top) / 2, f"$qV_{{bi}}$={vbi:.2f} eV",
             fontsize=14.5, va="center")
    ax1.legend(fontsize=14, frameon=False, loc="lower right")
    _style(ax1, "Equilibrium: one flat Fermi level")


    ax2.plot(x, Ec_i, color=C_BLUE, lw=1.8, label="$E_c$")
    ax2.plot(x, Ev_i, color=C_ORANGE, lw=1.8, label="$E_v$")
    ax2.plot(x, Efn_i, color=C_BLUE, lw=1.2, ls="--", label="$E_{Fn}$")
    ax2.plot(x, Efp_i, color=C_ORANGE, lw=1.2, ls="--", label="$E_{Fp}$")
    ax2.axvline(junction, color="k", ls=":", lw=1)

    ax2.annotate("", xy=(sample_x, Efp_i[i_mid]), xytext=(sample_x, Efn_i[i_mid]),
                 arrowprops=dict(arrowstyle="<->", color=C_DARK, lw=1.2))
    ax2.text(sample_x + 0.06, (Efn_i[i_mid] + Efp_i[i_mid]) / 2,
             f"local $\\Delta E_F$={delta_ef:.2f} eV", fontsize=14.5, va="center")
    ax2.legend(fontsize=14, frameon=False, loc="upper right")
    if abs(bias) < 1e-12:
        state = "short circuit"
    elif args.bias == "near-voc":
        state = f"near open circuit ({bias:.3f} V)"
    else:
        state = f"applied bias ({bias:.3f} V)"
    _style(ax2, f"{state.capitalize()}:\nquasi-Fermi levels split", show_ylabel=False)

    fig.tight_layout()
    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {out}")
    print(f"Built-in potential V_bi = {vbi:.3f} V; quasi-Fermi splitting Delta_E_F = {delta_ef:.3f} eV")


if __name__ == "__main__":
    main()
