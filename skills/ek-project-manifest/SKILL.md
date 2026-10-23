---
name: ek-project-manifest
description: Decide which Engage Kit features a specific project should install, and write project.config.json with a one-sentence reason for each include and skip. Use this after ek-ingest-presentation, whenever the user asks what features their engagement tool should have, wants to add or remove a feature, or asks why a feature was or wasn't included.
---

# Project manifest

The manifest is the whole point of Engage Kit: a project installs only what its decisions need. Write
`project.config.json` (schema in the repo root example) from `work/brief.json`.

## Decision table
| Install | When the brief shows |
|---|---|
| `ek-shell` | always |
| `ek-timeline` | ≥ 3 dated history events, or the audience includes people new to the site |
| `ek-site-massing-3d` | ≥ 2 massing options, or any decision point about height, footprint, or placement |
| `ek-program-diagram` | ≥ 4 program areas, or any program marked `contested` |
| `ek-voice-reactions` | audience meets in person (drop-in/workshop) or includes groups less likely to type |
| `ek-massing-markup` | `ek-site-massing-3d` installed and a decision point is location-specific |
| `ek-feedback-synthesis` | always when any other feature is installed |

## Steps
1. Apply the table. For each row write the evidence from the brief in the `reason` field.
2. List skipped features with reasons; the person should be able to overrule in one word.
3. Copy `palette`, `typeface`, `audience` into `project.name/palette/typeface/audience`.
4. Present the list to the person and wait for confirmation. Do not run any feature skill before that.

## Rules
- Maximum 5 feature sections for a public audience; attention is the scarce resource at a drop-in table.
- A feature that cannot record a reaction with context is not installed, whatever the deck shows.
