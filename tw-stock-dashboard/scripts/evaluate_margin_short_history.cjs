/* Official TWSE credit record audit; no trading or score changes.
 * Binds observations to original TAIEX calendar, not to "next available credit row".
 * Future signal lookahead forbidden: credit EOD T -> T+1 close / T+5 close.
 * Historic TWSE reports may be subsequently restated, so PIT purity is not certified.
 */
const fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,".."),read=p=>JSON.parse(fs.readFileSync(path.join(root,p),"utf8"));
const out=path.join(root,"docs/data/research/margin_short_audit/official_study.json");
const engine=require("../docs/margin-short-research-engine.js");
const market=[...read("docs/data/research/g_regime_3y/market_risk_daily.json"),...read("docs/data/research/market_intelligence/history_delta.json")];
const unique=new Map(market.map(x=>[x.date,x]));const days=[...unique.keys()].sort();const indexByDate=new Map(days.map((day,i)=>[day,i]));
const archivePath=path.join(root,"docs/data/research/margin_short_audit/official_twse_history.json");
const official=fs.existsSync(archivePath)?JSON.parse(fs.readFileSync(archivePath,"utf8")).rows||[]:[];
const byDate=new Map(official.filter(x=>x?.origin==="twse_official_credit_summary").map(x=>[x.date,x]));
function pairs(field,horizon,start,end){
 const x=[],y=[];
 for(const [date,row] of byDate){
  if(date<start||date>end)continue;
  const i=indexByDate.get(date);if(i===undefined||i+horizon>=days.length)continue;
  const here=Number(unique.get(date)?.index),there=Number(unique.get(days[i+horizon])?.index),f=Number(row[field]);
  if(!Number.isFinite(here)||here<=0||!Number.isFinite(there)||there<=0||!Number.isFinite(f))continue;
  x.push(f);y.push((there/here-1)*100);
 }
 return {x,y,n:x.length};
}
const periods=[{name:"train2023_2025",from:"2023-10-11",to:"2025-12-31"},{name:"oos2026",from:"2026-01-01",to:"2026-10-13"}];
const all=[];for(const field of ["margin_delta_100m_twd","short_delta_lots","short_margin_ratio_pct"])for(const h of [1,5]){
 const windows=periods.map(p=>{const a=pairs(field,h,p.from,p.to);const r=engine.pearson(a.x,a.y);return {window:p.name,n:a.n,r:r==null?null:Number(r.toFixed(5))}});
 all.push({feature:field,horizon:h,segments:windows,qualifiedForRiskScore:false,
  reason:"No unadjusted correlation alone can authorize promotion; full transaction-cost portfolio replay and multiple-comparison correction required."});
}
const totalSessions=days.filter(d=>d>="2023-10-11"&&d<="2026-10-13").length;
const trainSessions=days.filter(d=>d>="2023-10-11"&&d<="2026-01-01").length;
const oosSessions=days.filter(d=>d>="2026-01-01"&&d<="2026-10-13").length;
const countFor=period=>[...byDate.keys()].filter(d=>d>=period.from&&d<=period.to).length;
const coverage=periods.map((p,i)=>({name:p.name,officialRows:countFor(p),marketSessions:i===0?trainSessions:oosSessions,ratio:countFor(p)/(i===0?trainSessions:oosSessions)}));
const completeEnough=coverage[0].officialRows>=300&&coverage[0].ratio>=.9&&coverage[1].officialRows>=100&&coverage[1].ratio>=.9;
const report={asOf:"2026-10-13",scope:"TWSE-listed credit totals, evening release, revised historical report, not point-in-time vintages",marketSessions:totalSessions,officialRows:byDate.size,coverage,completeEnough,features:all,decision:"RESEARCH_ONLY_NO_RISK_WEIGHT_CHANGE",problems:[
 "No historical margin-maintenance percentages in official market credit summary.",
 "End-of-day credit reports are published after TAIEX close, therefore same-day trades would leak future information.",
 "Reconstructed historic figures may reflect next-day revisions; not certified as point-in-time data.",
 "Overlapping future 5-day returns invalidate naive IID t-tests.",
 "Any production factor must improve out-of-sample net risk/reward beyond original Risk Score and inverse allocation."],source:"https://www.twse.com.tw/zh/trading/margin/mi-margn.html"};
fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(report,null,2)+"\n");console.log("TWSE credit backtest data readiness",JSON.stringify({officialRows:byDate.size,completeEnough,coverage}));
