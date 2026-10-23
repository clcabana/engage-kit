# Engage Kit — Work plan

From pitch to a studio-ready kit in four phases. Each phase ends with something a person can open.

## Phase 0 — Pitch (done in this session)
- Concept deck (cleaned up from the mid-term draft).
- Repo scaffold: README, three agents, nine skill drafts, example manifest.
- Prototype tool with five features installed on a sample project (Riverside Community Hub, invented).
- This plan.

## Phase 1 — Make the skills real (est. 3–4 working sessions)
Goal: the orchestrator can run end to end on one real pre-design deck and produce a tool without hand edits.
1. `ek-ingest-presentation`: write the extraction script (pdftotext + slide renders); test on 3 real decks; measure how many fields land in `to_confirm`.
2. `ek-shell`: extract the shell out of `demo/index.html` into a template with slots; QC debugger matrix passes.
3. Feature skills: each produces its section from `work/brief.json` alone. Order: timeline → program → massing → voice → markup → synthesis.
4. Round-trip loop: OBJ export from the massing viewer, OBJ/glTF upload with three.js loaders, browser sketching over sheets, and the submissions gallery. The gallery needs shared storage to be meaningful across devices, so it ships device-local in Phase 1 and shared in Phase 2.
4. Orchestrator dry run in Claude Code (has subagents) and in claude.ai (no subagents; sequential). Record token cost per feature so the manifest can show cost next to value.
5. Run the skill-creator eval loop on each skill's description so they trigger reliably.
Deliverable: `output/index.html` for one real project + `HANDOFF.md`.

## Phase 2 — Three portals (est. 4–6 sessions)
Goal: match the objective slide — designer creates, user engages, client acts.
1. Designer portal: a `/build` page in docs that walks a designer through ingest → manifest → publish, with the orchestrator log visible.
2. User portal: the generated tool, hardened for drop-in sessions (offline-first, QR entry, kiosk mode, multi-language copy from the brief).
3. Client portal: the synthesis view with decision-point status (open / endorsed / revised), exportable to the step-7 synthesis document.
4. Shared storage option: today reactions stay on the device. Add one optional sync target (a simple JSON endpoint or a hosted artifact database) so a session's reactions merge.

## Phase 3 — Library growth (ongoing)
Candidate skills, each added only when a project needs it: `ek-live-questionnaire` (facilitated session mode), `ek-precedent-wall` (upload references and react), `ek-site-walk` (geolocated reactions on site), `ek-shadow-study` (sun sweep on the massing), `ek-accessibility-audit` (QC agent for the public audience).

## Phase 4 — Studio adoption
- Pilot on two live projects; compare synthesis quality and engagement counts against the last project run on a platform tool.
- Write the practice note: where the kit fits in steps 5–8 of the consultation workflow, what it does not replace (statutory consultation, record keeping obligations).

## Risks and how the plan handles them
| Risk | Mitigation |
|---|---|
| Model drift breaks a skill | Skills describe outcomes and contracts, not model-specific prompts; QC agents catch regressions |
| Reactions lost on a device | Phase 2 sync; until then synthesis exports after every session |
| Invented facts in the tool | Ingest never guesses; `to_confirm` is surfaced before anything is built |
| Public audience can't use it | QC critic's 60-second rule and the accessibility floor are blocking |
| Voice data handling | Consent copy, device-local by default, transcripts labelled as drafts |
| Injected content steering the build, XSS in generated code, swapped dependencies | `qc-security` reviews every feature concurrently with a written threat model; content is data, not instructions; output escaped; scripts pinned |
| Participation gamed once sessions sync | Device counts shown, rate limits and duplicate detection in Phase 2, moderation before synthesis |

## Token and time budget guidance
A five-feature tool today: ingest ≈ 1 session, shell + features ≈ 2 sessions with QC loops, synthesis + handoff ≈ 0.5 session. Expect halving as the skills mature and models improve — which is the premise.
