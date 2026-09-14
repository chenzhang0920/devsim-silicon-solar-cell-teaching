# Data organization

The project keeps data provenance visible in the directory name:

- `raw/`: unmodified experimental instrument exports. Treat these files as
  immutable source records.
- `processed/`: standardized experimental tables generated from `raw/` (for
  example the Cell #3/#4 light and dark J–V files and `voc_summary.csv`).
- `synthetic/`: deterministic model-generated data used for hardware-free
  demonstrations and regression checks.

Never mix synthetic files into `raw/` or `processed/`, and never overwrite a
raw export during conversion. See the README in each directory for the exact
workflow.
