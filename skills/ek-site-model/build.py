#!/usr/bin/env python3
"""
ek-site-model — write the 3D site-model section into an ek-shell output.

  python skills/ek-site-model/build.py --brief work/brief.json --model work/model.json --out output/index.html [--root .]

Reads the viewer JSON written by export_3dm.py (terrain, water, existing buildings, proposed buildings as
separate meshes, trees as records, paths as polylines), replaces the shell's <section data-feature="model">
slot, inserts <style data-feature="model"> at <!-- ek:styles --> and, at <!-- ek:scripts -->, the pinned
three.js r128 UMD (cdnjs, SRI) followed by <script data-feature="model">. Idempotent.
The interaction is the one Massing Studio uses: drag to orbit, right-drag / shift-drag or two fingers to
pan, scroll or pinch to zoom, double-click to reset, a sun with azimuth and altitude, soft shadows, matte
greys so the buildings are the only colour, and labels that sit on the facade you are looking at. Every
proposed building is a reaction target: tap it, say whether its spot works, say why through the bar.
Model and brief strings are data: HTML-escaped into markup, JSON-encoded (</ neutralised) into the inline
SM object, rendered with textContent only. The mesh buffers are base64 numbers, never code.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path

FEATURE = "model"
THREE_SRC = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
THREE_SRI = "sha384-CI3ELBVUz9XQO+97x6nwMDPosPR5XvsxW2ua7N1Xeygeh1IxtgqtCkGfQY9WWdHu"  # computed 2026-10-26 from cdnjs bytes
MAX_BUILDINGS = 12
MAX_TREES = 3000
MAX_CURVES = 400
MAX_BYTES = 6_000_000
MAX_COORD = 100_000.0
B64 = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")
THREE_TAG = f'<script src="{THREE_SRC}" integrity="{THREE_SRI}" crossorigin="anonymous" data-feature="lib-three"></script>'


def log(msg: str) -> None:
    print(f"[ek-site-model] {msg}", file=sys.stderr)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def load_model(rel: str, root: Path, warnings: list[str]) -> dict | None:
    """The model path comes from the command line, but it is still resolved under --root so a brief or manifest
    that names it cannot point the build at an arbitrary file."""
    if rel.startswith(("\\\\", "//")) or Path(rel).is_absolute() or rel.startswith("\\") or ":" in rel[:3]:
        warnings.append(f"model path must be relative to --root: {rel!r}")
        return None
    root_r = root.resolve()
    path = (root / rel).resolve()
    if path != root_r and root_r not in path.parents:
        warnings.append(f"model outside --root: {rel!r}")
        return None
    if not path.is_file():
        warnings.append(f"model not found: {rel}")
        return None
    if path.stat().st_size > MAX_BYTES:
        warnings.append(f"model is {path.stat().st_size // 1024} KB, over the {MAX_BYTES // 1024} KB cap; re-export lighter")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        warnings.append(f"model not readable ({type(e).__name__})")
        return None


def num(v, default=0.0):
    try:
        f = float(v)
        return f if math.isfinite(f) else default
    except (TypeError, ValueError):
        return default


def check_buffer(m: dict, what: str, warnings: list[str]) -> dict | None:
    """Decode the buffers once here so a tampered model.json is refused at build time, not in the visitor's browser."""
    import base64
    import struct
    pos, idx = m.get("pos"), m.get("idx")
    if not isinstance(pos, str) or not isinstance(idx, str) or not B64.match(pos) or not B64.match(idx) or len(pos) % 4 or len(idx) % 4:
        warnings.append(f"{what}: mesh buffers are not base64; skipped")
        return None
    it = m.get("idx_type")
    if it not in ("u16", "u32"):
        warnings.append(f"{what}: unknown index type; skipped")
        return None
    try:
        pb, ib = base64.b64decode(pos, validate=True), base64.b64decode(idx, validate=True)
    except (ValueError, TypeError):
        warnings.append(f"{what}: buffers do not decode; skipped")
        return None
    isz = 2 if it == "u16" else 4
    if len(pb) % 12 or len(ib) % (3 * isz) or not pb or not ib:
        warnings.append(f"{what}: buffer sizes are not whole triangles; skipped")
        return None
    nv = len(pb) // 12
    ind = struct.unpack(f"<{len(ib) // isz}{'H' if isz == 2 else 'I'}", ib)
    if max(ind) >= nv:
        warnings.append(f"{what}: an index points past the vertex list; skipped")
        return None
    xs = struct.unpack(f"<{nv * 3}f", pb)
    if not all(math.isfinite(v) and abs(v) <= MAX_COORD for v in xs):
        warnings.append(f"{what}: a coordinate is not finite or is beyond {MAX_COORD:.0f} m; skipped")
        return None
    bb = [min(xs[0::3]), min(xs[1::3]), min(xs[2::3]), max(xs[0::3]), max(xs[1::3]), max(xs[2::3])]
    return {"pos": pos, "idx": idx, "idx_type": it, "verts": nv, "tris": len(ind) // 3, "bbox": [round(v, 3) for v in bb]}


def model_data(model: dict, brief: dict, warnings: list[str]) -> dict:
    meshes = []
    for m in model.get("meshes") or []:
        if not isinstance(m, dict):
            continue
        kind = str(m.get("kind") or "")
        if kind not in ("terrain", "water", "existing"):
            warnings.append(f"mesh kind {kind!r} not drawn")
            continue
        b = check_buffer(m, f"mesh {kind}", warnings)
        if b:
            meshes.append({"kind": kind, **b})
    if not any(m["kind"] == "terrain" for m in meshes):
        warnings.append("no terrain mesh; the model floats on a flat ground")
    buildings = []
    raw = model.get("buildings") or []
    if len(raw) > MAX_BUILDINGS:
        warnings.append(f"{len(raw)} buildings; only the first {MAX_BUILDINGS} are reaction targets")
        raw = raw[:MAX_BUILDINGS]
    seen = set()
    views = {}
    for v in ((brief.get("site") or {}).get("views") or []):
        if isinstance(v, dict) and v.get("building") and num(v.get("bearing_deg"), None) is not None:
            sl = v.get("source_slide")
            views[str(v["building"]).strip().lower()] = {"bearing": num(v["bearing_deg"]) % 360, "slide": (str(sl)[:12] if sl not in (None, "", False) else None)}
    for i, b in enumerate(raw):
        if not isinstance(b, dict):
            continue
        label = str(b.get("label") or f"Building {i + 1}").strip()[:60]
        if label.lower() in seen:
            warnings.append(f"duplicate building label {label!r}; reactions target by label")
        seen.add(label.lower())
        buf = check_buffer(b, f"building {label}", warnings)
        if not buf:
            continue
        c = b.get("center")
        if not (isinstance(c, list) and len(c) == 3):
            c = [(buf["bbox"][0] + buf["bbox"][3]) / 2, (buf["bbox"][1] + buf["bbox"][4]) / 2, (buf["bbox"][2] + buf["bbox"][5]) / 2]
        # exact match on the label, or on the label without its position word ("Hermitage cabin (north)" → "Hermitage cabin")
        base = re.sub(r"\s*\([^)]*\)\s*$", "", label).strip().lower()
        view = views.get(label.lower()) or views.get(base)
        buildings.append({"label": label, "center": [num(x) for x in c], "view": view, **buf})
    trees = []
    for t in (model.get("trees") or [])[:MAX_TREES]:
        if isinstance(t, list) and len(t) == 5 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in t):
            trees.append([round(float(v), 2) for v in t])
    if len(model.get("trees") or []) > MAX_TREES:
        warnings.append(f"{len(model['trees'])} trees; only the first {MAX_TREES} are drawn")
    curves = []
    for c in (model.get("curves") or [])[:MAX_CURVES]:
        if isinstance(c, list) and len(c) >= 2 and all(isinstance(p, list) and len(p) == 3 and all(isinstance(v, (int, float)) and math.isfinite(v) for v in p) for p in c):
            curves.append(c)
    return {"meshes": meshes, "buildings": buildings, "trees": trees, "curves": curves}


