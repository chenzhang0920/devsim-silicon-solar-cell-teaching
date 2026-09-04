"""Check CLI paths and saved-fit replay behavior."""

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from scripts import plot_fit, plot_iv, plot_optimization, prepare_data


def test_relative_cli_paths_are_project_root_anchored():
    root = Path(__file__).resolve().parents[1]
    expected = root / "results" / "iv_sim.csv"
    assert prepare_data._project_path("results/iv_sim.csv") == expected
    assert plot_iv._project_path("results/iv_sim.csv") == expected
    assert plot_fit._project_path("results/iv_sim.csv") == expected


def test_plot_iv_omits_efficiency_without_saved_power_provenance(capsys, tmp_path):
    frame = pd.DataFrame({"V": [0.0, 0.6], "J": [0.03, 0.0]})

    assert plot_iv.modeled_input_power(frame, tmp_path / "legacy.csv") is None
    assert "modeled efficiency will be omitted" in capsys.readouterr().out


def test_plot_iv_accepts_only_one_positive_saved_power_value(tmp_path):
    source = tmp_path / "curve.csv"
    valid = pd.DataFrame({plot_iv.MODELED_POWER_COLUMN: [0.1, 0.1]})
    assert plot_iv.modeled_input_power(valid, source) == pytest.approx(0.1)

    invalid = pd.DataFrame({plot_iv.MODELED_POWER_COLUMN: [0.1, 0.2]})
    with pytest.raises(ValueError, match="one positive finite value"):
        plot_iv.modeled_input_power(invalid, source)


def test_plot_iv_rejects_an_explicit_missing_reference(monkeypatch, tmp_path):
    monkeypatch.setattr(plot_iv, "PROJECT_ROOT", tmp_path)
    with pytest.raises(SystemExit, match="Comparison data file not found"):
        plot_iv.load_reference("missing.csv")


@pytest.mark.parametrize("expected", [None, "", "abc", "g" * 64])
def test_saved_fit_hash_verification_requires_a_valid_sha256(
    monkeypatch, tmp_path, expected,
):
    source = tmp_path / "data.csv"
    source.write_text("V,J\n0,0.03\n", encoding="utf-8")
    monkeypatch.setattr(plot_fit, "PROJECT_ROOT", tmp_path)

    with pytest.raises(SystemExit, match="missing or invalid"):
        plot_fit._verify_hash(source.name, expected)


def test_saved_fit_replay_rejects_unknown_metadata_schema(
    monkeypatch, tmp_path,
):
    params_path = tmp_path / "fitted_params.json"
    params_path.write_text("{}", encoding="utf-8")
    (tmp_path / "fit_metadata.json").write_text(
        json.dumps({"schema_version": 2}), encoding="utf-8"
    )
    monkeypatch.setattr(plot_fit, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["plot_fit.py", "--params", params_path.name])

    with pytest.raises(SystemExit, match="Unsupported fit-metadata schema"):
        plot_fit.main()


def test_joint_replay_metrics_use_the_saved_complete_parameter_snapshot(
    monkeypatch, tmp_path,
):
    params_path = tmp_path / "joint_fitted_params.json"
    params_path.write_text(json.dumps({
        "schema_version": 1,
        "parameters": {
            "photon_flux": {
                "value": 1.25, "vary": True, "min": 0.1, "max": 2.0,
                "stderr": 0.01,
            },
        },
    }), encoding="utf-8")
    saved_model = {"thickness": 0.0123, "photon_flux": 0.75}
    dataset_paths = {
        "light_iv": "light.csv",
        "dark_iv": "dark.csv",
        "ishort_summary": "ishort.csv",
        "voc_summary": "voc.csv",
    }
    dataset_hashes = {}
    for name, relative_path in dataset_paths.items():
        source = tmp_path / relative_path
        source.write_text(f"fixture,{name}\n", encoding="utf-8")
        dataset_hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()

    (tmp_path / "joint_fit_metadata.json").write_text(json.dumps({
        "schema_version": 1,
        "mode": "joint",
        "sample": "3",
        "model_params": saved_model,
        "simulation_config": plot_fit.SIMULATION,
        "datasets": dataset_paths,
        "dataset_sha256": dataset_hashes,
    }), encoding="utf-8")

    data = SimpleNamespace(paths={
        "light_iv": "light.csv", "dark_iv": "dark.csv",
        "ishort_summary": "ishort.csv", "voc_summary": "voc.csv",
    })
    seen = {}
    monkeypatch.setattr(plot_fit, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(plot_fit, "load_joint_data", lambda *args, **kwargs: data)
    monkeypatch.setattr(plot_fit, "joint_comparison_figure", lambda *args: plt.figure())

    def fake_evaluate(params, observed):
        seen.update(params)
        assert observed is data
        return {
            "light_iv_rmse_A_cm2": 0.0,
            "dark_iv_rmse_A_cm2": 0.0,
            "light_ishort_measured_A_cm2": 0.01,
            "light_ishort_simulated_A_cm2": 0.01,
            "light_voc_measured_V": 0.6,
            "light_voc_simulated_V": 0.6,
        }

    monkeypatch.setattr(plot_fit, "evaluate_joint", fake_evaluate)
    monkeypatch.setattr(
        sys, "argv", ["plot_fit.py", "--params", params_path.name]
    )

    plot_fit.main()

    assert seen["thickness"] == saved_model["thickness"]
    assert seen["photon_flux"] == 1.25


def test_sweep_uses_the_centralized_modeled_input_power_constant():
    source = (
        Path(__file__).resolve().parents[1] / "scripts" / "plot_sweep.py"
    ).read_text(encoding="utf-8")
    assert "MODELED_INPUT_POWER_W_CM2 * params[\"photon_flux\"]" in source
    assert "params[\"photon_flux\"] * 0.1" not in source


def test_optimization_gif_default_follows_custom_png_output():
    expected = plot_optimization.PROJECT_ROOT / "results" / "custom-trace.gif"
    assert plot_optimization._gif_output_path(
        "results/custom-trace.png"
    ) == expected


def test_optimization_accepts_a_positive_continuous_shunt_parameter():
    params = plot_optimization.make_params()
    rsh = params["shunt_resistance"]
    rsh.min = 10.0
    rsh.value = 100.0
    rsh.vary = True

    plot_optimization._validate_shunt_fit(params)


def test_optimization_rejects_the_zero_shunt_sentinel_as_a_fit_value():
    params = plot_optimization.make_params()
    params["shunt_resistance"].vary = True

    try:
        plot_optimization._validate_shunt_fit(params)
    except SystemExit as exc:
        assert "Rsh=0 represents ideal infinity" in str(exc)
    else:
        raise AssertionError("zero-valued varied Rsh should be rejected")
