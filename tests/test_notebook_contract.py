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


def _cell_source(cell_id: str) -> str:
    return next(
        "".join(cell.get("source", []))
        for cell in _notebook()["cells"]
        if cell.get("id") == cell_id
    )


def test_notebook_is_streamlined_unique_and_ordered():
    notebook = _notebook()
    cells = notebook["cells"]
    ids = [cell.get("id") for cell in cells]
    sources = ["".join(cell.get("source", [])) for cell in cells]
    flow_markers = [
        "## 1. Learning Objectives and Notebook Workflow",
        "project_root = next(",
        "$N_D-N_A<0$",
        r"\frac{d^2\psi}{dx^2}",
        "def poisson_newton",
        "1D p\u207a-on-n silicon solar-cell model",
        "device_data = profiles",
        "eq_bands = band_edges",
        "voltage, current_density = terminal_iv",
        "## 9. External Quantum Efficiency (EQE)",
        "simulate_eqe(eqe_params",
        "lifetimes = np.geomspace",
        "## 11. Data Provenance: Raw, Processed, and Synthetic Data",
        "parse_keithley",
        "fit_with_trace(",
        "## 13. Joint Calibration of Cell #3: Complementary Observations Constrain Different Model Responses",
        "joint_result = fit_joint",
        "joint_comparison_figure",
        "identifiability_figure",
        "## 15. Model Scope and Limitations",
        "## 16. Summary and Next Steps",
    ]

    assert 20 <= len(cells) <= 35
    assert all(ids)
    assert len(ids) == len(set(ids))
    assert all(
        sum(marker in source for source in sources) == 1
        for marker in flow_markers
    )
    positions = [
        next(index for index, source in enumerate(sources) if marker in source)
        for marker in flow_markers
    ]
    assert all(left < right for left, right in zip(positions, positions[1:]))
    assert cells[-1]["cell_type"] == "markdown"
    assert "## 16. Summary and Next Steps" in sources[-1]


def test_physics_polarity_units_and_jv_language_are_explicit():
    markdown, code = _sources()
    structure = _cell_source("device-structure")
    equations = _cell_source("equations-signs").casefold()
    provenance = _cell_source("data-provenance").casefold()

    assert "p⁺-on-n" in structure
    assert r"\frac{d^2\psi}{dx^2}=-\frac{q}{\varepsilon_{Si}}" in markdown
    assert "$N_D-N_A<0$ (p⁺ emitter)" in structure
    assert "generation-positive" in structure
    assert "net = np.where(x_newton < 0.5e-4, -1e17, 1e15)" in code
    assert "history[-1][-1] - history[-1][0]" in code
    assert "built-in potential = {built_in_voltage:.4f} V" in code
    assert "raw files contain instrument voltage and current" in provenance
    assert "processed curves are reported as voltage and current density" in provenance
    assert "effective photogeneration scale factor" in equations
    assert "not a calibrated" in equations
    assert "sun" in equations
    assert "independently calibrated irradiance" in equations


def test_data_provenance_and_joint_calibration_are_complete():
    markdown, code = _sources()
    provenance = _cell_source("data-provenance").casefold()

    assert "historical teaching-laboratory exports" in provenance
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
    assert "no calibrated cell-plane irradiance record is provided" in provenance


def test_animation_and_eqe_scope_avoid_misleading_extras():
    markdown, code = _sources()
    eqe_scope = _cell_source("eqe-notes").casefold()

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
    assert "all_bin_jsc" in code
    assert "All-bin Jsc" in code
    assert "all-bin model" in code
    assert "Full-spectrum" not in markdown + code
    assert "Relative mismatch" in code
    assert "data/synthetic/eqe.csv" not in markdown + code
    assert "no experimental eqe measurements are included" in eqe_scope
    assert "does not require additional measured eqe data" in eqe_scope


def test_notebook_uses_portable_setup_and_the_configured_reporting_grid():
    _, code = _sources()

    assert 'print("Project root detected.")' in code
    assert 'print(f"Project root: {project_root}")' not in code
    assert "terminal_iv(MODEL_PARAMS)" in code
    assert "terminal_iv(MODEL_PARAMS, n=81" not in code
    assert "lifetimes = np.geomspace(1e-6, 1e-4, 5)" in code
    assert "quality_adequate=quality_adequate" in code
    assert "not validated parameter uncertainties" in code
    assert code.index("Normalized block score") < code.index(
        "Fitted effective parameters and local covariance diagnostics"
    )


def test_code_cells_execute_without_errors():
    notebook = _notebook()
    code_cells = [
        cell for cell in notebook["cells"] if cell.get("cell_type") == "code"
    ]
    assert code_cells
    assert all("".join(cell.get("source", [])).strip() for cell in code_cells)
    assert all(cell.get("outputs") for cell in code_cells)

    visual_cell_ids = {
        "newton-demo",
        "model-schematic",
        "profiles",
        "band-diagram",
        "jv-metrics",
        "eqe",
        "sensitivity",
        "raw-to-processed",
        "synthetic-fit",
        "joint-data-preview",
        "joint-calibration-figure",
        "joint-calibration-identifiability",
    }
    visual_cells = {cell.get("id"): cell for cell in code_cells}
    assert visual_cell_ids <= visual_cells.keys()
    assert all(
        any("image/png" in output.get("data", {}) for output in visual_cells[cell_id]["outputs"])
        for cell_id in visual_cell_ids
    )

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