def about_text(data: dict, brief: dict) -> str:
    """What is in the model, from the data; what is not, from the brief's own note. Never a sentence about another project."""
    n = len(data["buildings"])
    kinds = [m["kind"] for m in data["meshes"]]
    parts = []
    if "terrain" in kinds:
        parts.append("the ground")
    if "water" in kinds:
        parts.append("the water")
    if data["trees"]:
        parts.append("the trees")
    if "existing" in kinds:
        parts.append("the existing buildings")
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}
    if n:
        parts.append(f"{words.get(n, str(n))} proposed building{'s' if n != 1 else ''}")
    inside = ", ".join(parts[:-1]) + (" and " + parts[-1] if len(parts) > 1 else (parts[0] if parts else "the site"))
    note = str(brief.get("model_note") or "").strip()
    not_in = " Anything the team has not modelled yet is not in it."
    if note:
        # the whole sentence of the brief's note that says what is not modelled, never a fragment
        for s in re.split(r"(?<=[.!?])\s+", note):
            if re.search(r"\bnot (?:modelled|in the (?:file|model))\b", s, re.I):
                not_in = " " + s.strip()[:240]
                break
    return f"The design team's working model, as exported: {inside}.{not_in}"


def section_html(data: dict, brief: dict) -> str:
    n = len(data["buildings"])
    chips = "".join(f'<button type="button" class="sm-chip" data-b="{html.escape(b["label"])}" aria-pressed="false">{html.escape(b["label"])}</button>' for b in data["buildings"])
    about = about_text(data, brief)
    return (
        f'<section data-feature="model" data-title="The model" hidden>\n'
        f'  <h2>The site in 3D</h2>\n'
        f'  <p class="lede" data-with-voice="Turn the model, move the sun, stand at each building and look out. Then say whether its spot works for you, and speak or type why." data-without-voice="Turn the model, move the sun, stand at each building and look out. Then say whether its spot works for you, and type why.">Turn the model, move the sun, stand at each building and look out. Then say whether its spot works for you, and type why.</p>\n'
        f'  <div class="sm-wrap ek-bleed">\n'
        f'    <div class="sm ek-stage" id="sm">\n'
        f'      <div class="sm-view" id="smView">\n'
        f'        <canvas id="smCanvas" tabindex="0" aria-label="3D site model. Drag to turn; arrow keys turn, plus and minus zoom, 0 resets the view, Tab reaches the building buttons."></canvas>\n'
        f'        <div class="sm-labels" id="smLabels" aria-hidden="true"></div>\n'
        f'        <details class="sm-ovl sm-viewbox" id="smViewBox"><summary>View</summary><div class="sm-vb">\n'
        f'          <label><input type="checkbox" id="smTrees" checked> trees</label>\n'
        f'          <label><input type="checkbox" id="smLabelsOn" checked> labels</label>\n'
        f'          <label><input type="checkbox" id="smShadows" checked> shadows</label>\n'
        f'          <div class="sm-sun"><span>Sun</span><input type="range" id="smAz" min="0" max="360" value="215" aria-label="Sun direction, degrees from north"><span id="smAzV">215°</span><input type="range" id="smAlt" min="5" max="85" value="42" aria-label="Sun height, degrees"><span id="smAltV">42°</span></div>\n'
        f'          <div class="sm-hint">Drag to turn · two fingers or shift-drag to move · pinch or scroll to zoom · double-tap to reset</div>\n'
        f'        </div></details>\n'
        f'        <div class="sm-fallback" id="smFallback" hidden><p id="smFallbackText"></p></div>\n'
        f'      </div>\n'
        f'      <div class="sm-card" id="smCard">\n'
        f'        <small class="sm-about" id="smAbout">{html.escape(about)}</small>\n'
        f'        <div class="sm-chips" id="smChips" role="group" aria-label="Buildings">{chips}</div>\n'
        f'        <div class="sm-sel" id="smSel" hidden>\n'
        f'          <div class="row sm-selhead"><button type="button" class="sm-all" id="smAll">&larr; All buildings</button></div>\n'
        f'          <span class="sm-name" id="smName"></span>\n'
        f'          <small id="smMeta"></small>\n'
        f'          <div class="row" role="group" aria-label="Does this spot work?"><button type="button" class="sm-vote" data-v="keep" aria-pressed="false">The spot works</button><button type="button" class="sm-vote" data-v="move" aria-pressed="false">It should move</button></div>\n'
        f'          <div class="row"><button type="button" class="primary" id="smSay">Say why</button><button type="button" id="smStand">Stand here</button><button type="button" id="smBack" hidden>Back to overview</button><span class="chip sm-count" id="smCount" hidden></span></div>\n'
        f'          <div class="sm-mem" id="smMem" role="list" aria-label="Your notes on this building"></div>\n'
        f'        </div>\n'
        f'        <div class="row sm-none" id="smNone"><button type="button" id="smOverview">Overview</button><span class="sm-hint2">Tap a building, in the model or above, to react to it.</span></div>\n'
        f'        <div class="sm-slot" data-slot="pins" id="smSlot"></div>\n'
        f'      </div>\n'
        f'    </div>\n'
        f'  </div>\n'
        f'</section>'
    )


