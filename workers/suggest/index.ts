/**
 * workers/suggest/index.ts
 *
 * Coptic Reference — anonymous suggestion bridge.
 *
 * This is the ONLY runtime component in the entire project. It handles
 * contributions and nothing else. If you delete it, revoke it, or break it,
 * READING IS COMPLETELY UNAFFECTED — every reader-facing feature falls back to
 * a mailto: link with a prefilled subject and body.
 *
 * Endpoints:
 *   POST /api/suggest   -> create a GitHub Issue on behalf of a submitter
 *                          with no GitHub account
 *   POST /api/endorse   -> add a 👍 reaction to an existing suggestion issue
 *   GET  /api/health    -> liveness + config check (no secrets leaked)
 *
 * Why there is no database
 * ------------------------
 * Dedup ("same IP within 24h per entry") is done by SEARCHING GITHUB, not by
 * storing anything. We look for an open issue on the same target carrying the
 * same submitter_hash in its body; if we find one we comment on it instead of
 * creating a duplicate. That keeps the project on architecture (B) instead of
 * dragging it into (C), and it reuses the audit trail we already have.
 *
 * HONEST LIMITATION — READ THIS BEFORE TRUSTING IT
 * ------------------------------------------------
 * Rate limiting is an in-memory Map. It dies with the isolate, it is not shared
 * across PoPs, and it is reset on deploy. It is a courtesy that stops an
 * accidental script loop. IT IS NOT A SECURITY BOUNDARY and must never be
 * described as one. The real defences are: the honeypot field, optional
 * Cloudflare Turnstile, GitHub's own abuse handling, and the fact that a
 * spammer gets exactly one issue per (IP, day, entry) either way.
 *
 * Deploy
 * ------
 *   cd workers/suggest
 *   npx wrangler secret put GITHUB_TOKEN     # needs issues:write
 *   npx wrangler deploy
 *
 * The token is a Worker secret. This file is public. Never commit a token.
 */

export interface Env {
  GITHUB_TOKEN: string;   // secret — issues:write, contents:read
  REPO: string;           // var    — "owner/repo"
  SITE_ORIGIN: string;    // var    — "https://coptic.re"
  TURNSTILE_SECRET?: string; // var — set to enable Turnstile
  RATE_LIMIT_PER_HOUR?: string; // var — default "5"
  RATE_LIMIT_PER_DAY?: string;  // var — default "20"
}

interface SuggestPayload {
  /** Nested per v5 §13.2. Flat target_* fields were the earlier draft. */
  target: {
    kind: "entry" | "work" | "lesson" | "site";
    id: string | null;
    url_path: string;
    dialect?: "B" | "S" | "N" | null;
  };
  kind: string;
  body: string;
  evidence?: string;
  contact?: string;
  current_value?: string;
  honeypot?: string;
  turnstile_token?: string;
}

const KINDS = new Set([
  "gloss", "example", "etymology", "typo", "parse",
  "translation", "licence", "bug", "feature",
]);
const TARGET_KINDS = new Set(["entry", "work", "lesson", "site"]);

// --- tiny helpers ------------------------------------------------------------
const enc = new TextEncoder();

function json(body: unknown, status = 200, headers: HeadersInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...headers,
    },
  });
}

const sha256hex = async (s: string): Promise<string> =>
  [...new Uint8Array(await crypto.subtle.digest("SHA-256", enc.encode(s)))]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

function baseHeaders(req: Request, env: Env): HeadersInit {
  const origin = req.headers.get("origin");
  return {
    // Only our own site may call this. Not a security control — the Worker is
    // public — but it stops drive-by use from other people's pages.
    ...(origin && origin === env.SITE_ORIGIN ? { "access-control-allow-origin": origin } : {}),
    "access-control-allow-methods": "POST, OPTIONS",
    "access-control-allow-headers": "content-type",
    "x-content-type-options": "nosniff",
  };
}

/**
 * submitter_hash = sha256(ip + UTC day + target) truncated to 16 hex chars.
 *
 * The IP is never stored, logged, or returned. The hash exists so this Worker
 * and the weekly bake can recognise a duplicate without us holding an IP
 * anywhere. It is written into an HTML comment in the issue body — invisible
 * in rendered Markdown but findable by the GitHub search API.
 */
async function submitterHash(ip: string, target: string): Promise<string> {
  const day = new Date().toISOString().slice(0, 10); // UTC day boundary
  const full = await sha256hex(`${ip}|${day}|${target}`);
  return full.slice(0, 16);
}

interface RateVerdict { ok: boolean; retryAfter?: number }

