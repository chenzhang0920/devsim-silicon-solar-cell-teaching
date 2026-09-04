"""Create the overview schematic used in the teaching materials."""
from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

from config import MODEL_PARAMS, MODELED_INPUT_POWER_W_CM2
from . import run_simulation, profiles, SolarCellParams, check_params
from .analysis import band_edges, solar_metrics
from .style import C_BLUE, C_ORANGE, C_GREEN, C_DARK


def _sci_latex(value: float) -> str:
    """Format a positive scalar as compact LaTeX scientific notation."""
    exponent = int(math.floor(math.log10(value)))
    coefficient = value / 10**exponent
    if math.isclose(coefficient, 1.0, rel_tol=1e-9):
        return f"10^{{{exponent}}}"
    return f"{coefficient:.2g}\\times10^{{{exponent}}}"


def _draw_device(ax: plt.Axes, p: SolarCellParams) -> None:
    """Draw the front-illuminated p+-on-n layer stack."""
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 13.4)
    ax.axis("off")

    left, width = 2.4, 5.2
    right = left + width
    ax.add_patch(Rectangle((left, 11.2), width, 0.7, fc="#444444", ec="k"))
    ax.text(5.0, 11.55, "ideal front contact", ha="center", va="center",
            fontsize=11.5, color="white")
    ax.add_patch(Rectangle((left, 0.1), width, 0.7, fc="#444444", ec="k"))
    ax.text(5.0, 0.45, "ideal rear contact", ha="center", va="center",
            fontsize=11.5, color="white")

    junction_y = 9.9
    ax.add_patch(Rectangle((left, junction_y), width, 11.2 - junction_y,
                           fc="#fdae6b", ec="k"))
    na_label = _sci_latex(p.emitter_doping)
    nd_label = _sci_latex(p.base_doping)
    ax.text(5.0, 10.55, f"p$^+$ emitter   $N_A={na_label}$ cm$^{{-3}}$",
            ha="center", va="center", fontsize=11.2)

    ax.add_patch(Rectangle((left, 0.8), width, junction_y - 0.8,
                           fc="#9ecae1", ec="k"))
    ax.text(5.0, 5.0, f"n-type base\n$N_D={nd_label}$ cm$^{{-3}}$\n\n"
            "SRH + Auger\nbulk recombination",
            ha="center", va="center", fontsize=11.2)

    # The space-charge region is not a third material layer. It straddles the
    # metallurgical junction and lies mostly in the lower-doped n-type base.
    depletion_bottom = 9.05
    depletion_top = 10.03
    ax.add_patch(Rectangle(
        (left, depletion_bottom), width, depletion_top - depletion_bottom,
        fc="white", ec=C_DARK, alpha=0.70, hatch="///", lw=1.0,
    ))
    ax.text(
        5.0, 9.48,
        "space-charge region\n(spans junction; mostly in n base)",
        ha="center", va="center", fontsize=10.8,
        bbox=dict(boxstyle="round,pad=0.14", fc="white", ec="none", alpha=0.82),
    )

    ax.plot([left, right], [junction_y, junction_y], ls="--", color="k", lw=1.2)
    ax.text(7.78, junction_y, "metallurgical junction", fontsize=10.8, va="center")

    for x0 in (3.7, 5.0, 6.3):
        ax.annotate("", xy=(x0, 11.95), xytext=(x0, 12.55),
                    arrowprops=dict(arrowstyle="->", color="gold", lw=2.2))
    ax.text(5.0, 12.72, "AM1.5-like teaching input · shading omitted", ha="center", fontsize=10.8,
            color="darkgoldenrod")

    ax.annotate("", xy=(1.55, 11.0), xytext=(1.55, 7.0),
                arrowprops=dict(arrowstyle="->", color=C_ORANGE, lw=2))
    ax.text(0.95, 9.0, "h$^+$", fontsize=12, color=C_ORANGE, ha="center")
    ax.annotate("", xy=(1.55, 1.2), xytext=(1.55, 5.0),
                arrowprops=dict(arrowstyle="->", color=C_BLUE, lw=2))
    ax.text(0.95, 3.0, "e$^-$", fontsize=12, color=C_BLUE, ha="center")

    depth_um = p.thickness * 1e4
    ax.annotate("", xy=(8.9, 1.0), xytext=(8.9, 11.0),
                arrowprops=dict(arrowstyle="<->", color=C_DARK, lw=1.4))
    ax.text(9.35, 6.0, "depth x", fontsize=11.5, va="center", rotation=90, color=C_DARK)
    ax.text(8.9, 11.25, "0", fontsize=11, ha="center", color=C_DARK)
    ax.text(8.9, 0.60, f"{depth_um:.0f} µm", fontsize=11, ha="center", color=C_DARK)

    ax.set_title("① $p^+$-on-n structure\n(not to scale)", fontsize=15, pad=8)


