# Request and change log

## 2026-11-21
- Asked to initialize a Git repository and create a commit.
- Added this change-log entry and committed the project files in a new Git repository.
- Outcome: repository initialized and clean; commit verified.

## 2026-11-21
- Asked to read `spec.md`, plan the Tkinter desktop app before coding, and explain the files and calculation organization.
- Implemented the Tkinter app, NumPy calculation module, draggable point loads, embedded Matplotlib diagrams, one-page PDF export, validation tests, dependencies, and updated project instructions. Preserved the user's pending `spec.md` edits.
- Outcome: all 11 automated calculation/PDF tests passed; Python compilation and Tkinter interaction smoke checks passed.

## 2026-11-21
- Asked to build the app following the approved plan and `spec.md`, and run it with `python3`.
- Reran the validation suite and launched the Tkinter application with `python3 app.py`.
- Outcome: all 11 tests passed and the app process is running.

## 2026-11-21
- Asked to run all validation cases in `spec.md` against the beam calculations and report expected versus actual values.
- Ran cases 1–8 directly through `beam_calculations.py` and generated the default one-page PDF for case 7.
- Outcome: all numerical values matched within the specified 0.5% tolerance; the PDF had one page.

## 2026-11-21
- Asked to add the Save and Open feature described in `spec.md`.
- Added a File menu with validated JSON persistence for beam settings and ordered loads, plus round-trip and invalid-file tests.
- Outcome: all 14 automated tests and Tkinter Save/Open interaction checks passed.

## 2026-11-21
- Asked to rerun the `spec.md` validation cases.
- Reran all eight numerical/PDF cases and the automated test suite.
- Outcome: all specified values remained within 0.5%; the default PDF was one page and all 14 tests passed.

## 2026-11-21
- Asked to add the Export results feature described in `spec.md`.
- Added an Export CSV button and Excel-friendly CSV output for sampled x, V, M, and deflection values, including one-sided shear rows at load and support jumps.
- Outcome: all 16 automated tests and the Tkinter CSV-button smoke check passed.

## 2026-11-21
- Asked to rerun the `spec.md` validation cases after adding CSV export.
- Reran cases 1–8 directly and the full automated test suite.
- Outcome: all specified numerical comparisons remained within 0.5%, case 3 failed deflection as expected, the case 7 PDF remained one page, and all 16 tests passed.
