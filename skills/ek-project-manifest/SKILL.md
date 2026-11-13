---
name: ek-project-manifest
description: Decide which Engage Kit features a specific project should install, and write project.config.json with a one-sentence reason for each include and skip. Use this after ek-ingest-presentation, whenever the user asks what features their engagement tool should have, wants to add or remove a feature, or asks why a feature was or wasn't included.
---

# Project manifest

The manifest is the whole point of Engage Kit: a project installs only what its decisions need. Write
`project.config.json` (schema in the repo root example) from `work/brief.json`.

## Decision table
| Install | When the brief shows |
|---|---|
| `ek-shell` | always |
| `ek-timeline` | ≥ 3 dated history events, or the audience includes people new to the site |
| `ek-site-massing-3d` | ≥ 2 massing options, or any decision point about height, footprint, or placement |
| `ek-program-diagram` | ≥ 4 program areas, or any program marked `contested` |
| `ek-voice-reactions` | audience meets in person (drop-in/workshop) or includes groups less likely to type |
| `ek-massing-markup` | `ek-site-massing-3d` installed and a decision point is location-specific |
| `ek-feedback-synthesis` | always when any other feature is installed |

## Step 0: accounts (asked before ingest)
Some accounts take a day to set up, so ask once at the very start, before the deck is read, and let the person
start them while the tool is built:
- **GitHub** (free), to host the pages; or the creator's own website, if they have one that serves HTTPS.
- **An Anthropic account, only if they want the assistant:** a separate API key for this project and a monthly
  spending limit set on the account. The key is never given to the kit or pasted into the chat.
- **Cloudflare (free), only if visitors should be able to ask the assistant:** it hosts the small proxy that holds
  the key (`skills/ek-chat/PROXY.md`). The team alone can use the assistant without it.

Say plainly what the recommended start is: **both portals locked, the assistant for the team only.** And that the
admin portal does not need to be hosted at all: it can be opened from the creator's own computer, which is the
strongest separation. The hosting, portal and chat choices themselves are still made at step 5 below (orchestrator
step 2).

## Steps
1. Apply the table. For each row write the evidence from the brief in the `reason` field.
2. List skipped features with reasons; the person should be able to overrule in one word.
3. Copy `palette`, `typeface`, `audience` into `project.name/palette/typeface/audience`.
4. Present the list to the person and wait for confirmation. Do not run any feature skill before that.
5. **Ask the kickoff questions** (together with the confirmation, one short message), and write the answers into the
   manifest's `publish` and `chat` blocks (schema in `skills/ek-publish/SKILL.md` and `skills/ek-chat/`):
   - **Hosting:** your own GitHub Pages (free; a public repo, `owner/name`) or your own domain / existing website
     (any static host with HTTPS; the address). → `publish.host`, `publish.repo` + `pages_dir` or `publish.domain`.
   - **User portal** (the community's page): public, or behind a passphrase? → `publish.user_portal.lock`.
   - **Admin portal** (the design team's page, with the Admin section): always behind its own passphrase; confirm.
     → `publish.admin_portal.lock: true`. Where should the passphrase files live, outside the repo (for a real
     project its gitignored `projects/<name>/` folder or the team's password manager)? → `publish.passphrases_dir`.
     Leave both `path`s empty; `ek-publish` generates random ones.
   - **Chat** (the assistant): none; **proxy** (a Cloudflare Worker the person deploys holds their LLM key; both
     portals can chat: the user portal answers questions, the admin portal analyses reactions; a daily cap); or
     **direct, admin only** (a team member pastes their own key into the admin portal on their own device; the user
     portal gets no chat). → `chat: {mode, proxy_url, provider, model, daily_cap}`. Say plainly: **a key never goes
     into the manifest, the repo or any file the kit writes**; do not ask for it, and if the person pastes one, tell
     them to revoke it.

## Rules
- Maximum 5 feature sections for a public audience; attention is the scarce resource at a drop-in table.
- A feature that cannot record a reaction with context is not installed, whatever the deck shows.
