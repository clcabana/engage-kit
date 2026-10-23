---
name: ek-program-diagram
description: Add an interactive proposed-program diagram to an Engage Kit tool — program areas drawn as proportional blocks or bubbles, with adjacency, a "what matters to you" ranking, and the ability to grow or shrink a space to express priority. Use whenever the brief lists program areas, functional program, room sizes, or the user asks for a program diagram, bubble diagram, or space-priority exercise.
---

# Program diagram

Renders `brief.program` as a packed set of rectangles whose area is proportional to `area_m2` (treemap
style, SVG). The visitor's job: feel the sizes, say which matter.

## Markup and behaviour
- SVG treemap sized to the stage; each program is a `<g role="button">` with name and area label; text
  hides when the block is narrower than its longest word.
- Selecting a block shows its use description and whether it is marked contested.
- "Should this be bigger or smaller?" −/= /+ control on the selected block: re-packs the treemap live with
  the visitor's adjusted areas (their copy only; the architect's version is one tap away as "Reset").
- "Rank what matters most": drag (or arrow keys) to order up to 5 programs.
- Reactions: `{feature:'program', target:'Community kitchen', kind:'edit', value:{delta:+20}}` and
  `{kind:'vote', value:rankPosition}`.

## Rules
- Areas missing from the brief render as equal blocks with a dashed outline and "[area to confirm]".
- Contested programs carry a small marker, not a colour change, so the signal survives greyscale.
- Keep the architect's vocabulary out of public labels; use the plain-language `use` field.
