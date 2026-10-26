#!/usr/bin/env python3
"""
ek-program-diagram — write the program section into an ek-shell output.

  python skills/ek-program-diagram/build.py --brief work/brief.json --out output/index.html

Reads brief.program, replaces the shell's <section data-feature="program"> slot, inserts one
<style data-feature="program"> at <!-- ek:styles --> and one <script data-feature="program"> at
<!-- ek:scripts -->. Idempotent. Brief strings are data: HTML-escaped into markup, JSON-encoded (</
neutralised) into the inline PG object, and rendered with textContent in the script.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path

FEATURE = "program"
MAX_BLOCKS = 16


def log(msg: str) -> None:
    print(f"[ek-program-diagram] {msg}", file=sys.stderr)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def spaces_from_brief(brief: dict, warnings: list[str]) -> tuple[list[dict], list[dict]]:
    out = []
    for i, p in enumerate(brief.get("program") or []):
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()
        if not name:
            warnings.append(f"program[{i}] has no name; skipped")
            continue
        area = p.get("area_m2")
        try:
            area = float(area) if area is not None and area != "" else None
        except (TypeError, ValueError):
            warnings.append(f"program[{i}] ({name}) area_m2 {area!r} is not a number; treated as unknown")
            area = None
        if area is not None and (not math.isfinite(area) or area <= 0):
            warnings.append(f"program[{i}] ({name}) area_m2 {area} is not a positive number; treated as unknown")
            area = None
        slide = p.get("source_slide")
        if isinstance(slide, bool) or slide is None or slide == "":
            slide = None
        elif isinstance(slide, (int, float)) and math.isfinite(slide):
            slide = int(slide)
        else:
            slide = str(slide)[:20]
        if slide is None:
            warnings.append(f"program[{i}] ({name}) has no source_slide; the claim is not traceable")
        out.append({"name": name[:60], "area": area, "use": str(p.get("use") or "").strip()[:160],
                    "contested": bool(p.get("contested")), "slide": slide})
    names = [s["name"].lower() for s in out]
    if len(set(names)) != len(names):
        warnings.append("duplicate space names in program; reactions target by name, so make them unique")
    if len(out) > MAX_BLOCKS and "other spaces" in names:
        warnings.append("a space is already named 'Other spaces'; the grouped block will collide with it")
    grouped = []
    if len(out) > MAX_BLOCKS:
        known = sorted([s for s in out if s["area"] is not None], key=lambda s: s["area"])
        while len(out) > MAX_BLOCKS - 1 and known:
            s = known.pop(0)
            out.remove(s)
            grouped.append(s)
        warnings.append(f"{len(grouped)} smallest spaces grouped into 'Other spaces' (cap {MAX_BLOCKS} blocks)")
    return out, grouped


def section_html(spaces: list[dict], grouped: list[dict]) -> str:
    n = len(spaces)  # main() has already appended the "Other spaces" block when grouped is non-empty
    return (
        f'<section data-feature="program" data-title="Program" hidden>\n'
        f'  <h2>The spaces inside</h2>\n'
        f'  <p class="lede">Each block is drawn to the size the design team proposed. Tap one to see what it is for, then make it bigger or smaller to show how much it matters to you; your suggested size is drawn over the block. Rank your top five.</p>\n'
        f'  <div class="pg-wrap ek-bleed">\n'
        f'    <div class="pg ek-stage" id="pg">\n'
        f'      <svg id="pgMap" role="group" aria-label="Program diagram, {n} spaces. Tab to a space and press Enter to select it." xmlns="http://www.w3.org/2000/svg"></svg>\n'
        f'      <div class="pg-card" id="pgCard" aria-live="polite">\n'
        f'        <span class="pg-kicker" id="pgKicker">Tap a space to see what it is for</span>\n'
        f'        <span class="pg-name" id="pgName"></span>\n'
        f'        <p id="pgUse"></p>\n'
        f'        <small id="pgMeta"></small>\n'
        f'        <div class="row pg-ctl" id="pgCtl" hidden><div class="grp" role="group" aria-label="Size"><button type="button" data-d="-1" aria-label="Smaller">−</button><button type="button" data-d="1" aria-label="Bigger">+</button></div><button type="button" id="pgReset" hidden>Reset my change</button></div>\n'
        f'        <div class="row"><button type="button" class="primary" id="pgRankBtn">Rank my top five</button><span class="chip" id="pgRanked" hidden></span></div>\n'
        f'      </div>\n'
        f'      <div class="pg-card pg-rank" id="pgRank" hidden>\n'
        f'        <span class="pg-kicker">What matters most to you?</span>\n'
        f'        <span class="pg-name pg-name-sm">Tap up to five, in order</span>\n'
        f'        <div class="pg-picks" id="pgPicks" role="group" aria-label="Spaces to rank"></div>\n'
        f'        <div class="row"><button type="button" class="primary" id="pgSave" disabled>Save my top five</button><button type="button" id="pgCancel">Back</button></div>\n'
        f'      </div>\n'
        f'    </div>\n'
        f'  </div>\n'
        f'</section>'
    )


STYLE = """<style data-feature="program">
/* ===== ek-program-diagram: full-frame treemap + floating card ===== */
.pg-wrap{position:relative}
/* the map and the card share the stage: card under the map on phones, beside it from 900 px; the map's box
   never changes on a tap, so blocks never move under the finger */
