"""Reject broken local links in the repository's Markdown documentation."""
import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def _local_target(document: Path, raw_target: str) -> Path | None:
    target = raw_target.strip().strip("<>")
    if target.startswith(("#", "http://", "https://", "mailto:")):
        return None
    target = unquote(target.split("#", 1)[0].split(maxsplit=1)[0])
    return (document.parent / target).resolve()


def test_all_markdown_local_links_resolve():
    documents = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "LICENSE-CONTENT.md"]
    documents.extend(sorted((ROOT / "docs").rglob("*.md")))
    documents.extend(sorted((ROOT / "data").rglob("README.md")))

    broken: list[str] = []
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for raw_target in LINK_PATTERN.findall(text):
            target = _local_target(document, raw_target)
            if target is not None and not target.exists():
                broken.append(f"{document.relative_to(ROOT)} -> {raw_target}")

    assert not broken, "Broken local documentation links:\n" + "\n".join(broken)
