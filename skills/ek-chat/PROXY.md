# Setting up the Ask assistant's proxy

The public page never holds your Anthropic key. It sends each question to a small program you run on
Cloudflare (a "Worker", the file `worker.js`). The Worker holds the key, answers only for your page's own
prompt, counts questions per day and per visitor, and passes the question to Anthropic.

## Before you start
- An **Anthropic account with billing** set up (console.anthropic.com).
- A **Cloudflare account** (free plan is enough; dash.cloudflare.com).
- The page built once with `ek-chat` installed: its build prints `system_sha256` and a ready-to-paste
  `SYSTEM_SHA256` line. Keep that output open.
- About **20 minutes**.

## Steps (Cloudflare dashboard, no Node needed)
1. **Create a separate API key for this project and set a monthly spending limit on it.** In the Anthropic
   console, make a workspace for this project, set its monthly spend limit (say what you can afford to lose
   in a bad month), and create an API key in that workspace. Copy the key once; you paste it in step 5.
2. **Create the Worker.** Cloudflare dashboard > Workers & Pages > Create > Create Worker. Name it
   `ek-chat-<project-slug>` and click Deploy (it deploys a placeholder).
3. **Paste the code.** Click Edit code, delete everything in the editor, paste the whole of
   `skills/ek-chat/worker.js`, click Deploy.
4. **Create the counter store.** Storage & Databases > KV > Create a namespace, name it `ek-chat-<slug>-cap`.
   Back on the Worker: Settings > Bindings > Add > KV namespace. Variable name **`EK_CAP`**, namespace the
   one you just made. Without this binding the Worker refuses every question (`proxy_has_no_cap`).
5. **Add the secrets.** Worker > Settings > Variables and Secrets > Add, type **Secret**:
   - `ANTHROPIC_API_KEY`: the key from step 1.
   - `IP_SALT`: any long random text (mash the keyboard for 40 characters). It lets the Worker count
     questions per visitor without ever storing an IP address.
   - `ADMIN_TOKEN` (only if the team will use the admin portal's assistant): another long random text,
     at least 16 characters. The team types it into the admin portal (Ask > Admin token).
6. **Add the variables.** Same page, type **Text**:
   - `ALLOWED_ORIGINS`: the address your page is published at, scheme and host only, e.g.
     `https://clcabana.github.io` (no path, no trailing slash). Several: separate with commas.
   - `SYSTEM_SHA256`: the `SYSTEM_SHA256` line the build printed (one to three long codes, comma-separated).
   - `DAILY_CAP`: questions per day for the whole page, e.g. `200`.
   - Optional: `IP_DAILY_CAP` (per visitor per day, default `20`), `ADMIN_DAILY_CAP` (default `50`),
     `MODEL` (default `claude-sonnet-5-5`), `MAX_TOKENS` (longest answer, default `2048`).
   Click Deploy so the settings take effect.
7. **Copy the address.** The Worker's page shows `https://ek-chat-<slug>.<account>.workers.dev`. Put that
   plus `/chat` in the manifest and rebuild:
   ```json
   "chat": { "mode": "proxy", "proxy_url": "https://ek-chat-<slug>.<account>.workers.dev/chat",
             "provider": "anthropic", "model": "claude-sonnet-5-5", "daily_cap": 200 }
   ```
8. **Test.** Open the published page, tap Ask, ask "When is the decision?". An answer means it works.
   "does not know this page's version" means `SYSTEM_SHA256` does not match: paste the build's line again.

**After every rebuild that changes the brief** (new facts, a corrected date), the prompt changes and so does
its code: paste the new `SYSTEM_SHA256` line into the Worker (step 6) and Deploy, or the assistant stops
answering. Rebuilding with an unchanged brief prints the same code.

## Alternative: wrangler (if you already use Node)
```
npm install -g wrangler && wrangler login
wrangler kv namespace create EK_CAP          # prints an id
```
`wrangler.toml` next to a copy of `worker.js`:
```toml
name = "ek-chat-<project-slug>"
main = "worker.js"
compatibility_date = "2026-10-01"
kv_namespaces = [{ binding = "EK_CAP", id = "<the id it printed>" }]
[vars]
ALLOWED_ORIGINS = "https://<you>.github.io"
SYSTEM_SHA256 = "<the line the build printed>"
DAILY_CAP = "200"
```
Then `wrangler secret put ANTHROPIC_API_KEY`, `wrangler secret put IP_SALT`, optionally
`wrangler secret put ADMIN_TOKEN` (each typed at the prompt, never written to a file), and `wrangler deploy`.

## What it may cost (check before you rely on it)
Each question sends roughly the project facts plus the question and the last few exchanges. For the sample
project the facts prompt is about 3,600 characters (the build prints `system_bytes`), so a question is at
most about 3,000 input tokens, and an answer at most `MAX_TOKENS` (2,048) output tokens, usually far fewer
(answers are asked to stay near 120 words, about 200 tokens).

*Assumed price, to check on Anthropic's pricing page for the model you set: USD 3 per million input tokens
and USD 15 per million output tokens.* On that assumption the worst case is about USD 0.04 per question, so at
the default cap of 200 questions a day about **USD 8 a day** (about USD 240 a month if every day hit the cap);
a typical question costs about USD 0.01. The admin path can send up to 200 KB (about 55,000 tokens) per call,
about USD 0.20 each, so its default 50 a day is at most about USD 10 a day. Scale with your own prompt size,
caps and the real price. The monthly spending limit from step 1 is the hard ceiling.

## What someone can do with the Worker's address
The address is in the page source, so assume anyone can find it.
- **They can** ask your project's assistant questions about your project, from a script as well as the page
  (a script can fake the page's origin). Each one costs you money, up to `IP_DAILY_CAP` per address per day
  and `DAILY_CAP` for everyone. One person with many addresses can use up the day's cap, after which real
  visitors see "the assistant has reached its limit" until midnight UTC.
- **They cannot** use it as a general AI service: the Worker answers only with your page's own prompt
  (checked by its code), with at most 12 short messages and 40 KB per request. They cannot read your key,
  change the model, see other visitors' questions (the Worker stores none), or use the admin path without
  `ADMIN_TOKEN`. Without `ADMIN_TOKEN` set, the admin path is closed.
- The day counters live in KV, which is not instantaneous: a burst of simultaneous requests can pass a cap by
  a few. The spending limit from step 1 is what truly bounds the bill.
- If you suspect misuse: lower `DAILY_CAP`, or rotate the key (new key in Anthropic, paste it as
  `ANTHROPIC_API_KEY`, delete the old one). If the admin token leaks, set a new `ADMIN_TOKEN`.

## Notes
- The Worker logs no questions, answers or IP addresses. `LOG_ERRORS = "on"` logs only the status and error
  type of failed calls. Anthropic and Cloudflare see every question in transit; Anthropic keeps API data as
  its terms say.
- `direct` mode (the key typed into the admin portal) needs no proxy, and is for the admin portal on the
  team's own computer only.
