'Utilities for tests/test_analysis.py.'
import numpy as np
import pytest
import lmfit

import model
from config import MODEL_PARAMS, CALIBRATION
from model.analysis import solar_metrics, band_edges, voc_zero_crossing
from model.parameters import check_params, VALID_FIELDS, SolarCellParams
from model.spectrum import wavelengths_nm, absorption_cm, flux_density
from calibration.fit import (
    make_params,
    residual_vector,
    validate_dark_iv_data,
    validate_iv_data,
)
from calibration.report import (
    physical_warnings,
    correlation_from_covar,
    identifiability_figure,
    identifiability_summary,
)


def test_solar_metrics():
    V = np.array([0.0, 0.2, 0.4, 0.6, 0.7])
    J = np.array([0.030, 0.025, 0.015, 0.005, -0.005])

    m = solar_metrics(V, J, pin=0.1)
    assert m["Jsc"] == pytest.approx(0.030)
    assert m["Voc"] == pytest.approx(0.65)

    assert m["Vmp"] == pytest.approx(0.35)
    assert m["FF"] == pytest.approx(0.006125 / (0.030 * 0.65))
    assert 0.0 < m["FF"] < 1.0
    assert m["eta"] == pytest.approx(m["FF"] * m["Jsc"] * m["Voc"] / 0.1)
    assert 0.0 < m["eta"] < 1.0


def test_solar_metrics_robust_to_unsorted_input():

    V = np.array([0.7, 0.0, 0.4, 0.2, 0.6])
    J = np.array([-0.005, 0.030, 0.015, 0.025, 0.005])
    m = solar_metrics(V, J)
    assert m["Jsc"] == pytest.approx(0.030)
    assert m["Voc"] == pytest.approx(0.65)
    assert m["Vmp"] == pytest.approx(0.35)


def test_solar_metrics_duplicate_voltage_no_crash():

    V = np.array([0.0, 0.2, 0.2, 0.4, 0.6, 0.7])
    J = np.array([0.030, 0.025, 0.015, 0.010, 0.005, -0.005])
    m = solar_metrics(V, J)
    assert m["Jsc"] == pytest.approx(0.030)
    assert m["Voc"] == pytest.approx(0.65)


def test_solar_metrics_no_crossing_returns_nan_voc():

    V = np.array([0.0, 0.1, 0.2])
    J = np.array([0.030, 0.028, 0.026])
    m = solar_metrics(V, J)
    assert np.isnan(m["Voc"])
    assert m["FF"] == 0.0
    assert m["Jsc"] == pytest.approx(0.030)


def test_solar_metrics_rejects_reversed_current_sign():
    with pytest.raises(ValueError, match="generation-positive"):
        solar_metrics([0.0, 0.4, 0.7], [-0.03, -0.015, 0.005])


def test_solar_metrics_rejects_nonfinite_data():
    with pytest.raises(ValueError, match="finite values"):
        solar_metrics([0.0, 0.4, 0.7], [0.03, np.nan, -0.005])


def test_solar_metrics_interpolates_jsc_at_zero():
    m = solar_metrics([-0.01, 0.01, 0.6, 0.7],
                      [0.031, 0.029, 0.005, -0.005])
    assert m["Jsc"] == pytest.approx(0.030)


def test_voc_uses_first_physical_crossing_when_tail_is_noisy():
    voltage = [0.0, 0.5, 0.6, 0.7, 0.8]
    current = [0.03, 0.01, -0.002, 0.001, -0.004]
    assert voc_zero_crossing(voltage, current) == pytest.approx(0.5833333333)


def test_mpp_ignores_positive_noise_after_first_voc_crossing():
    voltage = np.array([0.0, 0.4, 0.6, 0.7, 0.8])
    current = np.array([0.03, 0.02, -0.002, 0.08, -0.004])
    metrics = solar_metrics(voltage, current)
    assert metrics["Voc"] == pytest.approx(0.5818181818)
    assert metrics["Vmp"] < metrics["Voc"]
    assert metrics["Pmax"] < 0.02


