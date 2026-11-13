#!/usr/bin/env python3
"""
ek-model-pins — let visitors drop pins on the ek-site-model 3D view: "where should it go?" and "what about this spot?".

  python skills/ek-model-pins/build.py --brief work/brief.json --out output/index.html

Augment, no section. Inserts <style data-feature="pins"> at <!-- ek:styles --> and <script data-feature="pins">
immediately after <script data-feature="model">, so it runs once EK.feature.model exists. Idempotent. Needs the
model's extension point (scene, ground(), onPick, onRender, project, bbox, span, the #smSlot row in its card);
refuses an output whose model block predates it.
The only brief data read is program[].name, offered as "Welcome <name> here" when no model building carries
that name. Names are JSON-encoded (</ neutralised) and rendered with textContent; visitor text likewise.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FEATURE = "pins"
MAX_NAMES = 24
MAX_NAME = 60
MODEL_SCRIPT = re.compile(r'<script data-feature="model">.*?</script>', re.S)


def json_inline(obj) -> str:
    return (json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


def program_names(brief: dict, warnings: list[str]) -> list[str]:
    out, seen = [], set()
    for p in brief.get("program") or []:
        name = p.get("name") if isinstance(p, dict) else p if isinstance(p, str) else None
        if not isinstance(name, str):
            continue
        # The team's model labels and the deck's names differ ("Three Monastic Retreat Cabins" are the "Hermitage cabin"
        # instances), and some program elements are not buildings (a road). The brief says so explicitly:
        # in_model: true = already in the model; pinnable: false = not something to place with a pin.
        if isinstance(p, dict) and (p.get("in_model") is True or p.get("pinnable") is False):
            continue
        name = " ".join(name.split())[:MAX_NAME]
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    if len(out) > MAX_NAMES:
        warnings.append(f"{len(out)} program elements; only the first {MAX_NAMES} are offered")
        out = out[:MAX_NAMES]
    return out


STYLE = """<style data-feature="pins">
/* ===== ek-model-pins: visitor pins on the site model ===== */
.pn-labels{position:absolute;inset:0;pointer-events:none;overflow:hidden}
.pn-lbl{position:absolute;transform:translate(-50%,-100%);white-space:nowrap;max-width:220px;overflow:hidden;text-overflow:ellipsis;font-size:12px;color:var(--ink);background:var(--card);border:1px solid var(--marker);border-radius:999px;padding:2px 9px;box-shadow:0 1px 4px rgba(0,0,0,.12)}
.pn-lbl.sel{background:var(--marker);color:var(--on-marker)} .pn-lbl.pend{border-style:dashed}
.sm-view.pn-armed canvas{cursor:crosshair}
.pn-ask{position:absolute;left:10px;right:10px;bottom:10px;max-width:440px;max-height:calc(100% - 20px);overflow:auto;margin:0 auto;padding:10px 12px;display:flex;flex-direction:column;gap:8px;background:var(--card);color:var(--ink);border-radius:8px;box-shadow:0 1px 2px rgba(20,25,35,.05),0 10px 30px -14px rgba(20,25,35,.3)}
.pn-ask[hidden],.pn-sel[hidden],.pn-sub[hidden],.pn-bad[hidden],.pn-head[hidden]{display:none}
.pn-ask input{font:inherit;font-size:16px;font-weight:300;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--paper);color:var(--ink);min-height:44px;width:100%;box-sizing:border-box}
.pn-ask.pn-top{bottom:auto;top:10px}
body.ek-full .pn-ask{z-index:4;bottom:calc(var(--bar-h,52px) + 24px);max-height:calc(100% - var(--ek-safe-top) - var(--bar-h,52px) - 36px)} body.ek-full .pn-ask.pn-top{top:var(--ek-safe-top);bottom:auto}  /* full screen: clear of the legend and the reaction button */
.pn-ask .pn-row{flex-wrap:nowrap} .pn-ask .pn-row .kicker{flex:1 1 0;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
/* one scrolling row per chip set, so the field stays small over a phone-sized view */
.pn-kinds{display:flex;flex-wrap:nowrap;gap:6px;overflow-x:auto;scrollbar-width:none;flex:0 0 auto} .pn-kinds::-webkit-scrollbar{display:none}
.pn-kinds button{flex:0 0 auto;white-space:nowrap;min-height:44px;padding:6px 12px;border-radius:999px;font-size:14px}
.pn-kinds button[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.pn-kinds .pn-short{display:none} @media(max-width:599px){.pn-kinds .pn-long{display:none} .pn-kinds .pn-short{display:inline}}
.pn-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.pn-arm[aria-pressed=true]{background:var(--ink);color:var(--paper);border-color:var(--ink)}
.pn-hint,.pn-off,.pn-bad,.pn-meta{font-size:13px;color:var(--mute)}
.pn-sel{display:flex;flex-direction:column;gap:8px;padding-top:4px;border-top:1px solid var(--line)}
.pn-name{font-size:20px;font-weight:500;line-height:1.1;overflow-wrap:anywhere}
.pn-list{display:grid;gap:6px} .pn-list:empty{display:none}
.pn-item{display:flex;gap:6px;align-items:center} .pn-item .pn-go{flex:1 1 auto;min-width:0;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pn-item .pn-go[aria-current=true]{border-color:var(--marker)}
.pn-mem{display:grid;gap:6px} .pn-mem:empty{display:none}
.pn-mem div{padding:8px 10px;border-left:3px solid var(--marker);background:var(--soft);border-radius:0 6px 6px 0;font-size:15px;overflow-wrap:anywhere}
.pn-mem audio{width:100%;max-width:320px;height:36px;display:block}
</style>"""


SCRIPT = r"""<script data-feature="pins">
(function modelPins() {
  const PROGRAM = __PROGRAM__;  /* brief program names: data, rendered with textContent only */
  const slot = document.getElementById("smSlot"), view = document.getElementById("smView"), smSel = document.getElementById("smSel");
  const M = window.EK && EK.feature && EK.feature.model;
  if (!slot || !view) return;
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  const btn = (text, cls) => { const b = el("button", cls || null, text); b.type = "button"; return b; };
  if (!M || M.fallback || !M.scene || !M.onPick || !window.THREE) { slot.appendChild(el("small", "pn-off", "Pins need the 3D view, which this device cannot show. You can still react to each building above.")); return; }
  const T = window.THREE, css = v => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || "#888888";
  const MAXL = 60, PAD = 1, NEAR = 20;
  /* "keep" is no longer offered ("The spot works" on a building says it) but pins stored with it still read */
  const KIND = { welcome: "Welcome a building here", keep: "Keep this", change: "Change this", question: "Question" }, OFFER = ["change", "question"];
  const bb = M.bbox, r0 = Math.max(0.4, Math.min(3, M.span * 0.008)), stemH = r0 * 5;
  const hasVoice = () => EK.hasKind && EK.hasKind("voice");

  /* program elements the model does not carry: whole-word match either way ("Main hall" is the "Hall") */
  const norm = s => String(s).toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9]+/g, " ").trim();
  const has = (hay, n) => (" " + hay + " ").indexOf(" " + n + " ") >= 0;
  const modelled = M.buildings.map(b => norm(b.label)).filter(Boolean);
  const unmodelled = PROGRAM.filter(p => { const n = norm(p); return n && !modelled.some(l => has(n, l) || has(l, n)); });

  /* records: validated on every render (finite, inside the model's extent, known kind) */
  const fin = n => typeof n === "number" && isFinite(n);
  const inBox = (v, k) => v >= bb.min[k] - PAD && v <= bb.max[k] + PAD;
  function valid(r) { const v = r.value; if (!v || typeof v !== "object" || typeof r.target !== "string" || r.target.indexOf("pin:") !== 0) return null;
    if (![v.x, v.y, v.z].every(fin) || !inBox(v.x, 0) || !inBox(v.y, 1) || !inBox(v.z, 2) || !KIND.hasOwnProperty(v.kind)) return null;
    if (v.kind === "welcome" && (typeof v.program !== "string" || !v.program)) return null;
    return { id: r.id, target: r.target, x: v.x, y: v.y, z: v.z, kind: v.kind, label: typeof v.label === "string" ? v.label.slice(0, MAXL) : "", program: v.kind === "welcome" ? v.program.slice(0, 60) : "" }; }
  const kindText = p => p.kind === "welcome" ? "Welcome " + p.program + " here" : KIND[p.kind];
  const shown = p => p.label || kindText(p);
  let cur = [], bad = 0, selId = null, armed = false, pending = null, pKind = "", pProg = "";
  function load() { cur = []; bad = 0; EK.reactions().forEach(r => { if (r.feature !== "model" || r.kind !== "pin") return; const p = valid(r); if (p) cur.push(p); else bad++; }); }
  const byId = id => cur.find(p => p.id === id) || null;

  /* ---- 3D: a marker-coloured sphere on a thin stem; an invisible larger sphere takes the taps ---- */
  const pinGroup = new T.Group(); pinGroup.name = "ek-pins"; M.scene.add(pinGroup);
  const gBall = new T.SphereGeometry(r0, 16, 12), gHit = new T.SphereGeometry(r0 * 2.6, 8, 6), gStem = new T.CylinderGeometry(r0 * 0.12, r0 * 0.12, stemH, 6);
  const mPin = new T.MeshBasicMaterial(), mPend = new T.MeshBasicMaterial({ transparent: true, opacity: 0.55 }), mStem = new T.MeshBasicMaterial(), mHit = new T.MeshBasicMaterial({ visible: false });
  function addPin(p, isPending) { const g = new T.Group(); g.position.set(p.x, p.y, p.z);
    const stem = new T.Mesh(gStem, mStem); stem.position.y = stemH / 2; g.add(stem);
    const ball = new T.Mesh(gBall, isPending ? mPend : mPin); ball.position.y = stemH + r0 * 0.6; if (p.id && p.id === selId) ball.scale.setScalar(1.4); g.add(ball);
    if (!isPending) { const hit = new T.Mesh(gHit, mHit); hit.position.y = ball.position.y; hit.userData.pinId = p.id; g.add(hit); }
    pinGroup.add(g); }
  function draw() { mPin.color.set(css("--marker")); mPend.color.set(css("--marker")); mStem.color.set(css("--ink"));
    while (pinGroup.children.length) pinGroup.remove(pinGroup.children[0]);
    cur.forEach(p => addPin(p, false)); if (pending) addPin(pending, true); M.render(); }

  /* labels: pills over the balls, projected each frame like the building labels */
  const lay = el("div", "pn-labels"); lay.setAttribute("aria-hidden", "true"); view.appendChild(lay);
  M.onRender(() => { lay.textContent = ""; const w = view.clientWidth, h = view.clientHeight;
    cur.concat(pending ? [pending] : []).forEach(p => { const s = M.project([p.x, p.y + stemH + r0 * 2, p.z]); if (!s || !s.on) return;
      const t = el("span", "pn-lbl" + (p === pending ? " pend" : p.id === selId ? " sel" : ""), p === pending ? "New pin" : shown(p)); t.style.left = Math.round(Math.min(w, Math.max(0, s.x))) + "px"; t.style.top = Math.round(Math.min(h, Math.max(0, s.y))) + "px"; lay.appendChild(t); }); });

  /* ---- card: arm button, selected pin, the device's pins ---- */
  const armRow = el("div", "pn-row"); const armBtn = btn("Drop a pin", "pn-arm"); armBtn.setAttribute("aria-pressed", "false");
  armRow.appendChild(armBtn); armRow.appendChild(el("span", "pn-hint", "Pin a spot and say what should go there, or what about it."));
  const sel = el("div", "pn-sel"); sel.hidden = true; sel.setAttribute("aria-live", "polite");
  const selK = el("span", "kicker", "Your pin"), selName = el("span", "pn-name"), selMeta = el("small", "pn-meta");
  const selRow = el("div", "pn-row"); const sayBtn = btn("Say why", "primary"), rmBtn = btn("Remove"), doneBtn = btn("Done");
  selRow.appendChild(sayBtn); selRow.appendChild(rmBtn); selRow.appendChild(doneBtn);
  const mem = el("div", "pn-mem"); mem.setAttribute("role", "list"); mem.setAttribute("aria-label", "Your notes on this pin");
  [selK, selName, selMeta, selRow, mem].forEach(n => sel.appendChild(n));
  const head = el("span", "kicker pn-head"); const list = el("div", "pn-list"); list.setAttribute("role", "list"); list.setAttribute("aria-label", "Your pins");
  const badNote = el("small", "pn-bad"); badNote.hidden = true;
  [armRow, sel, head, list, badNote].forEach(n => slot.appendChild(n));

  /* ---- the inline field over the view ---- */
  const ask = el("div", "pn-ask"); ask.hidden = true; ask.setAttribute("role", "dialog"); ask.setAttribute("aria-label", "New pin");
  const askK = el("span", "kicker", "New pin");
  const input = document.createElement("input"); input.type = "text"; input.maxLength = MAXL; input.placeholder = "What should go here, or what about this spot?"; input.setAttribute("aria-label", "What should go here, or what about this spot? Up to 60 characters");
  const kinds = el("div", "pn-kinds"); kinds.setAttribute("role", "group"); kinds.setAttribute("aria-label", "What kind of pin");
  const sub = el("div", "pn-kinds pn-sub"); sub.hidden = true; sub.setAttribute("role", "group"); sub.setAttribute("aria-label", "Which part of the program");
  /* program chips say what they are for: the long label from 600 px, the short one on a phone */
  const progBtn = n => { const b = btn(null); b.appendChild(el("span", "pn-long", n + " — not in the model yet, pin where you would put it")); b.appendChild(el("span", "pn-short", n + " · not in the model yet"));
    b.setAttribute("aria-label", n + ", not in the model yet: pin where you would put it"); b.dataset.p = n; b.setAttribute("aria-pressed", "false"); return b; };
  /* the program comes first; a single unmodelled element is its own chip (no extra tap), several open a second row in brief order */
  const one = unmodelled.length === 1;
  const kindBtns = (unmodelled.length ? ["welcome"] : []).concat(OFFER).map(k => { const b = k === "welcome" && one ? progBtn(unmodelled[0]) : btn(k === "welcome" ? "A building from the program" : KIND[k]); b.dataset.k = k; b.setAttribute("aria-pressed", "false"); kinds.appendChild(b); return b; });
  const subBtns = one ? [] : unmodelled.map(n => { const b = progBtn(n); sub.appendChild(b); return b; });
  const askRow = el("div", "pn-row"); const saveBtn = btn("Save pin", "primary"), cancelBtn = btn("Cancel"); saveBtn.disabled = true; askRow.appendChild(saveBtn); askRow.appendChild(cancelBtn);
  askRow.insertBefore(askK, saveBtn); [input, kinds, sub, askRow].forEach(n => ask.appendChild(n)); view.appendChild(ask);
  const canSave = () => { saveBtn.disabled = !pKind || (pKind === "welcome" && !pProg); };
  kindBtns.forEach(b => b.addEventListener("click", () => { pKind = pKind === b.dataset.k ? "" : b.dataset.k; pProg = pKind === "welcome" && one ? unmodelled[0] : pKind === "welcome" ? pProg : ""; kindBtns.forEach(x => x.setAttribute("aria-pressed", String(x.dataset.k === pKind))); subBtns.forEach(x => x.setAttribute("aria-pressed", String(x.dataset.p === pProg))); sub.hidden = pKind !== "welcome" || one; canSave(); }));
  subBtns.forEach(b => b.addEventListener("click", () => { pProg = pProg === b.dataset.p ? "" : b.dataset.p; subBtns.forEach(x => x.setAttribute("aria-pressed", String(x.dataset.p === pProg))); canSave(); }));

  function arm(on) { armed = !!on; armBtn.setAttribute("aria-pressed", String(armed)); armBtn.textContent = armed ? "Cancel pin" : "Drop a pin"; view.classList.toggle("pn-armed", armed); if (armed) EK.toast("Tap the ground or a building where the pin goes"); }
  function closeAsk() { pending = null; ask.hidden = true; draw(); }
  armBtn.addEventListener("click", () => { if (pending) { closeAsk(); arm(false); return; } arm(!armed); });
  cancelBtn.addEventListener("click", () => { closeAsk(); arm(false); M.canvas.focus({ preventScroll: true }); });
  input.addEventListener("keydown", e => { if (e.key === "Enter") { e.preventDefault(); if (!saveBtn.disabled) saveBtn.click(); } });

  const r1 = v => Math.round(v * 10) / 10;
  function nearest(hit) { if (hit.building) return hit.building.label; let best = null, bd = Infinity; const [x, , z] = hit.point;
    M.buildings.forEach(b => { const dx = Math.max(b.bbox[0] - x, 0, x - b.bbox[3]), dz = Math.max(b.bbox[2] - z, 0, z - b.bbox[5]); const d = Math.hypot(dx, dz); if (d < bd) { bd = d; best = b; } });
    if (best && bd <= NEAR) return best.label; return hit.kind === "water" ? "the water" : hit.kind === "existing" ? "an existing building" : "the ground"; }
  const where = near => (/^(the|an?) /.test(near) ? "on " : "near ") + near;
  const targetOf = (x, y, z, near) => "pin:" + x.toFixed(1) + "," + y.toFixed(1) + "," + z.toFixed(1) + " (" + near + ")";
  function place(hit) { pending = { x: r1(hit.point[0]), y: r1(hit.point[1]), z: r1(hit.point[2]), near: nearest(hit) };
    input.value = ""; pKind = ""; pProg = ""; kindBtns.forEach(x => x.setAttribute("aria-pressed", "false")); subBtns.forEach(x => x.setAttribute("aria-pressed", "false")); sub.hidden = true; canSave();
    askK.textContent = "New pin, " + where(pending.near); ask.hidden = false; draw();
    /* keep the new pin in sight: the field goes to the half of the view the pin is not in */
    const s = M.project([pending.x, pending.y, pending.z]); ask.classList.toggle("pn-top", !!s && s.y > view.clientHeight / 2); input.focus({ preventScroll: true }); }
  saveBtn.addEventListener("click", () => { if (!pending || !pKind || (pKind === "welcome" && !pProg)) return; const p = pending;
    const value = { x: p.x, y: p.y, z: p.z, label: input.value.trim().slice(0, MAXL), kind: pKind }; if (pKind === "welcome") value.program = pProg;
    const rec = EK.react({ feature: "model", target: targetOf(p.x, p.y, p.z, p.near), kind: "pin", value });
    if (!rec) { EK.toast("Could not save on this phone (storage full?)"); return; }
    pending = null; ask.hidden = true; arm(false); selectPin(rec.id); EK.toast("Pin saved on this phone \u2014 say why below if you like"); });

  /* taps on the model: place when armed, select a pin when one is hit, otherwise let the model select buildings */
  M.onPick((hit, ray) => {
    if (pending) { if (hit) { place(hit); } return true; }
    if (armed) { if (!hit) { EK.toast("Tap the ground or a building"); return true; } arm(false); place(hit); return true; }
    const ph = ray.intersectObjects(pinGroup.children, true).find(i => i.object.userData.pinId);
    if (ph && (!hit || ph.distance <= hit.distance + r0 * 3)) { selectPin(ph.object.userData.pinId); return true; }
    if (selId) selectPin(null, true);
    return false; });

  function selectPin(id, quiet) { selId = id && byId(id) ? id : null; const p = selId ? byId(selId) : null; sel.hidden = !p;
    if (p) { M.select(null); selName.textContent = shown(p); selMeta.textContent = kindText(p) + " \u00b7 " + where(p.target.replace(/^pin:[^(]*\(/, "").replace(/\)$/, "")) + " \u00b7 " + p.x.toFixed(1) + ", " + p.y.toFixed(1) + ", " + p.z.toFixed(1) + " m";
      if (EK.current() === "model") EK.context("model", p.target, "\u2014 what about this spot?", "Your pin: " + shown(p)); }
    else if (!quiet && !M.selected() && EK.current() === "model") EK.context("model", "the model", "\u2014 tap a building to react to it");
    renderCard(); draw(); }
  sayBtn.addEventListener("click", () => { const p = byId(selId); if (!p) return; EK.context("model", p.target, "\u2014 why here? what should change?", "Your pin: " + shown(p)); EK.focusNote(); EK.toast(hasVoice() ? "Speak or type below" : "Type below"); });
  doneBtn.addEventListener("click", () => selectPin(null));
  function removePin(p) { const notes = EK.reactions().filter(r => r.feature === "model" && r.target === p.target && r.kind !== "pin");
    if (selId === p.id) selectPin(null); EK.remove(p.id); notes.forEach(r => EK.remove(r.id)); EK.toast(notes.length ? "Pin and its " + notes.length + " note" + (notes.length === 1 ? "" : "s") + " removed" : "Pin removed"); }
  rmBtn.addEventListener("click", () => { const p = byId(selId); if (p) removePin(p); });
  /* a building chosen from the model or its chip ends the pin selection and any pin being placed (the model hides this row then) */
  if (smSel && "MutationObserver" in window) new MutationObserver(() => { if (smSel.hidden) return; if (armed || pending) { pending = null; ask.hidden = true; arm(false); }
    if (selId) { selId = null; sel.hidden = true; renderCard(); } draw(); }).observe(smSel, { attributes: true, attributeFilter: ["hidden"] });

  function renderCard() { list.textContent = ""; head.hidden = !cur.length; head.textContent = "Your pins (" + cur.length + ", on this device)";
    cur.forEach(p => { const row = el("div", "pn-item"); row.setAttribute("role", "listitem"); const go = btn(shown(p), "pn-go"); go.setAttribute("aria-label", "Show pin: " + shown(p)); if (p.id === selId) go.setAttribute("aria-current", "true");
      go.addEventListener("click", () => selectPin(p.id)); const rm = btn("Remove"); rm.setAttribute("aria-label", "Remove pin: " + shown(p)); rm.addEventListener("click", () => removePin(p)); row.appendChild(go); row.appendChild(rm); list.appendChild(row); });
    badNote.hidden = !bad; badNote.textContent = bad + " stored pin" + (bad === 1 ? "" : "s") + " could not be read (outside the model or malformed) and " + (bad === 1 ? "is" : "are") + " not shown.";
    mem.textContent = ""; const p = byId(selId); if (!p) return;
    EK.reactions().filter(r => r.feature === "model" && r.target === p.target && r.kind !== "pin").forEach(r => { const d = el("div"); d.setAttribute("role", "listitem");
      if (r.kind === "voice" && r.value && typeof r.value.mime === "string" && /^audio\/[\w.+-]+$/.test(r.value.mime) && typeof r.value.base64 === "string" && /^[A-Za-z0-9+\/=]+$/.test(r.value.base64)) { const a = document.createElement("audio"); a.controls = true; a.src = "data:" + r.value.mime + ";base64," + r.value.base64; d.appendChild(a); d.appendChild(el("small", null, (r.value.seconds || "?") + " s, voice")); }
      else if (r.kind !== "voice" && r.value && typeof r.value.text === "string") { d.textContent = r.value.text; const sp = document.createElement("small"); sp.textContent = r.value.via === "voice" ? " (spoken)" : ""; d.appendChild(sp); } else d.textContent = r.kind === "voice" ? "Unsupported voice note" : typeof r.value === "string" ? r.value : "Unsupported note"; mem.appendChild(d); }); }

  EK.on("ek:reaction", () => { load(); if (selId && !byId(selId)) { selId = null; sel.hidden = true; } renderCard(); draw(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape" && EK.current() === "model" && (armed || pending)) { closeAsk(); arm(false); } });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", draw);
  load(); renderCard(); draw();
  EK.feature.pins = { list: () => cur.slice(), select: id => selectPin(id), arm, valid };

  /* ---- tour: drop an example pin on the ground at the middle of the view, recorded right here in do() with
     tour:true (no deferred write that could outlive the step); undone on Back / exit, and the shell removes it anyway ---- */
  let tourId = null;
  EK.registerTour([{ go: "model", text: "Drop a pin: tap the button, then tap the ground or a building, and say what should go there or what about that spot.",
    do: () => { if (typeof EK.tourRunning === "function" && !EK.tourRunning()) return; arm(false); if (pending) closeAsk(); M.select(null); M.render();
      const rc = new T.Raycaster(); rc.setFromCamera(new T.Vector2(0, -0.15), M.camera); const g = M.ground(), ter = g.filter(m => m.userData.kind === "terrain"); const s = rc.intersectObjects(ter.length ? ter : g)[0];
      if (!s) return; const x = r1(s.point.x), y = r1(s.point.y), z = r1(s.point.z);
      const rec = EK.react({ feature: "model", target: targetOf(x, y, z, nearest({ point: [x, y, z], building: null, kind: "terrain" })), kind: "pin", value: { x, y, z, label: "An example pin from the tour", kind: "question" }, tour: true });
      if (rec) { tourId = rec.id; selectPin(rec.id); } },
    undo: () => { arm(false); if (pending) closeAsk(); if (tourId) { const id = tourId; tourId = null; if (selId === id) selectPin(null); EK.remove(id); } } }]);
})();
</script>"""


def splice(doc: str, style: str, script: str) -> str:
    doc = re.sub(r'\n?<style data-feature="pins">.*?</style>', "", doc, flags=re.S)
    doc = re.sub(r'\n?<script data-feature="pins">.*?</script>', "", doc, flags=re.S)
    m = MODEL_SCRIPT.search(doc)
    if not m:
        raise SystemExit("no <script data-feature=\"model\"> in the output; run ek-site-model first (pins extend it)")
    if "onPick" not in m.group(0) or 'id="smSlot"' not in doc:
        raise SystemExit("the model block predates its extension point (onPick, #smSlot); re-run ek-site-model/build.py")
    if "<!-- ek:styles -->" not in doc:
        raise SystemExit("shell marker <!-- ek:styles --> missing from the output")
    doc = doc[:m.end()] + "\n" + script + doc[m.end():]
    return doc.replace("<!-- ek:styles -->", "<!-- ek:styles -->\n" + style, 1)


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
    names = program_names(brief, warnings)
    if not names:
        warnings.append("brief has no program names; the 'building from the program' choice is not offered")
    new_doc = splice(doc, STYLE, SCRIPT.replace("__PROGRAM__", json_inline(names), 1))
    args.out.write_text(new_doc, encoding="utf-8", newline="\n")
    for w in warnings:
        print(f"[ek-model-pins] warning: {w}", file=sys.stderr)
    print(json.dumps({"out": str(args.out), "bytes": len(new_doc.encode("utf-8")), "program_names": len(names), "warnings": len(warnings)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
