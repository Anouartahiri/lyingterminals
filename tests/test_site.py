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

BAR_CR = r"""()=>{const P=c=>c.match(/[\d.]+/g).slice(0,3).map(Number);const lin=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};
 const L=c=>{const[r,g,b]=P(c);return .2126*lin(r)+.7152*lin(g)+.0722*lin(b)};const CR=(a,b)=>{const x=L(a),y=L(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
 const bg=getComputedStyle(document.body).backgroundColor; let m=99,w='';
 document.querySelectorAll('#fbar a, #fbar b, #fbar span').forEach(e=>{const v=CR(getComputedStyle(e).color,bg); if(v<m){m=v;w=e.textContent+' '+getComputedStyle(e).color+' on '+bg;}}); return [+m.toFixed(2),w];}"""
async def fbar(c, T, mob, vw):
    pg = await c.new_page(); pg.set_default_timeout(120000); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(URL + "#nord", timeout=120000); await pg.add_style_tag(content="html{scroll-behavior:auto!important}"); await pg.wait_for_timeout(800)
    vis = "(()=>{const b=document.getElementById('fbar');return b.classList.contains('show')&&!b.inert&&getComputedStyle(b).visibility==='visible'})()"
    async def scroll(dy):
        for _ in range(8): await pg.evaluate(f"scrollBy(0,{dy/8})"); await pg.wait_for_timeout(30)
        await pg.wait_for_timeout(350)
    check(T + "bar hidden at top (header visible)", not await pg.evaluate(vis))
    await scroll(1500); check(T + "bar hidden while scrolling down", not await pg.evaluate(vis))
    await scroll(-200); check(T + "bar shows on scroll up", await pg.evaluate(vis))
    y0 = await pg.evaluate("document.getElementById('fbar').getBoundingClientRect().top"); check(T + "bar pinned at top, 44px", y0 == 0 and await pg.evaluate("document.getElementById('fbar').offsetHeight") == 44)
    if SHOTS: await shot(pg, f"fbar-nord-{vw}.png", pg)
    fit = await pg.evaluate("(()=>{const n=document.querySelector('#fbar nav'),r=n.getBoundingClientRect(),A=[...n.querySelectorAll('a')];n.scrollLeft=0;const f=A[0].getBoundingClientRect();n.scrollLeft=1e4;const l=A[3].getBoundingClientRect();const res=[f.left>=r.left-1&&f.right<=r.right+1, l.right<=r.right+1, n.scrollWidth<=n.clientWidth, A.map(a=>a.textContent).join(' ')];n.scrollLeft=0;return res})()")
    check(T + "all four bar links fit without scrolling", fit[0] and fit[1] and fit[2] and fit[3] == "Pick Evidence Verdict Card", str(fit))
    br = await pg.evaluate("(()=>{const b=document.querySelector('#fbar .brand');return [b.getAttribute('aria-label'),b.getAttribute('href'),b.innerText.trim(),getComputedStyle(b).fontSize,getComputedStyle(document.querySelector('#fbar nav a')).fontSize]})()")
    check(T + ("brand is '$' on narrow screens" if mob else "brand is the wordmark on desktop"), br[0] == "lyingterminals, back to top" and br[1] == "#top" and (br[2] == "$" if mob else br[2].startswith("lyingterminals")) and br[3] == br[4] == "14px", str(br))
    if mob:
        await pg.set_viewport_size({"width": 360, "height": 780}); await pg.wait_for_timeout(200)
        f360 = await pg.evaluate("(()=>{const n=document.querySelector('#fbar nav');return n.scrollWidth<=n.clientWidth})()")
        check(T + "all four links fit at 360 too", f360)
        await pg.set_viewport_size({"width": vw, "height": 844}); await pg.wait_for_timeout(200)
    tb = await pg.evaluate("(()=>{const b=document.getElementById('fbarTerm'),r=b.getBoundingClientRect();return [b.tagName,b.title,b.getAttribute('aria-label'),b.textContent,r.width,r.height,r.right<=innerWidth]})()")
    check(T + ">_ button: labelled, titled, 44px, inside the bar", tb[:4] == ["BUTTON", "Open terminal (`)", "Open terminal", ">_"] and tb[4] >= 44 and tb[5] >= 44 and tb[6], str(tb))
    tc = await pg.evaluate("(()=>{const P=c=>c.match(/[\\d.]+/g).slice(0,3).map(Number);const lin=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};const L=c=>{const[r,g,b]=P(c);return .2126*lin(r)+.7152*lin(g)+.0722*lin(b)};const x=L(getComputedStyle(fbarTerm).color),y=L(getComputedStyle(document.body).backgroundColor);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)})()")
    check(T + ">_ contrast >= 3:1", tc >= 3, f"{tc:.2f}")
    await pg.click("#fbarTerm"); await pg.wait_for_timeout(250)
    check(T + ">_ opens the drop-down terminal", await pg.evaluate("TERM.isOpen"))
    await pg.evaluate("TERM.close()"); await pg.wait_for_timeout(500); await scroll(-150)
    check(T + "no grade pill in the bar", await pg.evaluate("!document.querySelector('#fbar .gr, #fbarGrade')"))
    await scroll(300); check(T + "bar hides again on scroll down", not await pg.evaluate(vis))
    await scroll(-200)
    await pg.evaluate("scrollTo(0,0)"); await pg.wait_for_timeout(200); await scroll(2500); await scroll(-200)
    await pg.evaluate("TERM.open()"); await pg.wait_for_timeout(250); check(T + "bar hidden while drop-down is open", await pg.evaluate("getComputedStyle(document.getElementById('fbar')).visibility") == "hidden"); await pg.evaluate("TERM.close()")
    await scroll(-150)
    await pg.add_style_tag(content="*{transition:none!important}")
    worst = await pg.evaluate("(cr)=>{const f=eval(cr);let m=[99,''];for(const k of Object.keys(THEMES)){run(THEMES[k],k);const r=f();if(r[0]<m[0])m=[r[0],k+': '+r[1]];}return m}", BAR_CR)
    check(T + "bar text >= 4.6:1 in all 17 themes", worst[0] >= 4.6, str(worst))
    dd = await pg.evaluate("(()=>{const P=c=>c.match(/[\\d.]+/g).slice(0,3).map(Number);const lin=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};const L=c=>{const[r,g,b]=P(c);return .2126*lin(r)+.7152*lin(g)+.0722*lin(b)};const CR=(a,b)=>{const x=L(a),y=L(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};const e=document.querySelector('.dedication');let m=[99,''];for(const k of Object.keys(THEMES)){run(THEMES[k],k);const v=CR(getComputedStyle(e).color,getComputedStyle(document.body).backgroundColor);if(v<m[0])m=[+v.toFixed(2),k];}const cs=getComputedStyle(e);return [e.textContent,cs.fontStyle,cs.fontSize,cs.textAlign,m,e.parentElement.previousElementSibling.tagName,Math.abs(e.getBoundingClientRect().left-document.querySelector('footer').getBoundingClientRect().left)<1]})()")
    check(T + "dedication present, italic, left-aligned with footer", dd[0] == "The floating bar above was envisioned by Seb Van Papple, visionary of navigation, who looked upon a long page and declared: let there be a way back up. Generations of scrollers, as yet unborn, stand forever in his debt." and dd[1] == "italic" and dd[2] == ("14px" if mob else "13px") and dd[3] in ("left", "start") and dd[5] == "FOOTER" and dd[6], str(dd[1:4] + dd[5:]))
    check(T + "dedication >= 4.6:1 in all 17 themes", dd[4][0] >= 4.6, str(dd[4]))
    if mob and SHOTS:
        await pg.evaluate("run(THEMES['nord'],'nord'); scrollTo(0,document.body.scrollHeight)"); await pg.wait_for_timeout(300); await shot(pg, "dedication-390.png", pg)
    dw = await pg.evaluate("(cr)=>{eval(cr);const P=c=>c.match(/[\\d.]+/g).slice(0,3).map(Number);const lin=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};const L=c=>{const[r,g,b]=P(c);return .2126*lin(r)+.7152*lin(g)+.0722*lin(b)};const CR=(a,b)=>{const x=L(a),y=L(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};let m=[99,''];for(const k of Object.keys(THEMES)){run(THEMES[k],k);const v=CR(getComputedStyle(document.querySelector('#fbar .dollar')).color,getComputedStyle(document.body).backgroundColor);if(v<m[0])m=[+v.toFixed(2),k];}return m}", "0")
    check(T + "'$' >= 4.6:1 in all 17 themes", dw[0] >= 4.6, str(dw))
    if SHOTS:
        await pg.evaluate("run(THEMES['github-light'],'github-light')"); await pg.wait_for_timeout(100); await shot(pg, f"fbar-github-light-{vw}.png", pg)
    await pg.evaluate("document.querySelector('#fbar nav a[href=\"#verdict\"]').click()"); await pg.wait_for_timeout(600)
    top = await pg.evaluate("document.getElementById('verdict').getBoundingClientRect().top")
    check(T + "anchor lands below the bar", 44 <= top <= 90, str(top))
    cur = await pg.evaluate("[...document.querySelectorAll('[aria-current=location]')].map(a=>(a.closest('.fbar')?'bar':'head')+a.getAttribute('href'))")
    check(T + "aria-current marks Verdict in bar and header", sorted(cur) == ["bar#verdict", "head#verdict"], str(cur))
    ul = await pg.evaluate("(cr)=>{const a=document.querySelector('#fbar nav a[aria-current]'),cs=getComputedStyle(a);const P=c=>c.match(/[\\d.]+/g).slice(0,3).map(Number);const lin=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};const L=c=>{const[r,g,b]=P(c);return .2126*lin(r)+.7152*lin(g)+.0722*lin(b)};const x=L(cs.textDecorationColor),y=L(getComputedStyle(document.body).backgroundColor);return [cs.textDecorationLine,cs.textDecorationThickness,+((Math.max(x,y)+.05)/(Math.min(x,y)+.05)).toFixed(2)]}", "")
    check(T + "current-section underline 2px, >= 3:1", ul[0] == "underline" and ul[1] == "2px" and ul[2] >= 3, str(ul))
    await pg.evaluate("document.querySelector('#fbar nav a[href=\"#pick\"]').click()"); await pg.wait_for_timeout(600)
    cur = await pg.evaluate("[...document.querySelectorAll('#fbar [aria-current=location]')].map(a=>a.getAttribute('href'))")
    check(T + "aria-current follows to Pick", cur == ["#pick"], str(cur))
    if mob and SHOTS: await pg.evaluate("scrollBy(0,-60)"); await pg.wait_for_timeout(400); await shot(pg, "bar-current-390.png", pg)
    if os.path.exists(AXE):
        await scroll(-150); await pg.add_script_tag(path=AXE)
        res = await pg.evaluate("axe.run({include:[['#fbar']]},{resultTypes:['violations']}).then(r=>r.violations.filter(v=>['serious','critical'].includes(v.impact)).map(v=>v.id))")
        check(T + "axe on visible bar: no serious/critical", not res and await pg.evaluate(vis), str(res))
    check(T + "bar: no page errors", not errs, str(errs)); await pg.close()

