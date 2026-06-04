from __future__ import annotations

import json

from nylb.core.schema import ScanResult
from nylb.report.chart_data import extract_chart_data  # noqa: F401  (re-export convenience)

_COLORS = {"소금빵": "var(--salt)", "베이글": "var(--bagel)", "크로플": "var(--croffle)"}
_PALETTE = ["#7c5cff", "#2f9e5b", "#d24b4b", "#e2a32f", "#1f9d57"]

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
const app=document.getElementById("app");
const M=DATA.meta, S=DATA.syn;
document.title = "NYLB 트렌드 분석 · "+M.collected+" ("+M.lens+")";

/* HERO */
const hero=h("div",{class:"hero"});
hero.appendChild(h("div",{class:"brand"},M.brand));
hero.appendChild(h("h1",null,"📊 종합 트렌드 분석 — "+S.headline));
const meta=h("div",{class:"meta"});
const chanStr=Object.entries(M.counts).map(([s,n])=>s+" "+n).join("·");
["수집일 "+M.collected, "렌즈 "+M.lens, "스캔 "+M.run_id, "수집 "+M.items+"건 ("+chanStr+")"]
  .forEach(t=>meta.appendChild(h("span",null,t)));
hero.appendChild(meta);
app.appendChild(hero);

app.appendChild(h("div",{class:"summary",html:"<b>핵심 결론.</b> "+esc(S.executive_summary)}));

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
function sect(icon,title,sub){const s=h("section");s.appendChild(h("h2",null,[h("span",{class:"ic"},icon),title]));if(sub)s.appendChild(h("p",{class:"sub"},sub));return s;}

/* KPI + momentum */
const k=sect("📈","한눈에 보기","채널 수집량과 키워드별 검색 모멘텀 ("+M.trend_label+")");
const kp=h("div",{class:"grid kpis"});
kp.appendChild(kpi("총 수집", M.items+"건", Object.keys(M.counts).length+"개 채널 · 실패 "+M.errors));
S.trend_verdicts.forEach(v=>{
  const sym=v.momentum==="up"?"▲":v.momentum==="down"?"▼":"▬";
  const series=DATA.chart.series[v.keyword];
  kp.appendChild(kpi(v.keyword, sym+" "+(series?(series.mom>0?"+":"")+series.mom:""), momLabel(v.momentum)+" · 피크 "+(series?series.peak:"-"), v.momentum));
});
k.appendChild(kp);
app.appendChild(k);
function kpi(lab,val,sub2,mom){const c=h("div",{class:"kpi"});c.appendChild(h("div",{class:"lab"},lab));
  const vv=h("div",{class:"val"},val); if(mom)vv.style.color=mom==="up"?"var(--up)":mom==="down"?"var(--down)":"var(--steady)";
  c.appendChild(vv);c.appendChild(h("div",{class:"sub2"},sub2));return c;}
function momLabel(m){return m==="up"?"상승":m==="down"?"하락":"보합";}

/* CHART */
const cs=sect("📉","검색 관심도 추이",M.trend_label+" 일별 지수 (0~100, 상대 정규화)"+(DATA.chart.dates.length?(" · "+DATA.chart.dates[0]+" ~ "+DATA.chart.dates[DATA.chart.dates.length-1]):""));
const cc=h("div",{class:"card chartcard"});
cc.appendChild(buildChart());
const lg=h("div",{class:"legend"});
for(const name in DATA.chart.series){const sr=DATA.chart.series[name];
  lg.appendChild(h("span",null,[h("i",{style:"background:"+sr.color}),name+" (피크 "+sr.peak+")"]));}
cc.appendChild(lg);
cc.appendChild(h("div",{class:"note"}, DATA.chart.note));
cs.appendChild(cc);
app.appendChild(cs);

