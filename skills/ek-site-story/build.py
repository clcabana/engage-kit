#!/usr/bin/env python3
"""
ek-site-story — write "the site" section into an ek-shell output.

  python skills/ek-site-story/build.py --brief work/brief.json --out output/index.html [--root .]

Reads brief.places (undated places on the site: name, text, image, source_slide), replaces the shell's
<section data-feature="places"> slot, and inserts one <style data-feature="places"> at <!-- ek:styles -->
and one <script data-feature="places"> at <!-- ek:scripts -->. Idempotent. One full-bleed scene per place,
the deck's own photograph behind a floating caption, one question: what here must stay as it is?
Images are embedded as data: URIs and shown through <img>. Brief strings are data: HTML-escaped into
markup, JSON-encoded (</ neutralised) into the inline PL object; visitor text is rendered with textContent.
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

FEATURE = "places"
MAX_PLACES = 10
MAX_TEXT = 400
IMG_MAX_W = 1400
IMG_BUDGET = 2_000_000
SAFE_IMAGE_TYPES = {"image/svg+xml", "image/png", "image/jpeg", "image/webp", "image/gif"}


def log(msg: str) -> None:
    print(f"[ek-site-story] {msg}", file=sys.stderr)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


# --------------------------------------------------------------------------- images (same rules as ek-timeline)

SVG_UNSAFE = re.compile(
    r"<script|<foreignObject|<!ENTITY|<\?xml-stylesheet|on[a-z]+\s*=|javascript:|"
    r"(?:xlink:)?href\s*=\s*[\"']?\s*(?:https?:|//|data:text)|url\(\s*[\"']?\s*(?:https?:|//)", re.I)


def embed_image(rel: str, root: Path, warnings: list[str]) -> str:
    """Return a data: URI for an image named in the brief, or '' if it is missing, unsafe or outside --root."""
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
            has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
            if im.width > IMG_MAX_W:
                im.thumbnail((IMG_MAX_W, IMG_MAX_W * 4))
            buf = BytesIO()
            if has_alpha and len(data) <= 400_000:
                im.save(buf, "PNG", optimize=True)
                data, mime = buf.getvalue(), "image/png"
            else:
                im.convert("RGB").save(buf, "JPEG", quality=82, optimize=True)
                data, mime = buf.getvalue(), "image/jpeg"
        except ImportError:
            warnings.append(f"{path.name}: Pillow is not installed; embedded as-is (EXIF not stripped, not downscaled)")
        except Exception as e:
            warnings.append(f"image not embedded ({type(e).__name__}): {path.name}")
            return ""
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


# --------------------------------------------------------------------------- content

def places_from_brief(brief: dict, root: Path, warnings: list[str]) -> list[dict]:
    out = []
    for i, p in enumerate(brief.get("places") or []):
        if not isinstance(p, dict):
            continue
        name = str(p.get("name") or "").strip()[:60]
        if not name:
            warnings.append(f"places[{i}] has no name; skipped")
            continue
        text = str(p.get("text") or "").strip()
        if len(text) > MAX_TEXT:
            warnings.append(f"places[{i}] ({name}) text cut at {MAX_TEXT} characters")
            text = text[:MAX_TEXT].rstrip() + "…"
        slide = p.get("source_slide")
        if isinstance(slide, bool) or slide is None or slide == "":
            slide = None
            warnings.append(f"places[{i}] ({name}) has no source_slide; the claim is not traceable")
        elif isinstance(slide, (int, float)) and math.isfinite(slide):
            slide = int(slide)
        else:
            slide = str(slide)[:20]
        img = str(p.get("image") or "").strip()
        src = ""
        people = bool(p.get("people"))
        if img:
            if people and p.get("cleared") is not True:
                # A photograph that shows a person is not embedded until the team sets cleared: true (exactly true;
                # "pending", "no", 1 do not count). A public URL is forever. Checked before any filesystem access.
                warnings.append(f"places[{i}] ({name}) image shows a person and is not marked cleared: true; not embedded")
            else:
                src = embed_image(img, root, warnings)
                if src.startswith("data:image/svg+xml"):
                    warnings.append(f"places[{i}] ({name}) image is an SVG drawing, not a photograph; the section says 'pictures', never 'photographs', but check it reads honestly")
        out.append({"name": name, "text": text, "slide": slide, "img": src, "target": name, "people_embedded": bool(src) and people})
    names = [p["name"].lower() for p in out]
    if len(set(names)) != len(names):
        warnings.append("duplicate place names; reactions target by name, so make them unique")
    if len(out) > MAX_PLACES:
        warnings.append(f"{len(out)} places; only the first {MAX_PLACES} are shown (a longer walk loses the visitor)")
        out = out[:MAX_PLACES]
    return out


BEARING_WORDS = ["north", "north-east", "east", "south-east", "south", "south-west", "west", "north-west"]
MAX_VIEWS = 8


def bearing_word(deg: float) -> str:
    """Same 45-degree sectors as ek-site-model's bearingWord."""
    return BEARING_WORDS[round(deg / 45) % 8]


