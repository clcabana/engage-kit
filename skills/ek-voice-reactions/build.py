#!/usr/bin/env python3
"""
ek-voice-reactions — register the voice reaction kind on an ek-shell output.

  python skills/ek-voice-reactions/build.py --out output/index.html

Inserts <style data-feature="voice"> at <!-- ek:styles --> and <script data-feature="voice"> at
<!-- ek:scripts -->. No section, no brief data. Idempotent. The script registers 'voice' on the shell's
reaction bar: consent card on every page load (shared phones), hold-to-record or tap-to-start /
tap-to-stop, countdown and level bar, review row with Keep / Delete, typed fallback when the microphone
is unavailable, and an honest failure when the clip cannot be stored.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FEATURE = "voice"
MAX_SECONDS = 60
STORAGE_BUDGET = 4_000_000   # characters of stored JSON this device may hold before clips are refused
CONSENT_TTL_MS = 10 * 60 * 1000  # re-ask after this long without recording (next visitor on the same phone)

STYLE = """<style data-feature="voice">
/* ===== ek-voice-reactions: hold-to-talk on the shared bar ===== */
#bar .kinds button[data-kind=voice]{touch-action:none;-webkit-touch-callout:none;outline-offset:2px}
#bar .kinds button[data-kind=voice] svg{width:26px;height:26px;display:block;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
#bar .kinds button[data-kind=voice].rec{background:var(--marker);color:var(--on-marker);outline:4px solid var(--marker);animation:ek-rec 1s infinite}
@keyframes ek-rec{0%,100%{outline-offset:2px}50%{outline-offset:8px}}
#bar .kinds button[data-kind=voice].hint{outline:6px solid var(--marker);outline-offset:4px}
#bar .kinds button[data-kind=voice].typed{font-size:18px;font-weight:600}
.vx-level{position:absolute;bottom:-8px;left:50%;transform:translateX(-50%);width:40px;height:4px;background:var(--line);border-radius:2px;overflow:hidden;display:none} .rec .vx-level{display:block} .vx-level i{display:block;height:100%;width:0;background:var(--marker)}
.vx-timer{position:absolute;top:-10px;right:-6px;font-size:12px;font-weight:600;background:var(--ink);color:var(--paper);border-radius:10px;padding:1px 6px;line-height:1.3} .vx-timer[hidden]{display:none}
.vx-consent,.vx-review{display:flex;gap:10px;align-items:center;flex-wrap:wrap;width:100%}
.vx-consent p{font-size:14px;color:var(--ink);max-width:62ch;flex:1 1 240px;margin:0}
.vx-consent .row,.vx-review .row{display:flex;gap:8px;flex-wrap:wrap}
.vx-review audio{flex:1 1 200px;max-width:360px;height:40px}
@media(prefers-reduced-motion:reduce){#bar .kinds button[data-kind=voice].rec{animation:none;outline-offset:4px}}
</style>"""


SCRIPT = """<script data-feature="voice">
(function voice() {
  const MAX = %(max)d, BUDGET = %(budget)d, TTL = %(ttl)d, TAP_MS = 300;
  const note = document.getElementById("note");
  if (!window.EK || !EK.registerKind || !note) return;
  const supported = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder && window.isSecureContext !== false);
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  /* consent lives in memory only: a shared table phone must show the card to each visitor (page load or after TTL idle) */
  let consentedAt = 0; const consented = () => consentedAt && (Date.now() - consentedAt) < TTL;
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const MIC = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/></svg>';
  const clipsHere = () => EK.reactions().filter(r => r.kind === "voice").length;

  EK.registerKind("voice", { icon: "", label: "Hold to record a spoken reaction, or tap to start and tap again to stop", mount(btn, slot) {
    btn.innerHTML = MIC;  /* constant markup authored here, not data */
    const level = el("span", "vx-level"); const levelBar = el("i"); level.appendChild(levelBar); btn.appendChild(level);
    const timer = el("span", "vx-timer"); timer.hidden = true; btn.appendChild(timer);
    const IDLE = "Hold to record a spoken reaction, or tap to start and tap again to stop";

    /* typed fallback: the control never looks broken */
    function toTyped(reason) { btn.textContent = "Aa"; btn.classList.add("typed"); btn.setAttribute("aria-label", "Type a reaction instead"); btn.onclick = () => { note.focus(); }; btn.onpointerdown = null; btn.onkeydown = null; detach(); if (reason) EK.toast(reason); }
    if (!supported) { toTyped(); return; }

    /* consent card in the bar's extra row: announced as a dialog, shown to every visitor */
    function askConsent() { slot.textContent = ""; const box = el("div", "vx-consent"); box.setAttribute("role", "dialog"); box.setAttribute("aria-labelledby", "vxConsentTitle"); box.setAttribute("aria-describedby", "vxConsentText");
      const n = clipsHere();
      const p = el("p", null, ""); p.id = "vxConsentText";
      const t = el("b", null, "Before you record"); t.id = "vxConsentTitle"; p.appendChild(t); p.appendChild(document.createTextNode(" \\u2014 up to " + MAX + " seconds. The clip stays on this phone until the design team collects it, with the rest of your reactions; the design team and the client listen to it for the project record. Anyone using this phone today can play it back" + (n ? " (" + n + " clip" + (n === 1 ? "" : "s") + " already here)" : "") + "; you can remove everything from the Start page. Don\\u2019t record other people. You can always type instead."));
      box.appendChild(p);
      const row = el("div", "row"); const ok = el("button", "primary", "OK, record"); ok.type = "button"; const no = el("button", null, "Type instead"); no.type = "button";
      ok.onclick = () => { consentedAt = Date.now(); close(); btn.focus(); EK.toast("Now hold the mic, or tap it, to record"); }; no.onclick = () => { close(); note.focus(); };
      row.appendChild(ok); row.appendChild(no); box.appendChild(row); slot.appendChild(box); EK.barSlot(true); ok.focus(); }
    function close() { slot.textContent = ""; EK.barSlot(false); }

    /* recording */
    let rec = null, chunks = [], t0 = 0, stream = null, actx = null, raf = 0, stopT = 0, tickT = 0, busy = false, pressT = 0, tapMode = false, recording = false;
    function cleanup() { if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; } if (actx) { try { actx.close(); } catch (e) {} actx = null; } cancelAnimationFrame(raf); clearTimeout(stopT); clearInterval(tickT); levelBar.style.width = "0"; timer.hidden = true; btn.classList.remove("rec"); btn.setAttribute("aria-label", IDLE); busy = false; recording = false; tapMode = false; }
    async function start() {
      if (busy) return; if (!consented()) { askConsent(); return; }
      busy = true; pressT = Date.now();
      try { stream = await navigator.mediaDevices.getUserMedia({ audio: true }); }
      catch (e) { cleanup(); const denied = e && (e.name === "NotAllowedError" || e.name === "SecurityError"); toTyped(denied ? "The microphone is blocked for this page \\u2014 type instead, or allow it in the browser\\u2019s site settings and reload" : "No microphone available \\u2014 type instead"); note.focus(); return; }
      if (!busy) { cleanup(); return; }  /* released before permission came back */
      chunks = []; try { rec = new MediaRecorder(stream); } catch (e) { cleanup(); toTyped("Recording is not supported here \\u2014 type instead"); return; }
      rec.ondataavailable = e => { if (e.data && e.data.size) chunks.push(e.data); };
      rec.onstop = () => { const secs = Math.max(1, Math.round((Date.now() - t0) / 1000)); const b = chunks.length ? new Blob(chunks, { type: rec.mimeType || "audio/webm" }) : null; cleanup(); if (!b || !b.size) { EK.toast("Nothing was recorded"); return; } consentedAt = Date.now(); review(b, secs); };
      try { actx = new (window.AudioContext || window.webkitAudioContext)(); const src = actx.createMediaStreamSource(stream), an = actx.createAnalyser(); an.fftSize = 256; src.connect(an); const buf = new Uint8Array(an.frequencyBinCount);
        const tick = () => { an.getByteTimeDomainData(buf); let m = 0; for (let i = 0; i < buf.length; i++) m = Math.max(m, Math.abs(buf[i] - 128)); levelBar.style.width = Math.min(100, m * 1.6) + "%%"; raf = requestAnimationFrame(tick); }; if (!reduced) tick(); else levelBar.style.width = "100%%"; } catch (e) {}
      t0 = Date.now(); recording = true; rec.start(); btn.classList.add("rec"); btn.setAttribute("aria-label", "Recording \\u2014 release, or tap, to stop"); timer.hidden = false; timer.textContent = MAX + "s";
      tickT = setInterval(() => { const left = MAX - Math.floor((Date.now() - t0) / 1000); timer.textContent = Math.max(0, left) + "s"; }, 500);
      stopT = setTimeout(stop, MAX * 1000);
    }
    function stop() { if (rec && rec.state === "recording") rec.stop(); else if (busy && !recording) busy = false; }
    /* release: a short press (< TAP_MS) switches to tap mode and keeps recording; the next press stops */
    function release() { if (!busy) return; if (!recording) { busy = false; return; } if (Date.now() - pressT < TAP_MS) { tapMode = true; btn.setAttribute("aria-label", "Recording \\u2014 tap to stop"); return; } stop(); }
    function press() { if (recording && tapMode) { stop(); return; } start(); }

    /* review row: nothing is stored until Keep; a failed store is said plainly */
    function review(b, secs) { slot.textContent = ""; const box = el("div", "vx-review"); const a = document.createElement("audio"); a.controls = true; a.setAttribute("aria-label", "Your recording, " + secs + " seconds"); const url = URL.createObjectURL(b); a.src = url; box.appendChild(a);
      box.appendChild(el("span", "chip", secs + " s"));
      const row = el("div", "row"); const keep = el("button", "primary", "Keep"); keep.type = "button"; const del = el("button", null, "Delete"); del.type = "button";
      const done = () => { URL.revokeObjectURL(url); close(); };
      del.onclick = () => { done(); EK.toast("Deleted \\u2014 nothing was kept"); };
      keep.onclick = () => { keep.disabled = true; const fr = new FileReader(); fr.onload = () => { const base64 = String(fr.result).split(",")[1] || ""; const mime = (b.type || "audio/webm").split(";")[0];
          let size = 0; try { size = (localStorage.getItem("ek:" + EK.project.slug) || "").length; } catch (e) {}
          if (size + base64.length > BUDGET) { keep.disabled = false; EK.toast("This phone is nearly full of reactions; ask the team to collect them. You can delete this clip and type instead."); return; }
          const c = EK.ctx(); const r = EK.react({ feature: c.feature, target: c.target, kind: "voice", value: { mime, base64, seconds: secs } });
          if (!r) { keep.disabled = false; EK.toast("Could not keep the clip (this phone\\u2019s storage is full). Delete it and type instead."); return; }
          done(); EK.toast("Voice reaction kept for " + c.target); }; fr.onerror = () => { keep.disabled = false; EK.toast("Could not read the clip \\u2014 try again or type"); }; fr.readAsDataURL(b); };
      row.appendChild(keep); row.appendChild(del); box.appendChild(row); slot.appendChild(box); EK.barSlot(true); keep.focus(); }

    /* pointer and keyboard; attach/detach so the typed fallback leaves nothing live */
    const onDown = e => { e.preventDefault(); try { btn.setPointerCapture(e.pointerId); } catch (x) {} press(); };
    const onUp = () => release();
    const onKeyDown = e => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); press(); } };
    const onKeyUp = e => { if (e.key === " " || e.key === "Enter") release(); };
    const onVis = () => { if (document.hidden) stop(); };
    btn.addEventListener("pointerdown", onDown); btn.addEventListener("pointerup", onUp); btn.addEventListener("pointercancel", onUp); btn.addEventListener("lostpointercapture", onUp);
    btn.addEventListener("keydown", onKeyDown); btn.addEventListener("keyup", onKeyUp); btn.addEventListener("contextmenu", e => e.preventDefault());
    document.addEventListener("visibilitychange", onVis);
    function detach() { btn.removeEventListener("pointerdown", onDown); btn.removeEventListener("pointerup", onUp); btn.removeEventListener("pointercancel", onUp); btn.removeEventListener("lostpointercapture", onUp); btn.removeEventListener("keydown", onKeyDown); btn.removeEventListener("keyup", onKeyUp); document.removeEventListener("visibilitychange", onVis); }
  } });

  const mic = document.querySelector('#bar .kinds button[data-kind="voice"]');
  if (mic) EK.registerTour([{ go: "welcome", do: () => mic.classList.add("hint"), undo: () => mic.classList.remove("hint"), text: "Hold the mic and say why, or type. Your reaction stays on this phone until the design team collects it." }]);
})();
</script>"""


def splice(doc: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="voice">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="voice">.*?</script>', "", doc, flags=re.S)
    for marker, block in (("<!-- ek:styles -->", style), ("<!-- ek:scripts -->", script)):
        if marker not in doc:
            raise SystemExit(f"shell marker {marker} missing from the output")
        doc = doc.replace(marker, marker + "\n" + block, 1)
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("output/index.html"))
    args = ap.parse_args(argv)
    if not args.out.is_file():
        sys.exit(f"not a file: {args.out}")
    doc = args.out.read_text(encoding="utf-8")
    if 'id="barSlot"' not in doc or "registerKind" not in doc:
        sys.exit("this output has no ek-shell reaction bar with registerKind; build the shell first")
    new_doc = splice(doc, STYLE, SCRIPT % {"max": MAX_SECONDS, "budget": STORAGE_BUDGET, "ttl": CONSENT_TTL_MS})
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    print(f'{{"out": "{args.out}", "bytes": {len(new_doc.encode("utf-8"))}, "max_seconds": {MAX_SECONDS}, "storage_budget": {STORAGE_BUDGET}, "consent_ttl_min": {CONSENT_TTL_MS // 60000}}}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
