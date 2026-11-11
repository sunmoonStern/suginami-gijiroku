#!/usr/bin/env python3
"""raw/ と index.json から、閲覧・検索用の静的サイトを site/ に生成する。

    python3 build.py

site/index.html をブラウザで開けば使えます(サーバー不要)。
"""
import datetime
import html
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
SITE = os.path.join(HERE, "site")
OFFICIAL = "https://suginami.gijiroku.com/voices/voices/cgi/voiweb.exe?ACT=200&KENSAKU=0&SORT=0&KTYP=0,1,2,3&KGTP=1&FINO={}"
OFFICIAL_TOP = "https://suginami.gijiroku.com/voices/voices/g08v_viewh.asp"
SITE_NAME = "杉並区議会 会議録ビューア(非公式)"

MARKS = "○◎◆◯〇●◇△▲□■"
ROLES = {"委員長", "副委員長", "委員", "議員", "議長", "副議長", "委員外議員", "理事者", "参考人", "陳述人"}
SPLIT_RE = re.compile(r'<A NAME="HUID(\d+)"></A>', re.I)
ERA_RE = re.compile(r"^(?:令和|平成)[0-9０-９元]+年(?:[0-9０-９]+月[0-9０-９]+日)?(.+)$")


def clean(seg):
    seg = seg.replace("\r", "").replace("\n", "")
    seg = re.sub(r"<BR\s*/?>", "\n", seg, flags=re.I)
    seg = re.sub(r"<[^>]+>", "", seg)
    return html.unescape(seg).strip("\n").rstrip()


def split_speaker(text):
    """先頭の「○議長（木梨もりよし議員）　」「◆大和田伸　委員　　」などを分離する。"""
    if not text or text[0] not in MARKS:
        return "", "", text
    mark = text[0]
    first = text.split("\n", 1)[0]
    # 「○議長（木梨もりよし議員）御静粛に」「◎局長（秋吉誠吾）<改行>」のように、括弧の直後で切れる形
    m = re.match(r"^.([^　（\n]{1,30}（[^）\n]{1,25}）)　*", first)
    if not m:
        m = re.match(r"^.([^　]{1,40})(?:　+|$)", first)
    if not m:
        return mark, "", text[1:]
    speaker, end = m.group(1), m.end()
    m2 = re.match(r"([^　]{1,8})　+", first[end:])
    if m2 and m2.group(1) in ROLES:
        speaker += " " + m2.group(1)
        end += m2.end()
    return mark, speaker, text[end:]


def parse(raw):
    text = raw.decode("cp932", errors="replace")
    start = text.find('<A NAME="HUID')
    if start < 0:
        return []
    end = text.find("<FORM METHOD", start)
    body = text[start : end if end > 0 else len(text)]
    parts = SPLIT_RE.split(body)
    out = []
    for i in range(1, len(parts) - 1, 2):
        seg = clean(parts[i + 1])
        if not seg:
            continue
        mark, speaker, rest = split_speaker(seg)
        out.append({"id": int(parts[i]), "mark": mark, "sp": speaker, "tx": rest})
    return out


def titles(d):
    nm = re.sub(r"[\s　]", "", d["name"])
    if d["kind"] == "委員会":
        m = ERA_RE.match(nm)
        return m.group(1) if m else nm
    return nm


E = html.escape

