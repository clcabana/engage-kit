---
name: ek-timeline
description: Add an interactive site and community history timeline to an Engage Kit tool — dated events from the presentation as a scroll-driven story (full-bleed image per moment, floating caption, year rail), with a reaction surface so visitors can add their own memory or correction to any year. Use whenever the project brief has dated events, a site history, "how we got here", or the user asks for a timeline, chronology, or history feature.
---

# Timeline

Renders `brief.history` as a vertical, scroll-snapped story: one full-bleed scene per moment, the deck's
own image behind a floating caption card, a slim year rail to jump. The visitor's job: understand how the
site got here, and add what the architects missed.

## Run it
```
python skills/ek-timeline/build.py --brief work/brief.json --out output/index.html [--root .]
```
The shell must already exist (`ek-shell/build.py`). The script replaces the `<section data-feature="timeline">`
slot, inserts one `<style data-feature="timeline">` at `<!-- ek:styles -->` and one `<script data-feature="timeline">`
at `<!-- ek:scripts -->`, and is idempotent (re-running replaces its own blocks). Images named in
`history[].image` are resolved against `--root`, embedded as `data:` URIs so the file stays self-contained,
and shown through `<img>` (an SVG in an `<img>` cannot run script). Raster images wider than 1400 px are
downscaled to JPEG when Pillow is available; the script warns when embedded images pass 1.5 MB.

## Markup it writes
```html
<section data-feature="timeline" data-title="History" hidden>
  <h2>How the site got here</h2>
  <p class="lede">Scroll through the moments that shaped the site. Were you there? Add a memory to any year.</p>
  <div class="tl" tabindex="0" role="region" aria-label="Site history, N moments" aria-roledescription="scrolling story">
    <article class="tl-scene" data-i="0" data-year="1912">
      <img class="tl-img" src="data:…" alt="">                  <!-- or a quiet panel when the deck has no image -->
      <div class="tl-cap"> <span class="tl-year">1912</span> <p>…</p> <small>From the presentation, slide 4</small>
        <div class="row"><button class="primary">Add a memory of 1912</button><span class="chip">N memories</span></div>
        <div class="tl-mem" role="list"></div>                  <!-- this year's reactions, escaped on render -->
      </div>
    </article>
    …
    <nav class="tl-rail" aria-label="Years"><button aria-current="true">1912</button>…</nav>
  </div>
</section>
```

## Behaviour
- Scroll snaps scene to scene; `IntersectionObserver` marks the active scene, updates the rail and sets
  `EK.context('timeline', year, '— scroll for the next moment')`. Reduced motion: no smooth scrolling, no snap.
- Keyboard: the story region is focusable; ArrowDown/PageDown and ArrowUp/PageUp move one scene; Home/End
  jump; each caption's button is in the Tab order; rail buttons jump to a scene.
- Undated events (`year` empty or `to_confirm: true`) render as "[year to confirm]" with a dashed caption and
  the button "Do you know when? Tell us". Never a guessed year.
- "Add a memory" puts the cursor in the shared reaction bar with `target: year` set; voice is used if
  `ek-voice-reactions` registered it, otherwise a note. The feature never builds its own input.
- Reactions: `{feature:'timeline', target:'1962' | 'undated: <first words of event>', kind:'note'|'voice', value}`.
- This year's reactions list under the caption (notes as text, voice as `<audio>` from a data URI with an
  `audio/*` MIME only); the rail and the caption chip show per-device counts.
- Tour: registers three steps (scroll to the second moment; what a memory is; the undated moment if any).

## Rules
- Chronological, one story. Twelve moments at most; if the brief has more, keep the twelve with text and
  images and list the rest in a final "Also in the record" scene rather than inventing a grouping.
- Images are the deck's own renders, embedded, `object-fit: cover`, decorative (`alt=""`): the caption carries
  the meaning. The slide number is shown on the card (desktop) and in the bar hint (always) so the claim is
  traceable; a missing `source_slide` is a build warning.
- **Image guidance for a real project** (the sample's 4:3 flat SVGs show the problem): full-bleed cover crops a
  4:3 slide by about half on a phone. Supply portrait or square images at 1200 px or more on the short side,
  keep the subject in the centre 3:4, and never bake captions, labels or side-by-side comparisons into the
  image. Photos of identifiable people need the team's clearance before a public URL.
- Image paths in the brief are resolved under `--root` and refused if they escape it (absolute, `..`, UNC).
  SVGs with script, event handlers, entities, `foreignObject` or remote references are refused. Rasters are
  re-encoded through Pillow (downscaled to 1400 px, EXIF dropped); without Pillow they embed as-is with a warning.
- Copy never promises speaking: "speak or type" appears only when `EK.hasKind('voice')` is true at load (the
  lede uses the shell's `data-with-voice` / `data-without-voice` attributes; the toast checks at click time).
- Everything rendered from the brief or from reactions goes through `textContent` or `esc()`; no `innerHTML`
  with raw strings, no visitor text in attributes.
- Uses shell tokens only; no literal colours outside the embedded images.