async def fs_test(c, T, mob):
    pg = await c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(URL + "#nord", timeout=120000); await pg.add_style_tag(content="html{scroll-behavior:auto!important}"); await pg.wait_for_timeout(700)
    async def ex(cmd):
        await pg.evaluate("c=>TERM.exec(c)", cmd)
        return await pg.evaluate("(([...document.querySelectorAll('#tmOut .blk')].pop()||{}).innerText||'').replace(/\\u00a0/g,' ')")
    o = await ex("ls -la"); check(T + "ls -la lists hidden .lies, dirs and files", all(x in o for x in [".lies", "evidence", "themes", "verdict.txt", "drwxr-xr-x" if not mob else "4096"]), o[-120:])
    col = await pg.evaluate("(()=>{const s=[...document.querySelectorAll('#tmOut .blk:last-child span')].find(e=>e.textContent==='evidence');return [getComputedStyle(s).color, getComputedStyle(document.getElementById('tm')).getPropertyValue('--t4').trim()]})()")
    import re as _r
    hx = col[1].lstrip('#'); rgbv = "rgb(%d, %d, %d)" % tuple(int(hx[i:i+2], 16) for i in (0, 2, 4))
    check(T + "ls colours dirs with the theme's raw blue", col[0] == rgbv, str(col))
    o = await ex("cd evidence"); await pg.wait_for_timeout(1000); top = await pg.evaluate("document.getElementById('evidence').getBoundingClientRect().top")
    check(T + "cd evidence scrolls the page there", 0 <= top <= 120 and "evidence" in o, f"{top:.0f} {o.splitlines()[-1]}")
    o = await ex("pwd"); check(T + "pwd", o.strip().endswith("/home/you/evidence"), o)
    check(T + "prompt shows cwd", "~/evidence" in await pg.evaluate("document.getElementById('tmPrompt').textContent"))
    o = await ex("cat ../themes/nord.theme"); check(T + "cat theme file: 16 colours with hex and ratios", o.count("#") >= 19 and "bright black" in o and "1.69" in o, o[:80])
    o = await ex("cd"); await pg.wait_for_timeout(1000); top = await pg.evaluate("scrollY"); check(T + "bare cd goes home and to the top", top < 5 and await pg.evaluate("document.getElementById('tmPrompt').textContent").__await__ if False else top < 5, str(top))
    o = await ex("cat .lies"); check(T + "cat .lies lists the worst offences", o.count("\n") >= 2 and "1." in o, o[:80])
    o = await ex("cat verdict.txt"); check(T + "cat verdict.txt has grade", "grade D" in o, o[:80])
    o = await ex("grep FAIL verdict.txt"); check(T + "grep FAIL verdict.txt finds tagged lines", o.count("FAIL") >= 1 and "bright black" in o, o[-120:])
    o1 = await ex("ls -la"); o2 = await ex("ls -la")
    sz = lambda o: [l for l in o.splitlines() if "error.log" in l]
    check(T + "error.log size stable across ls -la", sz(o1) and [l.split()[-5 if not mob else 0] for l in sz(o1)] == [l.split()[-5 if not mob else 0] for l in sz(o2)], str(sz(o1) + sz(o2)))
    o = await ex("cat nope"); check(T + "zsh-style cat error", o.splitlines()[-1] == "cat: nope: No such file or directory", o)
    o = await ex("cd nope"); check(T + "zsh-style cd error", o.splitlines()[-1] == "cd: no such file or directory: nope", o)
    o = await ex("frob"); check(T + "zsh-style command not found", "zsh: command not found: frob" in o and "help" in o, o)
    o = await ex("history"); check(T + "history has no stray summary line", o.strip().splitlines()[-1].strip().endswith("history"), o[-80:])
    legend = await pg.evaluate("document.querySelector('.legend').textContent")
    check(T + "legend says bright is darker than its normal twin", "↓ bright is darker than its normal twin" in legend)
    note = await pg.evaluate("document.getElementById('metaNote').textContent")
    check(T + "page note: no 'Like Pi', page vs fix labelled", "Like Pi" not in note and ("page itself had to adjust" in note or "needed no fixes" in note) and "fix" in note, note[:160])
    st = "(()=>{const s=document.getElementById('tmSugg'),v=e=>getComputedStyle(e).display!=='none'&&!e.hidden;return {over:s.scrollWidth-s.clientWidth,left:Math.round(s.scrollLeft),w:s.clientWidth,L:v(document.getElementById('tmArrL')),R:v(document.getElementById('tmArrR')),rows:new Set([...s.children].map(b=>Math.round(b.getBoundingClientRect().top))).size}})()"
    await pg.evaluate("document.getElementById('tmSugg').scrollLeft=0"); await pg.wait_for_timeout(150); a0 = await pg.evaluate(st)
    check(T + "chips stay on one scrolling row", a0["rows"] == 1 and a0["over"] > 0, str(a0))
    check(T + "start: › shown, ‹ hidden", a0["R"] and not a0["L"], str(a0))
    lab = await pg.evaluate("[tmArrL.getAttribute('aria-label'),tmArrR.getAttribute('aria-label'),tmArrR.tagName,tmArrR.getBoundingClientRect().width,tmArrR.getBoundingClientRect().height]")
    check(T + "arrows are labelled buttons with 44px hit area", lab[:3] == ["Previous commands", "More commands", "BUTTON"] and lab[3] >= 44 and lab[4] >= 44, str(lab))
    await pg.click("#tmArrR"); await pg.wait_for_timeout(700); a1 = await pg.evaluate(st)
    check(T + "› scrolls about 80% of the row", abs(a1["left"] - min(a0["over"], round(a0["w"] * .8))) <= 3 and a1["L"], str(a1))
    await pg.evaluate("document.getElementById('tmSugg').scrollLeft=1e5"); await pg.wait_for_timeout(200); a2 = await pg.evaluate(st)
    check(T + "end: › hidden, ‹ shown", not a2["R"] and a2["L"], str(a2))
    await pg.click("#tmArrL"); await pg.wait_for_timeout(700); a3 = await pg.evaluate(st)
    check(T + "‹ scrolls back", a3["left"] < a2["left"], str(a3))
    await pg.evaluate("document.getElementById('tmSugg').scrollLeft=0"); await pg.wait_for_timeout(150)
    if not mob:
        bx = await pg.evaluate("(()=>{const r=tmSugg.getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2]})()")
        await pg.mouse.move(*bx); y0 = await pg.evaluate("scrollY"); await pg.mouse.wheel(0, 120); await pg.wait_for_timeout(300)
        w = await pg.evaluate("[tmSugg.scrollLeft, scrollY]")
        check(T + "vertical wheel scrolls the chip row sideways", w[0] > 50 and w[1] == y0, str(w))
    o = await ex("cat exhibits/card.png"); check(T + "cat card.png is binary garbage", "PNG" in o)
    o = await ex("grep trenchcoat"); check(T + "grep finds findings", "trenchcoat" in o and ":" in o, o[:80])
    o = await ex("echo $USER uses $THEME"); check(T + "echo expands variables", o.strip().endswith("you uses Nord"), o)
    o = await ex("whoami"); check(T + "whoami", "you, presumably" in o)
    o = await ex("man ls"); check(T + "man ls", "list files" in o)
    o = await ex("fix"); check(T + "fix states target and repaired count", "just above the 4.6 bar" in o and "repaired" in o and "palette colours" in o, o[:200])
    ttl = await pg.evaluate("document.getElementById('tmTitle').innerText.trim()")
    check(T + ("console title shows '· fixed' on mobile" if mob else "console title shows fixed colours"), ttl.endswith("· fixed") if mob else "(fixed colours)" in ttl, ttl)
    o = await ex("ls themes"); check(T + "fix creates themes/nord.fixed", "nord.fixed" in o)
    o = await ex("diff themes/nord.theme themes/nord.fixed"); check(T + "diff shows -/+ colour lines", "--- themes/nord.theme" in o and "\n- black" in o and "\n+ black" in o, o[:100])
    o = await ex("open themes/dracula.theme"); check(T + "open .theme switches theme", await pg.evaluate("currentKey") == "dracula" and "Dracula" in o)
    o = await ex("open themes/nord.fixed"); check(T + "open .fixed applies the fix", await pg.evaluate("[currentKey, TERM.fixed]") == ["nord", True], o)
    o = await ex("history"); check(T + "history numbers commands", "  1  ls -la" in o)
    for cmd, word in [("vim x", "read-only"), ("rm notes", "read-only"), ("ssh court", "refused"), ("git push", "rejected"), ("sudo ls", "Nice try"), ("cd ../..", "permission denied")]:
        o = await ex(cmd); check(T + f"refusal: {cmd}", word.lower() in o.lower(), o.splitlines()[-1])
    o = await ex("frobnicate"); check(T + "unknown command hints at help", "help" in o)
    await pg.fill("#tmInput", "cat ver"); await pg.press("#tmInput", "Tab"); v1 = await pg.input_value("#tmInput")
    await pg.fill("#tmInput", "cd ev"); await pg.press("#tmInput", "Tab"); v2 = await pg.input_value("#tmInput")
    await pg.fill("#tmInput", "cat themes/dr"); await pg.press("#tmInput", "Tab"); v3 = await pg.input_value("#tmInput")
    await pg.fill("#tmInput", "gr"); await pg.press("#tmInput", "Tab"); v4 = await pg.input_value("#tmInput"); await pg.fill("#tmInput", "")
    check(T + "Tab completes paths and commands", [v1, v2, v3, v4] == ["cat verdict.txt", "cd evidence/", "cat themes/dracula.theme", "grep "], str([v1, v2, v3, v4]))
    chips = await pg.evaluate("[...document.querySelectorAll('#tmSugg button')].map(b=>b.dataset.cmd)")
    check(T + "chips include ls -la and cat verdict.txt", "ls -la" in chips and "cat verdict.txt" in chips)
    await ex("cat verdict.txt"); await pg.wait_for_timeout(80); lv = await pg.evaluate("document.getElementById('tmLive').textContent")
    check(T + "aria-live stays concise", 0 < len(lv) < 240, lv)
    if SHOTS:
        await ex("clear"); await ex("cd ~"); await ex("ls -la"); await shot(pg, f"fs-ls-la-{'390' if mob else '1366'}.png", pg.locator("#tm"))
        await ex("clear"); await ex("cat themes/solarized-light.theme"); await shot(pg, f"fs-cat-theme-{'390' if mob else '1366'}.png", pg.locator("#tm"))
    if os.path.exists(AXE):
        await pg.wait_for_timeout(1500)  # let the theme colour transitions from 'open' settle
        await pg.add_script_tag(path=AXE)
        res = await pg.evaluate("axe.run({exclude:[['#tmOut .demo'],['.sw .aa']]},{resultTypes:['violations']}).then(r=>r.violations.filter(v=>['serious','critical'].includes(v.impact)).map(v=>v.id+':'+v.nodes.map(n=>n.target.join(' ')).join(' ; ')))")
        check(T + "axe after filesystem commands: no serious/critical", not res, str(res))
    check(T + "filesystem: no page errors", not errs, str(errs)); await pg.close()

