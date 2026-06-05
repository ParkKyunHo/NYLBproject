from __future__ import annotations

import json

from nylb.core.schema import ScanResult
from nylb.report.board import build_board  # noqa: F401
from nylb.report.chart_data import extract_chart_data  # noqa: F401  (re-export convenience)

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NYLB 종합 트렌드 분석</title>
<style>
  :root{
    --cream:#faf6f0; --card:#ffffff; --ink:#2d2620; --muted:#7c7268;
    --line:#ece3d8; --accent:#c8742f; --accent-soft:#f3e6d6;
    --salt:#d4742f; --bagel:#2f6fb5; --croffle:#9aa0a6;
    --up:#1f9d57; --down:#d24b4b; --steady:#e2a32f;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--cream);color:var(--ink);
    font-family:'Pretendard','Apple SD Gothic Neo','Malgun Gothic','맑은 고딕',sans-serif;
    line-height:1.6;-webkit-font-smoothing:antialiased}
  .wrap{max-width:980px;margin:0 auto;padding:28px 20px 64px}
  .hero{background:linear-gradient(135deg,#2d2620,#4a3b2c);color:#fff;border-radius:18px;
    padding:30px 32px;box-shadow:0 8px 30px rgba(45,38,32,.18)}
  .hero .brand{font-size:13px;letter-spacing:.14em;text-transform:uppercase;color:#e9c9a6;font-weight:700}
  .hero h1{margin:10px 0 6px;font-size:25px;line-height:1.35;font-weight:800}
  .hero .meta{font-size:13px;color:#d6c9ba;margin-top:14px}
  .hero .meta span{display:inline-block;margin-right:16px}
  .summary{background:var(--card);border:1px solid var(--line);border-radius:16px;
    padding:22px 24px;margin-top:18px;font-size:15.5px;color:#3a322a}
  .summary b{color:var(--accent)}
  section{margin-top:34px}
  h2{font-size:19px;font-weight:800;margin:0 0 4px;display:flex;align-items:center;gap:9px}
  h2 .ic{width:26px;height:26px;display:inline-grid;place-items:center;background:var(--accent-soft);
    border-radius:8px;font-size:15px}
  .sub{color:var(--muted);font-size:13px;margin:0 0 16px}
  .grid{display:grid;gap:14px}
  .kpis{grid-template-columns:repeat(4,1fr)}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
  .kpi .lab{font-size:12px;color:var(--muted);font-weight:600}
  .kpi .val{font-size:26px;font-weight:800;margin-top:4px}
  .kpi .sub2{font-size:12px;color:var(--muted);margin-top:2px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px 20px}
  .chartcard{padding:20px 18px 8px}
  .legend{display:flex;gap:18px;flex-wrap:wrap;margin:6px 4px 0;font-size:13px}
  .legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:6px;vertical-align:middle}
  .note{font-size:12.5px;color:var(--muted);background:#fbf4ea;border:1px dashed #e6d3bb;
    border-radius:10px;padding:10px 13px;margin-top:12px}
  .verdicts{grid-template-columns:repeat(3,1fr)}
  .vc{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;border-top:4px solid}
  .vc h3{margin:0;font-size:18px;font-weight:800;display:flex;justify-content:space-between;align-items:center}
  .vc .stage{font-size:12.5px;color:var(--muted);margin:3px 0 8px;font-weight:600}
  .vc p{margin:0;font-size:12.8px;color:#473d34}
  .mom{font-size:11px;font-weight:800;padding:3px 9px;border-radius:999px;color:#fff;white-space:nowrap}
  .mom.up{background:var(--up)} .mom.down{background:var(--down)} .mom.steady{background:var(--steady)}
  table{width:100%;border-collapse:collapse;font-size:13.5px}
  th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:top}
  th{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
  .bar{height:9px;border-radius:5px;background:#eee;overflow:hidden;min-width:60px}
  .bar > i{display:block;height:100%}
  .insight{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 18px;margin-bottom:11px}
  .insight h3{margin:0 0 5px;font-size:15px;font-weight:800;color:var(--accent)}
  .insight p{margin:0;font-size:13.3px;color:#473d34}
  .opp{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:12px}
  .opp .top{display:flex;justify-content:space-between;align-items:baseline;gap:10px;flex-wrap:wrap}
  .opp h3{margin:0;font-size:15.5px;font-weight:800}
  .tag{font-size:11px;font-weight:700;background:var(--accent-soft);color:#a85e21;padding:3px 9px;border-radius:999px}
  .opp p{margin:7px 0 0;font-size:13px;color:#473d34}
  .price{margin-top:9px;font-size:12.8px;font-weight:700;color:#2f6fb5;background:#eef4fb;
    border-radius:8px;padding:7px 11px;display:inline-block}
  .ap{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;margin-bottom:11px;
    display:grid;grid-template-columns:42px 1fr;gap:14px;align-items:start}
  .ap .pri{width:42px;height:42px;border-radius:11px;background:var(--accent);color:#fff;font-weight:800;
    font-size:18px;display:grid;place-items:center}
  .ap h3{margin:0 0 5px;font-size:14.5px;font-weight:800}
  .ap .rat{margin:0;font-size:12.7px;color:#5d5247}
  .badges{margin-top:9px;display:flex;gap:7px;flex-wrap:wrap}
  .badge{font-size:11px;font-weight:700;padding:3px 9px;border-radius:7px;color:#fff}
  .b-time{background:#6b5b4a}
  .b-imp-high{background:var(--up)} .b-imp-med{background:var(--steady)} .b-imp-low{background:#9aa0a6}
  .b-eff-low{background:var(--up)} .b-eff-med{background:var(--steady)} .b-eff-high{background:var(--down)}
  .ci{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:15px 17px;margin-bottom:11px}
  .ci .fmt{font-size:11px;font-weight:800;color:#a85e21;letter-spacing:.03em}
  .ci h3{margin:4px 0 6px;font-size:14.5px;font-weight:800}
  .ci p{margin:0;font-size:12.7px;color:#5d5247}
  .risk{display:grid;grid-template-columns:1fr 1fr;gap:10px 18px;font-size:13px}
  .risk .r{border-left:3px solid var(--down);padding-left:11px;margin-bottom:6px}
  .risk .r b{color:var(--down)}
  .risk .r span{color:#5d5247}
  ul.gaps{margin:0;padding-left:20px;font-size:12.8px;color:#5d5247}
  ul.gaps li{margin-bottom:6px}
  .foot{margin-top:40px;border-top:1px solid var(--line);padding-top:18px;font-size:12px;color:var(--muted)}
  .src{display:flex;gap:10px;flex-wrap:wrap;margin-top:8px}
  .pill{font-size:11.5px;font-weight:700;padding:4px 11px;border-radius:999px;border:1px solid var(--line)}
  .pill.on{background:#eaf6ef;color:#1f9d57;border-color:#bfe6cf}
  .pill.off{background:#f4f1ee;color:#9aa0a6}
  @media(max-width:720px){.kpis{grid-template-columns:repeat(2,1fr)}.verdicts{grid-template-columns:1fr}.risk{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap" id="app"></div>

<script>
const DATA = __DATA__;
function h(tag, attrs, kids){
  const e=document.createElement(tag);
  if(attrs) for(const k in attrs){ if(k==="class")e.className=attrs[k]; else if(k==="html")e.innerHTML=attrs[k]; else e.setAttribute(k,attrs[k]); }
  if(kids!=null){ (Array.isArray(kids)?kids:[kids]).forEach(c=>{ if(c==null)return; e.appendChild(typeof c==="string"?document.createTextNode(c):c); }); }
  return e;
}
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function sect(icon,title,sub){const s=h("section");s.appendChild(h("h2",null,[h("span",{class:"ic"},icon),title]));if(sub)s.appendChild(h("p",{class:"sub"},sub));return s;}
const app=document.getElementById("app");
const M=DATA.meta, HL=DATA.headline;
const ARROW={up:"▲",down:"▼",steady:"→"}, DCOL={up:"var(--up)",down:"var(--down)",steady:"var(--steady)"};
document.title = "NYLB 의사결정 상황판 · "+M.collected+" ("+M.lens+")";

/* HERO */
const hero=h("div",{class:"hero"});
hero.appendChild(h("div",{class:"brand"},M.brand));
hero.appendChild(h("h1",null,"📋 의사결정 상황판"));
const meta=h("div",{class:"meta"});
const chanStr=Object.entries(M.counts).map(([s,n])=>s+" "+n).join("·");
["수집일 "+M.collected,"렌즈 "+M.lens,"스캔 "+M.run_id,"수집 "+M.items+"건 ("+chanStr+")"].forEach(t=>meta.appendChild(h("span",null,t)));
hero.appendChild(meta); app.appendChild(hero);

/* SUMMARY — data-derived pointers, explicitly NOT a verdict */
const mv=HL.biggest_mover;
app.appendChild(h("div",{class:"summary",html:
  "<b>한눈에.</b> 검색 관심도 최상위 = <b>"+esc(HL.strongest_signal||"-")+"</b> · 모멘텀 최대 변화 = "+
  (mv?("<b>"+esc(mv.term)+"</b> ("+(mv.momentum>=0?"+":"")+mv.momentum+")"):"-")+
  " · 수집 "+HL.n_collected+"건/제외 "+HL.n_dropped+"건. <i>아래는 신호일 뿐 — 판단은 사장님 몫입니다.</i>"}));

/* KPIs */
const k=sect("📈","한눈에 보기","수집 현황과 최대 변화 (평결 아님, 데이터 산출)");
const kp=h("div",{class:"grid kpis"});
function kpi(lab,val,sub2,col){const c=h("div",{class:"kpi"});c.appendChild(h("div",{class:"lab"},lab));
  const vv=h("div",{class:"val"},val); if(col)vv.style.color=col; c.appendChild(vv);
  if(sub2)c.appendChild(h("div",{class:"sub2"},sub2)); return c;}
kp.appendChild(kpi("총 수집", M.items+"건", Object.keys(M.counts).length+"개 채널 · 실패 "+M.errors));
kp.appendChild(kpi("관련성 제외", HL.n_dropped+"건", "노이즈 게이트로 제외"));
kp.appendChild(kpi("최상위 관심", esc(HL.strongest_signal||"-"), "검색 관심도 1위"));
kp.appendChild(kpi("최대 변화", mv?esc(mv.term):"-", mv?((mv.momentum>=0?"▲ +":"▼ ")+mv.momentum+" 모멘텀"):"", mv?DCOL[mv.momentum>=0?"up":"down"]:null));
k.appendChild(kp); app.appendChild(k);

/* INTEREST RANKING */
(function(){const rk=DATA.interest_ranking||[]; if(!rk.length)return;
  const sec=sect("🍞","검색 관심도 랭킹","사람들이 지금 어떤 베이커리·디저트를 검색하나 (0~100)");
  const card=h("div",{class:"card"});
  const maxv=Math.max.apply(null, rk.map(x=>x.interest).concat([1]));
  rk.forEach(x=>{const row=h("div",{style:"display:grid;grid-template-columns:130px 1fr 40px;align-items:center;gap:10px;margin:7px 0"});
    row.appendChild(h("div",{style:"font-weight:700;font-size:13px"+(x.core?";color:var(--accent)":"")}, x.term+(x.core?" ★":"")));
    const bar=h("div",{class:"bar",style:"height:15px;background:#f0e7da"});
    bar.appendChild(h("i",{style:"width:"+(x.interest/maxv*100)+"%;background:"+(x.core?"var(--bagel)":"var(--salt)")}));
    row.appendChild(bar);
    row.appendChild(h("div",{style:"font-weight:800;font-size:13px;text-align:right"},String(Math.round(x.interest))));
    card.appendChild(row);});
  card.appendChild(h("div",{class:"note"},"★ = 우리 코어(파란 막대). 주황 = 레이더 인접 트렌드. 막대가 길수록 지금 검색 관심이 높음."));
  sec.appendChild(card); app.appendChild(sec);})();

/* CHART */
(function(){if(!DATA.chart.dates.length)return;
  const cs=sect("📉","검색 관심도 추이",M.trend_label+" 일별 지수 (0~100, 상대 정규화)");
  const cc=h("div",{class:"card chartcard"}); cc.appendChild(buildChart());
  const lg=h("div",{class:"legend"});
  for(const name in DATA.chart.series){const sr=DATA.chart.series[name];
    lg.appendChild(h("span",null,[h("i",{style:"background:"+sr.color}),name+" (피크 "+sr.peak+")"]));}
  cc.appendChild(lg); cc.appendChild(h("div",{class:"note"}, DATA.chart.note));
  cs.appendChild(cc); app.appendChild(cs);})();

function buildChart(){
  const W=760,H=340,L=48,R=24,T=24,B=44, pw=W-L-R, ph=H-T-B, ymax=DATA.chart.ymax;
  const dates=DATA.chart.dates, n=dates.length;
  const X=i=>L+pw*(i/(n-1)), Y=v=>T+ph*(1-v/ymax);
  const NS="http://www.w3.org/2000/svg";
  const svg=document.createElementNS(NS,"svg");
  svg.setAttribute("viewBox","0 0 "+W+" "+H); svg.setAttribute("width","100%");
  function sv(tag,a){const e=document.createElementNS(NS,tag);for(const k in a)e.setAttribute(k,a[k]);return e;}
  [0,1,2,3].map(i=>Math.round(ymax*i/3)).forEach(g=>{
    svg.appendChild(sv("line",{x1:L,y1:Y(g),x2:W-R,y2:Y(g),stroke:"#ece3d8","stroke-width":1}));
    const t=sv("text",{x:L-8,y:Y(g)+4,"text-anchor":"end","font-size":11,fill:"#9b8f80"});t.textContent=g;svg.appendChild(t);});
  const step=Math.max(1,Math.ceil(n/8));
  dates.forEach((d,i)=>{ if(i%step!==0 && i!==n-1) return;
    const lab=(d.length>5)?d.slice(5).replace("-","/"):d;
    const t=sv("text",{x:X(i),y:H-16,"text-anchor":"middle","font-size":11,fill:"#9b8f80"});t.textContent=lab;svg.appendChild(t);});
  for(const name in DATA.chart.series){const sr=DATA.chart.series[name];
    const pts=sr.v.map((v,i)=>X(i)+","+Y(v)).join(" ");
    svg.appendChild(sv("polyline",{points:pts,fill:"none",stroke:sr.color,"stroke-width":3,"stroke-linejoin":"round","stroke-linecap":"round"}));
    sr.v.forEach((v,i)=>svg.appendChild(sv("circle",{cx:X(i),cy:Y(v),r:3.2,fill:sr.color})));}
  return svg;
}

/* CORE SIGNALS */
(function(){const cs=DATA.core_signals||[]; if(!cs.length)return;
  const sec=sect("🥯","핵심 메뉴 신호","코어 키워드 — 맥락 붙인 수치 (관찰만, 처방 없음)");
  const g=h("div",{class:"grid verdicts"});
  cs.forEach(c=>{const card=h("div",{class:"vc"});card.style.borderTopColor=DCOL[c.direction];
    card.appendChild(h("h3",null,[document.createTextNode(c.term),
      h("span",{class:"mom "+c.direction},ARROW[c.direction]+" "+(c.momentum>=0?"+":"")+c.momentum)]));
    card.appendChild(h("div",{class:"stage"},"검증됨 ✓ · 피크 "+c.peak));
    card.appendChild(h("p",null,c.caption)); g.appendChild(card);});
  sec.appendChild(g); app.appendChild(sec);})();

/* RADAR (verified only) */
(function(){const rd=DATA.radar||[]; if(!rd.length)return;
  const sec=sect("🛰️","트렌드 레이더 — 인접 관심사","검증된 인접 트렌드만 (접목 판단은 사장님 몫)");
  const g=h("div",{class:"grid verdicts"});
  rd.forEach(c=>{const card=h("div",{class:"vc"});card.style.borderTopColor=DCOL[c.direction];
    card.appendChild(h("h3",null,[document.createTextNode(c.term),
      h("span",{class:"mom "+c.direction},ARROW[c.direction]+" "+(c.momentum>=0?"+":"")+c.momentum)]));
    card.appendChild(h("div",{class:"stage"},"검증됨 ✓"));
    card.appendChild(h("p",null,c.caption)); g.appendChild(card);});
  sec.appendChild(g); app.appendChild(sec);})();

/* UNVERIFIED RAW — quarantine (비키 베이글 lands here) */
(function(){const uv=DATA.unverified_raw||[]; if(!uv.length)return;
  const sec=sect("🚧","미검증 원시신호","구글 자동발견 급상승어 — 실존 미확인. 절대 경쟁사/레이더로 취급 금지, 참고만.");
  const card=h("div",{class:"card"});
  card.appendChild(h("div",{style:"font-size:11.5px;color:#b08968;margin-bottom:8px"},"※ 콘텐츠·데이터랩 뒷받침이 없어 격리된 용어입니다(없는 브랜드/오타 가능). 검증 전엔 판단 근거로 쓰지 마세요."));
  const ul=h("ul",{class:"gaps"});
  uv.slice(0,15).forEach(x=>ul.appendChild(h("li",null, x.query+"  ·  "+(x.seed||"")+" 연관  ·  뒷받침 "+(x.corroboration||0)+"건")));
  card.appendChild(ul); sec.appendChild(card); app.appendChild(sec);})();

/* PRICE POSITIONING */
(function(){const cmp=DATA.comparisons||[]; if(!cmp.length)return;
  const sec=sect("📊","가격 포지셔닝","NYLB 매장가 vs 경쟁사 — 차이(%) (위=비쌈·빨강, 아래=쌈·초록)");
  const card=h("div",{class:"card"});const tb=h("table");
  tb.appendChild(h("tr",null,["카테고리","NYLB","경쟁사","경쟁가","차이"].map(t=>h("th",null,t))));
  cmp.forEach(c=>{const color=c.position==="above"?"var(--down)":c.position==="below"?"var(--up)":"var(--muted)";
    const arrow=c.position==="above"?"▲":c.position==="below"?"▼":"→";
    tb.appendChild(h("tr",null,[
      h("td",null,h("b",null,c.category||"-")),
      h("td",null,(c.nylb_price!=null?Math.round(c.nylb_price).toLocaleString()+"원":"-")),
      h("td",null,[h("b",null,c.competitor_brand||"-"),document.createTextNode(" "+(c.competitor_product||""))]),
      h("td",null,(c.competitor_price!=null?Math.round(c.competitor_price).toLocaleString()+"원":"-")),
      h("td",null,h("b",{style:"color:"+color},arrow+" "+(c.diff_pct>0?"+":"")+c.diff_pct+"%"))]));});
  card.appendChild(tb);
  card.appendChild(h("div",{class:"note"},"※ 컬리 리테일가는 매장 단품가와 기준이 달라 직접 비교 주의(기준 라벨 참고). 시점·프로모션에 따라 변동."));
  sec.appendChild(card); app.appendChild(sec);})();

/* COMPETITORS */
(function(){const comp=DATA.competitors||[]; if(!comp.length)return;
  const sec=sect("🏷️","경쟁사 가격 (마켓컬리)","공개 상품페이지 크롤링 — 리테일 SKU 기준(매장가와 다를 수 있음)");
  const card=h("div",{class:"card"});const tb=h("table");
  tb.appendChild(h("tr",null,["브랜드","상품","판매가","정가"].map(t=>h("th",null,t))));
  comp.forEach(c=>tb.appendChild(h("tr",null,[
    h("td",null,h("b",null,c.brand||"-")), h("td",null,c.product||"-"),
    h("td",null,h("b",null,c.price!=null?Math.round(c.price).toLocaleString()+"원":"-")),
    h("td",{style:"color:#9b8f80;text-decoration:line-through"},c.base_price!=null?Math.round(c.base_price).toLocaleString()+"원":"")])));
  card.appendChild(tb); sec.appendChild(card); app.appendChild(sec);})();

/* DATA TRUST */
(function(){const dt=DATA.data_trust||[]; if(!dt.length)return;
  const sec=sect("🧪","데이터 신뢰도 & 한계","각 수치를 얼마나 믿을지 — 판단 보정용");
  const card=h("div",{class:"card"});const ul=h("ul",{class:"gaps"});
  dt.forEach(d=>ul.appendChild(h("li",null,d.note))); card.appendChild(ul);
  sec.appendChild(card); app.appendChild(sec);})();

/* FOOTER */
const ft=h("div",{class:"foot"}); ft.appendChild(h("div",null,"데이터 출처 상태"));
const src=h("div",{class:"src"});
(M.sources_status||[]).forEach(s=>src.appendChild(h("span",{class:"pill "+(s.on?"on":"off")},(s.on?"✓ ":"⏸ ")+s.name)));
ft.appendChild(src);
ft.appendChild(h("div",{style:"margin-top:12px"},"NYLB 의사결정 상황판 · 결정론 데이터 자동생성(LLM 없음) · 원본 data/raw/"+M.run_id+".json"));
app.appendChild(ft);
</script>
</body>
</html>
"""


def build_dashboard(result: ScanResult, chart: dict) -> str:
    """Render the deterministic decision-support board to self-contained HTML.
    No `synthesis` — the board is 100% data-driven (build_board)."""
    board = build_board(result, chart)
    return _TEMPLATE.replace("__DATA__", json.dumps(board, ensure_ascii=False))
