#!/usr/bin/env python3
"""
ek-sync — send every reaction to one shared record as it is made, and let the admin portal read that record.

  python skills/ek-sync/build.py --manifest project.config.json --out output/index.html                  # user portal
  python skills/ek-sync/build.py --manifest project.config.json --out output/admin/index.html --portal admin

Run it last, after the chain (and after ek-admin for the admin portal). It needs the manifest's data.sync_target:

  "data": { "sync_target": { "url": "/api", "held_by": "a computer the design team runs", "retention": "deleted when the project closes" } }

`url` is https://…, or http://localhost (127.0.0.1, name.localhost) for testing, or a path on the page's own
address ("/api"). `held_by` and `retention` are printed in the page's privacy card, so they must be true.

User portal: inserts <script data-feature="sync"> at <!-- ek:scripts --> and rewrites the privacy card: the page
may no longer say that nothing leaves the device. The script keeps the shared record equal to this device's own
(adds, and removals when the visitor removes), retries when the store cannot be reached, and shows how many
reactions have been sent. Reactions stay on the device as before; the device is still the visitor's own copy.

Admin portal: the script adds a "Shared record" card to the Admin section: the team's token (kept for this tab
only), a Load button and an optional refresh. What it loads goes through ek-admin's own checks (EK.admin.load).

Manifest strings are data: HTML-escaped into markup, JSON-encoded (</ neutralised) into the inline object.
Idempotent: re-running replaces the script; the privacy card is rewritten from the manifest each time.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

URL_RE = re.compile(r"^(https://[A-Za-z0-9.-]+(:\d{1,5})?(/[A-Za-z0-9._~/-]*)?"
                    r"|http://(localhost|127\.0\.0\.1|[a-z0-9-]{1,40}\.localhost)(:\d{1,5})?(/[A-Za-z0-9._~/-]*)?"
                    r"|/[A-Za-z0-9._~/-]*)$")


def log(msg: str) -> None:
    print(f"[ek-sync] {msg}", file=sys.stderr)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


USER = r"""<script data-feature="sync">
(function sync() {
  const SY = __SY_DATA__;  /* the store's address; DATA */
  if (!window.EK || !EK.project || EK.project.portal === "admin") return;   /* the team's own page never writes to the visitors' record */
  const slug = EK.project.slug, base = String(SY.url).replace(/\/+$/, "");
  const devKey = "ek:" + slug + ":device", sentKey = "ek:" + slug + ":sync-sent";
  /* the device id is the only thing that lets this device remove what it sent, so it is made from the browser's
     random source; ek-feedback-synthesis reads the same key for its export */
  let memDev = "";
  const newDev = () => { try { const a = new Uint8Array(12); crypto.getRandomValues(a); return Array.from(a, x => (x % 36).toString(36)).join(""); } catch (e) { return Math.random().toString(36).slice(2, 10) + Math.random().toString(36).slice(2, 6); } };
  const getDev = () => { try { let d = localStorage.getItem(devKey) || ""; if (!/^[A-Za-z0-9_-]{1,40}$/.test(d)) { d = newDev(); localStorage.setItem(devKey, d); } return d; } catch (e) { return memDev || (memDev = newDev()); } };
  getDev();
  /* the secret that proves an add or a removal comes from this browser: sent with every operation, kept by the store
     only as a hash, never exported and never shown. The device id is a label; this is the credential. */
  const secKey = "ek:" + slug + ":sync-key"; let memSec = "";
  const newSec = () => { const a = new Uint8Array(16); crypto.getRandomValues(a); return Array.from(a, x => x.toString(16).padStart(2, "0")).join(""); };
  const getSec = () => { try { let k = localStorage.getItem(secKey) || ""; if (!/^[a-f0-9]{32}$/.test(k)) { k = newSec(); localStorage.setItem(secKey, k); } return k; } catch (e) { return memSec || (memSec = newSec()); } };
  /* sent: reaction id -> the device id it was sent under (the device id can be reset; the removal still needs the old one).
     Read again before every pass, so a second tab on the same address does not work from a stale copy. */
  let sent = Object.create(null);
  const readSent = () => { try { const s = JSON.parse(localStorage.getItem(sentKey) || "{}"); const o = Object.create(null); if (s && typeof s === "object" && !Array.isArray(s)) Object.keys(s).forEach(k => { if (typeof s[k] === "string") o[k] = s[k]; }); sent = o; } catch (e) {} };
  readSent();
  const saveSent = () => { try { localStorage.setItem(sentKey, JSON.stringify(sent)); } catch (e) {} };
  const refused = Object.create(null);   /* the store said this record is not acceptable; not retried in this visit */
  const mine = () => EK.reactions().filter(r => r.tour !== true);
  function plan() { const want = new Map(); mine().forEach(r => want.set(r.id, r));
    const adds = []; want.forEach((r, id) => { if (!sent[id] && !refused[id]) adds.push(r); });
    const rem = Object.create(null); Object.keys(sent).forEach(id => { if (!want.has(id)) (rem[sent[id]] = rem[sent[id]] || []).push(id); });
    return { adds, rem }; }
  const pendingRemovals = () => { const have = new Set(mine().map(r => r.id)); return Object.keys(sent).filter(id => !have.has(id)).length; };
  async function post(body) { const text = JSON.stringify(body);
    const res = await fetch(base + "/r", { method: "POST", headers: { "Content-Type": "text/plain;charset=UTF-8" }, body: text, keepalive: text.length < 60000, credentials: "omit", cache: "no-store", referrerPolicy: "no-referrer" });
    let j = null; try { j = await res.json(); } catch (e) {}
    return { ok: res.ok && !!j && j.ok === true, status: res.status, error: j && typeof j.error === "string" ? j.error : "" }; }
  const permanent = r => r.status === 400 || r.status === 403 || r.status === 413 || r.status === 422;
  let running = false, again = false, timer = 0, fails = 0, lastError = "";
  async function flush() { if (running) { again = true; return; } running = true; clearTimeout(timer);
    try { for (;;) { again = false; readSent(); const p = plan(); const rdevs = Object.keys(p.rem); if (!p.adds.length && !rdevs.length) break;
        for (const dev of rdevs) { const ids = p.rem[dev].slice(0, 2000); const r = await post({ v: 1, slug, device: dev, key: getSec(), op: "remove", ids }); if (!r.ok && !permanent(r)) throw r; ids.forEach(id => delete sent[id]); saveSent(); status(); }
        for (const rec of p.adds) { const dev = getDev(); const r = await post({ v: 1, slug, device: dev, key: getSec(), op: "add", record: { feature: rec.feature, target: rec.target, kind: rec.kind, value: rec.value === undefined ? null : rec.value, id: rec.id, ts: rec.ts } });
          if (r.ok) sent[rec.id] = dev; else if (permanent(r)) refused[rec.id] = r.error || String(r.status); else throw r; saveSent(); status(); } }
      fails = 0; lastError = ""; }
    catch (e) { fails++; lastError = e && e.status === 429 ? "busy" : "unreachable"; timer = setTimeout(flush, Math.min(60000, 3000 * Math.pow(2, Math.min(fails, 4)))); }
    running = false; status(); if (again && !fails) flush(); }
  /* what the visitor is told: how many of this device's reactions the team's record holds */
  let chip = null;
  function status() { if (!chip) return; const all = mine(); const ok = all.filter(r => sent[r.id]).length; const no = all.filter(r => refused[r.id]).length; const wait = all.length - ok - no; const gone = pendingRemovals();
    chip.textContent = (!all.length ? (gone ? "Nothing left on this device" : "Nothing to send yet") : "Sent to the team: " + ok + " of " + all.length + (wait ? (lastError ? " \u00b7 " + wait + " waiting, will try again" : " \u00b7 sending") : "") + (no ? " \u00b7 " + no + " not accepted" : ""))
      + (gone ? " \u00b7 " + gone + " removal" + (gone === 1 ? "" : "s") + (lastError ? " not yet passed on, will try again" : " being passed on") : "");
    chip.classList.toggle("warn", !!((wait || gone) && lastError) || !!no); }
  function mount() { const row = document.querySelector(".card.privacy .row"); if (row && !document.getElementById("syncChip")) { chip = document.createElement("span"); chip.className = "chip"; chip.id = "syncChip"; chip.setAttribute("role", "status"); row.appendChild(chip); } status(); }
  EK.sync = { flush, state: () => { const all = mine(); return { device: getDev(), total: all.length, sent: all.filter(r => sent[r.id]).length, refused: Object.keys(refused).length, removals_pending: pendingRemovals(), error: lastError }; } };
  EK.on("ek:reaction", () => { flush(); });
  window.addEventListener("storage", ev => { if (ev.key === sentKey) { readSent(); status(); } });
  window.addEventListener("online", flush);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") flush(); });
  if (document.readyState === "complete") { mount(); flush(); } else window.addEventListener("load", () => { mount(); flush(); });
})();
</script>"""


ADMIN = r"""<script data-feature="sync">
(function syncAdmin() {
  const SY = __SY_DATA__;  /* the store's address; DATA */
  if (!window.EK || !EK.project || EK.project.portal !== "admin") return;
  const slug = EK.project.slug, base = String(SY.url).replace(/\/+$/, ""), tokKey = "ek:" + slug + ":synctoken";
  function start() { const sec = document.querySelector('section[data-feature="admin"]'); if (!sec || !EK.admin || typeof EK.admin.load !== "function") return;
    const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
    const card = el("div", "card ad-card"); card.id = "syCard";
    card.appendChild(el("h3", "", "Shared record"));
    card.appendChild(el("p", "ad-note", "Every device sends its reactions to the shared record as they are made (" + SY.held_by + "). Load it here to read everyone's reactions at once. The token is the team's; it stays in this tab and is sent only to the record's address. What is loaded stays in this browser's memory, as with files."));
    const form = el("form", "ad-key"); const lb = el("label", "kicker", "Team token"); lb.htmlFor = "syToken";
    const tok = el("input"); tok.type = "password"; tok.id = "syToken"; tok.autocomplete = "off"; tok.spellcheck = false;
    const go = el("button", "primary", "Load the shared record"); go.type = "submit";
    const forget = el("button", "", "Forget token"); forget.type = "button";
    const row = el("div", "row"); row.append(tok, go, forget); form.append(lb, row);
    const auto = el("label", "ad-toggle"); const cb = el("input"); cb.type = "checkbox"; cb.id = "syAuto"; auto.append(cb, el("span", "", "Load again every 30 seconds while this page is open"));
    const state = el("p", "ad-note"); state.setAttribute("role", "status"); state.textContent = "Not loaded yet.";
    card.append(form, auto, state);
    const first = sec.querySelector(".ad-card"); if (first) sec.insertBefore(card, first); else sec.appendChild(card);
    let token = ""; try { token = sessionStorage.getItem(tokKey) || ""; } catch (e) {}
    const hasTok = () => { tok.placeholder = token ? "kept for this tab" : "paste the token"; forget.disabled = !token; };
    hasTok();
    let busy = false, timer = 0;
    async function load(quiet) { if (busy) return; if (!token) { state.textContent = "Enter the team token first."; return; } busy = true; go.disabled = true; if (!quiet) state.textContent = "Loading\u2026";
      try { const res = await fetch(base + "/records?slug=" + encodeURIComponent(slug), { headers: { "X-EK-Admin": token }, credentials: "omit", cache: "no-store", referrerPolicy: "no-referrer" });
        let j = null; try { j = await res.json(); } catch (e) {}
        if (res.status === 403) { token = ""; try { sessionStorage.removeItem(tokKey); } catch (e) {} hasTok(); state.textContent = "The token was refused and has not been kept."; stop(); }
        else if (!res.ok || !j || j.ok !== true || !Array.isArray(j.exports)) state.textContent = "The shared record did not answer as expected (" + res.status + ").";
        else { const n = EK.admin.load(j.exports, { source: "shared record", replace: true }); const total = j.exports.reduce((a, e) => a + (e && Array.isArray(e.reactions) ? e.reactions.length : 0), 0);
          state.textContent = "Loaded " + total + " reaction" + (total === 1 ? "" : "s") + " from " + n + " device" + (n === 1 ? "" : "s") + " at " + new Date().toLocaleTimeString([], { timeStyle: "short" }) + "." + (n < j.exports.length ? " " + (j.exports.length - n) + " device record(s) did not pass the checks; see the table below." : ""); } }
      catch (e) { state.textContent = "The shared record could not be reached."; }
      busy = false; go.disabled = false; }
    const stop = () => { clearInterval(timer); timer = 0; cb.checked = false; };
    form.addEventListener("submit", ev => { ev.preventDefault(); const v = tok.value.trim(); tok.value = ""; if (v) { token = v; try { sessionStorage.setItem(tokKey, v); } catch (e) {} hasTok(); } load(false); });
    forget.addEventListener("click", () => { token = ""; try { sessionStorage.removeItem(tokKey); } catch (e) {} stop(); hasTok(); state.textContent = "Token forgotten. What was loaded stays until you reload the page or press Forget loaded files."; });
    const clr = document.getElementById("adClear"); if (clr) clr.addEventListener("click", () => { stop(); state.textContent = "Forgotten. Press Load to read the shared record again."; });
    cb.addEventListener("change", () => { clearInterval(timer); timer = 0; if (cb.checked) { if (!token) { cb.checked = false; state.textContent = "Enter the team token first."; return; } timer = setInterval(() => { if (document.visibilityState === "visible") load(true); }, 30000); load(true); } });
  }
  if (document.readyState === "complete") start(); else window.addEventListener("load", start);
})();
</script>"""

STYLE = """<style data-feature="sync">
/* ===== ek-sync ===== */
#syncChip.warn{border-color:var(--marker);color:var(--marker)}
</style>"""


STAY_PHRASES = (
    ("Nothing leaves the phone until the design team asks for it; download it for them here",
     "Everything here has also been sent to the design team's shared record; you can download your own copy here"),
    ("the photo stays on this phone until you hand it to the team", "the photo is kept on this phone and sent to the design team's shared record"),
    (" until the team collects them.", " and are sent to the design team's shared record."),
    (" until the team collects it.", " and is sent to the design team's shared record."),
    ("<h3>Hand it to the design team</h3>", "<h3>Keep your own copy</h3>"),
    ("One file with everything on this phone for the team to merge with the others.",
     "One file with everything on this phone. The design team already has it through the shared record."),
    ("Download for the team", "Download my copy"),
)
STAY_RE = re.compile(r"until the (design )?team (collects|asks)|Nothing leaves the (phone|device)|until you hand it|collects it from the device|Nothing is sent anywhere")

ADMIN_PRIVACY = ("This is the design team's portal. A note typed on this page stays in this browser and is not sent to the shared record. "
                 "Visitors' reactions reach the shared record from the visitors' page, and are read here under Admin.")


def privacy_text(target: dict, ai_team: bool) -> str:
    held = str(target.get("held_by") or "").strip()
    keep = str(target.get("retention") or "").strip()
    t = ("Everything you add (notes, choices, rankings, marks on drawings and any photo of a sketch) is kept on this device and "
         "sent to the design team's shared record as you add it"
         + (f" ({held})" if held else "") + ". "
         "It carries a random id for this device, not your name, so the team can tell devices apart. "
         "Other visitors cannot see what you add. "
         "Remove something here and it is removed from the team's record too, the next time this browser can reach the record; "
         "if you clear this browser's data first, ask the team to remove it. ")
    if keep:
        t += f"The record is {keep}. "
    t += "No name or contact is asked for; please don't add other people's."
    if ai_team:
        t += " The design team may use an AI service (Anthropic) to help read the collected reactions; your words are sent to it then."
    return t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--portal", choices=("user", "admin"), default="user")
    args = ap.parse_args(argv)
    for p in (args.manifest, args.out):
        if not p.is_file():
            sys.exit(f"not a file: {p}")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    target = (manifest.get("data") or {}).get("sync_target")
    if isinstance(target, str):
        target = {"url": target}
    if not isinstance(target, dict) or not isinstance(target.get("url"), str):
        sys.exit('[ek-sync] refused: the manifest has no data.sync_target {"url": …}. Without one, reactions stay on the device.')
    url = target["url"].strip()
    if not URL_RE.match(url):
        sys.exit("[ek-sync] refused: sync_target.url must be https://…, http://localhost… for testing, or a path on the page's own address.")
    if any(re.search(r"(token|key|secret|password)", str(k), re.I) for k in target):
        sys.exit("[ek-sync] refused: sync_target carries a field that looks like a token or key. The team token is never in the manifest or the page.")
    warnings: list[str] = []
    for k in ("held_by", "retention"):
        if not str(target.get(k) or "").strip():
            warnings.append(f"sync_target.{k} is empty; the privacy card cannot say it")
    doc = args.out.read_text(encoding="utf-8")
    m = re.search(r"const PROJECT = (\{.*?\});\n", doc)
    page_admin = bool(m and re.search(r'"portal":\s*"admin"', m.group(1)))
    if page_admin != (args.portal == "admin"):
        sys.exit(f"[ek-sync] refused: --portal is {args.portal!r} but the page in --out was built as {'an admin' if page_admin else 'a user'} portal.")
    doc = re.sub(r'\n?<script data-feature="sync">.*?</script>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<style data-feature="sync">.*?</style>', "", doc, flags=re.S)
    for marker in ("<!-- ek:scripts -->", "<!-- ek:styles -->"):
        if marker not in doc:
            sys.exit(f"[ek-sync] shell marker {marker} missing from the output")
    data = {"url": url, "held_by": str(target.get("held_by") or "the design team's store")[:120]}
    script = (ADMIN if args.portal == "admin" else USER).replace("__SY_DATA__", json_inline(data), 1)
    if args.portal == "admin" and '<script data-feature="admin">' not in doc:
        sys.exit("[ek-sync] refused: no Admin section in the page; build the admin portal (ek-admin) first.")
    doc = doc.replace("<!-- ek:scripts -->", "<!-- ek:scripts -->\n" + script, 1)
    doc = doc.replace("<!-- ek:styles -->", "<!-- ek:styles -->\n" + STYLE, 1)
    # The privacy card: one paragraph with the text and its two variants as attributes (the shell picks one on load).
    chat = manifest.get("chat") if isinstance(manifest.get("chat"), dict) else {}
    text = html.escape(ADMIN_PRIVACY if args.portal == "admin" else privacy_text(target, bool(chat)), quote=True)
    # The shell prints it under the same heading in the welcome card and in the first-visit intro; both are rewritten.
    pat = re.compile(r'(<h3>What happens to what you add</h3>\s*)<p data-with-voice="[^"]*" data-without-voice="[^"]*">[^<]*</p>')
    doc, hits = pat.subn(lambda m_: f'{m_.group(1)}<p data-with-voice="{text}" data-without-voice="{text}">{text}</p>', doc)
    # The feature sections were written for a page that keeps everything on the device; their own sentences that say so
    # are replaced (they sit in markup and in tour strings). Until the feature skills read data.sync_target themselves.
    for old, new in STAY_PHRASES:
        doc = doc.replace(old, new)
    left = STAY_RE.search(doc)
    if not hits or left:
        sys.exit("[ek-sync] refused: the page would still say that reactions stay on the device"
                 + (f" (found: {left.group(0)!r})" if left else " (the privacy card was not found)") + ". Nothing was written.")
    installed = [i.get("skill") for i in (manifest.get("install") or []) if isinstance(i, dict)]
    if "ek-voice-reactions" in installed:
        warnings.append("ek-voice-reactions is installed: the rewritten privacy card no longer says where Speak sends sound; add it by hand")
    if manifest.get("demo") is True:
        warnings.append("manifest.demo is true: a demonstration that nobody collects from must not have a sync target")
    args.out.write_text(doc, encoding="utf-8", newline="\n")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(doc.encode("utf-8")), "portal": args.portal, "url": url, "warnings": len(warnings)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