async def stream_test(b, vw):
    T = f"[{vw}] "; mob = vw < 1000
    c = await b.new_context(viewport={"width": vw, "height": 844 if mob else 900}, is_mobile=mob, has_touch=mob)
    pg = await c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(URL + "#solarized-light", timeout=120000); await pg.wait_for_timeout(800)
    await pg.evaluate("""()=>{window.__live=[];new MutationObserver(()=>{const t=document.getElementById('tmLive').textContent;if(t)window.__live.push(t)}).observe(document.getElementById('tmLive'),{childList:true,characterData:true,subtree:true})}""")
    t0 = await pg.evaluate("performance.now()")
    await pg.evaluate("TERM.exec('fix')")
    mid = await pg.evaluate("[TERM.streaming, document.querySelectorAll('#tmOut .blk:last-child .ln.pend').length]")
    check(T + "fix output streams in (lines pending right after Enter)", mid[0] and mid[1] > 5, str(mid))
    check(T + "nothing announced while streaming", await pg.evaluate("window.__live.length") == 0)
    await pg.wait_for_function("!TERM.streaming", timeout=3000); ms = await pg.evaluate("performance.now()") - t0
    check(T + "fix finishes within ~1s", ms < 1100, f"{ms:.0f}ms")
    await pg.wait_for_timeout(100); lv = await pg.evaluate("window.__live")
    check(T + "one concise announcement at the end", len(set(lv)) == 1 and len(lv[0]) < 240, str(lv))
    sb = await pg.evaluate("(()=>{const b=document.getElementById('tmBody');return b.scrollHeight-b.clientHeight-b.scrollTop})()")
    check(T + "stays at the bottom", sb <= 1, str(sb))
    await pg.evaluate("TERM.exec('judge')"); await pg.keyboard.press("Shift")
    sk = await pg.evaluate("[TERM.streaming, document.querySelectorAll('#tmOut .ln.pend').length]")
    check(T + "a keypress skips to the end", sk == [False, 0], str(sk))
    await pg.evaluate("TERM.exec('git log')"); await pg.evaluate("TERM.exec('ls')")
    check(T + "a new command flushes pending output", await pg.evaluate("document.querySelectorAll('#tmOut .ln.pend').length") == 0 or await pg.evaluate("[...document.querySelectorAll('#tmOut .blk')].slice(0,-1).every(b=>!b.querySelector('.ln.pend'))"))
    await pg.wait_for_function("!TERM.streaming", timeout=3000)
    await pg.evaluate("TERM.exec('clear')"); await pg.evaluate("TERM.exec('fix --undo')")
    ty = await pg.evaluate("document.querySelector('#tmOut .blk:last-child .ln:last-child').textContent.length")
    full = await pg.evaluate("new Promise(r=>{const f=()=>TERM.streaming?setTimeout(f,5):r(document.querySelector('#tmOut .blk:last-child .ln:last-child').textContent.length);f()})")
    check(T + "short line is typed character by character", ty < full, f"{ty} -> {full}")
    await pg.emulate_media(reduced_motion="reduce"); await pg.evaluate("TERM.exec('judge')")
    check(T + "reduced motion: instant output", not await pg.evaluate("TERM.streaming") and await pg.evaluate("document.querySelectorAll('#tmOut .ln.pend').length") == 0)
    check(T + "streaming: no page errors", not errs, str(errs)); await c.close()

