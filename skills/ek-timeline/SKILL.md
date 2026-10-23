---
name: ek-timeline
description: Add an interactive site and community history timeline to an Engage Kit tool — dated events from the presentation, a scrubber, images per event, and a reaction surface so visitors can add their own memory or correction to any year. Use whenever the project brief has dated events, a site history, "how we got here", or the user asks for a timeline, chronology, or history feature.
---

# Timeline

Renders `brief.history` as a horizontal scrubber on wide screens and a vertical list on phones. The
visitor's job: understand how the site got here, and add what the architects missed.

## Markup
`<section data-feature="timeline">` containing: the one-sentence purpose line; an SVG axis with one
marker per event (circle, year label, keyboard-focusable `<g role="button">`); a detail card showing the
selected event's year, text, image (if any), and source slide; a "Were you there? Add a memory" control.

## Behaviour
- Arrow keys move between events; the card updates; the axis scrolls the selected marker into view.
- Events the brief marked `[year to confirm]` render with a dashed marker and that label, never a guess.
- "Add a memory" opens the shared reaction bar with `target: year` preset; voice is used if
  `ek-voice-reactions` is installed, otherwise a note.
- Reactions: `{feature:'timeline', target:'1962', kind:'note'|'voice', value}`.
- Existing reactions for a year show as a small count on its marker so later visitors see the layers.

## Rules
- Chronological, one axis, no parallel lanes unless the brief has two distinct histories (site vs. community).
- Never more than 12 events on the axis; group older events into a decade marker that expands.
- Images are the deck's own renders; `object-fit: cover`, with the slide number as caption.
