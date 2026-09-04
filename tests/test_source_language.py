"""Keep executable teaching material consistently in English."""

import json
import re
from pathlib import Path

import numpy as np

from scripts.prepare_keithley import parse_keithley


ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u3400-\u9fff]")
SOURCE_DIRS = (ROOT / "model", ROOT / "calibration", ROOT / "scripts", ROOT / "tests")


def test_python_source_contains_no_literal_cjk_text():
    files = [ROOT / "config.py", ROOT / "environment.yml", ROOT / "pytest.ini"]
    files.extend(path for directory in SOURCE_DIRS for path in directory.glob("*.py"))
    offenders = [str(path.relative_to(ROOT)) for path in files if CJK.search(path.read_text(encoding="utf-8"))]
    assert not offenders, f"Translate executable Python text to English: {offenders}"


def test_tutorial_code_cells_contain_no_literal_cjk_text():
    notebook = json.loads((ROOT / "notebooks" / "tutorial.ipynb").read_text(encoding="utf-8"))
    offenders = []
    for index, cell in enumerate(notebook["cells"]):
        if cell.get("cell_type") == "code" and CJK.search("".join(cell.get("source", []))):
            offenders.append(index)
    assert not offenders, f"Translate tutorial code cells to English: {offenders}"


def test_localized_keithley_headers_remain_supported(tmp_path):
    raw = tmp_path / "keithley.csv"
    raw.write_text(
        "metadata\n"
        "\u7d22\u5f15,\u7535\u538b (V),\u7535\u6d41 (A)\n"
        "0,-0.10,0.020\n"
        "1,-0.20,0.015\n",
        encoding="utf-8",
    )
    voltage, current = parse_keithley(raw)
    np.testing.assert_allclose(voltage, [-0.10, -0.20])
    np.testing.assert_allclose(current, [0.020, 0.015])