def test_solar_metrics_rejects_data_far_from_zero_bias():
    with pytest.raises(ValueError, match="Jsc cannot be estimated"):
        solar_metrics([0.1, 0.4, 0.7], [0.03, 0.02, -0.01])


@pytest.mark.parametrize("pin", [0.0, -0.1, np.nan, np.inf])
def test_solar_metrics_rejects_invalid_incident_power(pin):
    with pytest.raises(ValueError, match="pin"):
        solar_metrics([0.0, 0.6, 0.7], [0.03, 0.005, -0.005], pin=pin)


def test_solar_metrics_omits_efficiency_when_irradiance_is_unknown():
    metrics = solar_metrics(
        [0.0, 0.4, 0.7], [0.03, 0.015, -0.005], pin=None)
    assert metrics["Pmax"] > 0
    assert np.isnan(metrics["eta"])


def test_band_edges():
    n = p = np.ones(5) * 1e10
    psi = np.zeros(5)
    Ec, Ev, Efn, Efp = band_edges(psi, n, p)
    assert Ec.shape == Ev.shape == Efn.shape == Efp.shape == (5,)
    assert Ec[0] == pytest.approx(0.56)            # EG/2
    assert Ev[0] == pytest.approx(-0.56)
    assert Efn[0] == pytest.approx(0.0)
    assert Efp[0] == pytest.approx(0.0)


def test_quasi_fermi_splitting_matches_carrier_product():
    n = np.array([2e15, 4e15])
    p = np.array([3e12, 5e12])
    psi = np.array([0.1, -0.2])
    _, _, efn, efp = band_edges(psi, n, p)
    vt = 8.617333262e-5 * 300.0
    expected = vt * np.log(n * p / 1e20)
    assert efn - efp == pytest.approx(expected)


def test_check_params_rejects_unknown():
    with pytest.raises(ValueError):
        check_params({"not_a_field": 1.0})


def test_check_params_accepts_valid():
    p = check_params({"emitter_doping": 1e19})
    assert isinstance(p, SolarCellParams)


def test_config_covers_every_device_parameter():
    'Test config covers every device parameter.'
    assert set(MODEL_PARAMS) == VALID_FIELDS
    assert set(CALIBRATION["params"]) <= VALID_FIELDS


def test_public_partial_override_inherits_current_config(monkeypatch):
    'Test public partial override inherits current config.'
    captured = {}

    def fake_simulate(p, voltages):
        captured["p"] = p
        v = np.asarray(voltages, dtype=float)
        return v, np.zeros_like(v)

    monkeypatch.setitem(model.MODEL_PARAMS, "base_doping", 2.5e16)
    monkeypatch.setattr(model, "simulate", fake_simulate)
    model.run_simulation({"hole_lifetime": 2e-5}, voltages=[0.0, 0.1])
    assert captured["p"].base_doping == pytest.approx(2.5e16)
    assert captured["p"].hole_lifetime == pytest.approx(2e-5)


def test_configured_voltage_grid_rejects_a_changed_step(monkeypatch):
    monkeypatch.setitem(
        model.SIMULATION,
        "voltages",
        {"start": 0.0, "stop": 0.65, "step": 0.02},
    )
    with pytest.raises(ValueError, match="integer multiple"):
        model.run_simulation()


def test_terminal_internal_solve_explicitly_disables_config_resistances(monkeypatch):
    'Test terminal internal solve explicitly disables config resistances.'
    seen = []

    def fake_run(params=None, voltages=None):
        seen.append(dict(params))
        v = np.asarray(voltages, dtype=float)
        return v, 0.03 - 0.04 * v

    monkeypatch.setattr(model, "run_simulation", fake_run)
    monkeypatch.setitem(model.MODEL_PARAMS, "series_resistance", 2.0)
    monkeypatch.setitem(model.MODEL_PARAMS, "shunt_resistance", 1000.0)

    model.terminal_iv(v_junc=np.array([0.0, 0.2, 0.4]))
    assert seen[-1]["series_resistance"] == 0.0
    assert seen[-1]["shunt_resistance"] == 0.0

    model.run_simulation_terminal(
        params=None,
        voltages=np.array([0.0, 0.2, 0.4]),
        j_meas=np.array([0.03, 0.02, 0.01]),
    )
    assert seen[-1]["series_resistance"] == 0.0
    assert seen[-1]["shunt_resistance"] == 0.0


