"""Checks for consistent mathematical notation in course materials."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_web_materials_use_pinned_mathjax_and_tex_notation():
    pages = [ROOT / "index.html"]
    for page in pages:
        html = page.read_text(encoding="utf-8")
        assert "mathjax@3.2.2/es5/tex-chtml.js" in html
        assert r"J_{\mathrm{sc}}" in html
        assert r"V_{\mathrm{oc}}" in html
        assert r"\varepsilon_{\mathrm{Si}}" in html
        assert r"N_{\mathrm D}" in html
        assert r"N_{\mathrm A}" in html


def test_readme_and_notebook_share_the_canonical_symbols():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    notebook = json.loads(
        (ROOT / "notebooks" / "tutorial.ipynb").read_text(encoding="utf-8")
    )
    markdown = "".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "markdown"
    )
    for symbol in (
        r"J_{\mathrm{sc}}",
        r"V_{\mathrm{oc}}",
        r"N_{\mathrm D}",
        r"N_{\mathrm A}",
        r"\varepsilon_{\mathrm{Si}}",
        r"\boldsymbol{u}",
        r"\mathrm d",
    ):
        assert symbol in readme
        assert symbol in markdown


def test_generated_figure_sources_use_upright_units_and_descriptive_subscripts():
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "scripts" / "plot_iv.py",
            ROOT / "scripts" / "plot_profiles.py",
            ROOT / "scripts" / "plot_spectrum.py",
            ROOT / "scripts" / "plot_sweep.py",
            ROOT / "calibration" / "report.py",
        )
    )
    assert r"J_{\mathrm{sc}}" in sources
    assert r"V_{\mathrm{oc}}" in sources
    assert r"N_{\mathrm{A}}" in sources
    assert r"N_{\mathrm{D}}" in sources
    assert r"\mathrm{mA\,cm^{-2}}" in sources
