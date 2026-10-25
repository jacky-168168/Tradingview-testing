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
  title:row(0).title+" 報導編號 "+i,
  url:"https://www.cna.com.tw/news/afe/202610240"+i+".aspx"})),d=doc(rows);
 let requests=0;
 await orion.classify(d,{},{now:NOW,apiKey:"test-only",fetchFn:async()=>{
  requests++;if(requests===2)throw Error("quota");
  return out(tags(rows.slice(0,8)));},sleepFn:async()=>{}});
 assert.equal(requests,2);assert.equal(d.semantic.status,"partial");
 assert.equal(d.semantic.classified,8);assert.equal(d.semantic.unclassified,1);
});

test("ORION no longer truncates to 24: 143 independent articles are all model-classified",async()=>{
 const rows=Array.from({length:143},(_,i)=>({...row(0),id:"id"+i,
  title:row(0).title+" 第 "+i+" 篇",url:"https://www.cna.com.tw/news/afe/example"+i+".aspx"}));
 const data=doc(rows);let calls=0,rests=0;
 await orion.classify(data,{},{now:NOW,apiKey:"test-only",
  fetchFn:async(_,args)=>{calls++;
   const input=JSON.parse(args.body).contents[0].parts[0].text;
   const posted=JSON.parse(input);
   const batch=posted.map(y=>rows.find(x=>orion.key(x)===y.id));
   assert(batch.every(Boolean));assert(batch.length<=8);
   return out(tags(batch));
  },sleepFn:async(ms)=>{rests++;assert(ms>=4000)}
 });
 assert.equal(calls,18);assert.equal(rests,17);
 assert.equal(data.semantic.status,"verified");assert.equal(data.semantic.classified,143);
 assert.equal(data.semantic.unclassified,0);assert.equal(data.semantic.coveragePct,100);
 assert.equal(data.semantic.inferenceCalls,18);assert.equal(data.semantic.attemptedCalls,18);
});
test("ORION reuses only exact validated headlines across sources, not falsely merging events",async()=>{
 const a=row(0),b={...row(0),id:"other-id",source:"Yahoo股市",
  url:"https://tw.stock.yahoo.com/news/unique-article"};
 const c={...row(0),id:"another",title:row(0).title+" 後續有疑慮",
  url:"https://www.cna.com.tw/news/afe/another.aspx"};
 const d=doc([a,b,c]);let calls=0;
 await orion.classify(d,{},{now:NOW,apiKey:"test-only",fetchFn:async(_,args)=>{
  calls++;const ids=JSON.parse(JSON.parse(args.body).contents[0].parts[0].text);
  return out(tags(ids.map(z=>d.items.find(p=>orion.key(p)===z.id))));
 },sleepFn:async()=>{}});
 assert.equal(calls,1);assert.equal(d.semantic.classified,3);
 assert.equal(d.semantic.headlineReuse,1);
 assert.equal(d.items[1].semantic.reusedIdenticalHeadline,true);
 assert.equal(d.items[2].semantic.reusedIdenticalHeadline,undefined);
});
test("ORION next run classifies previous missing, while cached decisions do not use calls",async()=>{
 const rows=Array.from({length:14},(_,i)=>({...row(0),id:"article"+i,
  title:row(0).title+" 案例 "+i,url:"https://www.cna.com.tw/news/afe/art"+i+".aspx"}));
 const first=doc(rows);
 const api=async(_,args)=>{
  const req=JSON.parse(JSON.parse(args.body).contents[0].parts[0].text);
  return out(tags(req.map(r=>rows.find(p=>orion.key(p)===r.id))));
 };
 await orion.classify(first,{},{now:NOW,apiKey:"unit",maxArticlesPerRun:8,fetchFn:api,sleepFn:async()=>{}});
 assert.equal(first.semantic.status,"partial");assert.equal(first.semantic.classified,8);
 const next=doc(rows);
 await orion.classify(next,first,{now:NOW,apiKey:"unit",fetchFn:api,sleepFn:async()=>{}});
 assert.equal(next.semantic.status,"verified");assert.equal(next.semantic.cached,8);
 assert.equal(next.semantic.inferenceCalls,1);assert.equal(next.semantic.classified,14);
});
test("Gemini quota refusal stops cleanly and preserves all source-verifiable cached results",async()=>{
 const rows=Array.from({length:17},(_,i)=>({...row(0),id:"item"+i,
  title:row(0).title+" 觀察 "+i,url:"https://www.cna.com.tw/news/afe/quota"+i+".aspx"}));
 const d=doc(rows);let n=0;
 await orion.classify(d,{},{now:NOW,apiKey:"unit",fetchFn:async(_,args)=>{
  n++;if(n>1)return {ok:false,status:429};
  const inp=JSON.parse(JSON.parse(args.body).contents[0].parts[0].text);
  return out(tags(inp.map(x=>rows.find(p=>orion.key(p)===x.id))));
 },sleepFn:async()=>{}});
 assert.equal(n,2);assert.equal(d.semantic.status,"partial");assert.equal(d.semantic.classified,8);
 assert.equal(d.semantic.unclassified,9);assert.equal(d.semantic.quotaLimited,true);
 assert.match(d.semantic.error,/HTTP 429/);
});
