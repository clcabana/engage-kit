#!/usr/bin/env python3
"""
ek-drawing-markup — write the "Mark up plans" section into an ek-shell output.

  python skills/ek-drawing-markup/build.py --brief work/brief.json --out output/index.html [--root .]

Reads brief.sheets[] (name, image, source_slide, optional text), falling back to brief.site.plan_image as
one sheet, replaces the shell's <section data-feature="markup"> slot, inserts <style data-feature="markup">
at <!-- ek:styles --> and <script data-feature="markup"> at <!-- ek:scripts -->. Idempotent.
Each sheet is the deck's drawing embedded once as a data: URI under an SVG the visitor draws on: pen strokes
and short labels, stored as vectors in sheet-relative coordinates; or the sheet is printed, sketched on
paper, photographed and added back as a layer (re-encoded through a canvas, so the photo's metadata never
reaches storage). Reactions: {feature:'markup', target:<sheet name>, kind:'markup', value:{paths, texts, w, h}}
and {kind:'submission', value:{mime, base64, w, h}}. Brief strings are data: HTML-escaped into markup;
visitor text is rendered with textContent / SVG text nodes, never innerHTML.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import math
import mimetypes
import re
import sys
from io import BytesIO
from pathlib import Path

FEATURE = "markup"
MAX_SHEETS = 8
IMG_MAX_W = 1400
SAFE_IMAGE_TYPES = {"image/svg+xml", "image/png", "image/jpeg", "image/webp", "image/gif"}
SVG_UNSAFE = re.compile(
    r"<script|<foreignObject|<!ENTITY|<\?xml-stylesheet|on[a-z]+\s*=|javascript:|"
    r"(?:xlink:)?href\s*=\s*[\"']?\s*(?:https?:|//|data:text)|url\(\s*[\"']?\s*(?:https?:|//)", re.I)


def log(msg: str) -> None:
    print(f"[ek-drawing-markup] {msg}", file=sys.stderr)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def embed_image(rel: str, root: Path, warnings: list[str]) -> tuple[str, int, int]:
    """data: URI plus pixel size, or ('', 0, 0). Same containment and SVG rules as the other skills."""
    if rel.startswith(("\\\\", "//")) or Path(rel).is_absolute() or rel.startswith("\\") or ":" in rel[:3]:
        warnings.append(f"image path must be relative to --root, not embedded: {rel!r}")
        return "", 0, 0
    root_r = root.resolve()
    try:
        path = (root / rel).resolve()
    except (OSError, ValueError):
        warnings.append(f"image path not usable: {rel!r}")
        return "", 0, 0
    if path != root_r and root_r not in path.parents:
        warnings.append(f"image outside --root, not embedded: {rel!r}")
        return "", 0, 0
    if not path.is_file():
        warnings.append(f"image not found: {rel}")
        return "", 0, 0
    mime = mimetypes.guess_type(path.name)[0] or ""
    if path.suffix.lower() == ".svg":
        mime = "image/svg+xml"
    if mime not in SAFE_IMAGE_TYPES:
        warnings.append(f"image type {mime or 'unknown'} not embedded: {path.name}")
        return "", 0, 0
    data = path.read_bytes()
    w = h = 0
    if mime == "image/svg+xml":
        text = data.decode("utf-8", "replace")
        if SVG_UNSAFE.search(text):
            warnings.append(f"SVG with script/event/entity/remote reference not embedded: {path.name}")
            return "", 0, 0
        m = re.search(r'viewBox\s*=\s*["\']\s*[-\d.]+[ ,]+[-\d.]+[ ,]+([\d.]+)[ ,]+([\d.]+)', text)
        if m:
            w, h = int(float(m.group(1))), int(float(m.group(2)))
        else:
            mw, mh = re.search(r'\swidth\s*=\s*["\']([\d.]+)', text), re.search(r'\sheight\s*=\s*["\']([\d.]+)', text)
            w, h = (int(float(mw.group(1))), int(float(mh.group(1)))) if mw and mh else (1000, 750)
    else:
        try:
            from PIL import Image  # type: ignore
            im = Image.open(BytesIO(data))
            im.load()
            if im.width > IMG_MAX_W:
                im.thumbnail((IMG_MAX_W, IMG_MAX_W * 4))
            buf = BytesIO()
            im.convert("RGB").save(buf, "JPEG", quality=82, optimize=True)
            data, mime = buf.getvalue(), "image/jpeg"
            w, h = im.width, im.height
        except ImportError:
            warnings.append(f"{path.name}: Pillow is not installed; embedded as-is (EXIF not stripped, size unknown)")
            w, h = 1000, 750
        except Exception as e:
            warnings.append(f"image not embedded ({type(e).__name__}): {path.name}")
            return "", 0, 0
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii"), max(1, w), max(1, h)


def sheets_from_brief(brief: dict, root: Path, warnings: list[str]) -> list[dict]:
    raw = brief.get("sheets") or []
    if not raw:
        plan = ((brief.get("site") or {}).get("plan_image") or "").strip()
        if plan:
            raw = [{"name": "Site plan", "image": plan, "source_slide": None}]
            warnings.append("no brief.sheets; using site.plan_image as the one sheet")
    out = []
    for i, s in enumerate(raw[:MAX_SHEETS]):
        if not isinstance(s, dict):
            continue
        name = str(s.get("name") or "").strip()[:60]
        img = str(s.get("image") or "").strip()
        if not name or not img:
            warnings.append(f"sheets[{i}] needs a name and an image; skipped")
            continue
        src, w, h = embed_image(img, root, warnings)
        if not src:
            continue
        slide = s.get("source_slide")
        if isinstance(slide, bool) or slide in (None, ""):
            slide = None
            warnings.append(f"sheets[{i}] ({name}) has no source_slide; the drawing is not traceable")
        elif isinstance(slide, (int, float)) and math.isfinite(slide):
            slide = int(slide)
        else:
            slide = str(slide)[:12]
        out.append({"name": name, "src": src, "w": w, "h": h, "slide": slide, "text": str(s.get("text") or "").strip()[:200]})
    if len(raw) > MAX_SHEETS:
        warnings.append(f"{len(raw)} sheets; only the first {MAX_SHEETS} are built")
    names = [s["name"].lower() for s in out]
    if len(set(names)) != len(names):
        warnings.append("duplicate sheet names; markups target by name, so make them unique")
    return out


def section_html(sheets: list[dict]) -> str:
    chips = "".join(f'<button type="button" class="dm-chip" data-s="{i}" aria-pressed="{"true" if i == 0 else "false"}">{html.escape(s["name"])}</button>' for i, s in enumerate(sheets))
    lede = "Draw straight on the design team's drawings: pick a sheet, mark what you would change or keep, save, then say what the marks mean. Or print a sheet, sketch on paper and add a photo of it. Marks stay on this phone until the team collects them."
    return (
        f'<section data-feature="markup" data-title="Mark up plans" hidden>\n'
        f'  <h2>Mark up the drawings</h2>\n'
        f'  <p class="lede">{html.escape(lede)}</p>\n'
        f'  <div class="dm-wrap ek-bleed">\n'
        f'    <div class="dm ek-stage" id="dm">\n'
        f'      <div class="dm-view" id="dmView">\n'
        f'        <svg id="dmSvg" tabindex="0" role="img" aria-label="Drawing sheet. Drawing needs a finger or stylus; with a keyboard, plus and minus zoom, arrows pan, 0 fits the sheet, and Enter adds a label when Text is chosen. Typing a note in the bar below always works."><g id="dmPan"><image id="dmImg" x="0" y="0" preserveAspectRatio="xMidYMid meet"/><g id="dmInk"></g><g id="dmLive"></g></g></svg>\n'
        f'        <div class="dm-tools" role="toolbar" aria-label="Drawing tools">\n'
        f'          <button type="button" class="dm-tool" data-mode="pen" aria-pressed="true" title="Draw">Pen</button>\n'
        f'          <button type="button" class="dm-tool" data-mode="text" aria-pressed="false" title="Add a short label">Text</button>\n'
        f'          <button type="button" class="dm-tool" data-mode="move" aria-pressed="false" title="Move and zoom with one finger">Move</button>\n'
        f'          <span class="dm-sep"></span>\n'
        f'          <button type="button" id="dmUndo" title="Undo the last mark" aria-label="Undo">&#8630;</button>\n'
        f'          <button type="button" id="dmZoomIn" aria-label="Zoom in">+</button><button type="button" id="dmZoomOut" aria-label="Zoom out">&minus;</button>\n'
        f'        </div>\n'
        f'        <form class="dm-label" id="dmLabel" hidden><input id="dmLabelIn" maxlength="60" placeholder="Label (a few words)" aria-label="Label text" autocomplete="off"><button type="submit" class="primary">Add</button><button type="button" id="dmLabelX">Cancel</button></form>\n'
        f'        <div class="dm-hud" id="dmHud" aria-live="polite"></div>\n'
        f'      </div>\n'
        f'      <div class="dm-card" id="dmCard">\n'
        f'        <div class="dm-chips" id="dmChips" role="group" aria-label="Sheets">{chips}</div>\n'
        f'        <small id="dmMeta" class="dm-meta"></small>\n'
        f'        <div class="dm-slot" data-slot="plan-list"></div>\n'
        f'        <div class="row"><button type="button" class="primary" id="dmSave" disabled>Save my marks</button><button type="button" id="dmClear" hidden>Start again</button></div>\n'
        f'        <div class="row dm-paper"><label class="dm-file"><input type="file" id="dmPhoto" accept="image/*" capture="environment"><span>Add a photo of a sketch</span></label><button type="button" id="dmPrint">Print this sheet</button></div>\n'
        f'        <small class="dm-meta">Rather draw on paper? Print the sheet, sketch, photograph only the paper; the photo stays on this phone until you hand it to the team.</small>\n'
        f'        <div class="dm-mem" id="dmMem" role="list" aria-label="Your markups on this sheet"></div>\n'
        f'      </div>\n'
        f'    </div>\n'
        f'  </div>\n'
        f'  <figure class="dm-print" id="dmPrintFig" hidden><img id="dmPrintImg" alt=""><figcaption id="dmPrintCap"></figcaption></figure>\n'
        f'</section>'
    )


STYLE = """<style data-feature="markup">
/* ===== ek-drawing-markup: a sheet to draw on; the toolbar and (on desktop) the card float over it as sheets ===== */
.dm-wrap{position:relative}
.dm{position:relative;background:var(--soft);overflow:hidden;display:flex;flex-direction:column}
.dm-view{position:relative;flex:1;min-height:0;background:var(--soft);overflow:hidden}
@media(max-width:899px){.dm-view{flex:0 0 auto}}
#dmSvg{display:block;width:100%;height:100%;touch-action:none;outline:none;background:var(--soft)} #dmSvg.move{cursor:grab} #dmSvg.pen,#dmSvg.text{cursor:crosshair}
.dm-view:focus-within{outline:3px solid var(--marker);outline-offset:-3px}
#dmInk path,#dmLive path{fill:none;stroke:var(--marker);stroke-linecap:round;stroke-linejoin:round;opacity:.9} #dmInk path.old{opacity:.55}
#dmInk text,#dmLive text{fill:var(--marker);font-family:var(--font);font-weight:500;paint-order:stroke;stroke:var(--paper);stroke-width:.5em;stroke-linejoin:round}
.dm-tools{position:absolute;left:10px;top:10px;display:flex;gap:2px;align-items:center;padding:4px;background:var(--sheet-a);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);border-radius:var(--radius,6px);box-shadow:var(--float);max-width:calc(100% - 20px);flex-wrap:wrap}
.dm-tools button{min-height:44px;min-width:44px;padding:6px 12px;border-radius:4px;border-color:transparent;background:transparent;font-size:14px} .dm-tools button[aria-pressed=true]{background:var(--ink);color:var(--paper)}
.dm-sep{width:1px;height:24px;background:var(--line);margin:0 4px}
.dm-label{position:absolute;left:10px;right:10px;bottom:10px;display:flex;gap:6px;padding:6px;background:var(--sheet-a);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);border-radius:var(--radius,6px);box-shadow:var(--float);max-width:420px} .dm-label[hidden]{display:none}
.dm-label input{flex:1;min-width:0;font:inherit;padding:8px 10px;border:1px solid var(--line);border-radius:4px;background:var(--paper);color:var(--ink);min-height:44px}
.dm-hud{position:absolute;left:10px;bottom:10px;font-size:12px;color:var(--mute);background:var(--sheet-a);border-radius:var(--radius,6px);padding:4px 10px;box-shadow:var(--float);pointer-events:none;max-width:calc(100% - 20px)} .dm-hud:empty{display:none}
.dm-card{flex:1 1 auto;min-height:0;overflow:auto;scrollbar-width:thin;background:var(--card);color:var(--ink);border:1px solid var(--line);border-width:1px 0 0;padding:10px 16px 14px;display:flex;flex-direction:column;gap:8px}
@media(min-width:900px){.dm-view{height:100%} .dm-card{position:absolute;right:12px;top:12px;bottom:12px;width:320px;border:1px solid var(--line);border-radius:var(--radius,6px);background:var(--sheet-a);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);box-shadow:var(--float);gap:10px}}
.dm-chips{display:flex;flex-wrap:wrap;gap:6px} .dm-chip{min-height:44px;padding:8px 14px;border-radius:999px;font-size:14px;text-align:left;white-space:nowrap} .dm-chip[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
@media(max-width:899px){.dm-chips{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;margin:0 -16px;padding:2px 16px} .dm-chips::-webkit-scrollbar{display:none}}  /* one row on a phone, so Save and the paper route stay in view */
.dm-meta{color:var(--mute);font-size:13px} .dm-meta:empty{display:none} .dm-slot:empty,.dm-slot:not(:has(> :not([hidden]))){display:none}
#dmClear[hidden]{display:none}
.dm-paper{gap:8px}
.dm-file{display:inline-flex;align-items:center;min-height:44px;padding:10px 14px;border:1px solid var(--line);border-radius:6px;background:var(--card);cursor:pointer;font-weight:400;position:relative;overflow:hidden} .dm-file input{position:absolute;inset:0;opacity:0;cursor:pointer;width:100%;height:100%} .dm-file:focus-within{outline:3px solid var(--marker);outline-offset:2px}
.dm-mem{display:grid;gap:6px} .dm-mem:empty{display:none}
.dm-mem .it{display:grid;grid-template-columns:64px 1fr auto;gap:8px;align-items:center;padding:6px 8px;border-left:3px solid var(--marker);background:var(--soft);border-radius:0 6px 6px 0;font-size:14px}
.dm-mem .it img,.dm-mem .it svg{width:64px;height:48px;object-fit:cover;border-radius:4px;background:var(--card);display:block} .dm-mem .it small{display:block;color:var(--mute);font-size:12px}
.dm-mem .it button{min-height:44px;padding:6px 10px;font-size:13px;border-color:transparent;background:transparent;color:var(--mute)}
.dm-print{display:none}
@media print{ body > *{display:none !important} body > .app{display:block !important} .app > *{display:none !important} main{display:block !important;padding:0 !important} main > *{display:none !important} section[data-feature="markup"]{display:block !important} section[data-feature="markup"] > *{display:none !important} .dm-print.on{display:block !important;page-break-inside:avoid} .dm-print.on img{width:100%;max-height:90vh;object-fit:contain} .dm-print.on figcaption{font:12px sans-serif;color:#444;margin-top:6px} }
</style>"""


SCRIPT = """<script data-feature="markup">
(function drawingMarkup() {
  const DM = %(data)s;  /* sheet names, sizes, slides and the sheet images (data: URIs); rendered with textContent / attributes only */
  const stageEl = document.getElementById("dm"), view = document.getElementById("dmView"), svg = document.getElementById("dmSvg"), pan = document.getElementById("dmPan"), img = document.getElementById("dmImg"), ink = document.getElementById("dmInk"), live = document.getElementById("dmLive"), card = document.getElementById("dmCard");
  if (!stageEl || !svg || !card) return;
  const $ = id => document.getElementById(id);
  const NS = "http://www.w3.org/2000/svg";
  const S = DM.sheets; let si = 0, mode = "pen", drawing = null;
  /* unsaved marks are kept per sheet, so looking at another sheet or section never loses them */
  const pend = S.map(() => ({ strokes: [], texts: [] }));
  const cur = () => pend[si];
  const sheet = () => S[si];
  const mine = () => EK.reactions().filter(r => r.feature === "markup");
  const hasVoice = () => EK.hasKind && EK.hasKind("voice");
  const MAX_PATHS = 400, MAX_PTS = 2000, PHOTO_CHARS = 600000, STORE_WARN = 4000000;

  /* ---- view transform: translate + scale over the sheet's own pixel space ---- */
  let T = { x: 0, y: 0, k: 1 };
  function fit() { const w = view.clientWidth, h = view.clientHeight, s = sheet(); if (!w || !h) return; svg.setAttribute("viewBox", "0 0 " + w + " " + h); const k = Math.min(w / s.w, h / s.h) * 0.96; T = { k, x: (w - s.w * k) / 2, y: (h - s.h * k) / 2 }; apply(); }
  function apply() { pan.setAttribute("transform", "translate(" + T.x + " " + T.y + ") scale(" + T.k + ")"); }
  function toSheet(cx, cy) { const r = svg.getBoundingClientRect(); const vx = (cx - r.left) * (svg.viewBox.baseVal.width / r.width), vy = (cy - r.top) * (svg.viewBox.baseVal.height / r.height); return [(vx - T.x) / T.k, (vy - T.y) / T.k]; }
  function zoom(f, cx, cy) { const nk = Math.max(0.2, Math.min(8, T.k * f)); const r = svg.getBoundingClientRect(); const px = cx == null ? r.width / 2 : (cx - r.left), py = cy == null ? r.height / 2 : (cy - r.top); T.x = px - (px - T.x) * (nk / T.k); T.y = py - (py - T.y) * (nk / T.k); T.k = nk; apply(); }

  /* ---- sheet ---- */
  function showSheet(i) { si = i; const s = sheet(); img.setAttribute("href", s.src); img.setAttribute("width", s.w); img.setAttribute("height", s.h); [...$("dmChips").querySelectorAll(".dm-chip")].forEach((c, k) => c.setAttribute("aria-pressed", String(k === i)));
    $("dmMeta").textContent = (s.text ? s.text + " " : "") + (s.slide != null ? "From the presentation, slide " + s.slide + "." : "Slide not recorded."); closeLabel(); fit(); redrawLive(); renderMine();
    if (EK.current() === "markup") EK.context("markup", s.name, "\\u2014 draw on it, then say what your marks mean"); }
  $("dmChips").addEventListener("click", e => { const b = e.target.closest(".dm-chip"); if (b) showSheet(+b.dataset.s); });

  /* ---- tools ---- */
  function hint() { const n = cur().strokes.length + cur().texts.length; $("dmHud").textContent = mode === "pen" ? "Draw with a finger or stylus \\u00b7 two fingers move and zoom" : mode === "text" ? "Tap where the label goes" : "One finger moves \\u00b7 choose Pen to draw" + (n ? " \\u00b7 " + n + " unsaved" : ""); }
  function setMode(m) { mode = m; document.querySelectorAll(".dm-tool").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.mode === m))); svg.className.baseVal = m; closeLabel(); hint(); }
  document.querySelectorAll(".dm-tool").forEach(b => b.addEventListener("click", () => setMode(b.dataset.mode)));
  $("dmZoomIn").addEventListener("click", () => zoom(1.25)); $("dmZoomOut").addEventListener("click", () => zoom(0.8));
  const strokeW = () => Math.max(2, sheet().w / 320);
  function pathEl(pts, cls) { const p = document.createElementNS(NS, "path"); p.setAttribute("d", pts.map((q, i) => (i ? "L" : "M") + (q[0] * sheet().w).toFixed(1) + " " + (q[1] * sheet().h).toFixed(1)).join(" ")); p.setAttribute("stroke-width", strokeW()); if (cls) p.setAttribute("class", cls); return p; }
  function textEl(t) { const e = document.createElementNS(NS, "text"); e.setAttribute("x", (t.x * sheet().w).toFixed(1)); e.setAttribute("y", (t.y * sheet().h).toFixed(1)); e.setAttribute("font-size", Math.max(12, sheet().w / 45)); e.textContent = t.t; return e; }
  function redrawLive() { live.textContent = ""; cur().strokes.forEach(s => live.appendChild(pathEl(s.pts))); cur().texts.forEach(t => live.appendChild(textEl(t))); dirty(); }
  function dirty() { const n = cur().strokes.length + cur().texts.length; $("dmSave").disabled = !n; $("dmClear").hidden = !n; $("dmSave").textContent = n ? "Save my marks (" + n + ")" : "Save my marks"; hint(); }
  $("dmUndo").addEventListener("click", () => { const c = cur(); if (c.texts.length && (!c.strokes.length || c.texts[c.texts.length - 1].at > c.strokes[c.strokes.length - 1].at)) c.texts.pop(); else c.strokes.pop(); redrawLive(); });
  $("dmClear").addEventListener("click", () => { const c = cur(); if (c.strokes.length + c.texts.length === 0 || confirm("Clear the marks you have not saved on this sheet?")) { c.strokes = []; c.texts = []; redrawLive(); } });

  /* ---- labels: an inline field at the bottom of the sheet, never a system prompt ---- */
  let labelAt = null;
  function openLabel(x, y) { labelAt = [x, y]; $("dmLabel").hidden = false; $("dmLabelIn").value = ""; $("dmLabelIn").focus(); }
  function closeLabel() { labelAt = null; $("dmLabel").hidden = true; }
  $("dmLabel").addEventListener("submit", e => { e.preventDefault(); const t = $("dmLabelIn").value.trim().slice(0, 60); if (t && labelAt) { cur().texts.push({ x: labelAt[0], y: labelAt[1], t, at: Date.now() }); redrawLive(); } closeLabel(); svg.focus({ preventScroll: true }); });
  $("dmLabelX").addEventListener("click", () => { closeLabel(); svg.focus({ preventScroll: true }); });

  /* ---- pointer: draw, place a label, or move (one finger in Move; two fingers always pan and zoom) ---- */
  const ptrs = new Map(); let pinch = 0, last = null;
  svg.addEventListener("pointerdown", e => { try { svg.setPointerCapture(e.pointerId); } catch (err) {} ptrs.set(e.pointerId, [e.clientX, e.clientY]); svg.focus({ preventScroll: true });
    if (ptrs.size === 2) { const p = [...ptrs.values()]; pinch = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]); if (drawing) { drawing.el.remove(); drawing = null; } last = null; return; }   /* a second finger means pinch, not a stroke */
    if (mode === "pen") { const q = toSheet(e.clientX, e.clientY); drawing = { pts: [[q[0] / sheet().w, q[1] / sheet().h]], at: Date.now() }; drawing.el = pathEl(drawing.pts); live.appendChild(drawing.el); }
    else if (mode === "text") { const q = toSheet(e.clientX, e.clientY); openLabel(Math.min(1, Math.max(0, q[0] / sheet().w)), Math.min(1, Math.max(0, q[1] / sheet().h))); }
    else last = [e.clientX, e.clientY]; });
  svg.addEventListener("pointermove", e => { if (!ptrs.has(e.pointerId)) return; ptrs.set(e.pointerId, [e.clientX, e.clientY]);
    if (ptrs.size === 2) { const p = [...ptrs.values()]; const d = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]); const mid = [(p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2]; if (pinch) zoom(d / pinch, mid[0], mid[1]); pinch = d; if (last) { T.x += mid[0] - last[0]; T.y += mid[1] - last[1]; apply(); } last = mid; return; }
    if (drawing) { if (drawing.pts.length >= MAX_PTS) return; const q = toSheet(e.clientX, e.clientY); const pt = [q[0] / sheet().w, q[1] / sheet().h]; const prev = drawing.pts[drawing.pts.length - 1]; if (Math.hypot(pt[0] - prev[0], pt[1] - prev[1]) > 0.002) { drawing.pts.push(pt); drawing.el.setAttribute("d", drawing.el.getAttribute("d") + " L" + (q[0]).toFixed(1) + " " + (q[1]).toFixed(1)); } }
    else if (mode === "move" && last && ptrs.size === 1) { T.x += e.clientX - last[0]; T.y += e.clientY - last[1]; last = [e.clientX, e.clientY]; apply(); } });
  const end = e => { ptrs.delete(e.pointerId); if (drawing) { if (drawing.pts.length > 1 && cur().strokes.length < MAX_PATHS) cur().strokes.push({ pts: drawing.pts, at: drawing.at }); else drawing.el.remove(); drawing = null; dirty(); } if (!ptrs.size) { last = null; pinch = 0; } else last = null; };
  svg.addEventListener("pointerup", end); svg.addEventListener("pointercancel", end); svg.addEventListener("lostpointercapture", e => { if (ptrs.has(e.pointerId)) end(e); });
  svg.addEventListener("wheel", e => { if (document.activeElement !== svg) return; e.preventDefault(); zoom(e.deltaY < 0 ? 1.1 : 0.9, e.clientX, e.clientY); }, { passive: false });
  svg.addEventListener("keydown", e => { if (e.key === "+" || e.key === "=") zoom(1.25); else if (e.key === "-") zoom(0.8); else if (e.key === "0") fit(); else if (e.key === "ArrowLeft") T.x += 40; else if (e.key === "ArrowRight") T.x -= 40; else if (e.key === "ArrowUp") T.y += 40; else if (e.key === "ArrowDown") T.y -= 40; else if (e.key === "Enter" && mode === "text") { openLabel(0.5, 0.5); return; } else return; e.preventDefault(); apply(); });

  /* ---- save, photo, print ---- */
  const storeChars = () => { try { return (localStorage.getItem("ek:" + EK.project.slug) || "").length; } catch (e) { return 0; } };
  $("dmSave").addEventListener("click", () => { const c = cur(); if (!c.strokes.length && !c.texts.length) return;
    const rec = EK.react({ feature: "markup", target: sheet().name, kind: "markup", value: { paths: c.strokes.map(s => ({ pts: s.pts.map(p => [Math.round(p[0] * 1000) / 1000, Math.round(p[1] * 1000) / 1000]) })), texts: c.texts.map(t => ({ x: Math.round(t.x * 1000) / 1000, y: Math.round(t.y * 1000) / 1000, t: t.t })), w: sheet().w, h: sheet().h } });
    if (!rec) { EK.toast("Could not save on this phone (storage full?). Hand your export to the team from What we heard."); return; } c.strokes = []; c.texts = []; redrawLive(); EK.context("markup", sheet().name, "\\u2014 what do your marks mean?"); EK.focusNote(); EK.toast("Marks saved on this phone \\u2014 " + (hasVoice() ? "say or type" : "type") + " what they mean below"); });
  $("dmPhoto").addEventListener("change", e => { const f = e.target.files && e.target.files[0]; e.target.value = ""; if (!f) return; if (f.size > 12 * 1024 * 1024) { EK.toast("That photo is too large (over 12 MB)"); return; }
    const url = URL.createObjectURL(f); const im = new Image(); im.onload = () => { URL.revokeObjectURL(url); if (!im.naturalWidth || !im.naturalHeight) { EK.toast("Could not read that image"); return; } const max = 1200; const k = Math.min(1, max / Math.max(im.naturalWidth, im.naturalHeight)); const c = document.createElement("canvas"); c.width = Math.max(1, Math.round(im.naturalWidth * k)); c.height = Math.max(1, Math.round(im.naturalHeight * k)); let data = "";
      /* re-encoded through a canvas: the photo's own metadata (location, device) never reaches storage */
      try { c.getContext("2d").drawImage(im, 0, 0, c.width, c.height); data = c.toDataURL("image/jpeg", 0.8); } catch (err) { EK.toast("Could not read that image"); return; }
      const b64 = (data.split(",")[1] || ""); if (!b64 || b64.length > PHOTO_CHARS) { EK.toast(b64 ? "That photo is too detailed to keep here; a plain photo of the paper is enough" : "Could not read that image"); return; }
      if (storeChars() + b64.length > STORE_WARN) { EK.toast("This phone is nearly out of room. Hand your export to the team from What we heard, then Remove all."); return; }
      const rec = EK.react({ feature: "markup", target: sheet().name, kind: "submission", value: { mime: "image/jpeg", base64: b64, w: c.width, h: c.height } }); EK.toast(rec ? "Photo added to this sheet on this phone" : "Could not keep the photo on this phone (storage full?)"); if (rec) { EK.context("markup", sheet().name, "\\u2014 what does your sketch show?"); EK.focusNote(); } };
    im.onerror = () => { URL.revokeObjectURL(url); EK.toast("Could not read that image"); }; im.src = url; });
  /* print: the figure takes the current sheet's image only now, so the page carries each sheet once */
  $("dmPrint").addEventListener("click", () => { const s = sheet(); $("dmPrintImg").src = s.src; $("dmPrintImg").alt = s.name; $("dmPrintCap").textContent = s.name + (s.slide != null ? " \\u00b7 from the presentation, slide " + s.slide : ""); $("dmPrintFig").hidden = false; $("dmPrintFig").classList.add("on"); const done = () => { $("dmPrintFig").classList.remove("on"); $("dmPrintFig").hidden = true; $("dmPrintImg").removeAttribute("src"); window.removeEventListener("afterprint", done); }; window.addEventListener("afterprint", done); window.print(); setTimeout(done, 4000); });

  /* ---- this device's markups on the current sheet ---- */
  const num01 = n => typeof n === "number" && isFinite(n) && n >= -0.1 && n <= 1.1;
  const imgOk = v => v && v.mime === "image/jpeg" && typeof v.base64 === "string" && v.base64.length < 2000000 && /^[A-Za-z0-9+\\/=]+$/.test(v.base64);
  const mkOk = v => v && Array.isArray(v.paths) && v.paths.length <= MAX_PATHS && Array.isArray(v.texts) && v.texts.length <= 100 && v.paths.every(p => p && Array.isArray(p.pts) && p.pts.length <= MAX_PTS && p.pts.every(q => Array.isArray(q) && q.length === 2 && num01(q[0]) && num01(q[1]))) && v.texts.every(t => t && typeof t.t === "string" && num01(t.x) && num01(t.y));
  function thumb(paths) { const t = document.createElementNS(NS, "svg"); t.setAttribute("viewBox", "0 0 " + sheet().w + " " + sheet().h); const bg = document.createElementNS(NS, "image"); bg.setAttribute("href", sheet().src); bg.setAttribute("width", sheet().w); bg.setAttribute("height", sheet().h); bg.setAttribute("opacity", "0.35"); t.appendChild(bg); paths.forEach(p => { const e = pathEl(p.pts); e.setAttribute("stroke-width", strokeW() * 3); t.appendChild(e); }); return t; }
  function renderMine() { const R = mine().filter(r => r.target === sheet().name); ink.textContent = ""; const box = $("dmMem"); box.textContent = "";
    R.forEach(r => { const it = document.createElement("div"); it.className = "it"; it.setAttribute("role", "listitem"); let th, label;
      if (r.kind === "markup" && mkOk(r.value)) { r.value.paths.forEach(p => ink.appendChild(pathEl(p.pts, "old"))); r.value.texts.forEach(t => ink.appendChild(textEl({ x: t.x, y: t.y, t: t.t.slice(0, 60) })));
        th = thumb(r.value.paths); const first = r.value.texts.map(t => t.t.trim()).filter(Boolean)[0]; label = first ? "\\u201c" + first.slice(0, 40) + "\\u201d" : r.value.paths.length + " stroke" + (r.value.paths.length === 1 ? "" : "s"); }
      else if (r.kind === "submission" && imgOk(r.value)) { th = document.createElement("img"); th.src = "data:image/jpeg;base64," + r.value.base64; th.alt = ""; label = "Photo of a sketch"; }
      else if (r.kind === "note" || r.kind === "voice") { return; } else { th = document.createElement("span"); label = "Unsupported markup"; }
      const t = document.createElement("div"); t.textContent = label; const s = document.createElement("small"); s.textContent = new Date(r.ts).toLocaleString([], { dateStyle: "medium", timeStyle: "short" }); t.appendChild(s);
      const x = document.createElement("button"); x.type = "button"; x.textContent = "Remove"; x.setAttribute("aria-label", "Remove " + label); x.addEventListener("click", () => { if (confirm("Remove this from this phone?")) EK.remove(r.id); });
      it.append(th, t, x); box.appendChild(it); }); }
  EK.on("ek:reaction", renderMine);

  /* ---- sizing ---- */
  let viewW = 0;
  function layoutView(force) { if (window.innerWidth >= 900) view.style.height = ""; else if (force || window.innerWidth !== viewW) { viewW = window.innerWidth; const h = stageEl.clientHeight; view.style.height = Math.round(h * 0.52) + "px"; } fit(); }
  EK.fitStage(stageEl, "markup", { onResize: () => layoutView(false) });
  EK.on("ek:show", id => { if (id === "markup") { layoutView(true); fit(); if (EK.current() === "markup") EK.context("markup", sheet().name, "\\u2014 draw on it, then say what your marks mean"); hint(); } });
  if ("ResizeObserver" in window) new ResizeObserver(() => fit()).observe(view);
  setMode("pen"); layoutView(true); showSheet(0);
  /* extension point: other features show a sheet by name (ek-list-reactions' "Show on plan") */
  EK.feature = EK.feature || {};
  EK.feature.markup = { show: name => { const i = S.findIndex(s => s.name === name); if (i < 0) return false; showSheet(i); return true; }, sheets: () => S.map(s => s.name) };

  EK.registerTour([
    { go: "markup", do: () => { showSheet(0); setMode("pen"); }, text: "Mark up the drawings: " + S.length + " sheet" + (S.length === 1 ? "" : "s") + " from the presentation. Draw with a finger what you would keep or change, then save and say what it means." },
    { go: "markup", do: () => $("dmPrint").focus(), text: "Rather draw on paper? Print the sheet, sketch, and add a photo of it here. It is kept on this phone until the team collects it." }
  ]);
})();
</script>"""


def splice(doc: str, section: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="markup">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="markup">.*?</script>', "", doc, flags=re.S)
    sec_re = re.compile(r'<section data-feature="markup"[^>]*>.*?</section>', re.S)
    if not sec_re.search(doc):
        raise SystemExit("no <section data-feature=\"markup\"> slot in the output; is ek-drawing-markup installed in the manifest and the shell built?")
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
    ap.add_argument("--root", type=Path, default=Path("."), help="where sheets[].image paths are resolved from")
    args = ap.parse_args(argv)
    for p in (args.brief, args.out):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    brief = json.loads(args.brief.read_text(encoding="utf-8-sig"))
    doc = args.out.read_text(encoding="utf-8")
    warnings: list[str] = []
    sheets = sheets_from_brief(brief, args.root, warnings)
    if not sheets:
        sys.exit("no usable sheets (brief.sheets[] or site.plan_image); ek-project-manifest should not have installed ek-drawing-markup")
    data = {"sheets": [{"name": s["name"], "w": s["w"], "h": s["h"], "slide": s["slide"], "text": s["text"], "src": s["src"]} for s in sheets]}
    new_doc = splice(doc, section_html(sheets), STYLE, SCRIPT.replace("%(data)s", json_inline(data), 1))
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "sheets": [s["name"] for s in sheets],
                      "image_bytes": sum(len(s["src"]) for s in sheets), "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
