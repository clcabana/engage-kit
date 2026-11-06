#!/usr/bin/env python3
"""
ek-process-timeline — write the "Where we are" section into an ek-shell output.

  python skills/ek-process-timeline/build.py --brief work/brief.json --out output/index.html

Reads brief.schedule: gates[] (name, status here|next|later, text, source_slide, optional note), entries[]
(when, event, source_slide) and optional phases (note, elements[], steps[]). Replaces the shell's
<section data-feature="process"> slot, writes one <div data-slot="start-strip"> first in #welcomeExtra on
Start (replaced if present), and inserts one <style data-feature="process"> at <!-- ek:styles -->
and one <script data-feature="process"> at <!-- ek:scripts -->. Idempotent. The strip names gates only, never a
gate's text, so a step number in the deck's text never reaches Start.

A process view, not a site history (that is ek-timeline): the gates in order, the one we are at and the next
one marked, each gate's text verbatim with its slide, and a gate's note (where the deck contradicts itself)
shown as a note, never resolved. Dates appear only from entries[]; the phases matrix carries no dates.
Brief strings are data: HTML-escaped into markup, JSON-encoded (</ neutralised) into the inline PR object;
the script renders visitor text with textContent only.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path

FEATURE = "process"
MAX_GATES = 10
MAX_ENTRIES = 16
MAX_TEXT = 500
STATUS = {"here": "We are here", "next": "Next", "later": "Later"}


def log(msg: str) -> None:
    print(f"[ek-process-timeline] {msg}", file=sys.stderr)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def slide_of(v, warnings: list[str], where: str):
    if isinstance(v, bool) or v is None or v == "":
        warnings.append(f"{where} has no source_slide; the claim is not traceable")
        return None
    if isinstance(v, (int, float)) and math.isfinite(v):
        return int(v)
    return str(v)[:20]


def slide_txt(s) -> str:
    return ("slide " + str(s)) if s is not None else "slide not recorded"


def cut(text: str, n: int, warnings: list[str], where: str) -> str:
    if len(text) > n:
        warnings.append(f"{where} text cut at {n} characters")
        return text[:n].rstrip() + "…"
    return text


def schedule_from_brief(brief: dict, warnings: list[str]) -> dict:
    sch = brief.get("schedule") if isinstance(brief.get("schedule"), dict) else {}
    gates = []
    for i, g in enumerate(sch.get("gates") or []):
        if not isinstance(g, dict):
            continue
        name = str(g.get("name") or "").strip()[:100]
        if not name:
            warnings.append(f"schedule.gates[{i}] has no name; skipped")
            continue
        status = str(g.get("status") or "").strip().lower()
        if status not in STATUS:
            warnings.append(f"schedule.gates[{i}] ({name}) status {status!r} is not here|next|later; shown as 'later'")
            status = "later"
        text = cut(str(g.get("text") or "").strip(), MAX_TEXT, warnings, f"schedule.gates[{i}] ({name})")
        if not text:
            warnings.append(f"schedule.gates[{i}] ({name}) has no text; only the name is shown")
        note = cut(str(g.get("note") or "").strip(), MAX_TEXT, warnings, f"schedule.gates[{i}] ({name}) note")
        gates.append({"name": name, "status": status, "text": text, "note": note,
                      "slide": slide_of(g.get("source_slide"), warnings, f"schedule.gates[{i}] ({name})")})
    if len(gates) > MAX_GATES:
        warnings.append(f"{len(gates)} gates; only the first {MAX_GATES} are shown")
        gates = gates[:MAX_GATES]
    names = [g["name"].lower() for g in gates]
    if len(set(names)) != len(names):
        warnings.append("duplicate gate names; reactions target by name, so make them unique")
    for st in ("here", "next"):
        n = sum(1 for g in gates if g["status"] == st)
        if n == 0 and gates:
            warnings.append(f"no gate has status '{st}'; nothing is marked {STATUS[st]!r}")
        elif n > 1:
            warnings.append(f"{n} gates have status '{st}'; each is marked, but the tour uses the first")

    entries = []
    for i, e in enumerate(sch.get("entries") or []):
        if not isinstance(e, dict):
            continue
        when = str(e.get("when") or "").strip()[:60]
        event = cut(str(e.get("event") or "").strip(), 300, warnings, f"schedule.entries[{i}]")
        if not when or not event:
            warnings.append(f"schedule.entries[{i}] lacks when or event; skipped (no date is shown that the deck does not give)")
            continue
        entries.append({"when": when, "event": event,
                        "slide": slide_of(e.get("source_slide"), warnings, f"schedule.entries[{i}]")})
    if len(entries) > MAX_ENTRIES:
        warnings.append(f"{len(entries)} dated entries; only the first {MAX_ENTRIES} are listed")
        entries = entries[:MAX_ENTRIES]

    phases = None
    ph = sch.get("phases")
    if isinstance(ph, dict):
        els = [str(x).strip()[:60] for x in (ph.get("elements") or []) if str(x).strip()]
        steps = [str(x).strip()[:60] for x in (ph.get("steps") or []) if str(x).strip()]
        if els and steps:
            phases = {"elements": els[:8], "steps": steps[:8]}
        else:
            warnings.append("schedule.phases has no elements or no steps; the matrix is not drawn")
    if sch.get("note"):
        log("info: schedule.note is a reading note for the builder and is not shown on the page; a gate's own note is")
    return {"gates": gates, "entries": entries, "phases": phases}


def section_html(s: dict, question: str = "") -> str:
    gates, entries, phases = s["gates"], s["entries"], s["phases"]
    n = len(gates)
    lis = []
    for i, g in enumerate(gates):
        st = g["status"]
        e_name = html.escape(g["name"])
        text = f'<p class="pr-text">{html.escape(g["text"])}</p>' if g["text"] else ""
        note = f'<p class="pr-note">Note: {html.escape(g["note"])}</p>' if g["note"] else ""
        cur = ' aria-current="step"' if st == "here" else ""
        ask = (f'<div class="pr-q"><p>The question this step needs from you: {html.escape(question)}</p>'
               f'<button type="button" class="primary pr-answer">Answer on Start</button></div>'
               if st == "next" and question else "")
        lis.append(
            f'    <li class="pr-gate" data-i="{i}" data-status="{st}" data-target="{e_name}"{cur}>\n'
            f'      <span class="pr-dot" aria-hidden="true"></span>\n'
            f'      <div class="pr-card">\n'
            f'        <span class="kicker pr-st">{STATUS[st]}</span>\n'
            f'        <button type="button" class="pr-sel" aria-pressed="false"><span class="sr">{i + 1} of {n},{STATUS[st].lower()}: </span>{e_name}</button>\n'
            f'        {text}\n'
            f'        <small class="pr-src">From the presentation, {html.escape(slide_txt(g["slide"]))}</small>\n'
            f'        {note}\n'
            f'        {ask}\n'
            f'        <div class="row pr-acts"><button type="button" class="pr-ask">Ask about this</button></div>\n'
            f'        <div class="pr-mem" role="list" aria-label="Your notes on {e_name}"></div>\n'
            f'      </div>\n'
            f'    </li>'
        )
    dates = ""
    if entries:
        rows = "".join(
            f'<li><b>{html.escape(e["when"])}</b> <span aria-hidden="true">\u00b7</span> {html.escape(e["event"])} <span aria-hidden="true">\u00b7</span> <small>{html.escape(slide_txt(e["slide"]))}</small></li>'
            for e in entries)
        dates = (f'  <div class="pr-dates">\n'
                 f'    <h3 class="kicker">Dates in the presentation</h3>\n'
                 f'    <ul>{rows}</ul>\n'
                 f'  </div>\n')
    matrix = ""
    if phases:
        head = "".join(f'<th scope="col">{html.escape(x)}</th>' for x in phases["steps"])
        body = "".join(
            f'<tr><th scope="row">{html.escape(el)}</th>' + "".join(
                '<td><span class="pr-cell" aria-hidden="true"></span><span class="sr">goes through this step, no date given</span></td>'
                for _ in phases["steps"]) + "</tr>"
            for el in phases["elements"])
        matrix = (f'  <div class="pr-phases">\n'
                  f'    <h3 class="kicker">Each part, step by step</h3>\n'
                  f'    <div class="pr-tablewrap" tabindex="0" role="region" aria-label="Parts of the plan and their steps">\n'
                  f'    <table><thead><tr><td></td>{head}</tr></thead><tbody>{body}</tbody></table>\n'
                  f'    </div>\n'
                  f'    <small>The presentation shows each of these parts going through these steps; no dates per element are given.</small>\n'
                  f'  </div>\n')
    lede = "The project moves through a series of steps. See where we are and what comes next; tap any step to {v} a question or a worry about it."
    return (
        f'<section data-feature="process" data-title="Where we are" hidden>\n'
        f'  <h2>Where we are</h2>\n'
        f'  <p class="lede" data-with-voice="{html.escape(lede.format(v="say or type"))}" data-without-voice="{html.escape(lede.format(v="type"))}">{html.escape(lede.format(v="type"))}</p>\n'
        f'  <ol class="pr-path" aria-label="The steps, {n} in all">\n' + "\n".join(lis) + "\n  </ol>\n"
        f'  <div class="pr-other" hidden><small>Your other notes on this section</small><div class="pr-mem" role="list" aria-label="Your other notes on this section"></div></div>\n'
        f'  <small class="pr-dev">Your notes stay on this device until the team collects them.</small>\n'
        + dates + matrix +
        f'</section>'
    )


STRIP_OPEN, STRIP_CLOSE = "<!-- ek:start-strip -->", "<!-- /ek:start-strip -->"


def first_decision(brief: dict) -> dict:
    dps = brief.get("decision_points")
    d = dps[0] if isinstance(dps, list) and dps and isinstance(dps[0], dict) else {}
    return {"question": " ".join(str(d.get("question") or "").split())[:200],
            "who": " ".join(str(d.get("who_decides") or "").split())[:120]}


def strip_html(s: dict, dp: dict) -> str:
    """One line on Start: the gate we are at, the next one (with a date only from entries[]), and who gets the
    first answer. Gate names only: a gate's text (which may name a step number) never appears here."""
    gates = s["gates"]
    here = next((g for g in gates if g["status"] == "here"), None)
    nxt = next((g for g in gates if g["status"] == "next"), None)
    if not here and not nxt:
        return ""
    when = ""
    if nxt:
        key = nxt["name"].lower()
        when = next((e["when"] for e in s["entries"] if key in e["event"].lower()), "")
    parts = []
    if here:
        parts.append("We are at: " + here["name"])
    if nxt:
        parts.append("next: " + nxt["name"] + (", " + when if when else ""))
    line = " · ".join(parts)
    line = line[0].upper() + line[1:]
    second = ""
    if dp["question"] and dp["who"]:
        txt = "Your answer to the first question goes to " + dp["who"] + ((", " if "," in dp["who"] else " ") + "before “" + nxt["name"] + "”" if nxt else "") + "."
        second = f'\n  <p class="pr-sline2">{html.escape(txt)}</p>'
    return (
        f'{STRIP_OPEN}\n'
        f'<div data-slot="start-strip" class="pr-strip">\n'
        f'  <div class="pr-stext"><span class="kicker">Where we are</span>\n'
        f'  <p class="pr-sline">{html.escape(line)}</p>{second}</div>\n'
        f'  <button type="button" class="pr-sgo">See the gates</button>\n'
        f'</div>\n'
        f'{STRIP_CLOSE}'
    )


