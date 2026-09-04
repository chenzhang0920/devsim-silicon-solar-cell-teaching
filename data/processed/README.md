# Standardized experimental data

This directory contains cleaned and unit-converted tables derived from the
unmodified files in `data/raw/keithley/`. The bundled Cell #3 and Cell #4 files
are produced by `scripts/prepare_keithley.py` and use voltage in V and current
density in A/cm² (therefore they are J–V tables). The bundled tables use the documented
4.0 cm² illuminated-area conversion. That area is experimental metadata rather than a
DEVSIM device parameter.

Keithley J-V conversions retain the lesson's modeled forward-bias interval,
`0 <= V <= --v-max` (0.72 V by default). Reverse-bias measurements remain in the raw
exports and are not silently claimed as part of these processed calibration curves.

The `*_ishort_sample*.csv` files preserve the repeated near-zero-bias samples
from the short-circuit measurement. `ishort_summary.csv` reports their mean,
standard deviation, mean measured voltage, and sample count. The dark short
measurement is retained as a leakage/offset diagnostic; it is not automatically
treated as a physical illuminated Jsc.

`voc_summary.csv` uses the neutral field name `V_at_I0_V`. Its illuminated rows are
open-circuit-voltage measurements; its dark rows are zero-current voltage offsets, not
photovoltaic `Voc` values.

Power-conversion efficiency is not stored because irradiance at the cell plane was not
recorded with the bundled example. Calculate efficiency only when the incident W/cm²
value has been measured independently.

Do not put generated demo data here. The synthetic J–V smoke-test table belongs in
`data/synthetic/`.
