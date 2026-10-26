---
name: ek-shell
description: Build the single-file HTML container that every Engage Kit feature plugs into — project header, feature navigation, persistent reaction bar, the window.EK reaction bus, local storage, theming from the project palette, and the accessibility floor. Use this before any feature skill, and whenever the user needs the page shell, navigation, reaction bus, or theme for an engagement tool changed.
---

# Shell

Writes `output/index.html`: one self-contained file, no build step at view time, works from `file://` and on a phone.

## Run it
```
python skills/ek-shell/build.py --brief work/brief.json --manifest project.config.json --out output/index.html
```
`build.py` fills `skills/ek-shell/template.html`. It reads project name, palette, typeface, phase and audience
from the manifest's `project` block (falling back to the brief), creates one empty slot per installed feature
skill, derives the full light and dark token set from the four palette colours, checks ink/paper contrast,
links the typeface from Google Fonts when it is one the script knows, and inlines a `PROJECT` object. It
prints warnings to stderr (missing name, unknown skill, more than 5 public sections, unknown typeface) and
never guesses silently. A sample input lives in `skills/ek-shell/sample/brief.riverside.json`.

## Contract
Every feature skill, and the three QC agents, rely on exactly this.

### Markup
```html
<main id="ek-stage">
  <section data-feature="welcome" data-title="Start"> … </section>        <!-- built by the shell -->
  <section data-feature="timeline" data-title="History" hidden>            <!-- one per installed skill -->
    <!-- ek:slot timeline — the feature skill replaces this whole section -->
    <h2>History</h2><p class="lede">…</p><div class="empty">This part of the tool has not been built yet.</div>
  </section>
</main>
```
- Feature ids and titles are fixed by `build.py` (`FEATURES`): `timeline` History, `massing` Massing, `program`
  Program, `roundtrip` Your model, `markup` Mark up plans, `gallery` Submissions, `synthesis` What we heard.
  `ek-voice-reactions` and `ek-massing-markup` get no section: they extend the bar or the massing section.
- A feature skill replaces its `<section data-feature="…">` in full, keeping `data-feature`, `data-title` and
  `hidden`. Its first child is an `<h2>`, its second a `<p class="lede">` saying what the visitor can do.
