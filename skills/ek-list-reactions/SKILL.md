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
python skills/ek-list-reactions/build.py --brief work/brief.json --out output/index.html [--groups auto|principles,program,<list id>]
```
The shell must already exist with `ek-list-reactions` installed (slot `list`, title "Priorities"). The script
replaces `<section data-feature="list">`, inserts one `<style data-feature="list">` at `<!-- ek:styles -->`
and one `<script data-feature="list">` at `<!-- ek:scripts -->`, and is idempotent. `--groups auto` takes
whichever of `principles` and `program` the brief has, in that order, then every `lists[]` entry in brief
order; `--groups` also accepts a list id.

Brief fields read:
- `principles[]`: `name`, `text` (the deck's wording), `source_slide`, optional `note`. An empty `text` (or a
  literal "to confirm" / "tbc") renders "[wording to confirm]" with a dashed card and the source line
  "Wording not yet confirmed by the design team; the name is from the presentation, slide N": never a
  paraphrase, never another item's paragraph, never attributed to the slide.
- `program[]`: `name`, `use` (the deck's wording), `source_slide`, `contested`. `area_m2` is ignored here on
  purpose; a program with areas belongs in `ek-program-diagram`. A project may install both, but then the
  same names appear in two sections with two verbs (resize there, rank here); the manifest decides and says
  why, and the sample does it only to exercise every skill.
- `lists[]`: any other list of written items (an arborist's tree inventory, say):
  `{id, title, kicker?, note?, items:[{name, text, source_slide, note?, tags?:[string]}], rank?, filters?, matters_label?,
  tag_label?, plan_sheet?}`.
  `id` becomes a DOM id: it must fully match `[a-z0-9-]{1,40}` (`re.fullmatch`, so no trailing newline), not be
  `principles` / `program`, and be unique; anything else is skipped with a warning. `kicker` renders above the list, `note` (≤ 300 chars) as a small line under it.
  `rank` defaults to true (same ranking as the built-in groups, 12 items at most); `rank:false` removes the
  ranking panel, allows up to 60 items, and gives each item a toggle (`matters_label`, default "This matters
  to me"). `filters:true` with tagged items adds a row of chips ("All" first, then each distinct tag in
  order of first appearance, with counts) that hides the items not carrying the chosen tag; tags (≤ 6 per
  item, ≤ 30 chars) also show as small chips on the row. `tag_label` (≤ 30 chars, e.g. "Recommended") says
  what a tag is: each chip on a row reads "<tag_label>: <tag>" ("Recommended: Remove"), so a consultant's
  recommendation never reads as a decision; the filter chips keep the bare tag and its count. Do not repeat
  the tag in the item text. `plan_sheet` is the `name` of a sheet in `brief.sheets[]` (or "Site plan" when
  `ek-drawing-markup` falls back to `site.plan_image`) on which the items are drawn; a name that is not a
  sheet is dropped with a warning. `brief.lists_note` is provenance for the team and is not rendered.

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
- Lists with `rank:false`: no ranking panel; instead **<matters_label>** on each open item toggles
  `{kind:'vote', value:'matters'}` (tap again removes it), shown as a "Matters to you" badge on the row and
  "You marked N as mattering (this phone)" under the list; synthesis reports it as "matters to me" under
  "your choices". Ranking saves only touch integer votes, so marks are never wiped by a ranking.
- Filters: choosing a chip hides the other items (`li.hidden`), closes the open item if it was hidden, and
  says "Showing n of N: <tag>" (aria-live). Filters do not change the ranking or the reactions.
- Plan link (lists with `plan_sheet`, needs `ek-drawing-markup`; the button is hidden when the tool has no
  markup section): each open item has **Show on plan**, which runs `EK.show('markup')` then
  `EK.feature.markup.show(plan_sheet)` (looked up at click time, so build order does not matter) and toasts
  "Find tag <n> on the plan", n being the first number in the item name ("Tree 006 · …" → "006"). The way
  back: the list fills the markup card's `[data-slot="plan-list"]` with "The numbered tags are listed under
  Priorities → <list title>" and **Go to the list** (`EK.show('list')` then `EK.feature.list.show(id)`), shown
  only while the sheet on screen is some list's `plan_sheet`. Out of scope: the tags' positions on the sheet
  are not digitised, so the plan is shown whole and the visitor finds the number by eye; a pin per item
  would need the tag coordinates traced by the team.
- Extension point: `EK.feature.list = { show(listId) }` selects that list's tab (returns false for an unknown
  id); call `EK.show('list')` first.
- The markup contract synthesis reads is unchanged for every list: `.ls-group[data-g]`,
  `.ls-items[aria-label="<title>, N items"]`, `.ls-item[data-target]`; rankings are grouped per list title.
- Tour: open the first item; open the first ranked list's ranking; on a `rank:false` list, open its first
  item and explain the marks (and chips); show the second list if no step has shown it yet. With
  `lists[]` present the lede and tour drop "in the design team's own words" (the words may be a
  consultant's); with only the built-in groups the markup is byte-identical to before.

## Rules
- Verbatim or marked: the item text is the deck's wording or "[wording to confirm]". The build cuts text
  beyond 600 characters with a warning and never summarises.
- Twelve items per ranked list at most; beyond that the list is cut with a warning, because a longer list
  cannot be ranked honestly by a first-time visitor. An unranked list (`rank:false`) takes up to 60.
- No sizes, no areas, no grow / shrink. If the team wants sizes felt, install `ek-program-diagram` as well.
- Item names are the reaction targets and must be unique across all lists (warning when not).
- Everything from the brief is HTML-escaped at build time; everything from reactions is rendered with
  `textContent`. Shell tokens only: the shell's `.kicker` for small labels, `var(--radius,6px)` on cards,
  tabs, filter and tag chips (only the round count / rank / "matters" badges stay pills), weights 300 / 500.
- Copy says "say" only when `EK.hasKind('voice')` is true at load (the lede uses the shell's
  `data-with-voice` / `data-without-voice` attributes; the toast checks at click time).
