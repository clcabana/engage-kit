#!/usr/bin/env python3
"""
ek-voice-reactions: register the 'voice' kind on an ek-shell output as a spoken dictation box.

  python skills/ek-voice-reactions/build.py --out output/index.html

Inserts <style data-feature="voice"> at <!-- ek:styles --> and <script data-feature="voice"> at
<!-- ek:scripts -->. No section, no brief data. Idempotent. The bar button "Speak" opens a drawer in
#barSlot: the visitor speaks, the browser's SpeechRecognition types it live, the project assistant
(EK.chat, when configured) tidies it into a short typed draft, the visitor edits or speaks a correction,
and "Add this" records a note whose value is {text, via:'voice'}. No audio is ever recorded or stored;
the words as heard live in memory only and are dropped on Add, Cancel or close.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FEATURE = "voice"
MAX_SECONDS = 60             # longest single listening turn
SILENCE_SECONDS = 8          # listening stops after this long without new words
MAX_CHARS = 1200             # cap on the draft text
CONSENT_TTL_MS = 10 * 60 * 1000  # re-ask after this long idle (next visitor on the same phone)
ASK_TIMEOUT_MS = 30_000      # give up on the assistant and use the transcript verbatim

STYLE = r"""<style data-feature="voice">
/* ===== ek-voice-reactions: spoken dictation box on the shared bar ===== */
#bar .kinds button[data-kind=voice] svg{width:26px;height:26px;display:block;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
#bar .kinds button[data-kind=voice][aria-expanded=true]{background:var(--marker);color:var(--on-marker)}
#bar .kinds button[data-kind=voice].hint{outline:6px solid var(--marker);outline-offset:4px}
.vx-drawer,.vx-consent{display:grid;gap:8px;width:100%}
.vx-consent p,.vx-msg{font-size:14px;color:var(--ink);max-width:62ch;margin:0}
.vx-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.vx-main{display:flex;gap:12px;align-items:center}
.vx-talk{flex:0 0 auto;width:88px;height:88px;border-radius:44px;display:grid;place-items:center;align-content:center;gap:2px;padding:6px;border:2px solid var(--marker);color:var(--marker);background:var(--card);font-size:12px;font-weight:500;line-height:1.15;text-align:center}
.vx-talk svg{width:28px;height:28px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.vx-talk[aria-pressed=true]{background:var(--marker);color:var(--on-marker);outline:4px solid var(--marker);animation:vx-pulse 1.2s infinite}
.vx-talk:disabled{opacity:.5}
@keyframes vx-pulse{0%,100%{outline-offset:2px}50%{outline-offset:8px}}
.vx-live{flex:1 1 auto;min-height:44px;margin:0;font-size:16px;color:var(--ink);overflow-wrap:anywhere;max-height:6.5em;overflow:auto}
.vx-live i{color:var(--mute);font-style:normal}
.vx-live:empty::before{content:attr(data-empty);color:var(--mute)}
.vx-status{font-size:13px;color:var(--mute);margin:0;min-height:1.2em}
.vx-drawer label.kicker{display:block;margin:0}
.vx-drawer textarea{width:100%;box-sizing:border-box;font:inherit;font-size:16px;font-weight:300;line-height:1.35;padding:6px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);resize:vertical}
.vx-drawer textarea[aria-busy=true]{opacity:.6}
/* with a draft showing, the round button shrinks so the whole drawer fits a phone under the bar's 55vh cap */
.vx-talkw{flex:0 0 auto;display:grid;justify-items:center;gap:2px}
.vx-cap{display:none;font-size:11px;line-height:1.15;color:var(--marker);font-weight:500;text-align:center;max-width:76px}
.vx-drawer.has-draft .vx-talk{width:56px;height:56px;border-radius:28px;padding:4px}
.vx-drawer.has-draft .vx-talk span{display:none}
.vx-drawer.has-draft .vx-cap{display:block}
.vx-drawer.has-draft .vx-talk svg{width:24px;height:24px}
.vx-drawer.has-draft .vx-live{font-size:14px;max-height:56px;min-height:0}
.vx-drawer.has-draft .vx-title{display:none}
@media(prefers-reduced-motion:reduce){.vx-talk[aria-pressed=true]{animation:none;outline-offset:4px}}
</style>"""


SCRIPT = r"""<script data-feature="voice">
(function voice() {
  const MAX = __MAX__, SILENCE = __SILENCE__, MAXC = __MAXC__, TTL = __TTL__, ASK_MS = __ASK__;
  if (!window.EK || !EK.registerKind || !document.getElementById("note")) return;
  const getSR = () => window.SpeechRecognition || window.webkitSpeechRecognition;  /* read on use, so a late polyfill counts */
  const secure = window.isSecureContext !== false;
  const chatOn = () => { try { return !!(EK.chat && typeof EK.chat.ask === "function" && typeof EK.chat.configured === "function" && EK.chat.configured()); } catch (e) { return false; } };
  /* consent lives in memory only: a shared table phone shows the card to each visitor (page load or after TTL idle) */
  let consentedAt = 0; const consented = () => consentedAt && (Date.now() - consentedAt) < TTL;
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const button = (text, cls) => { const b = el("button", cls || null, text); b.type = "button"; return b; };
  const MIC = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M8 21h8"/></svg>';
  const SYS_DRAFT = "Turn this spoken reaction into a short typed reaction in the speaker's own words, first person, no added facts, keep names and numbers exactly; reply with the text only.";
  const SYS_FIX = "Apply this spoken correction to the draft. Keep the speaker's own words, first person, no added facts, keep names and numbers exactly; reply with the corrected text only.";
  const FROM_SPEECH = "Typed from what you said.", FROM_AI = "Tidied by the assistant from what you said; edit anything it got wrong.";
  const clean = s => String(s || "").replace(/^\s*["“‘']+|["”’']+\s*$/g, "").trim().slice(0, MAXC);
  const sentence = e => { const m = e && typeof e.message === "string" ? e.message.trim() : ""; return m ? (/[.!?]$/.test(m) ? m : m + ".") : "The assistant could not be reached."; };

  EK.registerKind("voice", { icon: "", label: "Speak", caption: "Speak", mount(btn, slot) {
    btn.innerHTML = MIC;  /* constant markup authored here, not data */
    btn.setAttribute("aria-expanded", "false"); btn.title = "Speak";
    let open = false, S = null, node = null;  /* S: per-drawer state, torn down on close */

    /* drop everything held in memory for this drawer; the shell may already have hidden the slot */
    function reset() { if (S) S.teardown(); S = null; node = null; open = false; slot.textContent = ""; btn.setAttribute("aria-expanded", "false"); }
    function close(refocus) { reset(); EK.barSlot(false); if (refocus) btn.focus(); }
    /* EK.focusNote() closes the drawer and emits 'ek:bar' false; the listener below resets this one */
    function typeInstead() { EK.focusNote(); }
    EK.on("ek:bar", shown => { if (!open) return;
      if (!shown) reset();                                   /* focusNote() or another owner closed the slot */
      else if (node && !slot.contains(node)) reset(); });    /* another kind took the drawer over */
    function show(n, focus) { if (S) S.teardown(); S = null; slot.textContent = ""; slot.appendChild(n); node = n; open = true; btn.setAttribute("aria-expanded", "true"); EK.barSlot(true);
      n.addEventListener("keydown", e => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(true); } });
      if (focus) focus.focus(); }

    /* a plain message with Type instead / Close: unsupported browser, insecure page, blocked microphone */
    function message(text) { const box = el("div", "vx-consent"); box.setAttribute("role", "group"); box.setAttribute("aria-label", "Speak your reaction");
      box.appendChild(el("p", "vx-msg", text)); const row = el("div", "vx-row"); const t = button("Type instead", "primary"), c = button("Close");
      t.onclick = typeInstead; c.onclick = () => close(true); row.append(t, c); box.appendChild(row); show(box, t); }

    function consent() { const box = el("div", "vx-consent"); box.setAttribute("role", "dialog"); box.setAttribute("aria-labelledby", "vxConsentTitle"); box.setAttribute("aria-describedby", "vxConsentText");
      const p = el("p"); p.id = "vxConsentText"; const t = el("b", null, "Before you speak."); t.id = "vxConsentTitle"; p.appendChild(t);
      p.appendChild(document.createTextNode(" Speaking is turned into words by your browser: Chrome sends the sound to Google, Safari to Apple." +
        (chatOn() ? " The words are then sent to an AI service (Anthropic) to tidy them into a typed reaction." : "") +
        " Only the text you confirm is kept. Please don’t speak about other people by name."));
      box.appendChild(p); const row = el("div", "vx-row"); const ok = button("OK, let me speak", "primary"), no = button("Type instead");
      ok.onclick = () => { consentedAt = Date.now(); dictation(); }; no.onclick = typeInstead; row.append(ok, no); box.appendChild(row); show(box, ok); }

    function openDrawer() { if (!secure) return message("Speaking needs this page to be served over HTTPS. You can type your reaction instead.");
      if (!getSR()) return message("This browser cannot turn speech into text. You can type your reaction instead.");
      if (!consented()) return consent(); dictation(); }

    /* ===== the dictation drawer ===== */
    function dictation() {
      const box = el("div", "vx-drawer"); box.setAttribute("role", "group"); box.setAttribute("aria-labelledby", "vxTitle");
      const title = el("b", "vx-title", "Speak your reaction"); title.id = "vxTitle"; box.appendChild(title);
      const main = el("div", "vx-main"); const talk = button(""); talk.className = "vx-talk"; talk.setAttribute("aria-pressed", "false"); talk.innerHTML = MIC; const talkT = el("span", null, "Tap to speak"); talk.appendChild(talkT);
      const live = el("p", "vx-live"); live.id = "vxLive"; live.setAttribute("aria-live", "polite"); live.dataset.empty = "What you say appears here as you speak."; const cap = el("small", "vx-cap"); cap.setAttribute("aria-hidden", "true"); const tw = el("div", "vx-talkw"); tw.append(talk, cap); main.append(tw, live); box.appendChild(main);
      const lab = el("label", "kicker", "Typed version — edit it if anything is off"); lab.htmlFor = "vxDraft"; const draft = el("textarea"); draft.id = "vxDraft"; draft.rows = 3; draft.maxLength = MAXC;
      draft.placeholder = "Your reaction will appear here. You can also type."; box.append(lab, draft);
      const status = el("p", "vx-status"); status.setAttribute("role", "status"); box.appendChild(status);
      const row = el("div", "vx-row"); const add = button("Add this", "primary"), again = button("Say it again"), cancel = button("Cancel"); row.append(add, again, cancel); box.appendChild(row);

      /* the words as heard (turns, finalT, interimT) exist only here, for the live line and the assistant; never stored */
      let rec = null, state = "idle", gen = 0, turns = [], finalT = "", interimT = "", silenceT = 0, capT = 0, errored = false;
      const setTalk = () => { const on = state === "listening", has = !!draft.value.trim(); box.classList.toggle("has-draft", has);
        talk.setAttribute("aria-pressed", on ? "true" : "false");
        const word = on ? "Listening…" : has ? "Speak a correction" : "Tap to speak"; talkT.textContent = word; cap.textContent = word;
        talk.setAttribute("aria-label", on ? "Listening — tap to stop" : word); talk.title = on ? "Tap to stop" : word; talk.disabled = state === "drafting";
        add.disabled = state !== "idle"; again.disabled = state === "listening"; };
      const showLive = () => { live.textContent = ""; const done = turns.join(" … "); if (done) live.appendChild(document.createTextNode(done + (finalT || interimT ? " … " : ""))); if (finalT) live.appendChild(document.createTextNode(finalT + " ")); if (interimT) live.appendChild(el("i", null, interimT)); };
      const say = t => { status.textContent = t; };
      const armSilence = () => { clearTimeout(silenceT); silenceT = setTimeout(() => stop(), SILENCE * 1000); };
      function stop() { clearTimeout(silenceT); clearTimeout(capT); if (rec) { try { rec.stop(); } catch (e) {} } }

      function listen() { if (state !== "idle") return; const my = gen;
        try { const SR = getSR(); rec = new SR(); } catch (e) { return message("This browser cannot turn speech into text. You can type your reaction instead."); }
        rec.lang = document.documentElement.lang || navigator.language || "en"; rec.continuous = true; rec.interimResults = true; rec.maxAlternatives = 1;
        finalT = ""; interimT = ""; errored = false;
        rec.onresult = e => { if (my !== gen) return; let f = "", i = ""; for (let k = 0; k < e.results.length; k++) { const r = e.results[k], t = (r && r[0] && r[0].transcript) || ""; if (r.isFinal) f += t + " "; else i += t; } finalT = f.trim(); interimT = i.trim(); showLive(); armSilence(); };
        rec.onerror = e => { if (my !== gen) return; const c = e && e.error; errored = true;
          if (c === "not-allowed" || c === "service-not-allowed") { teardown(); return message("The microphone is blocked for this page. Allow it in the browser’s site settings and reload, or type instead."); }
          if (c === "audio-capture") { teardown(); return message("No microphone was found. You can type your reaction instead."); }
          say(c === "no-speech" ? "Nothing was heard. Tap to try again." : c === "network" ? "Speech-to-text needs a connection here. Try again, or type in the box." : c === "aborted" ? "" : "Listening stopped. Tap to try again."); };
        rec.onend = () => { if (my !== gen) return; clearTimeout(silenceT); clearTimeout(capT); rec = null; const heard = (finalT + " " + interimT).trim(); finalT = ""; interimT = ""; state = "idle";
          if (!heard) { if (!errored) say("Nothing was heard. Tap to try again."); showLive(); setTalk(); return; }
          turns.push(heard); showLive(); compose(heard); };
        try { rec.start(); } catch (e) { rec = null; say("Listening could not start. Tap to try again."); return; }
        state = "listening"; say(""); setTalk(); armSilence(); capT = setTimeout(stop, MAX * 1000); }

      async function compose(heard) { const before = draft.value.trim(), fix = !!before, my = gen;
        const verbatim = () => (fix ? before + " " + heard : heard).slice(0, MAXC);
        if (!chatOn()) { draft.value = verbatim(); done(fix ? "Your correction was added to the end. " + FROM_SPEECH : FROM_SPEECH); return; }
        state = "drafting"; draft.readOnly = true; draft.setAttribute("aria-busy", "true"); setTalk(); say("Tidying it into a typed reaction…");
        const c = EK.ctx(), about = "The reaction is about: " + c.target + " (" + c.feature + ").";
        const content = fix ? about + "\n\nDraft:\n" + before + "\n\nSpoken correction:\n" + heard : about + "\n\nSpoken reaction:\n" + heard;
        let out = "", why = "";
        try { out = clean(await Promise.race([EK.chat.ask({ system: fix ? SYS_FIX : SYS_DRAFT, messages: [{ role: "user", content }] }),
          new Promise((_, no) => setTimeout(() => no(new Error("The assistant took too long to answer.")), ASK_MS))])); }
        catch (e) { why = sentence(e); }
        if (my !== gen || !box.isConnected) return;
        draft.readOnly = false; draft.removeAttribute("aria-busy");
        if (out) { draft.value = out; done(FROM_AI); }
        else { draft.value = verbatim(); done((why || "The assistant gave no answer.") + " " + FROM_SPEECH); } }
      function done(msg) { state = "idle"; say(msg); setTalk(); }

      function restart() { gen++; stop(); if (rec) { try { rec.abort(); } catch (e) {} rec = null; } turns = []; finalT = ""; interimT = ""; state = "idle"; draft.readOnly = false; draft.removeAttribute("aria-busy"); draft.value = ""; showLive(); say(""); setTalk(); }
      function teardown() { gen++; clearTimeout(silenceT); clearTimeout(capT); if (rec) { try { rec.abort(); } catch (e) {} rec = null; } turns = []; finalT = ""; interimT = ""; live.textContent = ""; draft.value = ""; }

      talk.onclick = () => { if (state === "listening") stop(); else listen(); };
      again.onclick = () => { restart(); listen(); };
      cancel.onclick = () => close(true);
      draft.addEventListener("input", setTalk);
      add.onclick = () => { const text = draft.value.trim().slice(0, MAXC); if (!text) { say("There is nothing to add yet. Speak, or type in the box."); draft.focus(); return; }
        const c = EK.ctx(); const r = EK.react({ feature: c.feature, target: c.target, kind: "note", value: { text, via: "voice" }, tour: false });  /* the visitor's own, even during the tour */
        if (!r) { say("Could not add it (this phone’s storage is full). Ask the team to collect the reactions."); return; }
        close(true); EK.toast("Added to " + c.target); };

      show(box, talk); S = { teardown }; setTalk(); showLive();  /* listening starts on the visitor's tap, never by itself */
    }

    btn.addEventListener("click", () => { if (open) close(true); else openDrawer(); });
    document.addEventListener("visibilitychange", () => { if (document.hidden && open) close(false); });
  } });

  const mic = document.querySelector('#bar .kinds button[data-kind="voice"]');
  if (mic) EK.registerTour([{ go: "welcome", do: () => mic.classList.add("hint"), undo: () => mic.classList.remove("hint"), text: "Tap Speak and say why, or type. You see the typed version and can fix it before it is added; only that text is kept, on this phone, until the design team collects it." }]);
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


def render_script() -> str:
    s = SCRIPT
    for k, v in (("__MAX__", MAX_SECONDS), ("__SILENCE__", SILENCE_SECONDS), ("__MAXC__", MAX_CHARS),
                 ("__TTL__", CONSENT_TTL_MS), ("__ASK__", ASK_TIMEOUT_MS)):
        s = s.replace(k, str(v))
    return s


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("output/index.html"))
    args = ap.parse_args(argv)
    if not args.out.is_file():
        sys.exit(f"not a file: {args.out}")
    doc = args.out.read_text(encoding="utf-8")
    if 'id="barSlot"' not in doc or "registerKind" not in doc:
        sys.exit("this output has no ek-shell reaction bar with registerKind; build the shell first")
    new_doc = splice(doc, STYLE, render_script())
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    print(f'{{"out": "{args.out}", "bytes": {len(new_doc.encode("utf-8"))}, "max_seconds": {MAX_SECONDS}, '
          f'"silence_seconds": {SILENCE_SECONDS}, "consent_ttl_min": {CONSENT_TTL_MS // 60000}}}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
