/* Daily U.S. capital-structure report, solely from verified SqueezeMetrics close rows.
 * All thresholds are transparent descriptive heuristics, NOT backtested trading rules.
 * No dependency on charts' independent visual scales, no future data, no Taiwan gates.
 */
(function(scope){
"use strict";
const $=id=>typeof document==="undefined"?null:document.getElementById(id);
const range=(arr,i)=>({lo:Math.min(...arr.map(r=>r[i])),hi:Math.max(...arr.map(r=>r[i]))});
const med=a=>{const x=[...a].sort((a,b)=>a-b),n=x.length;return n%2?x[(n-1)/2]:(x[n/2-1]+x[n/2])/2};
const pct=(a,b)=>b>0?100*(a/b-1):0;
const change=(a,b)=>a-b;
const sign=n=>(n>0?"+":"")+n.toFixed(2);
const pos=(v,r)=>r.hi>r.lo?(v-r.lo)/(r.hi-r.lo):0.5;
const pLabel=x=>x>=0.75?"高位":x<=0.25?"低位":"中位";
const trend=(val,threshold)=>val>threshold?"上升":val< -threshold?"下降":"持平";
const pctText=n=>(n*100).toFixed(0)+"%";
const datefmt=d=>d.replace(/-/g,"/");
const gexText=n=>(n<0?"−":"+")+(Math.abs(n)>=1e8?(Math.abs(n)/1e8).toFixed(2)+" 億":(Math.abs(n)/1e4).toFixed(0)+" 萬");
function calculate(history,index=history?.length-1,includePrev=true){
 if(!Array.isArray(history)||index<89||index>=history.length)return null;
 const latest=history[index],cut=new Date(latest[0]+"T12:00:00Z");
 if(!Number.isFinite(cut.getTime()))return null;
 cut.setUTCMonth(cut.getUTCMonth()-6);
 const from=cut.toISOString().slice(0,10),half=history.slice(0,index+1).filter(r=>r[0]>=from),look=history.slice(0,index+1);
 if(half.length<85||!look.slice(-65).every(r=>Array.isArray(r)&&r.length===4&&r.slice(1).every(Number.isFinite)))return null;
 const last=latest,prev=history[index-1],five=history[index-5],ten=history[index-10],twenty=history[index-20],sixty=history[index-60];
 if(!last||!prev||!five||!ten||!twenty||!sixty)return null;
 const rp=range(half,1),rd=range(half,2),rg=range(half,3);
 const positions=[pos(last[1],rp),pos(last[2],rd),pos(last[3],rg)];
 const p5=pct(last[1],five[1]),prior5=pct(five[1],ten[1]),p20=pct(last[1],twenty[1]),p60=pct(last[1],sixty[1]);
 const momentum=p5-prior5>=1?"增強":p5-prior5<=-1?"轉弱":"持平";
 const ma60=look.slice(-60).reduce((sum,r)=>sum+r[1],0)/60;
 const structure=p60>=4&&last[1]>=ma60?"上升":p60<=-4&&last[1]<=ma60?"下降":"盤整";
 const priceDir=trend(p5,0.75),dixDelta=change(last[2],five[2]),dixDir=trend(dixDelta,0.6);
 const recentGEX=look.slice(-21,-1).map(r=>Math.abs(r[3])),typical20=med(recentGEX);
 const gex5=change(last[3],five[3]),gexNorm=typical20>0?gex5/typical20:0,gexDir=trend(gexNorm,0.2);
 const nearZero=typical20>0&&Math.abs(last[3])<0.25*typical20;
 const lowGex=positions[2]<=0.25,negative=last[3]<0;
 const gexStrength=negative||nearZero?"弱":positions[2]>=0.65&&last[3]>=0.8*typical20?"強":"中";
 const pastHigh=Math.max(...look.slice(-21,-1).map(r=>r[1])),pastDixHigh=Math.max(...look.slice(-21,-1).map(r=>r[2]));
 const priceRecord=last[1]>=pastHigh*0.995,dixNotFollow=last[2]<pastDixHigh-1.5;
 const highDivergence=priceRecord&&dixNotFollow;
 let resonance="三線方向分歧，尚未構成一致確認",severity="輕度";
 const priceWeak=priceDir==="下降"||(structure==="下降"&&p5<0);
 const priceStrong=priceDir==="上升"&&structure==="上升";
 const dDown=dixDir==="下降",gDown=gexDir==="下降";
 if(priceWeak&&dDown&&gDown){resonance="偏空共振：價格、DIX 與 GEX 近5日同步走弱";severity=nearZero||negative?"重度":"中度"}
 else if(priceStrong&&dixDir==="上升"&&gexDir==="上升"){resonance="偏多共振：價格、DIX 與 GEX 近5日同向上行";severity="輕度"}
 else if(priceDir==="上升"&&(dDown||gDown)){resonance="偏多背離：價格上漲，但"+(dDown?"DIX ":"")+(gDown?"GEX ":"")+"未跟上";severity=dDown&&gDown?"重度":nearZero||negative?"中度":"輕度"}
 else if(priceWeak&&dixDir==="上升"){resonance="價格下跌、DIX 回升的初步背離；未證實止跌";severity=gDown?"中度":"輕度"}
 else if(priceWeak&&gDown){resonance="價格下跌且 GEX 走弱，DIX 未同步確認";severity=nearZero?"重度":"中度"}
 if(highDivergence){resonance+="；20日價格測試新高時 DIX 未同步刷新高";if(severity==="輕度")severity="中度"}
 let code,label,reason;
 if(priceWeak&&dDown&&gDown){code="red";label="🔴 風險升高";reason="價格轉弱，DIX 和 GEX 近5日同步走低"}
 else if(negative||nearZero||(lowGex&&gDown)||gexNorm<=-0.9){code="orange";label="🟠 波動放大";reason="GEX 負值、接近零或快速下滑，市場波動緩衝可能減弱"}
 else if(priceStrong&&gexStrength==="強"&&dixDir!=="下降"&&positions[1]>=0.5){code="green";label="🟢 穩定偏多";reason="價格結構向上，GEX 相對偏高且 DIX 未顯著走弱"}
 else if((positions[0]>=0.75||structure==="上升")&&(dDown||gDown||highDivergence)){code="yellow";label="🟡 偏多但警戒";reason="價格仍在相對高檔，但 DIX 或 GEX 走弱"}
 else{code="white";label="⚪ 資訊不足";reason="三線未構成上述四種明確組合，暫不推論行情方向"}
 const pWhere=positions[0]>=0.85?"接近半年高點":positions[0]<=0.15?"接近半年低點":"位於半年區間中段";
 const dWhere=pLabel(positions[1]),gWhere=pLabel(positions[2]);
 const priceWhy="S&P 500 60日結構"+structure+"，5日動能"+momentum+"，"+pWhere+"（5日 "+sign(p5)+"%）。";
 const dixWhy="DIX 位於半年"+dWhere+"，5日"+(dixDir==="上升"?"增加 ":dixDir==="下降"?"減少 ":"變動 ")+Math.abs(dixDelta).toFixed(2)+" 個百分點；"+(highDivergence?"價格測試20日新高但 DIX 未跟上。":priceRecord?"價格測試20日高點，DIX 未見明顯創高背離。":"價格未測試20日高點，暫無創高背離條件。");
 const gexWhy="GEX 位於半年"+gWhere+"、5日"+(gexDir==="上升"?"回升":gexDir==="下降"?"下降":"持平")+"；推估避險穩定作用"+gexStrength+(nearZero?"（相對前20日典型值接近零）。":"。");
 const interplay= resonance+"（"+severity+"；屬技術訊號解讀，非機率預測）。";
 const points=[priceWhy,dixWhy,gexWhy,interplay];
 const spxThreshold=look.slice(-20).reduce((a,r)=>a+r[1],0)/20;
 const dixMid=(rd.lo+rd.hi)/2;
 const recovery=0.25*typical20;
 const watch=[
   "S&P 500 若連續2日收盤高於20日均價 "+spxThreshold.toFixed(2)+" 點，短線止跌證據增加；否則價格仍偏弱。",
   "DIX 若連續2日高於半年中位 "+dixMid.toFixed(2)+"%，且5日變化轉正，資金疑慮才有減輕依據。",
   "GEX 若恢復至正值且高於前20日絕對值中位數的25%（約 "+gexText(recovery)+"），可再觀察避險穩定作用；若轉負需警戒。"
 ];
 const rows=[
  {name:"DIX",value:last[2].toFixed(2)+"%",where:dWhere+"（"+pctText(positions[1])+"）",direction:dixDir+" "+sign(dixDelta)+" pp"},
  {name:"S&P 500",value:last[1].toLocaleString("en-US",{maximumFractionDigits:2}),where:pLabel(positions[0])+"（"+pctText(positions[0])+"）",direction:priceDir+" "+sign(p5)+"%"},
  {name:"GEX",value:gexText(last[3]),where:gWhere+"（"+pctText(positions[2])+"）",direction:gexDir}
 ];
 let compare=null;
 if(includePrev){
  const lastReport=calculate(history,index-1,false);
  if(lastReport){
   const factors=[
    lastReport.stats.priceDir!==priceDir?"價格5日方向":null,
    lastReport.stats.dixDir!==dixDir?"DIX5日方向":null,
    lastReport.stats.gexDir!==gexDir?"GEX5日方向":null,
    lastReport.stats.gexStrength!==gexStrength?"GEX緩衝強弱":null,
    lastReport.stats.highDivergence!==highDivergence?"價格創高背離條件":null
   ].filter(Boolean);
   compare={date:lastReport.date,prior:lastReport.status.label,changed:lastReport.status.code!==code,
     text:lastReport.status.code!==code?"由「"+lastReport.status.label+"」轉為「"+label+"」；主要變因："+(factors.length?factors.join("、"):"趨勢數值跨越分級門檻")+"。":
       "與前一交易日同規則回推的「"+lastReport.status.label+"」一致；"+(factors.length?"變動項目："+factors.join("、")+"，尚未改變狀態。":"未出現足以改變分級的訊號。")};
  }
 }
 return {date:last[0],status:{code,label,reason},rows,points,resonance,severity,watch,compare,
   stats:{structure,momentum,priceDir,dixDir,gexDir,nearZero,gexStrength,positions,dixDelta,gexNorm,highDivergence},
   disclaimer:"相對半年位置為區間高低比例；共振與分級採固定啟發式規則，尚未獨立驗證預測力。DIX 非機構淨買超，GEX 僅是有條件的避險風險參考。"};
}
/* Reader-first copy. The quantitative status/thresholds above stay unchanged.
 * The copy describes signals cautiously: DIX is a volume share, not net buying,
 * and GEX is model-dependent rather than a guaranteed volatility damper.
 */
function plainLanguage(report){
 if(!report)return null;
 const t=report.stats,price=report.rows.find(x=>x.name==="S&P 500"),dix=report.rows.find(x=>x.name==="DIX"),gex=report.rows.find(x=>x.name==="GEX");
 const summaries={
  green:"美股近期偏強，另外兩條線大致配合，但不代表接下來一定上漲。",
  yellow:"美股仍在相對高檔，但部分市場訊號沒有跟上，追高要謹慎。",
  orange:"選擇權市場的波動緩衝可能變弱，接下來比較容易出現大幅震盪。",
  red:"美股近期轉弱，另外兩項市場訊號也走低，短線要更留意下跌與震盪風險。",
  white:"三條線目前沒有給出一致方向，先觀察，別急著判斷漲跌。"
 };
 const priceTone=t.priceDir==="上升"?"近5日上漲":t.priceDir==="下降"?"近5日下跌":"近5日變動不大";
 const priceWhere=t.positions[0]>=0.75?"目前仍靠近近半年高檔":t.positions[0]<=0.25?"目前靠近近半年低檔":"目前在近半年中間區域";
 const dark=t.dixDir==="上升"?"最近5日比率回升":t.dixDir==="下降"?"最近5日比率下滑":"最近5日變化不大";
 const darkWhere=t.positions[1]>=0.75?"偏高":t.positions[1]<=0.25?"偏低":"中間";
 const gamma=t.gexStrength==="弱"?"目前對行情的穩定效果可能較弱":t.gexStrength==="強"?"依這套模型，可能較能緩和短線波動":"目前仍有一定緩衝，但不能保證市場穩定";
 const gTrend=t.gexDir==="上升"?"近5日上升":t.gexDir==="下降"?"近5日下降":"近5日變化不大";
 const cards=[
  {id:"spx",title:"綠線｜美股價格",signal:priceTone,detail:priceWhere+"；近5日 "+price.direction.split(" ").slice(-1)[0]+"。"},
  {id:"dix",title:"藍線｜暗池成交占比 DIX",signal:dark,detail:"近半年位置"+darkWhere+"（"+dix.value+"）。這是暗池交易占比，不等於大戶正在買超。"},
  {id:"gex",title:"黃線｜選擇權影響 GEX",signal:gTrend,detail:gamma+"；GEX 高低不能直接預測股價漲跌。"}
 ];
 const watch=[t.priceDir==="下降"?"先看美股能否止跌、連續2天站回20日均線。":"先看美股能否連續2天守住20日均線。",
  t.gexStrength==="弱"?"留意 GEX 是否持續接近零或變負，波動可能擴大。":t.dixDir==="下降"?"留意 DIX 是否連續2天改善，確認資金訊號有沒有跟上。":"留意 DIX 和 GEX 是否繼續配合價格方向。"];
 return {summary:summaries[report.status.code]||summaries.white,cards,watch};
}
function render(rows,stale){
 const root=$("usopDailyAnalysis"),title=$("usopDailyTitle"),body=$("usopDailyBody"),meta=$("usopDailyMeta");
 if(!root||!title||!body||!meta)return;
 body.replaceChildren();
 const report=calculate(rows);
 if(!report){
  title.textContent="⚪ 目前還無法判讀";
  meta.textContent="近半年資料不足，先不推測市場漲跌。";
  root.dataset.state="unavailable";return;
 }
 const create=(tag,value,cls)=>{const e=document.createElement(tag);if(value!==undefined)e.textContent=value;if(cls)e.className=cls;return e};
 const easy=plainLanguage(report);
 title.textContent="📅 "+datefmt(report.date)+" 美股三線圖｜今天怎麼看？";
 const status=create("p",report.status.label+"｜"+easy.summary,"usop-report-status usop-reader-status");
 status.dataset.status=report.status.code;body.appendChild(status);
 const simple=create("section",undefined,"usop-easy-view");
 simple.setAttribute("aria-label","三條線的白話說明");
 for(const item of easy.cards){
  const card=create("div",undefined,"usop-easy-line");
  card.dataset.series=item.id;
  const heading=create("div",undefined,"usop-easy-line-title");
  heading.appendChild(create("strong",item.title));heading.appendChild(create("span",item.signal,"usop-easy-signal"));
  card.appendChild(heading);card.appendChild(create("p",item.detail));simple.appendChild(card);
 }
 body.appendChild(simple);
 const next=create("div",undefined,"usop-easy-watch");
 next.appendChild(create("strong","接下來看什麼？"));
 const notes=create("ul");for(const item of easy.watch)notes.appendChild(create("li",item));next.appendChild(notes);body.appendChild(next);
 const details=create("details",undefined,"usop-deep-details");
 details.appendChild(create("summary","查看詳細分析：數據、半年位置、背離、昨日比較"));
 const inner=create("div",undefined,"usop-deep-inner");
 inner.appendChild(create("h4","三線數據"));
 const scroll=create("div",undefined,"usop-report-scroll"),table=create("table"),thead=create("thead"),tr=create("tr");
 for(const x of ["指標","最新值","相對近半年位置","近5日方向"])tr.appendChild(create("th",x));
 thead.appendChild(tr);table.appendChild(thead);
 const tbody=create("tbody");for(const r of report.rows){const line=create("tr");for(const v of [r.name,r.value,r.where,r.direction])line.appendChild(create("td",v));tbody.appendChild(line)}table.appendChild(tbody);scroll.appendChild(table);inner.appendChild(scroll);
 function bulletSection(heading,items){inner.appendChild(create("h4",heading));const list=create("ul",undefined,"usop-report-list");for(const item of items)list.appendChild(create("li",item));inner.appendChild(list)}
 bulletSection("重點解讀",report.points);
 inner.appendChild(create("p","背離／共振檢查："+report.resonance+"；程度："+report.severity,"usop-report-resonance"));
 bulletSection("明日觀察重點",report.watch);
 if(report.compare)inner.appendChild(create("p","與前一交易日比較（"+datefmt(report.compare.date)+"，依同一規則回推，非留存昨日報告）："+report.compare.text,"usop-report-compare"));
 details.appendChild(inner);body.appendChild(details);
 meta.textContent=(stale?"⚠ 資料已過期｜":"")+"資料日："+datefmt(report.date)+"｜僅供市場風險觀察，不是買賣訊號；分類規則尚未獨立回測證明有效。";
 root.dataset.state=stale?"stale":"ready";
}

if(typeof module!=="undefined")module.exports={calculate,plainLanguage};
scope.USOptionDailyReport={calculate,plainLanguage,render};
})(typeof window!=="undefined"?window:globalThis);
