# Standardized experimental data

This directory contains cleaned and unit-converted tables derived from the
unmodified files in `data/raw/keithley/`. The bundled Cell #3 and Cell #4 files
are produced by `scripts/prepare_keithley.py` and use voltage in V and current
density in A/cm² (therefore they are J–V tables). The bundled tables use the documented
3 cm × 4 cm illuminated dimensions, corresponding to a 12.0 cm² current-density
normalization area. That area is experimental metadata rather than a DEVSIM device
parameter.

Keithley J-V conversions retain the lesson's modeled forward-bias interval,
`0 <= V <= --v-max` (0.72 V by default). Reverse-bias measurements remain in the raw
exports and are not silently claimed as part of these processed calibration curves.

The `*_ishort_sample*.csv` files preserve the repeated near-zero-bias samples
from the short-circuit measurement. `ishort_summary.csv` reports their mean,
standard deviation, mean measured voltage, and sample count. The dark short
measurement is retained as a leakage/offset diagnostic; it is not automatically
treated as a physical illuminated Jsc.

`voc_summary.csv` uses the neutral field name `V_at_I0_V` for the median repeated
voltage. `V_std_V` is the sample standard deviation and `V_n_points` is the
number of retained readings; these names prevent confusion with the short-circuit
summary's voltage spread and `n_points`. Illuminated rows are open-circuit-voltage
measurements; dark rows are zero-current voltage offsets, not photovoltaic `Voc` values.

Power-conversion efficiency is not stored because irradiance at the cell plane was not
recorded with the bundled example. Calculate efficiency only when the incident W/cm²
value has been measured independently.

Do not put generated demo data here. The synthetic J–V smoke-test table belongs in
`data/synthetic/`.
