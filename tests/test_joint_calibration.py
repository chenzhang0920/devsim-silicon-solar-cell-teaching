"""Tests for the measured-cell multi-observable calibration interface."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from calibration.fit import (
    JointData,
    fit_joint,
    joint_block_score,
    joint_residual,
    load_joint_data,
    make_params,
)


@pytest.mark.parametrize("sample", [3, 4])
def test_joint_data_loads_all_observable_blocks(sample):
    data = load_joint_data(sample)
    assert isinstance(data, JointData)
    assert data.sample == str(sample)
    assert data.light_v.size >= 3
    assert data.dark_v.size >= 3
    assert data.light_v.size == data.light_j.size
    assert data.dark_v.size == data.dark_j.size
    assert data.light_ishort["n_points"] == pytest.approx(100)
    assert data.light_ishort["J_mean_A_cm2"] > 0
    assert data.light_voc > 0
    assert data.dark_ishort["J_mean_A_cm2"] > 0
    assert np.isfinite(data.dark_open_circuit_offset)
    assert set(data.weights) == {"light_iv", "dark_iv", "light_ishort", "light_voc"}
    assert data.iv_sigma_fraction == pytest.approx(0.025)


def test_dark_offset_diagnostics_are_optional(monkeypatch, tmp_path):
    import importlib

    fit_module = importlib.import_module("calibration.fit")

    root = fit_module._PROJECT_ROOT
    processed = root / "data" / "processed"
    voc = pd.read_csv(processed / "voc_summary.csv")
    ishort = pd.read_csv(processed / "ishort_summary.csv")
    voc = voc.loc[~((voc["sample"].astype(str) == "3") & (voc["condition"] == "dark"))]
    ishort = ishort.loc[
        ~((ishort["sample"].astype(str) == "3") & (ishort["condition"] == "dark"))
    ]
    voc_path = tmp_path / "voc_summary.csv"
    ishort_path = tmp_path / "ishort_summary.csv"
    voc.to_csv(voc_path, index=False)
    ishort.to_csv(ishort_path, index=False)
    monkeypatch.setitem(
        fit_module.CALIBRATION["joint"],
        "paths",
        {
            "light_iv": str(processed / "light_iv_sample{sample}.csv"),
            "dark_iv": str(processed / "dark_iv_sample{sample}.csv"),
            "ishort_summary": str(ishort_path),
            "voc_summary": str(voc_path),
        },
    )

    data = fit_module.load_joint_data(3)

    assert data.dark_open_circuit_offset is None
    assert data.dark_ishort is None


def test_joint_loader_accepts_recorded_path_override():
    root = Path(__file__).resolve().parents[1]
    processed = root / "data" / "processed"
    paths = {
        "light_iv": str(processed / "light_iv_sample{sample}.csv"),
        "dark_iv": str(processed / "dark_iv_sample{sample}.csv"),
        "ishort_summary": str(processed / "ishort_summary.csv"),
        "voc_summary": str(processed / "voc_summary.csv"),
    }

    data = load_joint_data(3, paths_override=paths)

    assert data.paths["light_iv"].endswith("light_iv_sample3.csv")


def test_joint_residual_includes_iv_short_and_voc_blocks(monkeypatch):
    import importlib
    fit_module = importlib.import_module("calibration.fit")

    data = load_joint_data(3)
    calls = []

    def fake_terminal(params, voltages, j_meas):
        calls.append((dict(params), np.asarray(voltages).copy(), np.asarray(j_meas).copy()))
        # Returning the target makes all residuals exactly zero, while still
        # allowing this test to inspect which data blocks were requested.
        return np.asarray(j_meas, dtype=float)

    monkeypatch.setattr(fit_module, "run_simulation_terminal", fake_terminal)
    values = joint_residual(make_params(), data)

    assert values.shape == (data.light_v.size + data.dark_v.size + 2,)
    assert np.allclose(values, 0.0)
    assert len(calls) == 4
    assert calls[0][1].shape == data.light_v.shape
    assert calls[1][1].shape == data.dark_v.shape
    assert calls[1][0]["photon_flux"] == pytest.approx(0.0)
    assert calls[2][1].tolist() == [pytest.approx(data.light_ishort["V_mean_V"])]
    assert calls[3][1].tolist() == [pytest.approx(data.light_voc)]
    assert calls[3][2].tolist() == [0.0]


def test_joint_residual_can_disable_observable_blocks(monkeypatch):
    import importlib
    fit_module = importlib.import_module("calibration.fit")

    data = load_joint_data(3)
    data.weights.update({"dark_iv": 0.0, "light_ishort": 0.0, "light_voc": 0.0})
    monkeypatch.setattr(
        fit_module,
        "run_simulation_terminal",
        lambda params, voltages, j_meas: np.asarray(j_meas, dtype=float),
    )
    values = joint_residual(make_params(), data)
    assert values.shape == (data.light_v.size,)


def test_each_iv_curve_is_normalized_as_one_rms_block(monkeypatch):
    import importlib
    fit_module = importlib.import_module("calibration.fit")

    data = load_joint_data(3)
    data.weights.update({"light_iv": 1.0, "dark_iv": 0.0,
                         "light_ishort": 0.0, "light_voc": 0.0})

    def fixed_fractional_error(params, voltages, j_meas):
        del params, voltages
        current = np.asarray(j_meas, dtype=float)
        scale = np.max(np.abs(current))
        return current + data.iv_sigma_fraction * scale

    monkeypatch.setattr(fit_module, "run_simulation_terminal", fixed_fractional_error)
    values = joint_residual(make_params(), data, mode="absolute")
    assert np.sum(values**2) == pytest.approx(1.0)


def test_joint_block_score_uses_active_block_weights():
    data = load_joint_data(3)
    active_weight = sum(weight for weight in data.weights.values() if weight > 0)
    assert joint_block_score(active_weight, data) == pytest.approx(1.0)
    assert joint_block_score(4 * active_weight, data) == pytest.approx(4.0)


def test_joint_fit_keeps_covariance_on_stated_discrepancy_scales(monkeypatch):
    import importlib
    fit_module = importlib.import_module("calibration.fit")

    data = load_joint_data(3)
    sentinel = object()
    captured = {}

    def fake_minimize(*args, **kwargs):
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(fit_module.lmfit, "minimize", fake_minimize)
    assert fit_joint(data) is sentinel
    assert captured["scale_covar"] is False


def test_voc_scale_uses_points_near_voc_not_end_of_extended_sweep():
    import importlib
    fit_module = importlib.import_module("calibration.fit")

    data = load_joint_data(3)
    data.light_voc = 0.65
    data.light_v = np.array([0.0, 0.50, 0.62, 0.64, 0.66, 0.68, 0.80, 1.00])
    data.light_j = np.array([0.325, 0.075, 0.015, 0.005, -0.005, -0.015, -0.02, -0.40])

    sigma = fit_module._voc_current_sigma(data)

    assert sigma == pytest.approx(0.5 * data.voc_sigma)
