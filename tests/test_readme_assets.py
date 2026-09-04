"""Regression checks for the GitHub-facing README visuals."""
import re
from pathlib import Path
from urllib.parse import unquote


def test_readme_visual_assets_are_tracked_and_referenced():
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    refs = set(re.findall(r'<img[^>]+src="([^"]+)"', readme))
    expected = {
        "docs/logo1_HKUSTGZ.png",
        "results/model.png",
        "results/profiles.png",
        "results/iv_plot.png",
        "results/joint_observables.png",
        "results/eqe.png",
        "results/identifiability.png",
    }
    assert expected <= refs
    assert all((root / ref).is_file() for ref in expected)

    links = set(re.findall(r'\]\(([^)]+)\)', readme))
    links.update(re.findall(r'href="([^"]+)"', readme))
    links.update(refs)
    local = {
        unquote(link.split("#", 1)[0])
        for link in links
        if link and not link.startswith(("#", "http://", "https://", "mailto:"))
    }
    assert not [link for link in sorted(local) if not (root / link).exists()]
