---
name: ek-model-pins
description: Let visitors drop pins anywhere on the Engage Kit 3D site model (terrain, water or a building) and say what the spot means — "where should it go?" (a program element the model does not have yet) and "what about this spot?" (change, question). Use whenever ek-site-model is installed and the user wants location-specific comments, pins, markers or "put it here" reactions on the team's own model; not for the deck-drawn option boxes (that is ek-massing-markup on ek-site-massing-3d).
---

# Model pins

Augment of `ek-site-model` ("The model"). No section: one `<style data-feature="pins">` at `<!-- ek:styles -->`
and one `<script data-feature="pins">` immediately after `<script data-feature="model">`. Requires the model's
extension point (see `ek-site-model/SKILL.md`, "Extension point"); refuses an output built before it.

## Run it
```
python skills/ek-site-model/build.py --brief work/brief.json --model model.json --out output/index.html --root work
python skills/ek-model-pins/build.py --brief work/brief.json --out output/index.html
```
Idempotent: removes its own blocks before inserting. Re-running `ek-site-model` keeps the pins script after the
model's (the model re-inserts itself right after the shared `lib-three` tag). Brief field read: `program[].name`
(max 24, 60 characters each), JSON-encoded into the script.

## Behaviour
- **Drop a pin** in the card's `#smSlot` row, which the model shows only in overview: while a building is selected
  its own votes are the way to react, the row is hidden, and choosing a building cancels a pin being placed. Armed, the next tap on
  the model places a pending pin at the first surface the ray meets (terrain, water, a proposed building), drawn
  as a marker-coloured sphere on a thin stem, with a label pill projected each frame like the building labels.
  A drag still turns the model; a tap on empty sky says so and stays armed.
- A small field over the view (moved to the half of the view the pin is not in) asks "What should go here, or what
  about this spot?" (60 characters, optional) and a kind, one scrolling row of chips, the program first:
  **A building from the program** (only when the brief's program has elements no model building carries, matched
  by whole words either way, so "Main hall" counts as the modelled "Hall"; it opens a second row of those names in
  brief order, each "<name> — not in the model yet, pin where you would put it", "<name> · not in the model yet"
  under 600 px; when exactly one element is unmodelled, that name chip stands in the first row itself), then
  **Change this**, **Question**. No "Keep this": "The spot works" on a building says that. Tapping another spot
  while the field is open moves the pin. Escape or Cancel drops it.
- **Save pin** records `{feature:'model', target:'pin:<x>,<y>,<z> (<near>)', kind:'pin', value:{x,y,z,label,kind[,program]}}`,
  coordinates rounded to 0.1 m; `kind` is `welcome|change|question` (`keep` pins stored by earlier builds still
  read and show as "Keep this"), `program` the chosen name for `welcome`.
  `<near>` is the building hit, else the nearest proposed building within 20 m (plan distance to its bbox), else
  "the ground" ("the water", "an existing building" for those surfaces). A null from `EK.react` is said, not hidden.
- Saved pins render on load and are listed in the card ("Your pins (n, on this device)") with **Remove**. Tapping a
  pin in the view or its list entry selects it: name, kind, place and coordinates, **Say why** (sets
  `EK.context('model', <pin target>, …, 'Your pin: <label>')` and focuses the bar), **Remove**, **Done**, and the
  notes and clips the bar stored on that target. Removing a pin removes its notes too. Choosing a building ends the
  pin selection; tapping elsewhere returns the tap to the model's own building select.
- Fallback (no three.js, no WebGL, no extension point): the card says pins need the 3D view; nothing else runs.
- Tour: one step after the model's — its `do()` itself records an example pin with `tour: true` on the terrain under
  the middle of the view and selects it (no deferred write; nothing when the tour is not running); `undo` removes it
  on Back / exit, and the shell removes tour:true records made during the tour anyway.
- `EK.feature.pins = {list(), select(id), arm(on), valid(record)}` for tests and later augments.

## Rules
- Every stored pin is re-validated on render: target starts with `pin:`, x/y/z finite numbers inside the model's
  bbox (+1 m), known kind, string program for `welcome`, label cut to 60. Others are skipped and counted in the card.
- Visitor text and program names go into the DOM with `textContent` only; no `innerHTML` anywhere in the script.
- Pins are this device's own (single-device store); the card says so wherever it counts them.
- Pin objects live in the model's `scene` (not its rebuilt group), share three geometries, and recolour from the
  tokens on every draw (`--marker` ball, `--ink` stem), so theme changes and model rebuilds keep them.

## Brief flags for the program chips
`program[].in_model: true` marks an element the model already carries under another label (the deck's
"retreat cabins" are the model's "Hermitage cabin" instances), and `program[].pinnable: false` marks an
element that is not placed with a pin (a road). Both are left out of "not in the model yet"; without the
flags the build falls back to whole-word name matching against the model's labels.
