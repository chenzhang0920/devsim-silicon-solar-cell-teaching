"""Convert native Keithley 2636B exports into standard solar-cell CSV files."""
import argparse
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from model.analysis import solar_metrics

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" / "keithley"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


_FILE_RE = re.compile(r"^(dark|light)\s*-\s*(iv|voc|ishort)\s*-\s*(\d+)\.csv$", re.IGNORECASE)
_OWNED_OUTPUT_RE = re.compile(
    r"^(?:(?:dark|light)_(?:iv|ishort)_sample\d+|(?:voc|ishort)_summary)\.csv$",
    re.IGNORECASE,
)
_HEADER_ALIASES = {
    "index": ("\u7d22\u5f15", "index"),
    "voltage": ("\u7535\u538b", "voltage"),
    "current": ("\u7535\u6d41", "current"),
}
_REQUIRED_PRUNE_MEASUREMENTS = {
    ("light", "iv"),
    ("dark", "iv"),
    ("light", "voc"),
    ("light", "ishort"),
}


def classify_keithley_filename(name: str) -> tuple[str, str, int] | None:
    """Return normalized condition, measurement kind, and sample number."""
    match = _FILE_RE.match(name)
    if match is None:
        return None
    return match.group(1).lower(), match.group(2).lower(), int(match.group(3))


def parse_keithley(path: str | Path) -> tuple[np.ndarray, np.ndarray]:
    """Parse voltage and current arrays from a native Keithley CSV export."""
    import csv
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))

    def contains_alias(value: str, field: str) -> bool:
        normalized = value.strip().casefold().lstrip("\ufeff")
        return any(alias in normalized for alias in _HEADER_ALIASES[field])

    try:
        hi = next(i for i, row in enumerate(rows) if row and contains_alias(row[0], "index"))
    except StopIteration as exc:
        raise ValueError(
            f"{path} has no Keithley header containing an Index/\u7d22\u5f15 field"
        ) from exc
    header = [h.strip() for h in rows[hi]]
    data = [r for r in rows[hi + 1:] if r and r[0].strip()
            and not r[0].startswith(".")]

    def unique_column(field: str) -> int:
        matches = [i for i, value in enumerate(header) if contains_alias(value, field)]
        if len(matches) != 1:
            raise ValueError(
                f"{path} header must contain exactly one {field} column; "
                f"found {len(matches)} in {header}"
            )
        return matches[0]

    vi = unique_column("voltage")
    ii = unique_column("current")
    for index, unit, field in ((vi, "V", "voltage"), (ii, "A", "current")):
        compact = re.sub(r"\s+", "", header[index]).casefold()
        if f"({unit.casefold()})" not in compact:
            raise ValueError(
                f"{path} {field} header must declare ({unit}); found {header[index]!r}. "
                "Use prepare_data.py for exports with other units."
            )
    try:
        V = np.array([float(r[vi]) for r in data])
        I = np.array([float(r[ii]) for r in data])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"{path} has incomplete or non-numeric Keithley data rows") from exc
    if V.size == 0 or not np.all(np.isfinite(V)) or not np.all(np.isfinite(I)):
        raise ValueError(f"{path} contains no valid finite numeric data")
    return V, I


def _project_path(path: str | Path) -> Path:
    """Resolve a user-supplied relative path from the project root."""
    value = Path(path)
    return value if value.is_absolute() else PROJECT_ROOT / value


def to_solar_cell(V_smu, I_smu, area, voltage_sign=-1, current_sign=1):
    """Convert instrument polarity and average repeated sweep voltages."""
    V = voltage_sign * np.asarray(V_smu, dtype=float)
    J = current_sign * np.asarray(I_smu, dtype=float) / area
    order = np.argsort(V, kind="stable")
    V, J = V[order], J[order]
    unique_v, inverse, counts = np.unique(V, return_inverse=True, return_counts=True)
    if unique_v.size != V.size:
        J = np.bincount(inverse, weights=J) / counts
        V = unique_v
    return V, J


def crop(V, J, v_max):
    """Restrict a J-V curve to the modeled forward-bias interval."""
    m = (V >= 0.0) & (V <= v_max)
    return V[m], J[m]


def voltage_at_zero_current_from_file(
        path, voltage_sign=-1, current_tolerance=1e-8):
    """Return median voltage after verifying that a current-biased file is near zero A."""
    if not np.isfinite(current_tolerance) or current_tolerance <= 0:
        raise ValueError("zero-current tolerance must be finite and > 0")
    V, I = parse_keithley(path)
    max_current = float(np.max(np.abs(I)))
    if max_current > current_tolerance:
        raise ValueError(
            f"{path} is labeled as a zero-current voltage measurement but reaches "
            f"|I|={max_current:.3g} A (tolerance {current_tolerance:.3g} A)"
        )
    return float(np.median(voltage_sign * V))