STYLE = """<style data-feature="model">
/* ===== ek-site-model: full-frame viewer in the Massing Studio manner, overlays floating over the canvas ===== */
.sm-wrap{position:relative}
.sm{position:relative;background:var(--soft);overflow:hidden;display:flex;flex-direction:column}
.sm-view{position:relative;flex:1;min-height:0;background:var(--soft)}
@media(max-width:899px){.sm-view{flex:0 0 auto}}
.sm-view canvas{display:block;width:100%;height:100%;touch-action:none;outline:none;cursor:grab} .sm-view canvas:active{cursor:grabbing}
.sm-view:focus-within{outline:3px solid var(--marker);outline-offset:-3px}
.sm-labels{position:absolute;inset:0;pointer-events:none;overflow:hidden}
.sm-lbl{position:absolute;transform:translate(-50%,-50%);white-space:nowrap;font-size:12px;color:var(--ink);background:var(--card);border-radius:999px;padding:2px 9px 2px 7px;box-shadow:0 1px 4px rgba(0,0,0,.12);display:flex;align-items:center;gap:6px}
.sm-lbl i{display:inline-block;width:8px;height:8px;border-radius:2px;background:var(--plan)} .sm-lbl.sel i{background:var(--marker)}
.sm-ovl{position:absolute;background:var(--card);border-radius:8px;box-shadow:0 1px 2px rgba(20,25,35,.05),0 10px 30px -14px rgba(20,25,35,.3);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);font-size:13px;color:var(--mute)}
.sm-viewbox{left:10px;top:10px;padding:0;max-width:calc(100% - 20px)} .sm-viewbox summary{cursor:pointer;list-style:none;padding:8px 12px;font-size:11px;text-transform:uppercase;letter-spacing:.08em;min-height:36px;display:flex;align-items:center}
.sm-viewbox summary::-webkit-details-marker{display:none} .sm-viewbox summary::before{content:"▸ "} .sm-viewbox[open] summary::before{content:"▾ "}
.sm-vb{padding:0 12px 10px;width:250px;max-width:100%;display:flex;flex-direction:column;gap:6px} .sm-vb label{display:flex;align-items:center;gap:8px;min-height:32px}
.sm-sun{display:grid;grid-template-columns:auto 1fr auto 1fr auto;gap:6px 8px;align-items:center} .sm-sun input[type=range]{width:100%;min-height:32px;accent-color:var(--marker)}
.sm-hint{font-size:12px;line-height:1.35} .sm-hint2{font-size:13px;color:var(--mute)}
.sm-fallback{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:16px;text-align:center;color:var(--mute);background:var(--soft)} .sm-fallback[hidden]{display:none}
.sm-card{flex:1 1 auto;min-height:0;overflow:auto;scrollbar-width:thin;background:var(--card);color:var(--ink);border:1px solid var(--line);border-width:1px 0 0;padding:10px 16px 14px;display:flex;flex-direction:column;gap:8px}
@media(min-width:900px){.sm{flex-direction:row} .sm-view{height:100%} .sm-card{flex:0 0 340px;width:340px;border-width:0 0 0 1px;gap:10px}}
.sm-about{font-size:13px;line-height:1.35;color:var(--mute)}
.sm-chips{display:flex;flex-wrap:wrap;gap:6px} .sm-chip{min-height:44px;padding:8px 14px;border-radius:999px;font-size:14px}
.sm-chip[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.sm-sel[hidden],.sm-none[hidden],#smBack[hidden],#smCount[hidden],.sm-about[hidden],.sm-chips[hidden],.sm-slot[hidden]{display:none}
.sm-sel{display:flex;flex-direction:column;gap:8px} .sm-all{min-height:36px;padding:4px 10px;font-size:13px;color:var(--mute);border-color:transparent;background:transparent} .sm-name{font-size:24px;font-weight:500;line-height:1.05}
.sm-sun input[type=range]{min-height:44px}
.sm-sel small{color:var(--mute);font-size:13px} .sm-sel small:empty{display:none}
.sm-vote{min-height:44px;padding:8px 12px;border:1px solid var(--line);border-radius:22px;background:var(--paper);color:var(--ink);font-size:14px;display:inline-flex;align-items:center;gap:6px}
.sm-vote::before{content:"";width:12px;height:12px;border-radius:6px;border:2px solid var(--mute);flex:0 0 auto}
.sm-vote[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)} .sm-vote[aria-pressed=true]::before{background:var(--marker);border-color:var(--marker)}
.sm-mem{display:grid;gap:6px} .sm-mem:empty{display:none} .sm-slot{display:flex;flex-direction:column;gap:8px} .sm-slot:empty{display:none}
.sm-mem div{padding:8px 10px;border-left:3px solid var(--marker);background:var(--soft);border-radius:0 6px 6px 0;font-size:15px;overflow-wrap:anywhere}
.sm-mem audio{width:100%;max-width:320px;height:36px;display:block}
@media(prefers-reduced-motion:reduce){.sm-view canvas{transition:none}}
</style>"""


