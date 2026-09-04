# Contributing

Contributions that make the project clearer, more reproducible, or more useful
for undergraduate teaching are welcome. Keep the model intentionally compact:
new complexity should address a documented teaching or validation need.

## Before changing code

1. Create the Conda environment from `environment.yml`.
2. Read `README.md`, `docs/lab_guide.md`, and the relevant module docstrings.
3. Keep physical and calibration defaults in `config.py`; do not duplicate them
   inside scripts or notebooks.

## Development checks

Run these commands from the repository root:

```bash
python -m pytest tests -q
python -m pytest tests -m slow -q
python scripts/build_slides.py --dry-run
python scripts/build_slides.py --check
```

If a change intentionally alters figures or notebook outputs, rebuild and inspect
them before submitting the change. Commit the updated checked `results/` baseline
only when that change is deliberate.

## Data rules

- Keep instrument exports unmodified under `data/raw/`.
- Put standardized experimental tables under `data/processed/`.
- Put generated demonstration data under `data/synthetic/`.
- Do not commit data that contains personal information, confidential metadata,
  or material you do not have permission to share.
- Document area, units, sign convention, illumination condition, and every
  transformation needed to reproduce processed data.
- Report efficiency only when incident irradiance at the cell plane was measured
  independently.

## Scope and style

- Preserve the p+-on-n orientation and the terminal-current sign convention
  unless the change explicitly teaches another architecture.
- Use English for source code, identifiers, terminal messages, and comments.
- Student-facing explanatory prose may remain bilingual where it improves the
  lesson.
- Keep caches, local environments, and disposable `_audit*` results out of commits.
- Add or update a focused test for behavior changes.

By contributing code, you agree that it is provided under the MIT License. By
contributing original teaching content or shareable data, you agree that it is
provided under CC BY 4.0 as described in `LICENSE-CONTENT.md`.
