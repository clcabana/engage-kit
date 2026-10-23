---
name: ek-submissions-gallery
description: Add an "Explore submissions" section to an Engage Kit tool where everyone — visitors, designers, client — can browse, compare and react to the models, markups and sketches other people have uploaded. Use whenever ek-model-roundtrip or ek-drawing-markup is installed, or the user asks to show what people have come up with, a gallery of responses, or to make participation visible to all portals.
---

# Submissions gallery

Lists every `submission` and `markup` reaction as a card: thumbnail, which option or sheet it responds
to, the one-sentence note, when it was made, and a session tag (never a name).

## Behaviour
- Filter by option / sheet; sort by newest or most reacted-to.
- Open a card: a 3D submission loads beside the original option in the massing viewer; a markup opens
  on its sheet. Reactions to a submission use the shared bar with `target: 'submission/<id>'`.
- A live count ("23 submissions from 9 devices") sits at the top and is the number every portal shows.
- Designer and client portals see the same gallery with one extra control: "Include in synthesis"
  (default on) and a "Hide" that records a reason.

## Rules
- Nothing appears in the gallery before `qc-security` has checked the upload (format, size, stripped
  metadata, no embedded scripts). Until then the card shows "Checking…" to its owner only.
- The gallery is public to everyone with the link; say so in the consent sentence on upload.
- Counts always show devices alongside submissions.
