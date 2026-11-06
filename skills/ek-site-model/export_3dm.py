#!/usr/bin/env python3
"""
ek-site-model — export a Rhino .3dm site model to the compact JSON the viewer embeds.

  python skills/ek-site-model/export_3dm.py --in <file.3dm> --out work/model.json
         [--terrain "3D Site::Surface"] [--water "3D Site::Waterbody"] [--trees "3D Site::NEW"]
         [--buildings "Massings"] [--existing "3D Site::NEW"] [--curves "3D Site::Site Features"]
         [--label "Hermitage Single=Hermitage cabin" --label "Chaplain Residence=Chaplain's House"]

Reads the file with rhino3dm (no Rhino needed). Uses the render meshes Rhino saved with the breps and
extrusions, so nothing is re-meshed here; a brep without a render mesh is reported and skipped.
Writes one JSON with every coordinate in metres, relative to an origin at the centre of the terrain and
in the viewer's frame (x east, y up, z south). Block instances on the buildings layer are baked to world
coordinates, one mesh per instance, so the viewer can pick and label each building. Tree meshes are
reduced to one record per tree (position, height, crown radius) and drawn procedurally by the viewer.
Nothing in the model is executed; names are strings the viewer renders with textContent.
"""
from __future__ import annotations

import argparse
import base64
import collections
import json
import math
import struct
import sys
from pathlib import Path

try:
    import rhino3dm as r3  # type: ignore
except ImportError:
    sys.exit("rhino3dm is not installed: pip install rhino3dm==8.17.0 (or the version pinned in requirements.txt)")

MAX_VERTS = 400_000
CURVE_SAMPLES = 48


def log(msg: str) -> None:
    print(f"[ek-site-model] {msg}", file=sys.stderr)


# --------------------------------------------------------------------------- layers

def layer_paths(model) -> dict[int, str]:
    byid = {str(L.Id): L for L in model.Layers}
    out = {}
    for L in model.Layers:
        parts = [L.Name]
        p = str(L.ParentLayerId)
        n = 0
        while p in byid and n < 32:
            parts.append(byid[p].Name)
            p = str(byid[p].ParentLayerId)
            n += 1
        out[L.Index] = "::".join(reversed(parts))
    return out


def on_layer(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "::")


# --------------------------------------------------------------------------- meshes

def mesh_of(geom):
    """Render mesh(es) of a geometry object as a list of rhino3dm.Mesh, or []."""
    t = type(geom).__name__
    if t == "Mesh":
        return [geom]
    out = []
    if t == "Brep":
        for i in range(len(geom.Faces)):
            try:
                m = geom.Faces[i].GetMesh(r3.MeshType.Render)
            except Exception:
                m = None
            if m is not None:
                out.append(m)
    elif t == "Extrusion":
        try:
            m = geom.GetMesh(r3.MeshType.Render)
        except Exception:
            m = None
        if m is not None:
            out.append(m)
    return out


class Buffer:
    """Accumulates triangles into one indexed buffer (viewer frame, origin-relative)."""

    def __init__(self, origin):
        self.ox, self.oy, self.oz = origin
        self.pos: list[float] = []
        self.idx: list[int] = []
        self.n = 0
        self.min = [math.inf] * 3
        self.max = [-math.inf] * 3

    def add(self, mesh, xform=None):
        base = self.n
        verts = mesh.Vertices
        for i in range(len(verts)):
            v = verts[i]
            x, y, z = float(v.X), float(v.Y), float(v.Z)
            if xform is not None:
                p = r3.Point3d(x, y, z)
                p.Transform(xform)
                x, y, z = p.X, p.Y, p.Z
            X, Y, Z = x - self.ox, z - self.oz, -(y - self.oy)
            self.pos.extend((X, Y, Z))
            for k, c in enumerate((X, Y, Z)):
                if c < self.min[k]:
                    self.min[k] = c
                if c > self.max[k]:
                    self.max[k] = c
        self.n += len(verts)
        faces = mesh.Faces
        for i in range(len(faces)):
            f = faces[i]
            a, b, c, d = int(f[0]), int(f[1]), int(f[2]), int(f[3])
            self.idx.extend((base + a, base + b, base + c))
            if d != c:
                self.idx.extend((base + a, base + c, base + d))

    def empty(self):
        return self.n == 0

    def pack(self):
        pos = base64.b64encode(struct.pack(f"<{len(self.pos)}f", *self.pos)).decode("ascii")
        if self.n < 65536:
            idx = base64.b64encode(struct.pack(f"<{len(self.idx)}H", *self.idx)).decode("ascii")
            it = "u16"
        else:
            idx = base64.b64encode(struct.pack(f"<{len(self.idx)}I", *self.idx)).decode("ascii")
            it = "u32"
        return {"pos": pos, "idx": idx, "idx_type": it, "verts": self.n, "tris": len(self.idx) // 3,
                "bbox": [round(v, 2) for v in self.min + self.max]}


