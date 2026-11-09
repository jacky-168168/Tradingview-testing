"use strict";
/* Freeze forward news hypotheses BEFORE the next eligible market baseline.
 * Never retroactively change a frozen rule/direction after outcomes mature.
 * Rule score is heuristic intensity, not calibrated probability.
 */
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const root=path.resolve(__dirname,"../docs");
const NewsImpactSector=require(path.join(root,"news-impact-sector.js"));
const NewsImpactTaxonomy=require(path.join(root,"news-impact-taxonomy.js"));
global.window={NewsImpactSector,NewsImpactTaxonomy};
const {classify,VERSION}=require(path.join(root,"news-impact.js"));
const MARKET_ASSETS=new Set(["美股S&P500","NASDAQ","台股","黃金","白銀","WTI原油","美元","美債殖利率","銅"]);
const INPUT=path.join(root,"data/news_impact/history.json");
const OUTPUT=path.join(root,"data/news_impact/predictions.json");
const MAX_AGE_MS=24*3600*1000;
const MAX_ROWS=5000;
function groupKey(item){
 const normalized=String(item.title||"").toLowerCase().replace(/\s+-\s+(ap news|reuters|bloomberg)\s*$/i,"")
  .normalize("NFKC").replace(/[\p{P}\p{S}\s]+/gu," ").trim();
 const date=String(item.publishedAt||"").slice(0,10);
 return crypto.createHash("sha256").update(date+"|"+normalized).digest("hex").slice(0,24);
}
function freeze(existing,events,now=new Date()){
 const byId=new Map((existing?.records||[]).filter(e=>e&&e.id&&e.frozenAt).map(e=>[e.id,e]));
 const seenGroups=new Set([...byId.values()].map(e=>e.group));
 let newRecords=0,skippedExpired=0,excludedNoSignal=0;
 for(const event of events||[]){
  if(!event||!event.id||!event.title||!event.publishedAt||byId.has(event.id))continue;
  const when=Date.parse(event.publishedAt),age=now.getTime()-when;
  if(!Number.isFinite(when)||age<0||age>MAX_AGE_MS){skippedExpired++;continue}
  const group=groupKey(event);
  if(seenGroups.has(group))continue;
  const classified=classify(event);
  const signals=classified.impacts.filter(x=>MARKET_ASSETS.has(x.asset)&&!x.mixed&&x.score!==0&&
   !classified.observations.some(o=>o.asset===x.asset)).map(x=>({
    asset:x.asset,direction:Math.sign(x.score),ruleScore:x.score,
    ruleIds:classified.hits.filter(r=>Number(r.impact?.[x.asset]||0)!==0).map(r=>r.id)
   }));
  if(!signals.length){excludedNoSignal++;continue}
  byId.set(event.id,{
   id:event.id,group,title:event.title,source:event.source||"",publishedAt:event.publishedAt,
   frozenAt:now.toISOString(),classifierVersion:VERSION,
   signalKind:"conditional_news_headline",predictionIsProbability:false,
   signals
  });
  seenGroups.add(group);newRecords++;
 }
 const records=[...byId.values()].sort((a,b)=>a.frozenAt.localeCompare(b.frozenAt)).slice(-MAX_ROWS);
 return {schema:1,generatedAt:now.toISOString(),classifierVersionCurrent:VERSION,
  definition:"Immutable observed-at-time conditional news directional hypotheses. Does not backfill older/matured items or predictions from after benchmark start.",
  minNForWinrate:30,records,refresh:{newRecords,skippedExpired,excludedNoSignal}};
}
function run(){
 if(!fs.existsSync(INPUT))throw Error("No published news archive");
 const news=JSON.parse(fs.readFileSync(INPUT,"utf8"));
 if(news.schema!==1||!Array.isArray(news.events))throw Error("Invalid archive schema");
 const prior=fs.existsSync(OUTPUT)?JSON.parse(fs.readFileSync(OUTPUT,"utf8")):{records:[]};
 const result=freeze(prior,news.events);
 fs.mkdirSync(path.dirname(OUTPUT),{recursive:true});
 fs.writeFileSync(OUTPUT,JSON.stringify(result,null,2)+"\n");
 console.log("freeze:",result.records.length,"stored",result.refresh.newRecords,"new;","excluded(no direction)",result.refresh.excludedNoSignal);
}
if(require.main===module)run();
module.exports={freeze,groupKey,MARKET_ASSETS};