def test_check_params_checks_merged_geometry():

    with pytest.raises(ValueError, match="emitter_depth"):
        check_params({"thickness": 1e-5})


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_check_params_rejects_nonfinite(bad):
    with pytest.raises(ValueError, match="finite"):
        check_params({"electron_lifetime": bad})


def test_check_params_rejects_unsupported_temperature():
    with pytest.raises(ValueError, match="supports only temperature=300"):
        check_params({"temperature": 325.0})


def test_check_params_requires_p_plus_emitter_doping_contrast():
    with pytest.raises(ValueError, match=r"emitter_doping >= 10\*base_doping"):
        check_params({"emitter_doping": 5e17, "base_doping": 1e17})


def test_validate_iv_data_accepts_teaching_curve():
    v, j = validate_iv_data([0.0, 0.3, 0.7], [0.03, 0.02, -0.01])
    assert v.shape == j.shape == (3,)


def test_validate_iv_data_accepts_exact_voc_endpoint():
    validate_iv_data([0.0, 0.3, 0.65], [0.03, 0.02, 0.0])


def test_validate_dark_iv_accepts_either_small_zero_bias_offset_sign():
    voltage = np.array([0.0, 0.2, 0.5])
    for offset in (-2e-7, 2e-7):
        _, current = validate_dark_iv_data(voltage, [offset, -1e-5, -3e-3])
        assert current[0] == pytest.approx(offset)


def test_validate_dark_iv_requires_forward_current_with_the_project_sign():
    with pytest.raises(ValueError, match="negative forward current"):
        validate_dark_iv_data([0.0, 0.2, 0.5], [1e-7, 1e-5, 3e-3])


def test_validate_dark_iv_does_not_accept_reverse_bias_negative_current():
    with pytest.raises(ValueError, match="negative forward current"):
        validate_dark_iv_data([-0.2, 0.0, 0.3], [-1e-3, 1e-7, 2e-3])


@pytest.mark.parametrize("v,j,match", [
    ([0.0, 0.3, 0.3], [0.03, 0.02, -0.01], "strictly increasing"),
    ([0.0, 0.3, 0.7], [-0.03, -0.02, -0.01], "Short-circuit current"),
    ([0.0, 0.3, 0.7], [0.03, 0.02, 0.01], "do not reach Voc"),
    ([-0.2, 0.0, 0.3, 0.7], [-0.01, 0.03, 0.02, 0.01], "do not reach Voc"),
    ([0.0, 0.3, 0.7], [0.03, np.nan, -0.01], "finite values"),
])
def test_validate_iv_data_rejects_bad_input(v, j, match):
    with pytest.raises(ValueError, match=match):
        validate_iv_data(v, j)


def test_make_params_keys_are_valid():
    p = make_params()
    assert len(p) > 0
    assert set(p.keys()) <= VALID_FIELDS


def test_fixed_fit_params_follow_model_params(monkeypatch):
    import importlib
    fit_module = importlib.import_module("calibration.fit")

    monkeypatch.setitem(fit_module.MODEL_PARAMS, "electron_lifetime", 2.5e-5)
    p = fit_module.make_params()
    assert not p["electron_lifetime"].vary
    assert p["electron_lifetime"].value == pytest.approx(2.5e-5)


def test_non_least_squares_does_not_receive_diff_step(monkeypatch):
    import importlib
    fit_module = importlib.import_module("calibration.fit")

    captured = {}

    def fake_minimize(*args, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(fit_module.lmfit, "minimize", fake_minimize)
    fit_module.fit([0.0, 0.3, 0.7], [0.03, 0.02, -0.01], method="nelder")
    assert "diff_step" not in captured


def test_residual_vector_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="equal length"):
        residual_vector([0.1, 0.2], [0.1])


