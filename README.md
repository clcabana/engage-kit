# Engage Kit

**Turn a pre-design presentation into a project-specific community and stakeholder engagement tool.**

## Live links

- **[Engage Kit info page →](https://clcabana.github.io/engage-kit/)** what it is, how it works, and how to build one from your own deck.
- **[Showcase project (private) →](https://clcabana.github.io/engage-kit/p/c2be2949/)** a real engagement tool built with Engage Kit.
  It is encrypted: **please ask the author for the passphrase.**
- **[Open sample →](https://clcabana.github.io/engage-kit/sample/)** an invented project with every feature installed; no passphrase needed.

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
│   ├── ek-site-story/            the site's places as a photo story: "must this stay as it is?"
│   ├── ek-site-model/            the team's Rhino site model in 3D (export_3dm.py + viewer), each building a reaction target
│   ├── ek-lock-page/             publish a tool on a static host as an encrypted page that a passphrase opens
│   ├── ek-publish/               build the user and admin portals, lock them, place them for the host, write the project README
│   ├── ek-about/                 the deck's own narrative as paragraphs to underline and react to
│   ├── ek-process-timeline/      the gates ahead, "we are here", questions and "involve me" per gate
│   ├── ek-precedents/            the team's references as a gallery: feels right / not for us, favourites
│   ├── ek-model-pins/            pins on the 3D site model: "where should it go?", keep / change / question
│   ├── ek-site-massing-3d/       interactive 3D site and massing options
│   ├── ek-program-diagram/       interactive proposed-program diagram
│   ├── ek-list-reactions/        principles and plan elements as a ranked list in the team's words
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

## Publishing

Before the deck is read, the orchestrator asks about the accounts that take time to set up: GitHub (or your own
host); an Anthropic account with a separate key and a monthly spending limit, only if you want the assistant;
Cloudflare, only if visitors should be able to ask the assistant. With the feature list it asks the hosting, portal
and chat questions; after the final review `skills/ek-publish/publish.py` acts on the answers. The recommended start:
both portals locked, the assistant for the team only.

- **Two portals.** A **user portal** for the community (public, or behind a passphrase) and an **admin portal** for
  the design team (its own passphrase) with an Admin section where the assistant analyses the reactions. Each locked
  portal is the whole page encrypted (`ek-lock-page`), at a random path. The admin portal need not be hosted at all:
  opened from your own computer it is the strongest separation.
- **The README is private.** The project README (both links, where the passphrases are, how to re-lock, the data
  notes) is written to `output/README.md`, next to the build, and is never published. Nothing but the pages goes into
  the public folder, unless you ask for a minimal public README (neutral title and the user link only).
- **Where it lives.** Your own **GitHub Pages**, free and with no command line: the script prints the steps (create
  an account, a free organisation for a closed group so its pages have their own address, a public repository,
  upload the `docs` folder with "Add file → Upload files", Settings → Pages → `main`, `/docs`). People who use a
  terminal get the `gh` commands. Or **your own domain / existing website**: upload the `dist` folder to any static
  host with HTTPS (the microphone and the encrypted pages need HTTPS). You upload or push; the kit never does.
- **The chat key.** Bring your own LLM key, kept in a small proxy you deploy (`skills/ek-chat/PROXY.md`), or pasted
  by a team member into the admin portal on their own device. The proxy's per-day cap is rough unless its KV
  namespace is bound; the monthly spending limit on the Anthropic account is what bounds cost. A key never goes into
  the manifest, the repo or the README.

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