DOC_TMPL = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{date} {title} {no} | {site}</title>
<link rel="stylesheet" href="../app.css">
</head><body class="doc">
<header class="top"><a href="../index.html">← 検索・一覧</a><span class="unofficial">非公式</span></header>
<main>
<p class="meta">{date}・{kind}</p>
<h1>{title} <small>{no}</small></h1>
<p class="links"><a href="{official}" rel="noopener">公式の会議録検索システムで開く</a></p>
<p id="hitbar" hidden></p>
{toc}
{body}
</main>
<footer>これは杉並区議会の公式サイトではありません。杉並区議会会議録検索システムの公開内容を読みやすく再構成したもので、正確な内容は<a href="{official_top}">公式の会議録</a>で確認してください。</footer>
<script src="../doc.js"></script>
</body></html>
"""


def render_doc(d, us):
    toc_items, body = [], []
    for u in us:
        uid = f"u{u['id']}"
        if not u["mark"]:
            body.append(f'<details class="note" id="{uid}" open><summary>記載事項</summary><div class="tx">{E(u["tx"])}</div></details>')
            continue
        cls = {"○": "m-o", "◯": "m-o", "〇": "m-o", "◎": "m-a", "◆": "m-q"}.get(u["mark"], "m-o")
        sp = E(u["sp"] or "(発言者不明)")
        toc_items.append(f'<li class="{cls}"><a href="#{uid}">{sp}</a></li>')
        body.append(
            f'<article class="u {cls}" id="{uid}"><header><span class="sp">{sp}</span>'
            f'<a class="pl" href="#{uid}" title="この発言へのリンクをコピー">リンク</a></header>'
            f'<div class="tx">{E(u["tx"])}</div></article>'
        )
    toc = ""
    if toc_items:
        toc = f'<details class="toc"><summary>発言一覧({len(toc_items)}件)</summary><ol>{"".join(toc_items)}</ol></details>'
    return DOC_TMPL.format(
        date=E(d["date"]), title=E(d["title"]), no=E(d["no"]), kind=E(d["kind"]), site=E(SITE_NAME),
        official=E(OFFICIAL.format(d["fino"])), official_top=OFFICIAL_TOP, toc=toc, body="\n".join(body),
    )


INDEX_HTML = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__SITE__</title>
<link rel="stylesheet" href="app.css">
</head><body class="home">
<header class="top"><strong>__SITE__</strong></header>
<main>
<form id="f" autocomplete="off">
  <input id="q" type="search" placeholder="キーワード(スペース区切りで絞り込み)" autofocus>
  <button>検索</button>
  <div class="filters">
    <label>種別 <select id="k"><option value="">すべて</option><option value="h">本会議</option><option value="c">委員会</option></select></label>
    <label>年 <select id="y0"></select>〜<select id="y1"></select></label>
    <label>発言者 <input id="s" type="text" placeholder="例: 区長"></label>
  </div>
</form>
<p id="status"></p>
<div id="results"></div>
<button id="more" hidden>さらに表示</button>
<section id="browse"><h2>会議録一覧</h2><div id="list"></div></section>
<noscript>検索と一覧の表示には JavaScript が必要です。</noscript>
</main>
<footer>これは杉並区議会の公式サイトではありません。杉並区議会会議録検索システムの公開内容を読みやすく再構成したもので、正確な内容は<a href="__TOP__">公式の会議録</a>で確認してください。<span id="built"></span></footer>
<script src="s/manifest.js"></script>
<script src="app.js"></script>
</body></html>
"""

