"""Keep executable teaching material consistently in English."""

import json
import re
from pathlib import Path

import numpy as np

from scripts.prepare_keithley import parse_keithley


ROOT = Path(__file__).resolve().parents[1]
CJK = re.compile(r"[\u3400-\u9fff]")
RAW_DATA_ROOT = ROOT / "data" / "raw"
RAW_EXPORT_SUFFIXES = {".csv", ".dat", ".tsv", ".txt"}
SOURCE_DIRS = (ROOT / "model", ROOT / "calibration", ROOT / "scripts", ROOT / "tests")
TEACHING_TEXT_SUFFIXES = {
    "",
    ".cff",
    ".css",
    ".csv",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".txt",
    ".yaml",
    ".yml",
}


def test_executable_source_contains_no_literal_cjk_text():
    files = [ROOT / "config.py", ROOT / "environment.yml", ROOT / "pytest.ini"]
    files.extend(path for directory in SOURCE_DIRS for path in directory.rglob("*.py"))
    files.extend((ROOT / "scripts").rglob("*.sh"))
    offenders = [
        str(path.relative_to(ROOT))
        for path in files
        if CJK.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"Translate executable source text to English: {offenders}"


def test_repository_maintained_text_contains_no_literal_cjk_text():
    roots = (
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "CITATION.cff",
        ROOT / "LICENSE",
        ROOT / "LICENSE-CONTENT.md",
        ROOT / ".github",
        ROOT / "docs",
        ROOT / "data",
        ROOT / "results",
    )
    files = []
    for root in roots:
        candidates = (root,) if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in TEACHING_TEXT_SUFFIXES:
                continue
            is_raw_data = RAW_DATA_ROOT in path.parents and (
                path.suffix.casefold() in RAW_EXPORT_SUFFIXES
            )
            if is_raw_data:
                continue
            files.append(path)
    offenders = [
        str(path.relative_to(ROOT))
        for path in files
        if CJK.search(path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"Translate maintained teaching text to English: {offenders}"


def _visible_output_text(output: dict) -> str:
    parts = []
    for key in ("text", "ename", "evalue", "traceback"):
        value = output.get(key, "")
        parts.append("".join(value) if isinstance(value, list) else str(value))
    data = output.get("data", {})
    visible_mime_types = {
        mime_type
        for mime_type in data
        if mime_type.startswith("text/")
        or mime_type in {
            "application/javascript",
            "application/json",
            "image/svg+xml",
        }
    }
    for mime_type in visible_mime_types:
        value = data[mime_type]
        parts.append(
            json.dumps(value, ensure_ascii=False)
            if isinstance(value, (dict, list))
            else str(value)
        )
    return "\n".join(parts)


def test_tutorial_sources_and_text_outputs_contain_no_literal_cjk_text():
    notebook = json.loads((ROOT / "notebooks" / "tutorial.ipynb").read_text(encoding="utf-8"))
    offenders = []
    for index, cell in enumerate(notebook["cells"]):
        visible_text = "".join(cell.get("source", []))
        visible_text += "\n".join(
            _visible_output_text(output) for output in cell.get("outputs", [])
        )
        if CJK.search(visible_text):
            offenders.append(index)
    assert not offenders, f"Translate tutorial cells and text outputs to English: {offenders}"


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
