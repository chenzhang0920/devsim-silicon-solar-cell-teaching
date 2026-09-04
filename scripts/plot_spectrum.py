"""Plot the compact teaching spectrum and silicon absorption model."""
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
from model.spectrum import wavelengths_nm, absorption_cm, flux_density, dlambda_nm
from model.style import C_BLUE, C_ORANGE, C_GRAY

BANDGAP_NM = 1107.0
Q = 1.602176634e-19


def main() -> None:
    ap = argparse.ArgumentParser(description="Spectrum, absorption coefficient, and ideal EQE")
    ap.add_argument("--out", default="results/spectrum.png", help="Output PNG path")
    args = ap.parse_args()

    lam = wavelengths_nm()
    alpha = absorption_cm()
    flux = flux_density()
    W = MODEL_PARAMS["thickness"]
    R = MODEL_PARAMS.get("front_reflectance", 0.0)

    eqe = (1.0 - R) * (1.0 - np.exp(-alpha * W))

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.2))


    ax = axes[0]
    ax.plot(lam, flux * 1e-14, color=C_BLUE, lw=2.0, marker="o", ms=4)
    ax.fill_between(lam, 0, flux * 1e-14, color=C_BLUE, alpha=0.15)
    ax.axvline(BANDGAP_NM, color="k", ls=":", lw=1)
    ax.annotate("band gap\n1107 nm", xy=(BANDGAP_NM, 0.6), xytext=(850, 0.8),
                fontsize=12, arrowprops=dict(arrowstyle="->", lw=1.1))
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Photon flux (10$^{14}$ cm$^{-2}$ s$^{-1}$ nm$^{-1}$)")
    ax.set_title("Teaching spectrum: 16 wavelength bins")
    ax.grid(True)


    ax = axes[1]
    ax.semilogy(lam, alpha, color=C_ORANGE, lw=2.0, marker="o", ms=4)
    ax.axvline(BANDGAP_NM, color="k", ls=":", lw=1)
    ax.set_xlabel("Wavelength (nm)")
    ax.set_ylabel("Absorption coefficient α (cm$^{-1}$)")
    ax.set_title("Silicon absorbs blue light near the front")
    ax.grid(True)

    fig.suptitle("Wavelength controls photon supply and absorption depth", fontsize=20)
    fig.text(
        0.5,
        0.01,
        "Teaching approximation: 50 nm bins; use ASTM G173 and tabulated silicon "
        "optical constants for precision work.",
        ha="center",
        fontsize=11.5,
        color=C_GRAY,
    )
    fig.tight_layout(rect=(0.035, 0.10, 0.995, 0.90))
    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {out}")

    dl = dlambda_nm()
    jsc_ideal = Q * np.sum(flux * eqe * dl) * 1e3  # A/cm² -> mA/cm²
    print(
        f"Ideal Jsc (R={R:.2f}, complete collection of absorbed photons) = "
        f"{jsc_ideal:.1f} mA/cm^2"
    )
    print("Compare this optical limit with the regenerated device Jsc to quantify collection loss.")


if __name__ == "__main__":
    main()
