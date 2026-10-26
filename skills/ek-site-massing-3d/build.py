#!/usr/bin/env python3
"""
ek-site-massing-3d — write the 3D massing section into an ek-shell output.

  python skills/ek-site-massing-3d/build.py --brief work/brief.json --out output/index.html [--root .]

Reads brief.options[].massing, brief.context_blocks and brief.site, replaces the shell's
<section data-feature="massing"> slot, inserts <style data-feature="massing"> at <!-- ek:styles -->,
and at <!-- ek:scripts --> the pinned three.js r128 UMD (cdnjs, SRI) followed by
<script data-feature="massing">. Idempotent. Option images are embedded as data: URIs with the same
containment and SVG rules as ek-timeline. Brief strings are data: HTML-escaped into markup, JSON-encoded
(</ neutralised) into the inline MS object, rendered with textContent only.
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

FEATURE = "massing"
THREE_SRC = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
THREE_SRI = "sha384-CI3ELBVUz9XQO+97x6nwMDPosPR5XvsxW2ua7N1Xeygeh1IxtgqtCkGfQY9WWdHu"  # computed 2026-10-26 from cdnjs bytes
STOREY_M = 3.4
IMG_MAX_W = 1400
SAFE_IMAGE_TYPES = {"image/svg+xml", "image/png", "image/jpeg", "image/webp", "image/gif"}
SVG_UNSAFE = re.compile(
    r"<script|<foreignObject|<!ENTITY|<\?xml-stylesheet|on[a-z]+\s*=|javascript:|"
    r"(?:xlink:)?href\s*=\s*[\"']?\s*(?:https?:|//|data:text)|url\(\s*[\"']?\s*(?:https?:|//)", re.I)


def log(msg: str) -> None:
    print(f"[ek-site-massing-3d] {msg}", file=sys.stderr)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


# --------------------------------------------------------------------------- images (same rules as ek-timeline)

def embed_image(rel: str, root: Path, warnings: list[str]) -> str:
    # Refuse UNC and absolute paths BEFORE touching the filesystem: on Windows, resolving \\host\share opens
    # an SMB session (credential exposure) even when the file is never read.
    if rel.startswith(("\\\\", "//")) or Path(rel).is_absolute() or rel.startswith("\\") or ":" in rel[:3]:
        warnings.append(f"image path must be relative to --root, not embedded: {rel!r}")
        return ""
    root_r = root.resolve()
    try:
        path = (root / rel).resolve()
    except (OSError, ValueError):
        warnings.append(f"image path not usable: {rel!r}")
        return ""
    if path != root_r and root_r not in path.parents:
        warnings.append(f"image outside --root, not embedded: {rel!r}")
        return ""
    if not path.is_file():
        warnings.append(f"image not found: {rel}")
        return ""
    mime = mimetypes.guess_type(path.name)[0] or ""
    if path.suffix.lower() == ".svg":
        mime = "image/svg+xml"
    if mime not in SAFE_IMAGE_TYPES:
        warnings.append(f"image type {mime or 'unknown'} not embedded: {path.name}")
        return ""
    data = path.read_bytes()
    if mime == "image/svg+xml":
        if SVG_UNSAFE.search(data.decode("utf-8", "replace")):
            warnings.append(f"SVG with script/event/entity/remote reference not embedded: {path.name}")
            return ""
    else:
        try:
            from PIL import Image  # type: ignore
            im = Image.open(BytesIO(data))
            im.load()
            if im.width > IMG_MAX_W or len(data) > 200_000 or mime == "image/jpeg":
                if im.width > IMG_MAX_W:
                    im.thumbnail((IMG_MAX_W, IMG_MAX_W * 4))
                buf = BytesIO()
                im.convert("RGB").save(buf, "JPEG", quality=82, optimize=True)
                data, mime = buf.getvalue(), "image/jpeg"
        except ImportError:
            if len(data) > 200_000:
                warnings.append(f"{path.name} is {len(data) // 1024} KB and Pillow is not installed to downscale it; EXIF not stripped")
        except Exception as e:
            warnings.append(f"image not embedded ({type(e).__name__}): {path.name}")
            return ""
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


# --------------------------------------------------------------------------- content

def num(v, default=None):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


# Sanity caps: a brief is data from an untrusted deck; a 20,000-block option or a 1e9 coordinate must not
# freeze a phone or break the camera. Everything clamped is reported.
MAX_OPTIONS, MAX_BLOCKS, MAX_CONTEXT, MAX_OUTLINE = 8, 40, 300, 500
DIM_MIN, DIM_MAX, STOREYS_MAX, COORD_MAX = 0.5, 1000.0, 100.0, 2000.0


def clamp(v: float, lo: float, hi: float, what: str, warnings: list[str]) -> float:
    if v < lo or v > hi:
        warnings.append(f"{what} {v} clamped to [{lo}, {hi}]")
        return min(hi, max(lo, v))
    return v


def slide_of(v):
    if isinstance(v, bool) or v is None or v == "":
        return None
    if isinstance(v, (int, float)) and math.isfinite(v):
        return int(v)
    return str(v)[:20]


def options_from_brief(brief: dict, root: Path, warnings: list[str]) -> list[dict]:
    out = []
    raw = brief.get("options") or []
    if len(raw) > MAX_OPTIONS:
        warnings.append(f"{len(raw)} options; only the first {MAX_OPTIONS} are built")
        raw = raw[:MAX_OPTIONS]
    seen = set()
    for i, o in enumerate(raw):
        if not isinstance(o, dict):
            continue
        oid = re.sub(r"[^A-Za-z0-9_-]", "", str(o.get("id") or chr(65 + len(out))))[:8] or chr(65 + len(out))
        if oid in seen:
            k = 2
            while f"{oid}{k}" in seen:
                k += 1
            warnings.append(f"duplicate option id {oid!r}; renamed to {oid}{k} so votes stay separate")
            oid = f"{oid}{k}"
        seen.add(oid)
        name = str(o.get("name") or f"Option {oid}").strip()[:40]
        desc = str(o.get("description") or "").strip()[:160]
        blocks = []
        massing = o.get("massing") or []
        if len(massing) > MAX_BLOCKS:
            warnings.append(f"options[{i}] {name}: {len(massing)} blocks; only the first {MAX_BLOCKS} are drawn")
            massing = massing[:MAX_BLOCKS]
        for j, b in enumerate(massing):
            if not isinstance(b, dict):
                continue
            label = str(b.get("label") or f"Block {j + 1}").strip()[:40]
            fp = b.get("footprint_m")
            w = d = None
            if isinstance(fp, (list, tuple)) and len(fp) == 2:
                w, d = num(fp[0]), num(fp[1])
            if not w or not d or w <= 0 or d <= 0:
                warnings.append(f"options[{i}] {name} / {label}: no footprint; drawn as a 6 x 6 m placeholder")
                w, d, placeholder = 6.0, 6.0, True
            else:
                placeholder = False
                w = clamp(w, DIM_MIN, DIM_MAX, f"{name}/{label} width", warnings)
                d = clamp(d, DIM_MIN, DIM_MAX, f"{name}/{label} depth", warnings)
            s = num(b.get("storeys"), None)
            if s is None or s <= 0:
                warnings.append(f"options[{i}] {name} / {label}: no storeys; drawn as 1")
                s = 1.0
            s = clamp(s, 0.1, STOREYS_MAX, f"{name}/{label} storeys", warnings)
            x = clamp(num(b.get("x"), 0.0), -COORD_MAX, COORD_MAX, f"{name}/{label} x", warnings)
            y = clamp(num(b.get("y"), 0.0), -COORD_MAX, COORD_MAX, f"{name}/{label} y", warnings)
            blocks.append({"label": label, "w": w, "d": d, "s": s, "x": x, "y": y, "placeholder": placeholder})
        if not blocks:
            warnings.append(f"options[{i}] {name} has no massing blocks; skipped")
            continue
        img = str(o.get("image") or "").strip()
        out.append({"id": oid, "name": name, "desc": desc, "blocks": blocks, "img": embed_image(img, root, warnings) if img else "",
                    "slide": slide_of(o.get("source_slide"))})
    return out


def context_from_brief(brief: dict, warnings: list[str]) -> list[list[float]]:
    out = []
    raw = brief.get("context_blocks") or []
    if len(raw) > MAX_CONTEXT:
        warnings.append(f"{len(raw)} context blocks; only the first {MAX_CONTEXT} are drawn")
        raw = raw[:MAX_CONTEXT]
    for c in raw:
        if isinstance(c, (list, tuple)) and len(c) == 5 and all(num(v) is not None for v in c):
            x, y, w, d, s = (float(v) for v in c)
            if w > 0 and d > 0 and s > 0:
                out.append([clamp(x, -COORD_MAX, COORD_MAX, "context x", warnings), clamp(y, -COORD_MAX, COORD_MAX, "context y", warnings),
                            clamp(w, DIM_MIN, DIM_MAX, "context width", warnings), clamp(d, DIM_MIN, DIM_MAX, "context depth", warnings),
                            clamp(s, 0.1, STOREYS_MAX, "context storeys", warnings)])
    if not out:
        warnings.append("no context_blocks in the brief; the options are drawn without surroundings")
    return out


def outline_from_brief(brief: dict, warnings: list[str]) -> list[list[float]]:
    site = brief.get("site") or {}
    pts = site.get("outline_m") or []
    if len(pts) > MAX_OUTLINE:
        warnings.append(f"site.outline_m has {len(pts)} points; only the first {MAX_OUTLINE} are used")
        pts = pts[:MAX_OUTLINE]
    out = [[clamp(float(p[0]), -COORD_MAX, COORD_MAX, "outline x", warnings), clamp(float(p[1]), -COORD_MAX, COORD_MAX, "outline y", warnings)]
           for p in pts if isinstance(p, (list, tuple)) and len(p) == 2 and num(p[0]) is not None and num(p[1]) is not None]
    return out if len(out) >= 3 else []


def section_html(options: list[dict], has_outline: bool, has_context: bool) -> str:
    n = len(options)
    missing = [] if has_outline else ["site line"]
    missing += ["river", "street"]  # the brief schema carries no geometry for these; a project adds them via site.outline_m or context
    about = (f"A massing study, not a design: boxes at {STOREY_M} m per storey, dimensions from the presentation. "
             + ("Not in this model, because the presentation gives no site geometry: " + ", ".join(missing) + "." if missing else "")
             + ("" if has_context else " No surrounding buildings are given either."))
    words = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five"}.get(n, str(n))
    tabs = "".join(
        f'<button type="button" role="tab" data-opt="{html.escape(o["id"])}" aria-selected="{"true" if i == 0 else "false"}"><b>{html.escape(o["name"])}</b>'
        + (f'<small>{html.escape(o["desc"])}</small>' if o["desc"] else "") + '</button>'
        for i, o in enumerate(options))
    return (
        f'<section data-feature="massing" data-title="Massing" hidden>\n'
        f'  <h2>{words} massing option{"s" if n != 1 else ""}</h2>\n'
        f'  <p class="lede">Drag to walk around the model, pinch or scroll to zoom. Switch options, move the sun to see the shadows, and tell us which one works for you.</p>\n'
        f'  <div class="ms-wrap ek-bleed">\n'
        f'    <div class="ms ek-stage" id="ms">\n'
        f'      <div class="ms-view" id="msView">\n'
        f'        <canvas id="msCanvas" tabindex="0" aria-label="3D massing model. Drag to orbit; arrow keys orbit, plus and minus zoom, 0 resets the view."></canvas>\n'
        f'        <div class="ms-hud" id="msHud" aria-live="polite"></div>\n'
        f'        <div class="ms-fallback" id="msFallback" hidden><img id="msFallbackImg" alt="" hidden><p id="msFallbackText"></p></div>\n'
        f'      </div>\n'
        f'      <div class="ms-card" id="msCard">\n'
        f'        <small class="ms-about">{html.escape(about)}</small>\n'
        f'        <div class="ms-tabs" id="msTabs" role="tablist" aria-label="Options">{tabs}</div>\n'
        f'        <div class="row"><button type="button" class="primary" id="msVote" aria-pressed="false">This option works for me</button><span class="chip ms-choice" id="msChoice" hidden></span></div>\n'
        f'        <div class="row ms-modes" data-slot="massing-modes"></div>\n'
        f'        <div class="row"><label class="chip ms-sun">Sun <input type="range" id="msSun" min="9" max="18" step="1" value="12" aria-label="Time of day"> <span id="msSunLbl">12:00</span></label><button type="button" id="msStreet">Eye level</button><button type="button" id="msResetView" hidden>Back to overview</button></div>\n'
        f'      </div>\n'
        f'    </div>\n'
        f'  </div>\n'
        f'</section>'
    )


STYLE = """<style data-feature="massing">
/* ===== ek-site-massing-3d: full-frame viewer + docked card ===== */
.ms-wrap{position:relative}
.ms{position:relative;background:var(--soft);overflow:hidden;display:flex;flex-direction:column}
.ms-view{position:relative;flex:1;min-height:0;background:var(--soft)}
@media(max-width:899px){.ms-view{flex:0 0 auto}}
.ms-view canvas{display:block;width:100%;height:100%;touch-action:none;outline:none}
.ms-view:focus-within{outline:3px solid var(--marker);outline-offset:-3px}  /* drawn on the container, above the bitmap */
.ms-hud{position:absolute;left:12px;top:12px;display:flex;flex-direction:column;gap:6px;pointer-events:none;max-width:calc(100% - 24px)}
.ms-hud .chip{background:var(--card);box-shadow:0 1px 3px rgba(0,0,0,.15)}
.ms-fallback{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;padding:16px;text-align:center;color:var(--mute);background:var(--soft)}
.ms-fallback[hidden]{display:none} .ms-fallback img{max-width:min(100%,520px);max-height:70%;border-radius:6px;border:1px solid var(--line);background:var(--card)} .ms-fallback img[hidden]{display:none}
.ms-card{flex:1 1 auto;min-height:0;overflow:auto;scrollbar-width:thin;background:var(--card);color:var(--ink);border:1px solid var(--line);border-width:1px 0 0;padding:10px 16px 14px;display:flex;flex-direction:column;gap:8px}
@media(max-width:899px){.ms-card{-webkit-mask-image:linear-gradient(to bottom,#000 calc(100% - 28px),transparent);mask-image:linear-gradient(to bottom,#000 calc(100% - 28px),transparent)} .ms-card.at-end{-webkit-mask-image:none;mask-image:none}}
@media(min-width:900px){.ms{flex-direction:row} .ms-view{height:100%} .ms-card{flex:0 0 340px;width:340px;border-width:0 0 0 1px;gap:10px}}
.ms-about{font-size:13px;line-height:1.35}
.ms-tabs{display:flex;gap:6px;flex-wrap:wrap} .ms-tabs button{flex:1 1 90px;min-height:44px;text-align:left;display:flex;flex-direction:column;gap:2px;padding:6px 10px}
.ms-tabs button small{font-weight:400;font-size:12px;color:inherit;opacity:.8} .ms-tabs button[aria-selected=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
@media(max-width:899px){.ms-tabs button small{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}}
.ms-choice{font-size:13px}
.ms-card p{max-width:52ch} .ms-card p:empty{display:none} .ms-card small{color:var(--mute);font-size:14px} .ms-card small:empty{display:none}
.ms-modes:empty{display:none}
.ms-sun{min-height:44px} #msSun{accent-color:var(--marker);width:120px;height:44px;vertical-align:middle;margin:0 4px}
#msChoice[hidden]{display:none} #msResetView[hidden]{display:none}
#msVote[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
</style>"""


SCRIPT = """<script data-feature="massing">
(function massing() {
  const MS = %(data)s;  /* brief data: options, blocks, context, outline. Rendered with textContent only. */
  const stageEl = document.getElementById("ms"), view = document.getElementById("msView"), canvas = document.getElementById("msCanvas"), hud = document.getElementById("msHud"), fb = document.getElementById("msFallback"), card = document.getElementById("msCard");
  if (!stageEl || !view || !canvas || !card) return;
  const $ = id => document.getElementById(id);
  const O = MS.options; let oi = 0; const optKey = () => "option-" + O[oi].id;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#888888";
  const dark = () => matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light" || document.documentElement.dataset.theme === "dark";

  /* ---- votes: one choice per device, derived from stored reactions ---- */
  const mine = () => EK.reactions().filter(r => r.feature === "massing" && r.kind === "vote" && typeof r.target === "string" && r.target.indexOf("option-") === 0);
  const choice = () => { const v = mine().pop(); return v ? v.target.slice(7) : null; };
  function drawChoice() { const c = choice(); const o = O.find(x => x.id === c); $("msChoice").hidden = !o; $("msChoice").textContent = o ? "Your choice (this phone): " + o.name : ""; const on = c === O[oi].id; $("msVote").textContent = on ? "\\u2713 My choice" : "This option works for me"; $("msVote").setAttribute("aria-pressed", String(on)); }
  $("msVote").addEventListener("click", () => { if (choice() === O[oi].id) { EK.toast("Already your choice \\u2014 pick another option to change it"); return; } mine().forEach(r => EK.remove(r.id)); EK.react({ feature: "massing", target: optKey(), kind: "vote", value: 1 }); EK.toast(O[oi].name + " is your choice \\u2014 saved on this phone"); });

  /* ---- option tabs + card ---- */
  const tabs = [...$("msTabs").querySelectorAll("button")];
  function showOption(i, fromTab) { oi = i; tabs.forEach((t, k) => t.setAttribute("aria-selected", String(k === i))); const o = O[i];
    if (fb && !fb.hidden) { const im = $("msFallbackImg"); im.hidden = !o.img; if (o.img) im.src = o.img; }
    selectMesh(null); if (gl) build(true); drawChoice(); EK.context("massing", optKey(), "\\u2014 " + (o.desc || o.name), o.name); }
  tabs.forEach((t, i) => { t.addEventListener("click", () => showOption(i, true)); t.addEventListener("keydown", e => { if (e.key === "ArrowRight") tabs[(i + 1) % tabs.length].focus(); if (e.key === "ArrowLeft") tabs[(i - 1 + tabs.length) % tabs.length].focus(); }); });
  $("msSun").addEventListener("input", e => { $("msSunLbl").textContent = e.target.value + ":00"; if (sun) setSun(+e.target.value); });

  /* ---- three.js ---- */
  let gl = null, scene, camera, renderer, sun, blocks = [], ctxMeshes = [], selected = null, deltas = () => ({}), selectHandlers = [], pickHandlers = [];
  const T = window.THREE;
  function fallback(msg) { fb.hidden = false; $("msFallbackText").textContent = msg; const im = $("msFallbackImg"); im.hidden = !O[oi].img; if (O[oi].img) im.src = O[oi].img; canvas.hidden = true; $("msSun").disabled = true; $("msStreet").disabled = true; }
  if (!T) fallback("The live 3D viewer could not load here, so this is the design team\\u2019s drawing of the option. Voting still works.");
  else { try { renderer = new T.WebGLRenderer({ canvas, antialias: true, alpha: true }); gl = renderer.getContext(); } catch (e) { fallback("3D needs WebGL, which this device has turned off. Voting still works."); } }

  /* one chip: the selected block when there is one (the tab already names the option), else the option */
  const hudText = () => { const o = O[oi]; hud.textContent = ""; const mk = t => { const s = document.createElement("span"); s.className = "chip"; s.textContent = t; hud.appendChild(s); }; if (selected) mk(selected.userData.label + " \\u00b7 " + fmtStoreys(storeysOf(selected.userData)) + " storey" + (storeysOf(selected.userData) === 1 ? "" : "s") + (selected.userData.placeholder ? " \\u00b7 size not given" : "")); else mk(o.name + (o.desc ? " \\u00b7 " + o.desc : "") + " \\u00b7 drag to turn"); };
  const fmtStoreys = s => (Math.round(s * 10) / 10).toString();
  const storeysOf = u => Math.max(0.3, u.s + ((deltas()[optKey() + "/" + u.label] || {}).s || 0));

  function selectMesh(m) { selected = m || null; blocks.forEach(b => b.material.color.set(b === selected ? css("--marker") : css("--plan"))); hudText();
    if (selected) EK.context("massing", optKey() + "/" + selected.userData.label, "\\u2014 what do you think of the " + selected.userData.label + "? Type below", O[oi].name + " \\u00b7 " + selected.userData.label); else if (gl) EK.context("massing", optKey(), "\\u2014 " + (O[oi].desc || O[oi].name), O[oi].name);
    selectHandlers.forEach(fn => { try { fn(selected); } catch (e) { console.error("[ek] massing onSelect", e); } }); }

  if (gl) {
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio)); renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
    scene = new T.Scene(); camera = new T.PerspectiveCamera(42, 1, 0.1, 600);
    const ground = new T.Mesh(new T.PlaneGeometry(400, 400), new T.MeshLambertMaterial({ color: css("--soft") })); ground.rotation.x = -Math.PI / 2; ground.receiveShadow = true; ground.userData.ground = true; scene.add(ground);
    if (MS.outline.length) { const pts = MS.outline.concat([MS.outline[0]]).map(p => new T.Vector3(p[0], 0.05, p[1])); scene.add(new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: css("--marker") }))); }
    MS.context.forEach(([x, z, w, d, s]) => { const m = new T.Mesh(new T.BoxGeometry(w, s * MS.storey, d), new T.MeshLambertMaterial({ color: css("--line") })); m.position.set(x + w / 2, s * MS.storey / 2, z + d / 2); m.castShadow = m.receiveShadow = true; scene.add(m); ctxMeshes.push(m); });
    const amb = new T.AmbientLight(0xffffff, 0.6); scene.add(amb);
    sun = new T.DirectionalLight(0xffffff, 0.9); sun.castShadow = true; sun.shadow.mapSize.set(1024, 1024); const sc = sun.shadow.camera; sc.left = sc.bottom = -80; sc.right = sc.top = 80; sc.far = 300; scene.add(sun);
    function setSun(h) { const a = ((h - 6) / 12) * Math.PI; sun.position.set(Math.cos(a) * 90, Math.sin(a) * 70 + 10, 30); }
    setSun(12);
    /* materials follow the colour scheme */
    const recolour = () => { ground.material.color.set(css("--soft")); ctxMeshes.forEach(m => m.material.color.set(css("--line"))); blocks.forEach(b => b.material.color.set(b === selected ? css("--marker") : css("--plan"))); amb.intensity = dark() ? 0.5 : 0.7; };
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", recolour);

    /* option blocks (heights animate unless reduced motion) */
    let anim = 0;
    function build(animate) { blocks.forEach(b => scene.remove(b)); blocks = []; const o = O[oi]; const D = deltas();
      o.blocks.forEach(u => { const k = optKey() + "/" + u.label, d = D[k] || {}; const s = Math.max(0.3, u.s + (d.s || 0)); const m = new T.Mesh(new T.BoxGeometry(u.w, s * MS.storey, u.d), new T.MeshLambertMaterial({ color: css("--plan") }));
        m.position.set(u.x + u.w / 2 + (d.x || 0), s * MS.storey / 2, u.y + u.d / 2 + (d.z || 0)); m.castShadow = m.receiveShadow = true; m.userData = u; if (u.placeholder) m.material.transparent = true, m.material.opacity = 0.6; scene.add(m); blocks.push(m);
        if (animate && !reduced) { m.scale.y = 0.05; m.position.y = s * MS.storey * 0.025; } });
      cancelAnimationFrame(anim); if (animate && !reduced) { const t0 = performance.now(); const tick = () => { const k = Math.min(1, (performance.now() - t0) / 400); const e = 1 - Math.pow(1 - k, 3); blocks.forEach(m => { const full = storeysOf(m.userData) * MS.storey; m.scale.y = 0.05 + 0.95 * e; m.position.y = full * m.scale.y / 2; }); if (k < 1) anim = requestAnimationFrame(tick); }; tick(); }
      hudText(); }

    /* camera: fit everything */
    let theta = 0.8, phi = 0.95, dist = 60, target = new T.Vector3(0, 2, 0), home = null;
    function fit() { const box = new T.Box3(); blocks.concat(ctxMeshes).forEach(m => box.expandByObject(m)); if (box.isEmpty()) box.set(new T.Vector3(-20, 0, -20), new T.Vector3(20, 10, 20)); const c = box.getCenter(new T.Vector3()), sz = box.getSize(new T.Vector3()); target.set(c.x, Math.min(4, sz.y / 3), c.z); dist = Math.max(sz.x, sz.z) * 1.15 + 20; theta = 0.8; phi = 0.95; home = { theta, phi, dist, target: target.clone() }; update(); }
    function update() { phi = Math.max(0.1, Math.min(1.5, phi)); dist = Math.max(8, Math.min(400, dist)); camera.position.set(target.x + dist * Math.sin(phi) * Math.sin(theta), target.y + dist * Math.cos(phi), target.z + dist * Math.sin(phi) * Math.cos(theta)); camera.lookAt(target); }
    /* eye level: the camera itself sits at 1.6 m, looking slightly down across the site from the front */
    $("msStreet").addEventListener("click", () => { const d = Math.max(16, home ? home.dist * 0.45 : 30); target.set(home ? home.target.x : 0, 1.6, home ? home.target.z : 0); theta = 0.3; dist = d; phi = Math.acos(Math.min(1, Math.max(-1, (1.6 - target.y) / d))) ; phi = Math.max(1.5, Math.min(1.56, phi)); update(); camera.position.y = 1.6; camera.lookAt(target); $("msResetView").hidden = false; $("msStreet").hidden = true; EK.toast("Eye level, 1.6 m above the ground"); });
    $("msResetView").addEventListener("click", () => { if (home) { theta = home.theta; phi = home.phi; dist = home.dist; target.copy(home.target); update(); } $("msResetView").hidden = true; $("msStreet").hidden = false; });

    /* pointer: orbit, pan (shift / two fingers), pinch, tap to pick */
    let drag = null; const ptrs = new Map(); let pinchD = 0;
    canvas.addEventListener("pointerdown", e => { canvas.setPointerCapture(e.pointerId); ptrs.set(e.pointerId, [e.clientX, e.clientY]); drag = { x: e.clientX, y: e.clientY, moved: 0 }; if (ptrs.size === 2) { const p = [...ptrs.values()]; pinchD = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]); } canvas.focus({ preventScroll: true }); });
    canvas.addEventListener("pointermove", e => { if (!ptrs.has(e.pointerId)) return; ptrs.set(e.pointerId, [e.clientX, e.clientY]);
      if (ptrs.size === 2) { const p = [...ptrs.values()]; const dd = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]); if (pinchD) dist *= pinchD / dd; pinchD = dd; const mid = [(p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2]; if (drag) { target.x -= (mid[0] - drag.x) * 0.05; target.z -= (mid[1] - drag.y) * 0.05; } drag = { x: mid[0], y: mid[1], moved: 99 }; update(); return; }
      if (!drag) return; const dx = e.clientX - drag.x, dy = e.clientY - drag.y; drag.moved += Math.abs(dx) + Math.abs(dy); if (e.shiftKey || e.buttons === 4) { target.x -= dx * 0.05; target.z -= dy * 0.05; } else { theta -= dx * 0.008; phi -= dy * 0.008; } drag.x = e.clientX; drag.y = e.clientY; update(); });
    const endPtr = e => { ptrs.delete(e.pointerId); if (drag && drag.moved < 6 && ptrs.size === 0) pick(e); if (ptrs.size === 0) drag = null; pinchD = 0; };
    canvas.addEventListener("pointerup", endPtr); canvas.addEventListener("pointercancel", endPtr);
    canvas.addEventListener("wheel", e => { if (document.activeElement !== canvas) return; e.preventDefault(); dist *= 1 + Math.sign(e.deltaY) * 0.08; update(); }, { passive: false });
    canvas.addEventListener("keydown", e => { const k = e.key; if (k === "ArrowLeft") theta += .1; else if (k === "ArrowRight") theta -= .1; else if (k === "ArrowUp") phi -= .08; else if (k === "ArrowDown") phi += .08; else if (k === "+" || k === "=") dist *= .9; else if (k === "-") dist *= 1.1; else if (k === "0") { $("msResetView").click(); return; } else return; e.preventDefault(); update(); });
    const ray = new T.Raycaster(), ndc = new T.Vector2();
    function pick(e) { const r = canvas.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(ndc, camera); const hit = ray.intersectObjects(blocks)[0];
      let handled = false; pickHandlers.forEach(fn => { try { if (fn(hit || null, e) === true) handled = true; } catch (err) { console.error("[ek] massing onPick", err); } });
      if (handled) return; selectMesh(hit ? hit.object : null); }

    build(false); fit(); resize();
    (function loop() { requestAnimationFrame(loop); if (document.querySelector('[data-feature="massing"]').hidden) return; renderer.render(scene, camera); })();
    window.addEventListener("resize", resize);
    if ("ResizeObserver" in window) new ResizeObserver(resize).observe(view);

    /* extension point for ek-massing-markup */
    EK.feature = EK.feature || {};
    EK.feature.massing = { options: O, option: () => O[oi], optionKey: optKey, blocks: () => blocks.slice(), context: () => ctxMeshes.slice(), select: selectMesh, selected: () => selected, onSelect: fn => selectHandlers.push(fn), onPick: fn => pickHandlers.push(fn), scene, camera, renderer, canvas, view, rebuild: () => { build(false); selectMesh(null); }, setDeltas: fn => { deltas = fn || (() => ({})); }, storeysOf, storey: MS.storey };
  } else { EK.feature = EK.feature || {}; EK.feature.massing = { options: O, option: () => O[oi], optionKey: optKey, blocks: () => [], select: () => {}, selected: () => null, onSelect: () => {}, onPick: () => {}, rebuild: () => {}, setDeltas: () => {}, fallback: true }; }

  /* ---- sizing: phones get a fixed-pixel view height per show; desktop the card is a side column ---- */
  let viewW = 0;
  /* phones: half the stage for the model; the card below holds tabs, vote, sun and the study note without an inner fold on a 812 px screen */
  function layoutView(force) { if (window.innerWidth >= 900) { view.style.height = ""; } else if (force || window.innerWidth !== viewW) { viewW = window.innerWidth; const h = stageEl.clientHeight; view.style.height = Math.round(h * (h < 520 ? 0.42 : 0.5)) + "px"; } if (gl) resize(); }
  const atEnd = () => card.classList.toggle("at-end", card.scrollHeight - card.clientHeight - card.scrollTop < 8);
  card.addEventListener("scroll", atEnd, { passive: true }); EK.on("ek:show", id => { if (id === "massing") setTimeout(atEnd, 100); });
  EK.fitStage(stageEl, "massing", { onResize: () => layoutView(false) });
  EK.on("ek:show", id => { if (id === "massing") { layoutView(true); if (gl) resize(); showOption(oi); } });
  EK.on("ek:reaction", drawChoice);
  layoutView(true); showOption(0);
  function resize() { if (!gl) return; const w = view.clientWidth, h = view.clientHeight; if (!w || !h) return; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }

  /* ---- tour ---- */
  EK.registerTour([
    { go: "massing", do: () => tabs[Math.min(1, tabs.length - 1)].click(), undo: () => tabs[0].click(), text: "Massing: " + O.length + " option" + (O.length === 1 ? "" : "s") + " on the site, as boxes. Drag to walk around; switch options with the tabs." },
    { go: "massing", do: () => { $("msSun").value = "16"; $("msSun").dispatchEvent(new Event("input", { bubbles: true })); }, undo: () => { $("msSun").value = "12"; $("msSun").dispatchEvent(new Event("input", { bubbles: true })); }, text: "Slide the sun to see where the shadows fall at 9, noon and 6." },
    { go: "massing", do: () => { if (!$("msVote").disabled) $("msVote").click(); }, undo: () => { mine().forEach(r => EK.remove(r.id)); }, text: "Tell us which option works for you. One choice per phone; you can change it any time." }
  ]);
})();
</script>"""


def splice(doc: str, section: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="massing">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script[^>]*data-feature="massing"[^>]*>.*?</script>', "", doc, flags=re.S)
    sec_re = re.compile(r'<section data-feature="massing"[^>]*>.*?</section>', re.S)
    if not sec_re.search(doc):
        raise SystemExit("no <section data-feature=\"massing\"> slot in the output; is ek-site-massing-3d installed in the manifest and the shell built?")
    doc = sec_re.sub(lambda m: section, doc, count=1)
    lib = f'<script src="{THREE_SRC}" integrity="{THREE_SRI}" crossorigin="anonymous" data-feature="massing"></script>'
    for marker, block in (("<!-- ek:styles -->", style), ("<!-- ek:scripts -->", lib + "\n" + script)):
        if marker not in doc:
            raise SystemExit(f"shell marker {marker} missing from the output")
        doc = doc.replace(marker, marker + "\n" + block, 1)
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", type=Path, default=Path("work/brief.json"))
    ap.add_argument("--out", type=Path, default=Path("output/index.html"))
    ap.add_argument("--root", type=Path, default=Path("."), help="where options[].image paths are resolved from")
    args = ap.parse_args(argv)
    for p in (args.brief, args.out):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    doc = args.out.read_text(encoding="utf-8")
    warnings: list[str] = []
    options = options_from_brief(brief, args.root, warnings)
    if not options:
        sys.exit("brief.options has no usable massing; ek-project-manifest should not have installed ek-site-massing-3d")
    data = {"options": options, "context": context_from_brief(brief, warnings), "outline": outline_from_brief(brief, warnings), "storey": STOREY_M}
    new_doc = splice(doc, section_html(options, bool(data["outline"]), bool(data["context"])), STYLE, SCRIPT.replace("%(data)s", json_inline(data), 1))
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "options": [o["id"] for o in options],
                      "blocks": sum(len(o["blocks"]) for o in options), "context_blocks": len(data["context"]), "outline_points": len(data["outline"]),
                      "images_embedded": sum(1 for o in options if o["img"]), "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
