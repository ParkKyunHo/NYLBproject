from __future__ import annotations

import json

from nylb.core.schema import ScanResult
from nylb.report.board import build_board
from nylb.report.chart_data import extract_chart_data  # noqa: F401  (re-export convenience)

# Self-contained editorial "market intelligence journal" board.
# Zero external dependencies (no CDN fonts/JS) — local serif/sans stacks only.
_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NYLB 시장 인텔리전스</title>
<style>
  :root{
    --paper:#f4eee1; --panel:#fffdf6; --panel2:#faf4e6;
    --ink:#241b10; --ink2:#4c4133; --muted:#8d7d67; --faint:#b3a48d;
    --hair:#e5dac4; --hair2:#d6c9ad;
    --esp:#201710; --esp2:#2e2417; --esp-line:#4a3a26;
    --brass:#a8772a; --brass2:#c89243; --copper:#b85c2e; --copper2:#d97b2f;
    --up:#2e7d4f; --down:#bf4934; --steady:#c2912e;
    --core:#33598f; --core2:#5b82b5;
    --serif:"Bodoni MT","Didot","Playfair Display",Georgia,"Times New Roman",serif;
    --sans:"Pretendard Variable",Pretendard,"Apple SD Gothic Neo","Malgun Gothic","맑은 고딕",sans-serif;
  }
  *{box-sizing:border-box}
  html{scroll-behavior:smooth}
  body{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);
    line-height:1.62;-webkit-font-smoothing:antialiased;
    background-image:radial-gradient(1200px 500px at 70% -10%,rgba(200,146,67,.10),transparent 60%),
      url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='2'/%3E%3CfeColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .035 0'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)'/%3E%3C/svg%3E")}
  .num{font-family:var(--serif);font-variant-numeric:tabular-nums lining-nums}
  .caps{font-size:10.5px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
  .wrap{max-width:1120px;margin:0 auto;padding:0 24px 80px}

  /* ── sticky nav ─────────────────────────────────────── */
  .topnav{position:sticky;top:0;z-index:50;background:rgba(244,238,225,.92);
    backdrop-filter:blur(8px);border-bottom:1px solid var(--hair2);
    display:flex;align-items:center;gap:14px;padding:9px 24px;margin:0 -24px}
  .topnav .nv-brand{font-family:var(--serif);font-weight:700;font-size:17px;letter-spacing:.04em;white-space:nowrap}
  .topnav .nv-links{display:flex;gap:2px;flex-wrap:wrap;margin-left:auto}
  .topnav a{font-size:11px;font-weight:700;letter-spacing:.08em;color:var(--ink2);
    text-decoration:none;padding:5px 9px;border-radius:7px;white-space:nowrap}
  .topnav a:hover{background:var(--panel2);color:var(--copper)}
  .tabs{display:flex;gap:6px}
  .tab{background:transparent;border:1px solid var(--hair2);border-radius:999px;padding:6px 15px;
    font-size:13px;font-weight:700;color:var(--ink2);cursor:pointer;font-family:inherit;transition:all .18s}
  .tab:hover{border-color:var(--brass)}
  .tab.on{background:var(--esp);color:#f3e8d2;border-color:var(--esp)}

  /* ── masthead ───────────────────────────────────────── */
  .mast{margin-top:26px;background:linear-gradient(160deg,var(--esp) 0%,var(--esp2) 100%);
    color:#efe4cd;border-radius:20px;padding:34px 38px 0;overflow:hidden;position:relative;
    box-shadow:0 18px 50px -18px rgba(32,23,16,.55)}
  .mast::after{content:"";position:absolute;inset:0;pointer-events:none;
    background:radial-gradient(700px 280px at 85% 0%,rgba(200,146,67,.16),transparent 70%)}
  .mast-top{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;flex-wrap:wrap}
  .wordmark{font-family:var(--serif);font-size:64px;line-height:.95;font-weight:700;color:#f6ecd8;letter-spacing:.01em}
  .wordmark i{font-style:italic;color:var(--brass2)}
  .wordsub{margin-top:10px;font-size:11.5px;font-weight:800;letter-spacing:.34em;color:#bba887;text-transform:uppercase}
  .colophon{text-align:right;font-size:12px;color:#a8946f;line-height:1.9}
  .colophon b{color:#e8d9b8;font-weight:700}
  .mast-rule{height:1px;background:linear-gradient(90deg,var(--brass2),rgba(200,146,67,.15));margin:26px 0 0}
  .statband{display:grid;grid-template-columns:repeat(4,1fr);position:relative}
  .stat{padding:22px 26px 24px;border-left:1px solid var(--esp-line)}
  .stat:first-child{border-left:0;padding-left:2px}
  .stat .sl{font-size:10.5px;font-weight:800;letter-spacing:.18em;color:#9d8a66;text-transform:uppercase}
  .stat .sv{font-family:var(--serif);font-size:34px;line-height:1.15;margin-top:6px;color:#f6ecd8;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .stat .sv small{font-size:16px;color:#bba887;font-family:var(--sans);font-weight:600}
  .stat .ss{font-size:11.5px;color:#a8946f;margin-top:3px}
  .mast-note{border-top:1px solid var(--esp-line);margin:0 -38px;padding:13px 38px;font-size:12px;
    color:#a8946f;display:flex;justify-content:space-between;gap:18px;flex-wrap:wrap}
  .mast-note b{color:#e8d9b8}

  /* ── sections ───────────────────────────────────────── */
  section{margin-top:54px;opacity:0;animation:rise .6s cubic-bezier(.2,.7,.25,1) forwards}
  @keyframes rise{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
  .shead{display:flex;align-items:baseline;gap:14px;border-bottom:2px solid var(--ink);padding-bottom:10px}
  .sno{font-family:var(--serif);font-style:italic;font-size:21px;color:var(--copper);min-width:54px}
  .shead h2{margin:0;font-size:21px;font-weight:800;letter-spacing:-.01em}
  .shead .ssub{margin-left:auto;font-size:12px;color:var(--muted);text-align:right;max-width:46%}
  .sbody{margin-top:18px}

  .grid{display:grid;gap:14px}
  .g3{grid-template-columns:repeat(3,1fr)} .g2{grid-template-columns:repeat(2,1fr)}
  .card{background:var(--panel);border:1px solid var(--hair);border-radius:14px;padding:18px 20px;
    box-shadow:0 1px 0 rgba(36,27,16,.03)}
  .note{font-size:12px;color:var(--muted);border-top:1px dashed var(--hair2);padding-top:10px;margin-top:14px}

  .chip{display:inline-block;font-size:10.5px;font-weight:800;letter-spacing:.1em;padding:3px 9px;
    border-radius:999px;border:1px solid var(--hair2);color:var(--muted);text-transform:uppercase;vertical-align:middle}
  .mom{display:inline-flex;align-items:center;gap:4px;font-size:11px;font-weight:800;padding:3px 10px;
    border-radius:999px;color:#fff;white-space:nowrap}
  .mom.up{background:var(--up)} .mom.down{background:var(--down)} .mom.steady{background:var(--steady)}
  .badge{display:inline-block;font-size:11px;font-weight:800;padding:3px 10px;border-radius:999px;vertical-align:middle}
  .badge.entering{background:var(--copper);color:#fff}
  .badge.in_season{background:var(--up);color:#fff}
  .badge.off{background:transparent;color:var(--muted);border:1px solid var(--hair2)}
  .badge.no_data{background:transparent;color:var(--faint);border:1px dashed var(--hair2)}

  /* opportunity cards */
  .opp{display:grid;grid-template-columns:86px 1fr;gap:18px;background:var(--panel);
    border:1px solid var(--hair);border-radius:16px;padding:20px 22px;position:relative;
    transition:transform .18s,box-shadow .18s}
  .opp:hover{transform:translateY(-3px);box-shadow:0 14px 34px -16px rgba(36,27,16,.35)}
  .opp .rankno{font-family:var(--serif);font-style:italic;font-size:13px;color:var(--muted);text-align:center;margin-top:7px}
  .opp h3{margin:0;font-size:18px;font-weight:800;display:flex;align-items:center;gap:9px;flex-wrap:wrap}
  .opp .cap{font-size:12.5px;color:var(--ink2);margin:5px 0 0}
  .fbars{margin-top:11px;display:grid;gap:5px}
  .fb{display:grid;grid-template-columns:74px 1fr 60px;align-items:center;gap:9px;font-size:11px;color:var(--muted)}
  .fb .tr{height:5px;border-radius:3px;background:var(--panel2);overflow:hidden}
  .fb .tr i{display:block;height:100%;border-radius:3px;background:linear-gradient(90deg,var(--brass),var(--brass2));
    transform-origin:left;animation:grow .8s cubic-bezier(.2,.7,.25,1) both}
  .fb .pt{text-align:right;font-weight:700;color:var(--ink2)}
  @keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}
  .sstrip{display:grid;grid-template-columns:repeat(12,1fr);gap:3px;margin-top:11px}
  .sstrip .mc{height:16px;border-radius:4px;background:var(--panel2);position:relative}
  .sstrip .mc.now{outline:2px solid var(--ink);outline-offset:1px}
  .sstrip .mc .pk{position:absolute;top:-4px;left:50%;width:4px;height:4px;border-radius:50%;
    background:var(--copper);transform:translateX(-50%)}
  .slegend{display:flex;justify-content:space-between;font-size:9.5px;color:var(--faint);margin-top:3px}

  /* season calendar */
  .cal-head{display:grid;grid-template-columns:150px 120px 1fr 130px;gap:14px;align-items:center;
    padding:4px 8px;font-size:10.5px;color:var(--faint);letter-spacing:.1em;font-weight:800}
  .cal-months{display:grid;grid-template-columns:repeat(12,1fr);gap:3px;text-align:center}
  .cal-row{display:grid;grid-template-columns:150px 120px 1fr 130px;gap:14px;align-items:center;
    background:var(--panel);border:1px solid var(--hair);border-radius:12px;padding:11px 8px 11px 14px;margin-top:7px}
  .cal-row .term{font-weight:800;font-size:14px}
  .cal-row .term .chip{margin-left:7px}
  .cal-row .sstrip{margin-top:0}
  .cal-row .meta2{font-size:11px;color:var(--muted);text-align:right;padding-right:8px;line-height:1.5}

  /* movers / signal cards */
  .mvc{background:var(--panel);border:1px solid var(--hair);border-radius:14px;padding:16px 18px;
    transition:transform .18s,box-shadow .18s}
  .mvc:hover{transform:translateY(-3px);box-shadow:0 14px 34px -16px rgba(36,27,16,.3)}
  .mvc h3{margin:0;font-size:15.5px;font-weight:800;display:flex;justify-content:space-between;align-items:center;gap:8px}
  .mvc .v{font-family:var(--serif);font-size:26px;margin-top:2px}
  .mvc .v small{font-size:13px;color:var(--muted);font-family:var(--sans)}
  .mvc .cap{font-size:12px;color:var(--ink2);margin-top:4px}
  .newsbx{margin-top:9px;border-top:1px dashed var(--hair);padding-top:7px}
  .newsbx a{display:block;font-size:11.5px;color:var(--core);text-decoration:none;margin-top:3px}
  .newsbx a:hover{color:var(--copper)}

  /* ranking bars */
  .rrow{display:grid;grid-template-columns:150px 1fr 46px;align-items:center;gap:12px;margin:8px 0}
  .rrow .rt{font-weight:700;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .rrow .rt.core{color:var(--core)}
  .rbar{height:14px;border-radius:7px;background:var(--panel2);overflow:hidden}
  .rbar i{display:block;height:100%;border-radius:7px;transform-origin:left;
    animation:grow .9s cubic-bezier(.2,.7,.25,1) both;
    background:linear-gradient(90deg,var(--brass),var(--brass2))}
  .rbar i.core{background:linear-gradient(90deg,var(--core),var(--core2))}
  .rrow .rv{font-family:var(--serif);font-size:15px;text-align:right}

  /* chart */
  .chartcard{padding:22px 20px 12px;position:relative}
  .legend{display:flex;gap:18px;flex-wrap:wrap;margin:8px 6px 0;font-size:12.5px;color:var(--ink2)}
  .legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px;vertical-align:middle}
  .ctip{position:absolute;pointer-events:none;background:var(--esp);color:#efe4cd;border-radius:9px;
    padding:8px 12px;font-size:11.5px;line-height:1.7;box-shadow:0 10px 26px -8px rgba(0,0,0,.4);
    opacity:0;transition:opacity .12s;z-index:5;white-space:nowrap}
  .ctip b{font-family:var(--serif);font-size:12.5px}

  table{width:100%;border-collapse:collapse;font-size:13.5px}
  th,td{text-align:left;padding:11px 12px;border-bottom:1px solid var(--hair);vertical-align:top}
  th{font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.12em}
  td .num{font-size:15px}
  tr:last-child td{border-bottom:0}

  .quar{background:repeating-linear-gradient(-45deg,var(--panel),var(--panel) 12px,var(--panel2) 12px,var(--panel2) 24px);
    border:1px dashed var(--hair2);border-radius:14px;padding:18px 20px}
  ul.plain{margin:0;padding-left:20px;font-size:12.8px;color:var(--ink2)}
  ul.plain li{margin-bottom:6px}
  .cloud{display:flex;flex-wrap:wrap;gap:8px}
  .cloud .tagc{font-size:12.5px;font-weight:700;background:var(--panel);border:1px solid var(--hair2);
    border-radius:999px;padding:6px 14px;color:var(--ink2)}
  .cloud .tagc b{color:var(--copper)}

  .foot{margin-top:64px;border-top:2px solid var(--ink);padding-top:18px;font-size:12px;color:var(--muted);
    display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
  .src{display:flex;gap:8px;flex-wrap:wrap}
  .pill{font-size:11px;font-weight:700;padding:4px 11px;border-radius:999px;border:1px solid var(--hair2)}
  .pill.on{background:#ecf3ea;color:var(--up);border-color:#c8dcc8}
  .pill.off{background:transparent;color:var(--faint)}

  @media(max-width:920px){
    .g3{grid-template-columns:repeat(2,1fr)} .statband{grid-template-columns:repeat(2,1fr)}
    .stat{border-left:0;padding-left:2px}
    .cal-head{display:none}
    .cal-row{grid-template-columns:1fr;gap:8px}
    .cal-row .meta2{text-align:left}
    .wordmark{font-size:44px}
    .topnav .nv-links{display:none}
  }
  @media(max-width:620px){.g3,.g2{grid-template-columns:1fr}.opp{grid-template-columns:1fr}}
  @media print{
    @page{size:A4;margin:9mm}
    .topnav,#nylb-run,#nylb-actions{display:none!important}
    body{background:#fff;-webkit-print-color-adjust:exact;print-color-adjust:exact}
    .wrap{max-width:100%;padding:0 2mm}
    section{animation:none;opacity:1}
    .mast{box-shadow:none}
    .card,.opp,.mvc,.cal-row,.quar{break-inside:avoid}
    .shead{break-after:avoid}
    .opp:hover,.mvc:hover{transform:none;box-shadow:none}
    .ctip{display:none}
  }
</style>
</head>
<body>
<div class="wrap" id="app"></div>

<script>
const LENSES = __DATA__;
const MONTH_KO=["1월","2월","3월","4월","5월","6월","7월","8월","9월","10월","11월","12월"];
const SEASON_LABEL={entering:"시즌 진입 임박",in_season:"지금 시즌",off:"비수기",no_data:"데이터 부족"};
const ARROW={up:"▲",down:"▼",steady:"→"}, DCOL={up:"var(--up)",down:"var(--down)",steady:"var(--steady)"};
function h(tag, attrs, kids){
  const e=document.createElement(tag);
  if(attrs) for(const k in attrs){ if(k==="class")e.className=attrs[k]; else if(k==="html")e.innerHTML=attrs[k]; else e.setAttribute(k,attrs[k]); }
  if(kids!=null){ (Array.isArray(kids)?kids:[kids]).forEach(c=>{ if(c==null)return; e.appendChild(typeof c==="string"?document.createTextNode(c):c); }); }
  return e;
}
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function fmt(n){return (Math.round(n*10)/10).toLocaleString();}
const NS="http://www.w3.org/2000/svg";
function sv(tag,a,kids){const e=document.createElementNS(NS,tag);for(const k in (a||{}))e.setAttribute(k,a[k]);
  if(kids)kids.forEach(c=>c&&e.appendChild(c));return e;}

/* sparkline: gradient area + line */
let _gid=0;
function spark(values,color,w,h2){
  if(!values||values.length<2)return null;
  w=w||120;h2=h2||34;const pad=2;
  const mn=Math.min.apply(null,values),mx=Math.max.apply(null,values),span=(mx-mn)||1;
  const X=i=>pad+(w-2*pad)*(i/(values.length-1));
  const Y=v=>pad+(h2-2*pad)*(1-(v-mn)/span);
  const pts=values.map((v,i)=>X(i)+","+Y(v)).join(" ");
  const id="sg"+(_gid++);
  const svg=sv("svg",{viewBox:"0 0 "+w+" "+h2,width:w,height:h2,style:"display:block"});
  const grad=sv("linearGradient",{id:id,x1:0,y1:0,x2:0,y2:1});
  grad.appendChild(sv("stop",{offset:"0%","stop-color":color,"stop-opacity":".30"}));
  grad.appendChild(sv("stop",{offset:"100%","stop-color":color,"stop-opacity":"0"}));
  svg.appendChild(sv("defs",null,[grad]));
  svg.appendChild(sv("polygon",{points:pad+","+(h2-pad)+" "+pts+" "+X(values.length-1)+","+(h2-pad),fill:"url(#"+id+")"}));
  svg.appendChild(sv("polyline",{points:pts,fill:"none",stroke:color,"stroke-width":2,"stroke-linejoin":"round","stroke-linecap":"round"}));
  const lx=X(values.length-1),ly=Y(values[values.length-1]);
  svg.appendChild(sv("circle",{cx:lx,cy:ly,r:2.6,fill:color}));
  return svg;
}

/* score donut */
function donut(score){
  const r=26,c=2*Math.PI*r,sz=68;
  const col=score>=70?"var(--copper)":score>=50?"var(--brass)":"var(--muted)";
  const svg=sv("svg",{viewBox:"0 0 "+sz+" "+sz,width:sz,height:sz});
  svg.appendChild(sv("circle",{cx:34,cy:34,r:r,fill:"none",stroke:"var(--panel2)","stroke-width":7}));
  svg.appendChild(sv("circle",{cx:34,cy:34,r:r,fill:"none",stroke:col,"stroke-width":7,
    "stroke-linecap":"round","stroke-dasharray":(c*score/100)+" "+c,transform:"rotate(-90 34 34)"}));
  const t=sv("text",{x:34,y:40,"text-anchor":"middle","font-size":"19",fill:"var(--ink)",
    style:"font-family:var(--serif)"});
  t.textContent=Math.round(score);
  svg.appendChild(t);
  return svg;
}

/* 12-cell season strip. profile keys arrive as strings via JSON. */
function seasonStrip(se,monthNow){
  if(!se||!se.profile||!Object.keys(se.profile).length)return null;
  const wrap=h("div",{class:"sstrip"});
  for(let m=1;m<=12;m++){
    const idx=Number(se.profile[m]!=null?se.profile[m]:se.profile[String(m)]);
    const cell=h("div",{class:"mc"+(m===monthNow?" now":""),
      title:MONTH_KO[m-1]+(isNaN(idx)?" — 데이터 없음":" · 시즌지수 "+Math.round(idx))});
    if(!isNaN(idx)){
      const a=Math.max(0,Math.min(1,(idx-60)/140));
      cell.style.background="rgba(184,92,46,"+(a*0.92).toFixed(2)+")";
      if(a<0.04)cell.style.background="var(--panel2)";
    }
    if((se.peak_months||[]).indexOf(m)>=0)cell.appendChild(h("span",{class:"pk"}));
    wrap.appendChild(cell);
  }
  return wrap;
}
function seasonBadge(se){
  if(!se)return null;
  const st=se.status||"no_data";
  const b=h("span",{class:"badge "+st},SEASON_LABEL[st]||st);
  if(se.low_coverage&&st!=="no_data")b.title="표본 12개월 미만 — 저신뢰";
  return b;
}
function momChip(c){return h("span",{class:"mom "+c.direction},ARROW[c.direction]+" "+(c.momentum>=0?"+":"")+fmt(c.momentum));}
function buzzChip(c){
  const b=c.buzz; if(!b||(b.youtube+b.naver)<1)return null;
  const parts=[]; if(b.youtube)parts.push("▶ 유튜브 "+b.youtube);
  if(b.naver)parts.push("✍ 블로그·검색 "+b.naver);
  return h("span",{class:"chip",title:"최근 수집분에서 이 용어를 언급한 콘텐츠 수"
    +(b.views?(" · 유튜브 조회 합계 "+b.views.toLocaleString()):"")},parts.join(" · "));}
function deltaRankChip(DATA,term){
  const d=DATA.delta; if(!d||!d.rank_moves)return null;
  const m=d.rank_moves[term]; if(!m)return null;
  if(m.new)return h("span",{class:"badge entering",title:"전회("+d.prev_date+") 미등장"},"NEW");
  if(m.move>0)return h("span",{style:"color:var(--up);font-weight:800;font-size:11.5px",
    title:"전회 "+m.prev+"위 → "+m.cur+"위"},"▲"+m.move);
  if(m.move<0)return h("span",{style:"color:var(--down);font-weight:800;font-size:11.5px",
    title:"전회 "+m.prev+"위 → "+m.cur+"위"},"▼"+(-m.move));
  return h("span",{style:"color:var(--faint);font-size:11.5px"},"—");}
function ageRow(DATA,term){
  const at=(DATA.age_trends||{})[term]; if(!at)return null;
  const row=h("div",{style:"margin-top:9px;display:flex;gap:6px;flex-wrap:wrap;align-items:center"});
  row.appendChild(h("span",{class:"caps",style:"font-size:9.5px"},"연령 추세"));
  ["10대","20대","30대","40대","50+"].forEach(b=>{const t=at[b]; if(!t)return;
    row.appendChild(h("span",{class:"chip",style:"color:"+DCOL[t.direction],
      title:b+" 검색 30일 모멘텀 "+(t.momentum>=0?"+":"")+t.momentum+" (연령 간 절대량 비교 불가 — 추세만)"},
      b+" "+ARROW[t.direction]));});
  return row.childNodes.length>1?row:null;}
function newsLinks(DATA,term){
  const nx=(DATA.news_context||{})[term]||[]; if(!nx.length)return null;
  const bx=h("div",{class:"newsbx"});
  bx.appendChild(h("div",{class:"caps",style:"font-size:9.5px"},"관련 뉴스"));
  nx.slice(0,3).forEach(nw=>bx.appendChild(h("a",{href:nw.link,target:"_blank",rel:"noopener noreferrer"},"— "+nw.title)));
  return bx;
}

let _secNo=0;
function sect(id,title,sub){
  _secNo++;
  const s=h("section",{id:id,style:"animation-delay:"+Math.min(_secNo*55,400)+"ms"});
  const head=h("div",{class:"shead"});
  head.appendChild(h("span",{class:"sno"},"No."+String(_secNo).padStart(2,"0")));
  head.appendChild(h("h2",null,title));
  if(sub)head.appendChild(h("span",{class:"ssub"},sub));
  s.appendChild(head);
  return s;
}
function body(s){const b=h("div",{class:"sbody"});s.appendChild(b);return b;}

function renderBoard(DATA, app){
const M=DATA.meta, HL=DATA.headline;
const monthNow=parseInt(M.collected.slice(5,7),10);
document.title="NYLB 시장 인텔리전스 · "+M.collected+" ("+M.lens+")";
_secNo=0;

/* ── MASTHEAD ── */
const mast=h("header",{class:"mast"});
const top=h("div",{class:"mast-top"});
const wm=h("div");
wm.appendChild(h("div",{class:"wordmark",html:"NYLB<i>.</i>"}));
wm.appendChild(h("div",{class:"wordsub"},"Market Intelligence · 의사결정 상황판"));
top.appendChild(wm);
const chanStr=Object.entries(M.counts).map(([s,n])=>s+" "+n).join(" · ");
top.appendChild(h("div",{class:"colophon",html:
  "<b>"+esc(M.brand)+"</b><br>발행 "+esc(M.collected)+" · 렌즈 <b>"+esc(M.lens)+"</b><br>"+
  "스캔 "+esc(M.run_id)+"<br>"+esc(chanStr)}));
mast.appendChild(top);
mast.appendChild(h("div",{class:"mast-rule"}));

const opp1=(DATA.opportunities||[])[0];
const mv=HL.biggest_mover;
const band=h("div",{class:"statband"});
function stat(lab,valNode,ss){const d=h("div",{class:"stat"});d.appendChild(h("div",{class:"sl"},lab));
  d.appendChild(valNode);if(ss)d.appendChild(h("div",{class:"ss"},ss));return d;}
band.appendChild(stat("총 수집",h("div",{class:"sv"},[String(M.items),h("small",null," 건")]),
  Object.keys(M.counts).length+"개 채널 · 실패 "+M.errors+" · 제외 "+HL.n_dropped));
band.appendChild(stat("검색 관심 1위",h("div",{class:"sv"},HL.strongest_signal||"—"),"제품 검색 관심도 최상위"));
band.appendChild(stat("최대 모멘텀",h("div",{class:"sv",style:mv?("color:"+(mv.momentum>=0?"#7fc89a":"#e09b8a")):""},
  mv?mv.term:"—"),mv?((mv.momentum>=0?"▲ +":"▼ ")+fmt(mv.momentum)+" (최근 3일 vs 이전)"):""));
band.appendChild(stat("기회 점수 1위",h("div",{class:"sv"},opp1?opp1.term:"—"),
  opp1?("점수 "+Math.round(opp1.opportunity.score)+"/100 · 공식 공개 합산"):"월별 데이터 수집 후 표시"));
mast.appendChild(band);
mast.appendChild(h("div",{class:"mast-note",html:
  "<span>신호는 시스템이, <b>판단은 사장님이</b> — 아래 모든 수치는 검증 마커·맥락이 붙은 관찰값입니다. 평결 없음.</span>"+
  "<span>"+(DATA.delta?("전회 "+esc(DATA.delta.prev_date)+" 대비 변화 표시 중 · "):"")+
  "결정론 자동생성 · LLM 없음 · ₩0</span>"}));
app.appendChild(mast);

/* ── No.01 신메뉴 기회 보드 ── */
(function(){const ops=DATA.opportunities||[]; if(!ops.length)return;
  const sec=sect("sec-opp","신메뉴 기회 보드","공식 공개 결정론 점수 = 관심도 30% · 30일 성장 30% · 시즌 25% · 방향 15% — 순위는 신호의 합산일 뿐, 판단은 사장님 몫");
  const g=h("div",{class:"grid g2"});
  ops.forEach((c,i)=>{
    const card=h("div",{class:"opp"});
    const left=h("div");
    left.appendChild(donut(c.opportunity.score));
    left.appendChild(h("div",{class:"rankno"},"No."+(i+1)));
    card.appendChild(left);
    const right=h("div");
    right.appendChild(h("h3",null,[document.createTextNode(c.term),
      h("span",{class:"chip"},c.category||"radar"),seasonBadge(c.season),momChip(c),buzzChip(c)]));
    const sm=((DATA.delta||{}).score_moves||{})[c.term];
    if(sm!=null)right.appendChild(h("div",{style:"font-size:11.5px;font-weight:700;margin-top:2px;color:"+(sm>=0?"var(--up)":"var(--down)")},
      "기회 점수 "+(sm>=0?"+":"")+sm+" (전회 "+(DATA.delta.prev_date||"")+" 대비)"));
    right.appendChild(h("p",{class:"cap"},c.caption));
    const fb=h("div",{class:"fbars"});
    Object.values(c.opportunity.parts).forEach((p,j)=>{
      const row=h("div",{class:"fb"});
      row.appendChild(h("span",null,p.label));
      const tr=h("div",{class:"tr"});
      tr.appendChild(h("i",{style:"width:"+p.points+"%;animation-delay:"+(j*90)+"ms"}));
      row.appendChild(tr);
      row.appendChild(h("span",{class:"pt"},Math.round(p.points)+" × "+Math.round(p.weight*100)+"%"));
      fb.appendChild(row);
    });
    right.appendChild(fb);
    const strip=seasonStrip(c.season,monthNow);
    if(strip){right.appendChild(strip);
      right.appendChild(h("div",{class:"slegend"},[h("span",null,"1월"),h("span",null,"12월")]));}
    const ar=ageRow(DATA,c.term); if(ar)right.appendChild(ar);
    if(c.pairings&&c.pairings.length)right.appendChild(h("div",
      {style:"margin-top:8px;font-size:12px;color:var(--ink2)"},
      [h("span",{class:"caps",style:"font-size:9.5px;margin-right:7px"},"조합 탐색"),
       document.createTextNode(c.pairings.join(" · ")+"  (기계 조합 — 아이디어 출발점)")]));
    const nl=newsLinks(DATA,c.term); if(nl)right.appendChild(nl);
    card.appendChild(right);
    g.appendChild(card);
  });
  const b=body(sec); b.appendChild(g);
  b.appendChild(h("div",{class:"note"},"점수 산식과 4개 부분점수를 전부 공개합니다. 시즌 25%는 다가오는 1~2개월의 시즌 지수 — 준비 리드타임을 반영한 신호이지 출시 지시가 아닙니다. 연령 추세는 연령별 검색의 30일 방향만 — 연령 간 절대 검색량 비교는 불가(척도 분리). 조합 탐색은 기계 조합 나열이며 추천이 아닙니다."));
  app.appendChild(sec);})();

/* ── No.02 시즌 캘린더 ── */
(function(){const cal=DATA.season_calendar||[]; if(!cal.length)return;
  const sec=sect("sec-season","시즌 캘린더","약 3년 네이버 월별 검색의 달력월 평균(자기 평균=100) — 진입 임박 → 지금 시즌 → 비수기 순");
  const b=body(sec);
  const head=h("div",{class:"cal-head"});
  head.appendChild(h("span",null,"제품"));head.appendChild(h("span",null,"상태"));
  const mh=h("div",{class:"cal-months"});
  for(let m=1;m<=12;m++)mh.appendChild(h("span",{style:m===monthNow?"color:var(--copper);font-weight:800":""},String(m)));
  head.appendChild(mh);head.appendChild(h("span",{style:"text-align:right"},"피크 월"));
  b.appendChild(head);
  cal.slice(0,18).forEach(e=>{
    const row=h("div",{class:"cal-row"});
    const t=h("div",{class:"term"},e.term);
    if(e.category&&e.category!=="radar")t.appendChild(h("span",{class:"chip"},e.category));
    row.appendChild(t);
    row.appendChild(h("div",null,seasonBadge(e.season)));
    row.appendChild(seasonStrip(e.season,monthNow)||h("div"));
    const peaks=(e.season.peak_months||[]).map(m=>MONTH_KO[m-1]).join(" · ")||"—";
    row.appendChild(h("div",{class:"meta2",html:
      "피크 <b>"+esc(peaks)+"</b><br>지금 "+Math.round(e.season.now_index||0)+" / 다음달 "+Math.round(e.season.next_index||0)}));
    b.appendChild(row);
  });
  if(cal.length>18)b.appendChild(h("div",{class:"note"},"외 "+(cal.length-18)+"개 — 원본 board JSON 참조."));
  b.appendChild(h("div",{class:"note"},"진한 칸 = 그 달에 검색이 몰리는 제품. ● = 피크 월, 테두리 = 이번 달. 12개월 미만 표본은 배지에 저신뢰 표시."));
  app.appendChild(sec);})();

/* ── No.03 지금 뜨는 제품 ── */
(function(){const mvs=DATA.movers||[]; if(!mvs.length)return;
  const sec=sect("sec-movers","지금 뜨는 제품","모멘텀(최근 3일 평균 − 이전 평균) 양수 상위 — 스파크라인은 최근 30일");
  const g=h("div",{class:"grid g3"});
  mvs.forEach(c=>{
    const card=h("div",{class:"mvc"});
    card.appendChild(h("h3",null,[document.createTextNode(c.term),momChip(c)]));
    const bz=buzzChip(c); if(bz)card.appendChild(h("div",{style:"margin-top:3px"},bz));
    card.appendChild(h("div",{class:"v num"},[document.createTextNode(String(Math.round(c.value))),
      h("small",null," · "+(M.anchor||"앵커")+"=100"+(c.rank?(" · "+c.rank+"위"):""))]));
    const sp=spark(c.spark,c.category==="core"?"var(--core)":"var(--copper2)",220,44);
    if(sp)card.appendChild(sp);
    card.appendChild(h("p",{class:"cap"},c.caption));
    const nl=newsLinks(DATA,c.term); if(nl)card.appendChild(nl);
    g.appendChild(card);
  });
  body(sec).appendChild(g); app.appendChild(sec);})();

/* ── No.04 제품 관심도 ── */
(function(){const rk=DATA.interest_ranking||[]; if(!rk.length)return;
  const sec=sect("sec-rank","제품 관심도","제품 검색 관심도 — "+(M.anchor||"앵커")+"의 30일 평균=100 기준, 100 초과 = "+(M.anchor||"앵커")+"보다 검색량 많음. 파랑 = 우리 코어, 황동 = 레이더");
  const card=h("div",{class:"card"});
  const maxv=Math.max.apply(null,rk.map(x=>x.interest).concat([1]));
  const shown=rk.slice(0,24);
  shown.forEach((x,i)=>{
    const row=h("div",{class:"rrow"});
    const dch=deltaRankChip(DATA,x.term);
    row.appendChild(h("div",{class:"rt"+(x.core?" core":""),
      style:"display:flex;align-items:center;gap:6px"},
      [document.createTextNode((x.core?"★ ":"")+x.term),dch]));
    const bar=h("div",{class:"rbar"});
    bar.appendChild(h("i",{class:x.core?"core":"",style:"width:"+(x.interest/maxv*100)+"%;animation-delay:"+Math.min(i*40,600)+"ms"}));
    row.appendChild(bar);
    row.appendChild(h("div",{class:"rv num"},String(Math.round(x.interest))));
    card.appendChild(row);
  });
  if(rk.length>24)card.appendChild(h("div",{class:"note"},"외 "+(rk.length-24)+"개 생략 — 상위 24개만 표시."));
  body(sec).appendChild(card); app.appendChild(sec);})();

/* ── No.05 검색 관심도 추이 ── */
(function(){if(!DATA.chart.dates.length)return;
  const sec=sect("sec-chart","검색 관심도 추이",M.trend_label+" 일별 지수 ("+(M.anchor||"앵커")+"=100 상대) — 차트에 마우스를 올리면 일별 값");
  const cc=h("div",{class:"card chartcard"});
  cc.appendChild(buildChart(DATA,cc));
  const lg=h("div",{class:"legend"});
  for(const name in DATA.chart.series){const sr=DATA.chart.series[name];
    lg.appendChild(h("span",null,[h("i",{style:"background:"+sr.color}),name+" (피크 "+sr.peak+")"]));}
  cc.appendChild(lg);
  cc.appendChild(h("div",{class:"note"},DATA.chart.note));
  body(sec).appendChild(cc); app.appendChild(sec);})();

function buildChart(DATA,host){
  const W=1040,H=360,L=46,R=18,T=20,B=40,pw=W-L-R,ph=H-T-B,ymax=DATA.chart.ymax;
  const dates=DATA.chart.dates,n=dates.length;
  const X=i=>n>1?L+pw*(i/(n-1)):L+pw/2, Y=v=>T+ph*(1-v/ymax);
  const svg=sv("svg",{viewBox:"0 0 "+W+" "+H,width:"100%"});
  [0,1,2,3].map(i=>Math.round(ymax*i/3)).forEach(g=>{
    svg.appendChild(sv("line",{x1:L,y1:Y(g),x2:W-R,y2:Y(g),stroke:"var(--hair)","stroke-width":1,"stroke-dasharray":"1 4"}));
    const t=sv("text",{x:L-8,y:Y(g)+4,"text-anchor":"end","font-size":11,fill:"var(--faint)",style:"font-family:var(--serif)"});
    t.textContent=g;svg.appendChild(t);});
  const step=Math.max(1,Math.ceil(n/9));
  dates.forEach((d,i)=>{if(i%step!==0&&i!==n-1)return;
    const lab=(d.length>5)?d.slice(5).replace("-","/"):d;
    const t=sv("text",{x:X(i),y:H-14,"text-anchor":"middle","font-size":11,fill:"var(--faint)"});
    t.textContent=lab;svg.appendChild(t);});
  let gi=0;
  for(const name in DATA.chart.series){const sr=DATA.chart.series[name];
    const id="cg"+(_gid++);
    const grad=sv("linearGradient",{id:id,x1:0,y1:0,x2:0,y2:1});
    grad.appendChild(sv("stop",{offset:"0%","stop-color":sr.color,"stop-opacity":".14"}));
    grad.appendChild(sv("stop",{offset:"100%","stop-color":sr.color,"stop-opacity":"0"}));
    svg.appendChild(sv("defs",null,[grad]));
    const pts=sr.v.map((v,i)=>X(i)+","+Y(v)).join(" ");
    svg.appendChild(sv("polygon",{points:L+","+Y(0)+" "+pts+" "+X(n-1)+","+Y(0),fill:"url(#"+id+")"}));
    svg.appendChild(sv("polyline",{points:pts,fill:"none",stroke:sr.color,"stroke-width":2.6,
      "stroke-linejoin":"round","stroke-linecap":"round"}));
    gi++;}
  /* hover crosshair + tooltip */
  const cross=sv("line",{x1:0,y1:T,x2:0,y2:H-B,stroke:"var(--ink)","stroke-width":1,
    "stroke-dasharray":"3 3",opacity:0});
  svg.appendChild(cross);
  const dots={};
  for(const name in DATA.chart.series){
    dots[name]=sv("circle",{r:4,fill:DATA.chart.series[name].color,stroke:"#fff","stroke-width":1.5,opacity:0});
    svg.appendChild(dots[name]);}
  const tip=h("div",{class:"ctip"});host.appendChild(tip);
  svg.addEventListener("mousemove",function(e){
    const rect=svg.getBoundingClientRect();
    const x=(e.clientX-rect.left)*(W/rect.width);
    let i=Math.round((x-L)/pw*(n-1)); i=Math.max(0,Math.min(n-1,i));
    cross.setAttribute("x1",X(i));cross.setAttribute("x2",X(i));cross.setAttribute("opacity",.6);
    let html="<b>"+esc(dates[i])+"</b>";
    for(const name in DATA.chart.series){const sr=DATA.chart.series[name];
      dots[name].setAttribute("cx",X(i));dots[name].setAttribute("cy",Y(sr.v[i]));dots[name].setAttribute("opacity",1);
      html+="<br><span style='color:"+sr.color+"'>●</span> "+esc(name)+" <b>"+sr.v[i]+"</b>";}
    tip.innerHTML=html;tip.style.opacity=1;
    const hr=host.getBoundingClientRect();
    let tx=e.clientX-hr.left+16, ty=e.clientY-hr.top-10;
    if(tx+170>hr.width)tx-=190;
    tip.style.left=tx+"px";tip.style.top=ty+"px";});
  svg.addEventListener("mouseleave",function(){cross.setAttribute("opacity",0);tip.style.opacity=0;
    for(const name in dots)dots[name].setAttribute("opacity",0);});
  return svg;
}

/* signal card (core/radar/brand 공용) */
function signalCard(DATA,c,extra){
  const card=h("div",{class:"mvc"});
  card.appendChild(h("h3",null,[document.createTextNode(c.term),momChip(c)]));
  const sub=h("div",{style:"margin-top:3px;display:flex;gap:7px;align-items:center;flex-wrap:wrap"});
  if(extra)sub.appendChild(h("span",{class:"chip"},extra));
  const sb=seasonBadge(c.season); if(sb&&c.season&&c.season.status!=="no_data")sub.appendChild(sb);
  const bz=buzzChip(c); if(bz)sub.appendChild(bz);
  if(sub.childNodes.length)card.appendChild(sub);
  const basis=c.category==="brands"?"1등 브랜드=100":(DATA.meta.anchor||"앵커")+"=100";
  card.appendChild(h("div",{class:"v num"},[document.createTextNode(String(Math.round(c.value))),
    h("small",null," · "+basis+" · 피크 "+Math.round(c.peak||0))]));
  const sp=spark(c.spark,c.category==="core"?"var(--core)":c.category==="brands"?"var(--steady)":"var(--copper2)",220,40);
  if(sp)card.appendChild(sp);
  card.appendChild(h("p",{class:"cap"},c.caption));
  const nl=newsLinks(DATA,c.term); if(nl)card.appendChild(nl);
  return card;
}

/* ── No.06 핵심 메뉴 신호 ── */
(function(){const cs=DATA.core_signals||[]; if(!cs.length)return;
  const sec=sect("sec-core","핵심 메뉴 신호","우리 코어 키워드 — 맥락 붙인 수치 (관찰만, 처방 없음)");
  const g=h("div",{class:"grid g3"});
  cs.forEach(c=>g.appendChild(signalCard(DATA,c,"검증됨 ✓")));
  body(sec).appendChild(g); app.appendChild(sec);})();

/* ── No.07 트렌드 레이더 ── */
(function(){const rd=DATA.radar||[]; if(!rd.length)return;
  const sec=sect("sec-radar","트렌드 레이더 — 인접 관심사","추적 유니버스의 검증된 인접 트렌드, 카테고리별 (접목 판단은 사장님 몫)");
  const b=body(sec);
  const byCat={};const order=[];
  rd.forEach(c=>{const k=c.category||"radar";if(!byCat[k]){byCat[k]=[];order.push(k);}byCat[k].push(c);});
  order.forEach(k=>{
    b.appendChild(h("div",{class:"caps",style:"margin:16px 2px 9px"},k+" · "+byCat[k].length));
    const g=h("div",{class:"grid g3"});
    byCat[k].forEach(c=>g.appendChild(signalCard(DATA,c)));
    b.appendChild(g);});
  app.appendChild(sec);})();

/* ── No.08 브랜드 동향 ── */
(function(){const br=DATA.brand_ranking||[],bs=DATA.brand_signals||[];
  if(!br.length&&!bs.length)return;
  const sec=sect("sec-brand","브랜드 동향","경쟁 브랜드 검색 관심 (1등 브랜드=100, 브랜드끼리만 비교) — 고유명사는 제품과 척도가 달라 분리");
  const b=body(sec);
  if(br.length){
    const card=h("div",{class:"card"});
    const maxv=Math.max.apply(null,br.map(x=>x.interest).concat([1]));
    br.forEach((x,i)=>{
      const row=h("div",{class:"rrow"});
      row.appendChild(h("div",{class:"rt"},(i+1)+". "+x.term));
      const bar=h("div",{class:"rbar"});
      bar.appendChild(h("i",{style:"width:"+(x.interest/maxv*100)+"%;animation-delay:"+Math.min(i*40,500)+"ms;background:linear-gradient(90deg,var(--steady),#e0b25c)"}));
      row.appendChild(bar);
      row.appendChild(h("div",{class:"rv num"},String(Math.round(x.interest))));
      card.appendChild(row);});
    b.appendChild(card);}
  if(bs.length){
    const g=h("div",{class:"grid g3",style:"margin-top:14px"});
    bs.slice(0,6).forEach(c=>g.appendChild(signalCard(DATA,c,(c.rank||"-")+"위")));
    b.appendChild(g);}
  app.appendChild(sec);})();

/* ── No.09 미검증 원시신호 (격리) ── */
(function(){const uv=DATA.unverified_raw||[]; if(!uv.length)return;
  const sec=sect("sec-quar","미검증 원시신호 — 격리","구글 자동발견 급상승어 중 실존 미확인 — 경쟁사/레이더로 절대 취급 금지, 참고만");
  const card=h("div",{class:"quar"});
  card.appendChild(h("div",{style:"font-size:11.5px;color:var(--copper);font-weight:700;margin-bottom:9px"},
    "⚠ 콘텐츠·데이터랩 뒷받침이 없어 격리된 용어 (없는 브랜드/오타 가능성) — 검증 전 판단 근거 사용 금지"));
  const ul=h("ul",{class:"plain"});
  uv.slice(0,15).forEach(x=>ul.appendChild(h("li",null,x.query+"  ·  "+(x.seed||"")+" 연관  ·  뒷받침 "+(x.corroboration||0)+"건")));
  card.appendChild(ul);
  body(sec).appendChild(card); app.appendChild(sec);})();

/* ── No.10 가격 포지셔닝 ── */
(function(){const cmp=DATA.comparisons||[],comp=DATA.competitors||[];
  if(!cmp.length&&!comp.length)return;
  const sec=sect("sec-price","가격 포지셔닝","NYLB 매장가 vs 경쟁사 공개가 — 기준이 달라 직접 비교 주의 (basis 라벨 참고)");
  const b=body(sec);
  if(cmp.length){
    const card=h("div",{class:"card"});const tb=h("table");
    tb.appendChild(h("tr",null,["카테고리","NYLB","경쟁사","경쟁가","차이"].map(t=>h("th",null,t))));
    cmp.forEach(c=>{const color=c.position==="above"?"var(--down)":c.position==="below"?"var(--up)":"var(--muted)";
      const arrow=c.position==="above"?"▲":c.position==="below"?"▼":"→";
      tb.appendChild(h("tr",null,[
        h("td",null,h("b",null,c.category||"-")),
        h("td",{class:"num"},(c.nylb_price!=null?Math.round(c.nylb_price).toLocaleString()+"원":"-")),
        h("td",null,[h("b",null,c.competitor_brand||"-"),document.createTextNode(" "+(c.competitor_product||"")+
          (c.competitor_basis?(" ("+c.competitor_basis+")"):""))]),
        h("td",{class:"num"},(c.competitor_price!=null?Math.round(c.competitor_price).toLocaleString()+"원":"-")),
        h("td",null,h("b",{style:"color:"+color},arrow+" "+(c.diff_pct>0?"+":"")+c.diff_pct+"%"))]));});
    card.appendChild(tb);b.appendChild(card);}
  if(comp.length){
    const card=h("div",{class:"card",style:cmp.length?"margin-top:14px":""});const tb=h("table");
    tb.appendChild(h("tr",null,["브랜드","상품 (마켓컬리)","판매가","정가"].map(t=>h("th",null,t))));
    comp.forEach(c=>tb.appendChild(h("tr",null,[
      h("td",null,h("b",null,c.brand||"-")),h("td",null,c.product||"-"),
      h("td",{class:"num"},h("b",null,c.price!=null?Math.round(c.price).toLocaleString()+"원":"-")),
      h("td",{class:"num",style:"color:var(--faint);text-decoration:line-through"},
        c.base_price!=null?Math.round(c.base_price).toLocaleString()+"원":"")])));
    card.appendChild(tb);b.appendChild(card);}
  app.appendChild(sec);})();

/* ── No.11 발굴 후보 ── */
(function(){const cs=DATA.candidates||[]; if(!cs.length)return;
  const sec=sect("sec-disc","발굴 후보 (미편입)","콘텐츠·급상승어에서 자동 발굴 — 유니버스 편입 판단은 사장님 몫");
  const cloud=h("div",{class:"cloud"});
  cs.forEach(c=>cloud.appendChild(h("span",{class:"tagc",
    title:(c.sample_title?("예: "+c.sample_title):"")},
    [document.createTextNode(c.term+" "),h("b",null,(c.from_rising?"🔥":"×"+c.freq))])));
  const b=body(sec);b.appendChild(cloud);
  b.appendChild(h("div",{class:"note"},"×N = 콘텐츠 제목 등장 횟수 · 🔥 = 구글 급상승 발굴. 마우스 오버 시 예시 제목."));
  app.appendChild(sec);})();

/* ── No.12 데이터 신뢰도 ── */
(function(){const dt=DATA.data_trust||[]; if(!dt.length)return;
  const sec=sect("sec-trust","데이터 신뢰도 & 한계","각 수치를 얼마나 믿을지 — 판단 보정용");
  const card=h("div",{class:"card"});const ul=h("ul",{class:"plain"});
  dt.forEach(d=>ul.appendChild(h("li",null,d.note)));card.appendChild(ul);
  body(sec).appendChild(card); app.appendChild(sec);})();

/* ── FOOTER ── */
const ft=h("div",{class:"foot"});
const fl=h("div");
fl.appendChild(h("div",{class:"caps",style:"margin-bottom:8px"},"데이터 출처 상태"));
const src=h("div",{class:"src"});
(M.sources_status||[]).forEach(s=>src.appendChild(h("span",{class:"pill "+(s.on?"on":"off")},(s.on?"✓ ":"⏸ ")+s.name)));
fl.appendChild(src);
ft.appendChild(fl);
ft.appendChild(h("div",{style:"text-align:right;line-height:1.9"},
  ["NYLB Market Intelligence — 결정론 데이터 자동생성 (LLM 없음)",
   h("br"),"원본 data/raw/"+M.run_id+".json"]));
app.appendChild(ft);
}

const _root=document.getElementById("app");
let _active=0;
function _renderTabs(){
  _root.innerHTML="";
  const nav=h("nav",{class:"topnav"});
  nav.appendChild(h("span",{class:"nv-brand"},"NYLB"));
  if(LENSES.length>1){
    const tabs=h("div",{class:"tabs"});
    LENSES.forEach((L,i)=>{const b=h("button",{class:"tab"+(i===_active?" on":"")},(L.icon||"")+" "+L.label);
      b.onclick=()=>{_active=i;_renderTabs();window.scrollTo(0,0);};tabs.appendChild(b);});
    nav.appendChild(tabs);
  }
  const links=h("div",{class:"nv-links"});
  [["sec-opp","기회"],["sec-season","시즌"],["sec-movers","급상승"],["sec-rank","관심도"],
   ["sec-chart","추이"],["sec-radar","레이더"],["sec-brand","브랜드"],["sec-price","가격"],
   ["sec-trust","신뢰도"]].forEach(([id,t])=>links.appendChild(h("a",{href:"#"+id},t)));
  nav.appendChild(links);
  _root.appendChild(nav);
  const board=h("div");_root.appendChild(board);
  renderBoard(LENSES[_active].board, board);
}
_renderTabs();
</script>
</body>
</html>
"""


def build_multi_dashboard(lenses: list[dict]) -> str:
    """Render multiple lens boards into one tabbed HTML. Each lens = {key,label,icon,board}."""
    return _TEMPLATE.replace("__DATA__", json.dumps(lenses, ensure_ascii=False))


def build_dashboard(result: ScanResult, chart: dict, news_context=None) -> str:
    """Single-lens convenience — wraps one board as a 1-tab dashboard (tab bar hidden)."""
    board = build_board(result, chart, news_context=news_context)
    return build_multi_dashboard([{"key": result.lens, "label": result.lens,
                                   "icon": "🍽", "board": board}])
