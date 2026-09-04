# Measuring a Solar Cell — Student Experiment Protocol

This protocol produces measurements suitable for Task 4 of the project. Read it before
using equipment and follow all laboratory instructions given by the instructor.

## 1. What you are measuring

The instrument records terminal voltage and current: a raw **I–V measurement**. The
simulation compares voltage with current density, so data preparation converts it to a
processed **J–V curve**:

$$
J = \frac{I}{A_{illum}},
$$

where `A_illum` is the illuminated active area in cm².

Two measurement branches are defined:

| Branch | Required measurements | Supports |
|---|---|---|
| Core | illuminated I–V sweep plus area and experimental metadata | J–V metrics and an instructor-authorized light-only fit |
| Joint calibration | core branch plus dark I–V, repeated illuminated short-circuit current, and illuminated open-circuit voltage | the recommended multi-observable calibration |

Dark short-circuit and dark zero-current-voltage measurements may also be recorded as
leakage and instrument-offset diagnostics. The dark zero-current voltage is not a
photovoltaic open-circuit voltage (`Voc`), and neither diagnostic is an illuminated
operating-point constraint.

## 2. Equipment and metadata

Use the equipment assigned by the laboratory. A typical setup contains:

- the silicon solar cell and sample holder;
- a solar simulator or stable lamp;
- a source-measure unit (SMU), such as a Keithley instrument;
- two-wire or four-wire leads, as provided;
- a ruler or calipers for illuminated-area measurement;
- a thermometer or temperature sensor;
- a calibrated reference cell or irradiance meter if efficiency will be reported.

Record the following before measuring:

| Field | Record |
|---|---|
| sample identifier | device label used in filenames and report |
| illuminated area | cm² and how it was determined |
| temperature | value, unit, and sensor location |
| illumination | lamp/source, setting, warm-up time, filter, and geometry |
| wiring | two-wire or four-wire; terminal assignment |
| instrument | model and relevant range/compliance/integration settings |
| sweep | start, stop, step size, direction, delay, and repeat count |

Four-wire sensing reduces lead-voltage error but does not automatically remove every
contact or device-series-resistance contribution. If two-wire sensing is used, state it
explicitly so the fitted effective resistance is interpreted correctly.

## 3. Safety and device protection

- Do not look directly into a solar simulator or intense lamp. Use the protective
  equipment and shielding specified by the laboratory.
- Use only the voltage range and current compliance approved by the instructor for the
  specific sample. Do not assume a generic voltage limit is safe for every device.
- Turn the source output off before changing wiring.
- Handle the cell by its edges and avoid scratching or contaminating the illuminated area.
- Stop the sweep if compliance is reached, the device heats unexpectedly, or the signal is
  unstable.

Do not infer the physical p⁺ and n terminals solely from the teaching model. Confirm the
real sample polarity from its documentation or with the instructor, then record how the
SMU HI/LO terminals were connected.

## 4. Prepare the setup

1. Mount the cell with the intended active surface facing the source.
2. Connect the SMU in the assigned two-wire or four-wire configuration.
3. Set a conservative current compliance and output range approved for the sample.
4. Allow the light source and measurement electronics to stabilize.
5. Measure or verify the illuminated active area and record the temperature.
6. If efficiency is required, measure irradiance at the cell plane with a calibrated
   reference. Record the value in W/cm² and the measurement method.

A fitted `photon_flux` or effective generation scale is **not** an irradiance measurement.
It must not be used to calculate experimental efficiency.

## 5. Core illuminated I–V measurement

1. Confirm the polarity with a low-risk test point under instructor supervision.
2. Sweep from short circuit toward forward bias and continue slightly beyond the measured
   zero-current crossing. Use the approved voltage limit and compliance.
3. Use sufficiently small steps to resolve the knee; denser points near the knee and a few
   safe forward-current points improve resistance information.
4. Allow each point to settle before recording it. Keep sweep direction, delay, and
   integration time fixed.
5. Save the native export without editing it.

The processed convention used by this project is:

- `V = V_front(p) - V_back(n)` for the modeled p⁺-on-n device;
- illuminated `J > 0` near short circuit;
- `J` crosses zero at open circuit and becomes negative beyond it.

Your instrument may use the opposite voltage or current polarity. Record the raw convention
first; correct it during processing rather than editing individual values.

## 6. Additional measurements for joint calibration

Use the same area, temperature, wiring and instrument settings wherever possible.

### 6.1 Dark I–V

Block the light completely, verify the dark condition, and repeat the voltage sweep. Record
any changed range, compliance, or integration setting.

### 6.2 Repeated illuminated short-circuit current

Under stable illumination, hold the terminal close to `V = 0` and record repeated current
readings. Keep their timestamps and voltages; do not replace the repeated readings with a
hand-calculated value in the raw file.

### 6.3 Illuminated open-circuit voltage

Measure the zero-current terminal voltage under the same illumination. Record repeated
readings when the instrument workflow supports them.

## 7. Preserve raw data and prepare processed J–V

