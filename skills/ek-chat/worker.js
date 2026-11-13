// ek-chat proxy: a Cloudflare Worker template the creator deploys (see PROXY.md).
//
// The page POSTs {system, messages, stream, max_tokens, effort} here; this Worker adds the key (secret
// ANTHROPIC_API_KEY), picks the model (env MODEL), clamps the size, counts the day's answers and forwards to the
// Anthropic Messages API. With stream:true the Anthropic event stream is passed through untouched; otherwise it
// answers {text, stop_reason}.
//
// Two paths:
//   visitor  the request's `system` must hash (SHA-256, hex) to one of SYSTEM_SHA256: the page's own prompt
//            (build.py prints it as system_sha256) and, when voice reactions are installed, their two prompts.
//            Any other system prompt, or none, is refused: the Worker is not a general-purpose relay.
//   admin    the request carries header X-EK-Admin equal to the secret ADMIN_TOKEN (typed by the team into the
//            admin portal). Any system prompt (the admin analysis prompt changes with the data). Closed when
//            ADMIN_TOKEN is not set.
//
// Settings (dashboard: Settings > Variables and Secrets; or wrangler.toml [vars] / `wrangler secret put`):
//   ANTHROPIC_API_KEY  secret, required
//   IP_SALT            secret, required: any long random text; the visitor's IP is stored only as SHA-256(salt + IP)
//   ADMIN_TOKEN        secret, optional: opens the admin path
//   ALLOWED_ORIGINS    comma list of exact origins, e.g. "https://clcabana.github.io" (required; others get 403)
//   SYSTEM_SHA256      comma list of allowed system-prompt hashes (required for the visitor path)
//   MODEL              default "claude-sonnet-5-5"
//   DAILY_CAP          answers per UTC day on the visitor path, whole Worker, default 200
//   IP_DAILY_CAP       answers per UTC day per visitor IP, default 20
//   ADMIN_DAILY_CAP    answers per UTC day on the admin path, default 50
//   MAX_TOKENS         ceiling for one answer, default 2048
//   FALLBACKS          "default" (server-side refusal fallback, on by default) or "off"
//   PATH               default "/chat"
//   LOG_ERRORS         "on" logs the status and error type of failed upstream calls (never content); off by default
// Binding (required): EK_CAP, a KV namespace for the day counters. Without it the Worker refuses to answer.
// KV is not atomic: a burst of simultaneous requests can pass the cap by a few. The Anthropic spending limit on
// the key is the hard bound.
//
// Nothing here logs what visitors ask, what the model answers, or a visitor's IP.

const UPSTREAM = "https://api.anthropic.com/v1/messages";
const LIMITS = {
  visitor: { body: 40_000, system: 30_000, messages: 12, content: 8_000 },
  admin: { body: 200_000, system: 180_000, messages: 24, content: 8_000 },
};

const int = (v, dflt) => { const n = parseInt(v, 10); return Number.isFinite(n) && n > 0 ? n : dflt; };
const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");
const sha256 = async text => hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text)));
async function sameSecret(a, b) {  // compares digests, so the time taken does not depend on where the strings differ
  const [x, y] = await Promise.all([sha256(a), sha256(b)]);
  let d = 0; for (let i = 0; i < x.length; i++) d |= x.charCodeAt(i) ^ y.charCodeAt(i);
  return d === 0;
}

