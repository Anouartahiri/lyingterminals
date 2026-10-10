"""End-to-end checks for lyingterminals.com. Usage: python tests/test_site.py [URL]
URL defaults to http://localhost:8000/index.html. Env: CHROME_PATH (optional), AXE_PATH (axe.min.js), SHOTS (screenshot dir)."""
import asyncio, json, os, sys
from playwright.async_api import async_playwright
URL = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BASE_URL", "http://localhost:8000/index.html")
AXE = os.environ.get("AXE_PATH", "node_modules/axe-core/axe.min.js")
SHOTS = os.environ.get("SHOTS", "")
FAILS = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  {info}" if info else "")); ok or FAILS.append(name)
CONTRAST = r"""(sel)=>{const P=c=>c.match(/[\d.]+/g).slice(0,3).map(Number);const lin=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};
 const L=c=>{const[r,g,b]=P(c);return .2126*lin(r)+.7152*lin(g)+.0722*lin(b)};const CR=(a,b)=>{const x=L(a),y=L(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
 const bg=getComputedStyle(document.getElementById('tm')).backgroundColor; let m=99;
 let w=''; document.querySelectorAll(sel).forEach(e=>{ if(!e.textContent.trim())return; const v=CR(getComputedStyle(e).color,bg); if(v<m){m=v;w=e.textContent.slice(0,40)+' '+getComputedStyle(e).color+' on '+bg;} }); return [+m.toFixed(2),w];}"""
async def typ(pg, c): await pg.fill("#tmInput", c); await pg.press("#tmInput", "Enter"); await pg.wait_for_timeout(60)
async def shot(pg, name, loc=None):
    if SHOTS: os.makedirs(SHOTS, exist_ok=True); await (loc or pg).screenshot(path=os.path.join(SHOTS, name))
async def swipe(pg, cdp, dy, term_pos):
    await pg.evaluate("(()=>{const r=document.getElementById('tmBody').getBoundingClientRect();scrollTo({top:scrollY+r.top-(innerHeight-r.height)/2,behavior:'instant'})})()")
    await pg.evaluate(f"(()=>{{const b=document.getElementById('tmBody');const m=b.scrollHeight-b.clientHeight;b.scrollTop={term_pos}}})()"); await pg.wait_for_timeout(120)
    st = "({p:Math.round(scrollY),t:Math.round(document.getElementById('tmBody').scrollTop)})"
    a = await pg.evaluate(st)
    x, y = await pg.evaluate("(()=>{const r=document.getElementById('tmBody').getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]})()")
    y -= dy / 2
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    for i in range(1, 13): await cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y + dy * i / 12}]}); await pg.wait_for_timeout(16)
    await cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}); await pg.wait_for_timeout(500)
    z = await pg.evaluate(st); return z["t"] - a["t"], z["p"] - a["p"]

