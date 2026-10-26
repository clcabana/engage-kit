---
name: ek-site-massing-3d
description: Add an interactive 3D site and massing viewer to an Engage Kit tool using three.js — context blocks, each design option as massing, orbit and sun controls, an option switcher, and a per-device vote. Use whenever the brief has massing options, heights, footprints, site plans, or the user asks for a 3D model, massing study, or "let people walk around the options".
---

# Site massing 3D

Builds a lightweight three.js scene from `brief.options[].massing` and `brief.context_blocks`. Nothing is
imported from BIM; massing is boxes, which is honest at pre-design. The visitor's job: walk around the
options, feel height and shadow, and say which one works.

## Run it
```
python skills/ek-site-massing-3d/build.py --brief work/brief.json --out output/index.html [--root .]
```
The shell must already exist. The script replaces `<section data-feature="massing">`, inserts one
`<style data-feature="massing">` at `<!-- ek:styles -->`, and at `<!-- ek:scripts -->` first the pinned
three.js r128 UMD from cdnjs (with its SRI hash, `crossorigin="anonymous"`) and then one
`<script data-feature="massing">`. Idempotent. Option images named in `options[].image` are embedded as
`data:` URIs (same containment and SVG rules as ek-timeline) for the fallback and the option tabs.

## Markup it writes
```html
<section data-feature="massing" data-title="Massing" hidden>
  <h2>Three massing options</h2>
  <p class="lede">…orbit, switch options, move the sun, vote…</p>
  <div class="ms-wrap ek-bleed"><div class="ms ek-stage" id="ms">
    <div class="ms-view" id="msView"> <canvas id="msCanvas" tabindex="0" aria-label="3D massing model …"></canvas>
      <div class="ms-hud" id="msHud"></div> <div class="ms-fallback" id="msFallback" hidden>…</div> </div>
    <div class="ms-card" id="msCard">
      <div class="ms-tabs" id="msTabs" role="tablist">…one button per option…</div>
      <p id="msDesc"></p> <small id="msMeta"></small>
      <div class="row" data-slot="massing-modes"></div>          <!-- ek-massing-markup inserts Look / Pin / Adjust here -->
      <div class="row"> <label class="chip">Sun <input type="range" id="msSun" min="9" max="18"></label>
        <button id="msStreet">Street view</button> <button id="msReset">Reset view</button> </div>
      <div class="row"> <button class="primary" id="msVote">This option works for me</button> <span class="chip" id="msChoice" hidden></span> </div>
    </div>
  </div></div>
</section>
```

## Behaviour
- Scene: ground plane (`--soft`), context blocks (`--line`/grey), the current option's blocks in `--plan`,
  the selected block in `--marker`, shadows from a directional "sun". Colours are read from the shell's
  tokens at build time and again when the colour scheme changes. No textures, no photoreal.
- Camera starts on a 3/4 aerial framed on all geometry; **Eye level** puts the camera at 1.6 m above the
  ground in front of the site; **Back to overview** returns. Orbit: drag; pan: two-finger drag or shift-drag; zoom: pinch, or wheel **only
  while the canvas is focused** (never traps page scroll). Keyboard on the focused canvas: arrows orbit,
  `+`/`-` zoom, `0` resets.
- Option tabs switch the massing (heights animate 400 ms unless reduced motion). Tap a block to select it:
  the HUD shows label and storeys and `EK.context('massing', 'option-B/Hall', '— tap another block')`;
  tap empty ground to clear. Context otherwise is `option-B`.
- **Vote**: one choice per device. "This option works for me" replaces this phone's previous massing vote
  with `{feature:'massing', target:'option-B', kind:'vote', value:1}` and the chip reads "Your choice (this
  phone): Option B". No counts are shown: one device is not a tally.
- Sun slider 9–18 h moves the light; the HUD shows the hour.
- Fallback: three.js not loaded or WebGL unavailable → the view shows the deck's drawing of the current
  option (embedded) with a one-line note; tabs, vote and sun label still work; the rest of the tool is unaffected.
- Extension point for `ek-massing-markup`: `EK.feature.massing = { option(), options, blocks(), select(mesh|null),
  selected(), onSelect(fn), onPick(fn), scene, camera, renderer, canvas, rebuild(), setDeltas(fn) }`, plus the
  empty `[data-slot="massing-modes"]` row in the card. The viewer never builds pins or edits itself.
- Tour: three steps (switch to the second option; slide the sun; vote).

## Rules
- Dimensions come from the brief: `footprint_m` [w, d], `storeys`, `x`, `y` in metres on a site grid. A block
  missing a footprint renders as a labelled 6 × 6 m placeholder and is listed in the build warnings.
- Storey height 3.4 m (a study assumption, stated in the HUD's "about this model" note).
- Context blocks are the brief's `context_blocks` `[x, y, w, d, storeys]`; none means no context, not an
  invented one. The site outline is drawn only if `site.outline_m` (a polygon) exists. The card's study note
  says what is missing (site line, river, street) so a visitor is not left guessing which edge is which.
- Caps, with a warning for each clamp: 8 options, 40 blocks per option, 300 context blocks, 500 outline
  points; dimensions 0.5–1000 m, storeys ≤ 100, coordinates within ±2000 m. Image paths must be relative
  to `--root` (UNC and absolute paths are refused before the filesystem is touched).
- Everything from the brief is rendered with `textContent`; no `innerHTML` with raw strings.
- Phones: the view takes a fixed pixel height set when the section shows (bar growth shrinks the card only);
  desktop: the card is a 340 px side column.