APP_CSS = r"""
:root{--bg:#faf9f6;--fg:#1f2328;--mut:#667085;--line:#e3e1da;--card:#fff;--acc:#0b6e4f;--q:#1d4ed8;--a:#b45309;--hl:#ffe58a}
@media(prefers-color-scheme:dark){:root{--bg:#15171a;--fg:#e6e6e3;--mut:#9aa3ad;--line:#2c3036;--card:#1c1f23;--acc:#5fd3a6;--q:#8ab4ff;--a:#f0b46a;--hl:#6b5a00}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.9 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP","Yu Gothic",Meiryo,sans-serif;-webkit-text-size-adjust:100%}
a{color:var(--acc)}
.top{position:sticky;top:0;z-index:5;display:flex;gap:.75rem;align-items:center;justify-content:space-between;padding:.5rem 1rem;background:var(--bg);border-bottom:1px solid var(--line);font-size:.9rem}
.unofficial{font-size:.75rem;color:var(--mut);border:1px solid var(--line);border-radius:99px;padding:0 .6rem}
main{max-width:46rem;margin:0 auto;padding:1rem}
footer{max-width:46rem;margin:2rem auto;padding:1rem;color:var(--mut);font-size:.8rem;line-height:1.6;border-top:1px solid var(--line)}
h1{font-size:1.35rem;line-height:1.4;margin:.2rem 0 .5rem}h1 small{font-size:.9rem;color:var(--mut);font-weight:400}
h2{font-size:1.05rem;margin:2rem 0 .5rem}
.meta{color:var(--mut);margin:0;font-size:.9rem}.links{font-size:.85rem;margin:.2rem 0 1rem}
#f{display:grid;grid-template-columns:1fr auto;gap:.5rem}
#q{font-size:1.05rem;padding:.65rem .8rem;border:1px solid var(--line);border-radius:.6rem;background:var(--card);color:var(--fg);min-width:0}
button{font:inherit;padding:.5rem 1rem;border:0;border-radius:.6rem;background:var(--acc);color:var(--bg);cursor:pointer}
.filters{grid-column:1/-1;display:flex;flex-wrap:wrap;gap:.4rem 1rem;font-size:.85rem;color:var(--mut)}
.filters select,.filters input{font:inherit;padding:.15rem .4rem;border:1px solid var(--line);border-radius:.4rem;background:var(--card);color:var(--fg);max-width:9rem}
#status{color:var(--mut);font-size:.9rem;min-height:1.5em}
.hit{background:var(--card);border:1px solid var(--line);border-radius:.7rem;padding:.7rem .9rem;margin:.7rem 0}
.hit h3{font-size:1rem;margin:0;line-height:1.5}.hit h3 small{color:var(--mut);font-weight:400;margin-right:.5em}
.hit a.sn{display:block;color:inherit;text-decoration:none;font-size:.9rem;line-height:1.7;padding:.45rem 0;border-top:1px dashed var(--line);margin-top:.45rem}
.hit a.sn b{color:var(--mut);font-weight:600;margin-right:.5em}.hit .rest{font-size:.8rem}
mark{background:var(--hl);color:inherit;border-radius:2px}
#more{display:block;margin:1rem auto}
#list details{border-bottom:1px solid var(--line)}#list summary{cursor:pointer;padding:.5rem 0;font-weight:600}
#list h4{margin:.6rem 0 .1rem;font-size:.85rem;color:var(--mut)}
#list ul{list-style:none;margin:0 0 .8rem;padding:0}#list li{display:flex;gap:.7rem;padding:.2rem 0;font-size:.92rem;line-height:1.5}
#list time{color:var(--mut);font-variant-numeric:tabular-nums;flex:none}
.toc,.note{background:var(--card);border:1px solid var(--line);border-radius:.7rem;padding:.4rem .9rem;margin:1rem 0}
.toc summary,.note summary{cursor:pointer;color:var(--mut);font-size:.9rem}
.toc ol{margin:.3rem 0;padding-left:2.2rem;font-size:.88rem;line-height:1.7;max-height:50vh;overflow:auto}
.tx{white-space:pre-wrap;overflow-wrap:anywhere}
.note .tx{font-size:.85rem;line-height:1.7;overflow-x:auto}
.u{margin:1.4rem 0;padding-left:.9rem;border-left:3px solid var(--line);scroll-margin-top:3.2rem}
.note{scroll-margin-top:3.2rem}
.u header{display:flex;justify-content:space-between;align-items:baseline;gap:1rem}
.sp{font-weight:700;font-size:.92rem}
.pl{font-size:.75rem;color:var(--mut);text-decoration:none;flex:none}
.m-q{border-left-color:var(--q)}.m-q .sp,li.m-q a{color:var(--q)}
.m-a{border-left-color:var(--a)}.m-a .sp,li.m-a a{color:var(--a)}
.m-o .sp{color:var(--mut)}li.m-o a{color:var(--mut)}
.u:target,.note:target{background:color-mix(in srgb,var(--hl) 25%,transparent);outline:.5rem solid color-mix(in srgb,var(--hl) 25%,transparent)}
#hitbar{position:sticky;top:2.6rem;z-index:4;background:var(--card);border:1px solid var(--line);border-radius:.6rem;padding:.2rem .8rem;font-size:.85rem}
#hitbar button{padding:.1rem .7rem;margin-left:.5rem;font-size:.8rem}
"""

