# Generated course artifacts

Everything in this directory is reproducible output, not raw experimental data. The
source of truth is `config.py`, the selected input under `data/`, and the command that
generated the artifact.

## Student task outputs

| Task | Main artifacts |
|---|---|
| Structure and equilibrium | `model.png`, `band.png` |
| Illuminated device response | `iv_sim.csv`, `iv_plot.png`, `profiles.png`, `eqe.png` |
| Parameter sensitivity | `sweep.png` |
| Joint measured-data calibration | `joint_observables.png`, `joint_metrics.json`, `joint_fitted_params.json`, `joint_fit_metadata.json` |
| Model–data adequacy and identifiability | `joint_identifiability.png` |

## Instructor-support artifacts

`spectrum.png` and `resistance.png` isolate two mechanisms used in the classroom slides.
`optimization.png` and `optimization.gif` show a bounded fit to explicitly synthetic data.

The optional light-only command `python scripts/run_calibration.py [CSV]` creates local
`fit_plot.png`, `identifiability.png`, `fitted_params.json`, and `fit_metadata.json` files.
Those files are intentionally not part of the checked repository baseline: the assessed
calibration uses the joint workflow described in the lab guide.

Rebuild the complete checked baseline with `bash scripts/run_all.sh full`, or follow the
individual commands in `docs/lab_guide.md`. Never relabel a file in this directory as a
measurement.
