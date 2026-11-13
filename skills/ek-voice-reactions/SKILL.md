---
name: ek-voice-reactions
description: Add a spoken dictation box to an Engage Kit tool — a "Speak" button on the shared reaction bar that opens a drawer where the visitor talks, sees their words typed live, gets a short typed draft (tidied by the project assistant when one is configured), edits it or speaks a correction, and adds it as a typed note tied to whatever they are looking at. No audio is ever stored. Use whenever the audience meets in person, uses phones, is less likely to type, or the user asks for voice notes, spoken comments, dictation, or "speak reactions".
---

# Voice reactions (spoken dictation box)

Registers the `voice` kind on the shell's bar via `EK.registerKind` (icon a mic, label and caption **Speak**). What
it stores is text only: a `note` reaction whose value records that it was spoken. It never produces `kind:'voice'`
records and never records or stores audio. It owns no section: it works wherever the visitor is (a year, a space,
an option, a block), using the bar's current context.

## Run it
```
python skills/ek-voice-reactions/build.py --out output/index.html
```
The shell must already exist. The script inserts one `<style data-feature="voice">` at `<!-- ek:styles -->` and one
`<script data-feature="voice">` at `<!-- ek:scripts -->`. Idempotent. It needs nothing from the brief.
Constants at the top of `build.py`: listening cap 60 s, silence stop 8 s, draft cap 1200 characters, consent
re-ask after 10 min idle, assistant timeout 30 s.

## What is stored
Exactly one record per **Add this**:
`EK.react({feature, target, kind: 'note', value: {text, via: 'voice'}, tour: false})`.
`text` is the draft as the visitor confirmed it (edited or not); `via: 'voice'` is the provenance. Nothing else:
the words as heard (interim and final) live in memory for the drawer only, for the live line and the assistant
call, and are dropped on Add this, Cancel, Escape, Type instead, or the drawer closing any other way.
`tour: false` because it is the visitor's own, even during the guided tour.

## External flows (and when each happens)
1. **Speech to text, the browser's own service.** Only while the round button shows *Listening…*, after the
   visitor tapped it. `SpeechRecognition` / `webkitSpeechRecognition`: Chrome and Edge send the sound to their
   maker's server (Chrome to Google), Safari to Apple (unless on-device). The page itself never touches the audio.
2. **Tidying by the assistant (Anthropic).** Only when `EK.chat && EK.chat.configured()` (from `ek-chat`), once
   per spoken turn after listening stops: `EK.chat.ask({system, messages})` receives the words as heard, the
   current draft when it is a correction, and the bar's target and feature. Words only, never audio.
   Without a configured assistant this flow does not exist.

## Behaviour
- **Speak** toggles a drawer in `#barSlot` via `EK.barSlot(true)` (the shell hides the note field and Add while it
  is open). The drawer holds: a round button (**Tap to speak** / **Listening…** / **Speak a correction**,
  `aria-pressed`; tap to start, tap to stop, also stops after 8 s without new words or 60 s in all), a live line
  (interim words muted, `aria-live`), the **typed version** (labelled 3-row `<textarea>`), a status line, and
  **Add this** / **Say it again** / **Cancel**. Listening never starts on its own.
- **Phone height**: once a draft exists the round button shrinks from 88 px to 56 px (its words move to a small
  caption under it) and the title hides, keeping the drawer under ~300 px at 375×812, inside the bar's 55vh cap.
- **Draft source** is always said in the status line: *"Typed from what you said."* (no assistant, or it failed) or
  *"Tidied by the assistant from what you said; edit anything it got wrong."* A spoken turn while a draft exists
  is a correction: sent to the assistant with the draft ("apply this spoken correction", same constraints), or
  appended to the draft when there is no assistant.
- **Assistant failure**: a rejection from `EK.chat.ask` (its `message` is a plain sentence), an empty reply, or the
  30 s timeout → the transcript becomes the draft and the status line shows that sentence plus "Typed from what
  you said." The textarea is read-only (`aria-busy`) while the assistant works.
- **Closing**: Escape, Cancel, the Speak button again, the page going to the background, or `EK.focusNote()` (the
  shell emits `'ek:bar'` false; the skill listens and resets) all discard everything not added. If another kind
  takes the drawer over, this one resets too.
- **Consent card**, before the first use on each page load and after 10 min idle (memory only, so the next visitor
  on a shared phone sees it): "Speaking is turned into words by your browser: Chrome sends the sound to Google,
  Safari to Apple." + (assistant configured only) "The words are then sent to an AI service (Anthropic) to tidy
  them into a typed reaction." + "Only the text you confirm is kept. Please don't speak about other people by
  name." Buttons: **OK, let me speak** / **Type instead**.
- **Fallbacks, never a broken control**: no `SpeechRecognition` (Firefox, some in-app browsers) → "This browser
  cannot turn speech into text. You can type your reaction instead." with **Type instead** (calls
  `EK.focusNote()`: the drawer closes and the cursor lands in the bar's note field) and **Close**; insecure
  context → "Speaking needs this page to be served over HTTPS"; microphone denied or missing → a plain message,
  type instead; nothing heard or a network error → a status line, tap to try again. The visitor can always type
  straight into the draft box.
- **Provenance on render**: every renderer that shows notes accepts a string or `{text}` and adds a small
  "(spoken)" tag when `via === 'voice'` (`ek-feedback-synthesis` `valueText`, and the note lists in the feature
  skills). Old `kind:'voice'` clips made by earlier builds still render through those features' own code.
- **Keyboard**: real buttons and a textarea in DOM order; focus goes to the round button when the drawer opens
  and back to Speak when it closes.
- **Copy elsewhere**: the shell's lede, privacy card and toasts say "speak or type" because `EK.hasKind('voice')`.
- **Tour**: one step highlighting Speak.

## Rules
- Never listen without a tap; always visibly running and stoppable. No `MediaRecorder`, no `getUserMedia`.
- The assistant may only rephrase: same person, same facts, names and numbers unchanged. Its reply is plain text
  placed in a textarea (never HTML); the visitor confirms it.
- Visitor text is escaped on render like any note (`textContent`).
- `HANDOFF.md` of a project that installs this skill lists both external flows above.
- Test on the actual table phones over HTTPS: speech recognition support and its network needs vary by browser.
