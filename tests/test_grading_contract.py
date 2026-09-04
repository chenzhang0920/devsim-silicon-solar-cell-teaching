"""Protect the fixed 100-point project grading contract."""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_grading_rubric_totals_100_points():
    text = (ROOT / "docs" / "grading.md").read_text(encoding="utf-8")
    table = text.split("## Task 1", 1)[0]
    points = [int(value) for value in re.findall(r"^\| .*? \| (\d+) \|", table, re.MULTILINE)]
    normalized = " ".join(text.split())

    assert points == [20, 20, 15, 30, 15]
    assert sum(points) == 100
    assert "10% of the final course grade" in normalized
    assert "experimental efficiency must be omitted" in normalized.lower()
