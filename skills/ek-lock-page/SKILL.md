---
name: ek-lock-page
description: Publish a built Engage Kit tool on a static host (GitHub Pages) as an encrypted page that opens with a passphrase in the browser — AES-256-GCM over the whole page, key from PBKDF2, decrypted by WebCrypto and written in place so storage, deep links and the microphone keep working. Use whenever a tool must go on a public static host but its content is for a closed group, or the user asks for a password on the site; never present it as access control.
---

# Lock a page

A static host cannot check a password, and a page that merely hides its content behind a JavaScript prompt
protects nothing. This skill encrypts the whole built page, so the host only ever holds ciphertext, and
ships a small gate page that decrypts it in the browser.

## Run it
```
python -m pip install -r skills/ek-lock-page/requirements.txt         # once
python skills/ek-lock-page/lock.py --in output/index.html --out docs/<path>/index.html \
       --passphrase-file <somewhere outside the repo>/passphrase.txt --manifest project.config.json
```
If the passphrase file does not exist, the script generates a seven-word passphrase into it (chmod 600
where the OS allows; `--words 9` for a stronger one) and refuses anything under 24 characters or without
variety. The passphrase is never on the command line and never printed. Re-run after every rebuild of
the tool; re-run with a new passphrase file to change it. Publish under a **random path** (`docs/p/<hex>/`)
and pass `--title` so the public gate carries no project name; the gate's storage key is a random
`hosting.lock_key` the script writes into the manifest, never derived from the name.

## What the visitor sees
A card in the project's colours (hex values only; anything else from the manifest falls back to the
defaults): a neutral title, "This page is encrypted. Enter the passphrase the design team gave you; it
opens the tool on this phone and nothing is sent anywhere", the passphrase field (with "show it while I
type"), and Open. A wrong passphrase fails with a plain message (GCM authentication, so there is no
partial decryption); a browser without WebCrypto gets its own message. On success the tool replaces the
gate in place: same origin and URL, so `localStorage['ek:<slug>']`, `#tour` and `#model` deep links and
`getUserMedia` over HTTPS behave exactly as on an open page. `noindex` and `no-referrer` are set on the
gate and injected into the decrypted page.
**Remember on this phone** exists only behind `--allow-remember`, for a page on its own origin: on a
shared origin such as `user.github.io` every other page of that account (samples, demos, their CDN
scripts) can read a stored passphrase, so there the visitor types it each time.

## What it protects, and what it does not
- Protects the content of the page (photographs, the 3D model, the deck's facts) from anyone who has the
  link but not the passphrase, with real cryptography (AES-256-GCM, PBKDF2-SHA256 at 1,000,000
  iterations, a random 16-byte salt and 12-byte IV per lock). A generated seven-word passphrase is about
  48 bits: years of rented GPU time to guess offline, which holds against a curious person or the press,
  not against a funded attacker; `--words 9` (about 59 bits) when that matters.
- Every published version stays in the host's git history and opens with the passphrase in use when it was
  published; a new passphrase protects new versions only.
- Reactions stay unencrypted on each phone; the host (GitHub) and the CDN see each visit's IP and the
  ciphertext, never the content or the reactions.
- Does **not** control access: one passphrase shared with a group can be passed on; nothing records who
  opened the page; the only revocation is a new passphrase and a new publish. The ciphertext can be
  downloaded and attacked offline, which is why the passphrase is long.
- "Remember on this phone" stores the passphrase in that browser's localStorage; the label says to use it
  only on one's own phone. A shared device must not use it.
- The reaction store is unencrypted browser storage as before; the lock is for the page, not the device.
- The team must still tell people, in the consent copy and in HANDOFF, where the tool is hosted and that
  the host (GitHub) sees the ciphertext, the visit and the IP address, not the content or the reactions.

## Rules
- Use it only where the manifest records the decision and the trade-off (`hosting.decision`), and only
  after the person has read the "does not" list above.
- The passphrase file lives outside the repo (for a real project, in its gitignored `projects/` folder or
  in the team's password manager); `lock.py` never writes it anywhere else.
- The encrypted page may be committed; the plain `output/index.html` of a real project must not be.
- The gate page makes no network request and loads no script; the decrypted page is whatever the build
  produced, with its own pinned CDN scripts.