def views_from_brief(brief: dict, warnings: list[str]) -> list[dict]:
    """brief.site.views[]: {building, bearing_deg, source_slide} -> buttons that open the model at that view."""
    site = brief.get("site") if isinstance(brief.get("site"), dict) else {}
    out = []
    for i, v in enumerate(site.get("views") or []):
        if not isinstance(v, dict):
            continue
        name = str(v.get("building") or "").strip()[:60]
        deg = v.get("bearing_deg")
        if not name or isinstance(deg, bool) or not isinstance(deg, (int, float)) or not math.isfinite(deg):
            warnings.append(f"site.views[{i}] needs a building and a numeric bearing_deg; skipped")
            continue
        deg = round(float(deg)) % 360
        slide = v.get("source_slide")
        if slide is None or slide == "" or isinstance(slide, bool):
            warnings.append(f"site.views[{i}] ({name}) has no source_slide; the claim is not traceable")
            slide = None
        out.append({"building": name, "deg": deg, "word": bearing_word(deg), "slide": slide})
    if len(out) > MAX_VIEWS:
        warnings.append(f"{len(out)} site views; only the first {MAX_VIEWS} are shown")
        out = out[:MAX_VIEWS]
    return out


def views_html(views: list[dict]) -> str:
    if not views:
        return ""
    parts = []
    for v in views:
        title = f' title="From the presentation, slide {html.escape(str(v["slide"]))}"' if v["slide"] is not None else ""
        parts.append(f'<button type="button" class="pl-view" data-building="{html.escape(v["building"])}" data-bearing="{v["deg"]}"{title}>'
                     f'{html.escape(v["building"])} · {v["word"]} ({v["deg"]}°)</button>')
    btns = "".join(parts)
    return (f'  <div class="pl-views-wrap"><div class="kicker" id="plViewsK">Views the presentation gives, from the model</div>\n'
            f'  <div class="pl-views" id="plViews" role="group" aria-labelledby="plViewsK">{btns}</div></div>\n')


COPY_DEFAULT = {
    "nav": "The site",
    "heading": "The site as it is",
    "lede": "A walk through the places on the site, in the design team's own pictures. For each one, say whether it must stay as it is, and {v} why.",
    "question": "Must this stay as it is?",
    "keep": "Keep it as it is",
    "change": "It could change",
    "said_keep": "keep it",
    "said_change": "it could change",
    "why": "why must it stay, or what could change?",
    "noun": "place",
    "nouns": "places",
    "tour_vote": "For each place, say whether it must stay as it is. One tap; tap again to take it back.",
    "tour_intro": "",   # empty: the script's own sentence ("<nav>: N <nouns> in the design team's own pictures. …")
}
COPY_MAX = {"nav": 24, "lede": 300, "tour_vote": 200, "tour_intro": 200, "noun": 20, "nouns": 20}