STYLE = """<style data-feature="process">
/* ===== ek-process-timeline: the gates as a path (phone) / a stepper (from 900 px) ===== */
/* contain:inline-size keeps the stepper's (and the matrix's) own width from widening main: they scroll inside themselves */
.pr-path{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;min-width:0;max-width:100%;contain:inline-size}
.pr-gate{position:relative;display:grid;grid-template-columns:28px 1fr;gap:0 12px;padding-bottom:14px}
.pr-gate::before{content:"";position:absolute;left:13px;top:6px;bottom:-6px;width:2px;background:var(--line)}
.pr-gate:last-child::before{display:none}
.pr-dot{position:relative;z-index:1;margin:18px auto 0;width:14px;height:14px;border-radius:50%;border:2px solid var(--mute);background:var(--paper)}
.pr-gate[data-status=here] .pr-dot{width:20px;height:20px;margin-top:15px;background:var(--marker);border-color:var(--marker);box-shadow:0 0 0 4px var(--paper)}
.pr-gate[data-status=next] .pr-dot{width:18px;height:18px;margin-top:16px;border:3px solid var(--ink);background:var(--paper)}
.pr-card{min-width:0;background:var(--card);border:1px solid var(--line);border-radius:var(--radius,6px);padding:12px 14px;display:flex;flex-direction:column;gap:6px;box-shadow:var(--float,none);cursor:pointer;transition:border-color .15s}
.pr-gate[data-status=here] .pr-card{border-left:3px solid var(--marker)}
.pr-gate[data-status=later] .pr-card{background:transparent;box-shadow:none}
.pr-gate[data-status=later] .pr-text,.pr-gate[data-status=later] .pr-sel{color:var(--mute)}
.pr-gate.sel .pr-card{border-color:var(--ink);box-shadow:var(--float,none)}
.pr-gate[data-status=here].sel .pr-card{border-left-color:var(--marker)}
.pr-st{align-self:flex-start}
.pr-gate[data-status=here] .pr-st{background:var(--marker);color:var(--on-marker);padding:3px 8px;border-radius:999px}
.pr-gate[data-status=next] .pr-st{color:var(--ink)}
.pr-sel{all:unset;box-sizing:border-box;cursor:pointer;font-size:20px;font-weight:500;line-height:1.15;letter-spacing:-.01em;color:var(--ink);min-height:44px;display:flex;align-items:center;overflow-wrap:anywhere}
.pr-gate .pr-sel,.pr-gate .pr-sel:hover,.pr-gate .pr-sel[aria-pressed=true]{background:transparent;border:none;padding:0;color:var(--ink)}  /* beat the shell's pressed-button fill */
.pr-sel:focus-visible{outline:3px solid var(--marker);outline-offset:2px;border-radius:4px}
.pr-text{max-width:60ch;font-size:16px}
.pr-src{color:var(--mute);font-size:13px}
.pr-note{color:var(--mute);font-size:14px;border-left:2px solid var(--line);padding-left:8px;max-width:60ch}
.pr-acts{gap:8px;margin-top:2px} .pr-acts button,.pr-q button{font-size:14px;padding:8px 12px;min-height:44px}
.pr-other[hidden]{display:none}
.pr-q{display:flex;flex-direction:column;align-items:flex-start;gap:8px;padding:10px 12px;background:var(--soft);border-radius:var(--radius,6px)}
.pr-q p{font-size:15px;font-weight:300;max-width:60ch;overflow-wrap:anywhere}
/* the Start strip (in #welcomeExtra, before the team's intro) */
.pr-strip{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;margin-top:24px;padding:12px 14px;background:var(--card);border:1px solid var(--line);border-radius:var(--radius,6px);box-shadow:var(--float,none);min-width:0}
.pr-stext{flex:1 1 240px;min-width:0;display:flex;flex-direction:column;gap:4px}
.pr-sline{font-size:16px;font-weight:500;color:var(--ink);overflow-wrap:anywhere}
.pr-sline2{font-size:14px;font-weight:300;color:var(--mute);overflow-wrap:anywhere}
.pr-sgo{min-height:44px;font-size:14px;padding:8px 14px}
.pr-mem{display:grid;gap:6px} .pr-mem:empty{display:none}
.pr-mem div{padding:8px 10px;border-left:3px solid var(--marker);background:var(--soft);border-radius:0 6px 6px 0;font-size:15px;overflow-wrap:anywhere}
.pr-mem audio{width:100%;max-width:320px;height:36px;display:block}
.pr-other{display:flex;flex-direction:column;gap:6px} .pr-other small,.pr-dev{color:var(--mute);font-size:13px}
.pr-dates ul{list-style:none;margin:8px 0 0;padding:0;display:grid;gap:0}
.pr-dates li{padding:8px 0;border-top:1px solid var(--line);font-size:15px;overflow-wrap:anywhere} .pr-dates li:last-child{border-bottom:1px solid var(--line)}
.pr-dates small{color:var(--mute);font-size:13px}
.pr-dates h3,.pr-phases h3{font-weight:500}
.pr-phases{display:flex;flex-direction:column;gap:8px} .pr-phases > small{color:var(--mute);font-size:13px}
.pr-tablewrap{overflow-x:auto;max-width:100%;contain:inline-size;border:1px solid var(--line);border-radius:var(--radius,6px);background:var(--card)}
.pr-phases table{border-collapse:collapse;font-size:13px;min-width:100%}
.pr-phases th,.pr-phases td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:center;vertical-align:middle}
.pr-phases thead th{font-weight:500;color:var(--mute);font-size:12px;min-width:84px}
.pr-phases tbody th{text-align:left;font-weight:500;white-space:nowrap}
.pr-phases tbody tr:last-child th,.pr-phases tbody tr:last-child td{border-bottom:none}
.pr-cell{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--mute)}
@media(min-width:900px){
  .pr-path{flex-direction:row;overflow-x:auto;gap:0;padding:4px 2px 12px;scroll-snap-type:x proximity}
  .pr-gate{flex:1 0 220px;max-width:340px;grid-template-columns:1fr;grid-template-rows:36px auto;padding:0 14px 0 0;scroll-snap-align:start}
  .pr-gate::before{left:0;right:0;top:17px;bottom:auto;width:auto;height:2px}
  .pr-gate:first-child::before{left:10px} .pr-gate:last-child::before{display:block;right:auto;width:14px}
  .pr-dot,.pr-gate[data-status] .pr-dot{margin:0;align-self:center;justify-self:start}
  .pr-gate .pr-dot{margin-left:2px}
  .pr-card{height:100%}
}
@media(prefers-reduced-motion:reduce){.pr-path{scroll-behavior:auto}}
</style>"""


