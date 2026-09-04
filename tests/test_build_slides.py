'Utilities for tests/test_build_slides.py.'
import re
from pathlib import Path

import pytest

import scripts.build_slides as build


def test_check_slides_reports_missing_html(monkeypatch, tmp_path):
    missing = tmp_path / "missing.html"
    monkeypatch.setattr(build, "SLIDES", missing)
    assert build._check_slides() == [str(missing)]


def test_check_slides_reports_empty_html(monkeypatch, tmp_path):
    empty = tmp_path / "empty.html"
    empty.write_bytes(b"")
    monkeypatch.setattr(build, "SLIDES", empty)
    assert build._check_slides() == [str(empty)]


def test_check_mode_exits_nonzero_when_assets_missing(monkeypatch, tmp_path):
    slides = tmp_path / "slides.html"
    slides.write_text('<img src="../results/missing.png">', encoding="utf-8")
    monkeypatch.setattr(build, "SLIDES", slides)
    monkeypatch.setattr(build, "PROJECT_ROOT", Path(tmp_path))
    monkeypatch.setattr(build.sys, "argv", ["build_slides.py", "--check"])
    with pytest.raises(SystemExit) as exc:
        build.main()
    assert exc.value.code == 1


def test_check_slides_rejects_stale_undeclared_asset(monkeypatch, tmp_path):
    slides = tmp_path / "slides.html"
    slides.write_text('<img src="../results/stale.png">', encoding="utf-8")
    results = tmp_path / "results"
    results.mkdir()
    (results / "stale.png").write_bytes(b"old")
    monkeypatch.setattr(build, "SLIDES", slides)
    monkeypatch.setattr(build, "PROJECT_ROOT", Path(tmp_path))
    assert build._check_slides() == ["undeclared:stale.png"]


def test_check_slides_rejects_an_empty_declared_asset(monkeypatch, tmp_path):
    slides = tmp_path / "slides.html"
    slides.write_text('<img src="../results/iv_plot.png">', encoding="utf-8")
    results = tmp_path / "results"
    results.mkdir()
    (results / "iv_plot.png").write_bytes(b"")
    monkeypatch.setattr(build, "SLIDES", slides)
    monkeypatch.setattr(build, "PROJECT_ROOT", Path(tmp_path))

    assert build._check_slides() == ["missing:iv_plot.png"]


def test_check_slides_reports_missing_local_asset(monkeypatch, tmp_path):
    slides = tmp_path / "slides.html"
    slides.write_text('<img src="cover.jpg">', encoding="utf-8")
    monkeypatch.setattr(build, "SLIDES", slides)
    monkeypatch.setattr(build, "PROJECT_ROOT", Path(tmp_path))
    assert build._check_slides() == ["missing:cover.jpg"]


def test_student_deck_matches_build_and_data_contracts():
    """Keep the student deck aligned with generated assets and course metadata."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "docs" / "lab_slides.html").read_text(encoding="utf-8")

    assert "data/processed/my_iv.csv" not in html
    assert "python scripts/plot_optimization.py --params photon_flux" in html
    assert "--max-nfev 30 --gif" in html
    assert "python scripts/run_calibration.py --joint --sample 3" in html
    assert "python scripts/plot_profiles.py --bias near-voc" in html
    assert "python scripts/plot_band.py --bias near-voc" in html
    assert html.index("Task 2 · Spectral response") < html.index("Task 3 · Before fitting")
    assert "plot_sweep.py --param hole_lifetime --start 1e-6 --stop 1e-4 --n 5" in html
    assert html.index("Task 4 · Historical measured data") < \
        html.index("Task 5 · Trust the parameter?")
    assert "synthetic/eqe.csv" not in html
    assert "overview.png" not in html
    assert "--bias 0.61" not in html

    assert "MICS3090 (L01) · Integrated Circuit Devices" in html
    assert html.count("Renjie WANG") == 2
    assert html.count("Zhang CHEN") == 2
    assert html.count("zchen758@connect.hkust-gz.edu.cn") >= 2
    assert html.count("W2-4F-028") == 2
    assert html.count("TA office W2-4F-028") == 2
    assert 'class="global-logo" src="logo1_HKUSTGZ.png"' in html
    assert (root / "docs" / "logo1_HKUSTGZ.png").is_file()
    assert 'class="device-emblem"' in html
    assert "p⁺ emitter" in html
    assert 'class="slide closing-slide"' in html
    assert len(re.findall(r'<section class="slide', html)) == 16
    assert "@media (min-width:1101px) and (max-height:720px)" in html
    assert html.count('class="kicker"') == html.count('data-step=') == 16
    assert ".kicker::before" in html
    assert "p { font-size:1.25rem; }" in html
    assert "ul > li { font-size:1.25rem;" in html
    assert "pre {" in html and "font-size:1.12rem;" in html
    assert "p, ul > li { font-size:1.25rem;" in html
    assert "pre { font-size:1.2rem;" in html

    refs = set(re.findall(r'src="\.\./results/([^"]+)"', html))
    declared = {
        Path(product).name
        for _, _, _, products, _ in build.STEPS
        for product in products
        if Path(product).parent.as_posix() == "results"
    }
    assert refs <= declared
    names = [step[0] for step in build.STEPS]
    assert names.index("demo-data") < names.index("iv") < names.index("calibration")
    demo_step = next(step for step in build.STEPS if step[0] == "demo-data")
    assert demo_step[3] == ["data/synthetic/iv.csv"]
    sweep_step = next(step for step in build.STEPS if step[0] == "sweep")
    assert sweep_step[2] == [
        "--param", "hole_lifetime", "--start", "1e-6",
        "--stop", "1e-4", "--n", "5",
    ]