def story_copy(brief: dict, warnings: list[str]) -> dict:
    """brief.places_story (optional): the section's wording, for a story that is not 'the site as it is' (for
    example the proposal's own views shown to a client). Every key is optional; a missing or unusable one keeps
    the default. The recorded values stay 'keep' / 'change' whatever the buttons say. Plain text only: every
    string is escaped on the way into the markup and travels to the script as JSON."""
    copy = dict(COPY_DEFAULT)
    raw = brief.get("places_story")
    if raw is None:
        return copy
    if not isinstance(raw, dict):
        warnings.append("places_story is not an object; default wording kept")
        return copy
    for k in COPY_DEFAULT:
        if k not in raw:
            continue
        v = raw[k]
        cap = COPY_MAX.get(k, 80)
        if not isinstance(v, str) or not v.strip():
            warnings.append(f"places_story.{k} is not a non-empty string; default kept")
            continue
        v = " ".join(v.split())
        if len(v) > cap:
            warnings.append(f"places_story.{k} cut at {cap} characters")
            v = v[:cap].rstrip()
        copy[k] = v
    for said, label in (("said_keep", "keep"), ("said_change", "change")):
        if label in raw and said not in raw:
            copy[said] = copy[label] if re.match(r"I\b", copy[label]) else copy[label][0].lower() + copy[label][1:]   # "I'd change something" keeps its I
    for k in raw:
        if k not in COPY_DEFAULT and k != "note":
            warnings.append(f"places_story.{k} is not a known key; ignored")
    return copy


def section_html(places: list[dict], views: list[dict] | None = None, copy: dict | None = None) -> str:
    c = copy or COPY_DEFAULT
    n = len(places)
    scenes = []
    for i, p in enumerate(places):
        img = (f'<img class="pl-img" src="{p["img"]}" alt="" loading="lazy" decoding="async">' if p["img"]
               else '<div class="pl-img pl-noimg" aria-hidden="true"></div>')
        slide_txt = ("slide " + str(p["slide"])) if p["slide"] is not None else "slide not recorded"
        text = f'<p>{html.escape(p["text"])}</p>' if p["text"] else ""
        scenes.append(
            f'    <article class="pl-scene" data-i="{i}" data-target="{html.escape(p["target"])}" data-slide="{html.escape(slide_txt)}" aria-label="{html.escape(p["name"])}, {i + 1} of {n}">\n'
            f'      {img}\n'
            f'      <div class="pl-cap">\n'
            f'        <span class="pl-name">{html.escape(p["name"])}</span>\n'
            f'        {text}\n'
            f'        <small class="pl-src">From the presentation, {html.escape(slide_txt)}</small>\n'
            f'        <div class="pl-q">{html.escape(c["question"])}</div>\n'
            f'        <div class="row pl-votes" role="group" aria-label="{html.escape(p["name"])}: {html.escape(c["question"][0].lower() + c["question"][1:])}"><button type="button" class="pl-vote" data-v="keep" aria-pressed="false">{html.escape(c["keep"])}</button><button type="button" class="pl-vote" data-v="change" aria-pressed="false">{html.escape(c["change"])}</button></div>\n'
            f'        <div class="row"><button type="button" class="primary pl-say">Say why</button><span class="chip pl-count" hidden><b>0</b> <span class="pl-cn">notes</span> on this device</span></div>\n'
            f'        <div class="pl-mem" role="list" aria-label="Your notes on {html.escape(p["name"])}"></div>\n'
            f'      </div>\n'
            f'    </article>'
        )
    rail = "".join(f'<button type="button" data-i="{i}" aria-label="{html.escape(p["name"])}"><span>{html.escape(p["name"])}</span></button>' for i, p in enumerate(places))
    lede_v = lambda v: html.escape(c["lede"].replace("{v}", v))   # replace, not format: the wording may come from the brief
    nouns_cap = c["nouns"][0].upper() + c["nouns"][1:]
    return (
        f'<section data-feature="places" data-title="{html.escape(c["nav"])}" hidden>\n'
        f'  <h2>{html.escape(c["heading"])}</h2>\n'
        f'  <p class="lede" data-with-voice="{lede_v("speak or type")}" data-without-voice="{lede_v("type")}">{lede_v("type")}</p>\n'
        + views_html(views or []) +
        f'  <div class="pl-wrap ek-bleed">\n'
        f'  <div class="pl ek-stage" id="pl" tabindex="0" role="region" aria-roledescription="scrolling story" aria-label="{html.escape(c["nav"])}, {n} {html.escape(c["nouns"])}. Use the arrow keys to move between them.">\n'
        + "\n".join(scenes) + "\n"
        f'  </div>\n'
        f'  <nav class="pl-rail" id="plRail" aria-label="{html.escape(nouns_cap)}">{rail}</nav>\n'
        f'  </div>\n'
        f'</section>'
    )


