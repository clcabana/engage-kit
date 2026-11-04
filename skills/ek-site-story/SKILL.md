---
name: ek-site-story
description: Add a "the site as it is" section to an Engage Kit tool — the places on the site from the presentation's own photographs as a scroll-driven story (full-bleed image per place, floating caption), with one question per place, "must this stay as it is?", answered by a tap and a note. Use whenever the brief has site photographs, named places, constraints or opportunities tied to a spot on the site, or the user asks for a site walk, "what people value on the site", or a photo story that is not a dated history.
---

# Site story

Renders `brief.places` as a vertical, scroll-snapped story: one full-bleed scene per place, the deck's own
photograph behind a floating caption, a slim rail of place names to jump. The visitor's job: walk the site
as the design team saw it, say for each place whether it must stay as it is, and say why. It is the
undated sibling of `ek-timeline`: same presentation, no years, no "do you know when?".

## Run it
```
python skills/ek-site-story/build.py --brief work/brief.json --out output/index.html [--root .]
```
The shell must already exist with `ek-site-story` installed (slot `places`, title "The site"). The script
replaces `<section data-feature="places">`, inserts one `<style data-feature="places">` at `<!-- ek:styles -->`
and one `<script data-feature="places">` at `<!-- ek:scripts -->`, and is idempotent.

Brief field read, `places[]`:
- `name` (the reaction target; unique), `text` (the deck's caption, constraint or opportunity text for that
  place, up to 400 characters), `image` (path relative to `--root`), `source_slide`.
- `people: true` marks a photograph that shows a person; it is **not embedded** until the team adds
  `cleared: true` (exactly `true`: "pending", "no" or 1 do not clear it). A public URL is forever; the build
  warns and shows a quiet panel instead, and its JSON summary lists every embedded image that carried
  `people: true` so HANDOFF can name them and who cleared them. The same gate exists in `ek-timeline`.
- Drawings: an SVG image embeds with a warning that it is a drawing, not a photograph; the section's copy says
  "pictures" so a sample built on drawings does not claim photographs. Real projects use photographs.

## Markup it writes
```html
<section data-feature="places" data-title="The site" hidden>
  <h2>The site as it is</h2>
  <p class="lede">A walk through the places on the site, in the design team's own pictures. For each one, say whether it must stay as it is, and type why.</p>
  <div class="pl ek-stage" tabindex="0" role="region" aria-roledescription="scrolling story" aria-label="The site, N places">
    <article class="pl-scene" data-target="The pond">
      <img class="pl-img" src="data:…" alt="">                        <!-- or a quiet panel when there is no image -->
      <div class="pl-cap"> <span class="pl-name">The pond</span> <p>…</p> <small>From the presentation, slide 10</small>
        <div class="pl-q">Must this stay as it is?</div>
        <div class="row" role="group"><button class="pl-vote" data-v="keep" aria-pressed="false">Keep it as it is</button><button class="pl-vote" data-v="change" aria-pressed="false">It could change</button></div>
        <div class="row"><button class="primary pl-say">Say why</button><span class="chip">N notes on this device</span></div>
        <div class="pl-mem" role="list"></div>                        <!-- this place's notes, escaped on render -->
      </div>
    </article> …
    <nav class="pl-rail" aria-label="Places"><button aria-current="true">The pond</button>…</nav>
  </div>
</section>
```

## Behaviour
- Scroll snaps scene to scene; `IntersectionObserver` marks the active place, updates the rail and sets
  `EK.context('places', <name>, '— slide N · scroll for the next place')`. Reduced motion: no smooth
  scrolling, no snap. The stage uses `EK.fitStage`, so it fills the frame between header and bar.
- Keyboard: the story region is focusable; ArrowDown/PageDown and ArrowUp/PageUp move one place; Home/End
  jump; every caption control is in the Tab order; rail buttons jump.
- **Keep it as it is / It could change**: one choice per place per device, recorded as
  `{feature:'places', target:<name>, kind:'vote', value:'keep'|'change'}`; the chosen chip shows
  `aria-pressed="true"` plus a filled dot (never colour alone); tapping it again removes the choice. A new
  choice is stored before the old one is removed, so a failed write keeps the earlier choice and says so.
- Phones: the caption card is capped at 52 % of the stage and scrolls inside itself, so the picture keeps the
  top half; the rail shows dots only (names from 600 px) and never overlaps the card. The tour's demo tap is
  skipped when the visitor has already chosen for that place, so no real choice is ever deleted by the tour.
- **Say why** sets the context and puts the cursor in the shared bar (voice if registered). Notes and clips
  for the place are listed under the caption (escaped, `audio/*` only) with a per-device count; the rail's
  labels carry the choice and the count for screen readers.
- Tour: three steps (walk; one tap; say why), the tap undone on exit.

## Rules
- Undated by design. A place with a date belongs in `ek-timeline`; do not put years here.
- Ten places at most; beyond that the build cuts the list with a warning rather than inventing a grouping.
- Captions are the deck's words (constraint, opportunity, photo caption), never the model's description of
  the photograph. Text over 400 characters is cut with a warning.
- Images are the deck's own photographs, embedded, `object-fit: cover`, decorative (`alt=""`); the caption
  carries the meaning. **Photographs, not drawings:** a labelled axon or plan loses its labels under a phone
  crop; such drawings belong in a drawing feature, not here. Portrait or square at 1200 px or more on the
  short side; subject in the centre 3:4.
- Image paths resolve under `--root` and are refused if they escape it (absolute, `..`, UNC); SVGs with
  script, event handlers, entities, `foreignObject` or remote references are refused; rasters are re-encoded
  through Pillow (downscaled to 1400 px, EXIF dropped).
- A photograph that shows a person needs `cleared: true` from the team before it is embedded.
- Copy says "speak" only when `EK.hasKind('voice')` is true at load (`data-with-voice` / `data-without-voice`;
  the toast checks at click time). Shell tokens only; no `innerHTML` with raw strings.
