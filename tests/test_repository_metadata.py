"""Checks for files that keep the public teaching repository reproducible."""
import csv
import json
import hashlib
from pathlib import Path

import pytest

from config import MODEL_PARAMS, MODELED_INPUT_POWER_W_CM2
from scripts.plot_fit import _verify_hash, load_params_json


ROOT = Path(__file__).resolve().parents[1]


def test_citation_metadata_is_complete_and_consistent():
    citation = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert citation.startswith("cff-version: 1.2.0\n")
    assert 'family-names: "CHEN"' in citation
    assert 'given-names: "Zhang"' in citation
    assert "type: software" in citation
    assert "license: MIT" in citation
    assert "github.com/chenzhang0920/devsim-silicon-solar-cell-teaching" in citation


def test_ci_uses_the_canonical_environment_and_both_test_groups():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )
    environment = (ROOT / "environment.yml").read_text(encoding="utf-8")
    assert "runs-on: ubuntu-24.04-arm" in workflow
    assert "environment-ci.yml" not in workflow
    assert "environment-file: environment.yml" in workflow
    assert "miniforge-version: latest" in workflow
    assert "activate-environment: devsim_solar" in workflow
    assert "python -m pytest tests -q" in workflow
    assert "python -m pytest tests -m slow -q" in workflow
    assert "python scripts/build_slides.py --dry-run" in workflow
    assert "  - defaults\n" not in environment
    assert "  - mkl" not in environment
    assert "pytest-cov" not in environment


def test_fit_and_plot_commands_have_distinct_responsibilities():
    run_source = (ROOT / "scripts" / "run_calibration.py").read_text(encoding="utf-8")
    plot_source = (ROOT / "scripts" / "plot_fit.py").read_text(encoding="utf-8")
    assert '"software_versions"' in run_source
    assert '"fit_configuration"' in run_source
    assert '"simulation_config"' in run_source
    assert '"--params", required=True' in plot_source
    assert "fit_from_csv" not in plot_source
    assert 'metadata["simulation_config"] != SIMULATION' in plot_source


def test_saved_fit_replot_rejects_changed_input(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text("V,J\n0,1\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    _verify_hash(source, digest)
    source.write_text("V,J\n0,2\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="input changed"):
        _verify_hash(source, digest)


def test_checked_fit_parameters_use_portable_strict_json():
    path = ROOT / "results" / "fitted_params.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert "unique_symbols" not in payload
    assert payload["parameters"]["electron_lifetime"]["stderr"] is None
    fitted = load_params_json(path)
    assert set(fitted) >= {"photon_flux", "series_resistance"}


def test_checked_calibration_results_state_covariance_and_schema_contracts():
    single = json.loads(
        (ROOT / "results" / "fit_metadata.json").read_text(encoding="utf-8")
    )
    joint = json.loads(
        (ROOT / "results" / "joint_fit_metadata.json").read_text(encoding="utf-8")
    )
    metrics = json.loads(
        (ROOT / "results" / "joint_metrics.json").read_text(encoding="utf-8")
    )

    assert single["schema_version"] == joint["schema_version"] == 1
    assert "lmfit default" in single["covariance_scaling"]
    assert "not an instrument-derived" in single["covariance_scaling"]
    assert "Unscaled local Jacobian" in joint["covariance_scaling"]
    assert metrics["schema_version"] == 1


def test_repository_text_and_binary_rules_cover_portable_entry_points():
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    editorconfig = (ROOT / ".editorconfig").read_text(encoding="utf-8")
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attributes
    assert "*.ipynb text eol=lf" in attributes
    assert "*.png binary" in attributes
    assert "data/raw/keithley/*.csv -text -whitespace" in attributes
    assert "end_of_line = lf" in editorconfig
    assert ".pytest_cache/" in gitignore
    assert ".venv/" in gitignore
    assert "results/*" not in gitignore.splitlines()
    assert "results/_audit*" in gitignore


def test_raw_data_do_not_bundle_uncalibrated_power_notes():
    raw = ROOT / "data" / "raw" / "keithley"
    note = (raw / "README.md").read_text(encoding="utf-8")
    assert not (raw / "illumination_power_notes.jpg").exists()
    assert "No calibrated irradiance record is bundled" in note
    assert "not irradiance" in note


def test_saved_simulation_records_modeled_input_power_provenance():
    with (ROOT / "results" / "iv_sim.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows
    values = {float(row["modeled_input_power_W_cm2"]) for row in rows}
    assert values == {
        MODELED_INPUT_POWER_W_CM2 * float(MODEL_PARAMS["photon_flux"])
    }
