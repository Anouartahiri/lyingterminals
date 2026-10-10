"""Render one 1200x630 share card per preset: python og/gen_cards.py <index.html> <outdir> <fonts-dir>
Rows are computed with the site's own maths and pill rules: FAIL < 3, MEH < 4.6, LIE = bright not brighter than its twin.
Every card text colour is the page's contrast-safe derivation (>= 4.6:1); the script asserts it."""
import asyncio, json, sys, os
from playwright.async_api import async_playwright
SRC, OUT, FONTS = sys.argv[1], sys.argv[2], sys.argv[3]
DM=open(os.path.join(FONTS,"dm.b64")).read().strip(); NR=open(os.path.join(FONTS,"nr.b64")).read().strip()
DATA_JS = r"""(()=>{
 const N=["black","red","green","yellow","blue","magenta","cyan","white"], nm=i=>i<8?N[i]:"bright "+N[i-8];
 const out={};
 for(const [k,t] of Object.entries(THEMES)){
  const A=analyze(t), {skin}=deriveSkin(t), bg=t.bg, light=lum(bg)>0.4, r=h=>contrast(h,bg), f=x=>fmt(x);
  const rows=[];
  // LIE: bright not brighter than its twin (same rule as lie mode)
  for(let i=1;i<7;i++){ const b=t.c[i+8], n=t.c[i]; if((b===n||r(b)<r(n)-0.05)&&r(b)<4.6) rows.push({p:0,lab:"LIE",cls:"lol",txt:b===n?`bright ${N[i]} = ${N[i]}`:`bright ${N[i]} dimmer than ${N[i]}`,v:f(r(b)),i:i+8}); }
  // foreground
  if(r(t.fg)<4.6) rows.push({p:-1,lab:r(t.fg)<3?"FAIL":"MEH",cls:r(t.fg)<3?"fail":"warn",txt:"foreground: under WCAG AA",v:f(r(t.fg)),i:"fg"});
  // per-colour FAIL / MEH (skip the black-on-dark / white-on-light pair: that's expected)
  for(let i=0;i<16;i++){ if(rows.some(x=>x.i===i)) continue; const v=r(t.c[i]); if(v>=4.6) continue;
    if((!light&&i===0)||(light&&(i===7||i===15))) continue;  // black on dark / white on light is expected, not a charge
    rows.push({p:(i===8?1:(v<3?2:3)),lab:v<3?"FAIL":"MEH",cls:v<3?"fail":"warn",txt:t.c[i]===bg?`${nm(i)} = background`:(i===8?"bright black (comments)":nm(i)),v:f(v),i}); }
  rows.sort((a,b)=>a.p-b.p||parseFloat(a.v)-parseFloat(b.v));
  // never show one number with two different verdicts
  const seen={}, pick=[]; for(const x of rows){ if(seen[x.v]&&seen[x.v]!==x.lab) continue; seen[x.v]=x.lab; pick.push(x); if(pick.length===4) break; }
  // honest passes to fill the card for well-behaved themes
  const pass=[["foreground","fg",t.fg],["bright black (comments)",8,t.c[8]],["red",1,t.c[1]],["blue",4,t.c[4]]];
  for(const [txt,i,h] of pass){ if(pick.length>=4) break; if(pick.some(x=>x.i===i)||r(h)<4.6) continue; const v=f(r(h)); if(seen[v]&&seen[v]!=="PASS") continue; seen[v]="PASS"; pick.push({lab:"PASS",cls:"ok",txt,v,i}); }
  const title=ensure(skin.muted,skin.panel,4.6);
  out[k]={name:t.name,grade:A.grade,score:A.score,verdict:A.verdict,light,skin:{...skin,title},rows:pick,top:(A.findings.find(x=>x.sev!=="ok")||{}).text||A.verdict};
 }
 return out; })()"""
