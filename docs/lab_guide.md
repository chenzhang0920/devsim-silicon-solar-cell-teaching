# Silicon Solar Cell Modeling — Student Lab Guide

This project introduces semiconductor-device simulation through a one-dimensional,
front-illuminated **p⁺-on-n silicon solar cell**. It is designed for second-year
undergraduates and contributes **10% of the course grade**. The project is marked out of
100 using the public rubric in [`grading.md`](grading.md).

Complete the five tasks in order. The central question is:

> How do device structure and physical parameters become observable J–V data, and what
> can those data support when we calibrate a model?

## Before you begin

Create the environment and verify that the project imports correctly:

```bash
conda env create -f environment.yml
conda activate devsim_solar
python -c "import devsim; print('DEVSIM:', devsim.__version__)"
```

Run commands from the repository root. Model and calibration settings belong in
`config.py`; do not duplicate parameter values inside scripts or the Notebook.

Keep these conventions visible in every figure and table:

- `x = 0` is the illuminated front p⁺ emitter; the n-type base is at larger `x`.
- `V = V_front(p) - V_back(n)`; positive voltage is forward bias.
- Processed curves use the generation-positive convention: illuminated `Jsc > 0`.
- Raw instrument **I–V** uses current `I` in A or mA. Area-normalized **J–V** uses
  current density `J` in A/cm² or mA/cm².
- A modeled efficiency may use the explicitly stated modeled input power. Report an
  **experimental** efficiency only when irradiance at the cell plane was measured
  independently.

The checked files in `results/` are examples, not your submission. Regenerate the
required outputs and record every command and parameter change. Follow the course LMS
for the submission deadline, file format, and group policy.

---

## Task 1 — Structure, equilibrium, and the built-in field (20 points)

### Goal

Connect the p⁺-on-n structure and doping profile to equilibrium band bending, the
depletion region, and the built-in electric field.

### Run

```bash
python scripts/plot_model.py
python scripts/plot_band.py --bias near-voc
```

Use `results/model.png` to establish the device orientation. For Task 1, use the
**equilibrium panel** of `results/band.png`; Task 2 uses its illuminated panel as a
different piece of evidence. The
`near-voc` option derives the operating point from the current model rather than assuming
one fixed voltage for every parameter set.

### Submit

- the device schematic and equilibrium panel of the band diagram;
- one clear annotation locating the p⁺ emitter, junction, n base, and illumination side;
- your calculated or simulated built-in potential, with units and the values used in the
  calculation.

### Explain

1. Why must the equilibrium Fermi level be spatially constant?
2. How does that condition produce band bending at the junction?
3. What sets the direction and spatial location of the strongest built-in field?

---

## Task 2 — Illumination, J–V performance, and EQE (20 points)

### Goal

Relate photogeneration and carrier transport to quasi-Fermi-level splitting, the
illuminated J–V curve, and wavelength-dependent collection.

### Run

```bash
python scripts/run_sim.py
python scripts/plot_iv.py --csv results/iv_sim.csv
python scripts/plot_profiles.py --bias near-voc
python scripts/plot_band.py --bias near-voc
python scripts/plot_eqe.py
```

The direct J-V command plots the simulation alone. To reproduce the explicitly labeled
synthetic overlay used in the classroom deck, first regenerate it and pass it deliberately:

```bash
python scripts/make_demo_data.py
python scripts/plot_iv.py --csv results/iv_sim.csv --data data/synthetic/iv.csv
```

`plot_eqe.py` compares the modeled EQE with the optical absorption limit. It uses the
project's 16-bin teaching spectrum and may take about 30 seconds.

Those bins approximate above-band-gap photons used for generation. The illustrative
modeled efficiency uses a separately stated total input of 100 mW/cm², including omitted
non-generating spectral power; it is not a precision ASTM G173 power balance.

### Submit

- `results/iv_plot.png` and a table containing `Jsc`, `Voc`, FF, and `Pmax`;
- the relevant panels from `results/profiles.png` showing illumination-dependent internal
  quantities;
- the illuminated panel from `results/band.png`, used to explain quasi-Fermi-level
  splitting (the equilibrium panel was assessed in Task 1);
- `results/eqe.png` and the Jsc value obtained from EQE integration.

No additional measured EQE dataset is required, and no synthetic EQE comparison table is
bundled. If the instructor supplies measured EQE, overlay it with:

```bash
python scripts/plot_eqe.py --data path/to/measured_eqe.csv
```

The CSV must contain increasing wavelength values and columns `wavelength_nm` (or
`wavelength`) and `EQE`, where EQE is a ratio from 0 to 1.

### Explain

1. How do generation, recombination, and diode current shape the illuminated J–V curve?
2. What does quasi-Fermi-level splitting mean, and how is it related to terminal voltage?
3. Why can the modeled EQE differ from the absorption limit at short and long wavelengths?
4. Under what experimental condition may efficiency be reported?

---

## Task 3 — Parameter sensitivity (15 points)

### Goal

Test how an observable responds to one physical parameter before deciding whether that
parameter could be calibrated.

### Run

Use the n-base minority-hole lifetime for the standard exercise:

```bash
python scripts/plot_sweep.py --param hole_lifetime --start 1e-6 --stop 1e-4 --n 5
```

If the instructor assigns another parameter, change only `--param`, `--start`, and
`--stop`; keep the range physically meaningful and record it.

### Submit

- `results/sweep.png`;
- a small table of parameter values and the corresponding `Jsc` and `Voc`;
- the baseline value from `config.py`, clearly marked on the table or plot.

### Explain

1. Which observable is most sensitive over the chosen range, and what evidence supports
   that conclusion?
