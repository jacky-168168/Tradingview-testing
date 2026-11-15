'use strict';
/* Event study: close-only, conservative next-session-close entry.
 * This is exploratory. Not all confounders/FDR/OOS verification are solved here.
 * Never mark any result "verified" without separate rigorous model review.
 */
const fs=require('node:fs'),path=require('node:path');
const HORIZONS=[1,3,5,10,20,60,90,180,360];
const MARKETS={SPX:'America/New_York',IXIC:'America/New_York',NDX:'America/New_York',SOX:'America/New_York',DAX:'Europe/Berlin',FTSE:'Europe/London',CAC:'Europe/Paris',STOXX50:'Europe/Paris',TAIEX:'Asia/Taipei'};
function localDate(iso,timezone){
 const d=new Date(iso);
 if(!Number.isFinite(d.getTime()))throw Error('invalid UTC event');
 const a=new Intl.DateTimeFormat('en-US',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(d);
 const p=Object.fromEntries(a.map(x=>[x.type,x.value]));
 return p.year+'-'+p.month+'-'+p.day;
}
function readPrices(csv){
 const lines=csv.trim().split(/\r?\n/),head=lines.shift().split(',').map(x=>x.trim().toLowerCase());
 const dateCol=head.indexOf('date'),closeCol=head.indexOf('close');
 if(dateCol<0||closeCol<0)throw Error('CSV requires date,close');
 const prices=lines.filter(x=>x.trim()).map(line=>{
   const cols=line.split(',');return {date:cols[dateCol]?.trim(),close:Number(cols[closeCol])};
 });
 for(let i=0;i<prices.length;i++){
   const p=prices[i];
   if(!/^\d{4}-\d{2}-\d{2}$/.test(p.date)||!Number.isFinite(p.close)||p.close<=0||(i>0&&prices[i-1].date>=p.date))
     throw Error('prices must have strictly increasing ISO trading dates and positive close');
 }
 return prices;
}
function mean(a){return a.reduce((s,x)=>s+x,0)/a.length;}
function median(a){const b=[...a].sort((x,y)=>x-y),i=Math.floor(b.length/2);return b.length%2?b[i]:(b[i-1]+b[i])/2;}
function study(events,prices,timezone,horizon){
 if(!HORIZONS.includes(horizon))throw Error('bad horizon');
 if(!prices.length)return {status:'unavailable',reason:'no-price-history'};
 const used=new Set(),samples=[];
 for(const event of [...events].sort((a,b)=>a.utc.localeCompare(b.utc))){
   const date=localDate(event.utc,timezone),at=prices.findIndex(p=>p.date>date);
   if(at<0||at+horizon>=prices.length||used.has(at))continue;
   used.add(at);
   const ret=100*(prices[at+horizon].close/prices[at].close-1);
   samples.push({eventId:event.id,date:event.utc,entryDate:prices[at].date,exitDate:prices[at+horizon].date,retPct:ret});
 }
 if(samples.length<10)return {status:'insufficient',sampleCount:samples.length,reason:'fewer-than-10-independent-entry-sessions'};
 const rets=samples.map(x=>x.retPct),baseline=[];
 for(let i=0;i+horizon<prices.length;i++)baseline.push(100*(prices[i+horizon].close/prices[i].close-1));
 const avg=mean(rets),base=mean(baseline);
 const oosStart=Math.floor(rets.length*.7),oos=rets.slice(oosStart);
 return {status:'exploratory',sampleCount:samples.length,meanReturnPct:+avg.toFixed(5),
   medianReturnPct:+median(rets).toFixed(5),winRatePct:+(100*rets.filter(x=>x>0).length/rets.length).toFixed(3),
   baselineMeanPct:+base.toFixed(5),excessReturnPct:+(avg-base).toFixed(5),
   oosSampleCount:oos.length,oosMeanReturnPct:+mean(oos).toFixed(5),oosVerified:false,
   limitations:['close-only conservative next-session entry','overlapping future holding windows not independent',
   'unadjusted confounders and FDR','holdout descriptive only; no claim of validated predictive edge'],
   sourceStatus:'external-supplied-market-price-csv',
   firstEntry:samples[0].entryDate,lastEntry:samples.at(-1).entryDate};
}
function run(catalogueDir,marketFileDir,outPath){
 const catalogue=JSON.parse(fs.readFileSync(path.join(catalogueDir,'historical-events.json'),'utf8'));
 if(!Array.isArray(catalogue.events))throw Error('bad event catalogue');
 const results={};const sources={};
 for(const [market,tz] of Object.entries(MARKETS)){
  const csv=path.join(marketFileDir,market+'.csv'),meta=path.join(marketFileDir,market+'.source.json');
  if(!fs.existsSync(csv)||!fs.existsSync(meta))continue;
  const source=JSON.parse(fs.readFileSync(meta,'utf8'));
  if(!source.url||!source.retrievedAt||!source.priceType||!source.licenseReviewed)continue;
  const prices=readPrices(fs.readFileSync(csv,'utf8'));results[market]={};
  for(const horizon of HORIZONS)results[market][horizon]=study(catalogue.events,prices,tz,horizon);
  sources[market]=source;
 }
 const doc={schema:1,generatedAt:new Date().toISOString(),status:Object.keys(results).length?'exploratory':'unavailable',
   method:'next-trading-session close to h-trading-sessions later close',timeBasis:'UTC events and exchange-local calendar',
   results,sources,notice:'No astrology-stock-market causal or predictive claim; rigorous significance and walk-forward remain pending'};
 fs.mkdirSync(path.dirname(outPath),{recursive:true});fs.writeFileSync(outPath,JSON.stringify(doc,null,2)+'\n');
 return doc;
}
module.exports={HORIZONS,MARKETS,localDate,readPrices,study,run};
if(require.main===module){
 const root=path.resolve(__dirname,'../../');
 const out=run(path.join(root,'research/financial_astrology'),path.join(root,'research/financial_astrology/markets'),path.join(root,'docs/data/financial_astrology/stats.json'));
 console.log('Event research status:',out.status);
}
