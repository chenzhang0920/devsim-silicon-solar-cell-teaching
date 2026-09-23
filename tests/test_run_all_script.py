"""Keep the cross-platform runner aligned with the documented workflows."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_run_all_script_declares_supported_profiles():
    script = ROOT / "scripts" / "run_all.py"
    text = script.read_text(encoding="utf-8")

    assert text.startswith('\"\"\"Cross-platform entry point')
    for profile in (
        'profile in {"full", "all"}',
        'profile == "quick"',
        'profile in {"simulation", "sim"}',
        'profile == "sweep"',
        'profile in {"calibration", "calibrate"}',
        'profile == "joint"',
        'profile == "eqe"',
        'profile == "synthetic"',
        'profile == "notebook"',
        'profile == "check"',
        'profile == "keithley"',
    ):
        assert profile in text
    assert "subprocess.run" in text
    assert "sys.executable" in text
    assert "scripts/build_results.py" in text
    assert "run_notebook" in text
    assert "--ExecutePreprocessor.record_timing=False" in text
    assert "--ClearMetadataPreprocessor.enabled=True" in text
    assert "--ClearMetadataPreprocessor.clear_notebook_metadata=False" in text
    assert '"--only", "joint"' in text
    assert '"--only", "demo-data"' in text
    assert "full profile intentionally does not convert raw experimental files" in text
    assert "Full always" in text and "joint --sample ID" in text
    assert "Recommended first run:" in text
    assert "python scripts/run_all.py full --dry-run" in text
    assert "python -m jupyter lab notebooks/tutorial.ipynb" in text
    assert "python scripts/run_all.py notebook" in text
    assert "Replace 12.0 with the recorded illuminated area" in text
    assert "Python command:" in text
    assert "Runtime:" in text
    assert "Run the standard hole-lifetime sensitivity sweep" in text
    assert "Windows PowerShell, macOS Terminal, and Linux shells" in text


def test_run_all_help_does_not_require_devsim():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_all.py"), "help"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert "Usage: python scripts/run_all.py" in result.stdout
    assert "Windows PowerShell, macOS Terminal, and Linux shells" in result.stdout
