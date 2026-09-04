# Raw experimental data

Keep original instrument exports here without editing. The bundled
`keithley/` directory contains the native Keithley 2636B files used to produce
the standardized Cell #3/#4 tables in `data/processed/`.

Keep each new measurement session in a separate subdirectory such as `group01/`.
That prevents one illuminated area or polarity transform from being applied to another
group's files; use a unique numeric sample ID in the native filenames.

Generated teaching data is not raw data; it belongs in `data/synthetic/`.
