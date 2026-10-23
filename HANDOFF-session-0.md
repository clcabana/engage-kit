# Session 0 handoff

Built in one session from the mid-term draft deck. Everything here is a starting point to review, not a finished product.

## What exists
- `README.md`, `WORKPLAN.md`, `project.config.json` (example manifest)
- `agents/`: orchestrator, qc-critic, qc-debugger (markdown instruction files, ~1 page each)
- `skills/`: nine SKILL.md drafts with frontmatter descriptions tuned to trigger from a user's phrasing
- `docs/index.html`: the GitHub Pages explainer (uses Mermaid from cdnjs for the pipeline diagram)
- `demo/index.html`: the prototype tool, hand-built as the reference the `ek-shell` and feature skills will be extracted from

## Phase 1, step 1 — ek-ingest-presentation (started 2026-10-23)
- `skills/ek-ingest-presentation/ingest.py` exists and runs end to end: text per page (pdftotext when poppler is on PATH, else PyMuPDF), 1600 px renders, fonts, measured palette, keyword auto-tags, year / area / option / storey regexes, duplicate-page hashing, `work/extract.json` + `work/brief.skeleton.json`. Pinned deps in `requirements.txt`. OCR via Tesseract when installed; otherwise image-only pages are flagged `needs_ocr` and the model reads the renders.
- Reviewed once by all three QC agents (security: fix, critic: revise, debugger: fix); every blocking finding was closed in one revision. Threat model: `work/security/ek-ingest-presentation.md`. Log: `work/log.md`.
- **Tested on 1 real deck, not the 3 the work plan asks for**, and that deck is the Engage Kit mid-term pitch itself, not an architectural pre-design deck. No pre-design deck exists on the machine. The resulting `work/brief.json` is therefore honest but nearly empty (no site, history, program, options). First thing next session: get 2–3 real pre-design decks (PDF) into `input/` and re-run.
- Lesson from the first deck: every page was a rasterised image with no text layer, so pdftotext would have returned nothing. Expect this from decks exported from InDesign / Miro / Figma; OCR or visual reading is the normal path, not an edge case. Tesseract is not installed here (winget `tesseract-ocr.tesseract` would add it; nobody has installed it).
- Bug found and fixed on the way: the palette quantiser overflowed 8-bit integers and reported white as near-black / cyan.
- Data rule added (qc-security): `input/`, `work/slides/`, `work/extract.json`, `work/brief.skeleton.json` are gitignored because they hold verbatim client material; `work/brief.json` is committed only after a person checks it for personal data. Renders that later skills embed as `history[].image` / `plan_image` may contain photos of residents; the team must decide what is published.

## Known gaps (honest list)
- Skills are instruction drafts; only `ek-ingest-presentation` has a script and has been run (see above). Phase 1 continues with `ek-shell`.
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
