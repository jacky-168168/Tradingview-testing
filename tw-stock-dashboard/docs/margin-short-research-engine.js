/* TWSE market-credit exploratory audit. No weights in the live Risk Score or inverse allocation.
 * Public release must not claim predictive power from contemporaneous margin-price correlations.
 * Snapshot data are official EOD numbers only after disclosure, possibly revised next day. */
(function(root){
"use strict";
const finite=x=>x!==null&&x!==""&&Number.isFinite(Number(x))?Number(x):null;
const FIELDS=["margin_balance_100m_twd","margin_delta_100m_twd","margin_maintenance_pct","short_balance_lots","short_delta_lots","short_margin_ratio_pct"];
const NAME={margin_delta_100m_twd:"融資增減（億元）",short_delta_lots:"融券增減（張）",margin_maintenance_pct:"融資維持率（%）",short_margin_ratio_pct:"券資比（%）"};
function fromScreenshot(data){
 if(!data||!Array.isArray(data.rows)||!Array.isArray(data.fields))throw Error("Missing raw provenance");
 const rows=data.rows.map(a=>Object.fromEntries(data.fields.map((key,i)=>[key,a[i]])));
 if(!rows.length||rows.some(x=>!/^\d{4}-\d\d-\d\d$/.test(x.date)))throw Error("Malformed dates");
 rows.sort((a,b)=>a.date.localeCompare(b.date));
 for(let i=1;i<rows.length;i++)if(rows[i].date===rows[i-1].date)throw Error("Duplicate day");
 return rows;
}
function joinIndex(credit,history,strict=true){
 if(!Array.isArray(credit)||!Array.isArray(history))throw Error("Data arrays required");
 const index=new Map(history.map(r=>[r.date,r.index]));
 let merged=[],missing=[],conflicts=[];
 for(const row of credit){
  const indexClose=finite(index.get(row.date)),snapshotClose=finite(row.taiex_close);
  if(indexClose===null){missing.push(row.date);continue}
  if(snapshotClose!==null&&Math.abs(indexClose-snapshotClose)>0.051){conflicts.push({date:row.date,indexClose,snapshotClose});continue}
  merged.push({...row,taiex_close:indexClose});
 }
 if(strict&&(missing.length||conflicts.length))throw Error("Index and margin data mismatch or incomplete");
 return {rows:merged,missing,conflicts};
}
function pearson(x,y){
 if(!Array.isArray(x)||x.length!==y.length||x.length<4)return null;
 const n=x.length,mx=x.reduce((a,b)=>a+b,0)/n,my=y.reduce((a,b)=>a+b,0)/n;
 let xy=0,xx=0,yy=0;for(let i=0;i<n;i++){const a=x[i]-mx,b=y[i]-my;xy+=a*b;xx+=a*a;yy+=b*b}
 return xx>0&&yy>0?Math.max(-1,Math.min(1,xy/Math.sqrt(xx*yy))):null;
}
function signedPairs(data,field,horizon){
 const x=[],y=[];
 for(let i=0;i<data.length;i++){
  const f=finite(data[i][field]),today=finite(data[i].taiex_close);if(f===null||today===null)continue;
  let ret=null;
  if(horizon===0)ret=finite(data[i].taiex_day_return_pct);
  else if(i+horizon<data.length){
   const next=finite(data[i+horizon].taiex_close);
   if(next!==null)ret=(next/today-1)*100;
  }
  if(ret===null)continue;x.push(f);y.push(ret);
 }
 return {x,y,n:x.length};
}
function audit(data,options={}){
 const fields=options.fields||Object.keys(NAME),horizons=options.horizons||[0,1,5];
 const metrics=[];for(const field of fields)for(const horizon of horizons){
  const {x,y,n}=signedPairs(data,field,horizon),r=pearson(x,y);
  metrics.push({field,name:NAME[field]||field,horizon,n,r,role:horizon===0?"SAME_DAY_NON_TRADEABLE":"EOD_TO_FUTURE",predictiveClaimPermitted:false});
 }
 const maxH=Math.max(...horizons),fwdMin=Number(options.minForwardObs??252);
 const decisions=metrics.map(x=>({...x,eligibleToPromote:x.horizon>0&&x.n>=fwdMin&&false}));
 const checks=[];
 for(let i=1;i<data.length;i++){
  const a=data[i-1],b=data[i],marginDiff=finite(b.margin_balance_100m_twd)-finite(a.margin_balance_100m_twd);
  const shortDiff=finite(b.short_balance_lots)-finite(a.short_balance_lots);
  if(Math.abs(marginDiff-finite(b.margin_delta_100m_twd))>.11)checks.push({date:b.date,field:"margin_delta_100m_twd",snapshot:b.margin_delta_100m_twd,adjacentDifference:Math.round(marginDiff*100)/100});
  if(Math.abs(shortDiff-finite(b.short_delta_lots))>1)checks.push({date:b.date,field:"short_delta_lots",snapshot:b.short_delta_lots,adjacentDifference:shortDiff});
 }
 return {n:data.length,dateRange:[data[0]?.date,data.at(-1)?.date],testCount:metrics.length,metrics:decisions,integrityWarnings:checks,decision:"OBSERVATION_ONLY",gate:{requireHistoricalSessions:fwdMin,requireStrictOOS:true,requireMultipleTestingCorrection:true,requireCostAdjustedEconomicBenefit:true,requireOfficialPublicationLag:true},limitations:["Same-day association is not a deployable next-day edge.","Daily margin disclosures arrive after market close; test only subsequent returns.","Maint. ratio is screenshot-only, not available from TWSE market credit summary.","5-day returns overlap, making ordinary correlation p-values optimistic.","Past-day published margin deltas can differ from differences of snapshot balances due to corrections."]};
}
const api={FIELDS,NAME,fromScreenshot,joinIndex,signedPairs,pearson,audit};
root.MarginShortResearch=api;if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof window!=="undefined"?window:typeof globalThis!=="undefined"?globalThis:{});
