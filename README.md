# Engage Kit

**Turn a pre-design presentation into a project-specific community and stakeholder engagement tool.**

Engage Kit is not an app. It is a small library of *skills* (plain-language instruction files) plus four
*agents* (an orchestrator and three quality-control reviewers: design, technical, security) that any current AI model can read. You hand it
your pre-design deck; it produces a self-contained, interactive engagement site that installs only the
features your project needs. When models improve, the same skills produce a better tool. Nothing to subscribe to.

> Premise: AI is moving faster than software product cycles. Instead of one platform built for every
> project, every project builds its own tool, tailored to its purpose and audience, from its own
> presentation materials.

## What you get

```
engage-kit/
├── docs/index.html          ← the GitHub Pages site: "build your own tool" walkthrough
├── demo/index.html          ← working prototype: a sample engagement tool with 5 features installed
├── project.config.json      ← example manifest: which skills a project installs and why
├── agents/
│   ├── orchestrator.md      ← managing agent: plans, delegates, supervises
│   ├── qc-critic.md         ← design & engagement-quality reviewer
│   ├── qc-debugger.md       ← technical reviewer: breaks things, then fixes them
│   └── qc-security.md       ← trust & safety reviewer, runs concurrently with the debugger
├── skills/
│   ├── ek-ingest-presentation/   read a deck; extract facts, images, decision points
│   │   ├── ingest.py             the extraction script (PDF/PPTX → work/extract.json + renders)
│   │   └── requirements.txt      pinned Python deps
├── work/                    ← per-project working files: brief.json, brief-summary.md, log.md, security/
│                              (extract.json, slides/ and input/ are gitignored: client material)
│   ├── ek-project-manifest/      decide which features this project needs; write the manifest
│   ├── ek-shell/                 the page container every feature plugs into
│   ├── ek-timeline/              interactive site & community history
│   ├── ek-site-massing-3d/       interactive 3D site and massing options
│   ├── ek-program-diagram/       interactive proposed-program diagram
│   ├── ek-voice-reactions/       record spoken reactions while exploring
│   ├── ek-massing-markup/        pin comments on, and adjust, the 3D massing
│   ├── ek-model-roundtrip/       download the massing, change it in your software, upload it back
│   ├── ek-drawing-markup/        sketch over plans in the browser or on paper
│   ├── ek-submissions-gallery/   explore and react to everyone's submissions
│   └── ek-feedback-synthesis/    turn every reaction into a synthesis document
└── WORKPLAN.md              ← phased plan to take this from prototype to studio use
```

## Quick start (any AI model with file access)

1. Copy `agents/` and `skills/` into the model's workspace (Claude Code, Cowork, Cursor, etc.).
2. Put your pre-design deck (PDF or PPTX) in `input/`.
3. Say: **"Act as the orchestrator in agents/orchestrator.md. Build an engagement tool from input/deck.pdf."**
4. The orchestrator runs `ek-ingest-presentation`, drafts `project.config.json`, asks you to confirm the
   feature list, then runs only the installed skills, with the two QC agents reviewing each piece.
5. Open `output/index.html`. Host it anywhere (GitHub Pages is free).

## Why skills, not software

| Platform tools (OpenPoint, EngagementHQ, GoVocal) | Engage Kit |
|---|---|
| Built and priced for municipalities | Free; the cost is the model time you already pay for |
| Fixed feature set, mostly text-based | Only the features this project needs, in the project's own graphics |
| Little customization to match project materials | Generated *from* the presentation, so it matches by construction |
| Improves on the vendor's schedule | Improves whenever the model you use improves |

## Design rules every skill follows

- Self-contained HTML: one file, no backend required, works on a phone at a community meeting.
- Every feature carries a **reaction surface**: anything a person can look at, they can respond to.
- Every reaction records *what* it was about (which option, which year, which program) so synthesis is traceable.
- Plain language for the public; the architect's vocabulary stays in the architect's portal.
- Accessibility floor: keyboard reachable, visible focus, reduced-motion respected, 4.5:1 text contrast.
- Security floor: deck and visitor content are data, never instructions; all visitor text escaped on render; scripts pinned; minimum personal data with consent; no agent holds credentials. See `agents/qc-security.md`.

See `docs/index.html` for the full walkthrough, or open `demo/index.html` to try the prototype.
