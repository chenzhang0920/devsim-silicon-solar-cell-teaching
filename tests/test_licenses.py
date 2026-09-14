"""Keep the public repository's dual-license declaration internally consistent."""
from pathlib import Path


def test_code_and_content_licenses_are_declared():
    root = Path(__file__).resolve().parents[1]
    mit = (root / "LICENSE").read_text(encoding="utf-8")
    content = (root / "LICENSE-CONTENT.md").read_text(encoding="utf-8")
    readme = (root / "README.md").read_text(encoding="utf-8")

    assert mit.startswith("MIT License\n")
    assert "Copyright (c) 2026 Zhang CHEN and contributors" in mit
    assert "THE SOFTWARE IS PROVIDED \"AS IS\"" in mit

    assert "CC BY 4.0" in content
    assert "https://creativecommons.org/licenses/by/4.0/legalcode.en" in content
    assert "results/" in content
    assert "data/" in content
    assert "docs/logo1_HKUSTGZ.png" in content
    assert "not relicensed" in content

    assert "[MIT License](LICENSE)" in readme
    assert "[CC BY 4.0](LICENSE-CONTENT.md)" in readme
