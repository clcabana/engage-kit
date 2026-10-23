---
name: ek-drawing-markup
description: Add 2D sketching and markup to an Engage Kit tool — plans, sections and elevations from the deck as sheets, drawn over in the browser with pen and text, or printed, sketched by hand, photographed and uploaded onto the matching sheet. Use whenever the user asks for sketching, redlines, markups, "draw on the plan", or wants hand-drawn feedback to be part of the record.
---

# Drawing markup

Renders `brief.site.plan_image` and any sheet the ingest tagged `plan|section|elevation` as a sheet
list. Each sheet is a canvas with the drawing beneath and the visitor's strokes above.

## In the browser
- Pen (three widths), eraser, text label, undo; touch and stylus friendly; strokes stored as vector paths
  so they scale. "Clear my marks" only clears this session's layer.
- Save asks one sentence on what the marks mean. Reaction:
  `{feature:'drawing', target:'<sheet id>', kind:'markup', value:{paths, note, thumb}}`.

## On paper
- "Print this sheet" opens a print-sized PDF of the drawing with a sheet id in the corner.
- "Upload a photo of your sketch" accepts JPG/PNG/HEIC up to 10 MB; the visitor picks the sheet it
  belongs to; the image is shown as a layer on that sheet, with a simple two-point align step.

## Rules
- Markups never alter the sheet; they are layers, attributed to a session.
- Photos are images only: strip metadata (location, device) on upload before storing.
- Every markup appears in `ek-submissions-gallery` and in the synthesis, grouped by sheet.
