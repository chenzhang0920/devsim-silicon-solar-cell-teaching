"""Tests for loss-aware conversion of student measurement files."""

import sys

import pandas as pd
import pytest

from scripts import make_demo_data, prepare_data, prepare_keithley
from scripts.prepare_keithley import (
    classify_keithley_filename,
    remove_stale_converter_outputs,
    to_solar_cell,
    voltage_at_zero_current_from_file,
)


@pytest.mark.parametrize(
    ("unit", "quantity"),
    [("A", "voltage"), ("V", "current")],
)
def test_generic_converter_rejects_dimensionally_wrong_units(unit, quantity):
    with pytest.raises(SystemExit, match=quantity):
        prepare_data._parse_unit_arg(unit, quantity)


def test_generic_converter_averages_repeated_voltages(monkeypatch, tmp_path, capsys):
    source = tmp_path / "raw.csv"
    output = tmp_path / "measured.csv"
    pd.DataFrame({
        "V": [0.0, 0.0, 0.4, 0.7],
        "I": [0.01, 0.03, 0.01, -0.01],
    }).to_csv(source, index=False)
    monkeypatch.setattr(sys, "argv", [
        "prepare_data.py", str(source), "--area", "1",
        "--current-unit", "A", "--out", str(output),
    ])

    prepare_data.main()

    converted = pd.read_csv(output)
    assert converted["V"].tolist() == pytest.approx([0.0, 0.4, 0.7])
    assert converted["J"].tolist() == pytest.approx([0.02, 0.01, -0.01])
    assert "Averaged 1 repeated voltage rows" in capsys.readouterr().out


def test_generic_converter_applies_explicit_voltage_and_current_signs(monkeypatch, tmp_path):
    source = tmp_path / "raw_opposite_polarity.csv"
    output = tmp_path / "measured.csv"
    pd.DataFrame({
        "V": [0.0, -0.4, -0.7],
        "I": [-0.03, -0.02, 0.01],
    }).to_csv(source, index=False)
    monkeypatch.setattr(sys, "argv", [
        "prepare_data.py", str(source), "--area", "1",
        "--current-unit", "A", "--voltage-sign", "-1",
        "--current-sign", "-1", "--out", str(output),
    ])

    prepare_data.main()

    converted = pd.read_csv(output)
    assert converted["V"].tolist() == pytest.approx([0.0, 0.4, 0.7])
    assert converted["J"].tolist() == pytest.approx([0.03, 0.02, -0.01])


def test_generic_converter_never_overwrites_its_raw_input(monkeypatch, tmp_path):
    source = tmp_path / "raw.csv"
    pd.DataFrame({"V": [0.0, 0.4, 0.7], "I": [30.0, 20.0, -1.0]}).to_csv(
        source, index=False
    )
    original = source.read_bytes()
    monkeypatch.setattr(sys, "argv", [
        "prepare_data.py", str(source), "--area", "1", "--out", str(source),
    ])

    with pytest.raises(SystemExit, match="must not overwrite"):
        prepare_data.main()
    assert source.read_bytes() == original


def test_generic_converter_cannot_mix_measurements_into_synthetic_data(
        monkeypatch, tmp_path):
    source = tmp_path / "raw.csv"
    pd.DataFrame({"V": [0.0, 0.4, 0.7], "I": [30.0, 20.0, -1.0]}).to_csv(
        source, index=False
    )
    monkeypatch.setattr(sys, "argv", [
        "prepare_data.py", str(source), "--area", "1",
        "--out", "data/synthetic/not-a-measurement.csv",
    ])

    with pytest.raises(SystemExit, match="data/synthetic"):
        prepare_data.main()


def test_generic_converter_reports_non_numeric_columns_cleanly(monkeypatch, tmp_path):
    source = tmp_path / "raw.csv"
    output = tmp_path / "measured.csv"
    pd.DataFrame({"V": [0.0, 0.4, "bad"], "I": [30.0, 20.0, -1.0]}).to_csv(
        source, index=False
    )
    monkeypatch.setattr(sys, "argv", [
        "prepare_data.py", str(source), "--area", "1", "--out", str(output),
    ])

    with pytest.raises(SystemExit, match="must contain numeric"):
        prepare_data.main()


