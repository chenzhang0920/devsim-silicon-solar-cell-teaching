"""Plot four complementary spatial profiles of the silicon solar cell."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import MODEL_PARAMS
from model import check_params, profiles, run_simulation
from model.analysis import solar_metrics
from model.style import C_BLUE, C_DARK, C_ORANGE


def _style(
    ax: plt.Axes,
    title: str,
    xlabel: str = "Depth (µm)",
    ylabel: str = "",
) -> None:
    ax.set_title(title, fontsize=18, pad=7)
    ax.set_xlabel(xlabel, fontsize=17)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=17)
    ax.tick_params(labelsize=15)
    ax.grid(True)


def _intrinsic_params() -> dict:
    """Profiles describe the device interior, before lumped terminal parasitics."""
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
    parser = argparse.ArgumentParser(description="Plot solar-cell physical profiles")
    parser.add_argument("--out", default="results/profiles.png", help="Output PNG path")
    parser.add_argument(
        "--bias",
        default="0.0",
        help="Illuminated junction bias in V, or 'near-voc' (default: 0.0)",
    )
    args = parser.parse_args()

    params = _intrinsic_params()
    p = check_params(params)
    bias = _resolve_bias(args.bias, params)
    if abs(bias) < 1e-12:
        state = "short circuit"
    elif args.bias == "near-voc":
        state = f"near $V_{{oc}}$ ({bias:.3f} V)"
    else:
        state = f"at {bias:.3f} V"
    data = profiles(p, bias=bias)
    x_um = data["x"] * 1e4
    junction_um = p.emitter_depth * 1e4
    field_x_um = data["field_x"] * 1e4
    equilibrium_field = data["electric_field"]
    illuminated_field = data["ill_electric_field"]

    fig, axes = plt.subplots(
        2, 2, figsize=(13.2, 7.2), constrained_layout=True,
    )

    ax = axes[0, 0]
    donors = np.where(data["donors"] > 0, data["donors"], np.nan)
    acceptors = np.where(data["acceptors"] > 0, data["acceptors"], np.nan)
    ax.semilogy(x_um, acceptors, color=C_ORANGE, label="Acceptors $N_A$")
    ax.semilogy(x_um, donors, color=C_BLUE, label="Donors $N_D$")
    ax.axvline(junction_um, color=C_DARK, ls=":", lw=1.2, label="junction")
    ax.set_xlim(0, 2.0)
    ax.set_ylim(1e15, 2e19)
    ax.legend(frameon=False, loc="center right", fontsize=15)
    _style(
        ax, "$p^+$ emitter / n-type base",
        xlabel="Depth (µm) — junction zoom", ylabel="Doping (cm$^{-3}$)",
    )

    ax = axes[0, 1]
    ax.plot(
        field_x_um, equilibrium_field / 1e3, color=C_BLUE, ls=":",
        label="equilibrium",
    )
    ax.plot(
        field_x_um, illuminated_field / 1e3, color=C_ORANGE,
        label=f"near $V_{{oc}}$, {bias:.3f} V" if args.bias == "near-voc"
        else f"illuminated, {bias:.3f} V",
    )
    ax.axhline(0, color=C_DARK, lw=0.8)
    ax.axvline(junction_um, color=C_DARK, ls=":", lw=1.2)
    ax.set_xlim(0, 2.0)
    peak = max(
        float(np.max(np.abs(equilibrium_field / 1e3))),
        float(np.max(np.abs(illuminated_field / 1e3))),
        1.0,
    )
    ax.set_ylim(-1.1 * peak, 1.1 * peak)
    ax.legend(frameon=False, loc="lower right", fontsize=15)
    _style(
        ax, "Electric field near the junction",
        xlabel="Depth (µm) — junction zoom", ylabel="Field (kV/cm)",
    )

    ax = axes[1, 0]
    ax.semilogy(x_um, data["electrons"], color=C_BLUE, ls=":", label="n eq.")
    ax.semilogy(x_um, data["holes"], color=C_ORANGE, ls=":", label="p eq.")
    ax.semilogy(x_um, data["ill_electrons"], color=C_BLUE, label="n light")
    ax.semilogy(x_um, data["ill_holes"], color=C_ORANGE, label="p light")
    ax.axvline(junction_um, color=C_DARK, ls=":", lw=1.2)
    ax.set_xlim(0, p.thickness * 1e4)
    ax.set_ylim(1e2, 1e21)
    ax.legend(frameon=False, ncol=2, loc="upper right", fontsize=15)
    _style(
        ax, f"Carrier profiles: equilibrium vs {state}",
        xlabel="Depth (µm) — full device", ylabel="Carrier density (cm$^{-3}$)",
    )

    ax = axes[1, 1]
    ax.semilogy(x_um, data["generation"], color=C_BLUE)
    ax.axvline(junction_um, color=C_DARK, ls=":", lw=1.2)
    ax.set_xlim(0, p.thickness * 1e4)
    positive = data["generation"][data["generation"] > 0]
    if positive.size:
        ax.set_ylim(max(float(positive.min()) * 0.5, 1e8), float(positive.max()) * 2.0)
    _style(
        ax,
        f"Photogeneration across the full device",
        xlabel="Depth (µm) — full device",
        ylabel="Generation (cm$^{-3}$ s$^{-1}$)",
    )

    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {out}")


if __name__ == "__main__":
    main()
