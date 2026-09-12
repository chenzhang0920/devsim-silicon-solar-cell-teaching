"""Portable provenance helpers for calibration input files."""
from __future__ import annotations

import hashlib
from pathlib import Path


CALIBRATION_HASH_METHOD = "sha256-lf-normalized-v1"
FIT_METADATA_SCHEMA_VERSION = 2


def calibration_input_sha256(path: str | Path) -> str:
    """Hash file content after normalizing text line endings to LF.

    Git may check out the same CSV with LF or CRLF line endings on different
    operating systems.  Treating those byte representations as equivalent
    keeps saved-fit replay portable while every other content change still
    changes the digest.
    """
    content = Path(path).read_bytes()
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()
