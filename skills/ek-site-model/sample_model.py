#!/usr/bin/env python3
"""
ek-site-model — write a small synthetic viewer JSON for the Riverside sample (no Rhino file exists for it).

  python skills/ek-site-model/sample_model.py --out skills/ek-shell/sample/model.riverside.json

A gently sloping ground falling to a river band, the three option-A blocks as simple gabled boxes, a few
trees and the flood line as a curve. Invented, like the rest of the sample; it exists so the viewer can be
built, tested and shown without client material.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import random
import struct
from pathlib import Path


def pack(pos, idx):
    n = len(pos) // 3
    p = base64.b64encode(struct.pack(f"<{len(pos)}f", *pos)).decode()
    if n < 65536:
        i = base64.b64encode(struct.pack(f"<{len(idx)}H", *idx)).decode(); it = "u16"
    else:
        i = base64.b64encode(struct.pack(f"<{len(idx)}I", *idx)).decode(); it = "u32"
    xs, ys, zs = pos[0::3], pos[1::3], pos[2::3]
    return {"pos": p, "idx": i, "idx_type": it, "verts": n, "tris": len(idx) // 3, "bbox": [min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)]}


def ground(w=160, d=120, step=4):
    pos, idx = [], []
    nx, nz = w // step + 1, d // step + 1
    for j in range(nz):
        for i in range(nx):
            x = -w / 2 + i * step; z = -d / 2 + j * step
            y = 2.5 - 0.03 * (z + d / 2) + 0.6 * math.sin(x / 23) * math.cos(z / 31)  # falls toward the river (south)
            if z > d / 2 - 14:
                y = min(y, 0.0 - (z - (d / 2 - 14)) * 0.08)  # the river band
            pos.extend((x, y, z))
    for j in range(nz - 1):
        for i in range(nx - 1):
            a = j * nx + i; b = a + 1; c = a + nx; dd = c + 1
            idx.extend((a, c, b, b, c, dd))
    return pos, idx


def box(x, z, w, d, h, y0, gable=1.6):
    """A gabled block: 8 base corners + ridge."""
    hw, hd = w / 2, d / 2
    v = [(x - hw, y0, z - hd), (x + hw, y0, z - hd), (x + hw, y0, z + hd), (x - hw, y0, z + hd),
         (x - hw, y0 + h, z - hd), (x + hw, y0 + h, z - hd), (x + hw, y0 + h, z + hd), (x - hw, y0 + h, z + hd),
         (x - hw, y0 + h + gable, z), (x + hw, y0 + h + gable, z)]
    pos = [c for p in v for c in p]
    idx = [0, 2, 1, 0, 3, 2,  # floor
           0, 1, 5, 0, 5, 4,  # north wall
           1, 2, 6, 1, 6, 5,  # east
           2, 3, 7, 2, 7, 6,  # south
           3, 0, 4, 3, 4, 7,  # west
           4, 5, 9, 4, 9, 8,  # roof north
           6, 7, 8, 6, 8, 9,  # roof south
           5, 6, 9,            # east gable
           7, 4, 8]            # west gable
    return pos, idx


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    random.seed(7)
    gp, gi = ground()
    rp = [-80, -0.6, 46, 80, -0.6, 46, 80, -0.6, 60, -80, -0.6, 60]; ri = [0, 2, 1, 0, 3, 2]
    buildings = []
    for label, (x, z, w, d, s) in {"Hall": (-4, 1, 14, 7, 1), "Rooms wing": (7, 1, 7, 7, 2), "Terrace": (-4, -5, 14, 4, 0.3)}.items():
        y0 = 2.5 - 0.03 * (z + 60)
        p, i = box(x, z, w, d, s * 3.4, y0, 1.6 if s >= 1 else 0.2)
        b = pack(p, i); b.update({"label": label, "definition": label, "parts": 1, "center": [x, y0 + s * 1.7, z]}); buildings.append(b)
    trees = []
    for _ in range(40):
        x = random.uniform(-75, 75); z = random.uniform(-55, 40)
        if abs(x) < 16 and -10 < z < 8:
            continue
        y = 2.5 - 0.03 * (z + 60) + 0.6 * math.sin(x / 23) * math.cos(z / 31)
        h = random.uniform(6, 14); trees.append([round(x, 2), round(y, 2), round(z, 2), round(h, 2), round(h * 0.3, 2)])
    curves = [[[x, 2.5 - 0.03 * (30 + 60) + 0.25, 30.0] for x in range(-80, 81, 8)]]  # the 1948 flood line
    out = {"units": "m", "origin": [0, 0, 0], "frame": "x east, y up, z south (viewer)", "source": {"file": "sample (invented)", "layers": {}},
           "meshes": [{"name": "terrain", "kind": "terrain", **pack(gp, gi)}, {"name": "water", "kind": "water", **pack(rp, ri)}],
           "buildings": buildings, "trees": trees, "curves": curves, "stats": {"note": "synthetic sample"}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "bytes": args.out.stat().st_size, "buildings": [b["label"] for b in buildings], "trees": len(trees)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