def transform_of(iref):
    """rhino3dm.Transform of an instance reference (identity when unavailable)."""
    X = iref.Xform
    return X


def bbox_of(geom):
    try:
        bb = geom.GetBoundingBox()
        return (bb.Min.X, bb.Min.Y, bb.Min.Z, bb.Max.X, bb.Max.Y, bb.Max.Z)
    except Exception:
        return None


def curve_points(curve, n=CURVE_SAMPLES):
    try:
        nc = curve.ToNurbsCurve()
    except Exception:
        nc = None
    if nc is None:
        return []
    d = nc.Domain
    pts = []
    for i in range(n + 1):
        t = d.T0 + (d.T1 - d.T0) * i / n
        p = nc.PointAt(t)
        pts.append((p.X, p.Y, p.Z))
    return pts


# --------------------------------------------------------------------------- main

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--terrain", default="3D Site::Surface", help="layer path (prefix) whose breps/meshes are the ground")
    ap.add_argument("--water", default="3D Site::Waterbody")
    ap.add_argument("--trees", default="3D Site::NEW", help="layer whose meshes named Tree_* are reduced to tree records")
    ap.add_argument("--existing", default="3D Site::NEW", help="layer whose breps/extrusions are existing buildings")
    ap.add_argument("--buildings", default="Massings", help="layer whose block instances are the proposed buildings")
    ap.add_argument("--curves", default="3D Site::Site Features", help="layer whose curves are drawn as lines (paths, roads)")
    ap.add_argument("--label", action="append", default=[], help="'Block definition name=Public label' (repeatable)")
    ap.add_argument("--z0", type=float, default=None, help="elevation that becomes y = 0 (default: lowest terrain vertex)")
    ap.add_argument("--allow-unlabelled", action="store_true", help="let a block definition's own name become the public label (otherwise every placed definition needs a --label)")
    args = ap.parse_args(argv)
    if not args.src.is_file():
        sys.exit(f"not a file: {args.src}")
    labels = {}
    for s in args.label:
        if "=" in s:
            k, v = s.split("=", 1)
            labels[k.strip()] = v.strip()[:60]
    warnings: list[str] = []

    model = r3.File3dm.Read(str(args.src))
    paths = layer_paths(model)
    layer_vis = {L.Index: L.Visible for L in model.Layers}
    units = str(model.Settings.ModelUnitSystem)
    if "Meters" not in units:
        warnings.append(f"model units are {units}, not metres; coordinates are exported as-is")

    def objs(prefix):
        return [o for o in model.Objects if on_layer(paths.get(o.Attributes.LayerIndex, ""), prefix) and layer_vis.get(o.Attributes.LayerIndex, True)]

    # terrain first: it defines the origin
    terrain_objs = objs(args.terrain)
    tmeshes = []
    for o in terrain_objs:
        ms = mesh_of(o.Geometry)
        if not ms and type(o.Geometry).__name__ in ("Brep", "Extrusion"):
            warnings.append(f"terrain object on {paths.get(o.Attributes.LayerIndex)!r} has no render mesh; skipped")
        tmeshes.extend(ms)
    if not tmeshes:
        sys.exit(f"no terrain meshes on layer {args.terrain!r}; pass --terrain")
    tb = [math.inf, math.inf, math.inf, -math.inf, -math.inf, -math.inf]
    for m in tmeshes:
        b = bbox_of(m)
        if b:
            tb = [min(tb[0], b[0]), min(tb[1], b[1]), min(tb[2], b[2]), max(tb[3], b[3]), max(tb[4], b[4]), max(tb[5], b[5])]
    z0 = args.z0 if args.z0 is not None else tb[2]
    origin = ((tb[0] + tb[3]) / 2, (tb[1] + tb[4]) / 2, z0)
    site_box = tb
    inside = lambda b: b and b[3] >= site_box[0] - 50 and b[0] <= site_box[3] + 50 and b[4] >= site_box[1] - 50 and b[1] <= site_box[4] + 50

    out = {"units": "m", "origin": [round(v, 3) for v in origin], "frame": "x east, y up, z south (viewer); y = elevation - origin z",
           "source": {"file": args.src.name, "layers": {"terrain": args.terrain, "water": args.water, "trees": args.trees, "existing": args.existing, "buildings": args.buildings, "curves": args.curves}},
           "meshes": [], "buildings": [], "trees": [], "curves": [], "stats": {}}

    tbuf = Buffer(origin)
    for m in tmeshes:
        tbuf.add(m)
    out["meshes"].append({"name": "terrain", "kind": "terrain", **tbuf.pack()})

    wbuf = Buffer(origin)
    for o in objs(args.water):
        for m in mesh_of(o.Geometry):
            wbuf.add(m)
    if not wbuf.empty():
        out["meshes"].append({"name": "water", "kind": "water", **wbuf.pack()})
    else:
        warnings.append(f"no water meshes on layer {args.water!r}")

    # existing buildings: breps / extrusions on the existing layer that sit within the site box
    ebuf = Buffer(origin)
    ex_n = 0
    for o in objs(args.existing):
        t = type(o.Geometry).__name__
        if t not in ("Brep", "Extrusion"):
            continue
        b = bbox_of(o.Geometry)
        if not inside(b):
            continue
        ms = mesh_of(o.Geometry)
        if not ms:
            warnings.append(f"existing object (bbox z {b[2]:.0f}..{b[5]:.0f}) has no render mesh; skipped")
            continue
        for m in ms:
            ebuf.add(m)
        ex_n += 1
    if not ebuf.empty():
        out["meshes"].append({"name": "existing", "kind": "existing", "objects": ex_n, **ebuf.pack()})

    # trees: cluster Tree_* meshes by xy (1 m cells) into one record each
    clusters = collections.defaultdict(lambda: [math.inf, -math.inf, math.inf, -math.inf, math.inf, -math.inf])
    tree_meshes = 0
    for o in objs(args.trees):
        if type(o.Geometry).__name__ != "Mesh":
            continue
        name = (o.Attributes.Name or "")
        if not name.lower().startswith("tree"):
            continue
        b = bbox_of(o.Geometry)
        if not inside(b):
            continue
        tree_meshes += 1
        cx, cy = (b[0] + b[3]) / 2, (b[1] + b[4]) / 2
        key = (round(cx / 1.5), round(cy / 1.5))
        c = clusters[key]
        c[0], c[1] = min(c[0], b[0]), max(c[1], b[3])
        c[2], c[3] = min(c[2], b[1]), max(c[3], b[4])
        c[4], c[5] = min(c[4], b[2]), max(c[5], b[5])
    for c in clusters.values():
        x, y = (c[0] + c[1]) / 2, (c[2] + c[3]) / 2
        h = c[5] - c[4]
        rad = max(c[1] - c[0], c[3] - c[2]) / 2
        if h < 1.5:
            continue
        out["trees"].append([round(x - origin[0], 2), round(c[4] - origin[2], 2), round(-(y - origin[1]), 2), round(h, 2), round(min(rad, h / 2), 2)])

    # proposed buildings: block instances on the buildings layer, baked to world coordinates
    defs = {str(d.Id): d for d in model.InstanceDefinitions}
    counts = collections.Counter()
    instances = []
    for o in objs(args.buildings):
        g = o.Geometry
        if type(g).__name__ != "InstanceReference":
            continue
        d = defs.get(str(g.ParentIdefId))
        if d is None:
            warnings.append("instance with unknown definition; skipped")
            continue
        X = transform_of(g)
        buf = Buffer(origin)
        parts = 0
        for oid in d.GetObjectIds():
            po = model.Objects.FindId(oid)
            if po is None:
                continue
            if not layer_vis.get(po.Attributes.LayerIndex, True):
                continue  # hidden sub-layers (cladding studies, alternates) stay out
            for m in mesh_of(po.Geometry):
                buf.add(m, X)
                parts += 1
        if buf.empty():
            warnings.append(f"instance of {d.Name!r} has no render meshes; skipped")
            continue
        counts[d.Name] += 1
        instances.append((d.Name, X, buf, parts))
    # a block definition's own name is the team's working name; it becomes public only when mapped with --label
    unl = sorted({name for name, _X, _b, _p in instances if name not in labels})
    if unl and not args.allow_unlabelled:
        sys.exit(f"block definitions without a public --label: {unl!r}; pass --label \"<name>=<public label>\" for each, or --allow-unlabelled")
    # labels: definition label plus a position word when a definition is placed more than once (north → south)
    by_def = collections.defaultdict(list)
    for name, X, buf, parts in instances:
        by_def[name].append((X.M13, name, X, buf, parts))  # M13 = y translation (north)
    for name, lst in by_def.items():
        lst.sort(key=lambda t: -t[0])
        words = ["north", "middle", "south"] if len(lst) == 3 else (["north", "south"] if len(lst) == 2 else [""] * len(lst))
        if len(lst) > 3:
            words = [str(i + 1) for i in range(len(lst))]
        for (ny, _n, X, buf, parts), w in zip(lst, words):
            base = labels.get(name, name)
            label = f"{base} ({w})" if w else base
            p = buf.pack()
            c = [(p["bbox"][0] + p["bbox"][3]) / 2, (p["bbox"][1] + p["bbox"][4]) / 2, (p["bbox"][2] + p["bbox"][5]) / 2]
            out["buildings"].append({"label": label[:60], "definition": name, "parts": parts, "center": [round(v, 2) for v in c], **p})
    if not out["buildings"]:
        warnings.append(f"no block instances with meshes on layer {args.buildings!r}")

    # curves: paths and features as polylines
    for o in objs(args.curves):
        g = o.Geometry
        if "Curve" not in type(g).__name__:
            continue
        pts = curve_points(g)
        if len(pts) < 2:
            continue
        out["curves"].append([[round(x - origin[0], 2), round(z - origin[2], 2), round(-(y - origin[1]), 2)] for x, y, z in pts])

    total_verts = sum(m["verts"] for m in out["meshes"]) + sum(b["verts"] for b in out["buildings"])
    if total_verts > MAX_VERTS:
        sys.exit(f"{total_verts} vertices exceeds the {MAX_VERTS} cap a phone can take; re-mesh the terrain or buildings lighter in Rhino and export again")
    out["stats"] = {"terrain_verts": out["meshes"][0]["verts"], "meshes": [(m["name"], m["verts"], m["tris"]) for m in out["meshes"]],
                    "buildings": [(b["label"], b["verts"]) for b in out["buildings"]], "definitions": dict(counts),
                    "trees": len(out["trees"]), "tree_meshes": tree_meshes, "curves": len(out["curves"]), "total_verts": total_verts,
                    "site_box_local": [round(site_box[0] - origin[0], 1), round(site_box[3] - origin[0], 1), round(-(site_box[4] - origin[1]), 1), round(-(site_box[1] - origin[1]), 1)]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, separators=(",", ":"))
    args.out.write_text(text, encoding="utf-8")
    for w in warnings:
        log(f"warning: {w}")
    print(json.dumps({"out": str(args.out), "bytes": len(text), **out["stats"], "warnings": len(warnings)}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