COMMON_JS = r"""
function gjNorm(s){return s.replace(/[！-～]/g,function(c){return String.fromCharCode(c.charCodeAt(0)-0xFEE0)}).replace(/　/g,' ').toLowerCase()}
function gjTerms(q){return gjNorm(q||'').split(/\s+/).filter(Boolean)}
function gjEsc(s){return s.replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
function gjMark(text,terms){var n=gjNorm(text),r=[],i,t,p;for(i=0;i<terms.length;i++){t=terms[i];p=n.indexOf(t);while(p>=0){r.push([p,p+t.length]);p=n.indexOf(t,p+t.length)}}
 if(!r.length)return gjEsc(text);r.sort(function(a,b){return a[0]-b[0]});var out='',pos=0;for(i=0;i<r.length;i++){if(r[i][1]<=pos)continue;var s=Math.max(r[i][0],pos);out+=gjEsc(text.slice(pos,s))+'<mark>'+gjEsc(text.slice(s,r[i][1]))+'</mark>';pos=r[i][1]}return out+gjEsc(text.slice(pos))}
"""

DOC_JS = COMMON_JS + r"""
(function(){
var q=new URLSearchParams(location.search).get('q'),terms=gjTerms(q);
if(terms.length){var els=document.querySelectorAll('.tx,.sp');for(var i=0;i<els.length;i++){var t=els[i].textContent,n=gjNorm(t);if(terms.some(function(x){return n.indexOf(x)>=0}))els[i].innerHTML=gjMark(t,terms)}
 var ms=document.querySelectorAll('mark'),bar=document.getElementById('hitbar'),cur=-1;
 if(ms.length){bar.hidden=false;bar.innerHTML='「'+gjEsc(q)+'」 '+ms.length+'か所 <button type="button">次へ</button>';
  bar.querySelector('button').onclick=function(){cur=(cur+1)%ms.length;ms[cur].scrollIntoView({block:'center'})};
  if(!location.hash){cur=0;ms[0].scrollIntoView({block:'center'})}}}
document.addEventListener('click',function(e){var a=e.target.closest&&e.target.closest('a.pl');if(!a)return;e.preventDefault();
 var url=location.origin+location.pathname+a.getAttribute('href');if(location.protocol==='file:')url=location.href.split(/[?#]/)[0]+a.getAttribute('href');
 history.replaceState(null,'',a.getAttribute('href'));
 var done=function(){a.textContent='コピーしました';setTimeout(function(){a.textContent='リンク'},1500)};
 if(navigator.clipboard&&navigator.clipboard.writeText)navigator.clipboard.writeText(url).then(done,function(){});});
})();
"""

