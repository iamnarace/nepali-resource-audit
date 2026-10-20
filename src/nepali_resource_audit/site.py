# ruff: noqa: E501
"""Static, dependency-free, offline-capable site for browsing an audit catalogue.

All data is inserted with ``textContent`` (never ``innerHTML``) because it originates from
third-party Markdown. Only http(s) links can reach the catalogue (see extract.py).
"""

from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="no-referrer">
<title>Nepali resource audit</title>
<style>
:root{--bg:#fbfaf7;--fg:#1c1b19;--muted:#5e5b55;--card:#fff;--line:#dcd8cf;--accent:#9b1c31;--ok:#1d6b3a;--warn:#8a5a00;
 --chip:#f0ede6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#171614;--fg:#eceae4;--muted:#a8a49b;--card:#211f1c;
 --line:#38352f;--accent:#ee8a9a;--ok:#6fcf93;--warn:#e6b450;--chip:#2c2925}}
:root[data-theme="dark"]{--bg:#171614;--fg:#eceae4;--muted:#a8a49b;--card:#211f1c;--line:#38352f;--accent:#ee8a9a;--ok:#6fcf93;
 --warn:#e6b450;--chip:#2c2925}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans Devanagari",sans-serif}
.wrap{max-width:1100px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:1.6rem;margin:0 0 4px}
.sub{color:var(--muted);margin:0 0 20px}
.stats{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 20px;padding:0;list-style:none}
.stats li{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:150px}
.stats b{display:block;font-size:1.4rem;color:var(--accent)}
.controls{display:grid;grid-template-columns:2fr repeat(4,1fr);gap:10px;margin-bottom:12px}
label{display:block;font-size:.8rem;color:var(--muted);margin-bottom:2px}
input,select{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font:inherit}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.count{color:var(--muted);margin:8px 0}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.8rem;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
.chip{display:inline-block;background:var(--chip);border-radius:999px;padding:1px 9px;margin:1px 3px 1px 0;font-size:.8rem}
.none{color:var(--warn)} .has{color:var(--ok)}
a{color:var(--accent);word-break:break-all}
.note{font-size:.85rem;color:var(--muted);margin-top:24px;border-top:1px solid var(--line);padding-top:12px}
@media (max-width:760px){
 .controls{grid-template-columns:1fr 1fr}.controls>div:first-child{grid-column:1/-1}
 table,thead,tbody,tr,th,td{display:block}thead{position:absolute;left:-9999px}
 tr{border-bottom:1px solid var(--line);padding:8px 0}td{border:0;padding:3px 12px}
 td::before{content:attr(data-h) ": ";color:var(--muted);font-size:.8rem}}
</style>
</head>
<body>
<main class="wrap">
<h1>Nepali resource audit</h1>
<p class="sub" id="sub"></p>
<ul class="stats" id="stats"></ul>
<div class="controls">
 <div><label for="q">Search name or URL</label><input id="q" type="search" autocomplete="off"></div>
 <div><label for="src">Found in list</label><select id="src"><option value="">any</option></select></div>
 <div><label for="kind">Kind</label><select id="kind"><option value="">any</option></select></div>
 <div><label for="lic">Licence hint in list</label><select id="lic"><option value="">any</option>
   <option value="has">has a hint</option><option value="none">no hint</option></select></div>
 <div><label for="multi">Overlap</label><select id="multi"><option value="">any</option>
   <option value="2">in 2+ lists</option><option value="3">in 3+ lists</option></select></div>
</div>
<p class="count" id="count" role="status" aria-live="polite"></p>
<table>
<thead><tr><th>Resource</th><th>Kind</th><th>Found in</th><th>Licence hint (list's claim)</th><th>Link</th></tr></thead>
<tbody id="rows"></tbody>
</table>
<p class="note" id="note"></p>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
(function(){
 var D=JSON.parse(document.getElementById('data').textContent);
 var E=D.entries,S=D.summary,M=D.meta;
 function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e}
 document.getElementById('sub').textContent='Built from '+S.sources.join(', ')+' \u2014 generated '+M.generated+'. Entries are links found in those lists, not endorsements.';
 var stats=[[S.unique_resources,'unique resources'],[S.in_2_or_more_sources,'in 2+ lists'],[S.without_license_hint,'with no licence hint']];
 stats.forEach(function(s){var li=el('li');li.appendChild(el('b',null,s[0]));li.appendChild(document.createTextNode(s[1]));document.getElementById('stats').appendChild(li)});
 function fill(id,vals){var s=document.getElementById(id);vals.forEach(function(v){var o=el('option',null,v);o.value=v;s.appendChild(o)})}
 fill('src',S.sources);fill('kind',Object.keys(S.by_kind));
 var q=document.getElementById('q'),src=document.getElementById('src'),kind=document.getElementById('kind'),
  lic=document.getElementById('lic'),multi=document.getElementById('multi'),rows=document.getElementById('rows'),count=document.getElementById('count');
 function render(){
  var t=q.value.trim().toLowerCase(),n=0,LIMIT=300;
  rows.textContent='';
  E.forEach(function(e){
   if(src.value&&e.sources.indexOf(src.value)<0)return;
   if(kind.value&&e.kind!==kind.value)return;
   if(lic.value==='has'&&!e.license_hints.length)return;
   if(lic.value==='none'&&e.license_hints.length)return;
   if(multi.value&&e.sources.length<+multi.value)return;
   var name=(e.names[0]||e.id);
   if(t&&(name+' '+e.id).toLowerCase().indexOf(t)<0)return;
   n++;if(n>LIMIT)return;
   var tr=el('tr');
   tr.appendChild(Object.assign(el('td',null,name),{}));tr.lastChild.setAttribute('data-h','Resource');
   var td=el('td',null,e.kind);td.setAttribute('data-h','Kind');tr.appendChild(td);
   td=el('td');td.setAttribute('data-h','Found in');e.sources.forEach(function(s){td.appendChild(el('span','chip',s))});tr.appendChild(td);
   td=el('td',e.license_hints.length?'has':'none',e.license_hints.length?e.license_hints.join(', '):'none stated');td.setAttribute('data-h','Licence hint');tr.appendChild(td);
   td=el('td');td.setAttribute('data-h','Link');var a=el('a',null,e.id);a.href=e.url;a.rel='noopener noreferrer';a.target='_blank';td.appendChild(a);tr.appendChild(td);
   rows.appendChild(tr)});
  count.textContent=n+' resource'+(n===1?'':'s')+(n>LIMIT?' (showing first '+LIMIT+')':'');
 }
 [q,src,kind,lic,multi].forEach(function(c){c.addEventListener('input',render)});
 document.getElementById('note').textContent='Licence hints are only what the source list says on the entry\u2019s line; they are not verified. Always confirm the licence on the resource itself before reuse.';
 render();
})();
</script>
</body>
</html>
"""


def write_site(out_dir: str | Path, entries: list[dict], summary: dict, meta: dict) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    blob = json.dumps({"entries": entries, "summary": summary, "meta": meta}, ensure_ascii=False)
    blob = blob.replace("</", "<\\/").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    path = out / "index.html"
    path.write_text(TEMPLATE.replace("__DATA__", blob), encoding="utf-8")
    return path
