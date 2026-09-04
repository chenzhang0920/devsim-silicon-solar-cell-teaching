"""Plot the simulated J-V curve and its standard solar-cell metrics."""
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from config import MODEL_PARAMS, MODELED_INPUT_POWER_W_CM2
from model import terminal_iv
from model.analysis import solar_metrics
from model.style import C_BLUE, C_GREEN, C_ORANGE, C_GRAY

MODELED_POWER_COLUMN = "modeled_input_power_W_cm2"


def _project_path(path: str | Path) -> Path:
    """Resolve a user-supplied relative path from the project root."""
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def load_reference(
    path: str | None,
) -> tuple[np.ndarray, np.ndarray, str] | None:
    """Load an optional J-V reference and label its provenance honestly."""
    if path is None:
        return None
    p = _project_path(path)
    if not p.exists():
        print(f"[NOTE] Comparison data not found: {p}; skipping overlay")
        return None
    df = pd.read_csv(p)
    V = df["V"].to_numpy(dtype=float)
    J_mA = df["J"].to_numpy(dtype=float) * 1e3   # A/cm^2 -> mA/cm^2
    synthetic_root = (PROJECT_ROOT / "data" / "synthetic").resolve()
    label = "synthetic reference" if synthetic_root in p.resolve().parents else "measured data"
    return V, J_mA, label


def modeled_input_power(df: pd.DataFrame, source: Path) -> float | None:
    """Read a constant modeled-input-power provenance column when available."""
    if MODELED_POWER_COLUMN not in df:
        print(
            f"[NOTE] {source} has no {MODELED_POWER_COLUMN!r} column; "
            "modeled efficiency will be omitted."
        )
        return None
    values = df[MODELED_POWER_COLUMN].to_numpy(dtype=float)
    if (
        values.size == 0
        or not np.all(np.isfinite(values))
        or np.any(values <= 0.0)
        or not np.allclose(values, values[0], rtol=1e-12, atol=0.0)
    ):
        raise ValueError(
            f"{MODELED_POWER_COLUMN} in {source} must be one positive finite "
            "value repeated for every row"
        )
    return float(values[0])


def plot(V: np.ndarray, J_mA: np.ndarray,
         reference: tuple[np.ndarray, np.ndarray, str] | None,
         modeled_pin: float | None,
         out: Path) -> None:
    m = solar_metrics(V, J_mA * 1e-3, pin=modeled_pin)
    jsc = m["Jsc"] * 1e3       # mA/cm^2
    voc = m["Voc"]
    ff = m["FF"]
    pmax = m["Pmax"] * 1e3     # mW/cm^2
    vmp = m["Vmp"]
    jmp = m["Jmp"] * 1e3       # mA/cm^2
    eta = m["eta"] * 100       # %, or nan when input power provenance is unavailable

    fig, ax = plt.subplots(figsize=(9.3, 6.0))
    ax.plot(
        V,
        J_mA,
        color=C_BLUE,
        lw=2.2,
        label="DEVSIM simulation" if reference is not None else None,
    )
    power_mask = (V >= 0.0) & (V <= voc) & (J_mA >= 0.0)
    ax.fill_between(V[power_mask], 0.0, J_mA[power_mask], color=C_BLUE, alpha=0.10)
    if reference is not None:
        ax.scatter(
            reference[0], reference[1], color=C_ORANGE, s=30, zorder=3,
            label=reference[2], edgecolors="white", linewidths=0.4,
        )

    ax.scatter([0.0], [jsc], color=C_BLUE, s=34, zorder=4)
    ax.scatter([voc], [0.0], color=C_BLUE, s=34, zorder=4)
    ax.scatter([vmp], [jmp], color=C_GREEN, s=52, marker="D", zorder=5)
    ax.plot([vmp, vmp], [0.0, jmp], color=C_GREEN, lw=1.0, ls="--")
    ax.plot([0.0, vmp], [jmp, jmp], color=C_GREEN, lw=1.0, ls="--")
    ax.annotate("MPP", xy=(vmp, jmp), xytext=(vmp - 0.07, jmp - 4.2),
                color=C_GREEN, fontsize=12.5, ha="center",
                arrowprops=dict(arrowstyle="->", color=C_GREEN, lw=1.0))

    if np.isfinite(eta):
        text = (f"Jsc={jsc:.2f} mA/cm²   Voc={voc:.3f} V   FF={ff:.3f}\n"
                f"Pmax={pmax:.2f} mW/cm²   ηmodel={eta:.2f}%   "
                f"MPP={vmp:.3f} V, {jmp:.1f} mA/cm²")
    else:
        text = (f"Jsc={jsc:.2f} mA/cm²   Voc={voc:.3f} V   FF={ff:.3f}\n"
                f"Pmax={pmax:.2f} mW/cm²   modeled η omitted (Pin unavailable)\n"
                f"MPP={vmp:.3f} V, {jmp:.1f} mA/cm²")
    ax.text(0.02, 0.035, text, transform=ax.transAxes, fontsize=11.5,
            va="bottom", ha="left", family="monospace",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="#cccccc", lw=0.8))

    ax.axhline(0.0, color=C_GRAY, lw=0.9)
    ax.grid(True)
    ax.set_xlim(-0.01, max(float(V.max()), voc + 0.02))
    ax.set_ylim(-5.0, max(32.0, jsc * 1.08))
    ax.set_xlabel("Voltage V (V)")
    ax.set_ylabel("Current density J (mA/cm²)")
    ax.set_title("The J–V knee locates the maximum-power point")
    ax.text(0.99, 0.98, "positive J = power delivered by the cell",
            transform=ax.transAxes, ha="right", va="top", fontsize=11.5, color=C_GRAY)
    if reference is not None:
        ax.legend(
            frameon=False,
            loc="upper center",
            bbox_to_anchor=(0.5, -0.16),
            ncol=2,
        )

    fig.tight_layout(rect=(0, 0.10 if reference is not None else 0, 1, 1))
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"Saved figure to {out}")
    summary = (f"  Jsc={jsc:.2f} mA/cm^2, Voc={voc:.3f} V, "
               f"FF={ff:.3f}, Pmax={pmax:.2f} mW/cm^2")
    if np.isfinite(eta):
        summary += f", modeled eta={eta:.2f}%"
    else:
        summary += ", modeled eta omitted (input-power provenance unavailable)"
    print(summary)


def main() -> None:
    ap = argparse.ArgumentParser(description="Plot the solar-cell J-V curve")
    ap.add_argument(
        "--data",
        help="Optional comparison CSV; omitted by default to avoid stale or accidental overlays",
    )
    ap.add_argument("--csv", help="Saved simulation CSV; skips simulation when provided")
    ap.add_argument("--out", default="results/iv_plot.png", help="Output PNG path")
    args = ap.parse_args()

    if args.csv:
        csv_path = _project_path(args.csv)
        df = pd.read_csv(csv_path)
        V = df["V"].to_numpy(dtype=float)
        J_mA = df["J"].to_numpy(dtype=float) * 1e3
        modeled_pin = modeled_input_power(df, csv_path)
        print(f"[NOTE] Using saved simulation results: {csv_path}")
    else:
        V, J = terminal_iv(params=MODEL_PARAMS)
        V = np.asarray(V, dtype=float)
        J_mA = np.asarray(J, dtype=float) * 1e3
        modeled_pin = (
            MODELED_INPUT_POWER_W_CM2 * float(MODEL_PARAMS["photon_flux"])
        )

    reference = load_reference(args.data)
    plot(V, J_mA, reference, modeled_pin, PROJECT_ROOT / args.out)


if __name__ == "__main__":
    main()