SCRIPT = """<script data-feature="process">
(function processTimeline() {
  const PR = %(data)s;  /* gate statuses and indices only (names are in the markup) */
  const sec = document.querySelector('section[data-feature="process"]');
  if (!sec) return;
  const gates = [...sec.querySelectorAll(".pr-gate")];
  if (!gates.length) return;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const hasVoice = () => EK.hasKind && EK.hasKind("voice");
  const mine = () => EK.reactions().filter(r => r.feature === "process");
  const name = i => gates[i].dataset.target;
  const HINT = "\\u2014 a question or a worry about this step?";
  let sel = -1;
  /* the Start strip: one line, a way into this section */
  const sgo = document.querySelector('[data-slot="start-strip"] .pr-sgo');
  if (sgo) sgo.addEventListener("click", () => EK.show("process"));

  function select(i, scroll) { if (i < 0 || !gates[i]) return; sel = i;
    gates.forEach((g, k) => { g.classList.toggle("sel", k === i); g.querySelector(".pr-sel").setAttribute("aria-pressed", String(k === i)); });
    if (EK.current() === "process") EK.context("process", name(i), HINT);
    if (scroll) gates[i].scrollIntoView({ block: "nearest", inline: "center", behavior: reduced ? "auto" : "smooth" }); }

  gates.forEach((g, i) => {
    /* tapping anywhere on a gate's card selects it; its own buttons do their own thing */
    g.querySelector(".pr-card").addEventListener("click", e => { const b = e.target.closest("button"); if (b && !b.classList.contains("pr-sel")) return; select(i); });
    g.querySelector(".pr-ask").addEventListener("click", () => { select(i); EK.focusNote(); EK.toast(hasVoice() ? "Speak or type below" : "Type below"); });
    /* the next gate's question is answered where the shell asks it: on Start */
    const ans = g.querySelector(".pr-answer");
    if (ans) ans.addEventListener("click", () => { EK.show("welcome"); EK.focusNote(); });
  });

  function renderNotes(box, rs) { box.textContent = "";
    rs.forEach(r => { const d = document.createElement("div"); d.setAttribute("role", "listitem");
      if (r.kind === "voice" && r.value && typeof r.value.mime === "string" && /^audio\\/[\\w.+-]+$/.test(r.value.mime) && typeof r.value.base64 === "string" && /^[A-Za-z0-9+\\/=]+$/.test(r.value.base64)) { const a = document.createElement("audio"); a.controls = true; a.src = "data:" + r.value.mime + ";base64," + r.value.base64; d.appendChild(a); const s = document.createElement("small"); s.textContent = (r.value.seconds || "?") + " s, voice"; d.appendChild(s); }
      else if (r.kind === "voice") d.textContent = "Unsupported voice note";
      else d.textContent = typeof r.value === "string" ? r.value : "Unsupported note";
      box.appendChild(d); }); }

  function render() { const R = mine(), names = gates.map((g, i) => name(i));
    gates.forEach((g, i) => { const t = name(i); const notes = R.filter(r => r.target === t && r.kind !== "vote");   /* old "involve" votes are no longer shown or made */
      renderNotes(g.querySelector(".pr-mem"), notes);
      g.querySelector(".pr-sel").setAttribute("aria-label", (i + 1) + " of " + gates.length + ", " + g.querySelector(".pr-st").textContent.toLowerCase() + ": " + t + (notes.length ? ", " + notes.length + " note" + (notes.length === 1 ? "" : "s") + " on this device" : "")); });
    /* notes whose target is no longer a gate (a renamed gate, say) stay visible */
    const other = R.filter(r => r.kind !== "vote" && !names.includes(r.target)); const ob = sec.querySelector(".pr-other"); renderNotes(ob.querySelector(".pr-mem"), other); ob.hidden = !other.length; }
  EK.on("ek:reaction", render); render();

  /* the bar always has a gate as its target here: the one selected, else the one we are at */
  const start = PR.here >= 0 ? PR.here : 0;
  EK.on("ek:show", id => { if (id === "process") select(sel >= 0 ? sel : start); });
  if (EK.current() === "process") select(start);

  const nx = PR.next >= 0 ? PR.next : (start + 1 < gates.length ? start + 1 : -1);
  const steps = [{ go: "process", do: () => select(start, true),
    text: "Where we are: " + gates.length + " steps in all. " + (PR.here >= 0 ? "We are here: " + name(start) + "." : "Tap a step to read it.") + " Each card is the presentation\\u2019s own words." }];
  if (nx >= 0) steps.push({ go: "process", do: () => { select(nx, true); const b = gates[nx].querySelector(".pr-ask"); if (b) b.focus({ preventScroll: true }); },
    text: (PR.next >= 0 ? "Next: " : "After that: ") + name(nx) + ". Tap \\u201cAsk about this\\u201d to ask a question or share a worry. It stays on this phone until the team collects it." });
  EK.registerTour(steps);
})();
</script>"""


