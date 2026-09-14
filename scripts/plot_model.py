"""Generate the complete device-model overview figure."""
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from model.schematic import draw_model_overview


def main() -> None:
    ap = argparse.ArgumentParser(description="Overview of the complete simulation model")
    ap.add_argument("--out", default="results/model.png", help="Output PNG path")
    args = ap.parse_args()

    fig = draw_model_overview()
    out = PROJECT_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved figure to {out}")


if __name__ == "__main__":
    main()
