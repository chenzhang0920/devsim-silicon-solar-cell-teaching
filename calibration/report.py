"""Calibration diagnostics, uncertainty checks, and report plots."""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import lmfit

from model import terminal_iv
from model.analysis import solar_metrics
from model.style import C_BLUE, C_GREEN, C_ORANGE, C_YELLOW, C_GRAY


def comparison_figure(
    v_meas: np.ndarray,
    j_meas: np.ndarray,
    fitted_params: dict,
    data_label: str = "measured data",
) -> tuple[plt.Figure, dict]:
    """Plot a fitted terminal J-V curve and pointwise current residuals."""
    v_meas = np.asarray(v_meas, dtype=float)
    j_meas = np.asarray(j_meas, dtype=float)


    # A large Rs stretches the terminal-voltage axis.  Use a dense junction
    # sweep and a small margin so sparse measured points are always covered.
    v_term, j_term = terminal_iv(
        fitted_params,
        n=max(240, 16 * v_meas.size),
        v_max=max(0.80, float(v_meas.max()) + 0.08),
    )


    # Pmax is determined by the J-V curve alone. Efficiency is intentionally
    # omitted here because a fitted effective light scale is not an independent
    # measurement of the incident irradiance at the cell plane.
    m_meas = solar_metrics(v_meas, j_meas, pin=None)
    m_sim = solar_metrics(v_term, j_term, pin=None)
    compare = {"meas": m_meas, "sim": m_sim}


    if v_term.size < 2 or v_meas.min() < v_term.min() or v_meas.max() > v_term.max():
        raise ValueError(
            "The self-consistent terminal J-V curve does not cover all measured voltages; "
            "extend the terminal_iv junction-voltage range")
    j_sim = np.interp(v_meas, v_term, j_term)
    resid = (j_sim - j_meas) * 1e3          # A/cm^2 -> mA/cm^2
    j_term_mA = j_term * 1e3
    j_meas_mA = j_meas * 1e3

    fig, (ax1, ax2) = plt.subplots(
        2, 1, figsize=(9.2, 7.5), sharex=True, constrained_layout=True,
        gridspec_kw={"height_ratios": [2.1, 1.0]},
    )


    plot_mask = v_term <= float(v_meas.max()) + 1e-12
    ax1.plot(v_term[plot_mask], j_term_mA[plot_mask], color=C_BLUE, lw=2.2,
             label="fitted model")
    ax1.scatter(v_meas, j_meas_mA, color=C_ORANGE, s=28, zorder=3,
                label=data_label)
    ax1.axhline(0.0, color=C_GRAY, lw=0.9)
    ax1.set_ylabel("J (mA/cm²)")
    ax1.set_title(f"Fit to the {data_label} J–V curve")
    ax1.legend(frameon=False, loc="upper right")

    text = (f"Jsc data {m_meas['Jsc'] * 1e3:6.2f}  sim {m_sim['Jsc'] * 1e3:6.2f} mA/cm²\n"
            f"Voc data {m_meas['Voc']:6.3f}  sim {m_sim['Voc']:6.3f} V\n"
            f"FF  data {m_meas['FF']:6.3f}  sim {m_sim['FF']:6.3f}\n"
            f"Pmax data {m_meas['Pmax'] * 1e3:6.2f}  sim {m_sim['Pmax'] * 1e3:6.2f} mW/cm²")
    ax1.text(0.02, 0.04, text, transform=ax1.transAxes, fontsize=11.5,
             va="bottom", ha="left", family="monospace",
             bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="#cccccc", lw=0.8))
    y_top = 1.10 * max(float(m_meas["Jsc"]), float(m_sim["Jsc"])) * 1e3
    ax1.set_ylim(-8.0, max(32.0, y_top))
    ax1.set_xlim(float(v_meas.min()) - 0.01, float(v_meas.max()) + 0.01)


    ax2.scatter(v_meas, resid, color=C_ORANGE, s=24, zorder=3)
    ax2.axhline(0.0, color=C_GRAY, lw=0.9)
    ax2.set_xlabel("Voltage V (V)")
    ax2.set_ylabel("Model − data (mA/cm²)")
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    ax2.set_title(f"Residuals: RMSE = {rmse:.2f} mA/cm²")
    resid_lim = max(1.0, 1.15 * float(np.max(np.abs(resid))))
    ax2.set_ylim(-resid_lim, resid_lim)
    ax2.grid(True)

    ax1.grid(True)
    return fig, compare


