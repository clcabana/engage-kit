---
name: ek-publish
description: Publish a finished Engage Kit tool as two portals — a user portal (public or passphrase) for the community and an admin portal (passphrase) for the design team — on the creator's own GitHub Pages or their own domain, and write the private project README with both links, where the passphrases are, how to re-lock, the chat setup and what the host sees. Use after the final review, or whenever the person asks to publish, host, re-lock, change a passphrase or get the links.
---

# Publish

Runs after the final review (orchestrator step 8). It reads the `publish` block that the kickoff questions wrote
(`ek-project-manifest` step 5) and does everything except the one thing that is the person's: putting the pages
online (uploading, or committing and pushing).

## Run it
```
python -X utf8 skills/ek-publish/publish.py --manifest <project>/project.config.json --brief <project>/work/brief.json
       [--root .] [--out-dir <folder>]
```
- `--out-dir` writes every output (plain builds, README, pages folder, dist) under one folder, for a trial run that
  must not touch the repo. The manifest is still updated (generated paths, `published`).
- `--run-gh` is for **a person at a terminal only. Agents never pass `--run-gh`.** It creates a public repository
  with the person's GitHub account and turns on Pages; the script refuses it unless it runs in an interactive
  terminal, prints exactly what will be created (owner/name, public, Pages from `main` and which folder) and needs the
  person to type the repository name. Without a terminal it prints the commands only. It never commits or pushes.

## The `publish` block
```json
"publish": {
  "host": "github-pages",                 // or "own"
  "repo": "owner/name",                   // github-pages
  "pages_dir": "docs",                    // github-pages: one folder name, letters/digits/-/_ (up to 40)
  "domain": "https://example.org/engage", // own: https only
  "user_portal":  { "lock": true, "path": "", "title": "Engagement tool" },
  "admin_portal": { "lock": true, "path": "", "title": "Design team portal" },
  "passphrases_dir": "<folder outside the repo>",
  "public_readme": false                  // true: a minimal README in the pages folder (title + user link)
}
```
- `path` empty → a random hex path is generated and written back. A path that is not lowercase hex (8+ characters)
  stops the run; so does a `pages_dir` that is not a plain folder name (`../x` is refused).
- `title` is what a locked gate shows and the only name a public README carries, so keep it neutral.
- A relative `passphrases_dir` is taken from **the manifest's folder** (the script prints the resolved folder).
- After a successful run each portal block gets `"published": true` and `"published_on"`. From then on, a locked
  portal whose passphrase file is missing stops the run with a clear message instead of generating a new passphrase:
  a mistyped folder must never silently lock a group out. To issue a new passphrase on purpose, delete the file, set
  that portal's `published` to false, re-run, publish, and tell the group.

## What it does
1. Builds the **user portal** with `skills/ek-shell/chain.py` (`--portal user`: `ek-admin` is never in it) and the
   **admin portal** with `chain.py --portal admin`. With `chat.mode == "direct"` the user portal has no `ek-chat`.
   A temporary manifest left by a killed build is removed on every exit.
2. Locks each portal whose `lock` is true with `skills/ek-lock-page/lock.py`, each with its own passphrase file
   (`user.txt`, `admin.txt` in `passphrases_dir`; a newly generated one is announced loudly, never shown).
3. Places them at `<pages_dir>/p/<path>/index.html` (github-pages) or `dist/<path>/index.html` (own). The plain
   builds stay in `output/` (`index.html`, `admin/index.html`) and are never published.
4. Writes the **project README** to `output/README.md` only. It is private ("keep this file out of any public
   repository"): both links, passphrase file names and folder, rebuild and re-lock, the chat setup pointer, what the
   host sees, the manifest's data notes, the hosting steps. **Nothing else goes into the pages folder** unless
   `public_readme` is true; then `<pages_dir>/README.md` holds the neutral title, the user-portal link and, when
   locked, "Ask the design team for the passphrase". Never the admin link, the project name or the data notes.
5. Prints the two links and the hosting steps.

Re-running is safe: same paths, same passphrases (read from their files), fresh ciphertext.

## Putting it online: GitHub Pages, no command line
1. Create a GitHub account (github.com, free).
2. If the tool is for a closed group, create a free **organisation** for the project (your picture → Your
   organizations → New organization → Free). Its pages get their own web address (`<org>.github.io`), which keeps
   this group's data apart from your other pages. Use it as the `owner` in `publish.repo`. A separate repository on
   your **own account** also works and is simpler, but every Pages site on one account shares one address
   (`<you>.github.io`): your other pages there can read what the tool saves in the browser, so the gate offers no
   "remember" and an admin should not tick "Keep on this computer" for the key. Say this to the person; it is their call.
3. Create a **public** repository in it (+ → New repository). Free Pages needs a public repository; a locked portal
   is stored there only as ciphertext.
4. Upload the `docs` folder (the pages folder) through the website: **Add file → Upload files**, drag in the folder,
   Commit changes. GitHub Desktop works too. Upload nothing else: never `output/`, the private README or the
   passphrase files.
5. **Settings → Pages**: deploy from a branch, branch `main`, folder `/docs`, Save.
6. Wait a minute or two, then open the two links the script printed.

People who use a terminal can use the printed `gh` commands instead.

**Own domain / existing website:** upload the `dist` folder's contents to any static host that serves HTTPS. The
microphone (voice reactions) and the encrypted pages (WebCrypto) both need HTTPS.

**The admin portal need not be hosted at all.** The team can open the plain `output/admin/index.html` from their own
computer: the strongest separation. Then host only the user portal.

## Rules
- Nothing here reads, holds or prints a passphrase or an API key. If the `chat` or `publish` block holds a field that
  looks like a key, the script stops and names the field (not the value).
- `passphrases_dir` must not be inside the pages folder, `dist/` or the build output; inside the kit it must be
  under the gitignored `projects/`, or the script warns.
- The admin portal is locked unless the person explicitly says otherwise (the script warns).
- Agents never pass `--run-gh` and never commit, push or upload; that is the person's step.
- Chat keys: proxy mode keeps the key in the Cloudflare Worker (`skills/ek-chat/PROXY.md`); direct mode keeps it in
  the admin's own browser. Never in the manifest, the repo or the README.