def splice(doc: str, section: str, style: str, script: str, strip: str = "") -> str:
    doc = re.sub(r'\n?<style data-feature="process">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="process">.*?</script>', "", doc, flags=re.S)
    sec_re = re.compile(r'<section data-feature="process"[^>]*>.*?</section>', re.S)
    if not sec_re.search(doc):
        raise SystemExit("no <section data-feature=\"process\"> slot in the output; is ek-process-timeline installed in the manifest and the shell built?")
    doc = sec_re.sub(lambda m: section, doc, count=1)
    # the Start strip: first thing in #welcomeExtra, so it sits before the team's intro (start-about)
    doc = re.sub(r'\n?' + re.escape(STRIP_OPEN) + r'.*?' + re.escape(STRIP_CLOSE), "", doc, flags=re.S)
    if strip:
        m = re.search(r'<div id="welcomeExtra"[^>]*>', doc)
        if not m:
            log("warning: no <div id=\"welcomeExtra\"> on Start; the strip is not written (rebuild the shell)")
        else:
            doc = doc[:m.end()] + "\n" + strip + doc[m.end():]
    for marker, block in (("<!-- ek:styles -->", style), ("<!-- ek:scripts -->", script)):
        if marker not in doc:
            raise SystemExit(f"shell marker {marker} missing from the output")
        doc = doc.replace(marker, marker + "\n" + block, 1)
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", type=Path, default=Path("work/brief.json"))
    ap.add_argument("--out", type=Path, default=Path("output/index.html"))
    args = ap.parse_args(argv)
    for p in (args.brief, args.out):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    doc = args.out.read_text(encoding="utf-8")
    warnings: list[str] = []
    s = schedule_from_brief(brief, warnings)
    if not s["gates"]:
        sys.exit("brief.schedule has no usable gates; ek-project-manifest should not have installed ek-process-timeline")
    st = [g["status"] for g in s["gates"]]
    data = {"here": st.index("here") if "here" in st else -1, "next": st.index("next") if "next" in st else -1}
    dp = first_decision(brief)
    strip = strip_html(s, dp)
    new_doc = splice(doc, section_html(s, dp["question"]), STYLE, SCRIPT.replace("%(data)s", json_inline(data), 1), strip)
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "gates": len(s["gates"]),
                      "here": data["here"], "next": data["next"], "notes": sum(1 for g in s["gates"] if g["note"]),
                      "entries": len(s["entries"]), "phases": bool(s["phases"]), "strip": bool(strip),
                      "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
