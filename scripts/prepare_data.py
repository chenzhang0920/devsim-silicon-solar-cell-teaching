"""Convert a raw two-column I–V measurement into standard V,J density data."""
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

from model.style import C_BLUE
from model.analysis import voc_zero_crossing

DATA_DIR = PROJECT_ROOT / "data"
RESULTS_DIR = PROJECT_ROOT / "results"


def _project_path(path: str | Path) -> Path:
    """Resolve a user-supplied relative path from the project root."""
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def _parse_unit_arg(s: str, quantity: str) -> float:
    """Return an SI multiplier while rejecting dimensionally wrong units."""
    tables = {
        "voltage": {"v": 1.0, "mv": 1e-3},
        "current": {"a": 1.0, "ma": 1e-3},
    }
    table = tables[quantity]
    key = s.strip().lower()
    if key not in table:
        choices = "/".join(table)
        raise SystemExit(f"Unknown {quantity} unit: {s!r} (choices: {choices})")
    return table[key]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=(
            "Convert one generic illuminated I–V sweep to a standardized "
            "light J–V table"
        )
    )
    ap.add_argument("input", help="Raw CSV path")
    ap.add_argument("--area", type=float, required=True,
                    help="Illuminated cell area (cm^2); required to convert current to density")
    ap.add_argument("--voltage-unit", default="V", help="Voltage unit: V or mV (default: V)")
    ap.add_argument("--current-unit", default="mA", help="Current unit: A or mA (default: mA)")
    ap.add_argument("--columns", default="V,I",
                    help="Input column names as voltage,current (default: V,I); output is always V,J")
    ap.add_argument("--skiprows", type=int, default=0,
                    help="Rows to skip at the start of the file (default: 0)")
    ap.add_argument(
        "--voltage-sign", type=int, choices=(-1, 1), default=1,
        help="Multiplier from recorded to cell voltage (default: +1)",
    )
    ap.add_argument(
        "--current-sign", type=int, choices=(-1, 1), default=1,
        help="Multiplier from recorded current to generation-positive current (default: +1)",
    )
    ap.add_argument("--out", default=None,
                    help="Output path (default: data/processed/measured_iv.csv)")
    ap.add_argument("--plot", action="store_true",
                    help="Save a preview figure to results/prepared_data_preview.png")
    args = ap.parse_args()

    area = args.area
    if not np.isfinite(area) or area <= 0:
        raise SystemExit(f"--area must be a positive finite value; received {area!r}")
    v_unit = _parse_unit_arg(args.voltage_unit, "voltage")
    i_unit = _parse_unit_arg(args.current_unit, "current")
    cols = [c.strip() for c in args.columns.split(",")]
    if len(cols) != 2:
        raise SystemExit(f"--columns requires two names (voltage,current); received {cols}")
    v_col, i_col = cols
    if not v_col or not i_col or v_col == i_col:
        raise SystemExit("--columns requires two distinct, non-empty column names")
    if args.skiprows < 0:
        raise SystemExit(f"--skiprows must be >= 0; received {args.skiprows}")

    in_path = _project_path(args.input)
    if not in_path.exists():
        raise SystemExit(f"Input file not found: {in_path}")
    out = _project_path(args.out) if args.out else DATA_DIR / "processed" / "measured_iv.csv"
    if out.resolve() == in_path.resolve():
        raise SystemExit("The output path must not overwrite the raw input file")
    raw_root = (DATA_DIR / "raw").resolve()
    if out.resolve() == raw_root or raw_root in out.resolve().parents:
        raise SystemExit("Processed output must not be written inside data/raw/")
    synthetic_root = (DATA_DIR / "synthetic").resolve()
    if out.resolve() == synthetic_root or synthetic_root in out.resolve().parents:
        raise SystemExit("Experimental output must not be written inside data/synthetic/")

    try:
        df = pd.read_csv(in_path, skiprows=args.skiprows)
    except (OSError, pd.errors.ParserError) as exc:
        raise SystemExit(f"Could not read input CSV {in_path}: {exc}") from exc
    for c in (v_col, i_col):
        if c not in df.columns:
            raise SystemExit(f"CSV is missing column '{c}'; found {list(df.columns)} "
                             "(use --columns to specify alternatives)")

    try:
        V = args.voltage_sign * df[v_col].to_numpy(dtype=float) * v_unit
        J = args.current_sign * df[i_col].to_numpy(dtype=float) * i_unit / area
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            f"Columns {v_col!r} and {i_col!r} must contain numeric values"
        ) from exc
    finite = np.isfinite(V) & np.isfinite(J)
    if not np.all(finite):
        print(f"WARNING: removed {np.count_nonzero(~finite)} rows containing NaN/Inf")
        V, J = V[finite], J[finite]
    if V.size < 3:
        raise SystemExit("Fewer than 3 valid J-V points remain")


    order = np.argsort(V, kind="stable")
    V, J = V[order], J[order]


    unique_v, inverse, counts = np.unique(V, return_inverse=True, return_counts=True)
    if unique_v.size != V.size:
        duplicate_count = int(V.size - unique_v.size)
        J = np.bincount(inverse, weights=J) / counts
        V = unique_v
        print(
            f"[NOTE] Averaged {duplicate_count} repeated voltage rows into "
            f"{V.size} unique voltage points")
    if V.size < 3:
        raise SystemExit("Fewer than 3 unique voltage points remain after averaging repeats")


    i0 = int(np.argmin(np.abs(V)))
    if abs(V[i0]) > 0.03:
        raise SystemExit("Data lack a short-circuit point near 0 V (required: |V| <= 0.03 V)")
    if J[i0] <= 0:
        raise SystemExit(
            "Current near short circuit is not positive; check wiring/signs and --current-sign")
    if not np.isfinite(voc_zero_crossing(V, J)):
        raise SystemExit(
            "Data do not cross Voc (no positive-to-nonpositive current crossing at V >= 0); "
            "check polarity or extend the forward-voltage range"
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"V": V, "J": J}).to_csv(out, index=False)
    print(f"Wrote {len(V)} points to {out}")
    print(f"  Area = {area:g} cm^2; voltage range = {V[0]:.3f} to {V[-1]:.3f} V")
    print(f"  Current density near V=0: Jsc ~= {J[i0] * 1e3:.2f} mA/cm^2")

    if args.plot:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        fig, ax = plt.subplots(figsize=(7, 4.5))
        ax.plot(V, J * 1e3, "o-", color=C_BLUE, ms=3, lw=1.2)
        ax.axhline(0.0, color="#888888", lw=0.8)
        ax.set_xlabel("Voltage V (V)")
        ax.set_ylabel("Current density J (mA/cm²)")
        ax.set_title("Prepared J–V data")
        ax.grid(True, color="#dddddd", lw=0.6)
        fig.tight_layout()
        preview = RESULTS_DIR / "prepared_data_preview.png"
        fig.savefig(preview, dpi=150)
        plt.close(fig)
        print(f"  Saved preview to {preview}")


if __name__ == "__main__":
    main()
