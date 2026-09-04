'Utilities for tests/test_terminal_circuit.py.'
import numpy as np
import pytest

import model


def _linear_device(params, voltages=None):
    v = np.asarray(voltages, dtype=float)
    return v, 0.03 - 0.05 * v


def test_terminal_equation_residual_side(monkeypatch):
    monkeypatch.setattr(model, "run_simulation", _linear_device)
    v = np.array([0.0, 0.2])
    j_trial = np.array([0.03, 0.02])
    out = model.run_simulation_terminal(
        {"series_resistance": 2.0, "shunt_resistance": 100.0}, v, j_trial)
    vj = v + 2.0 * j_trial
    expected = (0.03 - 0.05 * vj) - vj / 100.0
    assert out == pytest.approx(expected)


def test_terminal_equation_sorts_junction_voltage_and_restores_order(monkeypatch):
    seen = {}

    def recording_device(params, voltages=None):
        v = np.asarray(voltages, dtype=float)
        seen["v"] = v
        assert np.all(np.diff(v) >= 0)
        return v, 0.03 - 0.05 * v

    monkeypatch.setattr(model, "run_simulation", recording_device)
    v = np.array([0.0, 0.2, 0.4])
    j_trial = np.array([0.20, 0.02, -0.20])
    out = model.run_simulation_terminal(
        {"series_resistance": 3.0}, v, j_trial)
    vj = v + 3.0 * j_trial
    assert seen["v"] == pytest.approx(np.sort(vj, kind="stable"))
    assert out == pytest.approx(0.03 - 0.05 * vj)


def test_terminal_iv_is_self_consistent(monkeypatch):
    monkeypatch.setattr(model, "run_simulation", _linear_device)
    vj = np.array([0.0, 0.2, 0.4])
    vt, j = model.terminal_iv(
        {"series_resistance": 2.0, "shunt_resistance": 100.0}, v_junc=vj)
    assert j == pytest.approx((0.03 - 0.05 * vj) - vj / 100.0)
    assert vt == pytest.approx(vj - 2.0 * j)


def test_terminal_iv_vmax_extends_dense_junction_grid(monkeypatch):
    seen = {}

    def recording_device(params, voltages=None):
        voltage = np.asarray(voltages, dtype=float)
        seen["maximum"] = float(voltage.max())
        return voltage, 0.03 - 0.05 * voltage

    monkeypatch.setattr(model, "run_simulation", recording_device)
    model.terminal_iv(n=12, v_max=1.2)

    assert seen["maximum"] == pytest.approx(1.2)


@pytest.mark.parametrize("bad", [np.nan, np.inf, -0.051])
def test_terminal_iv_rejects_invalid_vmax_before_solver(bad):
    with pytest.raises(ValueError, match="v_max"):
        model.terminal_iv(v_max=bad)