STYLE = """<style data-feature="places">
/* ===== ek-site-story: undated places as a scroll-driven story ===== */
.pl-wrap{position:relative}
.pl{position:relative;overflow-y:auto;overscroll-behavior:contain;scroll-snap-type:y mandatory;background:var(--soft);outline:none;scrollbar-width:none}
.pl::-webkit-scrollbar{display:none}
.pl:focus-visible{outline:3px solid var(--marker);outline-offset:-3px}
.pl-scene{position:relative;height:100%;scroll-snap-align:start;scroll-snap-stop:always;display:flex;align-items:flex-end;padding:16px 16px 20px;overflow:hidden}
@media(min-width:900px){.pl-scene{padding:28px 32px 32px}}
.pl-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;background:var(--soft)}
.pl-noimg{background:linear-gradient(160deg,var(--soft),var(--card))}
.pl-scene::after{content:"";position:absolute;inset:auto 0 0 0;height:60%;background:linear-gradient(to top,rgba(0,0,0,.42),transparent);pointer-events:none}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]) .pl-scene::after{background:linear-gradient(to top,rgba(0,0,0,.6),transparent)}}
/* the picture gets the top half on a phone: the card is capped at 52% of the stage and scrolls inside itself */
.pl-cap{position:relative;z-index:1;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:var(--radius,6px);padding:14px 16px;max-width:440px;width:100%;display:flex;flex-direction:column;gap:8px;box-shadow:var(--float);margin-right:56px;max-height:52%;overflow:auto;overscroll-behavior:contain}
@media(min-width:600px){.pl-cap{margin-right:96px;max-height:calc(100% - 8px)}}
@media(min-width:900px){.pl-cap{margin-right:140px;padding:16px 18px}}
.pl-name{font-size:28px;font-weight:500;line-height:1.05;letter-spacing:-.01em}
.pl-cap p{max-width:52ch;margin:0} .pl-cap small{color:var(--mute);font-size:14px}
@media(max-width:599px){.pl-cap p{font-size:15px} .pl-src{font-size:13px}}
.pl-q{font-weight:500;margin-top:2px}
.pl-votes{gap:6px} .pl-vote{min-height:44px;padding:8px 12px;border:1px solid var(--line);border-radius:22px;background:var(--paper);color:var(--ink);font-size:14px;display:inline-flex;align-items:center;gap:6px}
.pl-vote::before{content:"";width:12px;height:12px;border-radius:6px;border:2px solid var(--mute);flex:0 0 auto}
.pl-vote[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)} .pl-vote[aria-pressed=true]::before{background:var(--marker);border-color:var(--marker)}
.pl-vote:focus-visible{outline:3px solid var(--marker);outline-offset:2px}
.pl-count[hidden]{display:none} .pl-count{gap:4px}
.pl-mem{display:grid;gap:6px;max-height:22vh;overflow:auto} .pl-mem:empty{display:none}
.pl-mem div{padding:8px 10px;border-left:3px solid var(--marker);background:var(--soft);border-radius:0 6px 6px 0;font-size:15px;overflow-wrap:anywhere}
.pl-mem audio{width:100%;max-width:320px;height:36px;display:block}
.pl-rail{position:absolute;right:8px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;align-items:flex-end;padding:6px 4px;z-index:2;background:rgba(20,20,18,.72);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);border-radius:22px}
.pl-rail button{min-height:44px;min-width:44px;padding:0 8px;border:none;border-radius:22px;background:transparent;color:#F7F6F2;display:flex;align-items:center;justify-content:flex-end;gap:8px;font-size:13px;line-height:1}
.pl-rail button:hover{background:rgba(255,255,255,.12)}
.pl-rail button::after{content:"";flex:0 0 auto;width:10px;height:10px;border-radius:5px;background:#F7F6F2;opacity:.7}
.pl-rail button span{display:none;white-space:nowrap}
.pl-rail button[aria-current="true"]::after{opacity:1;background:var(--marker);transform:scale(1.3)}
/* phones: dots only (the caption already carries the name); labels from 600 px */
@media(min-width:600px){.pl-rail button:hover span,.pl-rail button[aria-current="true"] span,.pl-rail button:focus-visible span{display:inline}}
.pl-rail button[aria-current="true"] span{font-weight:500}
.pl-rail button:focus-visible{outline:3px solid var(--marker);outline-offset:-3px}
@media(min-width:900px){.pl-rail{right:16px} .pl-rail button span{display:inline;opacity:.8} .pl-rail button[aria-current="true"] span{opacity:1}}
/* views from the brief: a chip row above the story; one line that scrolls sideways on a phone, wraps from 600 px */
.pl-views-wrap{display:grid;gap:6px;margin:0 0 12px;min-width:0;max-width:100%}
.pl-views{display:flex;gap:8px;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:none;min-width:0;max-width:100%;padding:2px 0}
.pl-views::-webkit-scrollbar{display:none}
@media(min-width:600px){.pl-views{flex-wrap:wrap;overflow:visible}}
.pl-view{flex:0 0 auto;min-height:44px;padding:8px 14px;border:1px solid var(--line);border-radius:22px;background:var(--card);color:var(--ink);font-size:14px;white-space:nowrap}
.pl-view:hover{border-color:var(--ink)} .pl-view:focus-visible{outline:3px solid var(--marker);outline-offset:2px}
@media(prefers-reduced-motion:reduce){.pl{scroll-snap-type:none;scroll-behavior:auto} .pl-rail button[aria-current="true"]::after{transform:none}}
</style>"""


