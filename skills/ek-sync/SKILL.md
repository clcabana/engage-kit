---
name: ek-sync
description: Give an Engage Kit tool one shared record, so every device's reactions reach the design team as they are made instead of staying on each phone until someone exports a file. Adds the sending script and an honest privacy card to the user portal, a "Shared record" loader to the admin portal, and ships a small local store for testing and for sessions run from the team's own computer. Use when a project needs many people's reactions in one place, when the admin portal should read everyone's reactions live, or when the manifest's data.sync_target is being set up or changed.
---

# Shared record (sync)

Status, 2026-11-13: first build. Tested only against the local store in this folder. No hosted store exists yet.

An augment: no section. Reactions are still kept on the device (the visitor's own copy, and the fallback when the
store cannot be reached). The shared record is admin-only: no visitor can read another visitor's reactions.

## Run it
Last, after the chain. `chain.py` does not know this skill yet; run it by hand on each built page.
```
python skills/ek-sync/build.py --manifest project.config.json --out output/index.html
python skills/ek-sync/build.py --manifest project.config.json --out output/admin/index.html --portal admin
python skills/ek-sync/server.py --slug <slug> --data <project>/work/store --site output/index.html --admin output/admin/index.html
```
The manifest needs:
```json
"data": { "sync_target": { "url": "/api", "held_by": "a computer the design team runs", "retention": "deleted when the project closes" } }
```
`held_by` and `retention` are printed in the privacy card, so they must be true. A token or key never goes in
the manifest; the build refuses a field that looks like one. The build also refuses when it cannot rewrite the
privacy card, because the page would still say that reactions stay on the device.

## What it adds
- **User portal:** `<script data-feature="sync">`. On every `ek:reaction`, on load, on `online` and when the tab
  comes back, it makes the shared record equal to this device's own: sends what is missing, removes what the
  visitor removed. Tour reactions are not sent. A chip in the privacy card says "Sent to the team: 12 of 12", or
  how many are waiting. `EK.sync = { flush(), state() }`.
- **Device id:** `localStorage['ek:<slug>:device']`, the key `ek-feedback-synthesis` already uses for exports,
  made from the browser's random source when this script gets there first. It is the only thing that lets a
  device remove what it sent, and it is never shown to other visitors.
- **Admin portal:** a "Shared record" card at the top of the Admin section: the team token (password field,
  `sessionStorage`, this tab only), Load, and an optional 30-second refresh. What it loads goes through
  `EK.admin.load(exports, {source, replace})`, the same checks a phone's export file passes.
- **ek-admin, "Everything, by place":** each target with every device's choices, ranks, notes word for word and,
  for sheets, every device's marks drawn together over the sheet, one colour per device.

## The contract (a hosted store must keep it)
- `POST <url>/r`, body `{v: 1, slug, device, op: "add", record: {feature, target, kind, value, id, ts}}` or
  `{v: 1, slug, device, op: "remove", ids: [...]}`. Sent as `text/plain` so a cross-origin page needs no
  preflight. Answers `{ok: true}` or `{ok: false, error}`. **Write-only:** it never returns reactions.
  400 / 413 / 422 mean "this record will never be accepted" (the page stops retrying it); anything else is retried.
- `GET <url>/records?slug=…` with header `X-EK-Admin: <team token>`: `{ok, exports: [{slug, device, count,
  reactions}]}`, one export object per device.
- A device can remove only records stored under its own id. Removing an id that does not exist answers the same
  as removing one that does.

## The local store (`server.py`)
Standard library only. Listens on 127.0.0.1, answers only to `localhost`, `127.0.0.1` and `name.localhost`
host names and origins. `name.localhost` matters for testing: each name is its own browser origin with its own
storage, so `p01.localhost:8787` and `p02.localhost:8787` behave as two devices in one browser.
Record: `<data>/<slug>.jsonl`, append-only. Team token: `<data>/admin-token.txt`, made on first run, never printed.
Limits: 900 KB a request, 2,000 reactions a device, 500 devices, 240 operations a minute a device.
It logs the kind and size of each operation, never the text or the address.

## Not done
- No hosted store (a Cloudflare Worker with the same contract is the obvious next step; it needs the creator's
  own account, like the chat proxy).
- `chain.py` and `ek-shell` do not know the skill; the privacy card is rewritten after the build, and the feature
  sections' own wording ("Download your record", "the team collects it from the device") is unchanged.
- No moderation step, no duplicate-device detection: device counts are what the devices say.
- The sheet images in "Everything, by place" are read by asking the markup section to show each sheet in turn;
  `ek-drawing-markup` should expose them properly.
