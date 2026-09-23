"""Cross-platform entry point for the reproducible teaching workflows."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

USAGE = """\
Usage: python scripts/run_all.py <profile> [options]

Recommended first run:
  1. Preview every automated step:
       python scripts/run_all.py full --dry-run
  2. Build the core device simulation and physics figures:
       python scripts/run_all.py simulation
  3. Study the model interactively:
       python -m jupyter lab notebooks/tutorial.ipynb
     Or execute the Notebook non-interactively and embed fresh outputs:
       python scripts/run_all.py notebook
  4. For new measurements only, confirm the metadata and convert the raw files:
       python scripts/run_all.py keithley --area 12.0
     Replace 12.0 with the recorded illuminated area in cm^2.
  5. Refit one processed measurement bundle:
       python scripts/run_all.py joint --sample 3
  6. Check that all expected results exist:
       python scripts/run_all.py check

One-command reproducible rebuild:
  python scripts/run_all.py full

Profiles:
  full, all       All figures + Cell #3 fit + optimization + executed Notebook.
  quick           Fast forward-model outputs only; skip sweep, EQE, and fitting.
  simulation      Core simulation, J-V, resistance, profiles, bands, and model map.
  sweep           Standard hole-lifetime sensitivity calculation and figure.
  calibration     Cell #3 joint fit plus the synthetic optimization demonstration.
  joint           Joint-calibrate one processed sample selected by --sample.
  eqe             Wavelength-dependent EQE calculation and figure.
  synthetic       Deterministic synthetic J-V smoke-test table.
  notebook        Execute notebooks/tutorial.ipynb in place and embed fresh outputs.
  check           Validate the expected generated result files.
  keithley        Convert Keithley exports using explicitly supplied metadata.

The full profile intentionally does not convert raw experimental files because
illuminated area and wiring polarity are experiment-specific. Convert new raw
data first with the keithley profile or scripts/prepare_data.py. Full always
rebuilds the canonical Cell #3 example; use joint --sample ID for another cell.

The model parameters are always read from config.py. Run this command with the
Python interpreter from the devsim_solar environment. The same commands work in
Windows PowerShell, macOS Terminal, and Linux shells.
"""


def announce(message: str) -> None:
    print(f"\n== {message} ==", flush=True)


def run_python(*arguments: str) -> None:
    subprocess.run(
        [sys.executable, *arguments],
        cwd=PROJECT_ROOT,
        check=True,
    )


def run_notebook(arguments: list[str]) -> None:
    if "--dry-run" in arguments:
        print("[planned] Execute notebooks/tutorial.ipynb in place and embed fresh outputs.")
        return
    announce("Execute the tutorial Notebook and embed fresh outputs")
    run_python(
        "-m", "jupyter", "nbconvert",
        "--to", "notebook",
        "--execute",
        "--inplace", "notebooks/tutorial.ipynb",
        "--ExecutePreprocessor.timeout=1200",
        "--ExecutePreprocessor.kernel_name=python3",
        "--ExecutePreprocessor.record_timing=False",
        "--ClearMetadataPreprocessor.enabled=True",
        "--ClearMetadataPreprocessor.clear_notebook_metadata=False",
        *arguments,
    )
    print("[OK] Updated notebooks/tutorial.ipynb")


def runtime_info() -> str:
    try:
        import devsim
    except ImportError as exc:
        raise SystemExit(
            "The selected Python cannot import DEVSIM. Activate the devsim_solar "
            "environment, then run this command again."
        ) from exc
    return f"Python {sys.version.split()[0]} | DEVSIM {devsim.__version__}"


def main() -> None:
    profile = sys.argv[1] if len(sys.argv) > 1 else "help"
    arguments = sys.argv[2:]
    if profile in {"help", "-h", "--help"}:
        print(USAGE)
        return

    print(f"Project root: {PROJECT_ROOT}")
    print(f"Python command: {sys.executable}")
    print(f"Runtime: {runtime_info()}")

    if profile in {"full", "all"}:
        announce("Rebuild all checked figures and calibration artifacts")
        run_python("scripts/build_results.py", *arguments)
        run_notebook(["--dry-run"] if "--dry-run" in arguments else [])
    elif profile == "quick":
        announce("Rebuild the fast forward-model outputs")
        run_python("scripts/build_results.py", "--skip-slow", *arguments)
    elif profile in {"simulation", "sim"}:
        announce("Rebuild the core simulation and device-physics figures")
        selected = ("demo-data", "sim", "iv", "resistance", "profiles", "band", "model")
        only = [value for name in selected for value in ("--only", name)]
        run_python("scripts/build_results.py", *only, *arguments)
    elif profile == "sweep":
        announce("Run the standard hole-lifetime sensitivity sweep")
        run_python("scripts/build_results.py", "--only", "sweep", *arguments)
    elif profile in {"calibration", "calibrate"}:
        announce("Rebuild the Cell #3 calibration and optimization demonstration")
        run_python(
            "scripts/build_results.py",
            "--only", "demo-data",
            "--only", "joint",
            "--only", "optimization",
            *arguments,
        )
    elif profile == "joint":
        announce("Joint-calibrate one processed measurement bundle")
        run_python("scripts/run_calibration.py", "--joint", *arguments)
    elif profile == "eqe":
        announce("Rebuild the wavelength-dependent EQE result")
        run_python("scripts/build_results.py", "--only", "eqe", *arguments)
    elif profile == "synthetic":
        announce("Regenerate the deterministic synthetic J-V table")
        run_python("scripts/build_results.py", "--only", "demo-data", *arguments)
    elif profile == "notebook":
        run_notebook(arguments)
    elif profile == "check":
        announce("Validate generated results")
        run_python("scripts/build_results.py", "--check", *arguments)
    elif profile == "keithley":
        announce("Convert Keithley exports into processed measurement tables")
        run_python("scripts/prepare_keithley.py", *arguments)
    else:
        print(f"Unknown profile: {profile}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
