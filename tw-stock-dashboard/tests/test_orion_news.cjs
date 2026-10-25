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
const tags=rows=>rows.map((p,i)=>({id:orion.key(p),tone:i?"中性資訊／難判":"中性資訊／難判",
 theme:i?"總體／利率":"AI／半導體",confidence:"中",
 evidence:i?"降息幅度仍需觀察":"營收成長，但市場仍有疑慮"}));
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
  ...tags(d.items)[0],evidence:"從來沒有出現過的爆炸利多"})]});
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
