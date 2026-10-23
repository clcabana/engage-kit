---
name: ek-site-massing-3d
description: Add an interactive 3D site and massing viewer to an Engage Kit tool using three.js — context blocks, the site, each design option as adjustable massing, sun/orbit controls, and an option switcher with a vote. Use whenever the brief has massing options, heights, footprints, site plans, or the user asks for a 3D model, massing study, or "let people walk around the options".
---

# Site massing 3D

Builds a lightweight three.js scene from `brief.options[].massing` and `brief.site`. Nothing is imported
from BIM; massing is boxes, which is honest at pre-design.

## Setup
- `three` r128 UMD from cdnjs, pinned. OrbitControls is not in r128's UMD build: implement a 60-line
  orbit (drag to rotate, wheel/pinch to zoom, two-finger drag to pan) rather than loading an extra file.
- Scene: ground plane in `--paper`, context blocks in a muted grey, site outline as a line loop, each
  option's blocks in `--plan`; selected block in `--marker`.
- Camera starts on a 3/4 aerial; "Street view" button drops to 1.6 m at the site edge.
- Sun: a directional light with a "Time of day" slider (9 / 12 / 15 / 18) so shadow impact is felt.

## Controls
- Option tabs A / B / C from `brief.options`; switching animates heights over 400 ms unless reduced motion.
- "Which option works better for you?" vote: `{feature:'massing', target:'option-B', kind:'vote', value:+1}`.
- Click/tap a block to select it (name + storeys shown). If `ek-massing-markup` is installed it takes
  over selection; otherwise selection only informs.

## Fallback
WebGL missing or script blocked → show the deck's massing image for the current option with the same
tabs and vote; the rest of the tool is unaffected.

## Rules
- Dimensions come from the brief; missing footprints render at a labelled default and are listed in HANDOFF.md.
- No textures, no photoreal; the model must look like what it is — a study.
- Canvas height = 60vh on phones, fills the stage on desktop; never traps scroll (wheel zooms only when the canvas is focused).
