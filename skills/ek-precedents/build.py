#!/usr/bin/env python3
"""
ek-precedents — write the "Inspiration" section into an ek-shell output.

  python skills/ek-precedents/build.py --brief work/brief.json --out output/index.html [--root .]

Reads brief.precedents (other people's buildings the design team looked at: name, by, image, source_slide,
credit, people, cleared; an image is embedded only when people is false or cleared is true),
replaces the shell's <section data-feature="precedents"> slot, and inserts one <style data-feature="precedents">
at <!-- ek:styles --> and one <script data-feature="precedents"> at <!-- ek:scripts -->. Idempotent.
A swipeable gallery on phones (one card per screen, dot rail), a grid from 900 px. Per card: feels right for
us / not for us, say why, and a top-3 ranking across the gallery.
Images are embedded as data: URIs and shown through <img>. Brief strings are data: HTML-escaped into
markup, JSON-encoded (</ neutralised) into the inline PC object; visitor text is rendered with textContent.

Reaction shapes (both kind 'vote'; renderers check the value type):
  choice:  {feature:'precedents', target:<name>, kind:'vote', value:'right'|'not'}
  ranking: {feature:'precedents', target:<name>, kind:'vote', value:{rank:1|2|3}}
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

FEATURE = "precedents"
MAX_ITEMS = 12
RANK_MAX = 3
IMG_MAX_W = 1200
IMG_BUDGET = 2_000_000
SAFE_IMAGE_TYPES = {"image/svg+xml", "image/png", "image/jpeg", "image/webp", "image/gif"}
NOTE = "These are other people\u2019s buildings the design team looked at. They are not the project."


def log(msg: str) -> None:
    print(f"[ek-precedents] {msg}", file=sys.stderr)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


# --------------------------------------------------------------------------- images (same rules as ek-site-story)

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
                im.convert("RGB").save(buf, "JPEG", quality=80, optimize=True)
                data, mime = buf.getvalue(), "image/jpeg"
        except ImportError:
            warnings.append(f"{path.name}: Pillow is not installed; embedded as-is (EXIF not stripped, not downscaled)")
        except Exception as e:
            warnings.append(f"image not embedded ({type(e).__name__}): {path.name}")
            return ""
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


# --------------------------------------------------------------------------- content

def precedents_from_brief(brief: dict, root: Path, warnings: list[str]) -> list[dict]:
    raw = [p for p in (brief.get("precedents") or []) if isinstance(p, dict)]
    sample = brief.get("sample") is True
    if len(raw) > MAX_ITEMS:
        warnings.append(f"{len(raw)} precedents; only the first {MAX_ITEMS} are shown (a longer gallery cannot be ranked)")
        raw = raw[:MAX_ITEMS]
    out = []
    for i, p in enumerate(raw):
        name = str(p.get("name") or "").strip()[:80]
        if not name:
            warnings.append(f"precedents[{i}] has no name; skipped")
            continue
        by = str(p.get("by") or "").strip()[:80]
        if not by:
            warnings.append(f"precedents[{i}] ({name}) has no 'by'; the card says the architect is not recorded. Credit the author.")
        slide = p.get("source_slide")
        if isinstance(slide, bool) or slide is None or slide == "":
            slide = None
            warnings.append(f"precedents[{i}] ({name}) has no source_slide; the claim is not traceable")
        elif isinstance(slide, (int, float)) and math.isfinite(slide):
            slide = int(slide)
        else:
            slide = str(slide)[:20]
        img = str(p.get("image") or "").strip()
        src = ""
        people = p.get("people")
        cleared = p.get("cleared") is True
        credit = str(p.get("credit") or "").strip()[:120]
        if img:
            # embed only after someone has looked: people exactly False, or cleared exactly True
            if people is False or cleared:
                src = embed_image(img, root, warnings)
                if src.startswith("data:image/svg+xml"):
                    warnings.append(f"precedents[{i}] ({name}) image is an SVG drawing; the section says these are other people's buildings, check that reads honestly")
            elif people is True:
                warnings.append(f"precedents[{i}] ({name}) image shows a person and is not marked cleared: true; not embedded")
            else:
                warnings.append(f"precedents[{i}] ({name}) image not embedded: nobody has recorded whether it shows people. "
                                "The team must look at it and set people: false, or cleared: true")
            if not credit and not sample:
                warnings.append(f"precedents[{i}] ({name}) has no credit (photographer / source); copyright: credit required")
        else:
            warnings.append(f"precedents[{i}] ({name}) has no image")
        out.append({"name": name, "by": by, "slide": slide, "img": src, "credit": credit,
                    "people_embedded": bool(src) and people is not False})
    names = [p["name"].lower() for p in out]
    if len(set(names)) != len(names):
        warnings.append("duplicate precedent names; reactions target by name, so make them unique")
    return out


def section_html(items: list[dict]) -> str:
    n = len(items)
    top = min(RANK_MAX, n)
    e = html.escape
    cards = []
    for i, p in enumerate(items):
        slide_txt = ("slide " + str(p["slide"])) if p["slide"] is not None else "slide not recorded"
        by = ("by " + p["by"]) if p["by"] else "Architect not recorded"
        alt = p["name"] + (", " + by if p["by"] else "")
        img = (f'<img class="pc-img" src="{p["img"]}" alt="{e(alt)}" loading="lazy" decoding="async">' if p["img"]
               else '<div class="pc-img pc-noimg" aria-hidden="true"></div>')
        credit = f'        <span class="pc-credit">Photo: {e(p["credit"])}</span>\n' if p["credit"] else ""
        cards.append(
            f'    <li class="pc-card" data-i="{i}" data-target="{e(p["name"])}" data-slide="{e(slide_txt)}" tabindex="0" aria-label="{e(p["name"])}, {e(by)}, {i + 1} of {n}">\n'
            f'      <div class="pc-frame">{img}<span class="pc-rank" hidden></span></div>\n'
            f'      <div class="pc-body">\n'
            f'        <span class="kicker">Reference \u00b7 {e(slide_txt)}</span>\n'
            f'        <span class="pc-name">{e(p["name"])}</span>\n'
            f'        <span class="pc-by">{e(by)}</span>\n'
            + credit +
            f'        <div class="row pc-votes" role="group" aria-label="{e(p["name"])}: does this feel right for us?"><button type="button" class="pc-vote" data-v="right" aria-pressed="false">Feels right for us</button><button type="button" class="pc-vote" data-v="not" aria-pressed="false">Not for us</button></div>\n'
            f'        <div class="row"><button type="button" class="primary pc-say">Say why</button><span class="chip pc-count" hidden><b>0</b> <span class="pc-cn">notes</span> on this device</span></div>\n'
            f'        <div class="pc-mem" role="list" aria-label="Your notes on {e(p["name"])}"></div>\n'
            f'      </div>\n'
            f'    </li>'
        )
    dots = "".join(f'<button type="button" data-i="{i}" aria-label="{e(p["name"])}"></button>' for i, p in enumerate(items))
    lede = "Swipe through, say which feel right for this place and which do not, {v} why, and rank your favourites."
    return (
        f'<section data-feature="precedents" data-title="Inspiration" hidden>\n'
        f'  <h2>What the team looked at</h2>\n'
        f'  <p class="lede" data-with-voice="{e(lede.format(v="say or type"))}" data-without-voice="{e(lede.format(v="type"))}">{e(lede.format(v="type"))}</p>\n'
        f'  <p class="pc-note">{e(NOTE)}</p>\n'
        f'  <div class="pc-wrap ek-bleed">\n'
        f'  <ul class="pc-track" id="pcTrack" role="list" aria-label="References, {n} buildings. Use the arrow keys to move between them; Enter to say why.">\n'
        + "\n".join(cards) + "\n"
        f'  </ul>\n'
        f'  <nav class="pc-dots" id="pcDots" aria-label="References">{dots}</nav>\n'
        f'  </div>\n'
        f'  <div class="pc-other" hidden><span class="kicker">Your notes on your ranking</span><div class="pc-mem" role="list" aria-label="Your notes on your ranking"></div></div>\n'
        f'  <div class="row pc-rankrow"><button type="button" class="primary pc-rankbtn">Rank my favourites</button><span class="chip pc-ranked" hidden></span></div>\n'
        f'  <div class="pc-rankbox" hidden>\n'
        f'    <span class="kicker">Your favourites</span>\n'
        f'    <span class="pc-sub">Tap up to {top}, favourite first</span>\n'
        f'    <div class="pc-picks" role="group" aria-label="References to rank"></div>\n'
        f'    <div class="row"><button type="button" class="primary pc-save" disabled>Save my top {top}</button><button type="button" class="pc-cancel">Back</button></div>\n'
        f'  </div>\n'
        f'</section>'
    )


STYLE = """<style data-feature="precedents">
/* ===== ek-precedents: other people's buildings as references; swipe on phones, grid from 900 px ===== */
.pc-note{color:var(--mute);font-size:14px;margin:0 0 12px}
.pc-wrap{position:relative}
.pc-track{position:relative;list-style:none;margin:0;padding:4px 16px 8px;display:flex;gap:12px;overflow-x:auto;overscroll-behavior-x:contain;scroll-snap-type:x mandatory;scroll-padding:0 16px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.pc-track::-webkit-scrollbar{display:none}
.pc-card{flex:0 0 100%;scroll-snap-align:center;scroll-snap-stop:always;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:var(--radius,6px);overflow:hidden;box-shadow:var(--float,none);display:flex;flex-direction:column;min-width:0;outline:none}
.pc-card:focus-visible{outline:3px solid var(--marker);outline-offset:2px}
.pc-frame{position:relative;aspect-ratio:4/3;background:var(--soft);overflow:hidden}
.pc-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block}
.pc-noimg{background:linear-gradient(160deg,var(--soft),var(--card))}
.pc-rank{position:absolute;top:10px;left:10px;display:inline-grid;place-items:center;min-width:34px;height:28px;padding:0 10px;border-radius:999px;background:var(--marker);color:var(--on-marker);font-size:13px;font-weight:500}
.pc-rank[hidden],.pc-count[hidden],.pc-ranked[hidden],.pc-rankbox[hidden],.pc-rankrow[hidden],.pc-other[hidden]{display:none}
.pc-body{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;min-width:0}
.pc-name{font-size:20px;font-weight:500;line-height:1.15;letter-spacing:-.01em;overflow-wrap:anywhere}
.pc-by{color:var(--mute);font-size:15px;overflow-wrap:anywhere}
.pc-credit{color:var(--mute);font-size:14px;overflow-wrap:anywhere}
.pc-votes{gap:6px;margin-top:4px} .pc-vote{min-height:44px;padding:8px 12px;border:1px solid var(--line);border-radius:999px;background:var(--paper);color:var(--ink);font-size:14px;display:inline-flex;align-items:center;gap:6px}
.pc-vote::before{content:"";width:12px;height:12px;border-radius:50%;border:2px solid var(--mute);flex:0 0 auto}
.pc-vote[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)} .pc-vote[aria-pressed=true]::before{background:var(--marker);border-color:var(--marker)}
.pc-vote:focus-visible{outline:3px solid var(--marker);outline-offset:2px}
.pc-count{gap:4px} .pc-count b{font-weight:500}
.pc-mem{display:grid;gap:6px} .pc-mem:empty{display:none}
.pc-mem div{padding:8px 10px;border-left:3px solid var(--marker);background:var(--soft);border-radius:0 var(--radius,6px) var(--radius,6px) 0;font-size:15px;overflow-wrap:anywhere}
.pc-mem audio{width:100%;max-width:320px;height:36px;display:block}
.pc-dots{display:flex;justify-content:center;gap:2px;padding:2px 16px 0;flex-wrap:wrap}
.pc-dots button{min-width:32px;min-height:44px;padding:0;border:none;background:transparent;display:grid;place-items:center;border-radius:999px}
.pc-dots button::after{content:"";width:8px;height:8px;border-radius:50%;background:var(--mute);opacity:.5}
.pc-dots button[aria-current="true"]::after{opacity:1;background:var(--marker);transform:scale(1.35)}
.pc-dots button:focus-visible{outline:3px solid var(--marker);outline-offset:-6px}
.pc-other{margin-top:12px;display:flex;flex-direction:column;gap:6px}
.pc-rankrow{margin-top:14px}
.pc-rankbox{margin-top:12px;background:var(--card);border:1px solid var(--line);border-radius:var(--radius,6px);padding:14px 16px;display:flex;flex-direction:column;gap:8px;box-shadow:var(--float,none)}
.pc-sub{font-size:18px;font-weight:500}
.pc-picks{display:flex;flex-wrap:wrap;gap:6px} .pc-picks button{min-height:44px;padding:6px 10px;font-size:14px;display:inline-flex;align-items:center;gap:6px;text-align:left}
.pc-picks button b{display:inline-grid;place-items:center;min-width:22px;height:22px;border-radius:999px;background:var(--marker);color:var(--on-marker);font-size:12px;font-weight:500}
.pc-picks button[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)} .pc-picks button[aria-pressed=true] b{background:var(--paper);color:var(--ink)}
@media(min-width:600px) and (max-width:899px){.pc-card{flex-basis:calc(70% - 6px)}}
@media(min-width:900px){
  .pc-wrap.ek-bleed{margin:0;width:auto}
  .pc-track{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;overflow:visible;padding:4px 0 8px;scroll-snap-type:none}
  .pc-dots{display:none}
}
@media(prefers-reduced-motion:reduce){.pc-track{scroll-behavior:auto} .pc-dots button[aria-current="true"]::after{transform:none}}
</style>"""


SCRIPT = """<script data-feature="precedents">
(function precedents() {
  const PC = %(data)s;  /* counts only */
  const sec = document.querySelector('section[data-feature="precedents"]');
  const track = document.getElementById("pcTrack"), dotsEl = document.getElementById("pcDots");
  if (!sec || !track || !dotsEl) return;
  const cards = [...track.querySelectorAll(".pc-card")], dots = [...dotsEl.querySelectorAll("button")];
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const grid = matchMedia("(min-width: 900px)");
  const hasVoice = () => EK.hasKind && EK.hasKind("voice");
  const target = i => cards[i] ? cards[i].dataset.target : "";
  const slideOf = i => cards[i] ? cards[i].dataset.slide || "" : "";
  const names = cards.map(c => c.dataset.target);
  const RANKS = "ranking: inspiration";
  const mine = () => EK.reactions().filter(r => r.feature === "precedents");
  /* two shapes of kind 'vote': a string choice ('right'|'not') and an object ranking ({rank:n}) */
  const isChoice = r => r.kind === "vote" && (r.value === "right" || r.value === "not");
  const isRank = r => r.kind === "vote" && r.value && typeof r.value === "object" && Number.isInteger(r.value.rank) && r.value.rank >= 1 && r.value.rank <= PC.top;
  const choiceOf = t => { const v = mine().filter(r => r.target === t && isChoice(r)).pop(); return v ? v.value : ""; };
  const rankOf = t => { const v = mine().filter(r => r.target === t && isRank(r)).pop(); return v ? v.value.rank : 0; };
  let active = 0;

  /* gallery: one card per screen on phones (scroll-snap inside the track), grid from 900 px */
  function setActive(i) { active = i; dots.forEach((d, k) => k === i ? d.setAttribute("aria-current", "true") : d.removeAttribute("aria-current"));
    if (EK.current() === "precedents") EK.context("precedents", target(i), "\\u2014 " + slideOf(i) + (grid.matches ? "" : (i < cards.length - 1 ? " \\u00b7 swipe for the next" : " \\u00b7 the last one"))); }
  function go(i, focus) { i = Math.max(0, Math.min(cards.length - 1, i)); const c = cards[i];
    if (!grid.matches) track.scrollTo({ left: c.offsetLeft - (track.clientWidth - c.clientWidth) / 2, behavior: reduced ? "auto" : "smooth" });
    setActive(i); if (focus) c.focus({ preventScroll: !grid.matches }); }
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(es => { if (grid.matches) return; es.forEach(e => { if (e.isIntersecting && e.intersectionRatio >= 0.6) setActive(+e.target.dataset.i); }); }, { root: track, threshold: [0.6] });
    cards.forEach(c => io.observe(c));
  } else { track.addEventListener("scroll", () => { if (!grid.matches && cards[0]) setActive(Math.round(track.scrollLeft / (cards[0].clientWidth + 12))); }, { passive: true }); }
  dots.forEach(d => d.addEventListener("click", () => go(+d.dataset.i, true)));

  function say(i) { setActive(i); EK.context("precedents", target(i), "\\u2014 what about it feels right, or not?"); EK.focusNote(); EK.toast(hasVoice() ? "Speak or type below" : "Type below"); }
  cards.forEach((c, i) => {
    c.addEventListener("focus", () => { if (active !== i || grid.matches) setActive(i); });
    c.addEventListener("keydown", e => { if (e.target !== c) return; const k = e.key;
      if (k === "ArrowRight" || k === "ArrowDown") { e.preventDefault(); go(i + 1, true); }
      else if (k === "ArrowLeft" || k === "ArrowUp") { e.preventDefault(); go(i - 1, true); }
      else if (k === "Home") { e.preventDefault(); go(0, true); } else if (k === "End") { e.preventDefault(); go(cards.length - 1, true); }
      else if (k === "Enter") { e.preventDefault(); say(i); } });
    /* feels right / not for us: one choice per reference per device; tapping the chosen one again removes it */
    c.querySelectorAll(".pc-vote").forEach(b => b.addEventListener("click", () => { const t = target(i), v = b.dataset.v, had = choiceOf(t);
      const old = mine().filter(r => r.target === t && isChoice(r));
      if (had === v) { old.forEach(r => EK.remove(r.id)); EK.toast("Choice removed"); return; }
      /* the new choice is stored first; the old one goes only once the new one is kept */
      /* the visitor's own tap: tour:false, so it stays even if they tap during the tour */
      const rec = EK.react({ feature: "precedents", target: t, kind: "vote", value: v, tour: false });
      if (!rec) { EK.toast("Could not save on this phone (storage full?)"); return; }
      old.forEach(r => EK.remove(r.id));
      EK.toast((v === "right" ? "Feels right for us" : "Not for us") + " \\u2014 saved on this phone"); }));
    c.querySelector(".pc-say").addEventListener("click", () => say(i)); });

  function renderNotes(box, rs) { box.textContent = "";
    rs.forEach(r => { const d = document.createElement("div"); d.setAttribute("role", "listitem");
      if (r.kind === "voice" && r.value && typeof r.value.mime === "string" && /^audio\\/[\\w.+-]+$/.test(r.value.mime) && typeof r.value.base64 === "string" && /^[A-Za-z0-9+\\/=]+$/.test(r.value.base64)) { const a = document.createElement("audio"); a.controls = true; a.src = "data:" + r.value.mime + ";base64," + r.value.base64; d.appendChild(a); const s = document.createElement("small"); s.textContent = (r.value.seconds || "?") + " s, voice"; d.appendChild(s); }
      else if (r.kind === "voice") d.textContent = "Unsupported voice note";
      else d.textContent = typeof r.value === "string" ? r.value : "Unsupported note";
      box.appendChild(d); }); }

  const rankedBtn = sec.querySelector(".pc-ranked"), other = sec.querySelector(".pc-other");
  function render() { const R = mine();
    cards.forEach((c, i) => { const t = target(i), v = choiceOf(t), rk = rankOf(t); const notes = R.filter(r => r.target === t && r.kind !== "vote");
      c.querySelectorAll(".pc-vote").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.v === v)));
      renderNotes(c.querySelector(".pc-mem"), notes);
      const chip = c.querySelector(".pc-count"); chip.hidden = !notes.length; chip.querySelector("b").textContent = notes.length; chip.querySelector(".pc-cn").textContent = notes.length === 1 ? "note" : "notes";
      const badge = c.querySelector(".pc-rank"); badge.hidden = !rk; badge.textContent = rk ? "#" + rk : ""; badge.setAttribute("aria-label", rk ? "your favourite number " + rk : "");
      const lab = t + (v ? (v === "right" ? ", you said it feels right" : ", you said not for us") : "") + (rk ? ", your number " + rk : "") + (notes.length ? ", " + notes.length + " note" + (notes.length === 1 ? "" : "s") + " on this device" : "");
      if (dots[i]) dots[i].setAttribute("aria-label", lab); });
    const n = names.filter(rankOf).length; rankedBtn.hidden = !n; rankedBtn.textContent = n ? "You ranked " + n + " (this phone)" : "";
    const on = R.filter(r => r.kind !== "vote" && r.target === RANKS); renderNotes(other.querySelector(".pc-mem"), on); other.hidden = !on.length; }
  EK.on("ek:reaction", render); render();

  /* ranking: top 3, each kept as {kind:'vote', value:{rank:n}} on the reference it names */
  const btn = sec.querySelector(".pc-rankbtn"), box = sec.querySelector(".pc-rankbox"), picksEl = sec.querySelector(".pc-picks"), save = sec.querySelector(".pc-save"), cancel = sec.querySelector(".pc-cancel"), row = sec.querySelector(".pc-rankrow");
  let picks = [];
  function drawPicks() { picksEl.textContent = ""; names.forEach(n => { const b = document.createElement("button"); b.type = "button"; const i = picks.indexOf(n); b.setAttribute("aria-pressed", String(i >= 0)); const tag = document.createElement("b"); tag.textContent = i >= 0 ? String(i + 1) : "+"; b.appendChild(tag); b.appendChild(document.createTextNode(n)); b.setAttribute("aria-label", n + (i >= 0 ? ", ranked " + (i + 1) : ", not ranked"));
    b.addEventListener("click", () => { const k = picks.indexOf(n); if (k >= 0) picks.splice(k, 1); else if (picks.length < PC.top) picks.push(n); else { EK.toast(PC.top + " chosen \\u2014 remove one first"); return; } drawPicks(); const nb = picksEl.querySelectorAll("button")[names.indexOf(n)]; if (nb) nb.focus(); }); picksEl.appendChild(b); });
    save.disabled = !picks.length; save.textContent = "Save my top " + (picks.length || PC.top); }
  function openRank() { picks = names.map(n => ({ n, r: rankOf(n) })).filter(x => x.r).sort((a, b) => a.r - b.r).map(x => x.n).slice(0, PC.top); drawPicks(); row.hidden = true; box.hidden = false; const f = picksEl.querySelector("button"); if (f) f.focus(); EK.context("precedents", RANKS, "\\u2014 tap your favourites in order", "your favourites"); }
  function closeRank(focus) { box.hidden = true; row.hidden = false; if (focus) btn.focus(); setActive(active); }
  btn.addEventListener("click", openRank);
  cancel.addEventListener("click", () => closeRank(true));
  save.addEventListener("click", () => { const old = mine().filter(isRank); const made = [];
    for (const [i, n] of picks.entries()) { const rec = EK.react({ feature: "precedents", target: n, kind: "vote", value: { rank: i + 1 }, tour: false }); if (!rec) { made.forEach(r => EK.remove(r.id)); EK.toast("Could not save on this phone (storage full?); your earlier ranking is kept"); return; } made.push(rec); }
    old.forEach(r => EK.remove(r.id)); EK.toast("Favourites saved on this phone"); closeRank(true); });

  EK.on("ek:show", id => { if (id === "precedents") setActive(active); });
  if (EK.current() === "precedents") setActive(0);

  /* tour: the demo vote is recorded directly as a tour:true record (removed by the shell when the tour exits, and
     by undo here); it never touches a choice the visitor already made. A step whose delayed do() lands after
     the tour has moved on (EK.current() is no longer this section) does nothing */
  let tourRec = null;
  function tourVote() { if (EK.current() !== "precedents" || !cards[0]) return;
    if (tourRec && !EK.reactions().some(r => r.id === tourRec.id)) tourRec = null;  /* the shell already removed it */
    const b = cards[0].querySelector('.pc-vote[data-v="right"]');
    if (tourRec || choiceOf(target(0))) { if (b) b.focus(); return; }
    tourRec = EK.react({ feature: "precedents", target: target(0), kind: "vote", value: "right", tour: true }); if (b) b.focus(); }
  function tourUnvote() { if (!tourRec) return; const id = tourRec.id; tourRec = null; if (EK.reactions().some(r => r.id === id)) EK.remove(id); }
  EK.registerTour([
    { go: "precedents", do: () => { if (EK.current() === "precedents") go(0); }, text: "Inspiration: " + PC.count + " buildings by other architects that the design team looked at. They are not the project. Swipe, or use the dots, to see each one." },
    { go: "precedents", do: tourVote, undo: tourUnvote, text: "For each one, say whether it feels right for this place or not. One tap; tap again to take it back. Then say why." },
    { go: "precedents", do: () => { if (EK.current() === "precedents") openRank(); }, undo: () => closeRank(false), text: "Then rank your top " + PC.top + ": tap them in order and save. Everything stays on this phone until the team collects it." }
  ]);
})();
</script>"""


def splice(doc: str, section: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="precedents">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="precedents">.*?</script>', "", doc, flags=re.S)
    sec_re = re.compile(r'<section data-feature="precedents"[^>]*>.*?</section>', re.S)
    if not sec_re.search(doc):
        raise SystemExit("no <section data-feature=\"precedents\"> slot in the output; is ek-precedents installed in the manifest and the shell built?")
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
    ap.add_argument("--root", type=Path, default=Path("."), help="where precedents[].image paths are resolved from")
    args = ap.parse_args(argv)
    for p in (args.brief, args.out):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    doc = args.out.read_text(encoding="utf-8")
    warnings: list[str] = []
    items = precedents_from_brief(brief, args.root, warnings)
    if not items:
        sys.exit("brief.precedents has no usable entries; ek-project-manifest should not have installed ek-precedents")
    data = {"count": len(items), "top": min(RANK_MAX, len(items))}
    new_doc = splice(doc, section_html(items), STYLE, SCRIPT.replace("%(data)s", json_inline(data), 1))
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    img_bytes = sum(len(p["img"]) for p in items)
    if img_bytes > IMG_BUDGET:
        warnings.append(f"embedded images total {img_bytes // 1024} KB (over {IMG_BUDGET // 1_000_000} MB); consider smaller photographs")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "precedents": len(items),
                      "images_embedded": sum(1 for p in items if p["img"]), "image_bytes": img_bytes,
                      "people_embedded": [p["name"] for p in items if p["people_embedded"]],
                      "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