.pg{position:relative;background:var(--soft);overflow:hidden;display:flex;flex-direction:column}
.pg svg{flex:1;min-height:0;width:100%;display:block}
.pg g[role=button]{cursor:pointer;outline:none} .pg rect.blk{fill:var(--plan);stroke:var(--paper);stroke-width:3;transition:fill .15s}
.pg g[aria-pressed=true] rect.blk{fill:var(--marker)} .pg g.tbc rect.blk{fill:var(--mute);stroke-dasharray:8 6}
.pg g:focus-visible rect.blk{stroke:var(--marker);stroke-width:5} .pg g.tbc:focus-visible rect.blk,.pg g[aria-pressed=true]:focus-visible rect.blk{stroke:var(--ink)}
.pg text{fill:var(--paper);font-family:var(--font);pointer-events:none} .pg text.nm{font-weight:600;font-size:15px} .pg text.ar{font-size:13px;opacity:.9}
.pg g[aria-pressed=true] text{fill:var(--on-marker)} .pg g[aria-pressed=true] circle.ct{stroke:var(--on-marker)} .pg g[aria-pressed=true] circle.ct2{fill:var(--on-marker)}
.pg circle.ct{fill:none;stroke:var(--paper);stroke-width:2} .pg circle.ct2{fill:var(--paper)}
/* the visitor's suggested size: an outline scaled from the block's centre, over everything, never moving the map */
.pg rect.sug{fill:var(--marker);fill-opacity:.18;stroke:var(--marker);stroke-width:2;stroke-dasharray:6 4;pointer-events:none}
.pg-card{flex:1 1 auto;min-height:0;overflow:auto;background:var(--card);color:var(--ink);border:1px solid var(--line);border-width:1px 0 0;padding:14px 16px;display:flex;flex-direction:column;gap:8px}
@media(max-width:899px){.pg svg{flex:0 0 auto}}  /* phones: the script sets the map's height in px once per show, so bar growth only shrinks the card */
@media(min-width:900px){.pg{flex-direction:row} .pg svg{flex:1;height:100%} .pg-card{flex:0 0 340px;width:340px;border-width:0 0 0 1px}}
.pg-card[hidden],.pg-ctl[hidden],.pg-card .chip[hidden]{display:none} .pg-card .pg-name:empty,.pg-card p:empty{display:none}
.pg-kicker{font-size:13px;color:var(--mute);letter-spacing:.02em} .pg-name{font-size:28px;font-weight:700;line-height:1.05} .pg-name-sm{font-size:18px}
.pg-card p{max-width:52ch} .pg-card small{color:var(--mute);font-size:14px} .pg-card small:empty{display:none}
.pg-ctl .grp{display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden} .pg-ctl .grp button{border:none;border-radius:0;min-width:48px;font-size:20px}
.pg-picks{display:flex;flex-wrap:wrap;gap:6px;overflow:auto} .pg-picks button{min-height:44px;padding:6px 10px;font-size:14px;display:inline-flex;align-items:center;gap:6px}
.pg-picks button b{display:inline-grid;place-items:center;min-width:22px;height:22px;border-radius:11px;background:var(--marker);color:var(--on-marker);font-size:12px}
.pg-picks button[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)} .pg-picks button[aria-pressed=true] b{background:var(--paper);color:var(--ink)}
@media(prefers-reduced-motion:reduce){.pg rect.blk{transition:none}}
</style>"""


SCRIPT = """<script data-feature="program">
(function program() {
  const PG = %(data)s;  /* brief data: names, areas, use text, contested flags, slides. Rendered with textContent only. */
  const stageEl = document.getElementById("pg"), svg = document.getElementById("pgMap"), card = document.getElementById("pgCard"), rankBox = document.getElementById("pgRank");
  if (!stageEl || !svg || !card || !rankBox) return;
  const NS = "http://www.w3.org/2000/svg";
  const el = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
  const spaces = PG.spaces; let sel = null, picks = [];
  const known = spaces.filter(s => s.area != null).map(s => s.area).sort((a, b) => a - b);
  const smallest = known.length ? known[0] : 60;   // an unknown area is drawn at the smallest known one, never larger
  const maxArea = known.length ? known[known.length - 1] : 100;
  const STEP = Math.max(5, Math.min(20, Math.round(maxArea * 0.1 / 5) * 5));
  const CAP = 5 * STEP;                             // one device can move a space at most this far, each way

  /* this device's adjustments and rank come from stored reactions, so they survive reloads and Reset is honest */
  const mine = () => EK.reactions().filter(r => r.feature === "program");
  const rawDelta = name => mine().filter(r => r.kind === "edit" && r.target === name && r.value && typeof r.value.delta === "number" && isFinite(r.value.delta)).reduce((s, r) => s + r.value.delta, 0);
  const delta = name => Math.max(-CAP, Math.min(CAP, rawDelta(name)));
  const rankOf = name => { const v = mine().filter(r => r.kind === "vote" && r.target === name && Number.isInteger(r.value) && r.value >= 1 && r.value <= 5).pop(); return v ? v.value : 0; };
  const base = s => s.area == null ? smallest : s.area;          // the layout uses proposed sizes only
  const area = s => Math.max(STEP, base(s) + delta(s.name));     // what the visitor suggests

  function squarify(items, x, y, w, h, out) { if (!items.length) return; if (items.length === 1) { out.push({ s: items[0].s, x, y, w, h }); return; } const total = items.reduce((t, i) => t + i.v, 0); let acc = 0, i = 0; const half = total / 2; while (i < items.length - 1 && acc + items[i].v <= half) acc += items[i++].v; if (i === 0) { acc = items[0].v; i = 1; } const f = acc / total; if (w >= h) { squarify(items.slice(0, i), x, y, w * f, h, out); squarify(items.slice(i), x + w * f, y, w * (1 - f), h, out); } else { squarify(items.slice(0, i), x, y, w, h * f, out); squarify(items.slice(i), x, y + h * f, w, h * (1 - f), out); } }

  /* word-wrap a name to at most two lines of ~px/char width */
  function wrap(name, maxChars) { const words = name.split(" "); const lines = []; let cur = ""; words.forEach(w => { if ((cur + " " + w).trim().length <= maxChars) cur = (cur + " " + w).trim(); else { if (cur) lines.push(cur); cur = w; } }); if (cur) lines.push(cur); if (lines.length > 2) { lines.length = 2; lines[1] = lines[1].slice(0, Math.max(1, maxChars - 1)) + "\\u2026"; } return lines; }

  function draw() {
    const W = Math.max(200, svg.clientWidth || stageEl.clientWidth), H = Math.max(160, svg.clientHeight || stageEl.clientHeight);
    svg.setAttribute("viewBox", "0 0 " + W + " " + H);
    // layout from the proposed areas only: the map is the design team's; the visitor's suggestion is drawn over it
    const items = spaces.map(s => ({ s, v: base(s) })).sort((a, b) => b.v - a.v); const out = []; squarify(items, 0, 0, W, H, out);
    svg.textContent = ""; const over = el("g", { class: "pg-over", "aria-hidden": "true" });
    out.forEach(r => {
      const s = r.s, d = delta(s.name), rk = rankOf(s.name);
      const g = el("g", { role: "button", tabindex: "0", "data-n": s.name, "aria-pressed": String(sel === s.name) });
      if (s.area == null) g.classList.add("tbc");
      g.setAttribute("aria-label", s.name + ", " + (s.area == null ? "area to confirm" : Math.round(s.area) + " square metres proposed") + (d ? ", you suggest " + (s.area == null ? (d > 0 ? "+" : "") + d : Math.round(area(s))) + (s.area == null ? " on an area not given" : "") : "") + (s.contested ? ", still being discussed" : "") + (rk ? ", you ranked it " + rk : ""));
      g.appendChild(el("rect", { class: "blk", x: r.x, y: r.y, width: r.w, height: r.h, rx: 2 }));
      const nameFs = r.w < 120 ? 13 : 15, pxPerChar = nameFs * 0.58, maxChars = Math.floor((r.w - 16) / pxPerChar);
      const longest = Math.max(...s.name.split(" ").map(w => w.length));
      const lines = (maxChars >= 4 && longest <= maxChars) ? wrap(s.name, maxChars) : [];   // a word that cannot fit is not drawn clipped
      const need = 10 + lines.length * (nameFs + 3) + 16;
      if (lines.length && r.h >= need + 6 && r.w >= 44) {
        lines.forEach((ln, i) => { const t = el("text", { x: r.x + 8, y: r.y + 8 + nameFs + i * (nameFs + 3), class: "nm", "font-size": nameFs }); t.textContent = ln; g.appendChild(t); });
        if (r.h >= need + 20) { const t2 = el("text", { x: r.x + 8, y: r.y + 8 + lines.length * (nameFs + 3) + 14, class: "ar" }); t2.textContent = (s.area == null ? "[area to confirm]" : Math.round(s.area) + " m\\u00b2") + (d ? " (" + (d > 0 ? "+" : "") + d + ")" : ""); g.appendChild(t2); }
      }
      if (s.contested) { g.appendChild(el("circle", { class: "ct", cx: r.x + r.w - 14, cy: r.y + 14, r: 6 })); g.appendChild(el("circle", { class: "ct2", cx: r.x + r.w - 14, cy: r.y + 14, r: 2 })); const tt = el("title", {}); tt.textContent = "Still being discussed"; g.appendChild(tt); }
      g.addEventListener("click", () => sel === s.name ? deselect() : select(s.name));
      g.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(s.name); } else if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); moveFocus(g, 1); } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); moveFocus(g, -1); } });
      svg.appendChild(g);
      if (d) { const k = Math.sqrt(area(s) / base(s)); const w = r.w * k, h = r.h * k; over.appendChild(el("rect", { class: "sug", x: r.x + (r.w - w) / 2, y: r.y + (r.h - h) / 2, width: w, height: h, rx: 2 })); }
    });
    svg.appendChild(over);
  }
  function moveFocus(g, dir) { const gs = [...svg.querySelectorAll("g[role=button]")]; const i = gs.indexOf(g); const nx = gs[(i + dir + gs.length) % gs.length]; if (nx) nx.focus(); }

  const $ = id => document.getElementById(id);
  function deselect() { sel = null; draw(); $("pgKicker").textContent = "Tap a space to see what it is for"; $("pgName").textContent = ""; $("pgUse").textContent = ""; $("pgMeta").textContent = ""; $("pgCtl").hidden = true; $("pgRanked").hidden = true; EK.context("program", "the program", "\\u2014 tap a space"); }
  function select(name) { sel = name; const s = spaces.find(x => x.name === name); draw(); if (!s) return; const d = delta(name), rk = rankOf(name);
    $("pgKicker").textContent = s.contested ? "Still being discussed" : "Proposed space"; $("pgName").textContent = s.name;
    $("pgUse").textContent = s.use || "What this space is for is not described in the presentation.";
    $("pgMeta").textContent = (s.area == null ? "The presentation gives no area yet." + (d ? " You suggest " + (d > 0 ? "+" : "") + d + " m\\u00b2 on an area not given (this phone)." : "") : "Proposed " + Math.round(s.area) + " m\\u00b2." + (d ? " You suggest " + Math.round(area(s)) + " m\\u00b2 (" + (d > 0 ? "+" : "") + d + ", this phone)." : "")) + (s.slide ? " Slide " + s.slide + "." : "") + " Each tap is " + STEP + " m\\u00b2, up to \\u00b1" + CAP + " from this phone.";
    $("pgCtl").querySelector('[data-d="1"]').setAttribute("aria-label", "Bigger by " + STEP + " square metres"); $("pgCtl").querySelector('[data-d="-1"]').setAttribute("aria-label", "Smaller by " + STEP + " square metres");
    $("pgCtl").hidden = false; $("pgReset").hidden = !d; $("pgRanked").hidden = !rk; $("pgRanked").textContent = rk ? "You ranked this #" + rk + " (this phone)" : "";
    EK.context("program", name, "\\u2014 tap + or \\u2212 to change its size");
    const g = svg.querySelector('g[data-n="' + CSS.escape(name) + '"]'); if (g && document.activeElement && document.activeElement.closest && !document.activeElement.closest(".pg-card")) g.focus({ preventScroll: true }); }

  $("pgCtl").querySelectorAll("[data-d]").forEach(b => b.addEventListener("click", () => { if (!sel) return EK.toast("Tap a space first"); const dlt = (+b.dataset.d) * STEP; if (Math.abs(rawDelta(sel) + dlt) > CAP) return EK.toast("That is as far as the control goes (\\u00b1" + CAP + " m\\u00b2). Write a note for more."); EK.react({ feature: "program", target: sel, kind: "edit", value: { delta: dlt } }); EK.toast((dlt > 0 ? "Bigger" : "Smaller") + " by " + Math.abs(dlt) + " m\\u00b2 \\u2014 saved on this phone"); }));
  $("pgReset").addEventListener("click", () => { if (!sel) return; mine().filter(r => r.kind === "edit" && r.target === sel).forEach(r => EK.remove(r.id)); EK.toast("Back to the proposal"); });

  /* ranking */
  function drawPicks() { const box = $("pgPicks"); box.textContent = ""; spaces.forEach(s => { const b = document.createElement("button"); b.type = "button"; const i = picks.indexOf(s.name); b.setAttribute("aria-pressed", String(i >= 0)); const tag = document.createElement("b"); tag.textContent = i >= 0 ? String(i + 1) : "+"; b.appendChild(tag); b.appendChild(document.createTextNode(s.name)); b.setAttribute("aria-label", s.name + (i >= 0 ? ", ranked " + (i + 1) : ", not ranked")); b.addEventListener("click", () => { const k = picks.indexOf(s.name); if (k >= 0) picks.splice(k, 1); else if (picks.length < 5) picks.push(s.name); else { EK.toast("Five chosen \\u2014 remove one first"); return; } drawPicks(); }); box.appendChild(b); }); $("pgSave").disabled = !picks.length; $("pgSave").textContent = picks.length ? "Save my top " + (picks.length === 5 ? "five" : picks.length) : "Save my top five"; }
  $("pgRankBtn").addEventListener("click", () => { picks = spaces.map(s => ({ n: s.name, r: rankOf(s.name) })).filter(x => x.r).sort((a, b) => a.r - b.r).map(x => x.n).slice(0, 5); drawPicks(); card.hidden = true; rankBox.hidden = false; layoutMap(false); $("pgPicks").querySelector("button").focus(); EK.context("program", "ranking", "\\u2014 tap spaces in order of importance"); });
  $("pgCancel").addEventListener("click", () => { rankBox.hidden = true; card.hidden = false; layoutMap(false); $("pgRankBtn").focus(); if (sel) select(sel); else EK.context("program", "the program", "\\u2014 tap a space"); });
  $("pgSave").addEventListener("click", () => { mine().filter(r => r.kind === "vote").forEach(r => EK.remove(r.id)); picks.forEach((n, i) => EK.react({ feature: "program", target: n, kind: "vote", value: i + 1 })); EK.toast("Ranking saved on this phone"); $("pgCancel").click(); });

  /* phones: the map gets a fixed pixel height when the section shows (or the width changes), so the bar growing
     only shrinks the card, and the blocks never move under the finger; while ranking the map gives up room */
  let mapW = 0;
  function layoutMap(force) { if (window.innerWidth >= 900) { svg.style.height = ""; return; } const ranking = !rankBox.hidden; if (force || window.innerWidth !== mapW || svg.dataset.mode !== (ranking ? "rank" : "map")) { mapW = window.innerWidth; svg.dataset.mode = ranking ? "rank" : "map"; svg.style.height = Math.round(stageEl.clientHeight * (ranking ? 0.36 : 0.56)) + "px"; draw(); } }
  EK.on("ek:reaction", () => { draw(); if (sel) select(sel); });
  EK.on("ek:show", id => { if (id === "program") { layoutMap(true); draw(); if (sel) select(sel); else EK.context("program", "the program", "\\u2014 tap a space"); } });
  EK.fitStage(stageEl, "program", { onResize: () => { layoutMap(false); if (window.innerWidth >= 900) draw(); } });
  if ("ResizeObserver" in window) { let last = ""; new ResizeObserver(() => { const k = svg.clientWidth + "x" + svg.clientHeight; if (k !== last) { last = k; draw(); } }).observe(svg); }
  layoutMap(true); draw(); if (EK.current() === "program") EK.context("program", "the program", "\\u2014 tap a space");

  const firstContested = spaces.find(s => s.contested) || spaces[0];
  EK.registerTour([
    { go: "program", do: () => select(firstContested.name), text: "Program: every space drawn to the size the design team proposed" + (spaces.some(s => s.contested) ? "; a ring marks the ones still being discussed" : "") + ". Tap one to see what it is for." },
    { go: "program", do: () => { select(firstContested.name); $("pgCtl").querySelector('[data-d="1"]').click(); }, undo: () => { const r = mine().filter(r => r.kind === "edit" && r.target === firstContested.name).pop(); if (r) EK.remove(r.id); }, text: "Grow what matters, shrink what doesn\\u2019t. Your change is saved on this phone and shown to the design team as a suggestion." },
    { go: "program", do: () => $("pgRankBtn").click(), undo: () => $("pgCancel").click(), text: "Then rank your top five: tap the spaces in order of importance and save." }
  ]);
})();
</script>"""


def splice(doc: str, section: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="program">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="program">.*?</script>', "", doc, flags=re.S)
    sec_re = re.compile(r'<section data-feature="program"[^>]*>.*?</section>', re.S)
    if not sec_re.search(doc):
        raise SystemExit("no <section data-feature=\"program\"> slot in the output; is ek-program-diagram installed in the manifest and the shell built?")
    doc = sec_re.sub(lambda m: section, doc, count=1)
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
    spaces, grouped = spaces_from_brief(brief, warnings)
    if not spaces:
        sys.exit("brief.program has no usable spaces; ek-project-manifest should not have installed ek-program-diagram")
    if grouped:
        spaces.append({"name": "Other spaces", "area": sum(s["area"] for s in grouped), "contested": any(s["contested"] for s in grouped),
                       "use": ("; ".join(f"{s['name']} ({round(s['area'])} m²)" for s in grouped))[:160], "slide": None})
    data = {"spaces": spaces, "step_note": "areas in m²; adjustments are per device"}
    new_doc = splice(doc, section_html(spaces, grouped), STYLE, SCRIPT.replace("%(data)s", json_inline(data), 1))
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "spaces": len(spaces), "grouped": len(grouped),
                      "unknown_area": sum(1 for s in spaces if s["area"] is None), "contested": sum(1 for s in spaces if s["contested"]),
                      "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
