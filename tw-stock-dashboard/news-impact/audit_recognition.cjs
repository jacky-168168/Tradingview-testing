"use strict";
/** Measure what the live headline engine actually understands.
 *  Topic recognition != directional prediction; no invented confidence.
 *  Audit is descriptive of current fresh feed, not an accuracy score.
 */
const fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,"../docs");
global.window={
 NewsImpactSector:require(path.join(root,"news-impact-sector.js")),
 NewsImpactTaxonomy:require(path.join(root,"news-impact-taxonomy.js"))
};
const {classify,VERSION}=require(path.join(root,"news-impact.js"));
const INPUT=path.join(root,"data/market_events/latest.json");
const OUTPUT=path.join(root,"data/news_impact/recognition_audit.json");
function reason(c){
 if(c.impacts.length)return "conditional_direction";
 if(c.observations.length)return "reported_market_move_not_prediction";
 if(c.hits.length)return "mechanism_or_event_known_direction_unverified";
 if(c.topicEvidence==="source_category_only")return "source_category_only";
 if(c.topics.length)return "headline_topic_only";
 return "unrecognized";
}
function audit(data,when=new Date()){
 if(!Array.isArray(data?.items))throw Error("Invalid market events feed");
 const seen=new Set(),items=[];
 for(const item of data.items){
  if(item?.type!=="news"||!item.title||!item.url)continue;
  const key=String(item.title).normalize("NFKC").toLowerCase().replace(/\s+/g," ").trim();
  if(seen.has(key))continue;seen.add(key);
  items.push(item);
 }
 const rows=items.map(item=>{
  const c=classify(item);
  return {id:item.id,source:item.source||"",title:item.title||"",
   topics:c.topics||[],topicEvidence:c.topicEvidence||"none",
   recognition:reason(c),ruleIds:c.hits.map(h=>h.id),
   directionalAssets:c.impacts.filter(x=>!x.mixed&&x.score!==0).map(x=>x.asset),
   reportedAssets:c.observations.map(x=>x.asset),
   sourceReview:/PTT|論壇|鉅亨號|股市爆料|討論牆/i.test((item.source||"")+" "+(item.category||""))};
 });
 const counts={},topics={},sources={};
 for(const row of rows){
  counts[row.recognition]=(counts[row.recognition]||0)+1;
  for(const t of row.topics)topics[t]=(topics[t]||0)+1;
  if(row.sourceReview)sources["forum_or_commentary"]=(sources["forum_or_commentary"]||0)+1;
 }
 const count=rows.length,dir=rows.filter(r=>r.directionalAssets.length).length;
 const obs=rows.filter(r=>r.reportedAssets.length).length;
 const weak=rows.filter(r=>r.topicEvidence==="source_category_only").length;
 const unclassified=rows.filter(r=>r.recognition==="unrecognized").length;
 return {
  schema:1,generatedAt:when.toISOString(),
  sourceNewsGeneratedAt:data.generatedAt||null,sourceNewsStatus:data.status||null,
  classifierVersion:VERSION,newsCount:count,
  recognizedHeadlineTopicCount:rows.filter(r=>r.topicEvidence==="headline_terms").length,
  sourceCategoryFallbackCount:weak,
  contextOrEventOnlyCount:rows.filter(r=>r.recognition==="headline_topic_only"||r.recognition==="mechanism_or_event_known_direction_unverified").length,
  directionalHeadlineCount:dir,
  reportedMarketMoveCount:obs,
  unrecognizedCount:unclassified,
  countsByRecognition:counts,countsByTopic:topics,sourceReviewCounts:sources,
  notAccuracy:true,notHitRate:true,
  caveats:[
   "A title matching generic topic keywords does not prove correct semantic understanding.",
   "An observed price change is not a forecast and cannot be counted as predictive accuracy.",
   "A direction is published only for narrowly-scoped identifiable mechanisms; unknowns are intentionally preserved.",
   "Full article facts, original publication times and multi-source verification are not available in this feed."
  ],
  unresolved:rows.filter(r=>r.recognition==="unrecognized"||r.recognition==="headline_topic_only"||
     r.recognition==="source_category_only")
   .slice(0,80).map(({id,title,source,topics,recognition})=>({id,title,source,topics,reason:recognition})),
 };
}
function run(){
 const news=JSON.parse(fs.readFileSync(INPUT,"utf8"));
 const result=audit(news);
 fs.mkdirSync(path.dirname(OUTPUT),{recursive:true});
 const tmp=OUTPUT+".tmp";
 fs.writeFileSync(tmp,JSON.stringify(result,null,2)+"\n");
 fs.renameSync(tmp,OUTPUT);
 console.log("recognition audit:",JSON.stringify({
  version:result.classifierVersion,news:result.newsCount,
  directional:result.directionalHeadlineCount,observed:result.reportedMarketMoveCount,
  contextOnly:result.contextOrEventOnlyCount,sourceOnly:result.sourceCategoryFallbackCount,
  unrecognized:result.unrecognizedCount
 }));
}
if(require.main===module)run();
module.exports={audit,reason};
