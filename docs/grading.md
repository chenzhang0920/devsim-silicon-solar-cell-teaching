# Silicon Solar Cell Modeling — Project Rubric

This public rubric matches the five tasks in [`lab_guide.md`](lab_guide.md). The project is
graded out of **100 points** and contributes **10% of the final course grade**. Each item is
assessed once; the same evidence is not counted under more than one task.

Partial credit is awarded when submitted evidence is incomplete but shows a correct,
traceable method. Unsupported values, mislabeled synthetic data, or plots without units do
not receive full credit.

## Point summary

| Task | Evidence assessed | Points |
|---:|---|---:|
| 1 | Structure, equilibrium, and built-in field | 20 |
| 2 | Illumination, J–V performance, and EQE | 20 |
| 3 | Parameter sensitivity | 15 |
| 4 | Experimental data and joint calibration | 30 |
| 5 | Identifiability, limitations, and reproducibility | 15 |
| **Total** |  | **100** |

## Task 1 — Structure, equilibrium, and built-in field (20 points)

| Criterion | Points |
|---|---:|
| Correctly identifies the front p⁺ emitter, junction, n-type base, illumination direction, and coordinate convention | 6 |
| Presents a readable equilibrium band diagram and obtains the built-in potential using a traceable method and correct units | 8 |
| Explains equilibrium Fermi-level alignment, band bending, and the built-in-field direction using physical reasoning | 6 |
| **Task 1 total** | **20** |

## Task 2 — Illumination, J–V performance, and EQE (20 points)

| Criterion | Points |
|---|---:|
| Presents a readable J–V plot and correctly reports `Jsc`, `Voc`, FF, and `Pmax` with units | 6 |
| Uses internal profiles and the illuminated band panel to explain generation, transport, and quasi-Fermi-level splitting, and relates recombination qualitatively to the observed losses | 6 |
| Presents the modeled EQE and interprets its relationship to the absorption limit and integrated `Jsc` | 5 |
| Applies the voltage/current sign convention and states correctly whether efficiency may be reported | 3 |
| **Task 2 total** | **20** |

Measured EQE is not required. A correct modeled-EQE analysis can receive all Task 2 points.

## Task 3 — Parameter sensitivity (15 points)

| Criterion | Points |
|---|---:|
| Uses a documented, physically meaningful parameter range and produces the required sweep | 4 |
| Reports the simulated values clearly and identifies the observable response from evidence rather than assertion | 5 |
| Explains the trend, nonlinearity or saturation using relevant device physics and acknowledges competing fixed mechanisms | 6 |
| **Task 3 total** | **15** |

## Task 4 — Experimental data and joint calibration (30 points)

| Criterion | Points |
|---|---:|
| Preserves raw data and records sample, area, temperature, illumination, wiring, units, sweep settings, and sign convention | 6 |
| Produces valid processed J–V data with correct area normalization, units, ordering, short-circuit coverage, and zero crossing | 6 |
| Applies the canonical joint-calibration workflow to the assigned dataset and documents the command, varied/fixed parameters, bounds, values, units, and uncertainties | 7 |
| Uses the multi-observable plot and metrics to evaluate illuminated J–V, dark J–V, short-circuit, open-circuit, and residual agreement | 7 |
| Distinguishes effective fitted quantities from independently measured irradiance or unique material constants | 4 |
| **Task 4 total** | **30** |

A light-only fit may replace the joint fit only when the instructor confirms that the
joint observables are unavailable. The report must state this limitation explicitly.

## Task 5 — Identifiability, limitations, and reproducibility (15 points)

| Criterion | Points |
|---|---:|
| Interprets parameter sensitivity, uncertainty, correlation, and bound behavior using the identifiability output | 6 |
| Explains systematic mismatch and identifies at least two relevant model limitations and one measurement limitation | 5 |
| Provides sufficient commands, filenames, parameter changes, and software information to reproduce the reported work | 4 |
| **Task 5 total** | **15** |

## Submission-wide requirements

The following requirements are already included in the task scores:

- figures must have readable axes, units, legends, and captions;
- raw I–V and processed J–V must not be confused;
- synthetic files must be labeled and must not be presented as measurements;
- experimental efficiency must be omitted unless irradiance at the cell plane was measured
  independently;
- conclusions must be supported by figures, tables, residuals, or metadata.
