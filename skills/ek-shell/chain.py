#!/usr/bin/env python3
"""
ek-shell chain — build a whole tool: the shell, then every installed feature skill in slot order.

  python skills/ek-shell/chain.py --brief work/brief.json --manifest project.config.json --out output/index.html [--root .] [--model model.json]

Reads manifest.install, runs skills/ek-shell/build.py, then each installed skill's build.py with the arguments
that skill takes (brief / out / root / model / manifest), in the shell's slot order with augments after the
feature they extend and synthesis last. Prints one line per step and every skill warning; stops at the
first failure. Nothing here reads the deck or the brief beyond the manifest's install list.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
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
         "ek-submissions-gallery", "ek-voice-reactions", "ek-feedback-synthesis"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brief", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--model", default=None, help="viewer JSON for ek-site-model, relative to --root (default: the manifest entry's 'model')")
    ap.add_argument("--skip", default="", help="comma list of skills to skip")
    args = ap.parse_args(argv)
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
        root, needs_model, needs_manifest, needs_brief = ARGS[s]
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
