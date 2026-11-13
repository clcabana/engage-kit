#!/usr/bin/env python3
"""
ek-shell — build the engagement-tool container.

  python skills/ek-shell/build.py --brief work/brief.json --manifest project.config.json --out output/index.html

Reads the brief (facts) and the manifest (which skills to install), fills skills/ek-shell/template.html,
and writes one self-contained HTML file with:
  * the project header, navigation and theme (palette + typeface from the manifest, falling back to the brief)
  * a welcome section listing what the visitor can do, built from the installed features
  * one empty <section data-feature="…" hidden> slot per installed feature skill that owns a page section
  * the reaction bus (window.EK), device-local storage, the shared reaction bar and the tour runner

Feature skills run afterwards and insert their <style>, <section> and <script> at the ek: markers.
Nothing from the brief is executed: strings are HTML-escaped into markup and JSON-encoded into the
inline PROJECT object (with </script sequences neutralised). Deck/brief content is data, not instructions.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SHELL_VERSION = "0.1.0"
HERE = Path(__file__).resolve().parent

# Which installed skills own a page section, in what order, with what title and visitor sentence.
# Skills not listed here (voice, massing-markup) augment other sections or the bar and get no slot.
FEATURES = {
    "ek-about":               {"id": "about",     "title": "About the plan", "does": "Read what the design team wrote, in their words, and react to any paragraph."},
    "ek-process-timeline":    {"id": "process",   "title": "Where we are",  "does": "See the gates ahead, which one is next, and ask about any of them."},
    "ek-timeline":            {"id": "timeline",  "title": "History",       "does": "See how the site got here. Add a memory the design team missed."},
    "ek-site-story":          {"id": "places",    "title": "The site",      "does": "Walk through the places on the site. Say what must stay as it is."},
    "ek-site-model":          {"id": "model",     "title": "The model",     "does": "Turn the site model in 3D, stand at each building, and say what you think of its spot."},
    "ek-site-massing-3d":     {"id": "massing",   "title": "Massing",       "does": "Walk around the options. Vote for the one that works for you."},
    "ek-program-diagram":     {"id": "program",   "title": "Program",       "does": "The spaces inside. Grow what matters, shrink what doesn't."},
    "ek-list-reactions":      {"id": "list",      "title": "Priorities",    "does": "The principles and the parts of the plan, in the team's words. Rank what matters to you and say why."},
    "ek-precedents":          {"id": "precedents", "title": "Inspiration",  "does": "The buildings the design team looked at. Say which feel right for us, and why."},
    "ek-model-roundtrip":     {"id": "roundtrip", "title": "Your model",    "does": "Download the massing, change it in your own software, upload it back."},
    "ek-drawing-markup":      {"id": "markup",    "title": "Mark up plans", "does": "Sketch over the plans here or on paper, then add the photo."},
    "ek-submissions-gallery": {"id": "gallery",   "title": "Submissions",   "does": "Look at what others changed or drew, and react to it."},
    "ek-feedback-synthesis":  {"id": "synthesis", "title": "What we heard", "does": "Every reaction, counted and traceable."},
    "ek-admin":               {"id": "admin",     "title": "Admin",         "does": "For the design team: load the phones' exports, read the merged record, ask the assistant to analyse it."},
}
AUGMENTS = {"ek-voice-reactions": "massing", "ek-massing-markup": "massing", "ek-model-pins": "model", "ek-chat": "bar"}  # no slot of their own
ORDER = list(FEATURES.keys())

# Google Fonts we know how to link; anything else falls back to the system stack.
# Weights 300 / 400 / 500: the shell sets body text at 300 and headings at 500 (the Massing Studio look).
GOOGLE_FONTS = {
    "Archivo": "family=Archivo:wdth,wght@87.5,300;87.5,400;87.5,500;100,300;100,400;100,500",
    "Inter": "family=Inter:wght@300;400;500", "Work Sans": "family=Work+Sans:wght@300;400;500",
    "Source Sans 3": "family=Source+Sans+3:wght@300;400;500", "IBM Plex Sans": "family=IBM+Plex+Sans:wght@300;400;500",
    "Manrope": "family=Manrope:wght@300;400;500", "DM Sans": "family=DM+Sans:wght@300;400;500",
    "Public Sans": "family=Public+Sans:wght@300;400;500", "Noto Sans": "family=Noto+Sans:wght@300;400;500",
    "Open Sans": "family=Open+Sans:wght@300;400;500", "Roboto": "family=Roboto:wght@300;400;500",
}

# --------------------------------------------------------------------------- colour helpers

def hex_to_rgb(h: str) -> tuple[float, float, float] | None:
    h = (h or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", h):
        return None
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


def rgb_to_hex(rgb) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(c))) for c in rgb)


def mix(a, b, t: float):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def luminance(rgb) -> float:
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (ch(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def on_colour(bg) -> tuple:
    """White or near-black text, whichever reads better on bg."""
    white, black = (255, 255, 255), (35, 36, 31)
    return white if contrast(bg, white) >= contrast(bg, black) else black


def normalise_palette(p: dict, warnings: list[str]) -> dict:
    """Accept both the brief's keys (accent1/accent2) and the example manifest's (marker/plan); warn on bad hex."""
    p = p or {}
    out = {"paper": p.get("paper", ""), "ink": p.get("ink", ""),
           "accent1": p.get("accent1") or p.get("marker") or "", "accent2": p.get("accent2") or p.get("plan") or ""}
    for k, v in out.items():
        if v and hex_to_rgb(v) is None:
            warnings.append(f"palette.{k} '{v}' is not a hex colour; default used")
            out[k] = ""
    return out


def readable_mute(ink, paper, floor: float = 4.5):
    """Secondary text colour: the lightest mix of ink toward paper that still meets the contrast floor."""
    for t in (0.42, 0.38, 0.34, 0.30, 0.26, 0.22, 0.18, 0.14, 0.1, 0.0):
        m = mix(ink, paper, t)
        if contrast(m, paper) >= floor:
            return m
    return ink


def theme(palette: dict, warnings: list[str]) -> tuple[str, str]:
    """Return (light :root vars, dark override vars) from {paper, ink, accent1, accent2}."""
    paper = hex_to_rgb(palette.get("paper")) or (247, 246, 242)
    ink = hex_to_rgb(palette.get("ink")) or (35, 36, 31)
    marker = hex_to_rgb(palette.get("accent1")) or (232, 100, 44)
    plan = hex_to_rgb(palette.get("accent2")) or (46, 94, 140)
    if luminance(paper) < luminance(ink):  # someone gave a dark paper; swap so "paper" is the light one
        paper, ink = ink, paper
        warnings.append("palette.paper was darker than palette.ink; swapped them for the light theme")
    c = contrast(ink, paper)
    if c < 4.5:
        warnings.append(f"ink/paper contrast {c:.1f}:1 is under 4.5:1; ink darkened to meet the floor")
        ink = mix(ink, (0, 0, 0), 0.5) if luminance(ink) < luminance(paper) else ink
    light = {
        "paper": paper, "ink": ink, "marker": marker, "plan": plan,
        "mute": readable_mute(ink, paper), "line": mix(paper, ink, 0.14), "card": mix(paper, (255, 255, 255), 0.6), "soft": mix(paper, ink, 0.05),
        "on-marker": on_colour(marker),
    }
    # Dark theme: neutral darks derived from the project's own ink/paper hue, accents lifted so they still read.
    dpaper = mix(ink, (0, 0, 0), 0.25)
    dink = mix(paper, (255, 255, 255), 0.3)
    dmarker = marker if contrast(marker, dpaper) >= 3 else mix(marker, (255, 255, 255), 0.25)
    dplan = plan if contrast(plan, dpaper) >= 3 else mix(plan, (255, 255, 255), 0.35)
    dark = {
        "paper": dpaper, "ink": dink, "marker": dmarker, "plan": dplan,
        "mute": readable_mute(dink, dpaper), "line": mix(dpaper, dink, 0.16), "card": mix(dpaper, dink, 0.06), "soft": mix(dpaper, dink, 0.1),
        "on-marker": on_colour(dmarker),
    }
    fmt = lambda d: " ".join(f"--{k}:{rgb_to_hex(v)};" for k, v in d.items())
    return fmt(light), fmt(dark)


# --------------------------------------------------------------------------- build

def slug(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")
    return s or "project"


def json_inline(obj) -> str:
    # JSON is valid JS; neutralise sequences that could close the script element or confuse parsers.
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


COVER_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
COVER_MAX_BYTES = 1_500_000


def cover_html(mp: dict, base: Path | None, warnings: list[str]) -> str:
    """Optional full-bleed key image at the top of the welcome page: manifest project.cover = {"image": <path
    relative to the manifest's folder>, "alt": <text>}. Embedded as a data URI so the tool stays one file (and,
    when locked, the image is inside the ciphertext, never a separate public file)."""
    c = mp.get("cover")
    if not c:
        return ""
    if not isinstance(c, dict) or not isinstance(c.get("image"), str) or base is None:
        warnings.append("project.cover must be {\"image\": path, \"alt\": text}; no cover")
        return ""
    root = base.resolve()
    p = (root / c["image"]).resolve()
    if root != p and root not in p.parents:
        warnings.append(f"project.cover.image {c['image']!r} is outside the project folder; no cover")
        return ""
    mime = COVER_TYPES.get(p.suffix.lower())
    if not mime or not p.is_file():
        warnings.append(f"project.cover.image {c['image']!r} is missing or not a jpg/png/webp; no cover")
        return ""
    data = p.read_bytes()
    if len(data) > COVER_MAX_BYTES:
        warnings.append(f"project.cover.image is {len(data):,} bytes (over {COVER_MAX_BYTES:,}); resize it; no cover")
        return ""
    alt = (c.get("alt") or "").strip()
    if not alt:
        warnings.append("project.cover has no alt text; the image is treated as decorative")
    uri = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
    return f'<figure class="ek-cover ek-bleed"><img src="{uri}" alt="{html.escape(alt)}"></figure>'


def build(brief: dict, manifest: dict, warnings: list[str], base: Path | None = None) -> tuple[str, dict]:
    mp = manifest.get("project", {}) or {}
    bp = brief.get("project", {}) or {}
    name = (mp.get("name") or bp.get("name") or "").strip()
    if not name:
        name = "Untitled project"
        warnings.append("no project name in manifest or brief; using 'Untitled project' (confirm)")
    palette = normalise_palette(mp.get("palette") or brief.get("palette") or {}, warnings)
    typeface = (mp.get("typeface") or brief.get("typeface") or "").strip()
    # The brief's phase is the plain one ("Design options"); the manifest's may carry internal process notes.
    phase = (bp.get("phase") or mp.get("phase") or "").strip()
    deadline = (mp.get("deadline") or "").strip()
    one_line = (bp.get("one_line") or "").strip()
    sample = bool(brief.get("sample")) or bool(manifest.get("sample"))
    decisions = [d for d in (brief.get("decision_points") or []) if isinstance(d, dict) and d.get("question")]
    first_q = (decisions[0].get("question") if decisions else "") or ""
    who = (decisions[0].get("who_decides") if decisions else "") or ""
    if deadline:
        tail = "have your say before " + deadline
    elif who:
        tail = "your reactions go to " + who
    else:
        tail = "have your say"
        warnings.append("no deadline in the manifest and no who_decides in the brief; subtitle says only 'have your say'")
    subtitle = " · ".join(x for x in [phase, tail] if x)

    installed = [i.get("skill") for i in manifest.get("install", []) if isinstance(i, dict) and i.get("skill")]
    unknown = [s for s in installed if s not in FEATURES and s not in AUGMENTS and s != "ek-shell"]
    for s in unknown:
        warnings.append(f"manifest installs unknown skill '{s}'; no slot created")
    slots = [FEATURES[s] for s in ORDER if s in installed]
    if not slots:
        warnings.append("manifest installs no feature skill that owns a section; the tool has a welcome page and a 'nothing installed' notice only")
    public_sections = [f for f in slots if f["id"] not in ("synthesis", "admin")]
    if len(public_sections) > 5:
        warnings.append(f"{len(public_sections)} public feature sections; ek-project-manifest caps a public audience at 5")

    # Theme. The typeface name lands inside <style>, so it is validated, never trusted.
    root_vars, dark_vars = theme(palette, warnings)
    if typeface and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 \-]{0,40}", typeface):
        warnings.append(f"typeface {typeface!r} is not a plain font name; dropped (system stack only)")
        typeface = ""
    font_link = ""
    want_google = (mp.get("font_link") or "").strip().lower() == "google"
    if typeface in GOOGLE_FONTS and want_google:
        # Opt-in only: every visit then tells Google the visitor's IP and this page's URL. HANDOFF.md must say so.
        font_link = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
                     f'<link href="https://fonts.googleapis.com/css2?{GOOGLE_FONTS[typeface]}&display=swap" rel="stylesheet">')
    elif typeface in GOOGLE_FONTS:
        warnings.append(f"typeface '{typeface}' is on Google Fonts but not linked: set project.font_link to \"google\" in the manifest to opt in (third-party request), or self-host it with @font-face")
    elif typeface:
        warnings.append(f"typeface '{typeface}' is not in the known Google Fonts list; system stack only (add a @font-face if the project ships the files)")
    stack = (f'"{typeface}", ' if typeface else "") + '"Helvetica Neue", Arial, sans-serif'

    # Welcome copy: only what the installed features make true. Voice is mentioned only if a voice kind is
    # actually registered at runtime (the shell swaps the two variants on load), so an installed-but-not-yet-built
    # ek-voice-reactions never promises a microphone that is not there.
    hero_h1 = one_line or f"Tell us what works for you at {name}, and why."
    verbs = ["type"]
    if "ek-massing-markup" in installed:
        verbs.append("drop a pin on the model")
    if "ek-site-massing-3d" in installed:
        verbs.append("vote for an option")
    if "ek-program-diagram" in installed:
        verbs.append("resize a space")
    if "ek-drawing-markup" in installed:
        verbs.append("mark up a plan")
    if "ek-list-reactions" in installed:
        verbs.append("rank what matters")
    if "ek-site-story" in installed:
        verbs.append("say what must stay")
    if "ek-site-model" in installed:
        verbs.append("stand at a building in the model")
    if "ek-model-pins" in installed:
        verbs.append("drop a pin where something should go")
    if "ek-precedents" in installed:
        verbs.append("pick the references that feel right")

    # The lede names at most three things the visitor can do; a list of every verb reads as a pile (critic, 2026-11-06).
    def join(vs):
        vs = vs[:3]
        return (", ".join(vs[:-1]) + " or " + vs[-1]) if len(vs) > 1 else vs[0]
    lede_tpl = "This is a working tool, not a brochure. Wherever you are in it you can {v}, and the tool records what it was about."
    hero_lede = lede_tpl.format(v=join(verbs))
    hero_lede_voice = lede_tpl.format(v=join(["speak"] + verbs))
    # The privacy card states every flow that leaves the phone, and "nothing is sent anywhere" only when that is true
    # (security + critic, 2026-11-13): Ask sends the question to the AI service; Speak sends sound to the browser
    # maker's speech service; a chat block in any mode means the team may send collected words to the AI service.
    chat_cfg = manifest.get("chat") if isinstance(manifest.get("chat"), dict) else {}
    ai_user = "ek-chat" in installed and str(chat_cfg.get("mode") or "") == "proxy"
    ai_team = bool(chat_cfg)
    speak = "ek-voice-reactions" in installed
    p_keep = "Everything you add is kept on this phone."
    p_none = " Nothing is sent anywhere."
    p_team = (" The design team collects it from the device and adds it to the record; until then you can remove it all here. "
              "No name or contact is asked for; please don't add other people's.")
    p_ask = " If you use Ask, your question is sent to an AI service (Anthropic) to be answered." if ai_user else ""
    p_speak = (" If you use Speak, your browser sends the sound to Google (Chrome) or Apple (Safari) to turn it into words"
               + (", and the words go to the AI service to be tidied" if ai_user else "") + ".")
    p_ai = " The design team may use an AI service (Anthropic) to help read the collected reactions; your words are sent to it then." if ai_team else ""
    p_id = " An export carries a random id for this phone, not your name, so the team can tell phones apart; Remove all resets it." if "ek-feedback-synthesis" in installed else ""
    privacy_text = p_keep + ("" if (ai_user or ai_team) else p_none) + p_team + p_ask + p_ai + p_id
    privacy_text_voice = p_keep + p_team + p_ask + (p_speak if speak else "") + p_ai + p_id
    # Primary button: the section that answers the first decision point; else the first installed section.
    ids = [f["id"] for f in slots]
    q = first_q.lower()
    pick = None
    # Whole words only ("sit" must not match "site" or "visit"); the first matching installed section wins.
    for needles, fid in ((("option", "options", "massing", "height", "where", "sit", "sits", "placement", "tall"), "massing"),
                         (("program", "space", "spaces", "room", "rooms", "area", "areas", "size", "sizes"), "program"),
                         (("principle", "principles", "priority", "priorities", "matter", "matters", "approve"), "list"),
                         (("site", "stay", "landscape"), "places"),
                         (("model", "spot", "location", "cabin", "cabins", "building", "buildings"), "model"),
                         (("history", "memory", "memories", "remember"), "timeline")):
        if fid in ids and any(re.search(r"\b" + re.escape(n) + r"\b", q) for n in needles):
            pick = fid
            break
    first = next((f for f in slots if f["id"] == pick), slots[0] if slots else None)
    hero_buttons = '<button class="primary" id="tourStart" type="button" hidden>Watch the tour</button>'
    if first:
        hero_buttons += f'<button type="button" class="primary" data-go="{first["id"]}">{html.escape(first["title"])}</button>'
    sample_note = ('<p style="font-size:14px;margin-top:4px">Sample project. Names, dates, dimensions and drawings are invented for this prototype and marked where the design team would need to confirm them.</p>'
                   if sample else "")

    # Slots
    sections = []
    for f in slots:
        sections.append(
            f'<section data-feature="{f["id"]}" data-title="{html.escape(f["title"])}" hidden>\n'
            f'  <!-- ek:slot {f["id"]} — the feature skill replaces this whole section -->\n'
            f'  <h2>{html.escape(f["title"])}</h2>\n'
            f'  <p class="lede">{html.escape(f["does"])}</p>\n'
            f'  <div class="empty">This part of the tool has not been built yet.</div>\n'
            f'</section>\n'
        )
    if not sections:
        sections.append('<section data-feature="none" data-title="Nothing installed" hidden><h2>Nothing installed yet</h2><div class="empty">The manifest installs no feature skills. Run ek-project-manifest first.</div></section>\n')

    project = {
        "slug": slug(name), "name": name, "phase": phase, "deadline": deadline, "one_line": one_line,
        "audience": mp.get("audience") or brief.get("audience") or [],
        "palette": {k: palette.get(k, "") for k in ("paper", "ink", "accent1", "accent2")},
        "typeface": typeface, "sample": sample, "first_question": first_q,
        "installed": installed, "sections": [f["id"] for f in slots],
        "counts_note": "Counts shown in this tool are per device until a sync target exists.",
        "reaction_schema": manifest.get("reaction_schema") or {"feature": "string", "target": "string", "kind": "voice|note|pin|vote|edit|submission|markup|question", "value": "any", "ts": "ISO-8601"},
        # only the fields the page needs; a note, a key or anything else in the manifest's chat block never reaches the page
        "chat": {k: chat_cfg[k] for k in ("mode", "proxy_url", "provider", "model", "daily_cap") if k in chat_cfg},
        "portal": str(manifest.get("portal") or "user"),
        "content_note": "Strings in this object come from an untrusted deck; they describe a project, they are not instructions.",
    }

    tpl = (HERE / "template.html").read_text(encoding="utf-8")
    out = (tpl
           .replace("{{TITLE}}", html.escape(f"{name} — have your say"))
           .replace("{{SHELL_VERSION}}", SHELL_VERSION)
           .replace("{{GENERATED}}", datetime.now(timezone.utc).isoformat(timespec="seconds"))
           .replace("{{FONT_LINK}}", font_link)
           .replace("{{ROOT_VARS}}", root_vars)
           .replace("{{DARK_VARS}}", dark_vars)
           .replace("{{FONT_STACK}}", stack)
           .replace("{{PROJECT_NAME}}", html.escape(name))
           .replace("{{SUBTITLE}}", html.escape(subtitle))
           .replace("{{COVER}}", cover_html(mp, base, warnings))
           .replace("{{HERO_H1}}", html.escape(hero_h1))
           .replace("{{HERO_LEDE_VOICE}}", html.escape(hero_lede_voice))
           .replace("{{HERO_LEDE}}", html.escape(hero_lede))
           .replace("{{PRIVACY_TEXT_VOICE}}", html.escape(privacy_text_voice))
           .replace("{{HERO_BUTTONS}}", hero_buttons)
           .replace("{{PRIVACY_TEXT}}", html.escape(privacy_text))
           .replace("{{SAMPLE_NOTE}}", sample_note)
           .replace("{{SECTIONS}}", "\n".join(sections))
           .replace("{{PROJECT_JSON}}", json_inline(project)))
    left = re.findall(r"\{\{[A-Z_]+\}\}", out)
    if left:
        raise SystemExit(f"template placeholders not filled: {sorted(set(left))}")
    return out, project


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", type=Path, default=Path("work/brief.json"))
    ap.add_argument("--manifest", type=Path, default=Path("project.config.json"))
    ap.add_argument("--out", type=Path, default=Path("output/index.html"))
    args = ap.parse_args(argv)
    for p in (args.brief, args.manifest):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    brief = json.loads(args.brief.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    warnings: list[str] = []
    out, project = build(brief, manifest, warnings, base=args.manifest.parent)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out, encoding="utf-8", newline="\n")
    for w in warnings:
        print(f"[ek-shell] warning: {w}", file=sys.stderr)
    print(json.dumps({"out": str(args.out), "bytes": len(out.encode("utf-8")), "project": project["name"], "slug": project["slug"],
                      "sections": project["sections"], "installed": project["installed"], "font_link": bool("fonts.googleapis" in out),
                      "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
