// /t/<slug>: the normal page, opened on that theme, with theme-specific share tags and card.
// Production note: the Worker serving lyingterminals.com needs the same route before this ships there.
import THEMES from "../../lib/themes.json";

export async function onRequestGet({ request, params, env }) {
  const url = new URL(request.url);
  const slug = String(params.slug || "").toLowerCase();
  const t = Object.prototype.hasOwnProperty.call(THEMES, slug) ? THEMES[slug] : null;
  if (!t) return Response.redirect(url.origin + "/", 302);

  const page = await env.ASSETS.fetch(new URL("/", url));
  const an = /^[AF]/.test(t.grade) ? "an" : "a";
  const title = `${t.name} gets ${an} ${t.grade}. Is your terminal theme lying to you?`;
  const desc = `${t.name}: grade ${t.grade}, ${t.score}/100. ${t.top} Cross-examine it in a terminal drawn in its raw colours, or: curl lyingterminals.com`;
  const img = `${url.origin}/og/${slug}.png`;
  const alt = `Share card: a terminal in ${t.name} running judge, grade ${t.grade}, ${t.score}/100.`;
  const content = (v) => ({ element(e) { e.setAttribute("content", v); } });

  const headers = new Headers(page.headers);
  headers.set("content-type", "text/html; charset=utf-8");
  return new HTMLRewriter()
    .on("title", { element(e) { e.setInnerContent(title); } })
    .on('meta[property="og:title"]', content(title))
    .on('meta[name="twitter:title"]', content(title))
    .on('meta[property="og:description"]', content(desc))
    .on('meta[name="twitter:description"]', content(desc))
    .on('meta[name="description"]', content(desc))
    .on('meta[property="og:image"]', content(img))
    .on('meta[name="twitter:image"]', content(img))
    .on('meta[property="og:image:alt"]', content(alt))
    .on('meta[name="twitter:image:alt"]', content(alt))
    .on('meta[property="og:url"]', content(`${url.origin}/t/${slug}`))
    .on('link[rel="canonical"]', { element(e) { e.setAttribute("href", `https://lyingterminals.com/t/${slug}`); } })
    .transform(new Response(page.body, { status: 200, headers }));
}
