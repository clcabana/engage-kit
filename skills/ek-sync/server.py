#!/usr/bin/env python3
"""
ek-sync local store — one small server that keeps every device's reactions in one shared record.

  python skills/ek-sync/server.py --slug pacific-design-institute --data projects/pdi-demo/work/store \
      --site projects/pdi-demo/output/test/index.html --admin projects/pdi-demo/output/test/admin/index.html [--port 8787]

For testing and for a session run from the design team's own computer. It listens on 127.0.0.1 only and answers
only to localhost names (localhost, 127.0.0.1, anything.localhost), so it is not a public host. A hosted store
must keep the same contract (SKILL.md, "The contract").

  POST /api/r         visitors: {v, slug, device, op: "add", record} | {op: "remove", ids}. Write-only: never returns
                      anyone's reactions. A device can remove only what it sent.
  GET  /api/records   the team: needs the X-EK-Admin token; returns one export object per device, the same shape a
                      phone downloads from What we heard, so ek-admin reads them through the same checks.
  GET  /  and /admin/ the two built pages, when --site / --admin are given.

Storage: <data>/<slug>.jsonl, one line per accepted operation (append-only, replayed at start).
The admin token is made on first run and kept in <data>/admin-token.txt; it is never printed.
Standard library only. Nothing here logs visitor text or addresses.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

KINDS = ("voice", "note", "pin", "vote", "edit", "submission", "markup", "question")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
DEV_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
HOST_RE = re.compile(r"^(localhost|127\.0\.0\.1|\[::1\]|[a-z0-9-]{1,40}\.localhost)(:\d{1,5})?$", re.I)
ORIGIN_RE = re.compile(r"^http://(localhost|127\.0\.0\.1|\[::1\]|[a-z0-9-]{1,40}\.localhost)(:\d{1,5})?$", re.I)

MAX_BODY = 900_000            # a photo of a sketch is at most 600k base64 characters
MAX_PER_DEVICE = 2000         # reactions one device may hold
MAX_DEVICES = 500
MAX_TOTAL_BYTES = 300_000_000
RATE_DEVICE = 240             # operations a minute from one device id
RATE_ADDR = 2400              # operations a minute from one address (a workshop shares one)
MAX_REMOVE = 2000


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


FEATURE_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
KEY_RE = re.compile(r"^[a-f0-9]{32,64}$")
MAX_NOTE = 4000
MAX_POINTS = 20000
MAX_PLAIN = 300_000           # any record that is not a photo or a voice clip


def value_ok(kind: str, v, size: int) -> bool:
    """Per-kind shape and size. The admin page checks again before it draws anything."""
    if kind in ("submission", "voice"):
        return isinstance(v, dict)
    if size > MAX_PLAIN:
        return False
    if kind == "note":
        if isinstance(v, str):
            return 0 < len(v) <= MAX_NOTE
        return isinstance(v, dict) and isinstance(v.get("text"), str) and 0 < len(v["text"]) <= MAX_NOTE
    if kind == "vote":
        return (isinstance(v, str) and len(v) <= 40) or (isinstance(v, int) and not isinstance(v, bool) and 0 < v < 100) or isinstance(v, dict)
    if kind == "markup":
        if not (isinstance(v, dict) and isinstance(v.get("paths"), list) and isinstance(v.get("texts"), list)):
            return False
        if len(v["paths"]) > 400 or len(v["texts"]) > 100:
            return False
        pts = 0
        for p in v["paths"]:
            if not (isinstance(p, dict) and isinstance(p.get("pts"), list)):
                return False
            pts += len(p["pts"])
        return pts <= MAX_POINTS and all(isinstance(t, dict) and isinstance(t.get("t"), str) and len(t["t"]) <= 200 for t in v["texts"])
    return True


def valid_record(r, size: int = 0) -> bool:
    return (isinstance(r, dict)
            and isinstance(r.get("feature"), str) and bool(FEATURE_RE.match(r["feature"]))
            and isinstance(r.get("target"), str) and len(r["target"]) <= 1000
            and r.get("kind") in KINDS
            and isinstance(r.get("id"), str) and 0 < len(r["id"]) <= 64
            and isinstance(r.get("ts"), str) and 0 < len(r["ts"]) <= 40
            and r.get("tour") is not True
            and value_ok(r["kind"], r.get("value"), size))


def line_of(op: dict) -> str:
    """One log line; raises ValueError for anything that would not read back (NaN, Infinity, lone surrogates)."""
    s = json.dumps(op, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    s.encode("utf-8")
    return s


def _no_constants(name):
    raise ValueError(name)


def clean_record(r: dict) -> dict:
    return {"feature": r["feature"], "target": r["target"], "kind": r["kind"], "value": r.get("value"), "id": r["id"], "ts": r["ts"]}


class Store:
    def __init__(self, data: Path, slug: str):
        self.slug = slug
        self.path = data / f"{slug}.jsonl"
        self.lock = threading.Lock()
        self.devices: dict[str, dict[str, dict]] = {}
        self.keys: dict[str, str] = {}      # device -> sha256 of the secret its browser sends; only that browser may add or remove
        self.bytes = 0
        self.rate: dict[str, list[float]] = {}
        self.log = None
        data.mkdir(parents=True, exist_ok=True)
        if self.path.is_file():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                try:
                    self._apply(json.loads(line, parse_constant=_no_constants))
                except Exception:
                    continue   # a damaged line loses one operation, not the record
        self._rewrite()   # the file holds what is on record and nothing that was removed

    def _apply(self, op: dict) -> None:
        dev = op.get("device")
        if not isinstance(dev, str) or not DEV_RE.match(dev):
            return
        if op.get("op") == "key" and isinstance(op.get("kh"), str):
            self.keys.setdefault(dev, op["kh"])
        elif op.get("op") == "add" and valid_record(op.get("record")):
            self.devices.setdefault(dev, {})[op["record"]["id"]] = clean_record(op["record"])
        elif op.get("op") == "remove":
            d = self.devices.get(dev) or {}
            for i in op.get("ids") or []:
                d.pop(i, None)
            if dev in self.devices and not d:
                del self.devices[dev]

    def _write(self, line: str) -> None:
        self.log.write(line + "\n")
        self.log.flush()
        self.bytes += len(line)

    def _rewrite(self) -> None:
        """Write the record as it stands to a new file and swap it in: a removed reaction is gone from the disk too."""
        if self.log:
            self.log.close()
        tmp = self.path.with_suffix(".jsonl.tmp")
        self.bytes = 0
        with tmp.open("w", encoding="utf-8", newline="\n") as f:
            for dev, kh in self.keys.items():
                if dev in self.devices:
                    f.write(line_of({"op": "key", "device": dev, "kh": kh}) + "\n")
            for dev, recs in self.devices.items():
                for rec in recs.values():
                    try:
                        s = line_of({"op": "add", "device": dev, "record": rec})
                    except ValueError:
                        continue
                    f.write(s + "\n")
                    self.bytes += len(s)
        os.replace(tmp, self.path)
        self.keys = {d: k for d, k in self.keys.items() if d in self.devices}
        self.log = self.path.open("a", encoding="utf-8", newline="\n")

    def key_ok(self, dev: str, kh: str) -> bool:
        have = self.keys.get(dev)
        return have is None or hmac.compare_digest(have, kh)

    def allow(self, key: str, limit: int) -> bool:
        t = time.monotonic()
        q = [x for x in self.rate.get(key, []) if t - x < 60]
        if len(q) >= limit:
            self.rate[key] = q
            return False
        q.append(t)
        self.rate[key] = q
        if len(self.rate) > 5000:
            self.rate = {k: v for k, v in self.rate.items() if v and t - v[-1] < 60}
        return True

    def add(self, dev: str, kh: str, rec: dict) -> tuple[int, str]:
        with self.lock:
            if not self.key_ok(dev, kh):
                return 403, "device_key_refused"
            d = self.devices.get(dev)
            if d is None and len(self.devices) >= MAX_DEVICES:
                return 429, "store_full"
            if d is not None and rec["id"] not in d and len(d) >= MAX_PER_DEVICE:
                return 429, "device_full"
            if self.bytes > MAX_TOTAL_BYTES:
                return 429, "store_full"
            rec = clean_record(rec)
            op = {"op": "add", "device": dev, "record": rec}
            try:
                line = line_of(op)
            except ValueError:
                return 422, "bad_record"
            if dev not in self.keys:   # written before the record, so the disk never holds a record without its owner
                self._write(line_of({"op": "key", "device": dev, "kh": kh}))
                self.keys[dev] = kh
            self._write(line)
            self._apply(op)
            return 200, ""

    def remove(self, dev: str, kh: str, ids: list[str]) -> tuple[int, int]:
        with self.lock:
            if dev not in self.devices:
                return 200, 0
            if not self.key_ok(dev, kh):
                return 403, 0
            d = self.devices[dev]
            hit = [i for i in ids if i in d]
            if hit:
                self._apply({"op": "remove", "device": dev, "ids": hit})
                self._rewrite()
            return 200, len(hit)

    def exports(self, project: str) -> list[dict]:
        with self.lock:
            stamp = now_iso()
            return [{"project": project, "slug": self.slug, "device": dev, "exported_at": stamp, "source": "ek-sync",
                     "count": len(recs), "reactions": list(recs.values())}
                    for dev, recs in self.devices.items() if recs]


class Handler(BaseHTTPRequestHandler):
    server_version = "ek-sync/0.1"
    protocol_version = "HTTP/1.1"
    timeout = 15   # a stalled or idle connection gives its thread back
    store: Store
    token: str
    site: Path | None
    admin: Path | None
    project: str

    def log_message(self, fmt, *args):   # the default line carries the address and the path; say less
        return

    def note(self, text: str) -> None:
        print(f"[ek-sync] {datetime.now().strftime('%H:%M:%S')} {text}", file=sys.stderr, flush=True)

    # ---- plumbing ----
    def origin_ok(self) -> str | None:
        """'' when there is no Origin header, the origin when it is allowed, None when it is not."""
        o = self.headers.get("Origin")
        if o is None:
            return ""
        return o if ORIGIN_RE.match(o) else None

    def send(self, code: int, body: bytes, ctype: str, origin: str | None = "", extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, code: int, obj: dict, origin: str | None = "") -> None:
        self.send(code, json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8", origin)

    def gate(self) -> tuple[bool, str]:
        """Host and Origin checks shared by every route. Returns (ok, origin)."""
        if not HOST_RE.match(self.headers.get("Host") or ""):
            self.close_connection = True
            self.send_json(403, {"ok": False, "error": "host_not_allowed"})
            return False, ""
        o = self.origin_ok()
        if o is None:
            self.close_connection = True
            self.send_json(403, {"ok": False, "error": "origin_not_allowed"})
            return False, ""
        return True, o

    # ---- routes ----
    def do_OPTIONS(self):
        ok, origin = self.gate()
        if not ok:
            return
        self.send(204, b"", "text/plain", origin, {"Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                                                    "Access-Control-Allow-Headers": "content-type, x-ek-admin",
                                                    "Access-Control-Max-Age": "600"})

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        ok, origin = self.gate()
        if not ok:
            return
        u = urlsplit(self.path)
        if u.path == "/api/records":
            return self.records(u, origin)
        page = self.site if u.path in ("/", "/index.html") else self.admin if u.path in ("/admin", "/admin/", "/admin/index.html") else None
        if page is None or not page.is_file():
            return self.send(404, b"Not found", "text/plain; charset=utf-8")
        if u.path == "/admin":
            return self.send(301, b"", "text/plain", "", {"Location": "/admin/"})
        self.send(200, page.read_bytes(), "text/html; charset=utf-8")

    def records(self, u, origin: str) -> None:
        given = self.headers.get("X-EK-Admin") or ""
        if not given or not hmac.compare_digest(given.encode("utf-8"), self.token.encode("utf-8")):
            # only wrong tokens are counted, so a page that guesses cannot lock the team out
            if not self.store.allow("admin-bad|" + self.client_address[0], 30):
                return self.send_json(429, {"ok": False, "error": "slow_down"}, origin)
            self.note("records: token refused")
            return self.send_json(403, {"ok": False, "error": "admin_token_refused"}, origin)
        slug = (parse_qs(u.query).get("slug") or [""])[0]
        if slug != self.store.slug:
            return self.send_json(404, {"ok": False, "error": "unknown_project"}, origin)
        ex = self.store.exports(self.project)
        self.note(f"records: {sum(e['count'] for e in ex)} reactions from {len(ex)} devices sent to the admin page")
        self.send_json(200, {"ok": True, "slug": slug, "generated_at": now_iso(), "devices": len(ex),
                             "count": sum(e["count"] for e in ex), "exports": ex}, origin)

    def do_POST(self):
        ok, origin = self.gate()
        if not ok:
            return
        if urlsplit(self.path).path != "/api/r":
            self.close_connection = True
            return self.send_json(404, {"ok": False, "error": "not_found"}, origin)
        try:
            n = int(self.headers.get("Content-Length") or "")
        except ValueError:
            n = -1
        if n < 0 or n > MAX_BODY:
            self.close_connection = True   # the body is not read
            return self.send_json(413 if n > MAX_BODY else 411, {"ok": False, "error": "too_large" if n > MAX_BODY else "length_required"}, origin)
        raw = self.rfile.read(n)
        if not self.store.allow("addr|" + self.client_address[0], RATE_ADDR):
            return self.send_json(429, {"ok": False, "error": "slow_down"}, origin)
        try:
            j = json.loads(raw.decode("utf-8"), parse_constant=_no_constants)   # NaN and Infinity are not JSON
            line_of(j)                                                         # nor is text that cannot be written back
        except Exception:
            return self.send_json(400, {"ok": False, "error": "not_json"}, origin)
        if not isinstance(j, dict) or j.get("slug") != self.store.slug:
            return self.send_json(400, {"ok": False, "error": "unknown_project"}, origin)
        dev = j.get("device")
        if not isinstance(dev, str) or not DEV_RE.match(dev):
            return self.send_json(400, {"ok": False, "error": "bad_device"}, origin)
        key = j.get("key")
        if not isinstance(key, str) or not KEY_RE.match(key):
            return self.send_json(400, {"ok": False, "error": "bad_key"}, origin)
        kh = hashlib.sha256(key.encode("ascii")).hexdigest()
        if not self.store.allow("dev|" + dev, RATE_DEVICE):
            return self.send_json(429, {"ok": False, "error": "slow_down"}, origin)
        op = j.get("op")
        if op == "add":
            rec = j.get("record")
            if not valid_record(rec, n):
                return self.send_json(422, {"ok": False, "error": "bad_record"}, origin)
            code, err = self.store.add(dev, kh, rec)
            if code != 200:
                return self.send_json(code, {"ok": False, "error": err}, origin)
            self.note(f"add {rec['kind']} ({n} bytes)")
            return self.send_json(200, {"ok": True}, origin)
        if op == "remove":
            ids = j.get("ids")
            if not isinstance(ids, list) or len(ids) > MAX_REMOVE or not all(isinstance(i, str) and len(i) <= 64 for i in ids):
                return self.send_json(422, {"ok": False, "error": "bad_ids"}, origin)
            code, hit = self.store.remove(dev, kh, ids)
            if code != 200:
                return self.send_json(code, {"ok": False, "error": "device_key_refused"}, origin)
            self.note(f"remove {hit} of {len(ids)}")
            return self.send_json(200, {"ok": True}, origin)   # the same answer whether or not the ids existed
        return self.send_json(422, {"ok": False, "error": "bad_op"}, origin)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True, help="the project's slug (PROJECT.slug in the built page)")
    ap.add_argument("--data", type=Path, required=True, help="folder for the record and the admin token; keep it out of git")
    ap.add_argument("--site", type=Path, default=None, help="the built user portal, served at /")
    ap.add_argument("--admin", type=Path, default=None, help="the built admin portal, served at /admin/")
    ap.add_argument("--project", default="", help="project name written into the exports")
    ap.add_argument("--port", type=int, default=8787)
    args = ap.parse_args(argv)
    if not SLUG_RE.match(args.slug):
        sys.exit("[ek-sync] --slug must look like the page's PROJECT.slug (lower case letters, digits, hyphens)")
    store = Store(args.data, args.slug)
    tok = args.data / "admin-token.txt"
    if not tok.is_file() or len(tok.read_text(encoding="utf-8").strip()) < 24:
        tok.write_text(secrets.token_urlsafe(24) + "\n", encoding="utf-8")
    Handler.store = store
    Handler.token = tok.read_text(encoding="utf-8").strip()
    Handler.site, Handler.admin, Handler.project = args.site, args.admin, (args.project or args.slug)[:80]
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    srv.daemon_threads = True
    n = sum(len(d) for d in store.devices.values())
    print(f"[ek-sync] {args.slug}: {n} reactions from {len(store.devices)} devices on record; http://localhost:{args.port}/ "
          f"(admin at /admin/, token in {tok})", file=sys.stderr, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
