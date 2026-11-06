---
name: ek-precedents
description: Add an "Inspiration" section to an Engage Kit tool — the precedent buildings the design team looked at (other architects' work, shown as references), as a swipeable gallery on phones and a grid on desktop, where visitors say which feel right for this place and which do not, say why, and rank their top three. Use whenever the brief has precedents, reference projects, "inspiration" or mood images of other buildings, or the user asks what people think of the team's references.
---

# Precedents

Renders `brief.precedents` as a gallery of reference buildings. The visitor's job: see what the design team
looked at, say which feel right for this community and which do not, say why, and rank favourites. The section
says once, plainly, that these are other people's buildings the design team looked at, not the project; each
card credits its author ("by …") and, when given, its photographer or source ("Photo: …").

## Run it
```
python skills/ek-precedents/build.py --brief work/brief.json --out output/index.html [--root .]
```
The shell must already exist with `ek-precedents` installed (slot `precedents`, title "Inspiration"). The script
replaces `<section data-feature="precedents">`, inserts one `<style data-feature="precedents">` at
`<!-- ek:styles -->` and one `<script data-feature="precedents">` at `<!-- ek:scripts -->`, and is idempotent
(byte-identical on a re-run). It prints a JSON summary (count, images embedded, image bytes, any embedded
image that was embedded on `cleared: true` rather than `people: false`) and warnings on stderr.

Brief field read, `precedents[]`:
- `name` (the reaction target; unique), `by` (architect or author, credited on the card; missing → "Architect
  not recorded" and a warning), `image` (path relative to `--root`), `source_slide`.
- `credit` (optional; photographer or source of the image) → a muted "Photo: <credit>" line on the card. A
  precedent with an image and no `credit` warns at build time ("copyright: credit required") unless the brief
  is the sample (`sample: true`).
- People gate: an image is embedded only when `people` is exactly `false` (someone looked and it shows no
  person) or `cleared` is exactly `true`. `people: true` without `cleared: true` is skipped with a warning; a
  precedent with **no `people` key** is also skipped, with a warning that the team must look at the image and
  set `people: false`, or `cleared: true`. Nothing is embedded unchecked. Same idea as `ek-site-story` and
  `ek-timeline`.
- `precedents_note` (if the brief has one) is not rendered; the section note is fixed copy.

## Markup it writes
```html
<section data-feature="precedents" data-title="Inspiration" hidden>
  <h2>What the team looked at</h2>
  <p class="lede" data-with-voice="…" data-without-voice="…">…</p>
  <p class="pc-note">These are other people's buildings the design team looked at. They are not the project.</p>
  <div class="pc-wrap ek-bleed">
    <ul class="pc-track" id="pcTrack" role="list">
      <li class="pc-card" data-target="<name>" tabindex="0">
        <div class="pc-frame"><img class="pc-img" src="data:…" alt="<name>, by <by>"><span class="pc-rank" hidden></span></div>
        <div class="pc-body"><span class="kicker">Reference · slide N</span><span class="pc-name">…</span>
          <span class="pc-by">by …</span><span class="pc-credit">Photo: …</span>   <!-- only when credit is set -->
          <div class="row pc-votes" role="group"><button class="pc-vote" data-v="right" aria-pressed="false">Feels right for us</button><button class="pc-vote" data-v="not" aria-pressed="false">Not for us</button></div>
          <div class="row"><button class="primary pc-say">Say why</button><span class="chip pc-count" hidden>…</span></div>
          <div class="pc-mem" role="list"></div></div>
      </li> …
    </ul>
    <nav class="pc-dots" aria-label="References">…</nav>
  </div>
  <div class="row pc-rankrow"><button class="primary pc-rankbtn">Rank my favourites</button>…</div>
  <div class="pc-rankbox" hidden>…</div>
</section>
```

## Reactions (both are `kind:'vote'`; renderers check the value type)
- Choice: `{feature:'precedents', target:<name>, kind:'vote', value:'right'|'not'}` — a **string**. One per
  precedent per device; tapping the chosen one again removes it. The new choice is stored before the old one
  is removed, so a full store keeps the earlier choice and says so.
- Ranking: `{feature:'precedents', target:<name>, kind:'vote', value:{rank:1|2|3}}` — an **object**. Saving
  writes the new ranking first and removes the old ranking records only when every new one is stored; a
  failed write rolls back the partial new ranking. Choices and rankings never touch each other.
- Notes and voice clips use the bar (`kind:'note'|'voice'`, target = the precedent name). Notes typed while
  the ranking panel is open target `ranking: inspiration` and are listed under the gallery.
- Synthesis must split `vote` records by `typeof value`: string → choice, object with integer `rank` → ranking.

## Behaviour
- Phones (< 900 px): a horizontal scroll-snap track inside the section (the page never scrolls sideways), one
  card per screen (two-ish from 600 px), a dot rail under it. `IntersectionObserver` marks the active card,
  updates the dots and sets `EK.context('precedents', <name>, '— slide N · swipe for the next')`.
- From 900 px: a grid (`auto-fill, minmax(280px, 1fr)`), no dots, no bleed.
- Images: 4:3 frame, `object-fit: cover`; the image is the content, so `alt="<name>, by <by>"` (just the name
  when `by` is missing).
- Keyboard: each card is focusable; ArrowRight/Down and ArrowLeft/Up move between cards, Home/End jump,
  Enter on a card is Say why. Dots and every card control are in the Tab order.
- **Say why** → `EK.context('precedents', <name>, '— what about it feels right, or not?')` + `EK.focusNote()`.
  This device's notes for the card are listed under it (escaped, `audio/*` only) with a count; the dots'
  labels carry the choice, rank and count for screen readers.
- Tour: three steps (swipe; choose — a demo "feels right" on the first card, recorded directly with
  `EK.react({…, tour:true})` (no click on the real button), skipped if the visitor already chose there, removed
  by the step's undo and in any case by the shell when the tour exits; rank — opens the panel, closed on exit).
  Each step's `do` checks it is still on this section, so a late timer after Finish does nothing.
- The visitor's own choices and rankings pass `tour:false`, so a tap made while the tour is playing is kept.

## Rules
- Honesty, said once: the section note ("other people's buildings the design team looked at … not the
  project") plus the "by <author>" line on each card; no per-card honesty line. Never put the project's own
  options here (they belong in massing/options features); an SVG drawing image triggers a warning to check the
  note still reads true.
- Credit the author (`by`) and the image (`credit`). Twelve precedents at most; more are cut with a warning.
- Look: cards and boxes use `var(--radius,6px)`; pills (vote buttons, rank badges, dots) `999px`; labels use the
  shell's `.kicker`; font weights 300 / 500 only.
- Images resolve under `--root` and are refused if they escape it (absolute, `..`, UNC); unsafe SVGs refused;
  rasters re-encoded through Pillow (downscaled to 1200 px, EXIF dropped). Embedded images over 2 MB in
  total give a warning. These are other people's photographs: HANDOFF should say whose and on what basis
  they are shown.
- Copy says "say" only when voice is registered (`data-with-voice`). Shell tokens only; no `innerHTML` with
  visitor or brief strings.
