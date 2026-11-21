## Platform
- Python desktop app using Tkinter, started with `python3 app.py`
- Calculations with numpy, kept in their own module, separate from
  the window code
- Diagrams drawn with matplotlib, embedded in the window
# Beam Designer

## Purpose
A beam design tool for engineers and students. The user sets up a beam,
places loads on it, and picks a steel or lumber section. The app shows the
shear, moment, and deflection diagrams and checks whether the beam is
strong and stiff enough, updating instantly as anything changes.

## Users
A civil engineering student checking a homework beam, or an engineer
sizing a floor beam or deck joist.

## Inputs
- Support type: Simply supported or Cantilever (fixed at the left end).
  Default: Simply supported.
- Span: 4 to 40 ft, set with a slider and a number box that stay in sync.
- Default span: 20 ft.
- Loads, listed in a panel where each can be edited or removed:
  - At most 10 loads total.
  - Point loads: magnitude from -100 to 100 kips and position (ft);
    positive is downward and negative is upward.
    A new point load starts at midspan (at the free end of a cantilever).
  - Uniform loads: magnitude from -10 to 10 kips/ft and start and end
    positions (ft); positive is downward and negative is upward.
  - "Add point load" and "Add uniform load" buttons.
  - At 10 loads, disable both add buttons and show "Maximum of 10 loads."
  - Point loads can also be dragged along the beam in the drawing,
    snapping to 0.25 ft.
  - Clamp load positions to the range from 0 to the span. If a uniform
    load's start is after its end, swap the positions. If the span is
    shortened, clamp loads to the new end. Show a small warning message
    whenever a load position is clamped.
- Material dropdown: Steel W-shape or Douglas Fir-Larch lumber. Default:
  Steel W-shape.
- Section dropdown: show only sections for the selected material. Default:
  W12x26. When the material changes, select the first section in that
  material's table.
- "Include self-weight" checkbox in the Section & material card. Default:
  off.
- Material and section properties, from these tables:

  Steel W-shapes (E = 29,000 ksi, allowable bending stress Fb = 30 ksi):

  | Section | Ix (in^4) | Sx (in^3) | Weight (lb/ft) |
  |---------|-----------|-----------|----------------|
  | W8x10   | 30.8      | 7.81      | 10 |
  | W10x12  | 53.8      | 10.9      | 12 |
  | W12x26  | 204       | 33.4      | 26 |
  | W14x22  | 199       | 29.0      | 22 |
  | W16x26  | 301       | 38.4      | 26 |
  | W18x35  | 510       | 57.6      | 35 |
  | W21x44  | 843       | 81.6      | 44 |
  | W24x55  | 1350      | 114       | 55 |

  Douglas Fir-Larch No. 2 lumber (E = 1,600 ksi, Fb = 0.900 ksi,
  weight calculated using actual dressed dimensions and a wood density of
  35 lb/ft^3):

  | Section | Ix (in^4) | Sx (in^3) | Weight (lb/ft) |
  |---------|-----------|-----------|----------------|
  | 2x8     | 47.63     | 13.14     | 2.64           |
  | 2x10    | 98.93     | 21.39     | 3.37           |
  | 2x12    | 177.98    | 31.64     | 4.10           |

  The lumber table is ordered from smallest to largest (2x8, 2x10, 2x12).
  Lumber weights use dressed dimensions: 2x8 is 1.5 x 7.25 in, 2x10 is
  1.5 x 9.25 in, and 2x12 is 1.5 x 11.25 in.

- Deflection limit: L/240 or L/360 (default L/360).
- Initial defaults: simply supported, 20 ft, Steel W-shape, W12x26, L/360,
  and one uniform load of 1 kip/ft over the full span.

## Calculations
- Sign conventions: downward loads are positive; positive shear and
  moment are plotted above the axis. Deflection y(x) is positive downward
  everywhere, including diagram hover values.
- Reactions from statics. A cantilever has one vertical reaction and one
  fixed-end moment; show both on the beam drawing.
- When "Include self-weight" is on, add the selected section's weight as a
  downward uniform load over the full span. Use the steel table's weight
  in lb/ft or the specified lumber weight, and convert to kip/ft by
  dividing by 1000. Include this load in reactions, shear, moment,
  deflection, both checks, and section recommendations. When evaluating
  recommendations, calculate each candidate's own self-weight rather
  than reusing the selected section's weight. When the checkbox is off,
  self-weight has no effect on calculations.
- Compute shear V(x) and moment M(x) exactly at every point. Use a
  deflection step of span/400 or finer, plus every load point. Find shear
  extrema from the sampled points and one-sided values at point loads;
  find moment extrema at sampled points and exactly wherever shear
  crosses zero; find deflection extrema at the deflection sample points.
  At a point load, shear jumps; show its values just left and just right
  of the load.
