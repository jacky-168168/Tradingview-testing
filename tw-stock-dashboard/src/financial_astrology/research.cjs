'use strict';
/* Reproducible *exploratory* event study, never a trading or predictive signal.
 * Only source-audited exchange trading sessions can be ingested. Missing data -> N/A.
 * Descriptive OOS + HAC/FDR approximations are NOT a validated trading strategy.
 */
const fs=require('node:fs'),path=require('node:path');
const HORIZONS=[1,3,5,10,20,60,90,180,360];
const MARKETS={SPX:'America/New_York',IXIC:'America/New_York',NDX:'America/New_York',SOX:'America/New_York',DAX:'Europe/Berlin',FTSE:'Europe/London',CAC:'Europe/Paris',STOXX50:'Europe/Paris',TAIEX:'Asia/Taipei'};
const HYPOTHESES={
 new_moon:e=>e.kind==='moon-quarter'&&e.name==='新月',
 full_moon:e=>e.kind==='moon-quarter'&&e.name==='滿月',
 mercury_retrograde:e=>e.kind==='station'&&e.body==='Mercury'&&e.motionAfter==='retrograde',
 mars_jupiter_conjunction:e=>e.kind==='aspect'&&e.angle===0&&[e.first,e.second].sort().join('/')==='Jupiter/Mars',
 jupiter_saturn_conjunction:e=>e.kind==='aspect'&&e.angle===0&&[e.first,e.second].sort().join('/')==='Jupiter/Saturn',
 saturn_uranus_square:e=>e.kind==='aspect'&&e.angle===90&&[e.first,e.second].sort().join('/')==='Saturn/Uranus'
};
function localDate(iso,timezone){
 const d=new Date(iso);
 if(!Number.isFinite(d.getTime()))throw Error('invalid UTC event');
 const parts=new Intl.DateTimeFormat('en-US',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
 const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
 return p.year+'-'+p.month+'-'+p.day;
}
function readPrices(csv){
 const lines=csv.trim().split(/\r?\n/),header=lines.shift().split(',').map(x=>x.trim().toLowerCase());
 const idx=k=>header.indexOf(k),dc=idx('date'),cc=idx('close'),hc=idx('high'),lc=idx('low');
 if(dc<0||cc<0)throw Error('CSV requires date,close');
 const prices=lines.filter(x=>x.trim()).map(line=>{
  const a=line.split(','),date=a[dc]?.trim(),close=Number(a[cc]);
  const high=hc<0||a[hc]===''?null:Number(a[hc]),low=lc<0||a[lc]===''?null:Number(a[lc]);
  return {date,close,high,low};
 });
 for(let i=0;i<prices.length;i++){
  const p=prices[i];
  if(!/^\d{4}-\d{2}-\d{2}$/.test(p.date)||!Number.isFinite(p.close)||p.close<=0||
    (i>0&&prices[i-1].date>=p.date)||(p.high!==null&&(!Number.isFinite(p.high)||p.high<p.close))||
    (p.low!==null&&(!Number.isFinite(p.low)||p.low>p.close||p.low<=0)))
   throw Error('invalid or unsorted market OHLC; do not insert synthetic sessions');
 }
 return prices;
}
function mean(a){return a.reduce((s,x)=>s+x,0)/a.length;}
function median(a){const b=[...a].sort((x,y)=>x-y),i=Math.floor(b.length/2);return b.length%2?b[i]:(b[i-1]+b[i])/2;}
function variance(a){const m=mean(a);return a.length<2?NaN:a.reduce((s,x)=>s+(x-m)**2,0)/(a.length-1);}
function normalTail(x){const z=Math.abs(x)/Math.sqrt(2),t=1/(1+0.3275911*z);
 const erf=1-(((((1.061405429*t-1.453152027)*t)+1.421413741)*t-0.284496736)*t+0.254829592)*t*Math.exp(-z*z);
 return Math.max(0,Math.min(1,1-erf));
}
function hacPValue(values,reference,lag){
 const n=values.length;if(n<10)return null;
 const residual=values.map(v=>v-reference),center=mean(residual);
 const x=residual.map(v=>v-center);
 let omega=x.reduce((s,v)=>s+v*v,0)/n;
 for(let k=1;k<=Math.min(lag,n-1);k++){
  const gamma=x.slice(k).reduce((s,v,i)=>s+v*x[i],0)/n;
  omega+=2*(1-k/(lag+1))*gamma;
 }
 const se=Math.sqrt(Math.max(0,omega)/n);
 return se>0?+normalTail(mean(residual)/se).toFixed(7):null;
}
function ciBootstrap(returns,iterations=500,seed=20261115){
 let state=seed>>>0;const random=()=>{state^=state<<13;state^=state>>>17;state^=state<<5;return(state>>>0)/4294967296;};
 const res=[];
 for(let i=0;i<iterations;i++){
  let sum=0;for(let j=0;j<returns.length;j++)sum+=returns[Math.min(returns.length-1,Math.floor(random()*returns.length))];
  res.push(sum/returns.length);
 }
 res.sort((x,y)=>x-y);
 return [res[Math.floor(.025*(res.length-1))],res[Math.ceil(.975*(res.length-1))]];
}
function bhAdjust(rows){
 const valid=rows.filter(r=>Number.isFinite(r.pHac)),ordered=[...valid].sort((a,b)=>a.pHac-b.pHac),m=ordered.length;
 let adjusted=1;
 for(let i=m-1;i>=0;i--){adjusted=Math.min(adjusted,ordered[i].pHac*m/(i+1));ordered[i].qFdr=+adjusted.toFixed(7);}
 return rows;
}
function study(events,prices,timezone,horizon){
 if(!HORIZONS.includes(horizon))throw Error('bad horizon');
 if(!prices.length)return {status:'unavailable',reason:'no-price-history'};
 const sorted=[...events].sort((a,b)=>a.utc.localeCompare(b.utc)),samples=[];
 let lastExit=-1;
 for(const event of sorted){
  const date=localDate(event.utc,timezone),idx=prices.findIndex(p=>p.date>date);
  if(idx<0||idx+horizon>=prices.length||idx<=lastExit)continue;
  const initial=prices[idx].close,ret=100*(prices[idx+horizon].close/initial-1);
  let peak=initial,drawdown=0;const holding=prices.slice(idx,idx+horizon+1);
  for(const p of holding){peak=Math.max(peak,p.close);drawdown=Math.min(drawdown,100*(p.close/peak-1));}
  const withHilo=holding.every(p=>p.high!==null&&p.low!==null);
  const mfe=withHilo?100*(Math.max(...holding.map(p=>p.high))/initial-1):null;
  const mae=withHilo?100*(Math.min(...holding.map(p=>p.low))/initial-1):null;
  samples.push({eventId:event.id,entryDate:prices[idx].date,exitDate:prices[idx+horizon].date,retPct:ret,drawdownPct:drawdown,mfePct:mfe,maePct:mae});
  lastExit=idx+horizon; // prevent correlated overlapping forward windows
 }
 if(samples.length<10)return {status:'insufficient',sampleCount:samples.length,reason:'fewer-than-10-nonoverlapping-events'};
 const returns=samples.map(x=>x.retPct),baseline=[];
 for(let i=0;i+horizon<prices.length;i++)baseline.push(100*(prices[i+horizon].close/prices[i].close-1));
 const avg=mean(returns),base=mean(baseline),ci=ciBootstrap(returns);
 const split=Math.floor(returns.length*.7),oos=returns.slice(split);
 const optionalMean=(key)=>samples.every(s=>s[key]!==null)?+mean(samples.map(s=>s[key])).toFixed(5):null;
 return {status:'exploratory',sampleCount:samples.length,
  meanReturnPct:+avg.toFixed(5),medianReturnPct:+median(returns).toFixed(5),
  winRatePct:+(100*returns.filter(x=>x>0).length/returns.length).toFixed(3),
  returnStdPct:+Math.sqrt(variance(returns)).toFixed(5),
  baselineMeanPct:+base.toFixed(5),excessReturnPct:+(avg-base).toFixed(5),
  ci95MeanPct:ci.map(v=>+v.toFixed(5)),pHac:hacPValue(returns,base,Math.min(horizon,15)),qFdr:null,
  oosSampleCount:oos.length,oosMeanReturnPct:+mean(oos).toFixed(5),oosVerified:false,
  avgDrawdownPct:+mean(samples.map(s=>s.drawdownPct)).toFixed(5),
  worstDrawdownPct:+Math.min(...samples.map(s=>s.drawdownPct)).toFixed(5),
  avgMfePct:optionalMean('mfePct'),avgMaePct:optionalMean('maePct'),
  limitations:['HAC and bootstrap are exploratory; event selection, survivorship and market regimes not fully controlled',
   'next-session CLOSE only, not an executable next-open strategy','chronological 70/30 descriptive holdout, not independently validated OOS',
   'FDR across tested market/event/horizon hypotheses does not establish causal forecasting'],
  firstEntry:samples[0].entryDate,lastEntry:samples.at(-1).entryDate};
}
function run(catalogueDir,marketFileDir,outPath){
 const archive=JSON.parse(fs.readFileSync(path.join(catalogueDir,'historical-events.json'),'utf8'));
 if(!Array.isArray(archive.events))throw Error('invalid astronomical historical archive');
 const results={},sources={},tests=[];
 for(const [market,tz] of Object.entries(MARKETS)){
  const csv=path.join(marketFileDir,market+'.csv'),meta=path.join(marketFileDir,market+'.source.json');
  if(!fs.existsSync(csv)||!fs.existsSync(meta))continue;
  const source=JSON.parse(fs.readFileSync(meta,'utf8'));
  if(!source.url||!source.retrievedAt||!source.priceType||source.licenseReviewed!==true)continue;
  const prices=readPrices(fs.readFileSync(csv,'utf8'));sources[market]=source;results[market]={};
  for(const [key,predicate] of Object.entries(HYPOTHESES)){
   const events=archive.events.filter(predicate);results[market][key]={};
   for(const horizon of HORIZONS){
    const value=study(events,prices,tz,horizon);
    results[market][key][horizon]=value;if(Number.isFinite(value.pHac))tests.push(value);
   }
  }
 }
 bhAdjust(tests);
 const report={schema:2,generatedAt:new Date().toISOString(),
  status:Object.keys(results).length?'exploratory':'unavailable',
  method:'UTC event -> next exchange-local trading session CLOSE -> h sessions later CLOSE',
  hypotheses:Object.keys(HYPOTHESES),results,sources,
  notice:'Historical descriptive research; no causal or validated predictive edge; no trades or original Risk Score changed.'};
 fs.mkdirSync(path.dirname(outPath),{recursive:true});fs.writeFileSync(outPath,JSON.stringify(report,null,2)+'\n');
 return report;
}
module.exports={HORIZONS,MARKETS,HYPOTHESES,localDate,readPrices,study,hacPValue,ciBootstrap,bhAdjust,run};
if(require.main===module){
 const root=path.resolve(__dirname,'../../');
 const out=run(path.join(root,'research/financial_astrology'),path.join(root,'research/financial_astrology/markets'),
   path.join(root,'docs/data/financial_astrology/stats.json'));
 console.log('Event research status: '+out.status);
}
