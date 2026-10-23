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
- The prototype's 3D viewer was syntax-checked but not rendered in the session-0 sandbox (no network for the CDN); the fallback message path was tested there. **Verified 2026-10-23 on the published Pages site in a Chromium browser:** three.js r128 loads from cdnjs, the massing viewer renders (site, river, context, options A/B/C), the Mermaid diagram on the explainer renders, and the `#tour` deep link plays all nine steps and cleans up its sample reactions on Finish. No console errors. One observation, not fixed: the shell reads the hash only on page load, so changing the hash in an already-open tab does not switch sections (navigation buttons do).
- Voice recording cannot be tested headless. In the published artifact the microphone may be blocked by the viewer sandbox; the control then switches to the typed fallback by design. For a live demo of voice, open `demo/index.html` directly in a browser.
- Illustrations (site plan, three option axons, one drawing per history event) are generated SVGs in `demo/illustrations/` (`generate.py` rebuilds them). A real project replaces them with the deck's own renders via `ek-ingest-presentation`.
- Reactions are device-local. Multi-device merge is Phase 2.
- Sample content (Riverside Community Hub) is invented.

## Hosting (done 2026-10-23)
Repo: https://github.com/clcabana/engage-kit (public). GitHub Pages deploys from `main`, folder `/docs`.
- Explainer site: https://clcabana.github.io/engage-kit/
- Prototype: https://clcabana.github.io/engage-kit/demo/
- Prototype with self-playing tour: https://clcabana.github.io/engage-kit/demo/#tour

`docs/demo/index.html` is a copy of `demo/index.html`; keep them identical when either changes.