2. Is the response linear, logarithmic, saturating, or negligible?
3. Which physical mechanism explains the trend, and what other fixed mechanism could
   limit it?

---

## Task 4 — Experimental data and Cell #3 joint calibration (30 points)

### Goal

Build a traceable path from raw measurements to standardized J–V data and then calibrate
only the effective parameters supported by the available observables.

Read [`experiment_protocol.md`](experiment_protocol.md) before using equipment. Preserve
raw exports unchanged and record sample, area, temperature, illumination condition,
wiring mode, units, sweep settings, and sign convention.

### Run

First reproduce the canonical bundled Cell #3 workflow:

```bash
python scripts/prepare_keithley.py --area 4.0
python scripts/run_calibration.py --joint --sample 3
```

Then apply the same data checks and calibration logic to your group's measurements when
required by the course. Use the bundled files only as a checked example; do not submit them
as measurements made by your group.

The joint objective uses four observable blocks:

| Observable | Information supplied |
|---|---|
| illuminated J–V | current plateau, knee, and curve shape |
| dark J–V | diode/leakage cross-check and limited leverage on effective series resistance |
| repeated illuminated short-circuit measurement | independent current and repeatability check |
| illuminated open-circuit measurement | independent zero-current voltage check |

The repeated short-circuit readings enter through a summary rather than as many copies of
the same constraint. Dark short-circuit and dark zero-current-voltage files remain offset
and leakage diagnostics; the latter is not a photovoltaic `Voc`. Each J–V block is scaled
by its own characteristic current magnitude and by the square root of its point count, so
a denser sweep does not win merely by containing more rows. The block priorities
and model–data discrepancy scales are documented under `CALIBRATION["joint"]` in
`config.py`. They are transparent teaching choices, not instrument-derived confidence
intervals; change them only with a stated reason and discuss whether the conclusion moves.

In the assessed two-parameter fit, the dark curve is primarily a cross-observable check and
can influence only the effective series resistance; lifetime, SRV, and diode parameters are
fixed. Identifying those mechanisms would require demonstrated sensitivity and richer data.

To keep optimization short enough for class, the residual evaluates the terminal circuit
equation at each measured point. The reported J–V curves and RMSE values are independently
recomputed from the self-consistent terminal relation. They coincide for an exact fit; when
the joint comparison shows systematic disagreement or the normalized residuals exceed the
chosen discrepancy scales, treat covariance as local numerical sensitivity rather than
evidence that the model is physically adequate. The metadata's normalized block score is
the weighted mean squared discrepancy across active blocks: 1 matches the stated scales on
average, while 4 corresponds to a twice-scale weighted RMS mismatch. It is a transparent
teaching diagnostic, not a statistical reduced chi-square.

For a generic two-column measurement, convert raw I–V to processed J–V explicitly:

```bash
python scripts/prepare_data.py data/raw/my_light_iv.csv --area 4.0 --current-unit mA --out data/processed/measured_iv.csv --plot
```

Use the real area and units from your experiment. After checking the wiring and raw
convention, use `--voltage-sign -1` and/or `--current-sign -1` only for axes that need
reversal. If the joint observables were not collected and the instructor
authorizes a light-only fit, run:

```bash
python scripts/run_calibration.py data/processed/measured_iv.csv
```

Treat that reduced fit as less informative than the canonical joint workflow.

### Submit

- a data-provenance table containing the required experimental metadata;
- the raw filenames and processed filenames used, without editing the raw files;
- the observable, fit, and metrics outputs for the assigned dataset, using the canonical
  Cell #3 joint workflow when those measurements are available;
- a table of varied and fixed parameters, bounds, fitted values, units, and uncertainties;
- the exact calibration command and any deliberate `config.py` changes.

### Explain

1. Why does each of the four observables add information to the joint objective?
2. Why are repeated measurements summarized rather than treated as equally independent
   curve points?
3. Which fitted quantities are effective measurement/device parameters rather than unique
   material constants?
4. Where does the residual show systematic model–experiment mismatch?

---

## Task 5 — Identifiability, limitations, and reproducibility (15 points)

### Goal

Decide which fitted values are supported by the data and communicate the limits of the
model and experiment.

### Run

Task 4 creates `results/joint_identifiability.png`, `results/joint_fitted_params.json`, and
`results/joint_fit_metadata.json`. If they are missing, rerun:

```bash
python scripts/run_calibration.py --joint --sample 3
```

### Submit

- `results/joint_identifiability.png`;
- a one-page conclusion that distinguishes fitted values, uncertainty, correlation,
  bounds, and residual mismatch;
- at least two model limitations and one measurement limitation relevant to your result;
- enough commands, filenames, parameter changes, and software information for another
  student to reproduce your figures.

### Explain

1. Does each fitted parameter have sufficient sensitivity and acceptable uncertainty?
2. What does a large-magnitude parameter correlation imply?
3. What should be concluded if a parameter reaches a bound or has uncertainty comparable
   with its value?
4. What additional independent measurement would best reduce the ambiguity, and why?

---

## Final submission checklist

- [ ] All figures have readable axes, units, legends, and captions.
- [ ] Raw I–V and processed J–V are named correctly and traceable to each other.
- [ ] Experimental area, temperature, illumination, wiring, units, and signs are recorded.
- [ ] Every changed `config.py` value is reported.
- [ ] Calibration plots include residual or multi-observable checks, not only a fitted curve.
- [ ] Experimental efficiency is omitted unless irradiance was independently measured.
- [ ] Synthetic data are labeled as synthetic and are not presented as measurements.
- [ ] Conclusions distinguish model evidence from assumptions and limitations.
