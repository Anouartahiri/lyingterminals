// Pages (theme-roast.pages.dev + previews) is staging only: keep it out of search engines.
// Production (lyingterminals.com) is served by the Worker and never runs this.
export async function onRequest({ request, next }) {
  const res = await next();
  const host = new URL(request.url).hostname;
  if (!host.endsWith(".pages.dev")) return res;
  const out = new Response(res.body, res);
  out.headers.set("X-Robots-Tag", "noindex, nofollow");
  if ((out.headers.get("content-type") || "").includes("text/html")) {
    return new HTMLRewriter().on("head", { element(e) { e.prepend('<meta name="robots" content="noindex, nofollow">', { html: true }); } }).transform(out);
  }
  return out;
}
