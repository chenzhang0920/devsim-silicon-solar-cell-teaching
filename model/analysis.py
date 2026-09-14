"""Post-processing utilities for solar-cell simulation results."""
from __future__ import annotations

import numpy as np


EG = 1.12
NI = 1e10


_KB = 8.617333262e-5


def _varshni(T: float) -> float:
    """Return the temperature-dependent Varshni correction in eV."""
    return 4.9e-4 * T * T / (T + 655.0)


def silicon_eg_ev(T: float = 300.0) -> float:
    """Return the silicon band gap in eV."""
    return float(EG + _varshni(300.0) - _varshni(T))


def intrinsic_ni(T: float = 300.0) -> float:
    """Estimate intrinsic carrier concentration in cm⁻³."""
    eg = silicon_eg_ev(T)
    eg300 = silicon_eg_ev(300.0)
    kT = _KB * T
    kT300 = _KB * 300.0
    return float(NI * (T / 300.0) ** 1.5 * np.exp(eg300 / (2 * kT300) - eg / (2 * kT)))


def thermal_voltage(T: float = 300.0) -> float:
    """Return thermal voltage kT/q in volts."""
    return float(_KB * T)


def band_edges(psi, n, p, T: float = 300.0):
    """Calculate band edges and quasi-Fermi levels from a device solution."""
    psi = np.asarray(psi, dtype=float)
    n = np.asarray(n, dtype=float)
    p = np.asarray(p, dtype=float)
    eg = silicon_eg_ev(T)
    ni = intrinsic_ni(T)
    vt = thermal_voltage(T)
    Ec = -psi + eg / 2
    Ev = -psi - eg / 2
    Efn = -psi + vt * np.log(np.maximum(n, 1e-3) / ni)
    Efp = -psi - vt * np.log(np.maximum(p, 1e-3) / ni)
    return Ec, Ev, Efn, Efp


def voc_zero_crossing(V, J) -> float:
    """Interpolate the first positive-to-negative current crossing at V >= 0."""
    V = np.asarray(V, dtype=float)
    J = np.asarray(J, dtype=float)
    if V.ndim != 1 or J.ndim != 1 or V.size != J.size or V.size < 2:
        raise ValueError("V and J must be equal-length one-dimensional arrays with at least 2 points")
    if not np.all(np.isfinite(V)) or not np.all(np.isfinite(J)):
        raise ValueError("V and J must contain only finite values")
    order = np.argsort(V, kind="stable")
    V, J = V[order], J[order]
    crossing = (V[:-1] >= 0.0) & (J[:-1] >= 0.0) & (J[1:] <= 0.0)
    if not np.any(crossing):
        return float("nan")
    index = int(np.flatnonzero(crossing)[0])
    v0, v1 = V[index], V[index + 1]
    j0, j1 = J[index], J[index + 1]
    if abs(j1 - j0) < 1e-14:
        return float(0.5 * (v0 + v1))
    return float(v0 + (0.0 - j0) * (v1 - v0) / (j1 - j0))


def _refine_mpp(V: np.ndarray, J: np.ndarray, idx: int) -> tuple[float, float, float]:
    """Refine the discrete maximum-power point with a local quadratic fit."""
    lo, hi = max(idx - 1, 0), min(idx + 1, V.size - 1)
    if hi - lo < 2:
        return float(V[idx]), float(J[idx]), float(J[idx] * V[idx])
    Vs = V[lo:hi + 1]
    Ps = J[lo:hi + 1] * Vs
    a, b, _ = np.polyfit(Vs, Ps, 2)
    if a < 0:
        vmp = float(np.clip(-b / (2 * a), Vs[0], Vs[-1]))
    else:
        vmp = float(V[idx])
    jmp = float(np.interp(vmp, V, J))
    return vmp, jmp, float(vmp * jmp)


def solar_metrics(V, J, pin: float | None = None):
    """Extract solar-cell metrics; return ``eta=nan`` when irradiance is unknown."""
    V = np.asarray(V, dtype=float)
    J = np.asarray(J, dtype=float)
    if V.ndim != 1 or J.ndim != 1 or V.size == 0 or V.size != J.size:
        raise ValueError(f"V and J must be non-empty arrays of equal length: V={V.size}, J={J.size}")
    if not np.all(np.isfinite(V)) or not np.all(np.isfinite(J)):
        raise ValueError("V and J must contain only finite values")
    if pin is not None and (not np.isfinite(pin) or pin <= 0):
        raise ValueError(f"pin must be a positive finite value in W/cm²; received {pin!r}")

    order = np.argsort(V, kind="stable")
    V, J = V[order], J[order]


    if V.size > 1:
        unique_v, inverse, counts = np.unique(V, return_inverse=True, return_counts=True)
        if unique_v.size != V.size:
            J = np.bincount(inverse, weights=J) / counts
            V = unique_v


    if V[0] <= 0.0 <= V[-1]:
        jsc = float(np.interp(0.0, V, J))
    else:
        nearest = int(np.argmin(np.abs(V)))
        if abs(float(V[nearest])) > 0.03:
            raise ValueError(
                "J-V data do not bracket 0 V or contain a point within 0.03 V; "
                "Jsc cannot be estimated reliably"
            )
        jsc = float(J[nearest])
    if jsc < 0:
        raise ValueError(
            "Current near short circuit is negative; solar_metrics requires the "
            "generation-positive convention (Jsc >= 0)")


    voc = voc_zero_crossing(V, J)


    gen = (V >= 0) & (J >= 0)
    if np.isfinite(voc):
        gen &= V <= voc
    if not np.any(gen):
        eta = np.nan if pin is None else 0.0
        return {"Jsc": jsc, "Voc": voc, "FF": 0.0,
                "Pmax": 0.0, "Vmp": 0.0, "Jmp": 0.0, "eta": eta}

    P = J * V
    idx = int(np.where(gen)[0][int(np.argmax(P[gen]))])
    vmp, jmp, pmax = _refine_mpp(V, J, idx)

    ff = pmax / (jsc * voc) if (jsc * voc > 0 and np.isfinite(voc)) else 0.0
    eta = np.nan if pin is None else pmax / pin
    return {"Jsc": jsc, "Voc": voc, "FF": ff,
            "Pmax": pmax, "Vmp": vmp, "Jmp": jmp, "eta": eta}
