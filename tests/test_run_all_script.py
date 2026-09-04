"""Keep the aggregate Bash runner discoverable and aligned with project entry points."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_run_all_script_declares_supported_profiles():
    script = ROOT / "scripts" / "run_all.sh"
    text = script.read_text(encoding="utf-8")

    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -Eeuo pipefail" in text
    for profile in ("full|all)", "quick)", "simulation|sim)", "calibration|calibrate)",
                    "joint)", "eqe)", "synthetic)", "notebook)", "check)", "keithley)"):
        assert profile in text
    assert "config.py" in text
    assert "scripts/build_slides.py" in text
    assert "run_notebook" in text
    assert "--ExecutePreprocessor.record_timing=False" in text
    assert "--ClearMetadataPreprocessor.enabled=True" in text
    assert "--ClearMetadataPreprocessor.clear_notebook_metadata=False" in text
    assert "--only joint" in text
    assert "--only demo-data" in text
    assert "full profile intentionally does not convert raw experimental files" in text
    assert "Full always" in text and "joint --sample ID" in text
    assert text.index('profile="${1:-help}"') < text.index('PYTHON_BIN="${PYTHON_BIN:-}"')
