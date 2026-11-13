---
name: ek-about
description: Put the design team's own account of the plan on the Start page of an Engage Kit tool — the deck's narrative, verbatim, as a short intro (the first block) with the rest behind "In the design team's words", every paragraph a reaction target (note or voice through the bar). Use when the brief has about.blocks and ek-about is installed, or when the user wants the team's written account of the plan shown so residents can respond to it paragraph by paragraph.
---

# About the plan (on Start)

The team's narrative lives on the Start page, not in its own nav section (the critic: a reading page nobody
opens). The first `brief.about.blocks[]` entry is a short intro under the shell's hero; the remaining blocks sit
in a `<details>` the visitor can open. Every paragraph is a reaction target.

## Run it
```
python skills/ek-about/build.py --brief work/brief.json --out output/index.html
```
Needs an `output/index.html` from `ek-shell`. The shell still creates an `about` slot when ek-about is installed
(the shell's `FEATURES` entry stays for compatibility); this build **removes** that
`<section data-feature="about">` so the nav has no "About the plan" (fine if it is already gone), and writes
into `#welcomeExtra`, after the `ek-process-timeline` strip when there is one. Reads `about.blocks[]`: `title`
(required, ≤ 80 chars), `text` (required), `source_slide`, optional `note`. Prints a JSON summary (blocks,
paragraphs, blocks cut) to stdout and warnings to stderr. Idempotent: it removes its own
`<style data-feature="about">` / `<script data-feature="about">` and its own Start block before inserting.

**Source line.** A block may carry `source` (plain text, 120 characters): the attribution shown under it in
place of "From the presentation, slide N", for text that is not on a numbered slide (a poster) or was written by
the team for the page ("From the design team, written for this page"). A block with `source` needs no
`source_slide`. Never use it to present the team's words as the presentation's.

## Markup (inside `#welcomeExtra`)
```html
<!-- ek:start-about -->
<div data-slot="start-about" data-feature-owner="about" class="ab">
  <article class="ab-block ab-intro" id="abBlock-0">
    <h3 class="kicker ab-t">Title</h3>
    <div class="ab-para" data-target="Title ¶1" data-label="Title, paragraph 1">
      <p class="ab-p" tabindex="0">…verbatim text…</p>
      <div class="row ab-act" hidden><button class="primary ab-react">React to this</button></div>
      <div class="ab-mem" role="list"></div>
    </div>
    <small class="ab-src">From the presentation, slide 2</small>
  </article>
  <details class="ab-more"><summary>In the design team's words</summary>
    <div class="ab-rest"> …the remaining blocks, same markup… </div></details>
  <div class="ab-other" hidden>…notes on paragraphs that no longer exist…</div>
</div>
<!-- /ek:start-about -->
```
With one block there is no `<details>`.

## Behaviour
- Tap (or Enter/Space on) a paragraph: it is highlighted, "React to this" appears, and while Start is shown the
  bar's context becomes `EK.context('about', '<title> ¶n', '— what do you think of this?', '<title>, paragraph n')`.
  Tapping it again, Escape, or closing the details clears it and puts back the Start context the shell had set
  (the first decision point). Coming back to Start with a paragraph still highlighted re-applies its context
  after the shell's. A tap that ends a text selection is ignored. With nothing highlighted the shell's welcome
  context is left alone.
- **React to this** focuses the note field (`EK.focusNote()`); toast "Speak or type below" only when
  `EK.hasKind('voice')`.
- No underline / `matters` vote (removed: it duplicated "React to this" and nobody read underlines back); old
  `vote` records are ignored.
- This device's notes and voice clips for a paragraph list under it (textContent; audio only for an
  `audio/*` mime and base64 payload). `feature:'about'` notes whose target is no longer a paragraph list at the
  end, so nothing stored is invisible.
- Tour, one step, `go:'welcome'`: highlight the first paragraph; undone on exit. It never depends on a section.

## Rules
- Never shorten, paraphrase or reorder the text. Blank lines in `text` are paragraph breaks; other whitespace
  collapses. A paragraph over 500 characters with no break is split at sentence ends into paragraphs of about
  420 characters, with a warning; the build checks that the paragraphs rejoin to the brief's words and falls back
  to one paragraph if they do not. Put blank lines in the brief to choose the breaks yourself.
- Over 2,000 characters a block is cut at a word boundary with "…", a warning, and a visible line "The rest of
  this text is in the presentation, slide N."
- At most 12 blocks (warning). Missing `source_slide` → "slide not recorded" and a warning. Duplicate titles
  warn: targets are `<title> ¶n`, so they must be unique; changing the text's breaks renumbers the targets.
- Quiet reading column (max 60ch); `.kicker` titles, text 300 at 17 px (18 px from 900 px), the details as a
  `--float` sheet with `var(--radius,6px)`, 44 px targets; shell tokens only, weights 300/500. Brief strings are
  HTML-escaped into markup; the inline `AB` object holds counts only.
