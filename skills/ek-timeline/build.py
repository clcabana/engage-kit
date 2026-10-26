#!/usr/bin/env python3
"""
ek-timeline — write the history section into an ek-shell output.

  python skills/ek-timeline/build.py --brief work/brief.json --out output/index.html [--root .]

Reads brief.history, replaces the shell's <section data-feature="timeline"> slot, and inserts one
<style data-feature="timeline"> at <!-- ek:styles --> and one <script data-feature="timeline"> at
<!-- ek:scripts -->. Idempotent. Images are embedded as data: URIs and displayed through <img>.
Brief strings are data: HTML-escaped into markup, JSON-encoded (</ neutralised) into the inline TL object;
the script renders them with textContent / esc().
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import mimetypes
import re
import sys
from io import BytesIO
from pathlib import Path

FEATURE = "timeline"
MAX_EVENTS = 12
IMG_MAX_W = 1400
IMG_BUDGET = 1_500_000  # bytes of embedded images before we warn
SAFE_IMAGE_TYPES = {"image/svg+xml", "image/png", "image/jpeg", "image/webp", "image/gif"}


def log(msg: str) -> None:
    print(f"[ek-timeline] {msg}", file=sys.stderr)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


# --------------------------------------------------------------------------- images

SVG_UNSAFE = re.compile(
    r"<script|<foreignObject|<!ENTITY|<\?xml-stylesheet|on[a-z]+\s*=|javascript:|"
    r"(?:xlink:)?href\s*=\s*[\"']?\s*(?:https?:|//|data:text)|url\(\s*[\"']?\s*(?:https?:|//)", re.I)


def embed_image(rel: str, root: Path, warnings: list[str]) -> str:
    """Return a data: URI for an image named in the brief, or '' if it is missing, unsafe or outside --root.

    The path comes from the brief (deck → model → JSON), so it is untrusted: it must resolve inside --root,
    or a hostile deck could have the build publish any image file from the design team's machine.
    """
    root_r = root.resolve()
    try:
        path = (root / rel).resolve()
    except (OSError, ValueError):
        warnings.append(f"image path not usable: {rel!r}")
        return ""
    if rel.startswith(("\\\\", "//")) or (path != root_r and root_r not in path.parents):
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
        text = data.decode("utf-8", "replace")
        # Shown through <img>, so script cannot run; still refuse SVGs that try, and ones that fetch remote content,
        # because a later feature may inline "the project's own SVGs" where these would be live.
        if SVG_UNSAFE.search(text):
            warnings.append(f"SVG with script/event/entity/remote reference not embedded: {path.name}")
            return ""
    else:
        # Re-encode every raster through Pillow: downscale big ones, and drop EXIF (GPS, device) from all of them.
        try:
            from PIL import Image  # type: ignore
            im = Image.open(BytesIO(data))
            im.load()
            if im.width > IMG_MAX_W or len(data) > 200_000 or mime == "image/jpeg":
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
            if len(data) > 200_000:
                warnings.append(f"{path.name} is {len(data) // 1024} KB and Pillow is not installed to downscale it; EXIF not stripped")
        except Exception as e:  # corrupt file, decompression bomb, unsupported mode
            warnings.append(f"image not embedded ({type(e).__name__}): {path.name}")
            return ""
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


# --------------------------------------------------------------------------- content

def events_from_brief(brief: dict, root: Path, warnings: list[str]) -> list[dict]:
    hist = brief.get("history") or []
    out = []
    for i, h in enumerate(hist):
        if not isinstance(h, dict):
            continue
        year = str(h.get("year") or "").strip()
        tbc = bool(h.get("to_confirm")) or not year or "confirm" in year.lower()
        event = str(h.get("event") or "").strip()
        if not event:
            warnings.append(f"history[{i}] has no event text; skipped")
            continue
        img = str(h.get("image") or "").strip()
        src = embed_image(img, root, warnings) if img else ""
        slide = h.get("source_slide") or h.get("slide") or None
        if not slide:
            warnings.append(f"history[{i}] ({year or 'undated'}) has no source_slide; the claim is not traceable")
        # A stable, short target for reactions. Undated moments use the first three words of the event text;
        # the bar shows a readable label instead.
        target = year if (year and not tbc) else "undated: " + " ".join(event.split()[:3]).rstrip(".,;:")
        out.append({"year": year if not tbc else "", "label": year if (year and not tbc) else "[year to confirm]",
                    "event": event, "slide": slide, "img": src, "tbc": tbc, "target": target})
    rest = []
    if len(out) > MAX_EVENTS:
        rest = out[MAX_EVENTS:]
        out = out[:MAX_EVENTS]
        warnings.append(f"{len(rest)} moments beyond {MAX_EVENTS} are listed in a final 'Also in the record' scene")
    return out, rest


def section_html(events: list[dict], rest: list[dict], installed_voice: bool) -> str:
    n = len(events) + (1 if rest else 0)
    scenes = []
    for i, e in enumerate(events):
        img = (f'<img class="tl-img" src="{e["img"]}" alt="" loading="lazy" decoding="async">' if e["img"]
               else '<div class="tl-img tl-noimg" aria-hidden="true"></div>')
        slide_txt = ("slide " + html.escape(str(e["slide"]))) if e["slide"] else "slide not recorded"
        slide = f'<small class="tl-src">From the presentation, {slide_txt}' + (" · date not given" if e["tbc"] else "") + "</small>"
        btn = ("Do you know when? Tell us" if e["tbc"] else f"Add a memory of {html.escape(e['label'])}")
        pos = f'<span class="tl-pos" aria-hidden="true">{i + 1} of {n}{"" if i == n - 1 else " · scroll ↓"}</span>'
        scenes.append(
            f'    <article class="tl-scene{" tbc" if e["tbc"] else ""}" data-i="{i}" data-target="{html.escape(e["target"])}" data-slide="{html.escape(slide_txt)}" aria-label="{html.escape(e["label"])}">\n'
            f'      {img}\n'
            f'      <div class="tl-cap">\n'
            f'        <div class="tl-top">{pos}<span class="tl-year">{html.escape(e["label"])}</span></div>\n'
            f'        <p>{html.escape(e["event"])}</p>\n'
            f'        {slide}\n'
            f'        <div class="row"><button type="button" class="primary tl-add">{btn}</button><span class="chip tl-count" hidden><b>0</b> <span class="tl-n">memories</span> on this device</span></div>\n'
            f'        <div class="tl-mem" role="list" aria-label="Memories for {html.escape(e["label"])}"></div>\n'
            f'      </div>\n'
            f'    </article>'
        )
    if rest:
        items = "".join(f'<li><b>{html.escape(r["label"])}</b> {html.escape(r["event"])} <small>(slide {html.escape(str(r["slide"]))})</small></li>' if r["slide"] else f'<li><b>{html.escape(r["label"])}</b> {html.escape(r["event"])}</li>' for r in rest)
        scenes.append(
            f'    <article class="tl-scene tl-rest" data-i="{len(events)}" data-target="also in the record" aria-label="Also in the record">\n'
            f'      <div class="tl-img tl-noimg" aria-hidden="true"></div>\n'
            f'      <div class="tl-cap"><span class="tl-year">Also in the record</span><ul>{items}</ul></div>\n'
            f'    </article>'
        )
    rail = "".join(f'<button type="button" data-i="{i}"{" class=tbc" if e["tbc"] else ""} aria-label="{html.escape(e["label"])}"><span>{html.escape(e["label"] if not e["tbc"] else "?")}</span></button>' for i, e in enumerate(events))
    if rest:
        rail += f'<button type="button" data-i="{len(events)}" aria-label="Also in the record"><span>…</span></button>'
    lede = "Scroll through the moments that shaped the site. Were you there, or do you remember it differently? Add a memory to any year: {v}, and the design team collects it with the rest."
    return (
        f'<section data-feature="timeline" data-title="History" hidden>\n'
        f'  <h2>How the site got here</h2>\n'
        f'  <p class="lede" data-with-voice="{html.escape(lede.format(v="speak or type"))}" data-without-voice="{html.escape(lede.format(v="type"))}">{html.escape(lede.format(v="type"))}</p>\n'
        f'  <div class="tl-wrap">\n'
        f'  <div class="tl" id="tl" tabindex="0" role="region" aria-roledescription="scrolling story" aria-label="Site history, {n} moments. Use the arrow keys to move between them.">\n'
        + "\n".join(scenes) + "\n"
        f'  </div>\n'
        f'  <nav class="tl-rail" id="tlRail" aria-label="Years">{rail}</nav>\n'
        f'  </div>\n'
        f'</section>'
    )


STYLE = """<style data-feature="timeline">
/* ===== ek-timeline: scroll-driven story ===== */
.tl-wrap{position:relative;margin:0 -20px;width:calc(100% + 40px)}
@media(min-width:900px){.tl-wrap{margin:0 -32px;width:calc(100% + 64px)}}
.tl{position:relative;height:calc(100dvh - var(--tl-top,0px) - var(--tl-bar,110px) - 12px);min-height:320px;max-height:900px;overflow-y:auto;overscroll-behavior:contain;scroll-snap-type:y mandatory;background:var(--soft);outline:none;scrollbar-width:none}
.tl::-webkit-scrollbar{display:none}
.tl:focus-visible{outline:3px solid var(--marker);outline-offset:-3px}
.tl-scene{position:relative;height:100%;scroll-snap-align:start;scroll-snap-stop:always;display:flex;align-items:flex-end;padding:16px 16px 20px;overflow:hidden}
@media(min-width:900px){.tl-scene{padding:28px 32px 32px}}
.tl-img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:block;background:var(--soft)}
.tl-noimg{background:linear-gradient(160deg,var(--soft),var(--card))}
.tl-scene::after{content:"";position:absolute;inset:auto 0 0 0;height:60%;background:linear-gradient(to top,rgba(0,0,0,.42),transparent);pointer-events:none}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]) .tl-scene::after{background:linear-gradient(to top,rgba(0,0,0,.6),transparent)}}
.tl-cap{position:relative;z-index:1;background:var(--card);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:16px 18px;max-width:440px;width:100%;display:flex;flex-direction:column;gap:8px;box-shadow:0 10px 30px rgba(0,0,0,.18);margin-right:96px}
@media(min-width:900px){.tl-cap{margin-right:140px}}
.tl-scene.tbc .tl-cap{border-style:dashed}
.tl-top{display:flex;flex-direction:column;gap:4px} .tl-pos{font-size:13px;color:var(--mute);letter-spacing:.02em}
.tl-year{font-size:44px;font-weight:700;line-height:1;letter-spacing:-.01em} .tl-scene.tbc .tl-year{font-size:28px;color:var(--mute)}
.tl-cap p{max-width:52ch} .tl-cap small{color:var(--mute);font-size:14px}
@media(max-width:599px){.tl-src{display:none}}
.tl-cap ul{margin:0;padding-left:18px;display:grid;gap:6px;max-height:40vh;overflow:auto} .tl-cap li{font-size:15px}
.tl-count[hidden]{display:none} .tl-count{gap:4px}
.tl-mem{display:grid;gap:6px;max-height:28vh;overflow:auto} .tl-mem:empty{display:none}
.tl-mem div{padding:8px 10px;border-left:3px solid var(--marker);background:var(--soft);border-radius:0 6px 6px 0;font-size:15px;overflow-wrap:anywhere}
.tl-mem audio{width:100%;max-width:320px;height:36px;display:block}
.tl-rail{position:absolute;right:8px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;align-items:flex-end;gap:0;padding:6px 4px;z-index:2;background:rgba(20,20,18,.55);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);border-radius:22px}
.tl-rail button{min-height:44px;min-width:44px;padding:0 8px;border:none;border-radius:22px;background:transparent;color:#F7F6F2;display:flex;align-items:center;justify-content:flex-end;gap:8px;font-size:13px;line-height:1}
.tl-rail button:hover{background:rgba(255,255,255,.12)}
.tl-rail button::after{content:"";flex:0 0 auto;width:10px;height:10px;border-radius:5px;background:#F7F6F2;opacity:.7}
.tl-rail button span{display:none;white-space:nowrap} .tl-rail button.tbc::after{border:2px dashed #F7F6F2;background:transparent;width:8px;height:8px}
.tl-rail button[aria-current="true"]::after{opacity:1;background:var(--marker);transform:scale(1.3)}
.tl-rail button:hover span,.tl-rail button[aria-current="true"] span,.tl-rail button:focus-visible span{display:inline}
.tl-rail button[aria-current="true"] span{font-weight:600}
.tl-rail button:focus-visible{outline:3px solid var(--marker);outline-offset:-3px}
@media(min-width:900px){.tl-rail{right:16px} .tl-rail button span{display:inline;opacity:.8} .tl-rail button[aria-current="true"] span{opacity:1}}
@media(prefers-reduced-motion:reduce){.tl{scroll-snap-type:none;scroll-behavior:auto} .tl-rail button[aria-current="true"]::after{transform:none}}
</style>"""


SCRIPT = """<script data-feature="timeline">
(function timeline() {
  const TL = %(data)s;
  const root = document.getElementById("tl"), rail = document.getElementById("tlRail");
  if (!root || !rail) return;
  const scenes = [...root.querySelectorAll(".tl-scene")], dots = [...rail.querySelectorAll("button")];
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  let active = 0, armed = false;
  const target = i => scenes[i] ? scenes[i].dataset.target : "";
  const label = i => scenes[i] ? scenes[i].getAttribute("aria-label") : "";
  const chipLabel = i => scenes[i] && scenes[i].classList.contains("tbc") ? "the undated moment" : label(i);
  const slideOf = i => scenes[i] ? scenes[i].dataset.slide || "" : "";
  const hasVoice = () => EK.hasKind && EK.hasKind("voice");

  /* size: the story fills the viewport between the sticky header (phones) and the shell's fixed bar */
  const hdr = document.querySelector("header.top"), bar = document.getElementById("bar");
  const stickyH = () => (hdr && window.innerWidth < 900) ? hdr.getBoundingClientRect().height : Math.max(0, Math.round(root.getBoundingClientRect().top + window.scrollY));
  function size() { root.style.setProperty("--tl-top", Math.round(stickyH()) + "px"); root.style.setProperty("--tl-bar", Math.round(bar ? bar.getBoundingClientRect().height : 110) + "px"); }
  /* on phones the intro scrolls away so the whole story is on screen: align its top under the header */
  function settle() { if (window.innerWidth >= 900 || EK.current() !== "timeline") return; const se = document.scrollingElement || document.documentElement; const max = Math.max(0, se.scrollHeight - window.innerHeight); const y = Math.min(max, Math.max(0, root.getBoundingClientRect().top + window.scrollY - stickyH())); if (Math.abs(window.scrollY - y) > 4) window.scrollTo({ top: y, behavior: "auto" }); }

  function setActive(i, fromScroll) { if (i === active && armed) return; active = i; armed = true;
    dots.forEach((d, k) => k === i ? d.setAttribute("aria-current", "true") : d.removeAttribute("aria-current"));
    if (EK.current() === "timeline") EK.context("timeline", target(i), "\\u2014 " + slideOf(i) + (i < scenes.length - 1 ? " \\u00b7 scroll for the next moment" : " \\u00b7 the last moment so far"), chipLabel(i)); }
  function go(i, focus) { i = Math.max(0, Math.min(scenes.length - 1, i)); root.scrollTo({ top: scenes[i].offsetTop, behavior: reduced ? "auto" : "smooth" }); setActive(i); settle(); if (focus) root.focus({ preventScroll: true }); }
  root.addEventListener("scroll", () => { if (!root._settled) { root._settled = true; settle(); } }, { passive: true });

  /* which scene is on screen */
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(es => { es.forEach(e => { if (e.isIntersecting && e.intersectionRatio >= 0.55) setActive(+e.target.dataset.i, true); }); }, { root, threshold: [0.55] });
    scenes.forEach(s => io.observe(s));
  } else { root.addEventListener("scroll", () => setActive(Math.round(root.scrollTop / root.clientHeight), true), { passive: true }); }

  /* rail, keyboard, buttons */
  dots.forEach(d => d.addEventListener("click", () => go(+d.dataset.i, true)));
  root.addEventListener("keydown", e => { const k = e.key; if (k === "ArrowDown" || k === "PageDown" || k === " ") { e.preventDefault(); go(active + 1); } else if (k === "ArrowUp" || k === "PageUp") { e.preventDefault(); go(active - 1); } else if (k === "Home") { e.preventDefault(); go(0); } else if (k === "End") { e.preventDefault(); go(scenes.length - 1); } });
  scenes.forEach((s, i) => { const b = s.querySelector(".tl-add"); if (!b) return; b.addEventListener("click", () => { setActive(i); EK.context("timeline", target(i), s.classList.contains("tbc") ? "\\u2014 when was this?" : "\\u2014 what do you remember?", chipLabel(i)); EK.focusNote(); EK.toast(s.classList.contains("tbc") ? "Tell us when, below" : (hasVoice() ? "Speak or type your memory below" : "Type your memory below")); }); });
  /* the bar grows when its context wraps; keep the story above it */
  if ("ResizeObserver" in window && bar) new ResizeObserver(() => { const before = root.clientHeight; size(); if (root.clientHeight !== before && scenes[active]) root.scrollTo({ top: scenes[active].offsetTop, behavior: "auto" }); }).observe(bar);

  /* memories: this device's reactions per moment, escaped on render */
  function render() { const R = EK.reactions().filter(r => r.feature === "timeline");
    scenes.forEach((s, i) => { const mine = R.filter(r => r.target === target(i)); const box = s.querySelector(".tl-mem"), chip = s.querySelector(".tl-count"); if (!box) return;
      box.textContent = "";
      mine.forEach(r => { const d = document.createElement("div"); d.setAttribute("role", "listitem");
        if (r.kind === "voice" && r.value && typeof r.value.mime === "string" && /^audio\\/[\\w.+-]+$/.test(r.value.mime) && typeof r.value.base64 === "string" && /^[A-Za-z0-9+\\/=]+$/.test(r.value.base64)) { const a = document.createElement("audio"); a.controls = true; a.src = "data:" + r.value.mime + ";base64," + r.value.base64; d.appendChild(a); const t = document.createElement("small"); t.textContent = (r.value.seconds || "?") + " s, voice"; d.appendChild(t); }
        else if (r.kind === "voice") d.textContent = "Unsupported voice note";
        else d.textContent = typeof r.value === "string" ? r.value : "Unsupported note";
        box.appendChild(d); });
      if (chip) { chip.hidden = !mine.length; chip.querySelector("b").textContent = mine.length; chip.querySelector(".tl-n").textContent = mine.length === 1 ? "memory" : "memories"; }
      if (dots[i]) dots[i].setAttribute("aria-label", label(i) + (mine.length ? ", " + mine.length + " memor" + (mine.length === 1 ? "y" : "ies") + " on this device" : "")); }); }
  EK.on("ek:reaction", render); render();

  EK.on("ek:show", id => { if (id === "timeline") { size(); armed = false; setActive(active); root._settled = false; setTimeout(settle, 350); } });
  window.addEventListener("resize", size); size();
  if (EK.current() === "timeline") { setActive(0); setTimeout(settle, 350); }
  window.addEventListener("load", () => { size(); setTimeout(settle, 50); });

  /* tour */
  const steps = [
    { go: "timeline", do: () => go(Math.min(1, scenes.length - 1)), text: "History: " + TL.count + " moments that shaped the site" + (TL.undated ? ", one undated" : "") + ". Scroll, or use the dots, to move between them." },
    { go: "timeline", do: () => { const b = scenes[active] && scenes[active].querySelector(".tl-add"); if (b) b.focus(); }, text: "Were you there? Add a memory and it becomes part of the record, tied to that year." }
  ];
  if (TL.undated >= 0 && TL.undated !== null) steps.push({ go: "timeline", do: () => go(TL.undated), text: "This one has no date in the presentation. If you know when it happened, tell us." });
  EK.registerTour(steps);
})();
</script>"""


# --------------------------------------------------------------------------- splice

def splice(doc: str, section: str, style: str, script: str) -> str:
    # remove our previous blocks (idempotent)
    doc = re.sub(r'\n?<style data-feature="timeline">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="timeline">.*?</script>', "", doc, flags=re.S)
    sec_re = re.compile(r'<section data-feature="timeline"[^>]*>.*?</section>', re.S)
    if not sec_re.search(doc):
        raise SystemExit("no <section data-feature=\"timeline\"> slot in the output; is ek-timeline installed in the manifest and the shell built?")
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
    ap.add_argument("--root", type=Path, default=Path("."), help="where history[].image paths are resolved from")
    args = ap.parse_args(argv)
    for p in (args.brief, args.out):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    doc = args.out.read_text(encoding="utf-8")
    warnings: list[str] = []
    events, rest = events_from_brief(brief, args.root, warnings)
    if not events:
        sys.exit("brief.history has no usable events; ek-project-manifest should not have installed ek-timeline")
    installed_voice = "ek-voice-reactions" in (re.search(r'"installed":\s*(\[[^\]]*\])', doc).group(1) if re.search(r'"installed":\s*(\[[^\]]*\])', doc) else "")  # informational only; copy follows EK.hasKind at runtime
    undated = next((i for i, e in enumerate(events) if e["tbc"]), None)
    data = {"count": len(events), "undated": undated}  # counts only; no brief text in the inline JSON
    section = section_html(events, rest, installed_voice)
    script = SCRIPT % {"data": json_inline(data)}
    new_doc = splice(doc, section, STYLE, script)
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    img_bytes = sum(len(e["img"]) for e in events)
    if img_bytes > IMG_BUDGET:
        warnings.append(f"embedded images total {img_bytes // 1024} KB; consider smaller renders")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "moments": len(events), "also_in_record": len(rest),
                      "undated_index": undated, "images_embedded": sum(1 for e in events if e["img"]), "image_bytes": img_bytes,
                      "voice_installed": installed_voice, "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