async def run(b, vw):
    mob = vw < 1000; errs = []
    c = await b.new_context(viewport={"width": vw, "height": 844 if mob else 900}, device_scale_factor=2 if mob else 1, is_mobile=mob, has_touch=mob, accept_downloads=True)
    pg = await c.new_page(); pg.set_default_timeout(120000)
    pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("console", lambda m: errs.append(m.text) if m.type in ("error", "warning") else None)
    T = f"[{vw}] "
    # C: random D/F on first load
    await pg.goto(URL, timeout=120000); await pg.wait_for_timeout(800)
    g = await pg.evaluate("[currentKey, current.grade, location.hash]")
    check(T + "first load opens a D/F preset without touching the URL", g[1] in ("D", "F") and g[2] == "", str(g))
    await pg.goto("about:blank"); await pg.goto(URL + "#gruvbox-dark", timeout=120000); await pg.add_style_tag(content="html{scroll-behavior:auto!important}"); await pg.wait_for_timeout(800)
    check(T + "#hash still selects the theme", await pg.evaluate("currentKey") == "gruvbox-dark")
    # A1: hero hint
    hint = await pg.evaluate("""(()=>{const b=document.getElementById('heroHint'), v=[...b.querySelectorAll('.key,.touch')].find(e=>getComputedStyle(e).display!=='none'); return [v.textContent.trim(), b.getBoundingClientRect().height]})()""")
    check(T + "hero hint text", hint[0] == ("tap to cross-examine ↓" if mob else "press ` to cross-examine your theme ↓"), hint[0])
    await pg.evaluate("scrollTo(0,0)"); await shot(pg, f"hero-hint-{vw}.png")
    await pg.click("#heroHint"); await pg.wait_for_timeout(300)
    d = await pg.evaluate("[TERM.isOpen, document.getElementById('tmDrop').getAttribute('aria-modal'), document.getElementById('tmDrop').hidden, document.getElementById('tmDrop').contains(document.activeElement)]")
    check(T + "hint opens modal drop-down with focus inside", d == [True, "true", False, True], str(d))
    # A3: focus trap (Shift+Tab out of the prompt cycles inside the dialog)
    inside = True
    for _ in range(6):
        await pg.keyboard.press("Shift+Tab"); inside &= await pg.evaluate("document.getElementById('tmDrop').contains(document.activeElement)")
    check(T + "focus trapped in dialog", inside)
    await pg.focus("#tmInput"); await pg.keyboard.press("Escape"); await pg.wait_for_timeout(200)
    check(T + "Esc closes and returns focus to the hint", await pg.evaluate("!TERM.isOpen && document.activeElement.id==='heroHint'"))
    # A2: fix
    await pg.evaluate("document.activeElement.blur()"); await pg.keyboard.press("`"); await pg.wait_for_timeout(200)
    await typ(pg, "theme solarized-light"); await pg.wait_for_timeout(500); await typ(pg, "clear"); await typ(pg, "fix")
    fx = await pg.evaluate("""(()=>{const t=[...document.querySelectorAll('#tmOut .blk')].pop().innerText; return {txt:t, fixed:TERM.fixed, live:document.getElementById('tmLive').textContent}})()""")
    check(T + "fix prints old → new rows and the new grade", "→" in fx["txt"] and "grade F → C, 7 → 72" in fx["txt"].replace("\n", " "), fx["txt"][-160:].replace("\n", " | "))
    await shot(pg, f"fix-{vw}.png", pg.locator("#tm"))
    pal = await pg.evaluate("""(()=>{const s=getComputedStyle(document.getElementById('tm')),bg=s.getPropertyValue('--tbg').trim();const v=[...Array(16).keys()].map(i=>s.getPropertyValue('--t'+i).trim());
      return {bg, under:v.filter((h,i)=>contrast(h,bg)<4.6&&i!==15&&i!==7).length, page:getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()}})()""")
    check(T + "fixed palette in terminal, no colour under 4.6", pal["under"] == 0, json.dumps(pal))
    await typ(pg, "judge"); j = await pg.evaluate("[...document.querySelectorAll('#tmOut .blk')].pop().innerText")
    check(T + "judge labels fixed palette", "(fixed)" in j)
    async with pg.expect_download() as dl: await typ(pg, "export kitty")
    path = await (await dl.value).path(); body = open(path).read()
    check(T + "export uses fixed palette", "(fixed)" in body and "Grade C" in body)
    await typ(pg, "fix --undo"); check(T + "fix --undo reverts", not await pg.evaluate("TERM.fixed"))
    await pg.fill("#tmInput", "fix --u"); await pg.press("#tmInput", "Tab"); check(T + "Tab completes fix --undo", await pg.input_value("#tmInput") == "fix --undo"); await pg.fill("#tmInput", "")
    # demo commands + lie mode, UI contrast, accessible pills
    for cmd in ["help", "git diff", "lie", "npm test", "ls", "git log", "cat error.log", "judge", "theme nord", "lie"]: await typ(pg, cmd)
    await typ(pg, "lie"); await typ(pg, "git diff"); await pg.wait_for_timeout(900)  # let colour transitions settle
    ui = await pg.evaluate(CONTRAST, "#tm .ui, #tmPrompt span"); check(T + "terminal UI text >= 4.6:1", ui[0] >= 4.6, str(ui))
    sr = await pg.evaluate("(document.querySelector('#tmOut .lab .sr-only')||{}).textContent||''")
    check(T + "pills have screen-reader text", "contrast" in sr and "to 1" in sr, sr.strip())
    live = await pg.evaluate("document.getElementById('tmLive').textContent")
    check(T + "live region announces a short summary", 0 < len(live) < 240, live)
    await pg.keyboard.press("ArrowUp"); await pg.keyboard.press("Escape"); await pg.wait_for_timeout(200)
    check(T + "Esc closes on first press after history", not await pg.evaluate("TERM.isOpen"))
    # axe
    if os.path.exists(AXE):
        await pg.add_script_tag(path=AXE)
        res = await pg.evaluate("axe.run({exclude:[['#tmOut .demo'],['.sw .aa']]},{resultTypes:['violations']}).then(r=>r.violations.filter(v=>['serious','critical'].includes(v.impact)).map(v=>v.id+':'+v.nodes.map(n=>n.target.join(' ')+' '+((n.any[0]||{}).message||'').slice(38,80)).join(' ; ')))")
        check(T + "axe: no serious/critical violations", not res, str(res))
        await pg.keyboard.press("`"); await pg.wait_for_timeout(200)
        res = await pg.evaluate("axe.run({exclude:[['#tmOut .demo'],['.sw .aa']]},{resultTypes:['violations']}).then(r=>r.violations.filter(v=>['serious','critical'].includes(v.impact)).map(v=>v.id+':'+v.nodes.map(n=>n.target.join(' ')+' '+((n.any[0]||{}).message||'').slice(38,80)).join(' ; ')))")
        check(T + "axe (drop-down open): no serious/critical", not res, str(res)); await pg.keyboard.press("Escape")
    else: print("SKIP axe (no axe.min.js)")
    # scroll behaviour
    if mob:
        await pg.evaluate("document.activeElement.blur()")
        for cmd in ["help", "git diff", "npm test", "cat error.log"]: await typ(pg, cmd)
        await pg.evaluate("document.activeElement.blur()")
        cdp = await c.new_cdp_session(pg)
        a = await swipe(pg, cdp, -150, "m/2"); check(T + "swipe mid scrolls terminal only", a[0] > 100 and a[1] == 0, str(a))
        a = await swipe(pg, cdp, -300, "m-100"); check(T + "swipe crossing bottom chains to page", a[0] == 100 and a[1] > 150, str(a))
        a = await swipe(pg, cdp, 300, "100"); check(T + "swipe crossing top chains to page", a[0] == -100 and a[1] < -150, str(a))
        check(T + "no horizontal page scroll", await pg.evaluate("document.documentElement.scrollWidth-innerWidth") <= 0)
        h = await pg.evaluate("Math.min(...[...document.querySelectorAll('#tmSugg button')].map(b=>b.getBoundingClientRect().height))")
        check(T + "chips >= 44px", h >= 44, str(h))
    else:
        for cmd in ["help", "git diff", "npm test"]: await typ(pg, cmd)
        await pg.evaluate("document.activeElement.blur()")
        await pg.evaluate("(()=>{const r=document.getElementById('tmBody').getBoundingClientRect();scrollTo({top:scrollY+r.top-200,behavior:'instant'})})()"); await pg.wait_for_timeout(200)
        await pg.mouse.move(600, 420); y0 = await pg.evaluate("scrollY"); await pg.mouse.wheel(0, 100); await pg.wait_for_timeout(800)
        check(T + "first wheel tick at terminal bottom scrolls page", await pg.evaluate("scrollY") - y0 >= 90)
    check(T + "no console errors", not errs, str(errs))
    await c.close()

async def main():
    async with async_playwright() as p:
        kw = {"executable_path": os.environ["CHROME_PATH"]} if os.environ.get("CHROME_PATH") else {}
        b = await p.chromium.launch(args=["--no-sandbox"], **kw)
        for vw in (1366, 390): await run(b, vw)
        await b.close()
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed"); sys.exit(1 if FAILS else 0)
asyncio.run(main())