SCRIPT = """<script data-feature="model">
(function siteModel() {
  const SM = %(data)s;  /* model buffers (base64 numbers) and building labels; rendered with textContent only */
  const stageEl = document.getElementById("sm"), view = document.getElementById("smView"), canvas = document.getElementById("smCanvas"), card = document.getElementById("smCard"), lblBox = document.getElementById("smLabels"), fb = document.getElementById("smFallback");
  if (!stageEl || !view || !canvas || !card) return;
  const $ = id => document.getElementById(id);
  const T = window.THREE;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#888888";
  const dark = () => document.documentElement.dataset.theme === "dark" || (matchMedia("(prefers-color-scheme: dark)").matches && document.documentElement.dataset.theme !== "light");
  const hasVoice = () => EK.hasKind && EK.hasKind("voice");
  const B = SM.buildings; let sel = null;
  const mine = () => EK.reactions().filter(r => r.feature === "model");
  const voteOf = t => { const v = mine().filter(r => r.kind === "vote" && r.target === t && (r.value === "keep" || r.value === "move")).pop(); return v ? v.value : ""; };
  const byLabel = l => B.find(b => b.label === l) || null;

  /* ---- decode buffers ---- */
  function bytes(b64) { const s = atob(b64); const a = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) a[i] = s.charCodeAt(i); return a; }
  function geom(m, flat) { if (!T) return null; const p = new Float32Array(bytes(m.pos).buffer); const ib = bytes(m.idx).buffer; const idx = m.idx_type === "u16" ? new Uint16Array(ib) : new Uint32Array(ib);
    let g = new T.BufferGeometry(); g.setAttribute("position", new T.BufferAttribute(p, 3)); g.setIndex(new T.BufferAttribute(idx, 1)); if (flat) g = g.toNonIndexed(); g.computeVertexNormals(); return g; }

  /* ---- three ---- */
  let gl = null, renderer, scene, camera, sun, hemi, group, bMeshes = [], gMeshes = [], treeGroup, shadowsOn = true;
  const pickHooks = [], renderHooks = [];  /* extension point: see EK.feature.model.onPick / onRender */
  function fallback(msg) { fb.hidden = false; $("smFallbackText").textContent = msg; canvas.hidden = true; $("smViewBox").hidden = true; $("smStand").disabled = true; $("smOverview").disabled = true; }
  if (!T) fallback("The 3D model could not load here (no connection to the script library). You can still react to each building from the list.");
  else { try { renderer = new T.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true }); gl = renderer.getContext(); } catch (e) { fallback("3D needs WebGL, which this device has turned off. You can still react to each building from the list."); } }

  /* palette: matte greys from the project tokens; the proposed buildings are the only colour */
  const P = () => { const d = dark(); return { bg: d ? 0x1a1e23 : 0xe8eaed, ground: d ? 0x3a4149 : 0xd9dde2, water: d ? 0x34485c : 0xb9c9d8, existing: d ? 0x4a525c : 0xc3c8ce, edge: d ? 0xffffff : 0x2a2f36, edgeA: d ? 0.22 : 0.16, path: d ? 0xa0a7b1 : 0x6c737c, trunk: d ? 0x5e4d38 : 0x7a6248, crown: d ? 0x5b7f5e : 0x89ad86, hemiGround: d ? 0x2a3038 : 0x9aa1ab, hemiI: d ? 0.75 : 0.5 }; };
  const bbox = { min: [Infinity, Infinity, Infinity], max: [-Infinity, -Infinity, -Infinity] };
  const grow = bb => { for (let k = 0; k < 3; k++) { bbox.min[k] = Math.min(bbox.min[k], bb[k]); bbox.max[k] = Math.max(bbox.max[k], bb[k + 3]); } };
  SM.meshes.forEach(m => grow(m.bbox)); B.forEach(b => grow(b.bbox));
  if (!isFinite(bbox.min[0])) { bbox.min = [-50, 0, -50]; bbox.max = [50, 10, 50]; }
  const span = Math.max(bbox.max[0] - bbox.min[0], bbox.max[2] - bbox.min[2], 40);
  const centre = B.length ? [B.reduce((s, b) => s + b.center[0], 0) / B.length, B.reduce((s, b) => s + b.center[1], 0) / B.length, B.reduce((s, b) => s + b.center[2], 0) / B.length] : [(bbox.min[0] + bbox.max[0]) / 2, (bbox.min[1] + bbox.max[1]) / 2, (bbox.min[2] + bbox.max[2]) / 2];

  let orbit = { th: -0.9, ph: 0.95, r: 1, pan: [0, 0] }, standing = null;
  const HOME = () => ({ th: -0.9, ph: 0.95, r: 1, pan: [0, 0] });
  function dispose(obj) { obj.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) (Array.isArray(o.material) ? o.material : [o.material]).forEach(m => m.dispose()); }); }
  function build() { try { buildScene(); } catch (e) { console.error("[ek] model build", e); fallback("The 3D model could not be drawn on this device. You can still react to each building from the list."); gl = null; } }
  function buildScene() {
    if (!gl) return; const C = P(); if (group) { scene.remove(group); dispose(group); } group = new T.Group(); scene.add(group); bMeshes = []; gMeshes = [];
    const lam = (color, extra) => new T.MeshLambertMaterial(Object.assign({ color }, extra || {}));
    SM.meshes.forEach(m => { const g = geom(m, m.kind === "existing"); if (!g) return; const mat = m.kind === "water" ? lam(C.water, { transparent: true, opacity: 0.85 }) : lam(m.kind === "existing" ? C.existing : C.ground); const mesh = new T.Mesh(g, mat); mesh.receiveShadow = true; mesh.castShadow = m.kind === "existing"; if (m.kind === "terrain") mesh.userData.ground = true; mesh.userData.kind = m.kind; gMeshes.push(mesh); group.add(mesh);
      if (m.kind === "existing") { const e = new T.LineSegments(new T.EdgesGeometry(g, 25), new T.LineBasicMaterial({ color: C.edge, transparent: true, opacity: C.edgeA })); group.add(e); } });
    B.forEach(b => { const g = geom(b, true); if (!g) return; const mesh = new T.Mesh(g, lam(parseInt(css("--plan").slice(1), 16) || 0x4c6fa3)); mesh.castShadow = mesh.receiveShadow = true; mesh.userData.b = b; group.add(mesh); bMeshes.push(mesh);
      const e = new T.LineSegments(new T.EdgesGeometry(g, 20), new T.LineBasicMaterial({ color: C.edge, transparent: true, opacity: C.edgeA })); group.add(e); });
    if (SM.curves.length) { const mat = new T.LineBasicMaterial({ color: C.path, transparent: true, opacity: 0.7 }); SM.curves.forEach(c => { const pts = c.map(p => new T.Vector3(p[0], p[1] + 0.15, p[2])); group.add(new T.Line(new T.BufferGeometry().setFromPoints(pts), mat)); }); }
    treeGroup = new T.Group(); group.add(treeGroup);
    if (SM.trees.length) { const n = SM.trees.length; const trunk = new T.InstancedMesh(new T.CylinderGeometry(0.16, 0.26, 1, 7), lam(C.trunk), n); const crown = new T.InstancedMesh(new T.SphereGeometry(1, 10, 8), lam(C.crown), n); const o = new T.Object3D();
      SM.trees.forEach((t, i) => { const [x, y, z, h, r] = t; const cr = Math.max(0.8, Math.min(r, h * 0.45)); const cz = Math.max(cr, h - cr); o.position.set(x, y + cz / 2, z); o.scale.set(1, cz, 1); o.rotation.set(0, 0, 0); o.updateMatrix(); trunk.setMatrixAt(i, o.matrix); o.position.set(x, y + cz, z); o.scale.set(cr, cr * 1.15, cr); o.updateMatrix(); crown.setMatrixAt(i, o.matrix); });
      trunk.castShadow = crown.castShadow = true; crown.receiveShadow = true; treeGroup.add(trunk); treeGroup.add(crown); }
    treeGroup.visible = $("smTrees").checked; scene.background = new T.Color(C.bg); if (hemi) { hemi.groundColor = new T.Color(C.hemiGround); hemi.intensity = C.hemiI; } colour(); render(); }
  function colour() { const mk = css("--marker"), pl = css("--plan"); bMeshes.forEach(m => m.material.color.set(m.userData.b === sel ? mk : pl)); }

  function render() { if (!gl) return; const w = view.clientWidth, h = view.clientHeight; if (!w || !h) return; if (canvas.width !== Math.round(w * renderer.getPixelRatio()) || canvas.height !== Math.round(h * renderer.getPixelRatio())) renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    if (standing) { camera.position.set(standing.pos[0], standing.pos[1], standing.pos[2]); camera.lookAt(standing.pos[0] + Math.sin(standing.az) * 50, standing.pos[1] - 3, standing.pos[2] - Math.cos(standing.az) * 50); }
    else { const R = span * 1.1 * orbit.r; const c = new T.Vector3(centre[0] + orbit.pan[0], centre[1], centre[2] + orbit.pan[1]); camera.position.set(c.x + R * Math.sin(orbit.ph) * Math.cos(orbit.th), c.y + R * Math.cos(orbit.ph), c.z + R * Math.sin(orbit.ph) * Math.sin(orbit.th)); camera.lookAt(c); }
    if (sun) { const az = +$("smAz").value * Math.PI / 180, alt = +$("smAlt").value * Math.PI / 180; const D = span * 2.2; const cx = centre[0], cz = centre[2]; sun.position.set(cx + D * Math.cos(alt) * Math.sin(az), centre[1] + D * Math.sin(alt), cz - D * Math.cos(alt) * Math.cos(az)); sun.target.position.set(cx, centre[1], cz); sun.intensity = 0.35 + 0.5 * Math.sin(alt); }
    renderer.render(scene, camera); labels(); renderHooks.forEach(fn => { try { fn(); } catch (e) { console.error("[ek] model onRender", e); } }); }
  /* world point → pixels in the view; on = in front of the camera and inside the frame (the labels' own test) */
  function project(p) { if (!gl) return null; const v = Array.isArray(p) ? new T.Vector3(p[0], p[1], p[2]) : p.clone(); v.project(camera); return { x: (v.x + 1) / 2 * view.clientWidth, y: (1 - v.y) / 2 * view.clientHeight, on: v.z <= 1 && Math.abs(v.x) <= 1.05 && Math.abs(v.y) <= 1.05 }; }
  function labels() { lblBox.textContent = ""; if (!gl || !$("smLabelsOn").checked) return; const w = view.clientWidth, h = view.clientHeight; const v = new T.Vector3();
    B.forEach(b => { v.set(b.center[0], b.bbox[4] + 1.2, b.center[2]).project(camera); if (v.z > 1 || Math.abs(v.x) > 1.05 || Math.abs(v.y) > 1.05) return; const s = document.createElement("span"); s.className = "sm-lbl" + (b === sel ? " sel" : ""); s.style.left = ((v.x + 1) / 2 * w).toFixed(0) + "px"; s.style.top = ((1 - v.y) / 2 * h).toFixed(0) + "px"; const i = document.createElement("i"); s.appendChild(i); s.appendChild(document.createTextNode(b.label)); lblBox.appendChild(s); }); }

  if (gl) {
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio)); renderer.shadowMap.enabled = true; renderer.shadowMap.type = T.PCFSoftShadowMap;
    scene = new T.Scene(); camera = new T.PerspectiveCamera(36, 1, 0.5, span * 12);
    hemi = new T.HemisphereLight(0xffffff, 0x9aa1ab, 0.5); scene.add(hemi);
    sun = new T.DirectionalLight(0xfff8ee, 0.9); sun.castShadow = true; sun.shadow.mapSize.set(2048, 2048); sun.shadow.bias = -0.0008; const sc = sun.shadow.camera; sc.left = sc.bottom = -span * 0.75; sc.right = sc.top = span * 0.75; sc.near = 1; sc.far = span * 6; scene.add(sun); scene.add(sun.target);
    build();
    matchMedia("(prefers-color-scheme: dark)").addEventListener("change", build);
    ["smAz", "smAlt"].forEach(id => $(id).addEventListener("input", () => { $("smAzV").textContent = $("smAz").value + "\\u00b0"; $("smAltV").textContent = $("smAlt").value + "\\u00b0"; render(); }));
    $("smShadows").addEventListener("change", () => { renderer.shadowMap.enabled = $("smShadows").checked; build(); });
    $("smTrees").addEventListener("change", () => { treeGroup.visible = $("smTrees").checked; render(); });
    $("smLabelsOn").addEventListener("change", render);

    /* pointer: orbit, pan (right / shift / two fingers), pinch, tap to pick */
    let od = null; const ptrs = new Map(); let pinchD = 0;
    canvas.addEventListener("contextmenu", e => e.preventDefault());
    canvas.addEventListener("pointerdown", e => { try { canvas.setPointerCapture(e.pointerId); } catch (err) {} ptrs.set(e.pointerId, [e.clientX, e.clientY]); od = { x: e.clientX, y: e.clientY, btn: e.button, shift: e.shiftKey, moved: 0 }; if (ptrs.size === 2) { const p = [...ptrs.values()]; pinchD = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]); } canvas.focus({ preventScroll: true }); });
    canvas.addEventListener("pointermove", e => { if (!ptrs.has(e.pointerId)) return; ptrs.set(e.pointerId, [e.clientX, e.clientY]); if (!od) return;
      if (ptrs.size === 2) { const p = [...ptrs.values()]; const dd = Math.hypot(p[0][0] - p[1][0], p[0][1] - p[1][1]); if (pinchD) orbit.r = Math.max(0.15, Math.min(4, orbit.r * pinchD / dd)); pinchD = dd; const mid = [(p[0][0] + p[1][0]) / 2, (p[0][1] + p[1][1]) / 2]; pan(mid[0] - od.x, mid[1] - od.y); od = { x: mid[0], y: mid[1], btn: 0, moved: 99 }; render(); return; }
      const dx = e.clientX - od.x, dy = e.clientY - od.y; od.moved += Math.abs(dx) + Math.abs(dy);
      if (standing) { standing.az -= dx * 0.005; } else if (od.btn === 2 || od.shift || e.buttons === 4) pan(dx, dy); else { orbit.th -= dx * 0.008; orbit.ph = Math.max(0.12, Math.min(1.52, orbit.ph - dy * 0.006)); }
      od.x = e.clientX; od.y = e.clientY; render(); });
    function pan(dx, dy) { if (standing) return; const k = span * 0.0025 * orbit.r; orbit.pan[0] += -dx * k * Math.sin(orbit.th) + dy * k * Math.cos(orbit.th); orbit.pan[1] += dx * k * Math.cos(orbit.th) + dy * k * Math.sin(orbit.th); }
    const endPtr = e => { ptrs.delete(e.pointerId); if (od && od.moved < 6 && ptrs.size === 0 && od.btn === 0) pick(e); if (ptrs.size === 0) od = null; pinchD = 0; };
    canvas.addEventListener("pointerup", endPtr); canvas.addEventListener("pointercancel", endPtr);
    canvas.addEventListener("wheel", e => { if (document.activeElement !== canvas) return; e.preventDefault(); if (standing) return; orbit.r = Math.max(0.15, Math.min(4, orbit.r * (1 + e.deltaY * 0.001))); render(); }, { passive: false });
    canvas.addEventListener("dblclick", () => overview());
    canvas.addEventListener("keydown", e => { const k = e.key; if (k === "ArrowLeft") orbit.th += .1; else if (k === "ArrowRight") orbit.th -= .1; else if (k === "ArrowUp") orbit.ph = Math.max(0.12, orbit.ph - .08); else if (k === "ArrowDown") orbit.ph = Math.min(1.52, orbit.ph + .08); else if (k === "+" || k === "=") orbit.r *= .9; else if (k === "-") orbit.r *= 1.1; else if (k === "0") { overview(); return; } else return; e.preventDefault(); if (standing && (k === "ArrowLeft" || k === "ArrowRight")) standing.az += k === "ArrowLeft" ? -0.15 : 0.15; render(); });
    const ray = new T.Raycaster(), ndc = new T.Vector2();
    function pick(e) { const r = canvas.getBoundingClientRect(); ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1); ray.setFromCamera(ndc, camera); const hit = ray.intersectObjects(bMeshes)[0];
      /* extensions see the first surface the ray meets (buildings, terrain, water, existing); one returning true has handled the tap */
      if (pickHooks.length) { const s = ray.intersectObjects(bMeshes.concat(gMeshes))[0]; const h = s ? { point: [s.point.x, s.point.y, s.point.z], distance: s.distance, building: s.object.userData.b || null, kind: s.object.userData.b ? "building" : (s.object.userData.kind || "terrain"), object: s.object } : null;
        for (const fn of pickHooks) { try { if (fn(h, ray, e)) return; } catch (err) { console.error("[ek] model onPick", err); } } }
      select(hit ? hit.object.userData.b : null); }
    window.addEventListener("resize", render);
    if ("ResizeObserver" in window) new ResizeObserver(render).observe(view);
  }

  /* ---- selection, votes, notes ---- */
  const chips = [...$("smChips").querySelectorAll(".sm-chip")];
  let prevSel = null;
  function select(b, keepView) { prevSel = sel; sel = b; chips.forEach(c => c.setAttribute("aria-pressed", String(!!b && c.dataset.b === b.label))); $("smSel").hidden = !b; $("smNone").hidden = !!b; colour();
    /* once a building is chosen the card is only about it: the about-text and the chips fold away (phones have 240 px of card) */
    $("smAbout").hidden = !!b; $("smChips").hidden = !!b; if (!b) card.scrollTop = 0;
    /* one way to react at a time: the augment row (pins) belongs to the overview, the votes to a chosen building */
    $("smSlot").hidden = !!b;
    if (b) { $("smName").textContent = b.label; const v = b.view; $("smMeta").textContent = (v ? "The presentation gives this building a view of " + bearingWord(v.bearing) + (v.slide ? " (slide " + v.slide + ")" : "") + "." : "The presentation gives no view bearing for this building; Stand here looks south.") + " Drag the model to look at it from every side.";
      if (EK.current() === "model") EK.context("model", b.label, "\\u2014 does its spot work, and why?"); }
    else { if (EK.current() === "model") EK.context("model", "the model", "\\u2014 tap a building to react to it"); }
    renderMine(); if (gl) render(); }
  const bearingWord = d => { const w = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"][Math.round(d / 45) % 8]; return w + " (" + Math.round(d) + "\\u00b0)"; };
  chips.forEach(c => c.addEventListener("click", () => { const b = byLabel(c.dataset.b); select(sel === b ? null : b); if (b && gl && !standing) flyTo(b); }));
  function flyTo(b) { orbit.pan = [b.center[0] - centre[0], b.center[2] - centre[2]]; orbit.r = Math.max(0.2, Math.min(orbit.r, 0.45)); render(); }
  function overview() { standing = null; orbit = HOME(); $("smBack").hidden = true; $("smStand").hidden = false; render(); }
  $("smOverview").addEventListener("click", overview); $("smAll").addEventListener("click", () => { select(null); if (standing) overview(); });
  /* eye level: just outside the facade on the bearing side, 1.6 m above the building's floor, looking along the bearing */
  /* with no building: the model's centre, 1.6 m above the terrain there (ray straight down), else the lowest floor */
  function groundY(x, z) { const low = B.length ? Math.min.apply(null, B.map(b => b.bbox[1])) : bbox.min[1]; if (!gl) return low;
    const rc = new T.Raycaster(new T.Vector3(x, bbox.max[1] + 50, z), new T.Vector3(0, -1, 0)); const s = rc.intersectObjects(gMeshes.filter(m => m.userData.kind !== "existing"))[0]; return s ? s.point.y : low; }
  function standFor(b, deg) { if (!gl) return false; const d = deg != null ? ((deg % 360) + 360) % 360 : (b && b.view ? b.view.bearing : 180); const az = d * Math.PI / 180; const dx = Math.sin(az), dz = -Math.cos(az);
    if (b) { const half = Math.max(Math.abs(b.bbox[3] - b.bbox[0]), Math.abs(b.bbox[5] - b.bbox[2])) / 2; const out = half + 2.5; standing = { pos: [b.center[0] + dx * out, b.bbox[1] + 1.6, b.center[2] + dz * out], az }; }
    else standing = { pos: [centre[0], groundY(centre[0], centre[2]) + 1.6, centre[2]], az };
    $("smBack").hidden = false; $("smStand").hidden = true; render();
    EK.toast((b ? "Standing just outside " + b.label + ", 1.6 m above its floor" : "Standing in the middle of the site, at eye level") + ", looking " + bearingWord(d).split(" (")[0] + ". Drag to look around."); return true; }
  $("smStand").addEventListener("click", () => { if (sel) standFor(sel); });
  /* for links from other sections (a view in the story, say): switch to the model first; the stage sizes on ek:show,
     and one more frame after a short timeout catches a layout that settles late */
  function goModel(fn) { if (EK.current() !== "model") EK.show("model"); const r = fn(); setTimeout(() => { if (gl) render(); }, 80); return r; }
  const findB = l => l == null ? null : byLabel(String(l)) || B.find(b => b.label.toLowerCase() === String(l).trim().toLowerCase()) || null;
  $("smBack").addEventListener("click", overview);
  $("smSay").addEventListener("click", () => { if (!sel) return; EK.context("model", sel.label, "\\u2014 why does its spot work, or where should it go?"); EK.focusNote(); EK.toast(hasVoice() ? "Speak or type below" : "Type below"); });
  $("smSel").querySelectorAll(".sm-vote").forEach(btn => btn.addEventListener("click", () => { if (!sel) return; const t = sel.label, v = btn.dataset.v, had = voteOf(t); const old = mine().filter(r => r.kind === "vote" && r.target === t);
    if (had === v) { old.forEach(r => EK.remove(r.id)); EK.toast("Choice removed"); return; }
    const rec = EK.react({ feature: "model", target: t, kind: "vote", value: v }); if (!rec) { EK.toast("Could not save on this phone (storage full?)"); return; } old.forEach(r => EK.remove(r.id)); EK.toast(v === "keep" ? "The spot works \\u2014 saved on this phone" : "It should move \\u2014 saved on this phone"); }));
  function renderMine() { const box = $("smMem"), chip = $("smCount"); box.textContent = ""; if (!sel) { chip.hidden = true; return; } const t = sel.label; const v = voteOf(t); $("smSel").querySelectorAll(".sm-vote").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
    const notes = mine().filter(r => r.target === t && r.kind !== "vote");
    notes.forEach(r => { const d = document.createElement("div"); d.setAttribute("role", "listitem");
      if (r.kind === "voice" && r.value && typeof r.value.mime === "string" && /^audio\\/[\\w.+-]+$/.test(r.value.mime) && typeof r.value.base64 === "string" && /^[A-Za-z0-9+\\/=]+$/.test(r.value.base64)) { const a = document.createElement("audio"); a.controls = true; a.src = "data:" + r.value.mime + ";base64," + r.value.base64; d.appendChild(a); const s = document.createElement("small"); s.textContent = (r.value.seconds || "?") + " s, voice"; d.appendChild(s); }
      else if (r.kind === "voice") d.textContent = "Unsupported voice note"; else d.textContent = typeof r.value === "string" ? r.value : "Unsupported note"; box.appendChild(d); });
    chip.hidden = !notes.length; chip.textContent = notes.length + (notes.length === 1 ? " note" : " notes") + " on this device";
    chips.forEach(c => { const cv = voteOf(c.dataset.b); c.setAttribute("aria-label", c.dataset.b + (cv ? (cv === "keep" ? ", you said the spot works" : ", you said it should move") : "")); }); }
  EK.on("ek:reaction", renderMine);

  /* ---- sizing: phones get a fixed-pixel view per show, desktop a side card ---- */
  let viewW = 0;
  function layoutView(force) { if (window.innerWidth >= 900) view.style.height = ""; else if (force || window.innerWidth !== viewW) { viewW = window.innerWidth; const h = stageEl.clientHeight; view.style.height = Math.round(h * (h < 520 ? 0.5 : 0.56)) + "px"; } if (gl) render(); }
  EK.fitStage(stageEl, "model", { onResize: () => layoutView(false) });
  EK.on("ek:show", id => { if (id === "model") { layoutView(true); if (gl) render(); select(sel, true); } });
  layoutView(true); if (EK.current() === "model") select(null);

  EK.feature = EK.feature || {}; EK.feature.model = { buildings: B, select: l => select(byLabel(l)), selected: () => sel, overview, fallback: !gl, render: () => render(), rebuild: () => build(), renderer: gl ? renderer : null, camera: gl ? camera : null, canvas, view,
    /* extension point (ek-model-pins): the scene survives rebuilds (only the model group is replaced), ground() is the
       current terrain / water / existing meshes, onPick(fn(hit|null, raycaster, event)) runs before the default select,
       onRender(fn) after every frame, project([x,y,z]) gives view pixels, bbox/span are the model's extent in metres */
    scene: gl ? scene : null, ground: () => gMeshes.slice(), onPick: fn => { if (typeof fn === "function") pickHooks.push(fn); }, onRender: fn => { if (typeof fn === "function") renderHooks.push(fn); }, project, bbox: { min: bbox.min.slice(), max: bbox.max.slice() }, span,
    /* stand(label): select that building and Stand here on its own bearing; standAt(deg, label?): stand at that building
       (or the model's centre) looking along deg from north. Both show the model section first; true when the camera moved */
    stand: l => goModel(() => { const b = findB(l); if (!b) return false; select(b); return standFor(b); }),
    standAt: (deg, l) => goModel(() => { const d = Number(deg); const b = findB(l); if (!isFinite(d) || (l != null && !b)) return false; select(b); return standFor(b, d); }) };

  /* ---- tour ---- */
  const first = B[0];
  EK.registerTour([
    { go: "model", do: () => { overview(); if (gl) { orbit.th = -0.9; render(); } }, text: "The model: the site as the design team has it today, with the sun where you put it. Drag to turn it, pinch to zoom." },
    { go: "model", do: () => { if (first) { select(first); if (gl) flyTo(first); } }, undo: () => select(prevSel && prevSel !== first ? prevSel : null), text: first ? "Tap a building to pick it out. " + first.label + ": say whether its spot works, and why." : "No proposed buildings are in the model yet." },
    { go: "model", do: () => { if (first) { select(first); $("smStand").click(); } }, undo: () => overview(), text: first ? "Stand here puts you at its floor, looking out the way the presentation says it faces. Drag to look around." : "" }
  ].filter(s => s.text));
})();
</script>"""


