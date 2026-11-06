#!/usr/bin/env python3
"""
ek-list-reactions — write the priorities section into an ek-shell output.

  python skills/ek-list-reactions/build.py --brief work/brief.json --out output/index.html [--groups auto|principles,program,<list id>]

Reads brief.principles (name, text, source_slide), brief.program (name, use, source_slide) and every
brief.lists[] entry ({id, title, kicker?, note?, items:[{name, text, source_slide, note?, tags?}], rank?, filters?,
matters_label?}) as lists of things written down, replaces the shell's <section data-feature="list"> slot, and inserts
one <style data-feature="list"> at <!-- ek:styles --> and one <script data-feature="list"> at
<!-- ek:scripts -->. Idempotent. No sizes, no areas, no grow/shrink: an item is the team's words, verbatim,
and the visitor reacts to it (note or voice through the bar) and ranks the ones that matter most.
Brief strings are data: HTML-escaped into markup, JSON-encoded (</ neutralised) into the inline LS object;
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

FEATURE = "list"
MAX_ITEMS = 12       # per ranked group; a list longer than this is not a list the visitor can rank
MAX_UNRANKED = 60    # per list with rank:false (read and marked one by one, filterable)
MAX_TEXT = 600
RANK_MAX = 5
MAX_TAG = 30
MAX_TAGS = 6
LIST_ID_PATTERN = r"[a-z0-9-]{1,40}"   # used with re.fullmatch: no "$" that would let a trailing newline through

GROUPS = {
    "principles": {"key": "principles", "title": "Guiding principles", "text_field": "text",
                   "kicker": "A principle the design team wrote", "tbc": "[wording to confirm]"},
    "program":    {"key": "program", "title": "The parts of the plan", "text_field": "use",
                   "kicker": "A part of the plan", "tbc": "What this is for is not described in the presentation."},
}


def log(msg: str) -> None:
    print(f"[ek-list-reactions] {msg}", file=sys.stderr)


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


def custom_lists(brief: dict, warnings: list[str]) -> dict:
    """brief.lists[] by id, in brief order; entries with an unsafe or duplicate id are dropped with a warning."""
    out: dict = {}
    raw = brief.get("lists")
    if raw is None:
        return out
    if not isinstance(raw, list):
        warnings.append("brief.lists is not a list; ignored")
        return out
    for k, lst in enumerate(raw):
        if not isinstance(lst, dict):
            warnings.append(f"lists[{k}] is not an object; skipped")
            continue
        lid = lst.get("id")
        if not isinstance(lid, str) or not re.fullmatch(LIST_ID_PATTERN, lid):
            warnings.append(f"lists[{k}] id {str(lid)[:40]!r} is not [a-z0-9-] (1-40 chars); skipped (it becomes a DOM id)")
            continue
        if lid in GROUPS or lid in out:
            warnings.append(f"lists[{k}] id {lid!r} is already used; skipped")
            continue
        out[lid] = lst
    return out


def clean_tags(v, warnings: list[str], where: str) -> list[str]:
    if v is None:
        return []
    if not isinstance(v, list):
        warnings.append(f"{where} tags is not a list; ignored")
        return []
    tags = []
    for t in v:
        t = str(t).strip()[:MAX_TAG] if isinstance(t, (str, int, float)) and not isinstance(t, bool) else ""
        if t and t not in tags:
            tags.append(t)
    if len(tags) > MAX_TAGS:
        warnings.append(f"{where} has {len(tags)} tags; only the first {MAX_TAGS} are kept")
        tags = tags[:MAX_TAGS]
    return tags


def groups_from_brief(brief: dict, wanted: list[str], warnings: list[str], lists: dict | None = None) -> list[dict]:
    lists = lists or {}
    # the sheet names ek-drawing-markup builds (it falls back to site.plan_image as "Site plan")
    sheet_names = {str(s.get("name") or "").strip()[:60] for s in (brief.get("sheets") or []) if isinstance(s, dict)}
    if not brief.get("sheets") and str((brief.get("site") or {}).get("plan_image") or "").strip():
        sheet_names = {"Site plan"}
    out = []
    for gid in wanted:
        if gid in GROUPS:
            spec = GROUPS[gid]
            raw = brief.get(spec["key"]) or []
            where, text_field, tbc_text = spec["key"], spec["text_field"], spec["tbc"]
            title, kicker, gnote, rank, filters, mlabel = spec["title"], "", "", True, False, ""
            tlabel, plan = "", ""
        else:
            lst = lists[gid]
            raw = lst.get("items") if isinstance(lst.get("items"), list) else []
            where, text_field, tbc_text = f"lists.{gid}", "text", "[wording to confirm]"
            title = str(lst.get("title") or "").strip()[:60]
            if not title:
                warnings.append(f"lists.{gid} has no title; its id is used")
                title = gid
            kicker = str(lst.get("kicker") or "").strip()[:80]
            gnote = str(lst.get("note") or "").strip()[:300]
            rank = lst.get("rank") is not False
            filters = lst.get("filters") is True
            mlabel = str(lst.get("matters_label") or "").strip()[:60] or "This matters to me"
            tlabel = str(lst.get("tag_label") or "").strip()[:30]
            plan = str(lst.get("plan_sheet") or "").strip()[:60]
            if plan and plan not in sheet_names:
                warnings.append(f"lists.{gid} plan_sheet {plan!r} is not a name in brief.sheets[]; no plan link")
                plan = ""
        items = []
        for i, it in enumerate(raw):
            if not isinstance(it, dict):
                continue
            name = str(it.get("name") or "").strip()[:80]
            if not name:
                warnings.append(f"{where}[{i}] has no name; skipped")
                continue
            text = str(it.get(text_field) or "").strip()
            tbc = (not text) or text.strip("[] ").lower() in ("wording to confirm", "to confirm", "tbc", "tbd")
            if len(text) > MAX_TEXT:
                warnings.append(f"{where}[{i}] ({name}) text cut at {MAX_TEXT} characters")
                text = text[:MAX_TEXT].rstrip() + "…"
            note = str(it.get("note") or "").strip()[:200]
            tags = clean_tags(it.get("tags"), warnings, f"{where}[{i}] ({name})") if gid not in GROUPS else []
            items.append({"name": name, "text": text if not tbc else tbc_text, "tbc": tbc,
                          "slide": slide_of(it.get("source_slide"), warnings, f"{where}[{i}] ({name})"),
                          "contested": bool(it.get("contested")), "note": note, "tags": tags})
        if not items:
            if gid not in GROUPS:
                warnings.append(f"lists.{gid} has no usable items; not shown")
            continue
        cap = MAX_ITEMS if rank else MAX_UNRANKED
        if len(items) > cap:
            why = "a longer list cannot be ranked" if rank else "a longer list is not readable on a phone"
            warnings.append(f"{where} has {len(items)} items; only the first {cap} are listed ({why})")
            items = items[:cap]
        tag_order: list[str] = []
        for it in items:
            for t in it["tags"]:
                if t not in tag_order:
                    tag_order.append(t)
        if filters and not tag_order:
            warnings.append(f"{where} asks for filters but no item carries tags; no filter row")
        out.append({"id": gid, "title": title, "kicker": kicker, "gnote": gnote, "items": items, "rank": rank,
                    "filters": tag_order if filters else [], "matters_label": mlabel, "custom": gid not in GROUPS,
                    "tag_label": tlabel, "plan_sheet": plan})
    names = [it["name"].lower() for g in out for it in g["items"]]
    if len(set(names)) != len(names):
        warnings.append("duplicate item names across the lists; reactions target by name, so make them unique")
    return out


def section_html(groups: list[dict]) -> str:
    multi = len(groups) > 1
    tabs = ""
    if multi:
        tabs = '  <div class="ls-tabs" role="tablist" aria-label="Lists">' + "".join(
            f'<button type="button" role="tab" id="lsTab-{g["id"]}" aria-controls="lsPanel-{g["id"]}" aria-selected="{"true" if k == 0 else "false"}" tabindex="{0 if k == 0 else -1}" data-g="{g["id"]}">{html.escape(g["title"])} <span class="ls-n">{len(g["items"])}</span></button>'
            for k, g in enumerate(groups)) + "</div>\n"
    panels = []
    for k, g in enumerate(groups):
        n = len(g["items"])
        top = min(RANK_MAX, n)
        lis = []
        for i, it in enumerate(g["items"]):
            slide_txt = ("slide " + str(it["slide"])) if it["slide"] is not None else "slide not recorded"
            tbc_cls = " tbc" if it["tbc"] else ""
            note = f'<small class="ls-note">{html.escape(it["note"])}</small>' if it["note"] else ""
            ct = '<span class="chip ls-ct">Still being discussed</span>' if it["contested"] else ""
            # A placeholder is never attributed to the presentation: the name is the slide's, the wording is not.
            src = (f"Wording not yet confirmed by the design team; the name is from the presentation, {slide_txt}" if it["tbc"]
                   else f"From the presentation, {slide_txt}")
            tags_attr = (f' data-tags="{html.escape(json.dumps(it["tags"], ensure_ascii=False))}"' if it["tags"] else "")
            tl = (g["tag_label"] + ": ") if g["tag_label"] else ""
            tags_html = ('<span class="ls-tags">' + "".join(f'<span class="ls-tag">{html.escape(tl + t)}</span>' for t in it["tags"]) + "</span>"
                         if it["tags"] else "")
            badge = '<span class="ls-rank" hidden></span>' if g["rank"] else '<span class="ls-mat" hidden>Matters to you</span>'
            matter = ("" if g["rank"] else
                      f'<button type="button" class="ls-matter" aria-pressed="false">{html.escape(g["matters_label"])}</button>')
            if g["plan_sheet"]:
                matter += '<button type="button" class="ls-plan">Show on plan</button>'
            lis.append(
                f'      <li class="ls-item{tbc_cls}" data-target="{html.escape(it["name"])}" data-slide="{html.escape(slide_txt)}"{tags_attr}>\n'
                f'        <button type="button" class="ls-head" aria-expanded="false" aria-controls="lsBody-{g["id"]}-{i}"><span class="ls-name">{html.escape(it["name"])}</span>{tags_html}{badge}</button>\n'
                f'        <div class="ls-body" id="lsBody-{g["id"]}-{i}" hidden>\n'
                f'          <p>{html.escape(it["text"])}</p>\n'
                f'          <small class="ls-src">{html.escape(src)}</small>{note}{ct}\n'
                f'          <div class="row"><button type="button" class="primary ls-react">Say what you think</button>{matter}<span class="chip ls-count" hidden><b>0</b> <span class="ls-cn">reactions</span> on this device</span></div>\n'
                f'          <div class="ls-mem" role="list" aria-label="Your reactions to {html.escape(it["name"])}"></div>\n'
                f'        </div>\n'
                f'      </li>'
            )
        panel_attrs = (f' role="tabpanel" id="lsPanel-{g["id"]}" aria-labelledby="lsTab-{g["id"]}"' if multi else "")
        if g["plan_sheet"]:
            panel_attrs += f' data-plan="{html.escape(g["plan_sheet"])}"'
        head = ""
        if g["kicker"]:
            head += f'    <p class="kicker ls-gk">{html.escape(g["kicker"])}</p>\n'
        if g["gnote"]:
            head += f'    <small class="ls-gnote">{html.escape(g["gnote"])}</small>\n'
        if g["filters"]:
            counts = {t: sum(1 for it in g["items"] if t in it["tags"]) for t in g["filters"]}
            head += (f'    <div class="ls-filters" role="group" aria-label="Show only the items tagged">'
                     f'<button type="button" data-tag="" aria-pressed="true">All <span class="ls-n">{n}</span></button>'
                     + "".join(f'<button type="button" data-tag="{html.escape(t)}" aria-pressed="false">{html.escape(t)} <span class="ls-n">{counts[t]}</span></button>'
                               for t in g["filters"])
                     + '</div>\n    <small class="ls-shown" aria-live="polite"></small>\n')
        if g["rank"]:
            tail = (
                f'    <div class="row ls-rankrow"><button type="button" class="primary ls-rankbtn">Rank my top {top}</button><span class="chip ls-ranked" hidden></span></div>\n'
                f'    <div class="ls-rankbox" hidden>\n'
                f'      <span class="kicker">Which matter most to you?</span>\n'
                f'      <span class="ls-sub">Tap up to {top}, in order</span>\n'
                f'      <div class="ls-picks" role="group" aria-label="Items to rank"></div>\n'
                f'      <div class="row"><button type="button" class="primary ls-save" disabled>Save my top {top}</button><button type="button" class="ls-cancel">Back</button></div>\n'
                f'    </div>\n')
        else:
            tail = '    <div class="row ls-matrow"><span class="chip ls-mats" hidden></span></div>\n'
        panels.append(
            f'  <div class="ls-group" data-g="{g["id"]}"{panel_attrs}{"" if k == 0 else " hidden"}>\n'
            + head +
            f'    <ol class="ls-items" aria-label="{html.escape(g["title"])}, {n} items">\n' + "\n".join(lis) + "\n    </ol>\n"
            f'    <div class="ls-other" hidden><small>Your notes on {html.escape(g["title"].lower())} as a whole</small><div class="ls-mem" role="list" aria-label="Your notes on {html.escape(g["title"].lower())} as a whole"></div></div>\n'
            + tail +
            f'  </div>'
        )
    any_custom = any(g["custom"] for g in groups)
    ranked, unranked = any(g["rank"] for g in groups), any(not g["rank"] for g in groups)
    if not any_custom and multi:
        lede = "The design team's own words, one item at a time. Tap an item to read it and {v} what you think; then rank the ones that matter most to you."
    elif not any_custom:
        lede = html.escape(groups[0]["title"]) + " in the design team's own words. Tap one to read it and {v} what you think; then rank the ones that matter most to you."
    elif ranked and unranked:
        lede = "One item at a time. Tap an item to read it and {v} what you think; rank the lists that ask for a ranking, and on the others mark the items that matter to you."
    elif ranked:
        lede = "One item at a time. Tap an item to read it and {v} what you think; then rank the ones that matter most to you."
    else:
        lede = "One item at a time. Tap an item to read it and {v} what you think, and mark the ones that matter to you."
    return (
        f'<section data-feature="list" data-title="Priorities" hidden>\n'
        f'  <h2>What matters most</h2>\n'
        f'  <p class="lede" data-with-voice="{html.escape(lede.format(v="say or type"))}" data-without-voice="{html.escape(lede.format(v="type"))}">{html.escape(lede.format(v="type"))}</p>\n'
        + tabs + "\n".join(panels) + "\n"
        f'</section>'
    )


STYLE = """<style data-feature="list">
/* ===== ek-list-reactions: the team's words as a ranked list ===== */
.ls-tabs{display:flex;gap:6px;margin:4px 0 14px;flex-wrap:wrap}
.ls-tabs button{min-height:44px;padding:8px 14px;border:1px solid var(--line);border-radius:var(--radius,6px);background:var(--card);color:var(--ink);display:inline-flex;align-items:center;gap:8px}
.ls-tabs button[aria-selected=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.ls-tabs .ls-n{display:inline-grid;place-items:center;min-width:22px;height:22px;border-radius:11px;background:var(--soft);color:var(--ink);font-size:12px;padding:0 6px}
.ls-tabs button[aria-selected=true] .ls-n{background:var(--paper);color:var(--ink)}
.ls-group[hidden],.ls-body[hidden],.ls-rank[hidden],.ls-count[hidden],.ls-ranked[hidden],.ls-rankbox[hidden],.ls-rankrow[hidden],.ls-other[hidden]{display:none}
.ls-other{margin-top:12px;display:flex;flex-direction:column;gap:6px} .ls-other small{color:var(--mute);font-size:14px}
.ls-items{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.ls-item{background:var(--card);border:1px solid var(--line);border-radius:var(--radius,6px);overflow:hidden;box-shadow:var(--float,none)}
.ls-item.tbc{border-style:dashed}
.ls-head{width:100%;min-height:56px;display:flex;align-items:center;gap:12px;padding:12px 14px;border:none;border-radius:0;background:transparent;color:var(--ink);text-align:left;font-size:18px;font-weight:500;line-height:1.2}
.ls-head:hover{background:var(--soft)} .ls-head:focus-visible{outline:3px solid var(--marker);outline-offset:-3px}
.ls-head[aria-expanded=true]{background:var(--soft)}
.ls-name{flex:1 1 auto;overflow-wrap:anywhere}
.ls-rank{flex:0 0 auto;display:inline-grid;place-items:center;min-width:34px;height:28px;padding:0 8px;border-radius:14px;background:var(--marker);color:var(--on-marker);font-size:13px}
.ls-body{padding:4px 14px 14px;display:flex;flex-direction:column;gap:8px;border-top:1px solid var(--line)}
.ls-body p{margin:8px 0 0;max-width:60ch;font-size:17px;line-height:1.45}
.ls-item.tbc .ls-body p{color:var(--mute);font-style:italic}
.ls-body small{color:var(--mute);font-size:14px} .ls-ct{align-self:flex-start}
.ls-mem{display:grid;gap:6px} .ls-mem:empty{display:none}
.ls-mem div{padding:8px 10px;border-left:3px solid var(--marker);background:var(--soft);border-radius:0 6px 6px 0;font-size:15px;overflow-wrap:anywhere}
.ls-mem audio{width:100%;max-width:320px;height:36px;display:block}
.ls-rankrow{margin-top:14px}
.ls-rankbox{margin-top:12px;background:var(--card);border:1px solid var(--line);border-radius:var(--radius,6px);padding:14px 16px;display:flex;flex-direction:column;gap:8px;box-shadow:var(--float,none)}
.ls-sub{font-size:18px;font-weight:500}
.ls-picks{display:flex;flex-wrap:wrap;gap:6px} .ls-picks button{min-height:44px;padding:6px 10px;font-size:14px;display:inline-flex;align-items:center;gap:6px;text-align:left}
.ls-picks button b{display:inline-grid;place-items:center;min-width:22px;height:22px;border-radius:11px;background:var(--marker);color:var(--on-marker);font-size:12px}
.ls-picks button[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)} .ls-picks button[aria-pressed=true] b{background:var(--paper);color:var(--ink)}
/* lists from brief.lists[]: kicker, filter chips, tags on the row, "matters" toggle */
.ls-gk{margin:0 0 6px} .ls-gnote{display:block;color:var(--mute);font-size:14px;margin:0 0 10px;max-width:60ch}
.ls-filters{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 6px}
.ls-filters button{min-height:44px;padding:6px 12px;border:1px solid var(--line);border-radius:var(--radius,6px);background:var(--card);color:var(--ink);font-size:14px;display:inline-flex;align-items:center;gap:6px}
.ls-filters button[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.ls-filters .ls-n{display:inline-grid;place-items:center;min-width:20px;height:20px;border-radius:10px;background:var(--soft);color:var(--ink);font-size:12px;padding:0 5px}
.ls-shown{display:block;color:var(--mute);font-size:14px;margin:0 0 10px} .ls-shown:empty{display:none}
.ls-item[hidden],.ls-mat[hidden],.ls-mats[hidden]{display:none}
.ls-head{flex-wrap:wrap;row-gap:6px}
.ls-tags{flex:0 0 auto;display:inline-flex;flex-wrap:wrap;gap:4px}
.ls-tag{padding:2px 8px;border:1px solid var(--line);border-radius:var(--radius,6px);background:var(--soft);color:var(--ink);font-size:12px;font-weight:300;line-height:1.4;white-space:nowrap}
.ls-mat{flex:0 0 auto;display:inline-grid;place-items:center;height:28px;padding:0 10px;border-radius:14px;background:var(--marker);color:var(--on-marker);font-size:13px}
.ls-matter{min-height:44px} .ls-matter[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.ls-matrow{margin-top:14px} .ls-matrow:has(.ls-mats[hidden]){display:none}
/* plan link: "Show on plan" on a row (lists with plan_sheet), and the line the list adds to the markup card */
.ls-plan[hidden],.ls-planlink[hidden]{display:none}
.ls-planlink{display:flex;flex-wrap:wrap;align-items:center;gap:6px 10px;font-size:13px;color:var(--mute)} .ls-planlink button{min-height:44px;font-size:14px}
</style>"""


SCRIPT = """<script data-feature="list">
(function listReactions() {
  const LS = %(data)s;  /* group ids, titles, item names (already in the markup); counts only otherwise */
  const sec = document.querySelector('section[data-feature="list"]');
  if (!sec) return;
  const groups = [...sec.querySelectorAll(".ls-group")], tabs = [...sec.querySelectorAll('.ls-tabs [role=tab]')];
  const hasVoice = () => EK.hasKind && EK.hasKind("voice");
  const mine = () => EK.reactions().filter(r => r.feature === "list");
  const rankOf = t => { const v = mine().filter(r => r.kind === "vote" && r.target === t && Number.isInteger(r.value) && r.value >= 1 && r.value <= 12).pop(); return v ? v.value : 0; };
  const mattersOf = t => mine().some(r => r.kind === "vote" && r.target === t && r.value === "matters");
  const renderNotes = (box, rs) => { box.textContent = "";
    rs.forEach(r => { const d = document.createElement("div"); d.setAttribute("role", "listitem");
      if (r.kind === "voice" && r.value && typeof r.value.mime === "string" && /^audio\\/[\\w.+-]+$/.test(r.value.mime) && typeof r.value.base64 === "string" && /^[A-Za-z0-9+\\/=]+$/.test(r.value.base64)) { const a = document.createElement("audio"); a.controls = true; a.src = "data:" + r.value.mime + ";base64," + r.value.base64; d.appendChild(a); const s = document.createElement("small"); s.textContent = (r.value.seconds || "?") + " s, voice"; d.appendChild(s); }
      else if (r.kind === "voice") d.textContent = "Unsupported voice note";
      else d.textContent = typeof r.value === "string" ? r.value : "Unsupported note";
      box.appendChild(d); }); };
  const gTitle = g => (LS.groups.find(x => x.id === g.dataset.g) || {}).title || "";
  const gTop = g => Math.min(5, g.querySelectorAll(".ls-item").length);
  let open = null;                                       /* the one expanded item */
  const cur = () => groups.find(g => !g.hidden) || groups[0];

  /* tabs: one list on screen at a time */
  function showGroup(id, focusTab) { groups.forEach(g => { g.hidden = g.dataset.g !== id; }); tabs.forEach(t => { const on = t.dataset.g === id; t.setAttribute("aria-selected", String(on)); t.tabIndex = on ? 0 : -1; if (on && focusTab) t.focus(); }); closeAll(); groupContext(); }
  function groupContext() { const g = cur(); if (g && EK.current() === "list") EK.context("list", gTitle(g).toLowerCase(), "\\u2014 tap an item to react to it", gTitle(g)); }
  tabs.forEach((t, i) => { t.addEventListener("click", () => showGroup(t.dataset.g)); t.addEventListener("keydown", e => { if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); const n = tabs[(i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length]; showGroup(n.dataset.g, true); } }); });

  /* items: an accordion; opening one sets the bar's context to it */
  function closeAll() { sec.querySelectorAll(".ls-head[aria-expanded=true]").forEach(h => { h.setAttribute("aria-expanded", "false"); document.getElementById(h.getAttribute("aria-controls")).hidden = true; }); open = null; }
  function openItem(li, focus) { const h = li.querySelector(".ls-head"), b = li.querySelector(".ls-body"); const was = h.getAttribute("aria-expanded") === "true"; closeAll(); if (was) { groupContext(); return; }
    h.setAttribute("aria-expanded", "true"); b.hidden = false; open = li; const g = li.closest(".ls-group");
    EK.context("list", li.dataset.target, "\\u2014 " + gTitle(g).toLowerCase() + " \\u00b7 " + li.dataset.slide); if (focus) h.focus(); }
  sec.querySelectorAll(".ls-item").forEach(li => { const h = li.querySelector(".ls-head"); h.addEventListener("click", () => openItem(li));
    li.querySelector(".ls-react").addEventListener("click", () => { if (open !== li) openItem(li); EK.context("list", li.dataset.target, "\\u2014 what do you think of this?"); EK.focusNote(); EK.toast(hasVoice() ? "Speak or type below" : "Type below"); }); });
  sec.addEventListener("keydown", e => { if (e.key === "Escape" && open) { const h = open.querySelector(".ls-head"); closeAll(); groupContext(); h.focus(); } });

  /* this device's reactions per item, escaped on render */
  function render() { const R = mine();
    sec.querySelectorAll(".ls-item").forEach(li => { const t = li.dataset.target; const rs = R.filter(r => r.target === t && r.kind !== "vote"); const box = li.querySelector(".ls-mem"), chip = li.querySelector(".ls-count"), rk = rankOf(t), badge = li.querySelector(".ls-rank");
      const mb = li.querySelector(".ls-matter"), mt = mb ? mattersOf(t) : false;
      renderNotes(box, rs);
      chip.hidden = !rs.length; chip.querySelector("b").textContent = rs.length; chip.querySelector(".ls-cn").textContent = rs.length === 1 ? "reaction" : "reactions";
      if (badge) { badge.hidden = !rk; badge.textContent = rk ? "#" + rk : ""; badge.setAttribute("aria-label", rk ? "you ranked this " + rk : ""); }
      if (mb) { mb.setAttribute("aria-pressed", String(mt)); li.querySelector(".ls-mat").hidden = !mt; }
      const tg = [...li.querySelectorAll(".ls-tag")].map(s => s.textContent).join(", ");
      li.querySelector(".ls-head").setAttribute("aria-label", t + (tg ? ", " + tg : "") + (rk ? ", you ranked it " + rk : "") + (mt ? ", it matters to you" : "") + (rs.length ? ", " + rs.length + " reaction" + (rs.length === 1 ? "" : "s") + " on this device" : "")); });
    groups.forEach(g => { const lis = [...g.querySelectorAll(".ls-item")]; const c = g.querySelector(".ls-ranked"), cm = g.querySelector(".ls-mats");
      if (c) { const n = lis.filter(li => rankOf(li.dataset.target)).length; c.hidden = !n; c.textContent = n ? "You ranked " + n + " (this phone)" : ""; }
      if (cm) { const n = lis.filter(li => mattersOf(li.dataset.target)).length; cm.hidden = !n; cm.textContent = n ? "You marked " + n + " as mattering (this phone)" : ""; }
      /* notes made with the list itself (or its ranking) as context, so nothing stored is invisible */
      const tl = gTitle(g).toLowerCase(); const other = R.filter(r => r.kind !== "vote" && (r.target === tl || r.target === "ranking: " + tl)); const ob = g.querySelector(".ls-other"); renderNotes(ob.querySelector(".ls-mem"), other); ob.hidden = !other.length; }); }
  EK.on("ek:reaction", render); render();

  /* "this matters to me": one toggle per item on lists without a ranking */
  sec.querySelectorAll(".ls-matter").forEach(b => { const t = b.closest(".ls-item").dataset.target;
    b.addEventListener("click", () => { const ex = mine().filter(r => r.kind === "vote" && r.target === t && r.value === "matters");
      if (ex.length) { ex.forEach(r => EK.remove(r.id)); EK.toast("Unmarked"); return; }
      EK.toast(EK.react({ feature: "list", target: t, kind: "vote", value: "matters" }) ? "Marked on this phone" : "Could not save on this phone (storage full?)"); }); });

  /* filter chips: show only the items carrying one tag */
  groups.forEach(g => { const fb = [...g.querySelectorAll(".ls-filters button")]; if (!fb.length) return; const lis = [...g.querySelectorAll(".ls-item")], shown = g.querySelector(".ls-shown");
    const tagsOf = li => { try { const v = JSON.parse(li.dataset.tags || "[]"); return Array.isArray(v) ? v : []; } catch (e) { return []; } };
    function apply(tag) { fb.forEach(b => b.setAttribute("aria-pressed", String((b.dataset.tag || "") === tag))); let n = 0;
      lis.forEach(li => { const on = !tag || tagsOf(li).includes(tag); li.hidden = !on; if (on) n++; });
      if (open && open.hidden) { closeAll(); groupContext(); }
      shown.textContent = tag ? "Showing " + n + " of " + lis.length + ": " + tag : ""; }
    fb.forEach(b => b.addEventListener("click", () => apply(b.dataset.tag || ""))); g._filter = apply; });

  /* plan link (lists with plan_sheet): a row shows its sheet in "Mark up plans"; EK.feature.markup is looked up at click time */
  const hasMarkup = !!document.querySelector('section[data-feature="markup"]');
  sec.querySelectorAll(".ls-plan").forEach(b => { const li = b.closest(".ls-item"), g = li.closest(".ls-group");
    if (!hasMarkup) { b.hidden = true; return; }
    b.addEventListener("click", () => { const M = EK.feature && EK.feature.markup, name = g.dataset.plan;
      if (!M || typeof M.show !== "function") { EK.toast("The plan is not in this tool"); return; }
      EK.show("markup"); if (!M.show(name)) { EK.toast("That plan is not in this tool"); return; }
      const m = /\\d+/.exec(li.dataset.target); EK.toast(m ? "Find tag " + m[0] + " on the plan" : "Shown on " + name); }); });
  /* and the way back: a line in the markup card while the sheet on screen is some list's plan_sheet */
  const plans = LS.groups.filter(x => x.plan), slot = document.querySelector('section[data-feature="markup"] [data-slot="plan-list"]');
  if (slot && plans.length) { slot.textContent = ""; const line = document.createElement("div"), txt = document.createElement("span"), go = document.createElement("button"); let back = null;
    line.className = "ls-planlink"; line.hidden = true; go.type = "button"; go.textContent = "Go to the list"; line.append(txt, go); slot.appendChild(line);
    const sync = () => { const c = document.querySelector('section[data-feature="markup"] .dm-chip[aria-pressed=true]'); back = c ? plans.find(x => x.plan === c.textContent) || null : null; line.hidden = !back; if (back) { txt.textContent = "The numbered tags are listed under Priorities \\u2192 " + back.title; go.setAttribute("aria-label", "Go to " + back.title + " under Priorities"); } };
    go.addEventListener("click", () => { if (!back) return; EK.show("list"); EK.feature.list.show(back.id); });
    EK.on("ek:context", sync); EK.on("ek:show", id => { if (id === "markup") sync(); }); sync(); }
  EK.feature = EK.feature || {};
  EK.feature.list = { show: id => { if (!groups.some(g => g.dataset.g === id)) return false; showGroup(id); return true; } };

  /* ranking, per list (lists with rank:false have no ranking panel) */
  groups.filter(g => g.querySelector(".ls-rankbtn")).forEach(g => { const btn = g.querySelector(".ls-rankbtn"), box = g.querySelector(".ls-rankbox"), picksEl = g.querySelector(".ls-picks"), save = g.querySelector(".ls-save"), cancel = g.querySelector(".ls-cancel"), row = g.querySelector(".ls-rankrow");
    const names = [...g.querySelectorAll(".ls-item")].map(li => li.dataset.target); const top = gTop(g); let picks = [];
    function drawPicks() { picksEl.textContent = ""; names.forEach(n => { const b = document.createElement("button"); b.type = "button"; const i = picks.indexOf(n); b.setAttribute("aria-pressed", String(i >= 0)); const tag = document.createElement("b"); tag.textContent = i >= 0 ? String(i + 1) : "+"; b.appendChild(tag); b.appendChild(document.createTextNode(n)); b.setAttribute("aria-label", n + (i >= 0 ? ", ranked " + (i + 1) : ", not ranked")); b.addEventListener("click", () => { const k = picks.indexOf(n); if (k >= 0) picks.splice(k, 1); else if (picks.length < top) picks.push(n); else { EK.toast(top + " chosen \\u2014 remove one first"); return; } drawPicks(); }); picksEl.appendChild(b); }); save.disabled = !picks.length; save.textContent = picks.length ? "Save my top " + picks.length : "Save my top " + top; }
    btn.addEventListener("click", () => { picks = names.map(n => ({ n, r: rankOf(n) })).filter(x => x.r).sort((a, b) => a.r - b.r).map(x => x.n).slice(0, top); drawPicks(); closeAll(); row.hidden = true; box.hidden = false; picksEl.querySelector("button").focus(); EK.context("list", "ranking: " + gTitle(g).toLowerCase(), "\\u2014 tap items in order of importance", "your ranking"); });
    cancel.addEventListener("click", () => { box.hidden = true; row.hidden = false; btn.focus(); groupContext(); });
    save.addEventListener("click", () => { const old = mine().filter(r => r.kind === "vote" && Number.isInteger(r.value) && names.includes(r.target)); const made = [];
      /* record the new ranking first; the old one goes only once every new vote is stored */
      for (const [i, n] of picks.entries()) { const rec = EK.react({ feature: "list", target: n, kind: "vote", value: i + 1 }); if (!rec) { made.forEach(r => EK.remove(r.id)); EK.toast("Could not save on this phone (storage full?); your earlier ranking is kept"); return; } made.push(rec); }
      old.forEach(r => EK.remove(r.id)); EK.toast("Ranking saved on this phone"); cancel.click(); });
    g._rank = { open: () => btn.click(), close: () => cancel.click() }; });

  EK.on("ek:show", id => { if (id === "list") groupContext(); });
  if (EK.current() === "list") groupContext();

  /* tour */
  const first = groups[0], firstLi = first && first.querySelector(".ls-item");
  const custom = LS.groups.some(g => g.custom), named = LS.groups.map(g => g.n + " " + (g.id === "program" ? "parts of the plan" : g.title.toLowerCase()));
  const steps = [
    { go: "list", do: () => { if (tabs.length) showGroup(first.dataset.g); if (firstLi) openItem(firstLi); }, undo: () => closeAll(), text: "Priorities: " + (named.length > 2 ? named.slice(0, -1).join(", ") + " and " + named[named.length - 1] : named.join(" and ")) + (custom ? "" : ", in the design team\\u2019s own words") + ". Tap one to read it and say what you think." }
  ];
  const ranker = groups.find(g => g._rank), marker = groups.find(g => g.querySelector(".ls-matter"));
  if (ranker) steps.push({ go: "list", do: () => { if (tabs.length) showGroup(ranker.dataset.g); ranker._rank.open(); }, undo: () => ranker._rank.close(), text: "Then rank the ones that matter most to you: tap them in order and save. Your ranking stays on this phone until the team collects it." });
  if (marker) steps.push({ go: "list", do: () => { if (tabs.length) showGroup(marker.dataset.g); openItem(marker.querySelector(".ls-item")); }, undo: () => closeAll(), text: gTitle(marker) + " has no ranking: mark the items that matter to you, one by one" + (marker._filter ? ", and use the chips to show only some of them" : "") + ". Marks stay on this phone until the team collects them." });
  if (groups.length > 1 && groups[1] !== marker && groups[1] !== ranker) steps.push({ go: "list", do: () => showGroup(groups[1].dataset.g, true), undo: () => showGroup(first.dataset.g), text: "The second list works the same way: " + gTitle(groups[1]).toLowerCase() + "." });
  EK.registerTour(steps);
})();
</script>"""


def splice(doc: str, section: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="list">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="list">.*?</script>', "", doc, flags=re.S)
    sec_re = re.compile(r'<section data-feature="list"[^>]*>.*?</section>', re.S)
    if not sec_re.search(doc):
        raise SystemExit("no <section data-feature=\"list\"> slot in the output; is ek-list-reactions installed in the manifest and the shell built?")
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
    ap.add_argument("--groups", default="auto", help="auto (principles, program, then brief.lists[] in order), or a comma list of: principles, program, <list id> (in display order)")
    args = ap.parse_args(argv)
    for p in (args.brief, args.out):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    brief = json.loads(args.brief.read_text(encoding="utf-8-sig"))
    doc = args.out.read_text(encoding="utf-8")
    warnings: list[str] = []
    lists = custom_lists(brief, warnings)
    if args.groups == "auto":
        wanted = [g for g in ("principles", "program") if brief.get(g)] + list(lists)
    else:
        wanted = []
        for g in (x.strip() for x in args.groups.split(",")):
            if g and g not in wanted:
                wanted.append(g)
        bad = [g for g in wanted if g not in GROUPS and g not in lists]
        if bad:
            sys.exit(f"unknown group(s) {bad}; choose from {list(GROUPS) + list(lists)}")
    groups = groups_from_brief(brief, wanted, warnings, lists)
    if not groups:
        for w in warnings:
            log(f"warning: {w}")
        if args.groups != "auto":
            sys.exit(f"the brief has none of the requested groups {wanted}")
        sys.exit("the brief has no principles, no program items and no usable lists; ek-project-manifest should not have installed ek-list-reactions")
    data = {"groups": [{"id": g["id"], "title": g["title"], "n": len(g["items"])} | ({"custom": True, "rank": g["rank"]} if g["custom"] else {})
                       | ({"plan": g["plan_sheet"]} if g["plan_sheet"] else {}) for g in groups]}
    new_doc = splice(doc, section_html(groups), STYLE, SCRIPT.replace("%(data)s", json_inline(data), 1))
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")),
                      "groups": [{"id": g["id"], "items": len(g["items"]), "to_confirm": sum(1 for it in g["items"] if it["tbc"]),
                                  "rank": g["rank"], "filters": g["filters"]} for g in groups],
                      "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
