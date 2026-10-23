---
name: ek-ingest-presentation
description: Read an architectural pre-design presentation (PDF or PPTX) and extract everything an engagement tool needs — project facts, site and community history with dates, program areas with sizes, design options, decision points, audience, images, and the firm's palette. Use this first whenever a user wants to build an engagement tool, community portal, stakeholder site, or "interactive version" of a deck, even if they only say "here's our presentation".
---

# Ingest presentation

Turn a deck into `work/brief.json`, the single source every other skill reads. Never rebuild the tool
from the deck directly; rebuild it from the brief.

## Steps
1. Extract text per slide (`pdftotext -layout` for PDF; python-pptx for PPTX). Render each slide to PNG
   at 1600 px wide into `work/slides/NN.png` for images the tool may reuse.
2. Read every slide. Tag each with one of: context, site, history, program, option, precedent, process,
   schedule, other. Note slide numbers; later skills cite them.
3. Fill the schema below. Leave a field empty rather than guessing; list guesses under `to_confirm`.
4. Pull the palette from the slides (dominant non-white, non-black colours) and the typeface if named.
5. Write a 10-line plain-English summary to `work/brief-summary.md` for the person to check.

## Schema (`work/brief.json`)
```json
{
 "project": {"name":"", "client":"", "location":"", "phase":"", "one_line":""},
 "audience": [{"group":"", "what_they_decide":"", "how_they_meet":"drop-in|workshop|online|committee"}],
 "history": [{"year":"", "event":"", "source_slide":0, "image":"work/slides/NN.png"}],
 "site": {"description":"", "constraints":[], "plan_image":"", "north_up":true},
 "program": [{"name":"", "area_m2":null, "use":"", "contested":false, "source_slide":0}],
 "options": [{"id":"A","name":"","description":"","massing":[{"label":"","footprint_m":[0,0],"storeys":0,"x":0,"y":0}],"image":""}],
 "decision_points": [{"question":"", "options":[], "who_decides":"", "when":""}],
 "palette": {"paper":"", "ink":"", "accent1":"", "accent2":""},
 "typeface": "",
 "candidate_features": ["ek-timeline","ek-site-massing-3d","ek-program-diagram","ek-voice-reactions","ek-massing-markup"],
 "to_confirm": []
}
```

## Rules
- Dates, areas, and option descriptions come verbatim from the deck or go in `to_confirm`.
- A deck with no dated events still gets a `history` array (empty) so `ek-project-manifest` can skip the timeline on evidence.
- Massing dimensions: estimate from plans only if a scale bar or dimension is present; otherwise record `storeys` and set footprint to `null`.