def joint_comparison_figure(data, fitted_params: dict) -> plt.Figure:
    """Plot the light and dark J-V data used by a joint calibration.

    The independent short-circuit and Voc observations are shown as markers,
    making it clear which measurements constrain which part of the model.
    ``data`` is duck-typed to keep this reporting module independent from the
    calibration loader at import time.
    """
    light_v = np.asarray(data.light_v, dtype=float)
    light_j = np.asarray(data.light_j, dtype=float)
    dark_v = np.asarray(data.dark_v, dtype=float)
    dark_j = np.asarray(data.dark_j, dtype=float)
    v_light, j_light = terminal_iv(fitted_params, n=260, v_max=0.84)
    dark_params = dict(fitted_params)
    dark_params["photon_flux"] = 0.0
    v_dark, j_dark = terminal_iv(dark_params, n=260, v_max=0.84)

    fig, axes = plt.subplots(1, 2, figsize=(11.8, 5.2), sharey=False,
                             constrained_layout=True)
    ax = axes[0]
    ax.plot(v_light, j_light * 1e3, color=C_BLUE, label="joint model")
    ax.scatter(light_v, light_j * 1e3, color=C_ORANGE, s=30,
               label="light data", zorder=3)
    ax.scatter([data.light_ishort["V_mean_V"]],
               [data.light_ishort["J_mean_A_cm2"] * 1e3],
               color=C_GREEN, marker="D", s=45, label="$J_{sc}$ check", zorder=4)
    ax.axvline(data.light_voc, color=C_YELLOW, ls="--", lw=1.5,
               label=f"$V_{{oc}}$ = {data.light_voc:.3f} V")
    ax.axhline(0.0, color=C_GRAY, lw=0.9)
    ax.set_title(f"Cell #{data.sample}: illuminated J–V", fontsize=18)
    ax.set_xlabel("Terminal voltage V (V)", fontsize=16)
    ax.set_ylabel("J (mA/cm²)", fontsize=16)
    ax.legend(frameon=False, loc="best", fontsize=14)

    ax = axes[1]
    ax.plot(v_dark, j_dark * 1e3, color=C_BLUE, label="dark model")
    ax.scatter(dark_v, dark_j * 1e3, color=C_ORANGE, s=30,
               label="dark data", zorder=3)
    ax.axhline(0.0, color=C_GRAY, lw=0.9)
    ax.set_yscale("symlog", linthresh=0.1, linscale=1.0)
    ax.set_title("Dark J–V (symmetric-log scale)", fontsize=18)
    ax.set_xlabel("Terminal voltage V (V)", fontsize=16)
    ax.set_ylabel("J (mA/cm²)", fontsize=16)
    ax.legend(frameon=False, loc="best", fontsize=14)
    diagnostic_lines = []
    if data.dark_open_circuit_offset is not None:
        diagnostic_lines.append(
            f"zero-current offset: {data.dark_open_circuit_offset:.3f} V"
        )
    if data.dark_ishort is not None:
        diagnostic_lines.append(
            f"J near 0 V: {data.dark_ishort['J_mean_A_cm2'] * 1e3:.3f} mA/cm²"
        )
    if diagnostic_lines:
        ax.text(
            0.03, 0.96,
            "\n".join(diagnostic_lines),
            transform=ax.transAxes, fontsize=14.5, va="top",
            bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#cccccc", lw=0.8),
        )
    for axis in axes:
        axis.tick_params(labelsize=15)
        axis.grid(True)
    return fig