/* INTEREST RANKING — 종목별 검색 관심도 (가장 직관적인 "지금 뜨는 종목" 뷰) */
(function(){
  const rk=DATA.interest_ranking||[];
  if(!rk.length) return;
  const sec=sect("🍞","검색 관심도 랭킹","사람들이 지금 어떤 베이커리·디저트를 검색하나 ("+M.trend_label+", 0~100)");
  const card=h("div",{class:"card"});
  const maxv=Math.max.apply(null, rk.map(x=>x.interest).concat([1]));
  rk.forEach(x=>{
    const row=h("div",{style:"display:grid;grid-template-columns:130px 1fr 40px;align-items:center;gap:10px;margin:7px 0"});
    row.appendChild(h("div",{style:"font-weight:700;font-size:13px"+(x.core?";color:var(--accent)":"")}, x.term+(x.core?" ★":"")));
    const bar=h("div",{class:"bar",style:"height:15px;background:#f0e7da"});
    bar.appendChild(h("i",{style:"width:"+(x.interest/maxv*100)+"%;background:"+(x.core?"var(--bagel)":"var(--salt)")}));
    row.appendChild(bar);
    row.appendChild(h("div",{style:"font-weight:800;font-size:13px;text-align:right"},String(Math.round(x.interest))));
    card.appendChild(row);
  });
  card.appendChild(h("div",{class:"note"},"★ = 우리 코어(베이글·소금빵·크로플), 파란 막대. 주황 막대는 레이더 인접 트렌드. 막대가 길수록 지금 한국 검색 관심이 높음."));
  sec.appendChild(card); app.appendChild(sec);
})();

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
    const t=sv("text",{x:L-8,y:Y(g)+4,"text-anchor":"end","font-size":11,fill:"#9b8f80"});t.textContent=g;svg.appendChild(t);
  });
  const step=Math.max(1,Math.ceil(n/8));
  dates.forEach((d,i)=>{ if(i%step!==0 && i!==n-1) return;
    const lab=(d.length>5)?d.slice(5).replace("-","/"):d;
    const t=sv("text",{x:X(i),y:H-16,"text-anchor":"middle","font-size":11,fill:"#9b8f80"});t.textContent=lab;svg.appendChild(t);});
  for(const name in DATA.chart.series){const sr=DATA.chart.series[name];
    const pts=sr.v.map((v,i)=>X(i)+","+Y(v)).join(" ");
    svg.appendChild(sv("polyline",{points:pts,fill:"none",stroke:sr.color,"stroke-width":name==="크로플"?2:3,
      "stroke-linejoin":"round","stroke-linecap":"round","stroke-dasharray":name==="크로플"?"4 4":""}));
    sr.v.forEach((v,i)=>svg.appendChild(sv("circle",{cx:X(i),cy:Y(v),r:name==="크로플"?2:3.2,fill:sr.color})));
  }
  return svg;
}

/* TREND VERDICTS */
const tv=sect("🔬","키워드별 라이프사이클 판정","검증 후 확정된 모멘텀과 단계");
const tvg=h("div",{class:"grid verdicts"});
const colors={"소금빵":"var(--salt)","베이글":"var(--bagel)","크로플":"var(--croffle)"};
S.trend_verdicts.forEach(v=>{const c=h("div",{class:"vc"});c.style.borderTopColor=colors[v.keyword]||"var(--accent)";
  c.appendChild(h("h3",null,[document.createTextNode(v.keyword),h("span",{class:"mom "+v.momentum},momLabel(v.momentum))]));
  c.appendChild(h("div",{class:"stage"},v.stage));
  c.appendChild(h("p",null,v.summary));tvg.appendChild(c);});
tv.appendChild(tvg);app.appendChild(tv);

/* MATRIX */
const mx=sect("🗂️","채널 교차 언급 매트릭스","각 키워드를 언급한 매장/영상 수 — 네이버 다수는 '나열형 카페'라 차별 신호 아님");
const mc=h("div",{class:"card"});
const tb=h("table");
tb.appendChild(h("tr",null,[th("키워드"),th("YouTube"),th("Naver (나열형 주의)"),th("Trends")]));
const maxN=20;
for(const kw in DATA.matrix){const row=DATA.matrix[kw];
  const td_kw=h("td",null,h("b",null,kw));
  const naverCell=h("td");
  const barwrap=h("div",{class:"bar",style:"background:#f0e7da"});
  barwrap.appendChild(h("i",{style:"width:"+(row.naver/maxN*100)+"%;background:var(--bagel)"}));
  naverCell.appendChild(h("div",null,String(row.naver)));naverCell.appendChild(barwrap);
  tb.appendChild(h("tr",null,[td_kw,h("td",null,String(row.youtube)),naverCell,h("td",null,String(row.google_trends))]));}
mc.appendChild(tb);
mc.appendChild(h("div",{class:"note"},"네이버 동시언급 수는 대부분 '디저트 나열형 카페' 글에서 함께 등장한 것이라 키워드 우열이 아닌 '업계 표준 진입' 신호로 봐야 합니다(차별 신호 아님)."));
mx.appendChild(mc);app.appendChild(mx);
function th(t){return h("th",null,t);}

