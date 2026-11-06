---
name: ek-drawing-markup
description: Add 2D sketching and markup to an Engage Kit tool — plans, sections, axons and site drawings from the deck as sheets, drawn over in the browser with a pen and short labels, or printed, sketched by hand, photographed and added back onto the matching sheet. Use whenever the user asks for sketching, redlines, markups, "draw on the plan", or wants hand-drawn feedback to be part of the record.
---

# Drawing markup

Renders `brief.sheets[]` (or `site.plan_image` as one sheet) as drawings to draw on. The visitor's job:
mark what they would keep or change, then say what the marks mean. Paper is a first-class route: print the
sheet, sketch, photograph, add the photo to the same sheet.

## Run it
```
python skills/ek-drawing-markup/build.py --brief work/brief.json --out output/index.html [--root .]
```
The shell must already exist with `ek-drawing-markup` installed (slot `markup`, "Mark up plans"). The script
replaces `<section data-feature="markup">`, inserts one `<style data-feature="markup">` and one
`<script data-feature="markup">`, and is idempotent.

Brief field, `sheets[]`: `name` (the reaction target; unique), `image` (path under `--root`; the deck's
drawing, a labelled axon or plan is right here, unlike the site story), `source_slide`, optional `text`.
Images follow the kit's image rules (containment under `--root`, SVG checks, rasters re-encoded through
Pillow at up to 1400 px). Up to eight sheets.

## Markup it writes
```html
<section data-feature="markup" data-title="Mark up plans" hidden>
  <h2>Mark up the drawings</h2>
  <p class="lede">Draw straight on the design team's drawings … Or print a sheet, sketch on paper and add a photo of it.</p>
  <div class="dm ek-stage">
    <div class="dm-view"> <svg tabindex="0"> <image/> <g id="dmInk">saved marks</g> <g id="dmLive">unsaved marks</g> </svg>
      <div class="dm-tools" role="toolbar"> Move | Pen | Text | ↶ | + | − </div> </div>
    <div class="dm-card"> sheet chips · source line · [Save my marks] [Start again] · [Add a photo of a sketch] [Print this sheet] · this phone's markups with Remove </div>
  </div>
  <figure class="dm-print" hidden>…one per sheet, shown only when printing…</figure>
</section>
```

## Behaviour
- **Move** drags and pinches (wheel when the sheet is focused; `+`, `−`, `0`, arrows on the keyboard).
  **Pen** draws strokes in the project's marker colour, stored as vector points in sheet-relative
  coordinates (0–1), so they scale with the sheet. **Text** places a label of up to 60 characters at a tap.
  **↶** undoes the last mark; **Start again** clears unsaved marks (with a confirm).
- **Save my marks** records `{feature:'markup', target:<sheet name>, kind:'markup', value:{paths:[{pts}],
  texts:[{x,y,t}], w, h}}`, then sets the bar's context to the sheet and asks what the marks mean, so the
  note that follows is tied to the sheet. Saved marks redraw under new ones at lower opacity.
- **Add a photo of a sketch** takes any image (camera on phones), draws it into a canvas at up to 1200 px
  and stores a JPEG re-encoding as `{kind:'submission', value:{mime:'image/jpeg', base64, w, h}}`. The
  canvas step drops the photo's own metadata (location, device); photos over 12 MB or whose encoding
  exceeds about 1.6 MB are refused with a plain message; a failed storage write is reported.
- **Print this sheet** prints the current sheet with its name and slide in a caption, through a print
  stylesheet; nothing is downloaded or sent.
- The card lists this phone's markups and photos on the current sheet with a thumbnail and **Remove**.
- Tour: two steps (pen on the first sheet; the paper route).

## Rules
- Markups never alter the sheet; they are layers over the deck's own drawing, attributed to a device.
- Values are checked on render: strokes must be arrays of numbers within the sheet, photos must be
  `image/jpeg` base64; anything else shows "Unsupported markup" and draws nothing.
- Sheets are the deck's drawings, named by the deck; a drawing that carries a legal description, a PID or a
  consultant's contact details stays out until the team has cropped it.
- Everything from the brief is HTML-escaped at build time; visitor labels are SVG text nodes; no
  `innerHTML` with raw strings. Shell tokens only.
- Copy says "say or type" only when `EK.hasKind('voice')` is true at click time.