export default {
  async fetch(request, env, ctx) {
    const origin = request.headers.get("Origin") || "";
    const allowed = String(env.ALLOWED_ORIGINS || "").split(",").map(s => s.trim()).filter(Boolean);
    const okOrigin = allowed.includes(origin);
    const cors = okOrigin
      ? { "Access-Control-Allow-Origin": origin, "Vary": "Origin", "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "content-type, x-ek-admin", "Access-Control-Max-Age": "86400" }
      : { "Vary": "Origin" };
    const json = (status, obj) => new Response(JSON.stringify(obj), { status, headers: { ...cors, "content-type": "application/json", "cache-control": "no-store" } });

    if (request.method === "OPTIONS") return new Response(null, { status: okOrigin ? 204 : 403, headers: cors });
    if (!okOrigin) return json(403, { error: "origin_not_allowed" });  // stops other web pages, not scripts: see the hash and caps below
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== (env.PATH || "/chat")) return json(404, { error: "not_found" });
    if (!env.ANTHROPIC_API_KEY) return json(500, { error: "proxy_has_no_key" });
    if (!env.EK_CAP) return json(500, { error: "proxy_has_no_cap" });
    if (!env.IP_SALT) return json(500, { error: "proxy_has_no_salt" });

    // which path: a request that names itself admin must carry the right token; there is no fallback to visitor
    const adminHeader = request.headers.get("X-EK-Admin");
    const admin = adminHeader !== null;
    if (admin) {
      if (!env.ADMIN_TOKEN) return json(403, { error: "admin_closed" });
      if (!(await sameSecret(adminHeader, String(env.ADMIN_TOKEN)))) return json(403, { error: "admin_token_refused" });
    }
    const L = admin ? LIMITS.admin : LIMITS.visitor;

    const declared = parseInt(request.headers.get("Content-Length") || "0", 10);
    if (declared > L.body) return json(413, { error: "too_large" });
    const raw = await request.text();
    if (new TextEncoder().encode(raw).length > L.body) return json(413, { error: "too_large" });
    let body;
    try { body = JSON.parse(raw); } catch { return json(400, { error: "not_json" }); }
    if (!body || typeof body !== "object") return json(400, { error: "not_json" });

    const system = typeof body.system === "string" ? body.system : "";
    if (system.length > L.system) return json(413, { error: "system_too_large" });
    if (!admin) {
      const list = String(env.SYSTEM_SHA256 || "").split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
      if (!list.length) return json(500, { error: "proxy_has_no_system_list" });
      if (!system || !list.includes(await sha256(system))) return json(400, { error: "system_not_allowed" });
    }
    const messages = Array.isArray(body.messages) ? body.messages : [];
    if (!messages.length || messages.length > L.messages
        || !messages.every(m => m && (m.role === "user" || m.role === "assistant") && typeof m.content === "string" && m.content && m.content.length <= L.content)
        || messages[messages.length - 1].role !== "user") return json(400, { error: "bad_messages" });

    // the day's counters: checked now, spent only after the upstream call succeeds
    const day = new Date().toISOString().slice(0, 10);
    const kv = env.EK_CAP, ttl = { expirationTtl: 172800 };
    const keys = admin
      ? [["admin:" + day, int(env.ADMIN_DAILY_CAP, 50)]]
      : [["day:" + day, int(env.DAILY_CAP, 200)],
         ["ip:" + day + ":" + (await sha256(env.IP_SALT + "|" + (request.headers.get("CF-Connecting-IP") || "unknown"))), int(env.IP_DAILY_CAP, 20)]];
    const counts = await Promise.all(keys.map(([k]) => kv.get(k).then(v => parseInt(v || "0", 10) || 0)));
    for (let i = 0; i < keys.length; i++) {
      if (counts[i] >= keys[i][1]) return json(429, { error: i === 0 ? (admin ? "admin_daily_cap" : "daily_cap") : "ip_daily_cap" });
    }
    const spend = () => ctx.waitUntil(Promise.all(keys.map(([k], i) => kv.put(k, String(counts[i] + 1), ttl))));

    const maxTokens = Math.max(64, Math.min(int(env.MAX_TOKENS, 2048), parseInt(body.max_tokens, 10) || 1024));
    const effort = ["low", "medium", "high"].includes(body.effort) ? body.effort : "low";
    const stream = body.stream === true;
    const upBody = { model: env.MODEL || "claude-sonnet-5-5", max_tokens: maxTokens, messages, stream, output_config: { effort } };
    if (system) upBody.system = system;
    const headers = { "content-type": "application/json", "x-api-key": env.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01" };
    if ((env.FALLBACKS || "default") !== "off") { upBody.fallbacks = "default"; headers["anthropic-beta"] = "server-side-fallback-2026-07-01"; }

    let up;
    try { up = await fetch(UPSTREAM, { method: "POST", headers, body: JSON.stringify(upBody) }); }
    catch { return json(502, { error: "upstream_unreachable" }); }  // nothing spent
    if (!up.ok) {  // nothing spent
      let type = "upstream_error";
      try { const e = await up.json(); type = (e && e.error && typeof e.error.type === "string" && e.error.type.slice(0, 60)) || type; } catch {}
      if (env.LOG_ERRORS === "on") console.log("ek-chat upstream", up.status, type);
      const s = up.status === 401 || up.status === 403 ? 401 : up.status === 429 ? 429 : up.status >= 500 ? 502 : 400;
      return json(s, { error: type });
    }
    spend();
    if (stream) return new Response(up.body, { status: 200, headers: { ...cors, "content-type": "text/event-stream", "cache-control": "no-store" } });
    let m;
    try { m = await up.json(); } catch { return json(502, { error: "upstream_bad_json" }); }
    const text = (m.content || []).filter(b => b && b.type === "text" && typeof b.text === "string").map(b => b.text).join("");
    return json(200, { text, stop_reason: m.stop_reason || "" });
  },
};
