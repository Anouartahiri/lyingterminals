// lyingterminals.com: static site plus tiny privacy-friendly analytics.
// Stores only daily aggregate counters (visits, referrer host, country, theme).
// No IPs, no user agents, no cookies, no per-visitor identifiers.
const THEMES = new Set(["gruvbox-dark","catppuccin-mocha","catppuccin-latte","tokyo-night","nord","dracula","solarized-dark","one-dark","one-light","monokai","github-dark","github-light","rose-pine","rose-pine-dawn","kanagawa-wave","solarized-light","everforest-dark","custom"]);
const OWN_HOSTS = new Set(["lyingterminals.com","www.lyingterminals.com"]);
const BOT_RE = /bot|crawl|spider|slurp|preview|facebookexternalhit|embedly|quora link|whatsapp|telegram|discord|slack|headless|lighthouse|curl|wget|python|httpclient|go-http|java\/|axios|node-fetch|okhttp|monitor|uptime/i;
const DAILY_HIT_CAP = 50000; // theme beacons per day, a light abuse cap

const day = (d = new Date()) => d.toISOString().slice(0, 10);

function refHost(request) {
  const r = request.headers.get("referer");
  if (!r) return "direct";
  try {
    const h = new URL(r).hostname.toLowerCase().replace(/^www\./, "");
    if (OWN_HOSTS.has(h) || OWN_HOSTS.has("www." + h)) return null; // internal navigation
    return h.slice(0, 80) || "direct";
  } catch { return "unknown"; }
}

function isHuman(request) {
  const ua = request.headers.get("user-agent") || "";
  if (!ua || BOT_RE.test(ua)) return false;
  const purpose = request.headers.get("sec-purpose") || request.headers.get("purpose") || "";
  if (/prefetch|prerender/i.test(purpose)) return false;
  return true;
}

function safeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let x = 0; for (let i = 0; i < a.length; i++) x |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return x === 0;
}

const UPSERT = "INSERT INTO counts (day, kind, k, n) VALUES (?1, ?2, ?3, 1) ON CONFLICT(day, kind, k) DO UPDATE SET n = n + 1";
const bump = (env, d, pairs) => env.DB.batch(pairs.map(([kind, k]) => env.DB.prepare(UPSERT).bind(d, kind, k)));

async function recordView(env, d, ref, cc) {
  const pairs = [["visits", "all"], ["cc", cc || "??"]];
  if (ref) pairs.push(["ref", ref]);
  await bump(env, d, pairs);
}

async function recordTheme(env, d, t) {
  const row = await env.DB.prepare("SELECT n FROM counts WHERE day = ?1 AND kind = 'hits' AND k = 'all'").bind(d).first();
  if (row && row.n >= DAILY_HIT_CAP) return;
  await bump(env, d, [["hits", "all"], ["theme", t]]);
}

async function report(env, days = 30) {
  const since = day(new Date(Date.now() - (days - 1) * 864e5));
  const top = (kind, lim) => env.DB.prepare("SELECT k, SUM(n) AS n FROM counts WHERE kind = ?1 AND day >= ?2 GROUP BY k ORDER BY n DESC LIMIT ?3").bind(kind, since, lim);
  const [daily, referrers, countries, themes] = (await env.DB.batch([
    env.DB.prepare("SELECT day, n FROM counts WHERE kind = 'visits' AND day >= ?1 ORDER BY day").bind(since),
    top("ref", 20), top("cc", 30), top("theme", 30),
  ])).map((r) => r.results);
  const total = daily.reduce((s, r) => s + r.n, 0);
  return { since, days, total, daily, referrers, countries, themes };
}

function dashboard(r) {
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const max = Math.max(1, ...r.daily.map((x) => x.n));
  const bars = r.daily.map((x) => `<div class="b" title="${x.day}: ${x.n}"><i style="height:${Math.round((x.n / max) * 100)}%"></i><span>${x.day.slice(5)}</span><em>${x.n}</em></div>`).join("");
  const table = (title, rows, label) => `<section><h2>${title}</h2>${rows.length ? `<table>${rows.map((x) => `<tr><td>${esc(x.k)}</td><td>${x.n}</td></tr>`).join("")}</table>` : `<p class="m">No ${label} yet.</p>`}</section>`;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>lyingterminals stats</title>
<style>body{margin:0;background:#282828;color:#ebdbb2;font:14px/1.5 ui-monospace,Menlo,Consolas,monospace;padding:28px}h1{font:400 28px Georgia,serif;margin:0 0 4px}h2{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#a89984;margin:0 0 8px}.m{color:#a89984}
.chart{display:flex;align-items:flex-end;gap:4px;height:180px;margin:20px 0 30px;border-bottom:1px solid #504945}.b{flex:1;height:100%;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;position:relative;min-width:0}.b i{display:block;width:100%;background:#fabd2f;border-radius:3px 3px 0 0;min-height:2px}.b span{position:absolute;bottom:-20px;font-size:10px;color:#a89984}.b em{font-style:normal;font-size:10px;color:#ebdbb2;margin-bottom:2px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:24px;margin-top:40px}table{width:100%;border-collapse:collapse}td{padding:4px 0;border-bottom:1px solid #3c3836}td:last-child{text-align:right;color:#fabd2f}</style></head><body>
<h1>lyingterminals.com</h1><div class="m">${r.total} visits in the last ${r.days} days (since ${r.since}, UTC days). Aggregate counters only: no IPs, no user agents, no cookies.</div>
<div class="chart">${bars || '<p class="m">No visits yet.</p>'}</div>
<div class="grid">${table("Referrers", r.referrers, "referrers")}${table("Countries", r.countries, "countries")}${table("Themes picked", r.themes, "theme picks")}</div>
<p class="m" style="margin-top:30px">JSON: add <code>&amp;format=json</code></p></body></html>`;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (url.pathname === "/stats") {
      const key = url.searchParams.get("key") || "";
      if (!env.STATS_KEY || !safeEqual(key, env.STATS_KEY)) return new Response("Not found", { status: 404 });
      const days = Math.min(365, Math.max(1, parseInt(url.searchParams.get("days") || "30", 10) || 30));
      const r = await report(env, days);
      const h = { "cache-control": "no-store", "x-robots-tag": "noindex" };
      if (url.searchParams.get("format") === "json") return Response.json(r, { headers: h });
      return new Response(dashboard(r), { headers: { ...h, "content-type": "text/html; charset=utf-8" } });
    }

    if (url.pathname === "/hit") {
      if (request.method !== "POST") return new Response(null, { status: 405 });
      const origin = request.headers.get("origin") || request.headers.get("referer") || "";
      let okOrigin = false; try { okOrigin = OWN_HOSTS.has(new URL(origin).hostname); } catch {}
      const t = (url.searchParams.get("t") || "").slice(0, 40);
      if (okOrigin && THEMES.has(t) && isHuman(request)) ctx.waitUntil(recordTheme(env, day(), t).catch(() => {}));
      return new Response(null, { status: 204, headers: { "cache-control": "no-store" } });
    }

    if (request.method === "GET" && url.pathname === "/" && isHuman(request)) {
      const ref = refHost(request);
      const cc = (request.cf && request.cf.country) || "??";
      ctx.waitUntil(recordView(env, day(), ref, cc).catch(() => {}));
    }

    return env.ASSETS.fetch(request);
  },
};
