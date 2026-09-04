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

Profiles:
  full, all       Rebuild every result, then execute and save the tutorial notebook.
  quick           Rebuild only the fast forward-model and figure steps.
  simulation      Run the core simulation and device-physics figures.
  calibration     Run calibration and optimization diagnostics.
  joint           Calibrate one measured cell with all compatible observables.
  eqe             Run the wavelength-dependent EQE calculation and figure.
  synthetic       Regenerate the deterministic synthetic J-V smoke-test table.
  notebook        Execute notebooks/tutorial.ipynb and embed its outputs.
  check           Validate every local and generated asset used by the slide deck.
  keithley        Convert Keithley CSV files; existing other-sample outputs are preserved.

The model parameters are always read from config.py. Select another Python
interpreter with, for example:

  PYTHON_BIN=/path/to/devsim_solar/bin/python bash scripts/run_all.sh full

Examples:
  bash scripts/run_all.sh full
  bash scripts/run_all.sh quick
  bash scripts/run_all.sh simulation --dry-run
  bash scripts/run_all.sh keithley --area 4.0
  bash scripts/run_all.sh keithley --area 4.0 --prune  # complete input bundle only
  bash scripts/run_all.sh joint --sample 3
EOF
}


run_notebook() {
    "${PYTHON_BIN}" -m jupyter nbconvert \
        --to notebook \
        --execute \
        --inplace notebooks/tutorial.ipynb \
        --ExecutePreprocessor.timeout=600 \
        --ExecutePreprocessor.kernel_name=python3 \
        --ExecutePreprocessor.record_timing=False \
        --ClearMetadataPreprocessor.enabled=True \
        --ClearMetadataPreprocessor.clear_notebook_metadata=False \
        "$@"
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

case "${profile}" in
    full|all)
        "${PYTHON_BIN}" scripts/build_slides.py "$@"
        for option in "$@"; do
            if [[ "${option}" == "--dry-run" ]]; then
                exit 0
            fi
        done
        run_notebook
        ;;
    quick)
        "${PYTHON_BIN}" scripts/build_slides.py --skip-slow "$@"
        ;;
    simulation|sim)
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
    calibration|calibrate)
        "${PYTHON_BIN}" scripts/build_slides.py \
            --only demo-data \
            --only calibration \
            --only joint \
            --only optimization \
            "$@"
        ;;
    joint)
        "${PYTHON_BIN}" scripts/run_calibration.py --joint "$@"
        ;;
    eqe)
        "${PYTHON_BIN}" scripts/build_slides.py --only eqe "$@"
        ;;
    synthetic)
        "${PYTHON_BIN}" scripts/build_slides.py --only demo-data "$@"
        ;;
    notebook)
        run_notebook "$@"
        ;;
    check)
        "${PYTHON_BIN}" scripts/build_slides.py --check "$@"
        ;;
    keithley)
        "${PYTHON_BIN}" scripts/prepare_keithley.py "$@"
        ;;
    *)
        printf 'Unknown profile: %s\n\n' "${profile}" >&2
        usage >&2
        exit 2
        ;;
esac