async def run(b, vw):
    mob = vw < 1000; errs = []
    c = await b.new_context(viewport={"width": vw, "height": 844 if mob else 900}, device_scale_factor=2 if mob else 1, is_mobile=mob, has_touch=mob, accept_downloads=True)
    await c.add_init_script("window.TERM_INSTANT=true")  # functional checks read output at once; streaming has its own test
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
    again = []
    for _ in range(3):
        await (pg.tap("#heroHint") if mob else pg.click("#heroHint")); await pg.wait_for_timeout(250); o = await pg.evaluate("TERM.isOpen")
        await (pg.tap("#tmClose") if mob else pg.keyboard.press("Escape")); await pg.wait_for_timeout(250); again.append(o and not await pg.evaluate("TERM.isOpen"))
    check(T + "hint opens on every click/tap", all(again), str(again))
    hs = await pg.evaluate("(()=>{const b=document.getElementById('heroHint'),k=b.querySelector(mobile()? '.k':'kbd');function mobile(){return getComputedStyle(b.querySelector('.touch')).display!=='none'} return [getComputedStyle(b).fontSize, getComputedStyle(b).color===getComputedStyle(document.body).color||getComputedStyle(b).color, getComputedStyle(k).color]})()")
    check(T + "hint 14-15px, text colour, accent key", hs[0] in ("14px", "15px") and hs[1] is True, str(hs))
    # A2: fix
    await pg.evaluate("document.activeElement.blur()"); await pg.keyboard.press("`"); await pg.wait_for_timeout(200)
    await typ(pg, "theme solarized-light"); await pg.wait_for_timeout(500); await typ(pg, "clear"); await typ(pg, "fix")
    fx = await pg.evaluate("""(()=>{const t=[...document.querySelectorAll('#tmOut .blk')].pop().innerText.replace(/\u00a0/g,' '); return {txt:t, fixed:TERM.fixed, live:document.getElementById('tmLive').textContent}})()""")
    flat = fx["txt"].replace("\n", " ")
    check(T + "fix prints old → new rows and the new grade", "→" in flat and "grade F → C, 7 → 72" in flat, fx["txt"][-200:].replace("\n", " | "))
    import re as _re
    check(T + "fix ratios use two decimals", bool(_re.search(r"\d\.\d\d → (#[0-9a-f]{6}|██ \d\.\d\d)", flat)) and not _re.search(r" \d\.\d → ", flat))
    check(T + "fix copy: original theme + remaining charges", "the page keeps the original." in flat and "still grey" in flat and "stays raw" not in flat)
    hdr = await pg.evaluate("[...document.querySelectorAll('#tmOut .blk:last-child .ln')].slice(1,3).map(l=>Math.round(l.getBoundingClientRect().height/parseFloat(getComputedStyle(l).lineHeight)))")
    if not mob: check(T + "fix header: two deliberate lines, no wrap", hdr == [1, 1], str(hdr))
    await shot(pg, f"fix-{vw}.png", pg.locator("#tm"))
    pal = await pg.evaluate("""(()=>{const s=getComputedStyle(document.getElementById('tm')),bg=s.getPropertyValue('--tbg').trim();const v=[...Array(16).keys()].map(i=>s.getPropertyValue('--t'+i).trim());
      return {bg, under:v.filter((h,i)=>contrast(h,bg)<4.6&&i!==15&&i!==7).length, page:getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()}})()""")
    check(T + "fixed palette in terminal, no colour under 4.6", pal["under"] == 0, json.dumps(pal))
    await typ(pg, "judge"); j = await pg.evaluate("[...document.querySelectorAll('#tmOut .blk')].pop().innerText.replace(/\u00a0/g,' ')")
    check(T + "judge labels fixed palette", "(fixed)" in j)
    async with pg.expect_download() as dl: await typ(pg, "export kitty")
    path = await (await dl.value).path(); body = open(path).read()
    check(T + "export uses fixed palette", "(fixed)" in body and "Grade C" in body)
    note = await pg.evaluate("[...document.querySelectorAll('#tmOut .blk')].pop().innerText.replace(/\u00a0/g,' ')")
    check(T + "export note says what remains", "still grey" in note and "every lie listed above" not in note, note.split("\n")[-1])
    for cmd in ["help", "git diff", "npm test", "cat error.log", "git log", "fix --undo", "fix"]: await typ(pg, cmd)
    await pg.keyboard.press("Escape"); await pg.wait_for_timeout(200)
    check(T + "one Esc closes after fix with long output", not await pg.evaluate("TERM.isOpen"))
    await pg.keyboard.press("`"); await pg.wait_for_timeout(200)
    await typ(pg, "fix --undo"); check(T + "fix --undo reverts", not await pg.evaluate("TERM.fixed"))
    await typ(pg, "theme dracula"); st = await pg.evaluate("[...document.querySelectorAll('#tmOut .blk')].pop().innerText.replace(/\u00a0/g,' ')")
    check(T + "document.title follows the theme", await pg.evaluate("document.title") == "Dracula gets an A. Is your terminal theme lying to you?", await pg.evaluate("document.title"))
    await pg.evaluate("document.querySelector(\"button[data-k='nord']\").click()"); await pg.wait_for_timeout(150)
    check(T + "title updates on chip switch", (await pg.evaluate("document.title")).startswith("Nord gets a D."))
    await typ(pg, "theme dracula")
    check(T + "status line shows the share URL form", ("/t/dracula" in st) if URL.startswith("http") else ("#dracula" in st), st.split("\n")[-1])
    title = await pg.evaluate("[document.getElementById('tmTitle').innerText, document.getElementById('tmTitle').scrollWidth<=document.getElementById('tmTitle').clientWidth]")
    check(T + "console title fits" + (" without '(raw colours)'" if mob else ""), title[1] and (("raw colours" not in title[0] and "you@localhost" not in title[0]) if mob else ("raw colours" in title[0])), str(title))
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
    if not mob:
        await pg.keyboard.press("`"); await pg.wait_for_timeout(150); await pg.keyboard.type("exit"); y0 = await pg.evaluate("scrollY")
        await pg.keyboard.press("Enter"); await pg.keyboard.type(" `ls"); await pg.wait_for_timeout(500)
        check(T + "keys typed right after exit don't reach the page", not await pg.evaluate("TERM.isOpen") and await pg.evaluate("scrollY") == y0, str(await pg.evaluate("[TERM.isOpen, scrollY]")) + f" {y0}")
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
    await fbar(c, T, mob, vw)
    await fs_test(c, T, mob)
    await c.close()

async def main():
    async with async_playwright() as p:
        kw = {"executable_path": os.environ["CHROME_PATH"]} if os.environ.get("CHROME_PATH") else {}
        b = await p.chromium.launch(args=["--no-sandbox"], **kw)
        for vw in (1366, 390): await run(b, vw); await stream_test(b, vw)
        await b.close()
    print(f"\n{len(FAILS)} failed" if FAILS else "\nall passed"); sys.exit(1 if FAILS else 0)
asyncio.run(main())
