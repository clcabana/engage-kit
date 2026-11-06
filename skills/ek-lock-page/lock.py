#!/usr/bin/env python3
"""
ek-lock-page — publish a built Engage Kit tool as an encrypted page that a passphrase opens in the browser.

  python skills/ek-lock-page/lock.py --in output/index.html --out docs/<path>/index.html \
         --passphrase-file <file> [--manifest project.config.json] [--iterations 600000]

Static hosts (GitHub Pages) cannot check a password; a "password page" that hides content with JavaScript
protects nothing, because the content is in the file. This does the only honest thing a static host allows:
the whole built page is encrypted with AES-256-GCM under a key derived from the passphrase (PBKDF2-SHA256,
600,000 iterations, random salt), and the published file holds the ciphertext plus a small gate page that
derives the key with WebCrypto, decrypts in the browser, and writes the page in place (same origin, same
URL, so the tool's storage, hash deep-links and the microphone over HTTPS all work as before).

What it is: confidentiality for the content against anyone who has the link but not the passphrase.
What it is not: access control. One passphrase shared with a group can be passed on; nothing logs who
opened it; revoking means re-encrypting with a new passphrase and telling the group. A short passphrase can
be guessed offline against the downloaded file, so use the long one this script can generate.
The passphrase is read from a file, never from the command line (shell history) and never written here.
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import secrets
import sys
from pathlib import Path

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # type: ignore
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC  # type: ignore
    from cryptography.hazmat.primitives import hashes  # type: ignore
except ImportError:
    sys.exit("the cryptography package is not installed: python -m pip install -r skills/ek-lock-page/requirements.txt")

WORDS = ("amber birch cedar delta ember fjord glade heron ivory juniper kestrel lumen maple nettle ochre pebble quill river "
         "sable thistle umber valley willow yarrow zephyr alder basalt cairn dune estuary fern granite harbour inlet "
         "kelp lichen meadow north orchard prairie quartz ridge summit tundra vale wren").split()


def gen_passphrase(n: int = 7) -> str:
    # 46 words → 5.5 bits each; 7 words + 3 digits ≈ 48 bits. Enough against a curious person or the press over months
    # at 1,000,000 PBKDF2 iterations; not against a funded attacker (see SKILL.md). Pass --words 9 for ~59 bits.
    return "-".join(secrets.choice(WORDS) for _ in range(n)) + "-" + str(secrets.randbelow(900) + 100)


HEX = __import__("re").compile(r"^#[0-9A-Fa-f]{3,8}$")


def colour(v, default: str) -> str:
    """Palette values come from a deck measurement, so they are untrusted; only a hex colour lands in the gate's <style>."""
    v = str(v or "").strip()
    return v if HEX.match(v) else default


def gate_html(name: str, key: str, blob: dict, palette: dict, allow_remember: bool) -> str:
    paper = colour(palette.get("paper"), "#F7F6F2")
    ink = colour(palette.get("ink"), "#23241F")
    marker = colour(palette.get("accent1") or palette.get("marker"), "#E8642C")
    remember = ('  <label><input type="checkbox" id="keep"> remember it on this phone (only if the phone is yours)</label>\n' if allow_remember
                else '  <input type="hidden" id="keep" value="">\n')
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<title>{html.escape(name)} — private</title>
<style>
:root{{--paper:{paper};--ink:{ink};--marker:{marker};--line:color-mix(in srgb,var(--ink) 14%,var(--paper));--mute:color-mix(in srgb,var(--ink) 62%,var(--paper));--card:color-mix(in srgb,var(--paper) 60%,white)}}
@media(prefers-color-scheme:dark){{:root{{--paper:color-mix(in srgb,{ink} 75%,black);--ink:color-mix(in srgb,{paper} 70%,white);--card:color-mix(in srgb,var(--paper) 94%,white)}}}}
*{{box-sizing:border-box}} html,body{{height:100%;margin:0}}
body{{background:var(--paper);color:var(--ink);font:300 16px/1.45 "Helvetica Neue",Helvetica,Arial,sans-serif;display:grid;place-items:center;padding:24px}}
.card{{width:100%;max-width:420px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:22px;display:flex;flex-direction:column;gap:12px;box-shadow:0 1px 2px rgba(20,25,35,.05),0 10px 30px -14px rgba(20,25,35,.22)}}
.kicker{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mute)}} h1{{margin:0;font-size:26px;font-weight:500;line-height:1.05;letter-spacing:-.02em}}
p{{margin:0;color:var(--mute);font-size:14px}} label{{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--mute);min-height:44px}}
input[type=password],input[type=text]{{width:100%;font:inherit;padding:10px 12px;border:1px solid var(--line);border-radius:6px;background:var(--paper);color:var(--ink);min-height:44px}}
button{{font:inherit;font-weight:400;min-height:44px;padding:10px 14px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink);cursor:pointer}}
button.primary{{background:var(--marker);border-color:var(--marker);color:white}} button:disabled{{opacity:.5}}
.row{{display:flex;gap:8px;align-items:center}} .msg{{min-height:20px;font-size:14px;color:var(--marker)}} .msg.ok{{color:var(--mute)}}
:focus-visible{{outline:3px solid var(--marker);outline-offset:2px}}
</style>
</head>
<body>
<form class="card" id="gate" autocomplete="off">
  <span class="kicker">Private</span>
  <h1>{html.escape(name)}</h1>
  <p>This page is encrypted. Enter the passphrase the design team gave you; it opens the tool on this phone and nothing is sent anywhere.</p>
  <input type="password" id="pw" placeholder="Passphrase" aria-label="Passphrase" autocapitalize="off" autocorrect="off" spellcheck="false" required>
  <label><input type="checkbox" id="show"> show it while I type</label>
{remember}  <div class="row"><button type="submit" class="primary" id="open">Open</button><span class="msg" id="msg" role="status" aria-live="polite"></span></div>
  <p>Lost the passphrase? Ask the design team. If the passphrase has changed, the new one is the only one that opens the current page.</p>
