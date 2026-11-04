---
name: ek-list-reactions
description: Add a "what matters most" section to an Engage Kit tool — the design team's guiding principles and the parts of the plan as a list in their own words, each item expandable with a reaction surface, and a per-list top-five ranking. Use whenever the brief has principles, objectives, values, or program elements without areas, or the user asks for a priorities exercise, "rank the principles", or wants people to react to a list of statements rather than a drawing.
---

# List reactions

Renders `brief.principles` and/or `brief.program` as one section with one list per group: the team's
words, verbatim, one item per row. The visitor's job: read each item, say what they think of it, and rank
the ones that matter most. Nothing here is sized or drawn; this is the skill for a project whose most
reactable content is text (a draft with principles and named elements but no areas yet).

## Run it
```
python skills/ek-list-reactions/build.py --brief work/brief.json --out output/index.html [--groups auto|principles,program]
```
The shell must already exist with `ek-list-reactions` installed (slot `list`, title "Priorities"). The script
replaces `<section data-feature="list">`, inserts one `<style data-feature="list">` at `<!-- ek:styles -->`
and one `<script data-feature="list">` at `<!-- ek:scripts -->`, and is idempotent. `--groups auto` takes
whichever of `principles` and `program` the brief has, in that order.

Brief fields read:
- `principles[]`: `name`, `text` (the deck's wording), `source_slide`, optional `note`. An empty `text` (or a
  literal "to confirm" / "tbc") renders "[wording to confirm]" with a dashed card and the source line
  "Wording not yet confirmed by the design team; the name is from the presentation, slide N": never a
  paraphrase, never another item's paragraph, never attributed to the slide.
- `program[]`: `name`, `use` (the deck's wording), `source_slide`, `contested`. `area_m2` is ignored here on
  purpose; a program with areas belongs in `ek-program-diagram`. A project may install both, but then the
  same names appear in two sections with two verbs (resize there, rank here); the manifest decides and says
  why, and the sample does it only to exercise every skill.

## Markup it writes
```html
<section data-feature="list" data-title="Priorities" hidden>
  <h2>What matters most</h2>
  <p class="lede">The design team's own words, one item at a time. Tap an item to read it and type what you think; then rank the ones that matter most to you.</p>
  <div class="ls-tabs" role="tablist"> <button role="tab" aria-selected="true">Guiding principles 6</button> <button role="tab">The parts of the plan 4</button> </div>   <!-- only with two groups -->
  <div class="ls-group" role="tabpanel">
    <ol class="ls-items">
      <li class="ls-item" data-target="Long-term Stewardship">
        <button class="ls-head" aria-expanded="false"> Long-term Stewardship <span class="ls-rank" hidden>#2</span> </button>   <!-- no ordinal: the only number on a row is the visitor's rank -->
        <div class="ls-body" hidden> <p>…deck text…</p> <small>From the presentation, slide 7</small>
          <div class="row"><button class="primary ls-react">Say what you think</button><span class="chip">N reactions on this device</span></div>
          <div class="ls-mem" role="list"></div>            <!-- this device's notes and clips for the item -->
        </div>
      </li> …
    </ol>
    <div class="row"><button class="primary ls-rankbtn">Rank my top 5</button></div>
    <div class="ls-rankbox" hidden> …tap items in order; Save my top 5 / Back… </div>
  </div>
</section>
```

## Behaviour
- One list on screen at a time (tabs when there are two; arrow keys move between tabs). Switching lists
  closes any open item and sets `EK.context('list', <list title>, '— tap an item to react to it')`.
- Items are an accordion: tap or Enter opens one and closes the others; Escape closes and returns focus.
  Opening sets `EK.context('list', <item name>, '— <list> · slide N')`, so a note or clip made from the bar
  is tied to that item. **Say what you think** also puts the cursor in the bar (voice if registered).
- Reactions: `{feature:'list', target:<item name>, kind:'note'|'voice'|'vote'}`. A `list` vote's value is
  an integer **rank** 1..N (the same convention as `ek-program-diagram`), not a score and not an option id;
  synthesis reports it as "ranked #n by k devices". Notes and clips are listed under the item (escaped,
  `audio/*` only) with a per-device count; rank shows as a badge on the row. A note made with the list
  itself as context (nothing open, or while ranking) is listed under the list as "your notes on … as a
  whole", so nothing stored is invisible.
- **Rank my top N** (N = 5 or the list length if shorter): a panel of toggles; tap to add in order, tap again
  to remove; Save records `{kind:'vote', value:rank}` per pick, replacing this device's previous votes for
  that list only (the other list's ranking is untouched). The new ranking is stored before the old one is
  removed; if storage fails mid-way the new votes are rolled back and the earlier ranking is kept.
- Tour: open the first item; open the ranking; show the second list if there is one.

## Rules
- Verbatim or marked: the item text is the deck's wording or "[wording to confirm]". The build cuts text
  beyond 600 characters with a warning and never summarises.
- Twelve items per list at most; beyond that the list is cut with a warning, because a longer list cannot
  be ranked honestly by a first-time visitor.
- No sizes, no areas, no grow / shrink. If the team wants sizes felt, install `ek-program-diagram` as well.
- Item names are the reaction targets and must be unique across both lists (warning when not).
- Everything from the brief is HTML-escaped at build time; everything from reactions is rendered with
  `textContent`. Shell tokens only.
- Copy says "say" only when `EK.hasKind('voice')` is true at load (the lede uses the shell's
  `data-with-voice` / `data-without-voice` attributes; the toast checks at click time).