SCRIPT = """<script data-feature="places">
(function siteStory() {
  const PL = %(data)s;  /* the count and the section's wording (plain text; shown with textContent / toasts only) */
  const C = PL.copy;
  const root = document.getElementById("pl"), rail = document.getElementById("plRail");
  if (!root || !rail) return;
  const scenes = [...root.querySelectorAll(".pl-scene")], dots = [...rail.querySelectorAll("button")];
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let active = 0, armed = false;
  const target = i => scenes[i] ? scenes[i].dataset.target : "";
  const slideOf = i => scenes[i] ? scenes[i].dataset.slide || "" : "";
  const hasVoice = () => EK.hasKind && EK.hasKind("voice");
  const mine = () => EK.reactions().filter(r => r.feature === "places");
  const voteOf = t => { const v = mine().filter(r => r.kind === "vote" && r.target === t && (r.value === "keep" || r.value === "change")).pop(); return v ? v.value : ""; };

  const stage = EK.fitStage(root, "places", { onResize: () => { if (scenes[active]) root.scrollTo({ top: scenes[active].offsetTop, behavior: "auto" }); } });
  const settle = () => stage.settle();

  function setActive(i, fromScroll) { if (i === active && armed) return; active = i; armed = true;
    dots.forEach((d, k) => k === i ? d.setAttribute("aria-current", "true") : d.removeAttribute("aria-current"));
    if (EK.current() === "places") EK.context("places", target(i), "\\u2014 " + slideOf(i) + (i < scenes.length - 1 ? " \\u00b7 scroll for the next " + C.noun : " \\u00b7 the last " + C.noun)); }
  function go(i, focus) { i = Math.max(0, Math.min(scenes.length - 1, i)); root.scrollTo({ top: scenes[i].offsetTop, behavior: reduced ? "auto" : "smooth" }); setActive(i); settle(); if (focus) root.focus({ preventScroll: true }); }
  root.addEventListener("scroll", () => { if (!root._settled) { root._settled = true; settle(); } }, { passive: true });

  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(es => { es.forEach(e => { if (e.isIntersecting && e.intersectionRatio >= 0.55) setActive(+e.target.dataset.i, true); }); }, { root, threshold: [0.55] });
    scenes.forEach(s => io.observe(s));
  } else { root.addEventListener("scroll", () => setActive(Math.round(root.scrollTop / root.clientHeight), true), { passive: true }); }

  dots.forEach(d => d.addEventListener("click", () => go(+d.dataset.i, true)));
  root.addEventListener("keydown", e => { const k = e.key; if (e.target !== root) return; if (k === "ArrowDown" || k === "PageDown" || k === " ") { e.preventDefault(); go(active + 1); } else if (k === "ArrowUp" || k === "PageUp") { e.preventDefault(); go(active - 1); } else if (k === "Home") { e.preventDefault(); go(0); } else if (k === "End") { e.preventDefault(); go(scenes.length - 1); } });

  /* keep / change: one choice per place per device; tapping the chosen one again removes it */
  scenes.forEach((s, i) => {
    s.querySelectorAll(".pl-vote").forEach(b => b.addEventListener("click", () => { const t = target(i), v = b.dataset.v, had = voteOf(t);
      const old = mine().filter(r => r.kind === "vote" && r.target === t);
      if (had === v) { old.forEach(r => EK.remove(r.id)); EK.toast("Choice removed"); return; }
      /* record the new choice first; the old one is removed only once the new one is stored */
      const rec = EK.react({ feature: "places", target: t, kind: "vote", value: v });
      if (!rec) { EK.toast("Could not save on this phone (storage full?)"); return; }
      old.forEach(r => EK.remove(r.id));
      EK.toast((v === "keep" ? C.keep : C.change) + " \\u2014 saved on this phone"); }));
    const say = s.querySelector(".pl-say"); say.addEventListener("click", () => { setActive(i); EK.context("places", target(i), "\\u2014 " + slideOf(i) + " \\u00b7 " + C.why); EK.focusNote(); EK.toast(hasVoice() ? "Speak or type below" : "Type below"); }); });

  function render() { const R = mine();
    scenes.forEach((s, i) => { const t = target(i); const notes = R.filter(r => r.target === t && r.kind !== "vote"), v = voteOf(t); const box = s.querySelector(".pl-mem"), chip = s.querySelector(".pl-count");
      s.querySelectorAll(".pl-vote").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
      box.textContent = "";
      notes.forEach(r => { const d = document.createElement("div"); d.setAttribute("role", "listitem");
        if (r.kind === "voice" && r.value && typeof r.value.mime === "string" && /^audio\\/[\\w.+-]+$/.test(r.value.mime) && typeof r.value.base64 === "string" && /^[A-Za-z0-9+\\/=]+$/.test(r.value.base64)) { const a = document.createElement("audio"); a.controls = true; a.src = "data:" + r.value.mime + ";base64," + r.value.base64; d.appendChild(a); const sm = document.createElement("small"); sm.textContent = (r.value.seconds || "?") + " s, voice"; d.appendChild(sm); }
        else if (r.kind === "voice") d.textContent = "Unsupported voice note";
        else if (r.value && typeof r.value.text === "string") { d.textContent = r.value.text; const sp = document.createElement("small"); sp.textContent = r.value.via === "voice" ? " (spoken)" : ""; d.appendChild(sp); } else d.textContent = typeof r.value === "string" ? r.value : "Unsupported note";
        box.appendChild(d); });
      chip.hidden = !notes.length; chip.querySelector("b").textContent = notes.length; chip.querySelector(".pl-cn").textContent = notes.length === 1 ? "note" : "notes";
      if (dots[i]) dots[i].setAttribute("aria-label", t + (v ? ", you said " + (v === "keep" ? C.said_keep : C.said_change) : "") + (notes.length ? ", " + notes.length + " note" + (notes.length === 1 ? "" : "s") + " on this device" : "")); }); }
  EK.on("ek:reaction", render); render();

  /* views the presentation gives: open the model there. EK.feature.model.stand / standAt are looked up at click time */
  const viewRow = document.getElementById("plViews");
  if (viewRow) {
    const base = s => String(s || "").replace(/\\s*\\([^)]*\\)\\s*$/, "").trim().toLowerCase();
    viewRow.querySelectorAll(".pl-view").forEach(b => b.addEventListener("click", () => {
      const M = window.EK && EK.feature && EK.feature.model;
      if (!M || typeof M.stand !== "function") { EK.toast("The model is not in this tool"); return; }
      const name = b.dataset.building || "", deg = Number(b.dataset.bearing);
      const labels = (Array.isArray(M.buildings) ? M.buildings : []).map(x => x && x.label).filter(l => typeof l === "string");
      const hit = labels.find(l => l === name) || labels.find(l => l.toLowerCase() === name.toLowerCase()) || labels.find(l => base(l) === base(name));
      try {
        if (hit) { M.stand(hit); return; }
        if (typeof M.standAt !== "function" || !isFinite(deg)) { EK.toast("The model is not in this tool"); return; }
        M.standAt(deg); EK.toast(name + " is not in the model yet; looking that way from the site\\u2019s centre");   /* no label: the model stands at its centre */
      } catch (err) { EK.toast("The model could not open that view"); }
    }));
  }

  EK.on("ek:show", id => { if (id === "places") { armed = false; setActive(active); root._settled = false; } });
  if (EK.current() === "places") setActive(0);

  /* the demo tap never touches a choice the visitor already made: with one in place the step only shows the control */
  let tourDemo = false;
  EK.registerTour([
    { go: "places", do: () => go(0), text: C.tour_intro || (C.nav + ": " + PL.count + " " + C.nouns + " in the design team\\u2019s own pictures. Scroll, or use the dots, to walk through.") },
    { go: "places", do: () => { const b = scenes[0] && scenes[0].querySelector('.pl-vote[data-v="keep"]'); if (!b) return; if (voteOf(target(0))) { tourDemo = false; b.focus(); return; } tourDemo = true; b.click(); }, undo: () => { if (!tourDemo) return; tourDemo = false; mine().filter(r => r.kind === "vote" && r.target === target(0)).forEach(r => EK.remove(r.id)); }, text: C.tour_vote },
    { go: "places", do: () => { const b = scenes[0] && scenes[0].querySelector(".pl-say"); if (b) b.focus(); }, text: "Then say why. Your note is tied to that " + C.noun + (PL.demo ? " and stays on this phone; this is a demonstration, so nobody collects it." : " and stays on this phone until the team collects it.") }
  ]);
})();
</script>"""