</form>
<script id="ek-cipher" type="application/json">{json.dumps(blob)}</script>
<script>
(function () {{
  var B = JSON.parse(document.getElementById("ek-cipher").textContent);
  var key = "ek-lock:" + {json.dumps(key)};
  var ALLOW = {"true" if allow_remember else "false"};
  var $ = function (id) {{ return document.getElementById(id); }};
  var b64 = function (s) {{ var bin = atob(s); var a = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) a[i] = bin.charCodeAt(i); return a; }};
  function say(t, ok) {{ var m = $("msg"); m.textContent = t; m.className = "msg" + (ok ? " ok" : ""); }}
  async function open(pw) {{
    if (!window.crypto || !crypto.subtle) {{ return "nocrypto"; }}
    var enc = new TextEncoder();
    var km = await crypto.subtle.importKey("raw", enc.encode(pw.normalize("NFKC")), "PBKDF2", false, ["deriveKey"]);
    var k = await crypto.subtle.deriveKey({{ name: "PBKDF2", salt: b64(B.salt), iterations: B.iter, hash: "SHA-256" }}, km, {{ name: "AES-GCM", length: 256 }}, false, ["decrypt"]);
    var pt;
    try {{ pt = await crypto.subtle.decrypt({{ name: "AES-GCM", iv: b64(B.iv) }}, k, b64(B.data)); }} catch (e) {{ return false; }}
    var html = new TextDecoder().decode(pt);
    document.open(); document.write(html); document.close();
    return true;
  }}
  async function go(pw, remember) {{
    $("open").disabled = true; say("Opening…", true);
    var ok = false;
    try {{ ok = await open(pw); }} catch (e) {{ ok = false; }}
    if (ok === "nocrypto") {{ $("open").disabled = false; say("This browser cannot decrypt the page: it needs a current browser over https."); return; }}
    if (!ok) {{ $("open").disabled = false; say("That passphrase does not open this page. Check it and try again."); try {{ localStorage.removeItem(key); }} catch (e) {{}} return; }}
    try {{ if (ALLOW && remember) localStorage.setItem(key, pw); else localStorage.removeItem(key); }} catch (e) {{}}
  }}
  $("show").addEventListener("change", function () {{ $("pw").type = this.checked ? "text" : "password"; }});
  $("gate").addEventListener("submit", function (e) {{ e.preventDefault(); var pw = $("pw").value.trim(); if (!pw) return; go(pw, ALLOW && !!$("keep").checked); }});
  var saved = ""; try {{ saved = ALLOW ? (localStorage.getItem(key) || "") : ""; if (!ALLOW) localStorage.removeItem(key); }} catch (e) {{}}
  if (saved) {{ $("keep").checked = true; go(saved, true); }} else {{ $("pw").focus(); }}
}})();
</script>
</body>
</html>
"""


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="src", type=Path, required=True, help="the built tool (output/index.html)")
    ap.add_argument("--out", type=Path, required=True, help="where the encrypted page goes (e.g. docs/<path>/index.html)")
    ap.add_argument("--passphrase-file", type=Path, required=True, help="a file whose first line is the passphrase; created with a generated passphrase when missing")
    ap.add_argument("--manifest", type=Path, default=None, help="project.config.json for the gate page's name and colours")
    ap.add_argument("--title", default=None, help="what the public gate page calls the tool (default: the manifest's project name; use a neutral title when the client is not to be named on the open web)")
    ap.add_argument("--iterations", type=int, default=1_000_000)
    ap.add_argument("--min-length", type=int, default=24, help="refuse a passphrase shorter than this (offline guessing is the threat)")
    ap.add_argument("--words", type=int, default=7, help="words in a generated passphrase (7 ≈ 48 bits, 9 ≈ 59 bits)")
    ap.add_argument("--allow-remember", action="store_true", help="offer 'remember on this phone'. Only when the page is on its own origin: on a shared origin (user.github.io) every other page there could read the stored passphrase.")
    args = ap.parse_args(argv)
    if not args.src.is_file():
        sys.exit(f"not a file: {args.src}")
    if args.passphrase_file.exists():
        pw = args.passphrase_file.read_text(encoding="utf-8").splitlines()[0].strip() if args.passphrase_file.read_text(encoding="utf-8").strip() else ""
        generated = False
    else:
        pw = gen_passphrase(args.words)
        args.passphrase_file.parent.mkdir(parents=True, exist_ok=True)
        args.passphrase_file.write_text(pw + "\n", encoding="utf-8")
        try:
            os.chmod(args.passphrase_file, 0o600)
        except OSError:
            pass
        generated = True
    if len(pw) < args.min_length or len(set(pw)) < 8:
        sys.exit(f"passphrase is too weak ({len(pw)} characters, {len(set(pw))} distinct); use at least {args.min_length} characters with real variety, or delete the file to have one generated")
    name, palette, lock_key, manifest = "Engage Kit tool", {}, "", None
    if args.manifest and args.manifest.is_file():
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        name = str((manifest.get("project") or {}).get("name") or name)[:80]
        palette = (manifest.get("project") or {}).get("palette") or {}
        lock_key = str(((manifest.get("hosting") or {}).get("lock_key")) or "")
    # the gate's storage key is random and kept in the manifest (hosting.lock_key) so it survives re-locks; it never derives
    # from the project's name, which a guess could confirm
    import re
    if not re.fullmatch(r"[0-9a-f]{12}", lock_key):
        lock_key = secrets.token_hex(6)
        if manifest is not None:
            manifest.setdefault("hosting", {})["lock_key"] = lock_key
            args.manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.title:
        name = args.title.strip()[:80]
    plain = args.src.read_bytes()
    # the decrypted page replaces the gate, so it carries its own robots / referrer rules
    meta = b'<meta name="robots" content="noindex, nofollow">\n<meta name="referrer" content="no-referrer">\n'
    if b'name="robots"' not in plain:
        plain = plain.replace(b"<head>\n", b"<head>\n" + meta, 1) if b"<head>\n" in plain else plain.replace(b"<head>", b"<head>" + meta, 1)
    salt, iv = secrets.token_bytes(16), secrets.token_bytes(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=args.iterations)
    import unicodedata
    k = kdf.derive(unicodedata.normalize("NFKC", pw).encode("utf-8"))
    ct = AESGCM(k).encrypt(iv, plain, None)
    blob = {"v": 1, "kdf": "PBKDF2-SHA256", "iter": args.iterations, "cipher": "AES-256-GCM",
            "salt": base64.b64encode(salt).decode(), "iv": base64.b64encode(iv).decode(), "data": base64.b64encode(ct).decode()}
    out = gate_html(name, lock_key, blob, palette, args.allow_remember)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(out, encoding="utf-8", newline="\n")
    print(json.dumps({"out": str(args.out), "bytes": len(out.encode("utf-8")), "plain_bytes": len(plain), "iterations": args.iterations,
                      "passphrase": ("generated into " if generated else "read from ") + str(args.passphrase_file), "passphrase_length": len(pw),
                      "remember_offered": args.allow_remember, "lock_key_in_manifest": manifest is not None}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
