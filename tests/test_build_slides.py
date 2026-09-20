"""Checks for generated assets and classroom-slide content."""
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


def test_student_deck_matches_build_and_data_requirements():
    """Keep the slide deck aligned with generated assets and course data."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "docs" / "lab_slides.html").read_text(encoding="utf-8")

    assert "data/processed/my_iv.csv" not in html
    assert "python scripts/plot_optimization.py --params photon_flux" in html
    assert "--max-nfev 30 --gif" in html
    assert "python scripts/run_calibration.py --joint --sample &lt;sample-id&gt;" in html
    assert "python scripts/plot_profiles.py --bias near-voc" in html
    assert "python scripts/plot_band.py --bias near-voc" in html
    assert html.index("External quantum efficiency") < \
        html.index("Calibration as an inverse problem")
    assert "plot_sweep.py --param hole_lifetime --start 1e-6 --stop 1e-4 --n 5" in html
    assert html.index("Joint calibration with complementary data") < \
        html.index("Evaluating model–data adequacy")
    assert html.index("Evaluating model–data adequacy") < \
        html.index("From residual to scientific decision") < \
        html.index("Student workflow")
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
    assert "p⁺ emitter" in html
    assert 'class="slide closing"' in html
    assert len(re.findall(r'<section class="slide', html)) == 25
    assert "@media (min-width:1101px) and (max-height:720px)" in html
    assert html.count("data-step=") == 25
    assert re.findall(r'data-step="([0-9]{2})"', html) == [
        f"{i:02d}" for i in range(1, 26)
    ]
    assert 'class="kicker"' not in html
    assert 'class="card"' not in html
    assert 'class="takeaway"' not in html
    assert ".slide:has(> .command)" in html
    assert 'class="cover-device"' in html
    assert 'class="electrostatic-plot"' in html
    assert 'class="mesh-figure"' in html
    assert 'class="content calibration-layout"' in html
    assert 'class="content quality-layout"' in html
    assert "../results/joint_identifiability.png" not in html
    assert "p, li, td, th, dd { font-size:1.55rem; }" in html
    assert ".small { color:var(--muted); font-size:1.3rem; }" in html
    assert "font-size:1.25rem; font-weight:650; font-family" in html
    assert "font-size:clamp(2.35rem,3.5vw,3.25rem)" in html
    assert "DEVSIM in semiconductor TCAD" in html
    assert "DEVSIM and Crosslight APSYS" in html
    assert "Running the course model" in html
    assert "python -m jupyter lab notebooks/tutorial.ipynb" in html
    assert "python scripts/run_all.py full --dry-run" in html
    assert "python scripts/run_all.py simulation" in html
    assert "python scripts/run_all.py keithley --area 12.0" in html
    assert "python scripts/run_all.py joint --sample 3" in html
    assert "python scripts/run_all.py full" in html
    assert "Device, coordinates and external circuit" in html
    assert "The complete mathematical problem" in html
    assert "Abrupt-junction electrostatics" in html
    assert "Poisson and drift–diffusion equations" in html
    assert "Generation and recombination" in html
    assert "Boundary conditions and terminal mapping" in html
    assert "Numerical solution" in html
    assert "Scharfetter–Gummel flux" in html
    assert "Calibration as an inverse problem" in html
    assert "The model contains more parameters than the present measurements can identify" in html
    assert "Bounded least-squares calibration" in html
    assert r"Q=\frac{\lVert\boldsymbol{r}\rVert_2^2}" in html
    assert "Determine the result for your assigned dataset" in html
    assert "Four complementary observable blocks" in html
    assert "Four independent checks" not in html
    assert "Test one sensitivity-supported physical hypothesis." in html
    assert "course threshold is an adequacy screen" in html
    decision_slide = re.search(
        r'<section class="slide" data-step="24" '
        r'data-title="From residual to scientific decision">(.*?)</section>',
        html,
        re.DOTALL,
    ).group(1)
    for step in ("Observe", "Verify", "Test one", "Decide"):
        assert step in decision_slide
    assert "verified, missing or inconsistent" in decision_slide
    assert "Evidence to record" in decision_slide
    assert "dominant block, sign, voltage range and objective share" in decision_slide
    assert "voltage resolution near the knee" in decision_slide
    assert "dark-current reach relative to illuminated current" in decision_slide
    assert "agreement between sweeps and separate checks" in decision_slide
    assert "Decision to defend" in decision_slide
    assert "accept a limited claim" in decision_slide
    assert "Student workflow" in html
    assert 'href="https://zenodo.org/records/17328734"' in html

    refs = set(re.findall(r'src="\.\./results/([^"]+)"', html))
    declared = {
        Path(product).name
        for _, _, _, products, _ in build.STEPS
        for product in products
        if Path(product).parent.as_posix() == "results"
    }
    assert refs <= declared
    names = [step[0] for step in build.STEPS]
    assert "calibration" not in names
    assert names.index("demo-data") < names.index("iv") < names.index("joint")
    demo_step = next(step for step in build.STEPS if step[0] == "demo-data")
    assert demo_step[3] == ["data/synthetic/iv.csv"]
    sweep_step = next(step for step in build.STEPS if step[0] == "sweep")
    assert sweep_step[2] == [
        "--param", "hole_lifetime", "--start", "1e-6",
        "--stop", "1e-4", "--n", "5",
    ]


def test_course_website_has_valid_local_assets_and_student_entry_points():
    root = Path(__file__).resolve().parents[1]
    html = (root / "index.html").read_text(encoding="utf-8")
    assert ".core-system { grid-template-columns: minmax(0, 1fr); }" in html

    assert "MICS3090 (L01)" in html
    assert "p<sup>+</sup>-on-n" in html
    assert 'href="docs/lab_slides.html"' in html
    assert ".pptx" not in html
    assert "notebooks/tutorial.ipynb" in html
    assert "docs/lab_guide.md" in html
    assert "docs/experiment_protocol.md" in html
    assert "docs/grading.md" in html
    assert "python scripts/run_all.py full --dry-run" in html
    assert "python scripts/run_all.py simulation" in html
    assert "python -m jupyter lab notebooks/tutorial.ipynb" in html
    assert "python scripts/run_all.py keithley --area 12.0" in html
    assert "python scripts/run_all.py joint --sample 3" in html
    assert "python scripts/run_all.py check" in html
    assert "skip step 3 when using the supplied processed data" in html
    assert 'href="https://zenodo.org/records/17328734"' in html
    assert "Zhang CHEN" in html
    assert "zchen758@connect.hkust-gz.edu.cn" in html
    assert 'id="model"' in html
    assert 'id="device-circuit-title"' in html
    assert "flows through an external load" in html
    assert "I = AJ" in html
    assert "schematic not to scale" in html
    assert "Begin with the complete mathematical problem" in html
    assert "Problem statement." in html
    assert "Solved self-consistently" in html
    assert "Prescribed model inputs" in html
    assert "Calculated after the PDE solve" in html
    assert "solve the internal one-dimensional silicon PDE model" in html
    assert "solve the intrinsic one-dimensional silicon device" not in html
    assert r"\boldsymbol{u}(x)=[\psi(x),n(x),p(x)]^{\mathsf T}" in html
    assert "Unknowns</strong><span>\\(\\psi(x)\\), \\(n(x)\\), and \\(p(x)\\)" in html
    assert "Boltzmann statistics, complete dopant ionization" in html
    assert "band-gap narrowing and Fermi–Dirac degeneracy" in html
    assert "it does not mean an intrinsic silicon layer" in html
    assert r"V_{\mathrm{bi}}\simeq0.95\ \mathrm V" in html
    assert "the solver uses cm–V–s units" in html
    assert "Which equations are solved in the silicon?" in html
    assert "Core PDE system" in html
    assert "three unknown fields and three coupled conservation equations" in html
    assert "Scharfetter–Gummel Bernoulli edge form" in html
    assert "What is imposed at \\(x=0\\) and \\(x=L\\)?" in html
    assert r"n(0)=n_{c,\mathrm{front}}" in html
    assert "Boundary-condition count" in html
    assert r"V_{\mathrm j}>0\) is forward bias" in html
    assert "Thermal equilibrium" in html and "Dark J–V" in html and "EQE" in html
    assert r"V_{\mathrm{back}}=0\) is the electrical reference" in html
    assert r"R_{\mathrm s}\)/\(R_{\mathrm{sh}}\) terminal mapping" in html
    assert r"external \(R_{\mathrm s}\)/\(R_{\mathrm{sh}}\) mapping disabled" in html
    assert "shunt_resistance = 0" in html
    assert "Forward problem:" in html and "Inverse problem:" in html
    assert "Baseline forward-model inputs" in html
    assert "it is not a measured irradiance" in html
    assert "raw instrument files are not direct PDE inputs" in html
    assert "Area is experimental metadata" in html
    assert r"A=3\ \mathrm{cm}\times4\ \mathrm{cm}=12\ \mathrm{cm^2}" in html
    assert r"0.1\ \mathrm{W\,cm^{-2}}\) input-power value is an illustrative reporting convention" in html
    assert "Solve equilibrium Poisson with both external contact biases at zero" in html
    assert r"J_n\simeq J_p\simeq0" in html
    assert 'id="physics"' in html
    assert "Now interpret the model one mechanism at a time" in html
    assert "Question 1 · Junction electrostatics" in html
    assert "Question 5 · From device solution to measured data" in html
    assert r"\frac{\mathrm d^2\psi}{\mathrm d x^2}" in html
    assert r"J_n=q\mu_n nE" in html
    assert r"R_{\mathrm{SRH}}" in html
    assert r"V_{\mathrm{term}}=V_{\mathrm j}" in html
    assert "illuminated J–V, dark J–V, separately acquired \\(J_{\\mathrm{sc}}\\)" in html
    assert "Only \\(s\\) (<code>photon_flux</code>) and \\(R_{\\mathrm s}\\) vary" in html
    assert r"not a reduced \(\chi^2\) test" in html
    assert "out-of-sample check" not in html
    assert "not held-out validation data" not in html

    assert "Your analysis:" in html
    assert "calculate the score for the assigned dataset" in html
    assert "Current Cell #3 snapshot" not in html

    local_refs = re.findall(r'(?:href|src)="((?!https?:|mailto:|#)[^"]+)"', html)
    assert local_refs
    assert all((root / ref).is_file() for ref in local_refs)


def test_public_student_slides_do_not_publish_reference_answers():
    root = Path(__file__).resolve().parents[1]
    html = (root / "docs" / "lab_slides.html").read_text(encoding="utf-8")

    assert "Joint calibration with complementary data" in html
    assert "Determine the result for your assigned dataset" in html
    assert "Cell #3 evidence" not in html
    assert "Q=15.1" not in html
    assert "Remeasure first" not in html


def test_course_website_preserves_editorial_reading_and_wide_data_layout():
    """Keep prose readable while allowing equations, tables, and figures to use the viewport."""
    root = Path(__file__).resolve().parents[1]
    html = (root / "index.html").read_text(encoding="utf-8")

    assert "--reader: 840px" in html
    assert "--wide: 1440px" in html
    assert "Recommended path:" in html
    assert ".section-head { max-width: var(--reader)" in html
    assert ".model-block > h3" in html
    assert ".model-equation-table { overflow-x: auto" in html
    assert "display: grid; grid-template-columns: repeat(2, minmax(0, 1fr))" in html
    assert 'grid-template-areas: "profiles eqe" "calibration calibration"' in html
    assert 'class="figure-calibration"' in html
    assert html.count("Open full-size figure") == 3