SUMMARY={"A+":"mostly truthful","A":"mostly truthful","B":"minor perjury","C":"it's complicated","D":"gaslighting you","F":"certified liar"}
ROLE={"A+":"green","A":"green","B":"blue","C":"yellow","D":"yellow","F":"red"}
MARK={"fail":("✗","red"),"warn":("!","yellow"),"lol":("?","magenta"),"ok":("✓","green")}
def html(d):
    s=d["skin"]; rows="".join(f'<div class="ln"><span data-m="marker" style="color:var(--{MARK[x["cls"]][1]})">{MARK[x["cls"]][0]}</span> <span data-m="finding">{x["txt"]}</span><span data-m="pill" class="lab" style="color:var(--{MARK[x["cls"]][1]})">{x["lab"]} {x["v"]}</span></div>' for x in d["rows"])
    shadow="rgba(88,70,20,.35)" if d["light"] else "#000"
    return f'''<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:"DM";src:url(data:font/woff2;base64,{DM}) format("woff2")}}
@font-face{{font-family:"NR";src:url(data:font/woff2;base64,{NR}) format("woff2")}}
:root{{--bg:{s["bg"]};--fg:{s["fg"]};--muted:{s["muted"]};--line:{s["line"]};--panel:{s["panel"]};--red:{s["red"]};--green:{s["green"]};--yellow:{s["yellow"]};--magenta:{s["magenta"]};--blue:{s["blue"]};--cyan:{s["cyan"]}}}
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:1200px;height:630px;overflow:hidden;background:var(--bg);color:var(--fg)}}
h1{{position:absolute;top:62px;left:0;right:0;text-align:center;font:400 62px/1 "NR";letter-spacing:-.02em}}
h1 i{{color:var(--red);font-style:normal}}
.win{{position:absolute;left:120px;top:154px;width:960px;height:364px;border:1px solid var(--line);border-radius:16px;background:var(--bg);box-shadow:0 30px 60px -34px {shadow};overflow:hidden}}
.bar{{height:46px;background:var(--panel);border-bottom:1px solid var(--line);display:flex;align-items:center;padding:0 20px;gap:10px;font:20px "DM"}}
.bar b{{width:14px;height:14px;border-radius:50%;display:inline-block}}
.bar .t{{margin-left:auto;margin-right:auto;transform:translateX(-30px);color:{s["title"]}}}
.body{{position:relative;padding:22px 30px;font:28px/46px "DM"}}
.ln{{white-space:nowrap}}
.lab{{display:inline-block;font-size:19px;line-height:1;letter-spacing:.05em;padding:6px 11px;border:2px solid currentColor;border-radius:99px;vertical-align:4px;margin-left:14px}}
.grade{{position:absolute;right:34px;top:30px;text-align:center;color:var(--{ROLE[d["grade"]]})}}
.grade .g{{font:400 210px/.8 "NR";letter-spacing:-.05em}}
.grade .s{{font:22px/1 "DM";color:var(--muted);margin-top:-8px;letter-spacing:.08em}}
.wm{{position:absolute;bottom:62px;left:0;right:0;text-align:center;font:32px/1 "DM";color:var(--cyan)}}
.wm span{{color:var(--muted)}}
</style></head><body>
<h1 data-m="headline">Is your terminal theme <i data-m="lying">lying</i> to you?</h1>
<div class="win"><div class="bar"><b style="background:#ff5f57"></b><b style="background:#febc2e"></b><b style="background:#28c840"></b><span class="t" data-m="title">you@localhost: ~ — {d["name"]}</span></div>
<div class="body">
 <div class="ln"><span data-m="prompt" style="color:var(--green)">you@localhost</span> <span data-m="prompt" style="color:var(--blue)">~</span> <span data-m="prompt">$ judge</span></div>
 {rows}
 <div class="ln"><span data-m="summary" style="color:var(--muted)">{SUMMARY[d["grade"]]} · {d["score"]}/100</span></div>
 <div class="grade"><div class="g" data-m="grade">{d["grade"]}</div><div class="s" data-m="grade label">grade</div></div>
</div></div>
<div class="wm" data-m="footer"><span data-m="footer">$</span> curl lyingterminals.com</div>
</body></html>'''
MEASURE=r"""(()=>{const P=c=>c.match(/[\d.]+/g).slice(0,3).map(Number);const lin=v=>{v/=255;return v<=0.04045?v/12.92:Math.pow((v+0.055)/1.055,2.4)};const L=c=>{const[r,g,b]=P(c);return .2126*lin(r)+.7152*lin(g)+.0722*lin(b)};const CR=(a,b)=>{const x=L(a),y=L(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)};
 const bgOf=e=>{while(e){const c=getComputedStyle(e).backgroundColor;if(c!=='rgba(0, 0, 0, 0)')return c;e=e.parentElement}};
 let min=99,w=''; document.querySelectorAll('[data-m]').forEach(e=>{const v=CR(getComputedStyle(e).color,bgOf(e)); if(v<min){min=v;w=e.dataset.m}});
 const r=Math.max(...[...document.querySelectorAll('.ln')].map(l=>[...l.children].pop().getBoundingClientRect().right));
 return [+min.toFixed(2),w,Math.round(r)]})()"""
async def main():
    os.makedirs(OUT,exist_ok=True)
    async with async_playwright() as p:
        b=await p.chromium.launch(**({"executable_path":os.environ["CHROME_PATH"]} if os.environ.get("CHROME_PATH") else {}),args=["--no-sandbox"])
        pg=await b.new_page(); await pg.goto("file://"+os.path.abspath(SRC)+"#nord"); await pg.wait_for_timeout(800)
        data=await pg.evaluate(DATA_JS)
        card=await b.new_page(viewport={"width":1200,"height":630}); report={}
        for k,d in data.items():
            await card.set_content(html(d)); await card.evaluate("document.fonts.ready"); await card.wait_for_timeout(150)
            m=await card.evaluate(MEASURE); assert m[0]>=4.6,(k,m); assert m[2]<=925,(k,"rows overlap grade",m)
            await card.screenshot(path=os.path.join(OUT,k+".png")); report[k]={"grade":d["grade"],"score":d["score"],"minContrast":m[0],"rows":[f'{x["txt"]} [{x["lab"]} {x["v"]}]' for x in d["rows"]]}
        json.dump({k:{"name":d["name"],"grade":d["grade"],"score":d["score"],"top":d["top"]} for k,d in data.items()},open(os.path.join(OUT,"themes.json"),"w"),ensure_ascii=False,indent=1)
        print(json.dumps(report,indent=1,ensure_ascii=False)); await b.close()
asyncio.run(main())