def physical_warnings(params: lmfit.Parameters) -> list[str]:
    """Return plain-language warnings for suspicious fitted values."""
    warns: list[str] = []
    for name, p in params.items():
        if not getattr(p, "vary", True):
            continue
        val = float(p.value)

        if p.min is not None and val <= p.min * (1 + 1e-3):
            warns.append(f"{name} reached its lower bound {p.min:.3g} and may be poorly constrained")
        if p.max is not None and val >= p.max * (1 - 1e-3):
            warns.append(f"{name} reached its upper bound {p.max:.3g} and may be poorly constrained")

        stderr = getattr(p, "stderr", None)
        if stderr is not None and abs(val) > 0:
            rel = stderr / abs(val)
            if rel > 1.0:
                warns.append(
                    f"{name} has {rel:.0%} relative uncertainty "
                    "(insensitive or not reliably identified)"
                )
            elif rel > 0.5:
                warns.append(f"{name} has {rel:.0%} relative uncertainty (weakly constrained)")

        if "lifetime" in name and val > 0.1:
            warns.append(
                f"{name}={val:.3g} s is far above the teaching baseline; "
                "check units, missing physics, and identifiability")
        if "srv" in name and val > 1e7:
            warns.append(f"{name}={val:.3g} cm/s is unusually high (near an unpassivated metal surface)")
        if "doping" in name and not (1e12 <= val <= 1e21):
            warns.append(f"{name}={val:.3g} cm^-3 is outside the typical doping range")

    return warns


def _varied_names(params: lmfit.Parameters, var_names=None) -> list[str]:
    """Return covariance-order parameter names."""
    if var_names is not None:
        return list(var_names)
    return [n for n, p in params.items() if getattr(p, "vary", True)]


def correlation_from_covar(covar) -> np.ndarray:
    """Convert a covariance matrix to a correlation matrix."""
    covar = np.asarray(covar, dtype=float)
    if covar.ndim != 2 or covar.shape[0] != covar.shape[1]:
        raise ValueError("covar must be a square matrix")
    if not np.all(np.isfinite(covar)) or np.any(np.diag(covar) < 0):
        raise ValueError("covar must be finite with a non-negative diagonal")
    d = np.sqrt(np.diag(covar))
    with np.errstate(divide="ignore", invalid="ignore"):
        return covar / np.outer(d, d)


_STRONG_CORR = 0.8


def _identifiability_data(params: lmfit.Parameters, covar=None, var_names=None):
    """Assemble uncertainties, correlations, and trade-off flags."""
    names = _varied_names(params, var_names)

    rels = []
    for n in names:
        p = params[n]
        stderr = getattr(p, "stderr", None)
        rel = (stderr / abs(p.value)) if (stderr is not None and abs(p.value) > 0) else np.nan
        rels.append(rel)
    rels = np.asarray(rels, dtype=float)

    corr = None
    if covar is not None and len(names) > 1:
        corr = correlation_from_covar(covar)
        if corr.shape != (len(names), len(names)):
            raise ValueError(
                f"covar shape {corr.shape} does not match {len(names)} fitted parameters")

    strongly_correlated = set()
    if corr is not None:
        for i in range(len(names)):
            for j in range(len(names)):
                if i != j and abs(corr[i, j]) > _STRONG_CORR:
                    strongly_correlated.add(names[i])
    return names, rels, corr, strongly_correlated


