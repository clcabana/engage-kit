---
name: ek-process-timeline
description: Add a "Where we are" section to an Engage Kit tool, plus a one-line strip on Start — the project's approval and design gates in order, the gate we are at and the next one marked, each gate in the deck's own words with its slide, the deck's dated milestones, and an optional parts-by-steps matrix; the visitor asks about any gate, and the next gate points back to the first question on Start. Use whenever the brief has schedule.gates, or the user asks to show the process, the next steps, the approvals path, "where are we", or when the community can still have a say.
---

# Process timeline

Renders `brief.schedule` as one section: a project is a sequence of gates, and the community should see
which gate is next and ask about any of them. This is a process view, not a history of the site (that is
`ek-timeline`): nothing here is a past event with a picture.

## Run it
```
python skills/ek-process-timeline/build.py --brief work/brief.json --out output/index.html
```
The shell must already exist with `ek-process-timeline` installed (slot `process`, title "Where we are"). The
script replaces `<section data-feature="process">`, inserts one `<style data-feature="process">` at
`<!-- ek:styles -->` and one `<script data-feature="process">` at `<!-- ek:scripts -->`, and is idempotent.
It exits with an error when the brief has no usable gate.

Brief fields read (`schedule`):
- `gates[]`: `name`, `status` (`here` | `next` | `later`; anything else is shown as later, with a warning),
  `text` (verbatim), `source_slide`, optional `note`. The note is printed under the card as a muted line
  starting "Note:". It is where the deck contradicts itself; the skill shows it and never resolves it.
- `entries[]`: `when`, `event`, `source_slide`. The only dates on the page; an entry without `when` or
  `event` is skipped, never completed.
- `phases` (optional): `elements[]` × `steps[]` drawn as a small table with no dates and the line "no dates
  per element are given". `phases.note` is not shown (it is a reading note for whoever built the brief).
- `schedule.note` is not shown either; the build says so on stderr. Put anything the public must read in a
  gate's `note`.

## What the visitor sees and does
- Phone: a vertical path of gate cards on a line. From 900 px: a horizontal stepper that scrolls inside
  itself (it never widens the page). `here` is marked "We are here" (marker chip, filled marker dot, marker
  edge on the card, `aria-current="step"`), `next` has a ring dot, `later` is muted.
- Each card: `.kicker` status word, the gate name (500), the deck's text, "From the presentation, slide N",
  the optional note, then **Ask about this** (selects the gate and puts the cursor in the bar). This device's
  notes on the gate list under the card. No "I'd like to be involved" vote: no contact is collected, so it
  promised what the tool cannot keep (old `involve` votes are ignored).
- The `next` gate's card, when `brief.decision_points[0]` exists, adds "The question this step needs from you:
  <question>" and **Answer on Start** (`EK.show('welcome')` then `EK.focusNote()`; the shell's Start context is
  that first question).
- Tapping a card selects it and sets `EK.context('process', <gate name>, '— a question or a worry about this
  step?')`. On entering the section the `here` gate (else the first) is selected, so a note always has a
  gate as its target. Notes whose target is no longer a gate are listed under the path, never hidden.
- Below the path: "Dates in the presentation" (`when · event · slide N`) and, when present, the matrix.
- Tour: two steps — the `here` gate, then the `next` gate with its Ask button focused.

## The Start strip
The build also writes, first in the shell's `#welcomeExtra` (so before `ek-about`'s `start-about` block),
`<!-- ek:start-strip --><div data-slot="start-strip" class="pr-strip">…</div><!-- /ek:start-strip -->`,
replaced on every run:
- `.kicker` "Where we are", then "We are at: <here gate> · next: <next gate>[, <when>]", where `<when>` is the
  `when` of the first `schedule.entries` item whose event contains the next gate's name (case-insensitive),
  else nothing.
- When `decision_points[0]` has a question and `who_decides`: "Your answer to the first question goes to
  <who_decides> before “<next gate>”."
- **See the gates** → `EK.show('process')`.
- Gate names only: a gate's `text` (which may say "step 8") is printed verbatim on its own card and never in
  the strip. No step numbers on Start. No `here` and no `next` gate → no strip. No `#welcomeExtra` → warning,
  no strip.

## Rules
- Text verbatim; nothing invented; no dates except `entries[].when`; no date inferred for a gate.
- Brief strings are HTML-escaped into markup; the inline `PR` object holds only the here/next indices.
  Visitor text is rendered with `textContent`.
- Notes are per device and say so.
- Shell tokens only (`.kicker`, `var(--radius,6px)`, `var(--float)`); weights 300/500; 44 px targets.