def ishort_summary(V, J):
    """Summarize a near-zero-bias short-circuit measurement."""
    ddof = 1 if len(V) > 1 else 0
    return {
        "J_mean_A_cm2": float(np.mean(J)),
        "J_std_A_cm2": float(np.std(J, ddof=ddof)),
        "V_mean_V": float(np.mean(V)),
        "V_std_V": float(np.std(V, ddof=ddof)),
        "n_points": int(len(V)),
    }


def remove_stale_converter_outputs(out_dir: Path, written: set[str]) -> list[str]:
    """Remove converter-owned tables that were not produced by a complete run."""
    removed = []
    for path in out_dir.iterdir():
        if path.is_file() and _OWNED_OUTPUT_RE.match(path.name) and path.name not in written:
            path.unlink()
            removed.append(path.name)
    return sorted(removed)


def merge_summary_rows(path: Path, new_rows: pd.DataFrame,
                       prune: bool = False) -> pd.DataFrame:
    """Merge updated sample/condition rows, or replace them for a complete bundle."""
    keys = ["sample", "condition"]
    if prune or not path.exists():
        combined = new_rows.copy()
    else:
        existing = pd.read_csv(path)
        missing = [column for column in new_rows.columns if column not in existing.columns]
        if missing:
            raise ValueError(
                f"Existing summary {path} is missing columns {missing}; "
                "move it aside or rerun with --prune using a complete input bundle"
            )
        existing = existing.loc[:, new_rows.columns].copy()
        new_keys = {
            (str(sample).strip(), str(condition).strip().lower())
            for sample, condition in new_rows[keys].itertuples(index=False, name=None)
        }
        keep = [
            (str(sample).strip(), str(condition).strip().lower()) not in new_keys
            for sample, condition in existing[keys].itertuples(index=False, name=None)
        ]
        combined = pd.concat([existing.loc[keep], new_rows], ignore_index=True)
    combined["condition"] = combined["condition"].astype(str).str.strip().str.lower()
    return combined.sort_values(keys, kind="stable").reset_index(drop=True)


def write_validated_tables(out_dir: Path, tables: dict[str, pd.DataFrame]) -> None:
    """Serialize every validated table before replacing any published output."""
    staged: list[tuple[Path, Path]] = []
    try:
        for name, table in tables.items():
            target = out_dir / name
            temporary = out_dir / f".{name}.tmp"
            table.to_csv(temporary, index=False)
            staged.append((temporary, target))
        for temporary, target in staged:
            temporary.replace(target)
    finally:
        for temporary, _ in staged:
            if temporary.exists():
                temporary.unlink()


