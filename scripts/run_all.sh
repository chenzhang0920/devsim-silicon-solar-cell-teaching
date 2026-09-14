#!/usr/bin/env bash
# Run the reproducible command-line workflows for the DEVSIM teaching project.
# Physical model parameters remain in config.py; profiles below select workflows.

set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

usage() {
    cat <<'EOF'
Usage: bash scripts/run_all.sh <profile> [options]

Recommended first run:
  1. Preview every automated step:
       bash scripts/run_all.sh full --dry-run
  2. Build the core device simulation and physics figures:
       bash scripts/run_all.sh simulation
  3. Study the model interactively:
       python -m jupyter lab notebooks/tutorial.ipynb
     Or execute the Notebook non-interactively and embed fresh outputs:
       bash scripts/run_all.sh notebook
  4. For new measurements only, confirm the metadata and convert the raw files:
       bash scripts/run_all.sh keithley --area 12.0
     Replace 12.0 with the recorded illuminated area in cm^2.
  5. Refit one processed measurement bundle:
       bash scripts/run_all.sh joint --sample 3
  6. Check that all classroom-slide assets exist:
       bash scripts/run_all.sh check

One-command reproducible rebuild:
  bash scripts/run_all.sh full

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
  check           Validate every local and generated classroom-slide asset.
  keithley        Convert Keithley exports using explicitly supplied experiment metadata.

The full profile intentionally does not convert raw experimental files because
illuminated area and wiring polarity are experiment-specific. Convert new raw
data first with the keithley profile or scripts/prepare_data.py. Full always
rebuilds the canonical Cell #3 example; use joint --sample ID for another cell.

The model parameters are always read from config.py. Select another Python
interpreter with, for example:

  PYTHON_BIN=/path/to/devsim_solar/bin/python bash scripts/run_all.sh full

Examples:
  bash scripts/run_all.sh full
  bash scripts/run_all.sh quick
  bash scripts/run_all.sh simulation --dry-run
  bash scripts/run_all.sh sweep
  bash scripts/run_all.sh notebook --dry-run
  bash scripts/run_all.sh keithley --area 12.0
  bash scripts/run_all.sh keithley --area 12.0 --prune  # complete input bundle only
  bash scripts/run_all.sh joint --sample 3
EOF
}


has_option() {
    local expected="$1"
    shift
    local option
    for option in "$@"; do
        if [[ "${option}" == "${expected}" ]]; then
            return 0
        fi
    done
    return 1
}


announce() {
    printf '\n== %s ==\n' "$1"
}


run_notebook() {
    if has_option "--dry-run" "$@"; then
        printf '%s\n' \
            "[planned] Execute notebooks/tutorial.ipynb in place and embed fresh outputs."
        return 0
    fi
    announce "Execute the tutorial Notebook and embed fresh outputs"
    "${PYTHON_BIN}" -m jupyter nbconvert \
        --to notebook \
        --execute \
        --inplace notebooks/tutorial.ipynb \
        --ExecutePreprocessor.timeout=1200 \
        --ExecutePreprocessor.kernel_name=python3 \
        --ExecutePreprocessor.record_timing=False \
        --ClearMetadataPreprocessor.enabled=True \
        --ClearMetadataPreprocessor.clear_notebook_metadata=False \
        "$@"
    printf '%s\n' "[OK] Updated notebooks/tutorial.ipynb"
}


profile="${1:-help}"
if [[ $# -gt 0 ]]; then
    shift
fi

case "${profile}" in
    help|-h|--help)
        usage
        exit 0
        ;;
esac

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
    if [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/python.exe" ]]; then
        PYTHON_BIN="${CONDA_PREFIX}/python.exe"
    elif [[ -n "${CONDA_PREFIX:-}" && -x "${CONDA_PREFIX}/bin/python" ]]; then
        PYTHON_BIN="${CONDA_PREFIX}/bin/python"
    elif command -v python >/dev/null 2>&1 \
            && python -c "import devsim" >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python)"
    elif command -v python3 >/dev/null 2>&1 \
            && python3 -c "import devsim" >/dev/null 2>&1; then
        PYTHON_BIN="$(command -v python3)"
    else
        printf '%s\n' \
            "No active Python environment found. Activate devsim_solar or set PYTHON_BIN." >&2
        exit 127
    fi
fi

if ! runtime_info="$("${PYTHON_BIN}" -c \
        'import sys, devsim; print(f"Python {sys.version.split()[0]} | DEVSIM {devsim.__version__}")' \
        2>/dev/null)"; then
    printf 'Selected Python cannot import DEVSIM: %s\n' "${PYTHON_BIN}" >&2
    printf '%s\n' "Activate devsim_solar or set PYTHON_BIN to its Python interpreter." >&2
    exit 127
fi

printf 'Project root: %s\n' "${PROJECT_ROOT}"
printf 'Python command: %s\n' "${PYTHON_BIN}"
printf 'Runtime: %s\n' "${runtime_info}"

case "${profile}" in
    full|all)
        announce "Rebuild all checked figures and calibration artifacts"
        "${PYTHON_BIN}" scripts/build_slides.py "$@"
        if has_option "--dry-run" "$@"; then
            run_notebook --dry-run
            exit 0
        fi
        run_notebook
        ;;
    quick)
        announce "Rebuild the fast forward-model outputs"
        "${PYTHON_BIN}" scripts/build_slides.py --skip-slow "$@"
        ;;
    simulation|sim)
        announce "Rebuild the core simulation and device-physics figures"
        "${PYTHON_BIN}" scripts/build_slides.py \
            --only demo-data \
            --only sim \
            --only iv \
            --only resistance \
            --only profiles \
            --only band \
            --only model \
            "$@"
        ;;
    sweep)
        announce "Run the standard hole-lifetime sensitivity sweep"
        "${PYTHON_BIN}" scripts/build_slides.py --only sweep "$@"
        ;;
    calibration|calibrate)
        announce "Rebuild the Cell #3 calibration and optimization demonstration"
        "${PYTHON_BIN}" scripts/build_slides.py \
            --only demo-data \
            --only joint \
            --only optimization \
            "$@"
        ;;
    joint)
        announce "Joint-calibrate one processed measurement bundle"
        "${PYTHON_BIN}" scripts/run_calibration.py --joint "$@"
        ;;
    eqe)
        announce "Rebuild the wavelength-dependent EQE result"
        "${PYTHON_BIN}" scripts/build_slides.py --only eqe "$@"
        ;;
    synthetic)
        announce "Regenerate the deterministic synthetic J-V table"
        "${PYTHON_BIN}" scripts/build_slides.py --only demo-data "$@"
        ;;
    notebook)
        run_notebook "$@"
        ;;
    check)
        announce "Validate classroom-slide assets"
        "${PYTHON_BIN}" scripts/build_slides.py --check "$@"
        ;;
    keithley)
        announce "Convert Keithley exports into processed measurement tables"
        "${PYTHON_BIN}" scripts/prepare_keithley.py "$@"
        ;;
    *)
        printf 'Unknown profile: %s\n\n' "${profile}" >&2
        usage >&2
        exit 2
        ;;
esac
