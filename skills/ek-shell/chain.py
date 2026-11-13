#!/usr/bin/env python3
"""
ek-shell chain — build a whole tool: the shell, then every installed feature skill in slot order.

  python skills/ek-shell/chain.py --brief work/brief.json --manifest project.config.json --out output/index.html [--root .] [--model model.json]
  python skills/ek-shell/chain.py --brief work/brief.json --manifest project.config.json --portal admin   # → output/admin/index.html

--portal admin builds the design team's portal: the same chain from a temporary copy of the manifest with
portal "admin" and ek-admin appended to install (ek-chat stays as configured); the real manifest is not changed.

Reads manifest.install, runs skills/ek-shell/build.py, then each installed skill's build.py with the arguments
that skill takes (brief / out / root / model / manifest), in the shell's slot order with augments after the
feature they extend and synthesis last. Prints one line per step and every skill warning; stops at the
first failure. Nothing here reads the deck or the brief beyond the manifest's install list.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent.parent   # skills/ek-shell/chain.py → the kit root

# skill → (needs_root, needs_model, needs_manifest, needs_brief)
ARGS = {
    "ek-about": (False, False, False, True),
    "ek-process-timeline": (False, False, False, True),
    "ek-timeline": (True, False, False, True),
    "ek-site-story": (True, False, False, True),
    "ek-site-model": (True, True, False, True),
    "ek-model-pins": (False, False, False, True),
    "ek-site-massing-3d": (True, False, False, True),
    "ek-massing-markup": (False, False, False, True),
    "ek-program-diagram": (False, False, False, True),
    "ek-list-reactions": (False, False, False, True),
    "ek-precedents": (True, False, False, True),
    "ek-model-roundtrip": (True, False, False, True),
    "ek-drawing-markup": (True, False, False, True),
    "ek-submissions-gallery": (False, False, False, True),
    "ek-voice-reactions": (False, False, False, False),
    "ek-feedback-synthesis": (False, False, True, True),
}
ORDER = ["ek-about", "ek-process-timeline", "ek-timeline", "ek-site-story", "ek-site-model", "ek-model-pins", "ek-site-massing-3d",
         "ek-massing-markup", "ek-program-diagram", "ek-list-reactions", "ek-precedents", "ek-model-roundtrip", "ek-drawing-markup",
         "ek-submissions-gallery", "ek-voice-reactions", "ek-feedback-synthesis", "ek-chat", "ek-admin"]
# ek-chat and ek-admin are built by their own skills; their arguments are read from their build.py (whichever of
# --brief / --root / --manifest it declares), so this file does not have to change when they land.
DETECT = ("ek-chat", "ek-admin")


def detect_args(build: Path) -> tuple[bool, bool, bool, bool]:
    src = build.read_text(encoding="utf-8", errors="replace")
    return ('"--root"' in src, False, '"--manifest"' in src, '"--brief"' in src)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None, help="default: output/index.html (user portal) or output/admin/index.html (admin portal)")
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--model", default=None, help="viewer JSON for ek-site-model, relative to --root (default: the manifest entry's 'model')")
    ap.add_argument("--skip", default="", help="comma list of skills to skip")
    ap.add_argument("--portal", choices=("user", "admin"), default="user",
                    help="admin: build from a temporary manifest copy with portal 'admin' and ek-admin installed (ek-chat as configured)")
    args = ap.parse_args(argv)
    if args.out is None:
        args.out = Path("output/admin/index.html") if args.portal == "admin" else Path("output/index.html")
    m = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    inst = [i for i in m.get("install", []) if isinstance(i, dict)]
    has_admin = any(i.get("skill") == "ek-admin" for i in inst)
    # A user portal carries the chat only through a proxy: in direct mode the key lives in the admin's own browser, so
    # the user build would show a dead "Ask" button. Drop ek-chat there rather than ship a control that cannot work.
    chat_mode = str((m.get("chat") or {}).get("mode") or "") if isinstance(m.get("chat"), dict) else ""
    drop_chat = args.portal == "user" and chat_mode != "proxy" and any(i.get("skill") == "ek-chat" for i in inst)
    if drop_chat:
        print(f"[chain] ek-chat: not in the user portal (chat mode is {chat_mode or 'not set'}; only 'proxy' serves visitors)")
    if args.portal == "admin" or has_admin or drop_chat or m.get("portal") not in (None, "user"):
        # Admin: portal "admin" and ek-admin appended. User: portal "user" and ek-admin removed, so a manifest that lists
        # ek-admin never leaks the admin section into the public portal. The copy sits next to the real manifest so paths
        # the shell resolves against the manifest's folder (the cover) still work; it is removed whatever happens.
        # The real manifest is never changed here.
        if args.portal == "admin":
            m["portal"] = "admin"
            if not has_admin:
                inst.append({"skill": "ek-admin", "reason": "admin portal: the design team's view (added by chain.py --portal admin)"})
        else:
            m["portal"] = "user"
            inst = [i for i in inst if i.get("skill") != "ek-admin" and not (drop_chat and i.get("skill") == "ek-chat")]
        m["install"] = inst
        fd, tmp = tempfile.mkstemp(prefix=".ek-admin-manifest-", suffix=".json", dir=str(args.manifest.resolve().parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(m, f, ensure_ascii=False, indent=2)
            return run(args, Path(tmp))
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass
    return run(args, args.manifest)


def run(args, manifest_path: Path) -> int:
    args.manifest = manifest_path
    args.out.parent.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    installed = [i.get("skill") for i in manifest.get("install", []) if isinstance(i, dict) and i.get("skill")]
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    model = args.model or next((i.get("model") for i in manifest.get("install", []) if isinstance(i, dict) and i.get("skill") == "ek-site-model" and i.get("model")), None)
    py = sys.executable
    steps = [("ek-shell", [py, "-X", "utf8", str(KIT / "skills/ek-shell/build.py"), "--brief", str(args.brief), "--manifest", str(args.manifest), "--out", str(args.out)])]
    for s in installed:
        if s not in ORDER and s != "ek-shell":
            print(f"[chain] {s}: not a kit skill; ignored")
    for s in ORDER:
        if s not in installed or s in skip:
            continue
        build = KIT / "skills" / s / "build.py"
        if not build.is_file():
            print(f"[chain] {s}: no build.py yet (instruction draft); skipped")
            continue
        root, needs_model, needs_manifest, needs_brief = detect_args(build) if s in DETECT else ARGS[s]
        cmd = [py, "-X", "utf8", str(build), "--out", str(args.out)]
        if needs_brief:
            cmd += ["--brief", str(args.brief)]
        if root:
            cmd += ["--root", str(args.root)]
        if needs_model:
            if not model:
                print(f"[chain] {s}: no model given (--model or manifest install[].model); skipped")
                continue
            cmd += ["--model=" + str(model)]
        if needs_manifest:
            cmd += ["--manifest", str(args.manifest)]
        steps.append((s, cmd))
    for name, cmd in steps:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        for line in (r.stderr or "").splitlines():
            if line.strip():
                print(f"   {line}")
        if r.returncode != 0:
            print(f"[chain] {name}: FAILED (exit {r.returncode})")
            print((r.stdout or "")[-800:])
            return r.returncode
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
            size = info.get("bytes")
        except Exception:
            size = None
        print(f"[chain] {name}: ok" + (f" ({size:,} bytes)" if size else ""))
    print(f"[chain] done: {args.out} ({args.out.stat().st_size:,} bytes), {len(steps)} steps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
