"""Run the configured forward simulation and save its J-V curve."""
import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from config import MODEL_PARAMS, MODELED_INPUT_POWER_W_CM2
from model import terminal_iv

RESULTS_DIR = PROJECT_ROOT / "results"


def main() -> None:
    argparse.ArgumentParser(
        description="Run the configured p+-on-n solar-cell simulation"
    ).parse_args()
    V, J = terminal_iv(params=MODEL_PARAMS)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "iv_sim.csv"
    modeled_pin = MODELED_INPUT_POWER_W_CM2 * float(MODEL_PARAMS["photon_flux"])
    pd.DataFrame({
        "V": V,
        "J": J,
        "modeled_input_power_W_cm2": modeled_pin,
    }).to_csv(out, index=False)
    print(f"Saved J-V curve to {out}")
    print(f"Recorded modeled input power: {modeled_pin * 1e3:.1f} mW/cm^2")


if __name__ == "__main__":
    main()
