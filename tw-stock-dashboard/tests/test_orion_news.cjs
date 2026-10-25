"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const orion=require("../scripts/classify_orion_news.cjs");
const NOW=Date.parse("2026-10-25T03:00:00Z");
const row=(i=0)=>({id:"key"+i,title:i?"美國聯準會降息幅度仍需觀察":"台積電公布營收成長，但市場仍有疑慮",
 url:"https://www.cna.com.tw/news/afe/20261024000"+i+".aspx",
 publishedAt:"2026-10-24T23:00:00Z",source:"中央通訊社",themes:["AI／半導體"]});
const doc=items=>({schema:1,items:structuredClone(items),generatedAt:new Date(NOW).toISOString()});
const out=(a)=>({ok:true,status:200,json:async()=>({candidates:[{finishReason:"STOP",
 content:{parts:[{text:JSON.stringify({results:a})}]}}]})});
const tags=rows=>rows.map(p=>({id:orion.key(p),tone:"中性資訊／難判",
 theme:p.title.includes("台積電")?"AI／半導體":"總體／利率",confidence:"中",
 evidence:p.title.includes("台積電")?"營收成長，但市場仍有疑慮":"降息幅度仍需觀察"}));
test("real-transport style Gemini output is strictly verified",async()=>{
 const d=doc([row(0),row(1)]);let count=0;
 await orion.classify(d,{},{now:NOW,apiKey:"test-only",fetchFn:async(_,args)=>{
  count++;const body=JSON.parse(args.body);
  assert.equal(body.generationConfig.responseMimeType,"application/json");
  return out(tags(d.items));}});
 assert.equal(count,1);assert.equal(d.semantic.status,"verified");
 assert.equal(d.semantic.classified,2);assert.equal(d.semantic.neutral,2);
 assert.equal(d.semantic.noTrade,true);assert.equal(d.items[0].semantic.theme,"AI／半導體");
});
test("prior exact source citations cache without new API calls",async()=>{
 const d=doc([row(0)]);
 d.items[0].semantic=orion.check(d.items[0],tags(d.items)[0],"gemini-3.5-flash-lite");
 const n=doc([row(0)]);
 await orion.classify(n,d,{now:NOW,apiKey:"test-only",fetchFn:()=>{throw Error("must be cached")}});
 assert.equal(n.semantic.status,"cached");assert.equal(n.semantic.cached,1);
 assert.equal(n.semantic.inferenceCalls,0);
});
test("missing key never implies AI framing verification",async()=>{
 const d=doc([row(0)]);
 await orion.classify(d,{},{now:NOW,apiKey:""});
 assert.equal(d.semantic.status,"error");
 assert.equal(d.semantic.classified,0);assert.equal(d.semantic.noTrade,true);
});
test("model evidence must be exact source quote",async()=>{
 const d=doc([row(0)]);
 await orion.classify(d,{},{now:NOW,apiKey:"test-only",fetchFn:async()=>out([{
  ...tags(d.items)[0],evidence:"從來沒有出現過的爆炸利多"}])});
 assert.equal(d.semantic.status,"error");
 assert.equal(d.semantic.classified,0);
});
test("partial model batch failure reports uncovered headlines instead of faking neutrality",async()=>{
 const rows=Array.from({length:9},(_,i)=>({...row(0),id:"id"+i,
  url:"https://www.cna.com.tw/news/afe/202610240"+i+".aspx"})),d=doc(rows);
 let requests=0;
 await orion.classify(d,{},{now:NOW,apiKey:"test-only",fetchFn:async()=>{
  requests++;if(requests===2)throw Error("quota");
  return out(tags(rows.slice(0,8)));}});
 assert.equal(requests,2);assert.equal(d.semantic.status,"partial");
 assert.equal(d.semantic.classified,8);assert.equal(d.semantic.unclassified,1);
});


test("more than 24 fresh headlines are all classified when Gemini allows it",async()=>{
 const news=Array.from({length:41},(_,i)=>({...row(0),id:"article"+i,
  source:i%2?"Yahoo股市":"中央通訊社",url:"https://www.cna.com.tw/news/afe/s"+i+".aspx"}));
 const d=doc(news);let calls=0;
 await orion.classify(d,{},{now:NOW,apiKey:"unit-test",fetchFn:async(_url,args)=>{
  const j=JSON.parse(args.body),ids=JSON.parse(j.contents[0].parts[0].text).map(x=>x.id);
  calls++;return out(ids.map(id=>({id,tone:"中性資訊／難判",theme:"AI／半導體",
   confidence:"中",evidence:"營收成長，但市場仍有疑慮"})));
 }});
 assert.equal(calls,6);assert.equal(d.semantic.status,"verified");
 assert.equal(d.semantic.classified,41);assert.equal(d.semantic.unclassified,0);
 assert.equal(d.semantic.coveragePct,100);assert.equal(d.semantic.resumable,false);
 assert.equal(d.semantic.batchSize,8);
});
test("quota or request cap preserves verified articles for the next scheduled run",async()=>{
 const news=Array.from({length:33},(_,i)=>({...row(0),id:"id"+i,
  url:"https://www.cna.com.tw/news/afe/a"+i+".aspx"}));
 const d=doc(news);let calls=0;
 const mock=async(_url,args)=>{
  calls++;const ids=JSON.parse(JSON.parse(args.body).contents[0].parts[0].text).map(x=>x.id);
  return out(ids.map(id=>({id,tone:"偏利多報導",theme:"AI／半導體",
   confidence:"中",evidence:"營收成長，但市場仍有疑慮"})));
 };
 await orion.classify(d,{},{now:NOW,apiKey:"unit-test",maxCalls:2,fetchFn:mock});
 assert.equal(d.semantic.classified,16);assert.equal(d.semantic.unclassified,17);
 assert.equal(d.semantic.status,"partial");assert.equal(d.semantic.resumable,true);
 const next=doc(news);
 await orion.classify(next,d,{now:NOW,apiKey:"unit-test",fetchFn:mock});
 assert.equal(next.semantic.cached,16);assert.equal(next.semantic.classified,33);
 assert.equal(next.semantic.inferenceCalls,3);assert.equal(next.semantic.status,"verified");
 assert.equal(next.semantic.positive,33);
 assert.equal(next.semantic.eventTotals.positive,33);
});
test("topic-level differing headlines need independent publishers and unique events",()=>{
 const headlines=[
 {...row(0),id:"a",source:"中央通訊社",eventGroup:"x"},
 {...row(0),id:"b",source:"Yahoo股市",eventGroup:"y",
  title:"台積電可能獲利下修，但市場仍有疑慮"},
 {...row(0),id:"c",source:"Yahoo股市",eventGroup:"x"}
 ];
 headlines.forEach((p,i)=>p.semantic={
  ...orion.check(p,{tone:i===1?"偏利空報導":"偏利多報導",theme:"AI／半導體",
   confidence:"中",evidence:i===1?"獲利下修":"營收成長"},"gemini-3.5-flash-lite")
 });
 const data=doc(headlines);
 const m=orion.summarise(data,NOW,"gemini-3.5-flash-lite",0,0,"");
 assert.equal(m.classified,3);
 assert.equal(m.distinctEventsClassified,2);
 assert.equal(m.eventTotals.positive,1);assert.equal(m.eventTotals.negative,1);
 assert.equal(m.topicConflicts.length,1);
 assert.equal(m.topicConflicts[0].theme,"AI／半導體");
 assert.equal(m.topicConflicts[0].examples.length,2);
 assert(m.topicConflicts[0].examples.every(x=>x.url.startsWith("https://")));
});
