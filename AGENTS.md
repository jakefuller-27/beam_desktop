# Beam Designer project

The primary application is a Python desktop app built with Tkinter. Run it
from the repository root with `python3 app.py`. Do not add a web framework,
build system, or alternate application framework.

## Project layout

- `app.py`: Tkinter controls, beam drawing, embedded diagrams, checks, and
  recommendations.
- `beam_calculations.py`: NumPy-based beam calculations, kept separate from
  the window code.
- `beam_print.py`: one-page PDF calculation sheet generation and opening.
- `spec.md`: requirements and validation values.
- `prompts.md`: request and change log.
- `02_validation/`: hand calculations and automated validation tests.
- `01_data/`: project data files.
- `00_planning/`: planning notes and sketches.
- `03_output/`: screenshots and exported results.

The tracked root `index.html` is a prior web prototype; the Tkinter app is the
current target. Keep the four project documents (`AGENTS.md`, `spec.md`,
`prompts.md`, and `index.html`) at the repository root. Put supporting files in
the matching numbered folder.

Install runtime dependencies with `python3 -m pip install -r requirements.txt`.
Run calculation validation with
`python3 -m unittest discover -s 02_validation -v`.

After each request, add an entry to `prompts.md` describing what was asked,
what changed, and whether it worked.