def _draw_band(ax: plt.Axes, d: dict, p: SolarCellParams, bias: float) -> None:
    """Draw equilibrium and illuminated bands near the front junction."""
    x = d["x"] * 1e4
    Ec_eq, Ev_eq, _, _ = band_edges(d["potential"], d["electrons"], d["holes"], T=p.temperature)
    Ec_i, Ev_i, Efn_i, Efp_i = band_edges(d["ill_potential"], d["ill_electrons"], d["ill_holes"], T=p.temperature)

    ax.plot(x, Ec_eq, color=C_BLUE, lw=1.6, label="$E_c$ (equil.)")
    ax.plot(x, Ev_eq, color=C_ORANGE, lw=1.6, label="$E_v$ (equil.)")
    ax.plot(x, Ec_i, color=C_BLUE, lw=1.4, ls="--", label="$E_c$ (illum.)")
    ax.plot(x, Ev_i, color=C_ORANGE, lw=1.4, ls="--", label="$E_v$ (illum.)")
    ax.plot(x, Efn_i, color=C_BLUE, lw=1.2, ls=":", label="$E_{Fn}$")
    ax.plot(x, Efp_i, color=C_ORANGE, lw=1.2, ls=":", label="$E_{Fp}$")
    ax.axvline(p.emitter_depth * 1e4, color="k", ls=":", lw=0.8)
    ax.set_xlim(0, 2)
    ax.set_ylim(-1.4, 1.4)
    ax.set_xlabel("x (µm)")
    ax.set_ylabel("Energy (eV)")
    ax.set_title(f"② Bands near open circuit\n({bias:.3f} V, solved)",
                 fontsize=15, pad=8)
    ax.legend(
        fontsize=11,
        frameon=True,
        facecolor="white",
        framealpha=0.9,
        loc="center right",
    )
    ax.grid(alpha=0.3)


def _draw_iv(ax: plt.Axes, V, J, pin: float) -> None:
    """Draw the terminal J-V curve and its standard operating points."""
    m = solar_metrics(V, J, pin=pin)
    J_mA = J * 1e3  # mA/cm^2

    ax.plot(V, J_mA, color=C_BLUE, lw=2)
    power_mask = (V >= 0.0) & (V <= m["Voc"]) & (J_mA >= 0.0)
    ax.fill_between(V[power_mask], 0.0, J_mA[power_mask], color=C_BLUE, alpha=0.10)
    ax.axhline(0, color="#888888", lw=0.8)
    ax.scatter([0], [m["Jsc"] * 1e3], color=C_BLUE, zorder=3)
    ax.scatter([m["Voc"]], [0], color=C_BLUE, zorder=3)
    ax.scatter([m["Vmp"]], [m["Jmp"] * 1e3], color=C_GREEN, marker="D", zorder=4)
    ax.set_xlabel("Voltage V (V)")
    ax.set_ylabel("J (mA/cm²)")
    ax.set_title("③ Simulated J–V curve and\nmaximum-power point", fontsize=15, pad=8)
    ax.set_ylim(-5.0, 32.0)
    ax.grid(alpha=0.3)
    text = (f"$J_{{sc}}$ = {m['Jsc']*1e3:.2f} mA/cm²\n"
            f"$V_{{oc}}$ = {m['Voc']:.3f} V\n"
            f"FF = {m['FF']:.3f}\n"
            f"η$_{{model}}$ = {m['eta']*100:.1f}%")
    ax.text(0.03, 0.03, text, transform=ax.transAxes, fontsize=11.5, va="bottom",
            ha="left", family="monospace",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#cccccc", lw=0.8))


def _draw_workflow(ax: plt.Axes) -> None:
    """Draw the compact simulation-to-calibration workflow."""
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 3)
    ax.axis("off")

    steps = [
        ("Structure", "p⁺/n doping\ngeometry"),
        ("Mesh", "discretize into\nnodes / edges"),
        ("Equations", "Poisson +\ndrift-diffusion"),
        ("Solve", "Newton\niteration"),
        ("Extract", "J-V / bands\ncarriers"),
        ("Calibrate", "estimate effective\nparameters"),
    ]
    w = 1.7
    gap = 0.2
    x0 = 0.4
    for i, (title, sub) in enumerate(steps):
        x = x0 + i * (w + gap)
        ax.add_patch(Rectangle((x, 0.8), w, 1.4, fc="#eef3f8", ec=C_BLUE, lw=1.2))
        ax.text(x + w / 2, 1.9, title, ha="center", va="center", fontsize=12, fontweight="bold")
        ax.text(x + w / 2, 1.1, sub, ha="center", va="center", fontsize=11.2, color=C_DARK)
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + w + 0.18, 1.5), xytext=(x + w + 0.02, 1.5),
                        arrowprops=dict(arrowstyle="->", color="#888888", lw=1.6))
    ax.set_title("④ Simulation workflow", fontsize=15)


def draw_model_overview() -> plt.Figure:
    """Return the four-panel model overview used throughout the lesson."""
    p = check_params({**MODEL_PARAMS, "series_resistance": 0.0,
                      "shunt_resistance": 0.0})
    V, J = run_simulation(params=dict(vars(p)))
    metrics = solar_metrics(V, J)
    if not np.isfinite(metrics["Voc"]):
        raise RuntimeError(
            "The default voltage sweep does not cross Voc, so the near-open-circuit "
            "overview cannot be generated"
        )
    bias = 0.98 * metrics["Voc"]
    d = profiles(p, bias=bias)

    fig = plt.figure(figsize=(16, 9.2))
    gs = fig.add_gridspec(
        2, 3, height_ratios=[2.2, 1], width_ratios=[1.0, 1.18, 1.08],
        hspace=0.42, wspace=0.32,
    )

    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])
    ax3 = fig.add_subplot(gs[0, 2])
    ax4 = fig.add_subplot(gs[1, :])

    _draw_device(ax1, p)
    _draw_band(ax2, d, p, bias)
    _draw_iv(ax3, V, J, pin=MODELED_INPUT_POWER_W_CM2 * p.photon_flux)
    _draw_workflow(ax4)

    fig.suptitle(
        "From a $p^+$-on-n junction to a simulated J–V curve",
        fontsize=18,
        y=0.99,
    )
    fig.subplots_adjust(left=0.035, right=0.985, bottom=0.035, top=0.89)
    return fig
