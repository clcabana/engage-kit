#!/usr/bin/env python3
"""
ek-about — put the design team's own account on the Start page of an ek-shell output.

  python skills/ek-about/build.py --brief work/brief.json --out output/index.html

Reads brief.about.blocks (title, text, source_slide, optional note): the design team's own narrative, verbatim.
Removes the shell's <section data-feature="about"> slot (so the nav has no "About the plan"; fine if it is
already gone) and writes one <div data-slot="start-about" data-feature-owner="about"> into #welcomeExtra
(after the process strip when there is one; replaced if present): the first block as a short intro, the rest
in a <details class="ab-more">. Inserts one <style data-feature="about"> at <!-- ek:styles --> and one
<script data-feature="about"> at <!-- ek:scripts -->. Idempotent.
Every paragraph is a reaction target ("<title> ¶n") the visitor reacts to through the bar
("React to this"). The words are never changed: blank lines
in the brief are paragraph breaks; a long block with no breaks is split at sentence ends only, and the build
checks that the paragraphs rejoin to the original text. Brief strings are data: HTML-escaped into markup,
JSON-encoded (</ neutralised) into the inline AB object; visitor text is rendered with textContent.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
from pathlib import Path

FEATURE = "about"
MAX_BLOCKS = 12
MAX_TEXT = 2000       # per block; longer text is cut with a warning and a visible "the rest is in the presentation"
SPLIT_OVER = 500      # a paragraph with no breaks longer than this is split at sentence ends
PARA_TARGET = 420     # rough length of a split paragraph


def log(msg: str) -> None:
    print(f"[ek-about] {msg}", file=sys.stderr)


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


SENT_END = re.compile(r'[.!?\u2026]["\u201d\u2019)\]]*\s+(?=["\u201c\u2018(\[]?[A-Z0-9])')


def split_sentences(p: str) -> list[str]:
    """Group sentences into paragraphs of about PARA_TARGET characters. Words and order are untouched."""
    cuts, start = [], 0
    for m in SENT_END.finditer(p):
        cuts.append(p[start:m.end()].rstrip())
        start = m.end()
    cuts.append(p[start:].strip())
    sentences = [s for s in cuts if s]
    if len(sentences) < 2:
        return [p]
    n = max(1, math.ceil(len(p) / PARA_TARGET))
    goal = len(p) / n
    out, cur = [], ""
    for s in sentences:
        cur = (cur + " " + s) if cur else s
        if len(cur) >= goal * 0.85 and len(out) < n - 1:
            out.append(cur)
            cur = ""
    if cur:
        if out and len(cur) < 120:          # a short tail joins the paragraph before it
            out[-1] = out[-1] + " " + cur
        else:
            out.append(cur)
    return out


def paragraphs_of(text: str, warnings: list[str], where: str) -> list[str]:
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = [" ".join(p.split()) for p in re.split(r"\n\s*\n", t) if p.strip()]
    out = []
    split_any = False
    for p in parts:
        if len(p) > SPLIT_OVER:
            s = split_sentences(p)
            split_any = split_any or len(s) > 1
            out.extend(s)
        else:
            out.append(p)
    # honesty check: the paragraphs must rejoin to the brief's text, whitespace aside
    if " ".join(out).split() != t.split():
        warnings.append(f"{where}: paragraph split did not rejoin to the original; shown as one paragraph")
        return [" ".join(t.split())]
    if split_any:
        warnings.append(f"{where}: a paragraph over {SPLIT_OVER} characters with no blank-line break was split at sentence ends; "
                        f"{len(out)} paragraphs (words unchanged; add blank lines to the brief text to choose the breaks)")
    return out


def blocks_from_brief(brief: dict, warnings: list[str]) -> list[dict]:
    about = brief.get("about")
    raw = about.get("blocks") if isinstance(about, dict) else about if isinstance(about, list) else None
    out = []
    for i, b in enumerate(raw or []):
        if not isinstance(b, dict):
            continue
        title = " ".join(str(b.get("title") or "").split())[:80]
        if not title:
            warnings.append(f"about.blocks[{i}] has no title; skipped")
            continue
        text = str(b.get("text") or "").strip()
        if not text:
            warnings.append(f"about.blocks[{i}] ({title}) has no text; skipped")
            continue
        cut = False
        if len(text) > MAX_TEXT:
            warnings.append(f"about.blocks[{i}] ({title}) text cut at {MAX_TEXT} characters ({len(text)} in the brief)")
            head = text[:MAX_TEXT]
            sp = head.rfind(" ")
            text = (head[:sp] if sp > MAX_TEXT * 0.8 else head).rstrip() + "\u2026"
            cut = True
        note = " ".join(str(b.get("note") or "").split())[:300]
        # source (optional): the attribution line for a block that is not from the presentation (for example
        # "Written by the design team for this page"). It replaces "From the presentation, slide N"; a block with a
        # source needs no source_slide. Plain text, escaped on the way in.
        source = b.get("source")
        source = " ".join(source.split())[:120] if isinstance(source, str) else ""
        out.append({"title": title, "paras": paragraphs_of(text, warnings, f"about.blocks[{i}] ({title})"),
                    "slide": None if source else slide_of(b.get("source_slide"), warnings, f"about.blocks[{i}] ({title})"),
                    "note": note, "cut": cut, "source": source})
    if len(out) > MAX_BLOCKS:
        warnings.append(f"{len(out)} blocks; only the first {MAX_BLOCKS} are shown")
        out = out[:MAX_BLOCKS]
    titles = [b["title"].lower() for b in out]
    if len(set(titles)) != len(titles):
        warnings.append("duplicate block titles; reactions target '<title> ¶n', so make them unique")
    return out


def para_html(b: dict, indent: str) -> str:
    out = []
    for n, p in enumerate(b["paras"], 1):
        tgt = f'{b["title"]} ¶{n}'
        out.append(
            f'{indent}<div class="ab-para" data-target="{html.escape(tgt)}" data-label="{html.escape(b["title"])}, paragraph {n}">\n'
            f'{indent}  <p class="ab-p" tabindex="0" aria-describedby="abHow">{html.escape(p)}</p>\n'
            f'{indent}  <div class="row ab-act" hidden><button type="button" class="primary ab-react">React to this</button></div>\n'
            f'{indent}  <div class="ab-mem" role="list" aria-label="Your reactions to {html.escape(b["title"])}, paragraph {n}"></div>\n'
            f'{indent}</div>'
        )
    return "\n".join(out)


def block_html(k: int, b: dict, indent: str, extra_class: str = "") -> str:
    slide_txt = ("slide " + str(b["slide"])) if b["slide"] is not None else "slide not recorded"
    cut = (f'\n{indent}  <small class="ab-src">The rest of this text is in the presentation, {html.escape(slide_txt)}.</small>' if b["cut"] else "")
    note = f'\n{indent}  <small class="ab-note">{html.escape(b["note"])}</small>' if b["note"] else ""
    return (
        f'{indent}<article class="ab-block{extra_class}" id="abBlock-{k}" aria-labelledby="abT-{k}">\n'
        f'{indent}  <h3 class="kicker ab-t" id="abT-{k}">{html.escape(b["title"])}</h3>\n'
        + para_html(b, indent + "  ") + cut + "\n"
        f'{indent}  <small class="ab-src">{html.escape(b.get("source") or ("From the presentation, " + slide_txt))}</small>{note}\n'
        f'{indent}</article>'
    )


START_OPEN, START_CLOSE = "<!-- ek:start-about -->", "<!-- /ek:start-about -->"


def start_html(blocks: list[dict]) -> str:
    """The Start-page block: the first block as a short intro, the rest behind a <details>."""
    first = block_html(0, blocks[0], "  ", " ab-intro")
    more = ""
    if len(blocks) > 1:
        more = ('\n  <details class="ab-more">\n'
                '    <summary>In the design team’s words</summary>\n'
                '    <div class="ab-rest">\n'
                + "\n".join(block_html(k, b, "      ") for k, b in enumerate(blocks[1:], 1)) + "\n"
                '    </div>\n'
                '  </details>')
    return (
        f'{START_OPEN}\n'
        f'<div data-slot="start-about" data-feature-owner="about" class="ab">\n'
        f'  <span class="sr" id="abHow">Press Enter to react to this paragraph.</span>\n'
        + first + more + "\n"
        f'  <div class="ab-other" hidden><small class="kicker">Your notes on the plan as a whole</small><div class="ab-mem" role="list" aria-label="Your notes on the plan as a whole"></div></div>\n'
        f'</div>\n'
        f'{START_CLOSE}'
    )


STYLE = """<style data-feature="about">
/* ===== ek-about: the team's narrative on Start; every paragraph a reaction target ===== */
.ab{display:flex;flex-direction:column;gap:20px;max-width:60ch;margin-top:28px;min-width:0}
.ab-block{display:flex;flex-direction:column;gap:6px;min-width:0}
.ab-t{margin:0 0 4px;line-height:1.3}
.ab-act[hidden],.ab-other[hidden]{display:none}
.ab-para{display:flex;flex-direction:column;gap:8px;padding:6px 0 6px 12px;margin-left:-12px;border-radius:var(--radius,6px);transition:background .15s}
.ab-para.on{background:var(--soft)}
.ab-p{font-size:17px;font-weight:300;line-height:1.6;color:var(--ink);cursor:pointer;overflow-wrap:anywhere;border-radius:4px;-webkit-tap-highlight-color:transparent}
.ab-p:focus-visible{outline:3px solid var(--marker);outline-offset:3px}
@media(min-width:900px){.ab-p{font-size:18px}}
.ab-act{gap:8px;padding-bottom:2px} .ab-act button{min-height:44px;font-size:14px}
.ab-src,.ab-note{color:var(--mute);font-size:13px;line-height:1.4}
.ab-note{font-style:italic}
.ab-mem{display:grid;gap:6px} .ab-mem:empty{display:none}
.ab-mem div{padding:6px 10px;border-left:2px solid var(--mute);font-size:15px;color:var(--ink);overflow-wrap:anywhere}
.ab-mem audio{width:100%;max-width:320px;height:36px;display:block}
.ab-more{background:var(--card);border:1px solid var(--line);border-radius:var(--radius,6px);box-shadow:var(--float,none);min-width:0}
.ab-more summary{min-height:44px;display:flex;align-items:center;padding:0 14px;cursor:pointer;font-weight:500;color:var(--ink);border-radius:var(--radius,6px)}
.ab-more summary:focus-visible{outline:3px solid var(--marker);outline-offset:2px}
.ab-rest{display:flex;flex-direction:column;gap:28px;padding:8px 14px 16px 14px}
.ab-rest .ab-para{margin-left:-8px;padding-left:8px}
.ab-other{display:flex;flex-direction:column;gap:6px}
</style>"""


SCRIPT = """<script data-feature="about">
(function aboutPlan() {
  const AB = %(data)s;  /* counts only; titles and text are in the markup */
  const root = document.querySelector('[data-slot="start-about"]');
  if (!root) return;
  const paras = [...root.querySelectorAll(".ab-para")];
  const targets = new Set(paras.map(p => p.dataset.target));
  const more = root.querySelector(".ab-more");
  const hasVoice = () => EK.hasKind && EK.hasKind("voice");
  const mine = () => EK.reactions().filter(r => r.feature === "about");
  const HINT = "\\u2014 what do you think of this?";
  let on = null, saved = null;                                /* the one highlighted paragraph; the Start context it replaced */

  /* the shell owns Start's context; keep a copy of it while a paragraph is highlighted, put it back after */
  function snap() { const c = EK.ctx && EK.ctx(); if (!c || c.feature === "about") return;
    const chip = document.getElementById("ctxChip"), h = document.getElementById("hint");
    saved = { f: c.feature, t: c.target, h: h ? h.textContent : "", l: chip ? chip.textContent : c.target }; }
  function ctxFor(el) { if (EK.current() !== "welcome") return; snap(); EK.context("about", el.dataset.target, HINT, el.dataset.label); }
  function restore() { if (saved && EK.current() === "welcome") EK.context(saved.f, saved.t, saved.h, saved.l); saved = null; }
  function highlight(el, scroll) {
    if (on && on !== el) { on.classList.remove("on"); on.querySelector(".ab-act").hidden = true; on.querySelector(".ab-p").removeAttribute("aria-current"); }
    on = el; if (!el) { restore(); return; }
    if (more && more.contains(el)) more.open = true;
    el.classList.add("on"); el.querySelector(".ab-act").hidden = false; el.querySelector(".ab-p").setAttribute("aria-current", "true");
    ctxFor(el); if (scroll) el.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); }

  paras.forEach(el => { const p = el.querySelector(".ab-p");
    p.addEventListener("click", () => { const sel = window.getSelection && String(window.getSelection()); if (sel && sel.trim()) return;  /* selecting text, not tapping */
      highlight(on === el ? null : el); });
    p.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); highlight(on === el ? null : el); if (on === el) el.querySelector(".ab-react").focus(); } });
    el.querySelector(".ab-react").addEventListener("click", () => { highlight(el); EK.focusNote(); if (hasVoice()) EK.toast("Speak or type below"); }); });
  root.addEventListener("keydown", e => { if (e.key === "Escape" && on) { const p = on.querySelector(".ab-p"); highlight(null); p.focus(); } });
  if (more) more.addEventListener("toggle", () => { if (!more.open && on && more.contains(on)) highlight(null); });

  const renderNotes = (box, rs) => { box.textContent = "";
    rs.forEach(r => { const d = document.createElement("div"); d.setAttribute("role", "listitem");
      if (r.kind === "voice" && r.value && typeof r.value.mime === "string" && /^audio\\/[\\w.+-]+$/.test(r.value.mime) && typeof r.value.base64 === "string" && /^[A-Za-z0-9+\\/=]+$/.test(r.value.base64)) { const a = document.createElement("audio"); a.controls = true; a.src = "data:" + r.value.mime + ";base64," + r.value.base64; d.appendChild(a); const s = document.createElement("small"); s.textContent = (r.value.seconds || "?") + " s, voice"; d.appendChild(s); }
      else if (r.kind === "voice") d.textContent = "Unsupported voice note";
      else if (r.value && typeof r.value.text === "string") { d.textContent = r.value.text; const sp = document.createElement("small"); sp.textContent = r.value.via === "voice" ? " (spoken)" : ""; d.appendChild(sp); } else d.textContent = typeof r.value === "string" ? r.value : "Unsupported note";
      box.appendChild(d); }); };

  function render() { const R = mine().filter(r => r.kind !== "vote");   /* old underline votes are no longer shown or made */
    paras.forEach(el => renderNotes(el.querySelector(".ab-mem"), R.filter(r => r.target === el.dataset.target)));
    /* notes on a paragraph that no longer exists (a brief change): nothing stored is invisible */
    const other = R.filter(r => !targets.has(r.target)), ob = root.querySelector(".ab-other");
    renderNotes(ob.querySelector(".ab-mem"), other); ob.hidden = !other.length; }
  EK.on("ek:reaction", render); render();

  /* the shell sets Start's context first on ek:show; a highlighted paragraph then takes over */
  EK.on("ek:show", id => { if (id === "welcome" && on) ctxFor(on); });

  const first = paras[0];
  if (first) EK.registerTour([
    { go: "welcome", do: () => highlight(first, true), undo: () => highlight(null),
      text: "The design team\\u2019s own account, in their words" + (AB.blocks > 1 ? " (more under \\u201cIn the design team\\u2019s words\\u201d)" : "") + ". Tap any paragraph to react to it." }
  ]);
})();
</script>"""


SECTION_RE = re.compile(r'\n?[ \t]*<section data-feature="about"[^>]*>.*?</section>', re.S)
START_RE = re.compile(r'\n?' + re.escape(START_OPEN) + r'.*?' + re.escape(START_CLOSE), re.S)
EXTRA_OPEN = re.compile(r'<div id="welcomeExtra"[^>]*>')
STRIP_CLOSE = "<!-- /ek:start-strip -->"


def splice(doc: str, block: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="about">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="about">.*?</script>', "", doc, flags=re.S)
    doc = SECTION_RE.sub("", doc)            # the narrative lives on Start now; no nav entry (fine if already gone)
    doc = START_RE.sub("", doc)
    m = EXTRA_OPEN.search(doc)
    if not m:
        raise SystemExit("no <div id=\"welcomeExtra\"> on the shell's Start page; rebuild the shell")
    at = m.end()
    i = doc.find(STRIP_CLOSE, at)            # after the process strip, when there is one
    if i != -1 and i < doc.find("</section>", at):
        at = i + len(STRIP_CLOSE)
    doc = doc[:at] + "\n" + block + doc[at:]
    for marker, blk in (("<!-- ek:styles -->", style), ("<!-- ek:scripts -->", script)):
        if marker not in doc:
            raise SystemExit(f"shell marker {marker} missing from the output")
        doc = doc.replace(marker, marker + "\n" + blk, 1)
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
    blocks = blocks_from_brief(brief, warnings)
    if not blocks:
        sys.exit("brief.about.blocks has no usable blocks; ek-project-manifest should not have installed ek-about")
    data = {"blocks": len(blocks)}
    new_doc = splice(doc, start_html(blocks), STYLE, SCRIPT.replace("%(data)s", json_inline(data), 1))
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "blocks": len(blocks),
                      "paragraphs": sum(len(b["paras"]) for b in blocks), "cut": [b["title"] for b in blocks if b["cut"]],
                      "warnings": len(warnings)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