def test_keithley_converter_applies_explicit_signs_and_averages_repeats():
    voltage, current = to_solar_cell(
        [-0.1, -0.1, -0.2], [1.0, 3.0, 4.0], area=2.0,
        voltage_sign=-1, current_sign=-1,
    )
    assert voltage.tolist() == pytest.approx([0.1, 0.2])
    assert current.tolist() == pytest.approx([-1.0, -2.0])


def test_keithley_filename_classification_is_case_insensitive():
    assert classify_keithley_filename("Light - IV - 3.csv") == ("light", "iv", 3)
    assert classify_keithley_filename("notes.csv") is None


def test_keithley_voc_file_must_actually_be_near_zero_current(tmp_path):
    source = tmp_path / "light - voc - 3.csv"
    source.write_text(
        "instrument export\n\u7d22\u5f15,\u7535\u538b (V),\u7535\u6d41 (A)\n1,-0.64,0.001\n2,-0.65,0.002\n3,-0.66,0.001\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="labeled as a zero-current"):
        voltage_at_zero_current_from_file(source, current_tolerance=1e-8)


def test_keithley_parser_accepts_english_locale_headers(tmp_path):
    source = tmp_path / "english.csv"
    source.write_text(
        "instrument export\nIndex,Time (s),Voltage (V),Current (A)\n"
        "1,0,-0.1,0.03\n2,1,-0.2,0.02\n",
        encoding="utf-8",
    )

    voltage, current = prepare_keithley.parse_keithley(source)

    assert voltage.tolist() == pytest.approx([-0.1, -0.2])
    assert current.tolist() == pytest.approx([0.03, 0.02])


def test_keithley_parser_rejects_unscaled_millivolt_or_milliamp_headers(tmp_path):
    source = tmp_path / "wrong_units.csv"
    source.write_text(
        "instrument export\nIndex,Voltage (mV),Current (mA)\n1,-100,30\n2,-200,20\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"must declare \(V\)"):
        prepare_keithley.parse_keithley(source)


def test_keithley_cleanup_removes_only_stale_converter_outputs(tmp_path):
    current = tmp_path / "light_iv_sample3.csv"
    stale = tmp_path / "dark_iv_sample4.csv"
    unrelated = tmp_path / "measured_iv.csv"
    for path in (current, stale, unrelated):
        path.write_text("V,J\n", encoding="utf-8")

    removed = remove_stale_converter_outputs(tmp_path, {current.name})

    assert removed == [stale.name]
    assert current.exists()
    assert unrelated.exists()


def test_keithley_main_preserves_other_samples_unless_prune_is_requested(
        monkeypatch, tmp_path):
    raw = tmp_path / "raw"
    out = tmp_path / "processed"
    raw.mkdir()
    out.mkdir()
    (raw / "light - iv - 3.csv").write_text(
        "instrument export\n\u7d22\u5f15,\u7535\u538b (V),\u7535\u6d41 (A)\n1,0,0.03\n2,-0.3,0.02\n3,-0.7,-0.01\n",
        encoding="utf-8",
    )
    (raw / "dark - iv - 3.csv").write_text(
        "instrument export\n\u7d22\u5f15,\u7535\u538b (V),\u7535\u6d41 (A)\n1,0,0\n2,-0.3,-0.001\n3,-0.7,-0.01\n",
        encoding="utf-8",
    )
    (raw / "light - voc - 3.csv").write_text(
        "instrument export\n\u7d22\u5f15,\u7535\u538b (V),\u7535\u6d41 (A)\n1,-0.64,0\n2,-0.65,0\n3,-0.66,0\n",
        encoding="utf-8",
    )
    (raw / "light - ishort - 3.csv").write_text(
        "instrument export\n\u7d22\u5f15,\u7535\u538b (V),\u7535\u6d41 (A)\n1,0,0.030\n2,0,0.031\n3,0,0.029\n",
        encoding="utf-8",
    )
    other_sample = out / "dark_iv_sample4.csv"
    other_sample.write_text("V,J\n0,0\n", encoding="utf-8")
    pd.DataFrame({
        "sample": [4], "condition": ["light"], "V_at_I0_V": [0.62],
    }).to_csv(out / "voc_summary.csv", index=False)
    pd.DataFrame({
        "sample": [4], "condition": ["light"],
        "J_mean_A_cm2": [0.04], "J_std_A_cm2": [0.001],
        "V_mean_V": [0.0], "V_std_V": [0.0], "n_points": [3],
    }).to_csv(out / "ishort_summary.csv", index=False)
    base_args = [
        "prepare_keithley.py", "--area", "1", "--data", str(raw),
        "--out-dir", str(out),
    ]

    monkeypatch.setattr(sys, "argv", base_args)
    prepare_keithley.main()
    assert other_sample.exists()
    assert set(pd.read_csv(out / "voc_summary.csv")["sample"]) == {3, 4}
    assert set(pd.read_csv(out / "ishort_summary.csv")["sample"]) == {3, 4}

    monkeypatch.setattr(sys, "argv", [*base_args, "--prune"])
    prepare_keithley.main()
    assert not other_sample.exists()
    assert set(pd.read_csv(out / "voc_summary.csv")["sample"]) == {3}
    assert set(pd.read_csv(out / "ishort_summary.csv")["sample"]) == {3}


def test_keithley_converter_rejects_output_under_project_raw(monkeypatch, tmp_path):
    raw = tmp_path / "input"
    raw.mkdir()
    (raw / "light - iv - 3.csv").write_text(
        "instrument export\n\u7d22\u5f15,\u7535\u538b (V),\u7535\u6d41 (A)\n1,0,0.03\n2,-0.3,0.02\n3,-0.7,-0.01\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(sys, "argv", [
        "prepare_keithley.py", "--area", "1", "--data", str(raw),
        "--out-dir", "data/raw/generated",
    ])

    with pytest.raises(SystemExit, match="immutable data/raw"):
        prepare_keithley.main()


def test_keithley_converter_rejects_output_under_synthetic(monkeypatch, tmp_path):
    raw = tmp_path / "input"
    raw.mkdir()
    monkeypatch.setattr(sys, "argv", [
        "prepare_keithley.py", "--area", "1", "--data", str(raw),
        "--out-dir", "data/synthetic/measurements",
    ])

    with pytest.raises(SystemExit, match="data/synthetic"):
        prepare_keithley.main()


def test_keithley_validation_failure_does_not_overwrite_processed_curve(
        monkeypatch, tmp_path):
    raw = tmp_path / "input"
    out = tmp_path / "processed"
    raw.mkdir()
    out.mkdir()
    (raw / "light - iv - 3.csv").write_text(
        "instrument export\n\u7d22\u5f15,\u7535\u538b (V),\u7535\u6d41 (A)\n"
        "1,0,-0.03\n2,-0.3,-0.02\n3,-0.7,0.01\n",
        encoding="utf-8",
    )
    target = out / "light_iv_sample3.csv"
    original = b"V,J\n0,0.03\n"
    target.write_bytes(original)
    monkeypatch.setattr(sys, "argv", [
        "prepare_keithley.py", "--area", "1", "--data", str(raw),
        "--out-dir", str(out),
    ])

    with pytest.raises(ValueError, match="generation-positive"):
        prepare_keithley.main()
    assert target.read_bytes() == original


def test_keithley_measurement_like_filename_typo_is_not_silently_ignored(
        monkeypatch, tmp_path):
    raw = tmp_path / "input"
    raw.mkdir()
    (raw / "light - ivv - 3.csv").write_text("not parsed\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "prepare_keithley.py", "--area", "1", "--data", str(raw),
        "--out-dir", str(tmp_path / "processed"),
    ])

    with pytest.raises(SystemExit, match="does not match"):
        prepare_keithley.main()


@pytest.mark.parametrize("noise", [-0.01, float("nan"), float("inf")])
def test_synthetic_generator_rejects_invalid_noise_before_simulation(noise):
    with pytest.raises(ValueError, match="noise_frac"):
        make_demo_data.make_iv(seed=42, noise_frac=noise)


def test_synthetic_generator_cannot_write_into_raw_data(monkeypatch):
    monkeypatch.setattr(sys, "argv", [
        "make_demo_data.py", "--iv-out", "data/raw/not-a-measurement.csv",
    ])

    with pytest.raises(SystemExit, match="inside data/synthetic"):
        make_demo_data.main()
