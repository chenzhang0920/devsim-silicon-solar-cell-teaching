"""Regression checks for the executable undergraduate tutorial notebook."""

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks" / "tutorial.ipynb"


def _notebook() -> dict:
    return json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))


def _sources() -> tuple[str, str]:
    notebook = _notebook()
    markdown = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "markdown"
    )
    code = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )
    return markdown, code


def test_notebook_is_streamlined_unique_and_ordered():
    notebook = _notebook()
    cells = notebook["cells"]
    ids = [cell.get("id") for cell in cells]
    sources = ["".join(cell.get("source", [])) for cell in cells]
    flow_markers = [
        "## 1.",
        "project_root = next(",
        "$N_D-N_A<0$",
        r"\frac{d^2\psi}{dx^2}",
        "def poisson_newton",
        "1D p\u207a-on-n silicon solar-cell model",
        "device_data = profiles",
        "eq_bands = band_edges",
        "voltage, current_density = terminal_iv",
        "## 9. External quantum efficiency (EQE)",
        "simulate_eqe(eqe_params",
        "lifetimes = np.geomspace",
        "## 11.",
        "parse_keithley",
        "fit_with_trace(",
        "## 13.",
        "joint_result = fit_joint",
        "joint_comparison_figure",
        "identifiability_figure",
        "Model scope and limitations",
        "## 16.",
    ]

    assert 20 <= len(cells) <= 35
    assert len(ids) == len(set(ids))
    positions = [
        next(index for index, source in enumerate(sources) if marker in source)
        for marker in flow_markers
    ]
    assert positions == sorted(positions)
    assert cells[-1]["cell_type"] == "markdown"
    assert "## 16." in sources[-1]


def test_physics_polarity_units_and_jv_language_are_explicit():
    markdown, code = _sources()

    assert "p⁺-on-n" in markdown
    assert r"\frac{d^2\psi}{dx^2}=-\frac{q}{\varepsilon_{Si}}" in markdown
    assert "$N_D-N_A<0$\uff08p\u207a\uff09" in markdown
    assert "generation-positive" in markdown
    assert "net = np.where(x_newton < 0.5e-4, -1e17, 1e15)" in code
    assert "history[-1][-1] - history[-1][0]" in code
    assert "built-in potential = {built_in_voltage:.4f} V" in code
    assert "\u539f\u59cb\u6587\u4ef6\u662f I\u2013V" in markdown
    assert "\u5904\u7406\u540e\u7684 J\u2013V" in markdown
    assert "\u6709\u6548\u5149\u751f\u5f3a\u5ea6\u6bd4\u4f8b" in markdown
    assert "\u79f0\u4e3a \u201csun\u201d" in markdown


def test_data_provenance_and_joint_calibration_are_complete():
    markdown, code = _sources()

    assert "\u5386\u53f2\u8bfe\u5802\u5b9e\u9a8c\u5bfc\u51fa" in markdown
    assert "data/synthetic/iv.csv" in code
    assert "fit_with_trace" in code
    assert "max_nfev=60" in code
    assert "if not synthetic_result.success" in code
    assert "load_joint_data(3)" in code
    assert "fit_joint(joint_data)" in code
    for source in (
        "light_iv",
        "dark_iv",
        "ishort_summary.csv",
        "voc_summary.csv",
    ):
        assert source in markdown + code

    assert "light_iv_sample4.csv" not in code
    assert "lab_guide_answers" not in markdown + code
    assert "joint-calibration-preview" not in markdown + code
    assert "\u672c\u4ed3\u5e93\u672a\u63d0\u4f9b\u7ecf\u6821\u51c6\u7684\u7535\u6c60\u5e73\u9762\u8f90\u7167\u5ea6\u8bb0\u5f55" in markdown


def test_animation_and_eqe_scope_avoid_misleading_extras():
    markdown, code = _sources()

    assert code.count("display_gif(") <= 2
    for removed_demo in (
        "sweep_light",
        "sweep_bias",
        "interactive_optimization",
        "ipywidgets",
        "_draw_rs",
        "_draw_rsh",
    ):
        assert removed_demo not in code

    assert "simulate_eqe" in code
    assert "eqe_integrated_jsc" in code
    assert "full_spectrum_jsc" in code
    assert "Relative mismatch" in code
    assert "data/synthetic/eqe.csv" not in markdown + code
    assert "\u6ca1\u6709\u4f2a\u88c5\u6210\u6d4b\u91cf\u503c\u7684\u5408\u6210\u6563\u70b9" in markdown
    assert "\u4e0d\u8981\u6c42\u989d\u5916 EQE \u5b9e\u9a8c\u6570\u636e" in markdown


def test_notebook_uses_portable_setup_and_the_configured_reporting_grid():
    _, code = _sources()

    assert 'print("Project root detected.")' in code
    assert 'print(f"Project root: {project_root}")' not in code
    assert "terminal_iv(MODEL_PARAMS)" in code
    assert "terminal_iv(MODEL_PARAMS, n=81" not in code
    assert "lifetimes = np.geomspace(1e-6, 1e-4, 5)" in code
    assert "quality_adequate=quality_adequate" in code


def test_code_cells_are_english_only_and_execute_without_errors():
    notebook = _notebook()
    code_cells = [
        cell for cell in notebook["cells"] if cell.get("cell_type") == "code"
    ]
    assert code_cells
    assert all("".join(cell.get("source", [])).strip() for cell in code_cells)

    code_text = "\n".join("".join(cell.get("source", [])) for cell in code_cells)
    assert re.search(r"[\u4e00-\u9fff]", code_text) is None

    assert [cell.get("execution_count") for cell in code_cells] == list(
        range(1, len(code_cells) + 1)
    )
    errors = [
        output
        for cell in code_cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "error"
    ]
    stderr = [
        output
        for cell in code_cells
        for output in cell.get("outputs", [])
        if output.get("output_type") == "stream" and output.get("name") == "stderr"
    ]
    assert errors == []
    assert stderr == []


def test_newton_teaching_demo_never_reports_false_convergence():
    _, code = _sources()
    assert "Newton iteration did not converge" in code
    assert "if final_residual >= tol * initial_residual" in code


def test_notebook_has_no_stale_widget_metadata_or_external_preview_images():
    notebook = _notebook()
    markdown, _ = _sources()
    assert "widgets" not in notebook.get("metadata", {})
    assert all("execution" not in cell.get("metadata", {}) for cell in notebook["cells"])
    assert re.findall(r"!\[[^\]]*\]\([^)]+\)", markdown) == []