/* RADAR — 인접 트렌드 (워치리스트 + 자동발견) */
(function(){
  const sig=DATA.radar_signals||[], rising=DATA.rising||[], scored=S.radar||[];
  if(!sig.length && !rising.length && !scored.length) return;
  const rd=sect("🛰️","트렌드 레이더 — 인접 관심사","베이글 중심으로 본 음식·디저트 인접 트렌드 (워치리스트 + 자동발견)");
  if(scored.length){
    scored.forEach(r=>{const c=h("div",{class:"opp"});
      c.appendChild(h("div",{class:"top"},[h("h3",null,r.trend||""),h("span",{class:"tag"},"베이글 접목 "+(r.bagel_fit||"-"))]));
      if(r.rising_signal) c.appendChild(h("p",null,"📈 신호: "+r.rising_signal));
      if(r.angle) c.appendChild(h("p",null,"🥯 각도: "+r.angle));
      rd.appendChild(c);});
  }
  if(sig.length){
    const c=h("div",{class:"card"});
    c.appendChild(h("div",{class:"fmt",style:"margin-bottom:8px"},"🗂️ 워치리스트 검색 강도 ("+M.trend_label+")"));
    const tb=h("table");
    tb.appendChild(h("tr",null,[th("인접 트렌드"),th("검색강도"),th("피크")]));
    sig.forEach(x=>tb.appendChild(h("tr",null,[h("td",null,h("b",null,x.term)),
      h("td",null,String(Math.round(x.interest))),h("td",null,String(Math.round(x.peak)))])));
    c.appendChild(tb); rd.appendChild(c);
  }
  if(rising.length){
    const c=h("div",{class:"card"});
    c.appendChild(h("div",{class:"fmt",style:"margin-bottom:6px"},"🤖 자동발견 급상승어 (미검증 — 브랜드·오타·이슈 섞일 수 있음)"));
    c.appendChild(h("div",{style:"font-size:11.5px;color:#b08968;margin-bottom:8px"},"※ 구글이 자동 추출한 연관 급상승어입니다. 실재하지 않는 브랜드/오타가 섞일 수 있으니 '참고용 단서'로만 보세요."));
    const ul=h("ul",{class:"gaps"});
    rising.slice(0,12).forEach(x=>ul.appendChild(h("li",null,x.query+"  ·  "+x.seed+" 연관  ·  +"+Math.round(x.value))));
    c.appendChild(ul); rd.appendChild(c);
  }
  app.appendChild(rd);
})();

/* INSIGHTS */
const ins=sect("💡","핵심 인사이트","");
S.top_insights.forEach(i=>{const c=h("div",{class:"insight"});c.appendChild(h("h3",null,i.title));c.appendChild(h("p",null,i.detail));ins.appendChild(c);});
app.appendChild(ins);

/* MENU OPPORTUNITIES */
const mo=sect("🥯","신메뉴 기회","실제 블로그 근거가 있는 변주 위주");
S.menu_opportunities.forEach(o=>{const c=h("div",{class:"opp"});
  c.appendChild(h("div",{class:"top"},[h("h3",null,o.name),h("span",{class:"tag"},o.type)]));
  c.appendChild(h("p",null,o.why));
  c.appendChild(h("div",{class:"price"},"💰 "+o.price_suggestion));mo.appendChild(c);});
app.appendChild(mo);

/* PRICING */
const pr=sect("🏷️","가격 벤치마크","시장 관측 기반 · '확정'이 아닌 '잠정 가이드'");
const pc=h("div",{class:"card"});const pt=h("table");
pt.appendChild(h("tr",null,[th("항목"),th("시장가"),th("메모")]));
S.pricing_benchmark.forEach(p=>pt.appendChild(h("tr",null,[h("td",null,h("b",null,p.item)),h("td",null,h("b",{},p.market_price)),h("td",null,p.note)])));
pc.appendChild(pt);pr.appendChild(pc);app.appendChild(pr);

