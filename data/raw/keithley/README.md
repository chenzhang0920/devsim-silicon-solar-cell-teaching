# Keithley native exports

This directory contains unmodified CSV exports from the Keithley 2636B used in
the teaching calibration example. The files intentionally retain the instrument
names and metadata so students can see the original format. The current bundle
contains dark/light I-V, illuminated open-circuit voltage, dark zero-current-voltage,
and short-circuit (`ishort`) measurements for Cell #3 and Cell #4. Raw filenames retain
the instrument's `voc` label, but the dark reading is an offset diagnostic, not photovoltaic
`Voc`.

Convert all exports to standard voltage/current-density files with:

```bash
python scripts/prepare_keithley.py --area 4.0
```

If a calibrated reference cell established the incident irradiance, pass it explicitly,
for example `--irradiance 0.1` for 1 sun. Otherwise the converter deliberately omits
efficiency while still reporting $J_{sc}$, $V_{oc}$, FF and $P_{max}$.

The converter reads this directory by default using the historical setup's explicit
polarity transform, `--voltage-sign -1 --current-sign 1`. Verify and override those values
for a different wiring arrangement. A `*-voc-*` file is accepted only when every recorded
current remains within `--zero-current-tolerance` (10 nA by default), preventing a mislabeled
sweep from entering the Voc summary. English and Chinese-locale `Index`, `Voltage`, and
`Current` column labels are supported, with required header units `(V)` and `(A)`. Use
`prepare_data.py` for exports in mV, mA, or another format. It writes standardized J–V
tables and summary observables to `data/processed/`, including `*_ishort_sample*.csv`,
`ishort_summary.csv`, and `voc_summary.csv`. It preserves existing sample files and merges
summary rows for other samples by default. When this directory contains the complete
intended bundle, add `--prune` to validate the required measurement set and remove older
converter-owned tables that no longer have a matching raw export; unrelated
files are always left untouched. Do not edit the native files; keep corrections in a
separate copy and document the change.

The standardized J-V tables retain `0 <= V <= --v-max` (0.72 V by default), the modeled
forward-bias interval used in this lesson. All reverse-bias rows remain preserved in the
raw exports.

No calibrated irradiance record is bundled. Lamp power readings without a beam area and
measurement plane are not irradiance and must not be entered as `photon_flux` or W/cm².
