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

## Phase 1, step 2 — ek-shell (2026-10-25)
- `skills/ek-shell/template.html` + `build.py` produce `output/index.html` from a brief and a manifest: header, nav (strip on phones, 240 px rail from 900 px), theme tokens derived from four palette colours with contrast floors enforced, `window.EK` bus, device-local storage, shared reaction bar, toast, tour runner, one empty slot per installed section-owning skill. The Contract in `skills/ek-shell/SKILL.md` is what every feature skill and QC agent now builds against.
- Extracted from `demo/index.html`, which is unchanged. What left the shell comes back through feature skills: timeline, massing, program and synthesis sections; the SVG image bank; three.js; the voice recorder (via `EK.registerKind('voice', …)`).
- `output/index.html` is the Riverside sample with all slots empty ("not built yet"). It is a container, not a tool yet.
- One QC round (security block → critic revise → debugger fix), all blocking findings closed in one revision: typeface string validated before it reaches `<style>`; malformed stored reactions dropped on load; Google Fonts off by default (opt-in `project.font_link: "google"` in the manifest); welcome card states what is collected and offers Remove all; mute grey meets 4.5:1 in both schemes; desktop bar no longer covers the rail; palette keys `marker`/`plan` accepted as aliases of `accent1`/`accent2`; welcome copy derived from installed features; bar context on welcome is the brief's first decision point. Not re-reviewed by the agents after the revision; re-verified by the orchestrator in the browser.
- **Data notes the team must settle before a live session** (from qc-security): notes are free text and will carry names, including children's, on shared phones; retention is "until someone clears the device"; "the team collects them" has no mechanism in the shell yet (export lives in `ek-feedback-synthesis`); per-device counts are not a consensus; if `font_link` is turned on, every visit reaches Google; two tools with the same project name on one GitHub Pages origin share a reaction store; confirm PIPA (BC) applicability with the client.
- Typeface: the sample now renders in the system stack, not Archivo, because the third-party font request is opt-in. Self-hosting Archivo via `@font-face` is the clean fix (Phase 1 follow-up).
- Local preview: `python -m http.server 8765 --directory engage-kit` from the parent folder, then `http://localhost:8765/output/index.html`.

## Known gaps (honest list)
- Skills are instruction drafts except `ek-ingest-presentation` (script, run once) and `ek-shell` (template + build, run on the sample). Phase 1 continues with `ek-timeline`, the first feature to land in a slot.
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
