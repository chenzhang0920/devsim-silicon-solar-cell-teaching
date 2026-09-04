'Utilities for tests/test_integration.py.'
import numpy as np
import pytest

from config import MODEL_PARAMS
from model import SolarCellParams, profiles, run_simulation, sweep_light
from model.analysis import band_edges, solar_metrics
from model.spectrum import absorption_cm, bin_photon_flux


@pytest.mark.slow
def test_forward_simulation_is_physical():
    V, J = run_simulation(params=MODEL_PARAMS)

    assert V.shape == J.shape
    assert V.size > 10
    assert V[0] == pytest.approx(0.0, abs=1e-9)

    m = solar_metrics(V, J)

    assert 0.01 < m["Jsc"] < 0.06, f"Jsc={m['Jsc']} is non-physical"
    assert 0.4 < m["Voc"] < 0.8, f"Voc={m['Voc']} is non-physical"
    assert 0.4 < m["FF"] < 1.0, f"FF={m['FF']} is non-physical"
    assert 0.0 < m["Pmax"] < 0.03, f"Pmax={m['Pmax']} is non-physical"


@pytest.mark.slow
def test_solar_metrics_matches_direct_extraction():
    'Test solar metrics matches direct extraction.'
    V, J = run_simulation(params=MODEL_PARAMS)
    m = solar_metrics(V, J)

    j = J
    crossing = (j[:-1] >= 0) & (j[1:] < 0)
    if crossing.any():
        i0 = int(np.where(crossing)[0][0])
        assert V[i0] <= m["Voc"] <= V[i0 + 1]


@pytest.mark.slow
def test_device_is_front_p_plus_on_n_and_field_points_to_front():
    'Test device is front p plus on n and field points to front.'
    p = SolarCellParams(**MODEL_PARAMS)
    d = profiles(p)


    assert d["net_doping"][0] == pytest.approx(-p.emitter_doping)
    assert d["net_doping"][-1] == pytest.approx(p.base_doping)
    assert d["holes"][0] > d["electrons"][0]
    assert d["electrons"][-1] > d["holes"][-1]

    x_um = d["x"] * 1e4
    ec, _, _, _ = band_edges(
        d["potential"], d["electrons"], d["holes"], T=p.temperature)
    i_p = int(np.argmin(np.abs(x_um - 0.1)))
    i_n = int(np.argmin(np.abs(x_um - 1.8)))
    vbi_numeric = float(ec[i_p] - ec[i_n])
    vt = 8.617333262e-5 * p.temperature
    vbi_analytic = vt * np.log(p.emitter_doping * p.base_doping / 1e20)
    assert vbi_numeric == pytest.approx(vbi_analytic, abs=0.01)


    e_field = -np.gradient(d["potential"], d["x"])
    assert e_field[int(np.argmax(np.abs(e_field)))] < 0


    # ``numpy.trapezoid`` was added in NumPy 2.0; keep the test compatible
    # with the project's NumPy >=1.24 environment as well.
    integrate = getattr(np, "trapezoid", np.trapz)
    generated_numeric = integrate(d["generation"], d["x"])
    alpha = absorption_cm()
    generated_analytic = (1.0 - p.front_reflectance) * sum(
        bin_photon_flux(i) * (1.0 - np.exp(-a * p.thickness))
        for i, a in enumerate(alpha)
    )
    assert generated_numeric == pytest.approx(generated_analytic, rel=5e-3)


@pytest.mark.slow
def test_zero_light_sweep_returns_one_dark_frame_without_division_by_zero():
    p = SolarCellParams(**{**MODEL_PARAMS, "photon_flux": 0.0})
    frames = sweep_light(p, n_steps=2)
    assert len(frames) == 1
    assert frames[0]["flux"] == 0.0
    assert np.allclose(frames[0]["generation"], 0.0)