/* PRICE POSITIONING — 📊 가격 포지셔닝 (NYLB vs 경쟁사) */
(function(){
  const cmp=DATA.comparisons||[];
  if(!cmp.length) return;
  const sec=sect("📊","가격 포지셔닝","NYLB 매장가 vs 경쟁사 — 차이(%)로 본 포지셔닝 (위=비쌈·빨강, 아래=쌈·초록)");
  if(S.price_positioning)
    sec.appendChild(h("div",{class:"insight"},[h("h3",null,"포지셔닝 인사이트"),h("p",null,S.price_positioning)]));
  const card=h("div",{class:"card"});const tb=h("table");
  tb.appendChild(h("tr",null,[th("카테고리"),th("NYLB"),th("경쟁사"),th("경쟁가"),th("차이")]));
  cmp.forEach(c=>{
    const color=c.position==="above"?"var(--down)":c.position==="below"?"var(--up)":"var(--muted)";
    const arrow=c.position==="above"?"▲":c.position==="below"?"▼":"▬";
    const compCell=h("td",null,[h("b",null,c.competitor_brand||"-"),
      document.createTextNode(" "+(c.competitor_product||"")),
      c.competitor_basis?h("span",{class:"tag",style:"margin-left:6px"},c.competitor_basis):null]);
    const diffCell=h("td",null,h("b",{style:"color:"+color},
      arrow+" "+(c.diff_pct>0?"+":"")+c.diff_pct+"%"));
    tb.appendChild(h("tr",null,[
      h("td",null,h("b",null,c.category||"-")),
      h("td",null,(c.nylb_price!=null?Math.round(c.nylb_price).toLocaleString()+"원":"-")),
      compCell,
      h("td",null,(c.competitor_price!=null?Math.round(c.competitor_price).toLocaleString()+"원":"-")),
      diffCell]));
  });
  card.appendChild(tb);
  card.appendChild(h("div",{class:"note"},"※ 컬리 리테일가는 매장 단품가와 기준이 달라 직접 비교에 주의(기준 라벨 참고). 가격은 시점·프로모션에 따라 변동."));
  sec.appendChild(card);app.appendChild(sec);
})();

/* COMPETITORS — 경쟁사 가격 (크롤링) */
(function(){
  const comp=DATA.competitors||[];
  if(!comp.length) return;
  const sec=sect("🏷️","경쟁사 가격 (마켓컬리)","경쟁사 리테일 상품가 — 공개 상품페이지 크롤링(robots 허용·rate-limit·캐시 준수)");
  const card=h("div",{class:"card"});const tb=h("table");
  tb.appendChild(h("tr",null,[th("브랜드"),th("상품"),th("판매가"),th("정가")]));
  comp.forEach(c=>tb.appendChild(h("tr",null,[
    h("td",null,h("b",null,c.brand||"-")),
    h("td",null,c.product||"-"),
    h("td",null,h("b",{},c.price!=null?Math.round(c.price).toLocaleString()+"원":"-")),
    h("td",{style:"color:#9b8f80;text-decoration:line-through"},
      c.base_price!=null?Math.round(c.base_price).toLocaleString()+"원":"")])));
  card.appendChild(tb);
  card.appendChild(h("div",{class:"note"},"리테일 SKU 기준이라 매장 인스토어가와 다를 수 있음. 가격은 시점·프로모션에 따라 변동."));
  sec.appendChild(card);app.appendChild(sec);
})();

/* CONTENT */
const co=sect("🎬","콘텐츠·SNS 소재","");
const cog=h("div",{class:"grid",style:"grid-template-columns:repeat(2,1fr)"});
S.content_ideas.forEach(c=>{const x=h("div",{class:"ci"});
  x.appendChild(h("div",{class:"fmt"},"▶ "+c.format));x.appendChild(h("h3",null,c.idea));x.appendChild(h("p",null,c.angle));cog.appendChild(x);});
co.appendChild(cog);app.appendChild(co);

/* ACTION PLAN */
const ap=sect("✅","실행 계획 (우선순위순)","impact·effort·기간 포함");
S.action_plan.sort((a,b)=>a.priority-b.priority).forEach(a=>{const c=h("div",{class:"ap"});
  c.appendChild(h("div",{class:"pri"},String(a.priority)));
  const r=h("div");r.appendChild(h("h3",null,a.action));r.appendChild(h("p",{class:"rat"},"근거 · "+a.rationale));
  const bd=h("div",{class:"badges"});
  bd.appendChild(h("span",{class:"badge b-time"},"⏱ "+a.timeframe));
  bd.appendChild(h("span",{class:"badge b-imp-"+a.impact},"임팩트 "+impKo(a.impact)));
  bd.appendChild(h("span",{class:"badge b-eff-"+a.effort},"노력 "+impKo(a.effort)));
  r.appendChild(bd);c.appendChild(r);ap.appendChild(c);});
app.appendChild(ap);
function impKo(x){return x==="high"?"높음":x==="med"?"중간":"낮음";}

/* RISKS */
const rk=sect("⚠️","리스크 & 대응","");
const rkc=h("div",{class:"card"});const rg=h("div",{class:"risk"});
S.risks.forEach(r=>{const d=h("div",{class:"r"});d.appendChild(h("div",null,[h("b",null,"리스크 "),document.createTextNode(r.risk)]));
  d.appendChild(h("div",null,[h("span",null,"→ 대응: "+r.mitigation)]));rg.appendChild(d);});
