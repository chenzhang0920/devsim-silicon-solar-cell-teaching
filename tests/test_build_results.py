"""Checks for the public result builder and website entry points."""

from pathlib import Path

import pytest

import scripts.build_results as build


ROOT = Path(__file__).resolve().parents[1]


def test_result_check_reports_missing_or_empty_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(build, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(build, "STEPS", [
        ("demo", "scripts/example.py", [], ["results/demo.png", "results/empty.png"], False),
    ])
    results = tmp_path / "results"
    results.mkdir()
    (results / "empty.png").write_bytes(b"")

    assert build._check_results() == ["results/demo.png", "results/empty.png"]
    (results / "demo.png").write_bytes(b"image")
    (results / "empty.png").write_bytes(b"image")
    assert build._check_results() == []


def test_check_mode_fails_for_missing_results(monkeypatch, tmp_path):
    monkeypatch.setattr(build, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(build, "STEPS", [
        ("demo", "scripts/example.py", [], ["results/demo.png"], False),
    ])
    monkeypatch.setattr(build.sys, "argv", ["build_results.py", "--check"])
    with pytest.raises(SystemExit, match="1"):
        build.main()


def test_build_order_keeps_data_before_figures_and_calibration():
    names = [step[0] for step in build.STEPS]
    assert names.index("demo-data") < names.index("iv") < names.index("joint")
    assert names.index("sim") < names.index("profiles") < names.index("band")


def test_website_uses_available_student_entry_points():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert "Student slides" not in html
    for entry in (
        "notebooks/tutorial.ipynb",
        "docs/setup.md",
        "docs/lab_guide.md",
        "docs/experiment_protocol.md",
        "docs/grading.md",
    ):
        assert entry in html
        assert (ROOT / entry).is_file()
    for image in ("profiles.png", "eqe.png", "iv_plot.png"):
        assert f"results/{image}" in html
        assert (ROOT / "results" / image).is_file()
