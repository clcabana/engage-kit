---
name: ek-voice-reactions
description: Add spoken-reaction recording to an Engage Kit tool — a hold-to-talk control in the shared reaction bar that captures a short audio clip tied to whatever the visitor is looking at, with playback, a typed fallback, and consent copy. Use whenever the audience meets in person, uses phones, is less likely to type, or the user asks for voice notes, audio feedback, spoken comments, or "record reactions".
---

# Voice reactions

Registers the `voice` reaction kind with the shell. Captures ≤ 60 s clips with MediaRecorder, stored as
base64 WebM/Opus in the reaction's `value` with the current feature and target as context.

## Behaviour
- Control in the reaction bar: large hold-to-talk button (≥ 56 px), a timer, and a waveform-free level
  bar (amplitude only, drawn with a few divs; no canvas).
- On release: playback with a delete option and a "Keep" confirm. Nothing is stored until Keep.
- Consent: first use shows one sentence — what is recorded, that it stays on this device until the team
  exports it, and that the typed box is an alternative. Store acknowledgment in localStorage (try/catch).
- No microphone permission, no MediaRecorder, or the page is in a sandbox that blocks it → the button
  becomes "Type a reaction instead" and focuses the note field. Never show a broken control.
- Reactions: `{feature, target, kind:'voice', value:{mime, base64, seconds}}`.

## Rules
- Keep clips short; a 60 s cap stays well under localStorage limits (roughly 50 clips per device).
- Transcription is not done on device; `ek-feedback-synthesis` transcribes at export time with whatever
  model is available, and labels transcripts as machine-generated.
- Never auto-start recording; always user-initiated and visibly running.
