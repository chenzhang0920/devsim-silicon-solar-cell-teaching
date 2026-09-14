"""Compact AM1.5-like teaching input for optical-generation calculations."""
from __future__ import annotations

import numpy as np


_WAVELENGTH_NM = np.arange(350, 1150, 50)


_ALPHA = np.array([
    1.0e6,   # 350
    9.0e4,   # 400
    4.5e4,   # 450
    1.4e4,   # 500
    7.0e3,   # 550
    4.0e3,   # 600
    2.4e3,   # 650
    1.5e3,   # 700
    1.0e3,   # 750
    7.0e2,   # 800
    5.0e2,   # 850
    3.0e2,   # 900
    1.5e2,   # 950
    6.0e1,   # 1000
    1.5e1,   # 1050
    3.0e0,   # 1100
])


_FLUX_DENSITY = np.array([
    1.5e14,  # 350
    3.5e14,  # 400
    5.0e14,  # 450
    5.5e14,  # 500
    6.0e14,  # 550
    5.5e14,  # 600
    5.0e14,  # 650
    4.2e14,  # 700
    3.8e14,  # 750
    3.4e14,  # 800
    2.8e14,  # 850
    2.2e14,  # 900
    1.5e14,  # 950
    1.0e14,  # 1000
    5.0e13,  # 1050
    1.5e13,  # 1100
])

_DLAMBDA_NM = float(_WAVELENGTH_NM[1] - _WAVELENGTH_NM[0])


def wavelengths_nm() -> np.ndarray:
    """Return wavelength-bin centers in nanometers."""
    return _WAVELENGTH_NM.copy()


def absorption_cm() -> np.ndarray:
    """Return silicon absorption coefficients in inverse centimeters."""
    return _ALPHA.copy()


def flux_density() -> np.ndarray:
    """Return incident photon-flux density per nanometer."""
    return _FLUX_DENSITY.copy()


def dlambda_nm() -> float:
    """Return the uniform wavelength-bin width in nanometers."""
    return _DLAMBDA_NM


def total_photon_flux() -> float:
    """Integrate photon flux across the teaching spectrum."""
    return float((_FLUX_DENSITY * _DLAMBDA_NM).sum())


def fractional_weights() -> np.ndarray:
    """Return each wavelength bin's fraction of total photon flux."""
    flux = _FLUX_DENSITY * _DLAMBDA_NM
    return flux / flux.sum()


def generation_terms() -> list[tuple[float, float]]:
    """Return Beer-Lambert amplitude and absorption coefficient per bin."""
    f = fractional_weights()
    return [(float(fi * ai), float(ai)) for fi, ai in zip(f, _ALPHA)]


def bin_photon_flux(index: int) -> float:
    """Return integrated incident photon flux for one wavelength bin."""
    return float(_FLUX_DENSITY[index] * _DLAMBDA_NM)


def monochromatic_terms(index: int) -> tuple[float, float]:
    """Return the normalized Beer-Lambert terms for one wavelength bin."""
    a = float(_ALPHA[index])
    return a, a
