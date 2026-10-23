---
name: ek-massing-markup
description: Add location-specific commenting and light editing to the Engage Kit 3D massing viewer — drop a pin on a block face to comment, and nudge a block's height or position to show what the visitor would change. Use whenever ek-site-massing-3d is installed and comments need to be tied to a place on the model, or the user asks for markups, annotations, pins, or "let people edit the massing".
---

# Massing markup

Extends `ek-site-massing-3d`. Requires it; refuses otherwise.

## Behaviour
- Mode toggle in the 3D section header: Look / Pin / Adjust. Default Look.
- **Pin:** tap a block → a numbered pin (sprite) at the hit point; the reaction bar opens with
  `target: 'option-B/Hall block/north face'`. Pins show for every visitor as numbered dots; selecting one
  shows its note or plays its voice clip.
- **Adjust:** tap a block → height −/+ (one storey per tap) and a 4-way nudge (one grid cell). The
  visitor's change is their own layer; "Show architect's version" toggles back. Each change dispatches
  `{feature:'massing', target:'option-B/Hall block', kind:'edit', value:{storeys:+1}}`.
- Reduced motion: height changes are instant.

## Rules
- Edits never overwrite the brief's geometry; they are stored as deltas.
- Pins are placed with a raycast against option blocks only, never the context.
- A visitor can delete their own pin; nobody else's. (Single device, so "own" = this session.)
