"""Build and validate the generated assets used by the HTML slide deck."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SLIDES = PROJECT_ROOT / "docs" / "lab_slides.html"


STEPS = [
    ("spectrum",     "scripts/plot_spectrum.py",   [],                     ["results/spectrum.png"],    False),
    ("demo-data",    "scripts/make_demo_data.py",  [],                     ["data/synthetic/iv.csv"],   False),
    ("sim",          "scripts/run_sim.py",         [],                     ["results/iv_sim.csv"],      False),
    ("iv",           "scripts/plot_iv.py",         ["--csv", "results/iv_sim.csv",
                                                       "--data", "data/synthetic/iv.csv"],
                    ["results/iv_plot.png"], False),
    ("resistance",   "scripts/plot_resistance.py", [],                     ["results/resistance.png"], False),
    ("profiles",     "scripts/plot_profiles.py",   ["--bias", "near-voc"], ["results/profiles.png"],    False),
    ("band",         "scripts/plot_band.py",       ["--bias", "near-voc"], ["results/band.png"],        False),
    ("model",        "scripts/plot_model.py",      [],                     ["results/model.png"],       False),
    ("sweep",        "scripts/plot_sweep.py",
                     ["--param", "hole_lifetime", "--start", "1e-6",
                      "--stop", "1e-4", "--n", "5"],
                     ["results/sweep.png"], True),
    ("eqe",          "scripts/plot_eqe.py",        [],                     ["results/eqe.png"],          True),
    ("calibration",  "scripts/run_calibration.py", [],                     ["results/fit_plot.png",
                                                                            "results/identifiability.png",
                                                                            "results/fitted_params.json",
                                                                            "results/fit_metadata.json"], True),
    ("joint",        "scripts/run_calibration.py", ["--joint", "--sample", "3"],
                    ["results/joint_observables.png",
                     "results/joint_identifiability.png",
                     "results/joint_fitted_params.json",
                     "results/joint_fit_metadata.json",
                     "results/joint_metrics.json"], True),
    ("optimization", "scripts/plot_optimization.py",
                     ["--params", "photon_flux",
                      "--init", "photon_flux=0.5",
                      "--max-nfev", "30", "--gif"],
                     ["results/optimization.png", "results/optimization.gif"], True),
]

_NAME_TO_STEP = {s[0]: s for s in STEPS}


def _is_nonempty_file(path: Path) -> bool:
    """Return whether an expected build product exists and contains data."""
    return path.is_file() and path.stat().st_size > 0


def _resolve_steps(only, skip, skip_slow):
    """Select requested build steps and reject unknown names."""
    if only is not None:
        unknown = only - set(_NAME_TO_STEP)
        if unknown:
            raise SystemExit(f"Unknown steps: {sorted(unknown)}; choices: {list(_NAME_TO_STEP)}")
    unknown_skip = skip - set(_NAME_TO_STEP)
    if unknown_skip:
        raise SystemExit(f"Unknown steps: {sorted(unknown_skip)}; choices: {list(_NAME_TO_STEP)}")

    chosen = []
    for name, script, args, produces, slow in STEPS:
        if only is not None and name not in only:
            continue
        if name in skip:
            continue
        if skip_slow and slow:
            continue
        chosen.append((name, script, args, produces))
    return chosen


def _run_step(name, script, args, products) -> bool:
    """Run one step after removing its old products, preventing stale success."""
    for product in products:
        target = PROJECT_ROOT / product
        if target.exists():
            if not target.is_file():
                raise RuntimeError(f"Expected a generated file, found another object: {target}")
            target.unlink()
    cmd = [sys.executable, str(PROJECT_ROOT / script), *args]
    print(f"\n-- [{name}] {script} {' '.join(args)} --")
    t0 = time.perf_counter()
    r = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    dt = time.perf_counter() - t0
    if r.returncode != 0:
        print(f"  [FAIL] Failed (exit {r.returncode}, {dt:.0f}s)")
        return False
    missing = [
        product for product in products
        if not _is_nonempty_file(PROJECT_ROOT / product)
    ]
    if missing:
        print(f"  [FAIL] Command succeeded but did not create non-empty files: {missing}")
        return False
    print(f"  [OK] Completed ({dt:.0f}s)")
    return True


def _check_slides() -> list[str]:
    """Return missing or undeclared local assets referenced by the slide deck."""
    if not _is_nonempty_file(SLIDES):
        print(f"Slide deck not found or empty: {SLIDES}")
        return [str(SLIDES)]
    text = SLIDES.read_text(encoding="utf-8")
    refs = sorted(set(re.findall(r'src="\.\./results/([^"]+)"', text)))
    local_refs = sorted({
        ref
        for ref in re.findall(r'src="([^"]+)"', text)
        if not ref.startswith(("../results/", "http://", "https://", "data:"))
    })
    declared = {
        Path(product).name
        for _, _, _, products, _ in STEPS
        for product in products
        if Path(product).parent.as_posix() == "results"
    }
    print(f"\n-- Slide asset validation ({SLIDES.name}, {len(refs)} results/ files, "
          f"{len(local_refs)} local files) --")
    problems = []
    for ref in local_refs:
        exists = _is_nonempty_file(SLIDES.parent / ref)
        if not exists:
            problems.append(f"missing:{ref}")
        print(f"  {'[OK]' if exists else '[MISSING]'}  {ref}")
    for ref in refs:
        exists = _is_nonempty_file(PROJECT_ROOT / "results" / ref)
        is_declared = ref in declared
        if not exists:
            problems.append(f"missing:{ref}")
        if not is_declared:

            problems.append(f"undeclared:{ref}")
        status = "[OK]" if exists and is_declared else \
            "[MISSING]" if not exists else "[UNDECLARED]"
        print(f"  {status}  {ref}")
    return problems


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate all figures used by the slide deck")
    step_names = sorted(_NAME_TO_STEP)
    slow_names = [name for name, *_, slow in STEPS if slow]
    ap.add_argument("--skip-slow", action="store_true",
                    help=f"Skip slow steps: {', '.join(slow_names)}")
    ap.add_argument("--only", action="append", choices=step_names, default=None,
                    help="Build only this named step; may be repeated")
    ap.add_argument("--skip", action="append", choices=step_names, default=None,
                    help="Skip this named step; may be repeated")
    ap.add_argument("--check", action="store_true",
                    help="Validate slide assets without generating them")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the build plan without executing it")
    args = ap.parse_args()

    if args.check:
        if _check_slides():
            raise SystemExit(1)
        return

    only = set(args.only) if args.only else None
    skip = set(args.skip) if args.skip else set()
    chosen = _resolve_steps(only, skip, args.skip_slow)

    print(f"Planned build: {len(chosen)}/{len(STEPS)} steps:")
    for name, script, a, _ in chosen:
        slow = _NAME_TO_STEP[name][4]
        print(f"  {'[slow]' if slow else '      '} {name:12s} {script} {' '.join(a)}")

    if args.dry_run:
        print("\n(dry run: no scripts executed)")
        return

    t_all = time.perf_counter()
    produced = []
    for name, script, a, prod in chosen:
        produced.extend(prod)
        if not _run_step(name, script, a, prod):
            raise SystemExit(f"Build stopped at failed step: {name}")

    print("\n-- Build artifacts --")
    missing_produced = []
    for p in produced:
        ok = _is_nonempty_file(PROJECT_ROOT / p)
        if not ok:
            missing_produced.append(p)
        print(f"  {'[OK]' if ok else '[MISSING]'}  {p}")

    missing = _check_slides()
    full_build = only is None and not skip and not args.skip_slow
    print(f"\nTotal time: {time.perf_counter() - t_all:.0f}s; failed steps: none")
    if missing:
        level = "ERROR" if full_build else "NOTE"
        print(f"[{level}] {len(missing)} slide assets are still missing; "
              "run the corresponding scripts or remove --skip-slow")
    else:
        print("[OK] All slide assets are available; the deck is ready for printing or PDF export")


    if missing_produced or (full_build and missing):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
