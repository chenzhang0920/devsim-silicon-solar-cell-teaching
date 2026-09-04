"""Minimal import checks for the teaching environment and lightweight modules."""

import os
from pathlib import Path
import subprocess
import sys


def test_core_imports() -> None:
    import numpy  # noqa: F401
    import scipy  # noqa: F401
    import lmfit  # noqa: F401
    import devsim  # noqa: F401


def test_analysis_and_style_import_without_loading_devsim() -> None:
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        [
            sys.executable,
            "-B",
            "-c",
            "import sys; import model.analysis, model.style; "
            "print('devsim' in sys.modules)",
        ],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert completed.stdout.strip() == "False"
