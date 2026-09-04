"""Record and visualize the calibration optimization trajectory."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
import lmfit

from model import run_simulation_terminal
from model.style import C_BLUE, C_ORANGE, C_GRAY
from config import MODEL_PARAMS, CALIBRATION
from .fit import (make_params, residual_vector, residual_denominator,
                  validate_iv_data, RESIDUAL_MODE)


def fit_with_trace(v_meas, j_meas, params=None,
                   method: str = "least_squares", max_nfev: int | None = None,
                   mode: str | None = None):
    """Fit a J-V curve while recording distinct optimizer states."""
    if params is None:
        params = make_params()
    v_meas, j_meas = validate_iv_data(v_meas, j_meas)
    varied = [n for n, p in params.items() if getattr(p, "vary", True)]
    if not varied:
        raise ValueError("At least one fit parameter must have vary=True")
    if max_nfev is not None and (
            isinstance(max_nfev, bool) or not isinstance(max_nfev, (int, np.integer))
            or max_nfev < 1):
        raise ValueError(f"max_nfev must be an integer >= 1; received {max_nfev!r}")
    mode = mode or RESIDUAL_MODE
    denom = residual_denominator(j_meas, mode)

    trace: list[dict] = []

    def residual(pars):
        base = dict(MODEL_PARAMS)
        base.update(pars.valuesdict())
        j_sim = run_simulation_terminal(params=base, voltages=v_meas, j_meas=j_meas)
        return residual_vector(j_sim, j_meas, mode)

    def iter_cb(pars, nfev, resid, *args, **kws):
        r = np.asarray(resid, dtype=float)


        pd = {k: float(f"{v:.5g}") for k, v in pars.valuesdict().items()}
        state = {
            "params": pd,
            "chisq": float(np.sum(r * r)),
            "j_sim": r * denom + j_meas,
        }
        if not trace or trace[-1]["params"] != state["params"]:
            trace.append(state)

    fit_kws = {}
    if max_nfev is not None:
        fit_kws["max_nfev"] = max_nfev
    if method == "least_squares" and CALIBRATION.get("diff_step") is not None:
        fit_kws["diff_step"] = CALIBRATION["diff_step"]
    result = lmfit.minimize(residual, params, method=method,
                            iter_cb=iter_cb, **fit_kws)
    if not trace:
        raise RuntimeError("The optimizer returned no trajectory frames")
    names = [n for n, p in result.params.items() if getattr(p, "vary", True)]
    return names, trace, result


def _chisq(trace) -> np.ndarray:
    return np.asarray([t["chisq"] for t in trace], dtype=float)


def _plot_param_trajectory(ax, trace, names, k=None):
    """Plot fitted-parameter values through a selected trace state."""
    N = len(trace)
    single = len(names) == 1
    display_names = {
        "photon_flux": "generation scale",
        "series_resistance": "series resistance",
        "electron_lifetime": "electron lifetime",
        "hole_lifetime": "hole lifetime",
        "front_srv": "front SRV",
        "back_srv": "back SRV",
    }
    for n in names:
        vals = np.asarray([t["params"][n] for t in trace], dtype=float)
        if not single:
            scale = abs(vals[0])
            if scale <= np.finfo(float).tiny:
                scale = max(float(np.max(np.abs(vals))), 1.0)
            vals = vals / scale
        seg = vals if k is None else vals[: k + 1]
        ax.plot(range(len(seg)), seg, "-o", ms=4, lw=1.8,
                label=display_names.get(n, n.replace("_", " ")))
    if single:
        reference = MODEL_PARAMS.get(names[0])
        if reference is not None:
            ax.axhline(float(reference), color=C_GRAY, ls="--", lw=1.0,
                       label="reference value")
        units = " (× baseline)" if names[0] == "photon_flux" else ""
        ax.set_ylabel(display_names.get(names[0], names[0].replace("_", " ")) + units)
        ax.set_title("Parameter convergence")
    else:
        ax.axhline(1.0, color=C_GRAY, ls="--", lw=1.0, label="initial value")
        ax.set_ylabel("parameter / initial value")
        ax.set_title("Normalized parameter trajectories")
    ax.set_xlim(0, N - 1)
    ax.set_xlabel("iteration")
    ax.legend(ncol=1 if single else 2, frameon=False)
    ax.grid(alpha=0.3)


def plot_optimization_trace(names, trace, v_meas, j_meas):
    """Plot the final trajectory in the same order used by the animation."""
    v_meas = np.asarray(v_meas, dtype=float)
    j_meas = np.asarray(j_meas, dtype=float)
    iters = np.arange(len(trace))
    chi = _chisq(trace)

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))


    ax = axes[0]
    idxs = sorted({0, len(trace) // 2, len(trace) - 1})
    for j, k in enumerate(idxs):
        ax.plot(
            v_meas,
            trace[k]["j_sim"] * 1e3,
            color=plt.cm.Blues(0.35 + 0.4 * j),
            lw=1.8,
            label=f"iteration {k}",
        )
    ax.scatter(
        v_meas,
        j_meas * 1e3,
        s=20,
        color=C_ORANGE,
        edgecolors="white",
        linewidths=0.35,
        zorder=3,
        label="reference data",
    )
    ax.axhline(0, color="#888888", lw=0.8)
    ax.set_xlim(float(v_meas.min()) - 0.01, float(v_meas.max()) + 0.01)
    ax.set_ylim(-8.0, max(32.0, 1.08 * float(j_meas.max() * 1e3)))
    ax.set_xlabel("Voltage (V)")
    ax.set_ylabel("Current density (mA/cm²)")
    ax.set_title("J–V approaches the reference")
    ax.legend(fontsize=13, frameon=False)
    ax.grid(alpha=0.3)

    ax = axes[1]
    ax.semilogy(iters, chi, "o-", color=C_BLUE, lw=1.5)
    ax.set_xlabel("iteration")
    ax.set_ylabel("Objective Σr²")
    ax.set_title("Objective drops rapidly")
    ax.grid(alpha=0.3)

    _plot_param_trajectory(axes[2], trace, names)

    fig.tight_layout()
    return fig


def _trace_layout(trace, v_meas, j_meas, names):
    """Calculate fixed plot limits shared by all animation frames."""
    chi = _chisq(trace)
    N = len(trace)
    _, j_max = float(j_meas.min() * 1e3), float(j_meas.max() * 1e3)

    vals = np.asarray([[t["params"][n] for t in trace] for n in names], dtype=float)
    if len(names) == 1:
        plotted = vals
    else:
        scales = np.abs(vals[:, 0])
        zero = scales <= np.finfo(float).tiny
        if np.any(zero):
            scales[zero] = np.maximum(np.max(np.abs(vals[zero]), axis=1), 1.0)
        plotted = vals / scales[:, None]
    p_lo, p_hi = float(plotted.min()), float(plotted.max())
    p_pad = 0.08 * (p_hi - p_lo) if p_hi != p_lo else 0.1

    chi_lo = max(float(chi.min()) * 0.5, 1e-12)
    return (chi, N,
            (float(v_meas.min()), float(v_meas.max())),
            (-8.0, max(32.0, 1.08 * j_max)),
            (chi_lo, float(chi.max()) * 2.0),
            (p_lo - p_pad, p_hi + p_pad))


def _draw_trace_frame(k, ax1, ax2, ax3, trace, names, v_meas, j_meas,
                      chi, N, x_lim, j_lim, chi_lim, p_lim):
    """Draw one optimization state into the three teaching panels."""
    snap = trace[k]


    ax1.plot(v_meas, snap["j_sim"] * 1e3, color=C_BLUE, lw=2.0, label="model")
    ax1.scatter(
        v_meas, j_meas * 1e3, s=18, color=C_ORANGE, zorder=3,
        label="reference data",
    )
    ax1.axhline(0, color="#888888", lw=0.8)
    ax1.set_xlim(*x_lim); ax1.set_ylim(*j_lim)
    ax1.set_xlabel("Voltage (V)"); ax1.set_ylabel("Current density (mA/cm²)")
    ax1.set_title(f"iteration {k}   objective = {snap['chisq']:.4f}")
    ax1.legend(loc="upper left", fontsize=13, ncol=2, frameon=False)
    ax1.grid(alpha=0.3)


    ptxt = "\n".join(f"{n} = {snap['params'][n]:.3g}" for n in names)
    ax1.text(0.5, 0.03, ptxt, transform=ax1.transAxes, va="bottom", ha="center",
             fontsize=13, family="monospace",
             bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#cccccc", lw=0.6))


    ax2.semilogy(range(N), chi, "-", color="#cccccc", lw=1.2)
    ax2.scatter([k], [snap["chisq"]], color=C_BLUE, zorder=3)
    ax2.set_xlim(0, N - 1); ax2.set_ylim(*chi_lim)
    ax2.set_xlabel("iteration"); ax2.set_ylabel("Objective  Σr²")
    ax2.set_title("Fit convergence")
    ax2.grid(alpha=0.3)


    _plot_param_trajectory(ax3, trace, names, k=k)
    ax3.set_ylim(*p_lim)


def trace_to_gif(trace, v_meas, j_meas, names=None,
                 hold: int = 3, dpi: int = 100, interval: int = 350) -> bytes:
    """Render an optimization trajectory as GIF bytes."""
    from model.animation import frames_to_gif

    if not trace:
        raise ValueError("trace must not be empty")
    if isinstance(hold, bool) or not isinstance(hold, int) or hold < 0:
        raise ValueError(f"hold must be a non-negative integer; received {hold!r}")
    v_meas = np.asarray(v_meas, dtype=float)
    j_meas = np.asarray(j_meas, dtype=float)
    if names is None:
        names = list(trace[0]["params"])
    chi, N, x_lim, j_lim, chi_lim, p_lim = _trace_layout(trace, v_meas, j_meas, names)
    frames = list(range(N)) + [N - 1] * hold

    def make_fig():
        fig, axes = plt.subplots(1, 3, figsize=(16, 4.8))
        fig.subplots_adjust(left=0.06, right=0.985, bottom=0.22, top=0.86, wspace=0.32)
        return fig, axes

    def draw(k, axes):
        _draw_trace_frame(k, *axes, trace, names, v_meas, j_meas,
                          chi, N, x_lim, j_lim, chi_lim, p_lim)

    return frames_to_gif(draw, frames, make_fig=make_fig, dpi=dpi, interval=interval)


def save_optimization_gif(trace, v_meas, j_meas, out_path,
                          names=None, hold: int = 3, dpi: int = 100,
                          interval: int = 350):
    """Render and save an optimization-trajectory GIF."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(trace_to_gif(trace, v_meas, j_meas, names=names,
                                      hold=hold, dpi=dpi, interval=interval))
    return out_path
