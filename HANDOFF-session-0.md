# Session 0 handoff

Built in one session from the mid-term draft deck. Everything here is a starting point to review, not a finished product.

## What exists
- `README.md`, `WORKPLAN.md`, `project.config.json` (example manifest)
- `agents/`: orchestrator, qc-critic, qc-debugger (markdown instruction files, ~1 page each)
- `skills/`: nine SKILL.md drafts with frontmatter descriptions tuned to trigger from a user's phrasing
- `docs/index.html`: the GitHub Pages explainer (uses Mermaid from cdnjs for the pipeline diagram)
- `demo/index.html`: the prototype tool, hand-built as the reference the `ek-shell` and feature skills will be extracted from

## Known gaps (honest list)
- Skills are instruction drafts; no skill has been run by the orchestrator on a real deck yet. Phase 1 does this.
- The ingest skill describes a script that does not exist yet (`pdftotext` + slide renders). It is the first thing to build.
- The prototype's 3D viewer was syntax-checked but not rendered in this sandbox (no network for the CDN). Test in a browser before the pitch; the fallback message path was tested.
- Voice recording cannot be tested headless. In the published artifact the microphone may be blocked by the viewer sandbox; the control then switches to the typed fallback by design. For a live demo of voice, open `demo/index.html` directly in a browser.
- Illustrations (site plan, three option axons, one drawing per history event) are generated SVGs in `demo/illustrations/` (`generate.py` rebuilds them). A real project replaces them with the deck's own renders via `ek-ingest-presentation`.
- Reactions are device-local. Multi-device merge is Phase 2.
- Sample content (Riverside Community Hub) is invented.

## To host the GitHub Page
Push the repo; in Settings → Pages choose "Deploy from branch", folder `/docs`. The prototype is also copied to `docs/demo/index.html` so Pages serves it at `<pages-url>/demo/` (add `#tour` for the self-playing tour).