rkc.appendChild(rg);rk.appendChild(rkc);app.appendChild(rk);

/* DATA GAPS */
const dg=sect("🧪","데이터 한계 & 다음 수집 과제","");
const dgc=h("div",{class:"card"});const ul=h("ul",{class:"gaps"});
S.data_gaps.forEach(g=>ul.appendChild(h("li",null,g)));dgc.appendChild(ul);dg.appendChild(dgc);app.appendChild(dg);

/* FOOTER */
const ft=h("div",{class:"foot"});
ft.appendChild(h("div",null,"데이터 출처 상태"));
const src=h("div",{class:"src"});
DATA.meta.sources_status.forEach(s => src.appendChild(
  h("span",{class:"pill "+(s.on?"on":"off")}, (s.on?"✓ ":"⏸ ")+s.name)));
ft.appendChild(src);
ft.appendChild(h("div",{style:"margin-top:12px"},"NYLB 시장조사 도구 · 다채널 수집 → 종합 분석 · 원본 data/raw/"+M.run_id+".json · 향후 SaaS 웹 대시보드 프리뷰."));
app.appendChild(ft);
</script>
</body>
</html>
"""


def _build_chart(chart: dict) -> dict:
    source = "naver_datalab" if chart["trends"].get("naver_datalab") else "google_trends"
    tsrc = chart["trends"].get(source, {})
    core = set(chart.get("keywords", []))
    items = [(kw, info) for kw, info in tsrc.items() if not core or kw in core]
    dates: list[str] = sorted({d for _, info in items for d in info["daily"]})
    series: dict[str, dict] = {}
    spare = list(_PALETTE)
    for kw, info in items:
        color = _COLORS.get(kw) or (spare.pop(0) if spare else "#888")
        series[kw] = {
            "color": color,
            "v": [info["daily"].get(d, 0) for d in dates],
            "peak": info.get("peak", 0),
            "mom": info.get("momentum", 0),
        }
    ymax = max([v for s in series.values() for v in s["v"]] + [5])
    ymax = int((ymax // 5 + 1) * 5)
    return {"dates": dates, "series": series, "ymax": ymax, "source": source}


def build_dashboard(result: ScanResult, synthesis: dict, chart: dict) -> str:
    chart_block = _build_chart(chart)
    label = {"naver_datalab": "네이버 데이터랩", "google_trends": "Google Trends"}.get(
        chart_block["source"], chart_block["source"])
    sources_status = [
        {"name": "YouTube", "on": chart["counts"].get("youtube", 0) > 0},
        {"name": "Naver 검색", "on": chart["counts"].get("naver", 0) > 0},
        {"name": "Google Trends", "on": chart["counts"].get("google_trends", 0) > 0},
        {"name": "Naver DataLab", "on": chart["counts"].get("naver_datalab", 0) > 0},
        {"name": "Instagram", "on": chart["counts"].get("instagram", 0) > 0},
    ]
    core = set(chart.get("keywords", []))
    dl = chart["trends"].get("naver_datalab", {})
    radar_signals = sorted(
        ({"term": kw, "interest": info["latest"], "peak": info["peak"]}
         for kw, info in dl.items() if kw not in core),
        key=lambda r: r["interest"], reverse=True)
    interest_ranking = sorted(
        ({"term": kw, "interest": round(info["latest"], 1), "core": kw in core}
         for kw, info in dl.items()),
        key=lambda r: r["interest"], reverse=True)
    data = {
        "meta": {
            "brand": "NYLB · NEW YORK LOVE BAGEL",
            "run_id": result.run_id,
            "collected": f"{result.finished_at:%Y-%m-%d}",
            "lens": result.lens,
            "items": len(result.items),
            "errors": len(result.errors),
            "counts": chart["counts"],
            "sources_status": sources_status,
            "trend_label": label,
        },
        "chart": {
            "dates": chart_block["dates"],
            "series": chart_block["series"],
            "ymax": chart_block["ymax"],
            "note": synthesis.get("chart_note")
                    or f"{label} 기준 검색 관심도 추이. 상대 정규화(0~100) 지표이며 절대 수요 우열로 단정하지 마세요.",
        },
        "matrix": chart["matrix"],
        "rising": chart.get("rising", []),
        "radar_signals": radar_signals,
        "interest_ranking": interest_ranking,
        "competitors": chart.get("competitors", []),
        "comparisons": chart.get("comparisons", []),
        "syn": synthesis,
    }
    return _TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
