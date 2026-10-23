---
name: ek-shell
description: Build the single-file HTML container that every Engage Kit feature plugs into — project header, feature navigation, persistent reaction bar, the window.EK reaction bus, local storage, theming from the project palette, and the accessibility floor. Use this before any feature skill, and whenever the user needs the page shell, navigation, reaction bus, or theme for an engagement tool changed.
---

# Shell

Writes `output/index.html`: one self-contained file, no build, works from `file://` and on a phone.

## Contract every feature relies on
```html
<main id="ek-stage">
  <section data-feature="timeline" hidden> … </section>   <!-- one per installed skill -->
</main>
```
```js
window.EK = {
  project,                                   // from project.config.json, inlined
  react({feature, target, kind, value}),     // appends ts, stores, broadcasts 'ek:reaction'
  reactions(),                               // array, newest last
  show(featureId),                           // switches section, updates nav + location.hash
  on(event, fn)                              // 'ek:reaction' | 'ek:show'
};
```
- Reactions persist in `localStorage['ek:' + project.slug]` inside try/catch; storage absent → memory only.
- The reaction bar (bottom, sticky) is shared: a note field and whichever reaction kinds the installed
  features register via `EK.registerKind(kind, handler)`. Features never build their own bottom bar.

## Theme
- Palette from `project.palette` as CSS variables on `:root`; dark values under
  `@media (prefers-color-scheme: dark)` guarded with `:root:not([data-theme="light"])`.
- One typeface (project's, with a system fallback stack). Type scale: 14 / 16 / 20 / 28 / 44 px.
- Navigation is a horizontal strip of feature names on mobile, a left rail ≥ 900 px.

## Rules
- Pinned CDN scripts only (cdnjs preferred), exact versions, placed before the inline script that uses them.
- `<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">`, safe-area padding.
- Every section starts with one sentence that says what the visitor can do here.
- No feature-specific code in the shell; the shell ships with all sections empty and a visible "nothing installed yet" state.