def main() -> None:
    ap = argparse.ArgumentParser(description="Convert native Keithley 2636B CSV files to standard V,J data")
    ap.add_argument("--area", type=float, required=True,
                    help="Illuminated cell area (cm^2), used to convert A to A/cm^2")
    ap.add_argument("--data", default=str(RAW_DATA_DIR),
                    help="Directory containing native Keithley files (default: data/raw/keithley)")
    ap.add_argument("--out-dir", default=str(PROCESSED_DIR),
                    help="Directory for standardized V,J files (default: data/processed)")
    ap.add_argument("--v-max", type=float, default=0.72,
                    help="Retain J-V points in 0 <= V <= this limit (V; default: 0.72)")
    ap.add_argument(
        "--voltage-sign", type=int, choices=(-1, 1), default=-1,
        help="Multiplier converting instrument voltage to cell voltage (default: -1)",
    )
    ap.add_argument(
        "--current-sign", type=int, choices=(-1, 1), default=1,
        help="Multiplier converting instrument current to generation-positive current (default: +1)",
    )
    ap.add_argument(
        "--irradiance", type=float,
        help="Measured incident irradiance (W/cm^2); omit it when unknown so efficiency is not reported",
    )
    ap.add_argument(
        "--zero-current-tolerance", type=float, default=1e-8,
        help="Maximum |I| accepted in *-voc-* files (A; default: 1e-8)",
    )
    ap.add_argument(
        "--prune", action="store_true",
        help=(
            "Remove converter-owned outputs not represented in this input directory. "
            "Use only when --data contains the complete intended measurement bundle"
        ),
    )
    args = ap.parse_args()

    if not np.isfinite(args.area) or args.area <= 0:
        raise SystemExit(f"--area must be a positive finite value; received {args.area!r}")
    if not np.isfinite(args.v_max) or args.v_max <= 0:
        raise SystemExit(f"--v-max must be a positive finite value; received {args.v_max!r}")
    if args.irradiance is not None and (
            not np.isfinite(args.irradiance) or args.irradiance <= 0):
        raise SystemExit(
            f"--irradiance must be a positive finite value; received {args.irradiance!r}")
    if not np.isfinite(args.zero_current_tolerance) or args.zero_current_tolerance <= 0:
        raise SystemExit(
            "--zero-current-tolerance must be a positive finite current in A"
        )

    data_dir = _project_path(args.data)
    out_dir = _project_path(args.out_dir)
    if not data_dir.is_dir():
        raise SystemExit(f"Keithley data directory not found: {data_dir}")
    data_root = data_dir.resolve()
    output_root = out_dir.resolve()
    if output_root == data_root or data_root in output_root.parents:
        raise SystemExit("--out-dir must not be the raw input directory or one of its children")
    project_raw_root = (PROJECT_ROOT / "data" / "raw").resolve()
    if output_root == project_raw_root or project_raw_root in output_root.parents:
        raise SystemExit("--out-dir must not be inside the immutable data/raw namespace")
    project_synthetic_root = (PROJECT_ROOT / "data" / "synthetic").resolve()
    if output_root == project_synthetic_root or project_synthetic_root in output_root.parents:
        raise SystemExit("--out-dir must not mix experimental tables into data/synthetic")
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(
        (path for path in data_dir.iterdir() if path.is_file() and path.suffix.lower() == ".csv"),
        key=lambda path: path.name.lower(),
    )
    if not files:
        raise SystemExit(f"No CSV files found under {data_dir}")

    classified_files = []
    ignored_files = []
    seen_measurements = {}
    for path in files:
        classification = classify_keithley_filename(path.name)
        if classification is None:
            if re.match(r"^(?:dark|light)\b", path.name, re.IGNORECASE):
                raise SystemExit(
                    f"Measurement-like filename does not match the required pattern: {path.name!r}"
                )
            ignored_files.append(path.name)
            continue
        if classification in seen_measurements:
            raise SystemExit(
                "Duplicate Keithley measurement after filename normalization: "
                f"{seen_measurements[classification].name!r} and {path.name!r}"
            )
        seen_measurements[classification] = path
        classified_files.append((path, classification))
    if not classified_files:
        raise SystemExit(
            f"No Keithley files under {data_dir} match the expected "
            "dark/light - iv/voc/ishort - sample pattern"
        )
    if ignored_files:
        if args.prune:
            raise SystemExit(
                "--prune requires a dedicated, complete Keithley input directory; "
                f"unmatched CSV files: {ignored_files}"
            )
        print("[WARNING] Ignored CSV files with unrelated names: " + ", ".join(ignored_files))
    if args.prune:
        for sample in sorted({item[1][2] for item in classified_files}):
            available = {
                (condition, kind)
                for _, (condition, kind, item_sample) in classified_files
                if item_sample == sample
            }
            missing = sorted(_REQUIRED_PRUNE_MEASUREMENTS - available)
            if missing:
                raise SystemExit(
                    f"--prune requires light/dark IV plus light Voc/ishort for sample {sample}; "
                    f"missing {missing}"
                )

    pending_tables: dict[str, pd.DataFrame] = {}
    voc_rows = []
    summary = []
    ishort_rows = []
    for f, classification in classified_files:
        cond, kind, sample = classification
        if kind == "voc":
            voltage_at_i0 = voltage_at_zero_current_from_file(
                f,
                voltage_sign=args.voltage_sign,
                current_tolerance=args.zero_current_tolerance,
            )
            voc_rows.append({
                "sample": sample,
                "condition": cond,
                "V_at_I0_V": voltage_at_i0,
            })
            if cond == "light" and voltage_at_i0 <= 0:
                raise SystemExit(
                    f"{f.name} gives non-positive light Voc after sign conversion; "
                    "check --voltage-sign and the measurement mode"
                )
            quantity = "light Voc" if cond.lower() == "light" \
                else "dark zero-current offset"
            print(f"  {f.name:24s} -> {quantity} = {voltage_at_i0:.4f} V")
            continue
        V_smu, I_smu = parse_keithley(f)
        if kind == "ishort":
            # Preserve repeated near-zero-bias samples: deduplicating measured
            # voltages would discard valid current statistics for this test.
            V = args.voltage_sign * np.asarray(V_smu, dtype=float)
            J = args.current_sign * np.asarray(I_smu, dtype=float) / args.area
            if V.size < 3:
                raise SystemExit(f"{f.name} has only {V.size} points; at least 3 are required")
            out = out_dir / f"{cond}_ishort_sample{sample}.csv"
            row = {"sample": sample, "condition": cond, **ishort_summary(V, J)}
            if float(np.max(np.abs(V))) > 0.03:
                raise SystemExit(
                    f"{f.name} is labeled ishort but contains |V| > 0.03 V"
                )
            if cond == "light" and row["J_mean_A_cm2"] <= 0:
                raise SystemExit(
                    f"{f.name} gives non-positive illuminated short-circuit current; "
                    "check --current-sign"
                )
            pending_tables[out.name] = pd.DataFrame({"V": V, "J": J})
            ishort_rows.append(row)
            print(f"  {f.name:24s} -> {out.name} ({len(V)} points, near-zero-bias short measurement)  "
                  f"Jmean={row['J_mean_A_cm2'] * 1e3:.3f} mA/cm^2  "
                  f"Vmean={row['V_mean_V'] * 1e6:.2f} uV")
            continue
        V, J = to_solar_cell(
            V_smu, I_smu, args.area,
            voltage_sign=args.voltage_sign,
            current_sign=args.current_sign,
        )
        repeated = int(len(V_smu) - len(V))
        if repeated:
            print(
                f"  [NOTE] {f.name}: averaged {repeated} repeated rows into "
                f"{len(V)} unique voltage points")
        Vc, Jc = crop(V, J, args.v_max)
        cropped = int(V.size - Vc.size)
        if cropped:
            print(
                f"  [NOTE] {f.name}: excluded {cropped} points outside the "
                f"modeled operating range 0..{args.v_max:g} V")
        if Vc.size < 3:
            raise SystemExit(
                f"{f.name} has only {Vc.size} points in 0..{args.v_max:g} V, insufficient for a J-V curve")
        out = out_dir / f"{cond}_iv_sample{sample}.csv"
        if cond == "light":
            m_ = solar_metrics(Vc, Jc, pin=args.irradiance)
            if not np.isfinite(m_["Voc"]) or m_["Voc"] <= 0:
                raise SystemExit(
                    f"{f.name} does not contain a positive light-current zero crossing; "
                    "check polarity or extend the sweep beyond Voc"
                )
            summary.append((sample, out, m_))
            line = (f"  {f.name:24s} -> {out.name} ({len(Vc)} points)  "
                    f"Jsc={m_['Jsc']*1e3:.1f} mA/cm^2  Voc={m_['Voc']:.3f} V  "
                    f"FF={m_['FF']:.3f}  Pmax={m_['Pmax']*1e3:.2f} mW/cm^2")
            if args.irradiance is not None:
                line += f"  eta={m_['eta']*100:.1f}%"
            print(line)
        else:
            if not np.any((Vc > 0) & (Jc < 0)):
                raise SystemExit(
                    f"{f.name} has no negative dark forward current after sign conversion; "
                    "check --voltage-sign and --current-sign"
                )
            print(f"  {f.name:24s} -> {out.name} ({len(Vc)} points, dark diode curve)")
        pending_tables[out.name] = pd.DataFrame({"V": Vc, "J": Jc})

    if voc_rows:
        voc_out = out_dir / "voc_summary.csv"
        voc_df = merge_summary_rows(
            voc_out, pd.DataFrame(voc_rows), prune=args.prune
        )
        pending_tables[voc_out.name] = voc_df


    if ishort_rows:
        ishort_out = out_dir / "ishort_summary.csv"
        ishort_df = merge_summary_rows(
            ishort_out, pd.DataFrame(ishort_rows), prune=args.prune
        )
        pending_tables[ishort_out.name] = ishort_df

    write_validated_tables(out_dir, pending_tables)
    written_outputs = set(pending_tables)
    if voc_rows:
        print(f"\nWrote zero-current-voltage summary to {out_dir / 'voc_summary.csv'}")
        print(voc_df.to_string(index=False))
    if ishort_rows:
        print(f"\nWrote short-circuit summary to {out_dir / 'ishort_summary.csv'}")
        print(ishort_df.to_string(index=False))


    if summary:
        print("\n-- Illuminated J-V metrics --")
        if args.irradiance is None:
            print("Efficiency is omitted because incident irradiance was not provided.")
        else:
            print(f"Incident irradiance = {args.irradiance * 1e3:.3f} mW/cm^2")
        eta_header = f"{'eta(%)':>9}" if args.irradiance is not None else ""
        print(f"{'Sample':<8}{'Jsc(mA/cm^2)':>14}{'Voc(V)':>10}{'FF':>8}"
              f"{'Pmax(mW/cm^2)':>17}{eta_header}")
        for sample, _, m_ in summary:
            line = (f"{sample:<8}{m_['Jsc']*1e3:>14.1f}{m_['Voc']:>10.3f}"
                    f"{m_['FF']:>8.3f}{m_['Pmax']*1e3:>17.2f}")
            if args.irradiance is not None:
                line += f"{m_['eta']*100:>9.2f}"
            print(line)

    if args.prune:
        removed = remove_stale_converter_outputs(out_dir, written_outputs)
        if removed:
            print("\nRemoved stale converter outputs: " + ", ".join(removed))


if __name__ == "__main__":
    main()
