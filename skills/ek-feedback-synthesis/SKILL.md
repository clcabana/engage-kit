---
name: ek-feedback-synthesis
description: Turn every reaction an Engage Kit tool collected — votes, notes, pins, voice clips, edits — into a traceable synthesis view inside the tool and an exportable synthesis document for the step-7 feedback meeting. Use whenever the user asks what people said, for a "what we heard" report, results, synthesis, export, or when the tool is complete and needs its results section.
---

# Feedback synthesis

Adds `<section data-feature="synthesis">` (visible to the team, reachable from the nav as "What we heard")
and the export routine.

## In-tool view
- Counts by feature and kind; votes per option; program size deltas as a signed bar per program.
- A chronological list of every reaction with its context chip (feature / target), note text, pin number,
  or audio player.
- "Copy as JSON" (textarea select) and "Copy as Markdown" for the synthesis document. Download links are
  inert in some hosts; copy always works.

## Synthesis document (Markdown, exported by the team's model at step 7)
1. Project, date range, number of sessions and devices.
2. For each decision point in the brief: what the reactions say, with counts and three verbatim notes
   (or transcript lines, labelled machine-transcribed).
3. Program: requested changes, ordered by net delta.
4. Massing: pins grouped by block, with the plain-language theme of each group.
5. What this does *not* tell us: sample size, who was missing, and anything the tool could not capture.
6. Recommended revisions for step 8, each tied to the reactions that motivate it.

## Rules
- Every claim in the document links back to reaction ids; nothing is summarized without a source.
- Counts are shown with the number of devices they came from; one enthusiastic phone is not a consensus.
- Transcripts are drafts; the team confirms them before the client sees them.