function rateLimited(ip: string, env: Env): RateVerdict {
  const perHour = Number(env.RATE_LIMIT_PER_HOUR ?? "5");
  const perDay = Number(env.RATE_LIMIT_PER_DAY ?? "20");
  const now = Date.now();
  const hourAgo = now - 3_600_000;
  const dayAgo = now - 86_400_000;

  const hits = ((globalThis as any).__rl ??= new Map<string, number[]>())
    .get(ip) ?? [];
  const recent = hits.filter((t: number) => t > dayAgo);

  if (recent.filter((t: number) => t > hourAgo).length >= perHour) {
    const oldest = recent.filter((t: number) => t > hourAgo)[0];
    return { ok: false, retryAfter: Math.ceil((hourAgo + 3_600_000 - oldest) / 1000) };
  }
  if (recent.length >= perDay) return { ok: false, retryAfter: 86_400 };

  recent.push(now);
  ((globalThis as any).__rl).set(ip, recent);
  return { ok: true };
}

async function verifyTurnstile(token: string | undefined, ip: string, env: Env): Promise<boolean> {
  if (!env.TURNSTILE_SECRET) return true;          // not enabled — see README
  if (!token) return false;
  const res = await fetch(
    "https://challenges.cloudflare.com/turnstile/v0/siteverify",
    {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ secret: env.TURNSTILE_SECRET, response: token, remoteip: ip }),
    },
  );
  return ((await res.json()) as { success?: boolean }).success === true;
}

async function gh(env: Env, path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(`https://api.github.com${path}`, {
    ...init,
    headers: {
      authorization: `Bearer ${env.GITHUB_TOKEN}`,
      accept: "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "coptic-reference-suggest-bridge",
      ...(init.headers ?? {}),
    },
  });
}

// --- the suggestion endpoint -------------------------------------------------
async function handleSuggest(req: Request, env: Env): Promise<Response> {
  let p: SuggestPayload;
  try {
    p = (await req.json()) as SuggestPayload;
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400, baseHeaders(req, env));
  }

  // Honeypot: a real person never fills this in. Return 200 so a bot does not
  // learn it was filtered.
  if (p.honeypot) return json({ ok: true, id: null, deduplicated: false }, 200, baseHeaders(req, env));

  const ip = req.headers.get("cf-connecting-ip") ?? "0.0.0.0";
  if (!["gloss", "example", "etymology", "typo", "parse", "translation",
        "licence", "bug", "feature"].includes(p.kind)) {
    return json({ ok: false, error: "bad_kind" }, 400, baseHeaders(req, env));
  }
  const t = p.target;
  if (!t || !TARGET_KINDS.has(t.kind)) {
    return json({ ok: false, error: "bad_target_kind" }, 400, baseHeaders(req, env));
  }
  if (!t.url_path || !t.url_path.startsWith("/")) {
    return json({ ok: false, error: "bad_url_path" }, 400, baseHeaders(req, env));
  }
  if (!p.body || p.body.trim().length < 10) {
    return json({ ok: false, error: "body_too_short" }, 400, baseHeaders(req, env));
  }

  const rl = rateLimited(ip, env);
  if (!rl.ok) {
    return json({ ok: false, error: "rate_limited", retry_after: rl.retryAfter },
                429, { ...baseHeaders(req, env), "retry-after": String(rl.retryAfter) });
  }
  if (!(await verifyTurnstile(p.turnstile_token, ip, env))) {
    return json({ ok: false, error: "verification_failed" }, 403, baseHeaders(req, env));
  }

  const target = `${t.kind}:${t.id ?? t.url_path}`;
  const hash = await submitterHash(ip, target);

  // --- stateless dedup: ask GitHub whether this submitter already has one ---
  const label = t.id && t.kind === "entry" ? `entry/${t.id.toLowerCase()}` : null;
  const search = label
    ? `/search/issues?q=${encodeURIComponent(`repo:${env.REPO} is:issue is:open label:"${label}" in:body ${hash}`)}`
    : null;
  if (search) {
    const sr = await gh(env, search);
    if (sr.ok) {
      const found = ((await sr.json()) as { items?: { number: number; html_url: string }[] }).items;
      if (found?.length) {
        await gh(env, `/repos/${env.REPO}/issues/${found[0].number}/comments`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            body: `**Further submission from the same submitter on the same day**\n\n` +
                  `**Kind:** ${p.kind}\n\n${p.body.trim()}` +
                  (p.evidence ? `\n\n**Evidence**\n\n${p.evidence.trim()}` : "") +
                  `\n\n<!-- dedup:${hash} -->`,
          }),
        });
        return json({ ok: true, deduplicated: true, github_issue_number: found[0].number,
                      url: found[0].html_url }, 200, baseHeaders(req, env));
      }
    }
  }

  // --- create the issue ------------------------------------------------------
  const when = new Date().toISOString().slice(0, 19) + "Z";
  const body = [
    `**Kind:** \`kind/${p.kind}\``,
    ``,
    `**Target:** ${p.target_kind} \`${p.target_id ?? "(site)"}\``,
    `**Page:** ${env.SITE_ORIGIN}${p.url_path}`,
    t.dialect ? `**Dialect:** ${t.dialect === "B" ? "Bohairic" : t.dialect === "S" ? "Sahidic" : "undetermined"}` : null,
    ``,
    `## Suggested change`,
    ``,
    p.body.trim(),
    p.current_value ? `\n## Current value on the site\n\n\`\`\`\n${p.current_value.slice(0, 2000)}\n\`\`\`` : null,
    p.evidence ? `\n## Evidence\n\n${p.evidence.trim()}` : null,
    ``,
    `---`,
    `Submitted via the site on ${when} with no GitHub account.`,
    p.contact ? `\nCredit offered as: **${p.contact.trim()}**` : `\nNo contact details given.`,
    ``,
    `<!-- dedup:${hash} target:${target} -->`,
  ].filter((l) => l !== null).join("\n");

  const labels = ["suggestion", `kind/${p.kind}`, "status/new",
                  ...(label ? [label] : []),
                  ...(t.kind === "work" && t.id ? [`work/${t.id.split(":").pop()}`] : []),
                  ...(t.kind === "lesson" && t.id ? [`lesson/${t.id}`] : []),
                  ...(t.kind === "site" ? ["site"] : [])];

  const res = await gh(env, `/repos/${env.REPO}/issues`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ title: `[${p.kind}] ${t.id ?? t.url_path}`, labels, body }),
  });

  if (res.status === 403 || res.status === 429) {
    return json({ ok: false, error: "github_rejected", hint: "use the mailto link" },
                503, baseHeaders(req, env));
  }
  if (!res.ok) {
    return json({ ok: false, error: "github_error", status: res.status }, 502, baseHeaders(req, env));
  }
  const issue = (await res.json()) as { number: number; html_url: string };
  return json({ ok: true, deduplicated: false, github_issue_number: issue.number,
                url: issue.html_url }, 201, baseHeaders(req, env));
}

