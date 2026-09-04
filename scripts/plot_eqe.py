"""Plot the modeled external quantum efficiency and optional measured data."""
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import MODEL_PARAMS
from model import check_params, run_simulation, simulate_eqe
from model.spectrum import wavelengths_nm, absorption_cm, bin_photon_flux
from model.style import C_BLUE, C_GRAY, C_ORANGE

Q = 1.602176634e-19


def load_measured_eqe(path: str) -> tuple[np.ndarray, np.ndarray]:
    """Load and validate an optional measured EQE comparison table."""
    p = Path(path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    df = pd.read_csv(p)
    cols = {c.lower(): c for c in df.columns}
    wcol = cols.get("wavelength_nm") or cols.get("wavelength")
    ecol = cols.get("eqe")
    if wcol is None or ecol is None:
        raise SystemExit(
            "EQE comparison CSV requires 'wavelength_nm' (or 'wavelength') and 'EQE' columns; "
            f"found: {list(df.columns)}")
    wl = df[wcol].to_numpy(dtype=float)
    eqe = df[ecol].to_numpy(dtype=float)
    if wl.ndim != 1 or wl.size < 2 or not np.all(np.isfinite(wl)) \
            or not np.all(np.isfinite(eqe)):
        raise SystemExit("EQE comparison data require at least two finite numeric points")
    if np.any(np.diff(wl) <= 0):
        raise SystemExit("EQE wavelengths must be strictly increasing with no duplicates")
    if np.any((eqe < 0) | (eqe > 1)):
        raise SystemExit("EQE values must lie in [0, 1]")
    return wl, eqe


def main() -> None:
    ap = argparse.ArgumentParser(description="External quantum efficiency EQE(lambda)")
    ap.add_argument(
        "--data",
        help="Optional measured EQE CSV; omit when no spectral measurement is available",
    )
    ap.add_argument("--out", default="results/eqe.png", help="Output PNG path")
    args = ap.parse_args()


    p = check_params({**MODEL_PARAMS, "series_resistance": 0.0,
                      "shunt_resistance": 0.0})
    if p.photon_flux <= 0:
        raise SystemExit("photon_flux must be > 0 for EQE because normalization is undefined at zero light")
    lam = wavelengths_nm()
    alpha = absorption_cm()
    W = p.thickness
    ideal = (1.0 - p.front_reflectance) * (1.0 - np.exp(-alpha * W))

    print(f"Calculating EQE at {len(lam)} wavelength bins...")
    eqe = []
    for i, wl in enumerate(lam):
        jsc = simulate_eqe(p, i)
        phi = bin_photon_flux(i)              # Φ_i·Δλ (cm^-2 s^-1)

        eqe.append(jsc / (Q * p.photon_flux * phi))
        print(f"  lambda={wl:4.0f} nm  Jsc={jsc*1e3:8.4f} mA/cm^2  EQE={eqe[-1]:.3f}")
    eqe = np.asarray(eqe)


    jsc_from_eqe = Q * p.photon_flux * np.sum(
        eqe * np.array([bin_photon_flux(i) for i in range(len(lam))]))
    _, j_all = run_simulation(params=dict(vars(p)), voltages=np.array([0.0]))
    jsc_all_bins = float(j_all[0])
    mismatch = abs(jsc_from_eqe - jsc_all_bins) / max(abs(jsc_all_bins), 1e-30)
    print(f"\nEQE-integrated Jsc = {jsc_from_eqe*1e3:.2f} mA/cm^2; "
          f"all-bin simulation = {jsc_all_bins*1e3:.2f} mA/cm^2; difference = {mismatch:.1%}")

    fig, ax = plt.subplots(figsize=(10.2, 5.8))
    ax.axvspan(float(lam.min()), 500, color=C_ORANGE, alpha=0.06)
    ax.axvspan(950, float(lam.max()), color=C_BLUE, alpha=0.06)
    ax.plot(lam, ideal, color=C_GRAY, lw=1.8, ls="--", label="Absorption-only limit")
    ax.plot(lam, eqe, color=C_BLUE, lw=2.2, marker="o", ms=5,
            label="DEVSIM monochromatic simulation")
    if args.data:
        wl_meas, eqe_meas = load_measured_eqe(args.data)
        ax.scatter(wl_meas, eqe_meas, color=C_ORANGE, s=34, zorder=3,
                   label="measured EQE")

    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("EQE")
    ax.set_ylim(0, 1.05)
    ax.set_title("Modeled EQE: absorption versus carrier collection")
    ax.text(0.11, 0.13, "front-region / emitter\ncollection loss", transform=ax.transAxes,
            color=C_ORANGE, fontsize=12, ha="center")
    ax.text(0.90, 0.13, "weak absorption\nnear the band edge", transform=ax.transAxes,
            color=C_BLUE, fontsize=12, ha="center")
    ax.text(0.50, 0.02,
            f"EQE-integrated $J_{{sc}}$ = {jsc_from_eqe*1e3:.2f} mA/cm² "
            f"(all-bin model {jsc_all_bins*1e3:.2f})",
            transform=ax.transAxes, ha="center", va="bottom", fontsize=11.5, color=C_GRAY)
    ax.grid(True)
    ax.legend(
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.10),
        ncol=3 if args.data else 2,
    )

    fig.tight_layout(rect=(0, 0.13, 1, 1))
    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {out}")


if __name__ == "__main__":
    main()
