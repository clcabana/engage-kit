---
name: ek-voice-reactions
description: Add spoken-reaction recording to an Engage Kit tool — a hold-to-talk control in the shared reaction bar that captures a short audio clip tied to whatever the visitor is looking at, with playback, a typed fallback, and consent copy. Use whenever the audience meets in person, uses phones, is less likely to type, or the user asks for voice notes, audio feedback, spoken comments, or "record reactions".
---

# Voice reactions

Registers the `voice` reaction kind on the shell's bar via `EK.registerKind`. Captures clips of up to 60 s with
`MediaRecorder`, stored as base64 in the reaction's `value` with the current feature and target as context.
It owns no section: it works wherever the visitor is (a year, a space, an option, a block).

## Run it
```
python skills/ek-voice-reactions/build.py --out output/index.html
```
The shell must already exist. The script inserts one `<style data-feature="voice">` at `<!-- ek:styles -->`
and one `<script data-feature="voice">` at `<!-- ek:scripts -->`. Idempotent. It needs nothing from the
brief; the consent copy is fixed and the project name comes from `EK.project` at runtime.

## Behaviour
- **Button**: the shell's round 56 px kind button (🎙, label "Hold to record a spoken reaction"). Hold
  with a finger or mouse, or hold Space/Enter on the keyboard; release to stop. Max 60 s with a visible
  countdown; a level bar under the button shows that it is live.
- **Consent, first use only**: pressing the button opens a card in the bar's extra row instead of
  recording: *"Hold the button to record up to 60 seconds. The clip stays on this phone until the design
  team collects it, with the rest of your reactions. Don't record other people. You can always type instead."*
  Buttons: **OK, hold to record** / **Type instead**. Acknowledgment is stored in `localStorage['ek:consent']`
  (try/catch); nothing is recorded until the visitor presses the button again after consenting.
- **Review before keep**: on release the extra row shows a player, the length and **Keep** / **Delete**.
  Nothing is stored until Keep. Keep records `{feature, target, kind:'voice', value:{mime, base64, seconds}}`
  with the bar's current context, then toasts "Voice reaction kept for <target>".
- **Fallbacks, never a broken control**: no `MediaRecorder` / `getUserMedia` (old browser, insecure
  context, a sandboxed artifact viewer) → the button becomes **Aa** "Type a reaction instead" and focuses
  the note field. Permission denied at first use → same, with a toast. A recording that produced no data →
  "Nothing was recorded" toast, no reaction.
- **Storage guard**: before Keep, if this device's reactions would exceed roughly 4 MB in storage, the clip
  is refused with "This phone is nearly full of reactions; ask the team to collect them" (typing still works).
- **Copy elsewhere**: the shell's lede, privacy card and the features' toasts switch to "speak or type"
  automatically because `EK.hasKind('voice')` is true once this skill has registered.
- **Rendering a clip** is the consumer's job (timeline memories, synthesis feed): `<audio>` from
  `data:<mime>;base64,…` only when `mime` matches `^audio/[\w.+-]+$` and `base64` is base64 text.
- **Tour**: one step, pulsing the mic button: "Hold the mic and say why, or type. Your reaction stays on
  this phone until the design team collects it."

## Rules
- Never auto-start recording; always user-initiated, visibly running, and stoppable by releasing.
- Clips are capped at 60 s (a WebM/Opus minute is roughly 0.5 MB as base64); the storage guard keeps a
  device under the common 5 MB localStorage limit.
- The MIME type is whatever the recorder reports (`audio/webm`, `audio/mp4`, …); it is validated on render,
  never trusted as HTML.
- Transcription is not done on the device. `ek-feedback-synthesis` transcribes at export time and labels
  transcripts as machine-generated drafts.
- No microphone access is requested until the visitor has consented and pressed the button; the browser's
  own permission prompt follows. The consent card is the only place the word "record" is promised.