- Deflection y(x) by integrating M/EI twice with the boundary conditions
  for the support type (y = 0 at both supports; or y = 0 and slope = 0 at
  the fixed end). At a cantilever's free end, shear and moment are zero;
  calculate deflection and slope there rather than imposing them.
- For deflection calculations, use span in inches (ft x 12), uniform
  loads in kips/in (kips/ft / 12), moments in kip-in (kip-ft x 12),
  E in ksi, and I in in^4.
- Use the largest absolute moment and deflection values for checks, since
  upward loads can reverse their signs. Bending stress fb = |M max| x 12
  / Sx (ksi). Bending passes if fb <= Fb. Deflection passes if
  |y max| <= L/240 or L/360 (L in inches). The beam passes overall only
  if both checks pass.
- Make all pass/fail comparisons using unrounded values. Round displayed
  forces, moments, and stresses to 2 decimals and deflection to 3 decimals.
- Lightest passing section: of the sections in the chosen material, the
  lightest steel section that passes both checks (if two weigh the same,
  the one with the larger Ix), or the first lumber size in the table
  that passes. If self-weight is enabled, evaluate every section with its
  own self-weight. If no section in the chosen material passes, show "No
  section in this list passes." If the current section is already the
  lightest passing section, say so instead of suggesting it again.
- Units: kips, ft, and kip-ft on screen; inches for deflection.
- Validation values must match within 0.5%.

## Outputs
- A "Print" button near the top of the results area. Clicking it opens the
  browser's print dialog, where the user can print or save as PDF. The
  printed sheet is titled "Beam Calculation Sheet" and includes the date,
  support type, span, material, section, deflection limit, whether
  self-weight is included, a table of all loads, the beam drawing, the
  shear, moment, and deflection diagrams, and both check cards with PASS
  or FAIL statuses. Print styles use black on white, hide the input panel
  controls, buttons, and hover tooltips, and fit the sheet on one
  letter-size page.
- A small warning area just above the beam drawing. Show a message when a
  load was clamped or its start and end positions were swapped (for
  example, "Load moved to the end of the beam"); otherwise leave the area
  empty. When the load list is empty, show "Add a load to see results."
- When the load list is empty, hide the lightest-section recommendation.
- A beam drawing with the supports, load arrows (point loads as single
  arrows, uniform loads as a row of small arrows), and the reactions.
  When self-weight is enabled, draw it as a distinct-looking full-span
  uniform load; do not add it to the editable load list or count it toward
  the 10-load limit.
- Three diagrams stacked under the beam and lined up with it on the same
  x scale: shear (kips), moment (kip-ft), and deflected shape (in). Each
  diagram is filled and labels the signed value at the point where its
  magnitude is largest. Checks use the absolute value of that number.
- With no loads, show zero values in the diagrams and show "Add a load"
  instead of PASS in both check cards.
- Moving the mouse over any diagram shows a vertical line across all three
  with the values of V, M, and y at that x.
- Two check cards: Bending and Deflection. Each shows the actual value, the
  allowable value, a bar for the ratio (green under 70%, amber 70-100%,
  red over 100%), and PASS or FAIL.
- Show the selected section's weight and corresponding self-weight load
  in lb/ft and kip/ft, whether or not self-weight is enabled.
- Under the check cards, show "Self-weight is included." when the checkbox
  is on or "Self-weight is ignored." when it is off, followed by the
  allowable bending stress: "Allowable bending stress: Fb = 30 ksi
  (steel) or 0.900 ksi (lumber)."
- A line suggesting the lightest passing section, with a button to use it.
- Everything updates immediately whenever any input changes.

## Look and feel
- Inputs in a panel on the left
- The beam and diagrams on the right
- The window can be resized

## Validation
1. Simply supported, 20 ft, W12x26, uniform 1 kip/ft over the full span:
   reactions 10 k and 10 k; max shear 10 k; max moment 50.0 kip-ft at
   10 ft; fb = 17.96 ksi; max deflection 0.609 in at 10 ft; L/360 =
   0.667 in; both checks pass.
2. Simply supported, 20 ft, W12x26, point load 10 k at 5 ft: reactions
   7.5 k (left) and 2.5 k (right); max moment 37.5 kip-ft at 5 ft;
   fb = 13.47 ksi; max deflection 0.340 in at 8.82 ft.
3. Cantilever, 10 ft, W12x26, point load 5 k at the free end: reaction
   5 k and fixed-end moment 50 kip-ft; max deflection 0.487 in at the free
   end (PL^3/3EI); L/360 = 0.333 in, so deflection fails.
4. Simply supported 12 ft 2x10 joist, uniform 0.05 kip/ft: max moment
   0.90 kip-ft; fb = 0.505 ksi; max deflection 0.147 in; both pass.