- Extra CSS goes in one `<style data-feature="…">` inserted after the `<!-- ek:styles -->` marker (after the
  shell's `</style>` in `<head>`); extra code goes in one `<script data-feature="…">` after the
  `<!-- ek:scripts -->` marker at the end of `<body>` (EK is defined by then). Pinned CDN scripts go
  immediately before the feature's own script. A feature's build removes its own previous blocks before
  inserting, so re-running is safe. Feature code is wrapped in an IIFE; no globals except what it registers
  on `EK`. Full-bleed inside `main`: use `margin:0 -20px; width:calc(100% + 40px)` and, from 900 px,
  `-32px` / `+ 64px` to cancel the shell's `main` padding.
- Two optional hooks on the welcome page: `#welcomeImage` (a site plan or key drawing) and `#welcomeExtra`
  (a strip of option thumbnails, say). Leave them empty rather than fill them with text.

### `window.EK`
```js
EK.version                                    // shell version string
EK.project                                    // inlined PROJECT: slug, name, phase, deadline, one_line, audience,
                                              //   palette, typeface, sample, installed[], sections[], reaction_schema
EK.react({feature, target, kind, value})      // validates (feature+target strings, kind in schema), appends id + ts,
                                              //   stores, emits 'ek:reaction' with the record; returns it or null
EK.reactions()                                // copy of the list, oldest first
EK.remove(id); EK.clear()                     // emit 'ek:reaction' with null
EK.kinds()                                    // ['voice','note','pin','vote','edit','submission','markup']
EK.on('ek:reaction' | 'ek:show', fn)          // handlers are isolated: one throwing does not stop the others
EK.show(id); EK.current()                     // switch section (unknown id → welcome), update nav, hash, scroll, emit 'ek:show'
EK.context(feature, target, hint, label?)     // what the bar's note (and any registered kind) will be about;
                                              //   label is shown instead of target when target is not readable as-is
EK.hasKind(kind)                              // true once a feature registered that kind on the bar; any copy that
                                              //   says "speak" checks this at load (or uses data-with-voice / data-without-voice
                                              //   attributes, which the shell resolves on window load)
EK.toast(msg)                                 // 1.8 s status message, aria-live
EK.registerKind(kind, {icon, label, onActivate(ctx)} | {icon, label, mount(button, slotEl)})
                                              // adds one round button to the bar; mount() gets the button and the
                                              //   bar's extra row (#barSlot) for its own UI; second registration ignored
EK.barSlot(show?)                             // the extra row under the note field; show true/false toggles it
EK.focusNote()                                // put the cursor in the note field (after a pin, say)
EK.registerTour([{go, text, do?, undo?}])     // append steps; the shell plays them (9 s each, Next/Back/Finish,
                                              //   Escape exits, reactions made during the tour are removed on exit,
                                              //   auto-start on #tour, reduced motion → no auto-advance)
```
- Reaction schema (`project.config.json → reaction_schema`): `{feature, target, kind, value, ts}` plus `id`.
  `target` must say what the reaction is about (an option id, a year, a program name, a pin path).
- Storage: `localStorage['ek:' + project.slug]`, JSON array, every read/write in try/catch; storage absent →
  memory only, page still renders. On load, entries that do not have the shape `react()` produces are dropped
  (a tampered store cannot brick the page). `react()` copies schema keys only and always sets `id`/`ts` itself.
  Two tools with the same slug on one origin (e.g. `docs/demo/` and `output/` on GitHub Pages) share a store;
  give each project a distinct name or host them apart.
- Visitor text is stored raw and **escaped on render**: prefer `textContent`; use the global `esc()` only when
  building an HTML string; never put visitor text in an unquoted attribute, in `href`/`src`/`style`, or into
  SVG via `innerHTML`. `value` is not type-checked by the bus: a renderer checks the type it expects per kind.
- Counts (nav badges, vote bars) are per device until a sync target exists; say so wherever a count is shown.
- The welcome card states what is collected and where it goes, shows the device's reaction count and offers
  **Remove all** (`EK.clear()` behind a confirm). The bar's welcome context is the brief's first decision point,
  so even a note typed on the welcome page carries a target.
- On load the shell shows the hashed section (or welcome) *before* feature scripts run, so a feature reads
  `EK.current()` once at start instead of waiting for the first `ek:show`. `hashchange` also switches sections.

### Theme tokens
`--paper --ink --marker --plan --mute --line --card --soft --on-marker --font`, light on `:root`, dark under
`@media (prefers-color-scheme: dark)` guarded by `:root:not([data-theme="light"])` and again on
`:root[data-theme="dark"]`. Features use tokens only; no literal colours except inside the project's own SVGs.
Type scale: 14 / 16 / 20 / 28 / 44 px. Buttons ≥ 44 px, round bar buttons 56 px, visible `:focus-visible`.
Navigation: horizontal strip under the project name below 900 px, a 240 px left rail from 900 px.

## Rules
- Pinned CDN scripts only (cdnjs preferred), exact versions, placed before the inline script that uses them.
- No third-party request by default. The typeface is a system stack unless the manifest sets
  `project.font_link: "google"` (then `HANDOFF.md` must say that every visit reaches Google) or the project
  self-hosts the files with `@font-face`. A typeface name must match `[A-Za-z0-9][A-Za-z0-9 -]{0,40}`;
  anything else is dropped with a warning because it lands inside `<style>`.
- `build.py` warns (stderr) rather than guessing: missing name, bad hex, unknown skill, no section-owning skill,
  more than 5 public sections, unlinked or unknown typeface, no deadline and no decider for the subtitle.
- `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`, safe-area padding.
- Every section starts with one sentence that says what the visitor can do here.
- No feature-specific code in the shell; the shell ships with all sections empty and a visible "not built yet"
  state per slot, and a "nothing installed" section when the manifest installs no features.
- Brief and manifest strings are data: HTML-escaped into markup, JSON-encoded (with `</` neutralised) into
  `PROJECT`. The build never executes anything it reads.