Never overwrite the only copy of an instrument export. Store raw files under `data/raw/`
and standardized experimental tables derived from them under `data/processed/`.

### 7.1 Generic illuminated two-column export

For a CSV containing one illuminated voltage/current sweep, run a command such as:

```bash
python scripts/prepare_data.py data/raw/my_light_iv.csv --area 4.0 --current-unit mA --out data/processed/measured_iv.csv --plot
```

Replace the example area and unit with recorded values. Use `--voltage-unit`, `--columns`,
or `--skiprows` when required by the export. After inspecting the raw data and wiring,
apply `--voltage-sign -1` and/or `--current-sign -1` only when the corresponding recorded
axis is opposite to the project convention. The processed file has columns:

```csv
V,J
0.000,0.0312
0.025,0.0310
0.650,-0.0011
```

`V` is in V and `J` is in A/cm².

This converter produces one processed illuminated J–V table for the light-only workflow.
It does not create the dark-I–V, repeated-short-circuit, or open-circuit summaries required
by the joint workflow.

### 7.2 Native Keithley 2636B exports

The bundled course example uses filenames matching:

```text
light - iv - 3.csv
dark - iv - 3.csv
light - ishort - 3.csv
light - voc - 3.csv
```

Other sample numbers use the same pattern. Keep each new measurement session in its own
raw directory so one area and polarity transform cannot be applied accidentally to another
group's data. Use a unique numeric sample ID in all four filenames; for example, group 01
could use `data/raw/group01/` and sample `101`. Then run:

```bash
python scripts/prepare_keithley.py --data data/raw/group01 --area 4.0
python scripts/run_calibration.py --joint --sample 101
```

The processed files still go to `data/processed/` by default, where the unique sample ID
keeps them separate. Use `--prune` only when the selected `--data` directory is the complete
intended measurement bundle and you deliberately want stale converter-owned outputs
removed. For the bundled historical setup, the converter defaults are `--voltage-sign -1` and
`--current-sign 1`. These values describe that wiring only; verify and override them for a
new setup. Files labeled `voc` must also remain within the documented zero-current
tolerance (default maximum |I| = 10 nA); change that threshold only to match a known
instrument compliance/noise specification. The converter recognizes both English
(`Index`, `Voltage`, `Current`) and Chinese-locale Keithley column labels, and requires
header units `(V)` and `(A)`. Use the generic converter only for a standalone illuminated
sweep in other units. The Keithley converter locates the
native data columns, converts `I/A` to `J`, and writes
sample-specific files plus `ishort_summary.csv` and `voc_summary.csv`. Existing files and
summary rows for other samples are preserved by default, which makes a partial student
conversion safe. If the input directory is a complete measurement bundle, add `--prune`
to validate that each sample has light/dark J-V plus light Voc/short-circuit measurements
and remove older converter-owned outputs with no matching raw export; unrelated processed
files are always preserved. Measurement-like filename typos are rejected, while unrelated
CSV files are listed in a warning rather than silently treated as measurements.

For the teaching forward-bias workflow, Keithley J-V tables retain only
`0 <= V <= --v-max` (0.72 V by default). Reverse-bias rows remain unchanged in the raw
export but are intentionally excluded from these calibration tables. If reverse-bias
behavior is part of another assignment, prepare and label that dataset separately.

If irradiance was independently measured, pass the measured value in W/cm², for example:

```bash
python scripts/prepare_keithley.py --area 4.0 --irradiance 0.1
```

The numerical value above is the conventional 100 mW/cm² reference; use it only if that
irradiance was established at the sample plane. Without `--irradiance`, the converter
deliberately omits efficiency while still reporting electrical J–V metrics.

## 8. Validate before calibration

Inspect the processed CSV and preview. Confirm that:

- values are finite and sorted by voltage;
- voltage is in V and current density is in A/cm²;
- a measurement exists close to `V = 0`;
- illuminated current density is positive near short circuit;
- the illuminated curve crosses `J = 0` within the safe sweep range;
- the stated area, wiring, temperature, illumination, and sign convention match the raw
  experiment;
- raw, processed, and synthetic files have not been mixed.

For the canonical Cell #3 joint calibration, run:

```bash
python scripts/run_calibration.py --joint --sample 3
```

For an instructor-authorized light-only workflow, run:

```bash
python scripts/run_calibration.py data/processed/measured_iv.csv
```

## 9. Measurement checklist

- [ ] Sample identifier and illuminated area recorded.
- [ ] Temperature, illumination, wiring, instrument settings, and sweep settings recorded.
- [ ] Raw instrument files preserved unchanged.
- [ ] Core illuminated I–V sweep contains short circuit, knee, and zero crossing.
- [ ] Dark I–V, repeated illuminated short-circuit, and illuminated open-circuit data
      collected when using joint calibration.
- [ ] Processed J–V units and signs checked against the raw wiring convention.
- [ ] Irradiance measured independently if efficiency will be reported.
- [ ] Synthetic examples kept separate from experimental data.
