---
name: ek-program-diagram
description: Add an interactive proposed-program diagram to an Engage Kit tool — program areas drawn as proportional blocks (treemap), a floating card per space with a grow/shrink control, and a "what matters to you" top-five ranking. Use whenever the brief lists program areas, functional program, room sizes, or the user asks for a program diagram, bubble diagram, or space-priority exercise.
---

# Program diagram

Renders `brief.program` as a full-frame treemap: every space is a block whose area is proportional to
`area_m2`. The visitor's job: feel the sizes, say which matter, grow or shrink the ones they care about.

## Run it
```
python skills/ek-program-diagram/build.py --brief work/brief.json --out output/index.html
```
The shell must already exist. The script replaces `<section data-feature="program">`, inserts one
`<style data-feature="program">` at `<!-- ek:styles -->` and one `<script data-feature="program">` at
`<!-- ek:scripts -->`, and is idempotent. The stage uses `EK.fitStage` (class `ek-stage` in an `ek-bleed`
wrapper), so it fills the frame between the header and the reaction bar exactly like the timeline story.

## Markup it writes
```html
<section data-feature="program" data-title="Program" hidden>
  <h2>The spaces inside</h2>
  <p class="lede">Each block is drawn to the size the design team proposed. Tap one to see what it is for, then make it bigger or smaller to show how much it matters. Rank your top five.</p>
  <div class="pg-wrap ek-bleed">
    <div class="pg ek-stage" id="pg">
      <svg id="pgMap" role="group" aria-label="Program diagram, N spaces"> <g role="button" tabindex="0" data-n="…" aria-pressed="false" aria-label="Main hall, 420 square metres"> <rect/> <text/> </g> … </svg>
      <div class="pg-card" id="pgCard"> …selected space: name, use, proposed area, your change, contested chip, − / + / Reset, Rank my top five… </div>
      <div class="pg-card pg-rank" id="pgRank" hidden> …tap spaces in order of importance; Save my top five… </div>
    </div>
  </div>
</section>
```

## Behaviour
- The map is laid out from the **proposed** areas only and never re-flows on a tap: the visitor's suggested
  size is drawn as a dashed accent outline scaled from the block's centre (bigger than the block when grown,
  inside it when shrunk). `area_m2: null` blocks get a dashed grey fill, the smallest known area for layout
  only, and the label "[area to confirm]". Names wrap to two lines and shrink to 13 px before a label is
  dropped; the `aria-label` always carries name, proposed area, the visitor's suggestion and "still being discussed".
- Card placement: under the map on phones (fixed height, so the map's box never changes), beside it from
  900 px. Nothing is ever hidden behind the card.
- One device can move a space at most ±5 steps (±100 m² at the default 20 m² step); the control refuses
  beyond that with a toast, stored values beyond it are clamped, and the card states the step and the cap.
- Tap or Enter/Space on a block selects it: the card shows the plain-language `use`, the proposed area, the
  visitor's change so far, the source slide, and a "still being discussed" chip when `contested` is true.
  `EK.context('program', name, '— tap + or − to change its size')`.
- **+ / −** change the space by 20 m² (10 % of the largest space if that is smaller) and record
  `{feature:'program', target:name, kind:'edit', value:{delta}}`. The visitor's adjustment is the sum of this
  device's edit reactions for that name, so it survives reloads; **Reset** removes those reactions.
- **Rank my top five**: a panel lists every space as a toggle; tapping adds it to the visitor's list in order
  (1–5), tapping again removes it. **Save** records `{kind:'vote', value:rank}` per chosen space, replacing this
  device's previous program votes. The card then shows "You ranked this #2".
- Contested is a marker (ring) plus text, never a colour alone. All colours are shell tokens (`--plan`,
  `--marker`, `--mute`, text in `--paper`).
- Keyboard: blocks are in the Tab order; Enter/Space selects; the card's buttons follow. Arrow keys inside the
  diagram move the selection to the next/previous block by area.
- Tour: three steps (select the first contested space; grow it; open the ranking).

## Rules
- Up to 16 blocks; more than that and the smallest are grouped into one "Other spaces" block with a list in
  its card (never dropped).
- Keep the architect's vocabulary out of the public labels; use the brief's `use` field for what a space is for.
- Everything from the brief or from reactions is rendered with `textContent`; no `innerHTML` with raw strings.
- Per-device: counts and adjustments are this phone's, and the card says so.