def test_spectrum_accessors_return_defensive_copies():
    for getter in (wavelengths_nm, absorption_cm, flux_density):
        a = getter()
        original = getter()[0]
        a[0] = -123.0
        assert getter()[0] == pytest.approx(original)


def test_make_params_rejects_zero_bound_for_varied_rsh(monkeypatch):
    import importlib
    fit_module = importlib.import_module("calibration.fit")

    monkeypatch.setattr(fit_module, "_FIT_SPEC", {
        "shunt_resistance": {"value": 100.0, "min": 0.0,
                             "max": 5000.0, "vary": True}
    })
    with pytest.raises(ValueError, match="min must be > 0"):
        fit_module.make_params()


def test_physical_warnings_empty_for_defaults():

    assert physical_warnings(make_params()) == []


def test_millisecond_lifetime_is_not_declared_unphysical():
    p = lmfit.Parameters()
    p.add("hole_lifetime", value=1e-2, vary=True)
    assert not physical_warnings(p)


def test_extreme_lifetime_requests_verification():
    p = lmfit.Parameters()
    p.add("hole_lifetime", value=1.0, vary=True)
    assert any("units" in w and "identifiability" in w for w in physical_warnings(p))


def test_correlation_from_covar():
    covar = np.array([[1.0, 0.5], [0.5, 4.0]])
    corr = correlation_from_covar(covar)
    assert np.diag(corr) == pytest.approx([1.0, 1.0])
    assert corr[0, 1] == pytest.approx(0.5 / (1.0 * 2.0))   # 0.25
    assert corr[1, 0] == pytest.approx(0.25)


def test_identifiability_summary():
    p = lmfit.Parameters()
    p.add("a", value=2.0, vary=True)
    p["a"].stderr = 0.1
    p.add("b", value=1.0, vary=True)
    p["b"].stderr = 2.0
    lines = identifiability_summary(p, covar=None, var_names=["a", "b"])
    assert any("a" in ln and "identifiable" in ln for ln in lines)
    assert any("b" in ln and "not reliably identified" in ln for ln in lines)


def test_identifiability_summary_does_not_call_correlated_parameters_identifiable():
    p = lmfit.Parameters()
    p.add("a", value=1.0, vary=True)
    p.add("b", value=1.0, vary=True)
    p["a"].stderr = p["b"].stderr = 0.05
    covariance = np.array([[1.0, 0.95], [0.95, 1.0]])

    lines = identifiability_summary(p, covariance, var_names=["a", "b"])

    parameter_lines = [line for line in lines if line.startswith(("a:", "b:"))]
    assert all("not separately identifiable" in line for line in parameter_lines)


def test_identifiability_summary_downgrades_failed_quality_gate():
    p = lmfit.Parameters()
    p.add("a", value=1.0, vary=True)
    p["a"].stderr = 0.01

    lines = identifiability_summary(
        p, covar=None, var_names=["a"], quality_adequate=False
    )

    assert "local numerical sensitivity only" in lines[0]
    assert "locally identifiable" not in lines[0]


def test_identifiability_figure_makes_failed_quality_gate_visible():
    p = lmfit.Parameters()
    p.add("a", value=1.0, vary=True)
    p["a"].stderr = 0.05
    figure = identifiability_figure(
        p, context="test observations", quality_note="Quality gate failed"
    )
    try:
        assert "Quality gate failed" in figure._suptitle.get_text()
        assert "Local covariance sensitivity" in figure._suptitle.get_text()
    finally:
        import matplotlib.pyplot as plt
        plt.close(figure)


def test_identifiability_rejects_covariance_parameter_mismatch():
    p = lmfit.Parameters()
    p.add("a", value=1.0, vary=True)
    p.add("b", value=2.0, vary=True)
    with pytest.raises(ValueError, match="does not match"):
        identifiability_summary(p, covar=np.eye(3), var_names=["a", "b"])