def splice(doc: str, section: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="places">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="places">.*?</script>', "", doc, flags=re.S)
    sec_re = re.compile(r'<section data-feature="places"[^>]*>.*?</section>', re.S)
    if not sec_re.search(doc):
        raise SystemExit("no <section data-feature=\"places\"> slot in the output; is ek-site-story installed in the manifest and the shell built?")
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
    ap.add_argument("--root", type=Path, default=Path("."), help="where places[].image paths are resolved from")
    args = ap.parse_args(argv)
    for p in (args.brief, args.out):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    doc = args.out.read_text(encoding="utf-8")
    warnings: list[str] = []
    places = places_from_brief(brief, args.root, warnings)
    if not places:
        sys.exit("brief.places has no usable places; ek-project-manifest should not have installed ek-site-story")
    views = views_from_brief(brief, warnings)
    copy = story_copy(brief, warnings)
    data = {"count": len(places), "demo": brief.get("demo") is True,
            "copy": {k: copy[k] for k in ("nav", "keep", "change", "said_keep", "said_change", "why", "noun", "nouns", "tour_vote", "tour_intro")}}
    new_doc = splice(doc, section_html(places, views, copy), STYLE, SCRIPT.replace("%(data)s", json_inline(data), 1))
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    img_bytes = sum(len(p["img"]) for p in places)
    if img_bytes > IMG_BUDGET:
        warnings.append(f"embedded images total {img_bytes // 1024} KB; consider smaller photographs")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "places": len(places), "views": len(views),
                      "images_embedded": sum(1 for p in places if p["img"]), "image_bytes": img_bytes,
                      "people_embedded": [p["name"] for p in places if p["people_embedded"]],
                      "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
