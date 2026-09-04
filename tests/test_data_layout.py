"""Guard the separation between experimental, processed, and synthetic data."""
from pathlib import Path

import pandas as pd


def test_bundled_data_are_classified_by_provenance():
    root = Path(__file__).resolve().parents[1]
    raw = root / "data" / "raw"
    processed = root / "data" / "processed"
    synthetic = root / "data" / "synthetic"

    # Native Keithley exports are immutable source measurements.
    native_names = {path.name for path in (raw / "keithley").glob("*.csv")}
    expected_native = {
        f"{condition} - {kind} -{sample}.csv"
        for condition in ("light", "dark")
        for kind in ("iv", "voc", "ishort")
        for sample in ("3", "4")
    }
    # Allow additional measured cells to be added without making the test
    # fail, while still protecting the bundled Cell #3/#4 provenance.
    assert expected_native <= native_names

    # Standardized sample files are derived from the native exports.
    for name in (
        "light_iv_sample3.csv",
        "light_iv_sample4.csv",
        "dark_iv_sample3.csv",
        "dark_iv_sample4.csv",
        "voc_summary.csv",
        "light_ishort_sample3.csv",
        "light_ishort_sample4.csv",
        "dark_ishort_sample3.csv",
        "dark_ishort_sample4.csv",
        "ishort_summary.csv",
    ):
        assert (processed / name).is_file()

    # Generated files are kept out of both experimental-data directories.
    assert (synthetic / "iv.csv").is_file()
    assert not (synthetic / "eqe.csv").exists()
    assert not (raw / "eqe.csv").exists()
    assert not (processed / "iv.csv").exists()

    voltage_at_zero_current = pd.read_csv(processed / "voc_summary.csv")
    assert "V_at_I0_V" in voltage_at_zero_current.columns
    assert "Voc_V" not in voltage_at_zero_current.columns