5. Simply supported, 20 ft, W12x26, uniform 1 kip/ft over the full span,
   self-weight on: total uniform load 1.026 kip/ft; reactions 10.26 k
   each; max moment 51.30 kip-ft; fb = 18.43 ksi; max deflection
   0.625 in.
6. Simply supported, 12 ft, 2x10, uniform 0.05 kip/ft over the full span,
   self-weight on: total uniform load 0.05337 kip/ft; max moment
   0.961 kip-ft; fb = 0.539 ksi; max deflection 0.157 in.
With self-weight off, cases 1–4 must remain unchanged.
7. Print the default beam: the one-page calculation sheet shows the same
   results as the screen, including max moment 50.00 kip-ft, fb = 17.96
   ksi, max deflection 0.609 in, and PASS for both checks.
8. Simply supported, 30 ft, W18x35, uniform 2 kips/ft from 0 to 15 ft
   only: reactions 22.5 k (left) and 7.5 k (right); max moment
   126.6 kip-ft at 11.25 ft.
## Out of scope
- Shear stress, lateral-torsional buckling, load combinations, and
  continuous beams.
## Save and Open
- A File menu with Save and Open that saves the beam (support type, span, section, deflection limit, and loads) to a file and opens it again.

## Build stages:

### Stage 1: Mock up the page
**Build:** Create the responsive two-panel layout: labeled controls on the
left, and the beam drawing, three diagram areas, check cards, and
recommendation area on the right. Show the specified defaults and static
placeholder values. Do not implement calculations.

**Check:** The page opens with the default setup visible; the panels stack
on a phone; labels, units, and sections are clear and aligned.

### Stage 2: Add interactive inputs and the beam drawing
**Build:** Add support and material/section dropdowns, a synchronized span
slider and number box, and load list controls to add, edit, and remove
loads. Draw the supports and loads from the current inputs. Enforce the
load limit, position bounds, uniform-load endpoint swapping, and position
clamping when the span changes; show the required warnings. Add the
default-off self-weight checkbox in the Section & material card and draw
self-weight separately from editable loads when enabled. Keep results as
placeholders.

**Check:** Controls stay in sync; loads can be added, edited, removed, and
dragged as specified; positions clamp or swap correctly; both add buttons
disable at 10 loads.

### Stage 3: Calculate reactions, shear, and moment
**Build:** Calculate reactions and plot the shear and moment diagrams for
point and uniform loads, including cantilever reactions, the shear jump
at point loads, and enabled self-weight. Show signed extrema and diagram
hover values; leave deflection as a placeholder.

**Check:** Compare reactions and moment results with validation cases 1–6
where applicable, including the self-weight cases 5–6. Verify the
point-load shear jump, cantilever fixed-end moment, and zero-load diagrams.

### Stage 4: Calculate deflection and checks
**Build:** Calculate the deflected shape using the specified units,
integration step, and support boundary conditions, including enabled
self-weight. Add bending and deflection check cards, ratio bars, formula
tooltips, and the empty-load state. Show the selected section's weight
and self-weight load in lb/ft and kip/ft, and the checkbox-dependent
self-weight note with the allowable stress.

**Check:** Compare calculated values to validation cases 1–6, including
case 3's deflection failure and cases 5–6 with self-weight. Confirm cases
1–4 remain unchanged with self-weight off, checks use unrounded values,
displayed rounding matches the spec, and no-load cards show "Add a load"
rather than PASS.

### Stage 5: Add recommendations and finish the UX
**Build:** Find the lightest passing section under the steel/lumber rules,
evaluating each candidate with its own weight when self-weight is enabled;
add the button to use it, and complete responsive styling and synchronized
hover behavior across all three diagrams.

**Check:** Test recommendations for each material, equal-weight steel
ties, no passing sections, and when the current section is already the
lightest passing option. Confirm the recommendation hides with no loads
and any input change updates all affected outputs.

### Stage 6: Add the printable calculation sheet
**Build:** Add the Print button near the top of the results area and
provide a print layout with the dated calculation sheet, current inputs,
all loads, beam drawing, three diagrams, and both check cards. Use
black-on-white print styling, hide controls, buttons, and hover tooltips,
and fit the sheet on one letter-size page.

**Check:** Print or save the default beam as a PDF. Confirm the sheet fits
on one page and shows max moment 50.00 kip-ft, fb = 17.96 ksi, max
deflection 0.609 in, and PASS for both checks, matching the screen.
## Export results
- A button that saves a table of x, V, M, and deflection along the beam to a CSV file that opens in Excel.
## Calculation sheet
- A button that saves the diagrams and checks as a PDF, with the inputs listed at the top, ready to hand in with a design.