def splice(doc: str, section: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="model">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script[^>]*data-feature="model"[^>]*>.*?</script>', "", doc, flags=re.S)
    sec_re = re.compile(r'<section data-feature="model"[^>]*>.*?</section>', re.S)
    if not sec_re.search(doc):
        raise SystemExit("no <section data-feature=\"model\"> slot in the output; is ek-site-model installed in the manifest and the shell built?")
    doc = sec_re.sub(lambda m: section, doc, count=1)
    for marker in ("<!-- ek:styles -->", "<!-- ek:scripts -->"):
        if marker not in doc:
            raise SystemExit(f"shell marker {marker} missing from the output")
    doc = doc.replace("<!-- ek:styles -->", "<!-- ek:styles -->\n" + style, 1)
    # three.js once per page, as one shared tag right after the scripts marker that no feature's cleanup removes;
    # every three.js feature's script goes after that tag, whatever order the skills were run in
    if THREE_TAG not in doc:
        doc = doc.replace("<!-- ek:scripts -->", "<!-- ek:scripts -->\n" + THREE_TAG, 1)
    doc = doc.replace(THREE_TAG, THREE_TAG + "\n" + script, 1)
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", type=Path, default=Path("work/brief.json"))
    ap.add_argument("--model", default="model.json", help="viewer JSON from export_3dm.py, relative to --root")
    ap.add_argument("--out", type=Path, default=Path("output/index.html"))
    ap.add_argument("--root", type=Path, default=Path("."))
    args = ap.parse_args(argv)
    for p in (args.brief, args.out):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    doc = args.out.read_text(encoding="utf-8")
    warnings: list[str] = []
    model = load_model(args.model, args.root, warnings)
    if model is None:
        for w in warnings:
            log(f"warning: {w}")
        sys.exit("no model to build from; run export_3dm.py first")
    data = model_data(model, brief, warnings)
    if not data["meshes"] and not data["buildings"]:
        sys.exit("the model has no drawable meshes")
    new_doc = splice(doc, section_html(data, brief), STYLE, SCRIPT.replace("%(data)s", json_inline(data), 1))
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "meshes": [m["kind"] for m in data["meshes"]],
                      "buildings": [b["label"] for b in data["buildings"]], "with_view": sum(1 for b in data["buildings"] if b["view"]),
                      "trees": len(data["trees"]), "curves": len(data["curves"]), "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