def identifiability_figure(
    params: lmfit.Parameters,
    covar=None,
    var_names=None,
    context: str = "selected observations",
    quality_note: str | None = None,
) -> plt.Figure:
    """Visualize local relative uncertainty and fitted-parameter correlation."""
    names, rels, corr, strongly_correlated = _identifiability_data(params, covar, var_names)


    fig = plt.figure(figsize=(11.8, 5.1), constrained_layout=True)
    grid = fig.add_gridspec(
        1, 2, width_ratios=(1.12, 1.0),
    )
    ax1 = fig.add_subplot(grid[0])
    ax2 = fig.add_subplot(grid[1])
    title_prefix = "Local covariance sensitivity" if quality_note else "Local identifiability"
    title = f"{title_prefix} — {context}"
    if quality_note:
        title += f"\n{quality_note}"
    fig.suptitle(
        title,
        fontsize=18,
        fontweight="bold",
        color=C_ORANGE if quality_note else "black",
    )


    colors = []
    for n, r in zip(names, rels):
        if np.isnan(r):
            colors.append("#999999")
        elif quality_note:
            # A small local covariance must not be encoded as a green physical
            # pass when the model-data adequacy gate has already failed.
            colors.append(C_YELLOW)
        elif r >= 1.0:
            colors.append(C_ORANGE)
        elif r < 0.3 and n not in strongly_correlated:
            colors.append(C_GREEN)
        else:
            colors.append(C_YELLOW)
    ypos = np.arange(len(names))[::-1]
    finite_rels = rels[np.isfinite(rels) & (rels > 0)]
    x_min = min(0.1, max(1e-4, float(finite_rels.min()) / 2)) \
        if finite_rels.size else 1e-3
    x_max = max(2.0, float(finite_rels.max()) * 1.35) if finite_rels.size else 2.0
    ax1.axvspan(x_min, 0.3, color=C_GREEN, alpha=0.07, zorder=0)
    ax1.axvspan(0.3, 1.0, color=C_YELLOW, alpha=0.08, zorder=0)
    ax1.axvspan(1.0, x_max, color=C_ORANGE, alpha=0.06, zorder=0)
    ax1.barh(ypos, rels, color=colors, zorder=2)
    ax1.axvline(0.3, color="#888888", ls="--", lw=0.8)
    ax1.axvline(1.0, color="#888888", ls=":", lw=0.8)
    ax1.set_yticks(ypos)
    display_names = {
        "photon_flux": "Flux scale",
        "series_resistance": "Series R",
        "electron_lifetime": "Electron lifetime",
        "hole_lifetime": "Hole lifetime",
        "front_srv": "Front SRV",
        "back_srv": "Back SRV",
    }
    labels = [display_names.get(n, n.replace("_", " ")) for n in names]
    ax1.set_yticklabels(labels)
    ax1.set_xscale("log")
    ax1.set_xlim(x_min, x_max)
    ax1.set_xlabel("Relative uncertainty  σ / |fitted value|", fontsize=16)
    ax1.set_title("Relative parameter uncertainty", fontsize=18)
    ax1.tick_params(labelsize=15)
    ax1.grid(True, axis="x")
    for n, y, r in zip(names, ypos, rels):
        if np.isnan(r):
            ax1.text(x_min * 1.05, y, " no stderr", va="center", fontsize=14,
                     color="#999999")
        else:
            mark = " *" if n in strongly_correlated else ""
            ax1.text(r, y, f" {r:.1%}{mark}", va="center", fontsize=14)


    if corr is not None:
        im = ax2.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
        ax2.set_xticks(range(len(names)))
        ax2.set_yticks(range(len(names)))
        ax2.set_xticklabels(labels, rotation=35, ha="right")
        ax2.set_yticklabels(labels)
        ax2.tick_params(labelsize=15)
        for i in range(len(names)):
            for j in range(len(names)):
                ax2.text(j, i, f"{corr[i, j]:.2f}", ha="center", va="center",
                         fontsize=14, color="k")
        colorbar = fig.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
        colorbar.set_label("correlation", fontsize=16)
        colorbar.ax.tick_params(labelsize=15)
        ax2.set_title("Fitted-parameter correlation", fontsize=18)
    else:
        ax2.axis("off")
        ax2.text(0.5, 0.5, "(need ≥2 varied parameters\nand covariance)",
                 ha="center", va="center", fontsize=14, color="gray")

    return fig


def identifiability_summary(params: lmfit.Parameters,
                            covar=None, var_names=None,
                            quality_adequate: bool = True) -> list[str]:
    """Summarize local uncertainty and parameter trade-offs in text.

    ``quality_adequate=False`` prevents a small local covariance from being
    described as physical identifiability after the model-data quality gate has
    failed.  The covariance is still useful as a numerical sensitivity check.
    """
    names, rels, corr, strongly_correlated = _identifiability_data(
        params, covar, var_names
    )

    lines = []
    for n, rel in zip(names, rels):
        if np.isnan(rel):
            lines.append(f"{n}: no uncertainty estimate (not varied or fit failed)")
            continue
        if not quality_adequate:
            verdict = "local numerical sensitivity only (quality gate failed)"
        elif n in strongly_correlated:
            verdict = "not separately identifiable (strong correlation)"
        elif rel < 0.3:
            verdict = "locally identifiable"
        elif rel < 1.0:
            verdict = "weakly constrained"
        else:
            verdict = "not reliably identified"

        # Keep terminal summaries ASCII so they render reliably in Windows
        # PowerShell/CMD as well as UTF-8 terminals.
        lines.append(f"{n}: stderr/abs(value) = {rel:.2%} -> {verdict}")

    if corr is not None:
        strong = [(names[i], names[j], corr[i, j])
                  for i in range(len(names)) for j in range(i + 1, len(names))
                  if abs(corr[i, j]) > _STRONG_CORR]
        for a, b, c in strong:
            lines.append(f"WARNING: {a} and {b} are strongly correlated (rho={c:+.2f}) and cannot be separated")

    return lines