// --- the endorsement endpoint ------------------------------------------------
async function handleEndorse(req: Request, env: Env): Promise<Response> {
  let body: { issue_number?: number; reaction?: string };
  try {
    body = await req.json();
  } catch {
    return json({ ok: false, error: "invalid_json" }, 400, baseHeaders(req, env));
  }
  const issue = Number(body.issue_number);
  const allowed = new Set(["+1", "heart", "rocket"]);
  const reaction = String(body.reaction ?? "+1");
  if (!Number.isInteger(issue) || issue < 1) {
    return json({ ok: false, error: "bad_issue" }, 400, baseHeaders(req, env));
  }
  if (!allowed.has(reaction)) {
    return json({ ok: false, error: "bad_reaction" }, 400, baseHeaders(req, env));
  }
  const ip = req.headers.get("cf-connecting-ip") ?? "0.0.0.0";
  const rl = rateLimited(`endorse:${ip}`, env);
  if (!rl.ok) {
    return json({ ok: false, error: "rate_limited", retry_after: rl.retryAfter },
                429, { ...baseHeaders(req, env), "retry-after": String(rl.retryAfter) });
  }
  const res = await gh(env, `/repos/${env.REPO}/issues/${issue}/reactions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ content: reaction }),
  });
  if (res.status === 201) return json({ ok: true }, 201, baseHeaders(req, env));
  if (res.status === 422) return json({ ok: false, error: "already_reacted" }, 200, baseHeaders(req, env));
  return json({ ok: false, error: "github_error", status: res.status }, 502, baseHeaders(req, env));
}

// --- router ------------------------------------------------------------------
export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url);
    if (req.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: baseHeaders(req, env) });
    }
    if (url.pathname === "/api/health") {
      const configured = Boolean(env.GITHUB_TOKEN && env.REPO);
      return json({ ok: configured, repo: env.REPO ?? null,
                    turnstile: Boolean(env.TURNSTILE_SECRET),
                    time: new Date().toISOString() });
    }
    if (req.method !== "POST") {
      return json({ ok: false, error: "method_not_allowed" }, 405, baseHeaders(req, env));
    }
    try {
      if (url.pathname === "/api/suggest") return await handleSuggest(req, env);
      if (url.pathname === "/api/endorse") return await handleEndorse(req, env);
      return json({ ok: false, error: "not_found" }, 404, baseHeaders(req, env));
    } catch (e) {
      // Never leak the token or upstream body to the browser.
      // Never log a raw IP or a token. Message only.
      console.error("suggest worker error:", e instanceof Error ? e.message : "unknown");
      return json({ ok: false, error: "internal", hint: "use the mailto link" },
                  500, baseHeaders(req, env));
    }
  },
} satisfies ExportedHandler<Env>;