APP_JS = COMMON_JS + r"""
(function(){
var G=window.__gj=window.__gj||{};G.chunks={};var wait={};
G.add=function(y,docs){G.chunks[y]=docs;(wait[y]||[]).forEach(function(f){f()});delete wait[y]};
function load(y){if(G.chunks[y])return Promise.resolve();return new Promise(function(res,rej){if(wait[y]){wait[y].push(res);return}wait[y]=[res];var s=document.createElement('script');s.src='s/'+y+'.js';s.onerror=function(){rej(new Error('読み込み失敗'))};document.head.appendChild(s)})}
var M=G.manifest||{years:[],docs:[]},$=function(id){return document.getElementById(id)};
var years=M.years.slice().sort(function(a,b){return b-a});
years.forEach(function(y){$('y0').add(new Option(y,y));$('y1').add(new Option(y,y))});
if(years.length){$('y0').value=years[years.length-1];$('y1').value=years[0]}
$('built').textContent=' 収録: '+M.docs.length+'件(データ取得日 '+(M.built||'')+')';
// 一覧
(function(){var by={};M.docs.forEach(function(d){var y=d[1].slice(0,4);(by[y]=by[y]||[]).push(d)});var h='';
 Object.keys(by).sort().reverse().forEach(function(y,i){h+='<details'+(i===0?' open':'')+'><summary>'+y+'年('+by[y].length+'件)</summary>';
  [['本会議',function(d){return d[2]!=='委員会'}],['委員会',function(d){return d[2]==='委員会'}]].forEach(function(g){var ds=by[y].filter(g[1]);if(!ds.length)return;
   h+='<h4>'+g[0]+'</h4><ul>'+ds.map(function(d){return '<li><time>'+d[1].slice(5).replace('-','/')+'</time><a href="d/'+d[0]+'.html">'+gjEsc(d[3])+' '+gjEsc(d[4])+'</a></li>'}).join('')+'</ul>'});
  h+='</details>'});$('list').innerHTML=h})();
// 検索
var seq=0,groups=[],shown=0,PAGE=50;
function snippet(text,terms){var n=gjNorm(text),p=-1;terms.forEach(function(t){var i=n.indexOf(t);if(i>=0&&(p<0||i<p))p=i});if(p<0)p=0;var s=Math.max(0,p-40),e=Math.min(text.length,p+110);return (s>0?'…':'')+gjMark(text.slice(s,e).replace(/\n/g,' '),terms)+(e<text.length?'…':'')}
function render(terms,qs){var h='';for(var i=shown;i<Math.min(groups.length,shown+PAGE);i++){var g=groups[i],d=g.d;
 h+='<div class="hit"><h3><small>'+d.d+'</small><a href="d/'+d.f+'.html?q='+qs+'">'+gjEsc(d.t)+' '+gjEsc(d.n)+'</a></h3>';
 g.u.slice(0,3).forEach(function(u){h+='<a class="sn" href="d/'+d.f+'.html?q='+qs+'#u'+u[0]+'"><b>'+gjEsc(u[1]||'記載事項')+'</b>'+snippet(u[2],terms)+'</a>'});
 if(g.u.length>3)h+='<a class="rest" href="d/'+d.f+'.html?q='+qs+'">この会議録でほか'+(g.u.length-3)+'件の発言が一致</a>';h+='</div>'}
 shown=Math.min(groups.length,shown+PAGE);$('results').insertAdjacentHTML('beforeend',h);$('more').hidden=shown>=groups.length}
function run(){var my=++seq,q=$('q').value.trim(),terms=gjTerms(q),sp=gjNorm($('s').value.trim()),k=$('k').value;
 var a=+$('y0').value,b=+$('y1').value,lo=Math.min(a,b),hi=Math.max(a,b);
 var p=new URLSearchParams();if(q)p.set('q',q);if(k)p.set('k',k);if(sp)p.set('s',$('s').value.trim());if(years.length&&(lo!==years[years.length-1]||hi!==years[0])){p.set('y0',lo);p.set('y1',hi)}
 history.replaceState(null,'',p.toString()?'?'+p:location.pathname);
 groups=[];shown=0;$('results').innerHTML='';$('more').hidden=true;$('browse').hidden=!!(terms.length||sp);
 if(!terms.length&&!sp){$('status').textContent='';return}
 var qs=encodeURIComponent(q),ys=years.filter(function(y){return y>=lo&&y<=hi}),nu=0,first=true;
 (function next(i){if(my!==seq)return;if(i>=ys.length){$('status').textContent=groups.length?groups.length+'件の会議録、'+nu+'件の発言が一致しました。':'一致する発言は見つかりませんでした。';return}
  $('status').textContent=ys[i]+'年を検索中…'+(nu?'('+nu+'件)':'');
  load(ys[i]).then(function(){if(my!==seq)return;var before=groups.length;G.chunks[ys[i]].forEach(function(d){if(k==='h'&&d.k==='委員会')return;if(k==='c'&&d.k!=='委員会')return;var us=[];
    d.u.forEach(function(u){if(u[3]===undefined){u[3]=gjNorm(u[2]);u[4]=gjNorm(u[1])}if(sp&&u[4].indexOf(sp)<0)return;for(var j=0;j<terms.length;j++)if(u[3].indexOf(terms[j])<0)return;us.push(u)});
    if(us.length){groups.push({d:d,u:us});nu+=us.length}});
   if(shown<PAGE&&groups.length>before)render(terms,qs);else $('more').hidden=shown>=groups.length;
   setTimeout(function(){next(i+1)},0)},function(){$('status').textContent=ys[i]+'年のデータを読み込めませんでした。';})})(0);
 $('more').onclick=function(){render(terms,qs)}}
$('f').addEventListener('submit',function(e){e.preventDefault();run()});
['k','y0','y1'].forEach(function(id){$(id).addEventListener('change',run)});
var P=new URLSearchParams(location.search);if(P.get('q'))$('q').value=P.get('q');if(P.get('k'))$('k').value=P.get('k');if(P.get('s'))$('s').value=P.get('s');if(P.get('y0'))$('y0').value=P.get('y0');if(P.get('y1'))$('y1').value=P.get('y1');
if(P.get('q')||P.get('s'))run();
})();
"""


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main():
    with open(os.path.join(HERE, "index.json"), encoding="utf-8") as f:
        docs = json.load(f)
    by_year, manifest, missing, empty = {}, [], 0, []
    newest = 0.0
    for d in docs:
        path = os.path.join(RAW, f"{d['fino']}.html")
        if not os.path.exists(path):
            missing += 1
            continue
        newest = max(newest, os.path.getmtime(path))
        with open(path, "rb") as f:
            us = parse(f.read())
        if not us:
            empty.append(d["fino"])
            continue
        d["title"] = titles(d)
        write(os.path.join(SITE, "d", f"{d['fino']}.html"), render_doc(d, us))
        by_year.setdefault(d["date"][:4], []).append(
            {"f": d["fino"], "t": d["title"], "n": d["no"], "d": d["date"], "k": d["kind"],
             "u": [[u["id"], u["sp"], u["tx"]] for u in us]}
        )
        manifest.append([d["fino"], d["date"], d["kind"], d["title"], d["no"]])
    for y, ds in by_year.items():
        write(os.path.join(SITE, "s", f"{y}.js"),
              f"__gj.add({y}," + json.dumps(ds, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ");")
    # CI では checkout で mtime が失われるので、ワークフローから取得日を渡す
    built = os.environ.get("BUILT_DATE") or (datetime.date.fromtimestamp(newest).isoformat() if newest else "")
    m = {"years": sorted(int(y) for y in by_year), "docs": manifest, "built": built}
    write(os.path.join(SITE, "s", "manifest.js"),
          "window.__gj=window.__gj||{};__gj.manifest=" + json.dumps(m, ensure_ascii=False, separators=(",", ":")) + ";")
    write(os.path.join(SITE, "index.html"), INDEX_HTML.replace("__SITE__", E(SITE_NAME)).replace("__TOP__", OFFICIAL_TOP))
    write(os.path.join(SITE, "app.css"), APP_CSS)
    write(os.path.join(SITE, "app.js"), APP_JS)
    write(os.path.join(SITE, "doc.js"), DOC_JS)
    print(f"生成: {len(manifest)}件 / 未取得: {missing}件 / 本文なし: {len(empty)}件 {empty[:10]}")
    print(f"→ {os.path.join(SITE, 'index.html')} を開いてください")


if __name__ == "__main__":
    sys.exit(main())
