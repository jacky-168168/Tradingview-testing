"use strict";
const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const freshness=require("../docs/agent-freshness.js");
const now=new Date("2026-10-27T09:22:00Z");
const fixture=()=>({daily:{dataDate:"2026-10-22",risk:{date:"2026-10-22",score:11},models:{G:[{code:"2330"}]}},
 orion:{generatedAt:"2026-10-27T04:58:40Z",items:[{title:"新聞"}],coverage:{healthyFeeds:7,configuredFeeds:7},semantic:{classified:4,eligible:180}},
 social:{generatedAt:"2026-10-27T06:12:28Z",sources:{PTT:{status:"ok"}},items:[{title:"投資"}],stockHeat:{sourceDate:"2026-10-22"}},
 llm:{provider:"Google Gemini API",verifiedModelExecution:true,inferenceCalls:9,noTrade:true,generatedAt:"2026-10-24T21:24:19Z",evidenceDate:"2026-10-22"}});
test("separates stale G and Gemini from updated ORION and LUNA even when page was deployed today",()=>{
 const out=freshness.build(fixture(),now);
 assert.deepEqual(out.rows.map(x=>x.name),freshness.ROLES);
 assert.equal(out.rows[0].tone,"warn");assert.equal(out.rows[1].tone,"warn");
 assert.equal(out.rows[2].tone,"ok");assert.equal(out.rows[3].tone,"ok");
 assert.equal(out.rows[4].tone,"warn");assert.equal(out.rows[5].tone,"warn");
 assert.match(out.rows[3].detail,/2026-10-22/);
 assert.match(out.model.state,/歷史模型報告/);
 assert.match(out.model.detail,/10\/25/);
});
test("a new model report cannot be considered current when its input evidence is old",()=>{
 const f=fixture();f.llm.generatedAt="2026-10-27T08:00:00Z";
 assert.equal(freshness.build(f,now).model.tone,"warn");
 f.llm.evidenceDate="2026-10-27";
 assert.equal(freshness.build(f,now).model.tone,"ok");
});
test("invalid, future or missing timestamps cannot become successful fresh sources",()=>{
 const f=fixture();f.orion.generatedAt="2026-10-30T01:00:00Z";f.social.generatedAt="broken";
 f.llm.verifiedModelExecution=false;
 const out=freshness.build(f,now);
 assert.equal(out.rows[2].tone,"warn");assert.equal(out.rows[3].tone,"warn");
 assert.equal(out.model.tone,"warn");assert.match(out.model.state,/未取得/);
});
test("source cards are wired into HTML and do not invent a new analysis timestamp",()=>{
 const docs=path.join(__dirname,"../docs"),html=fs.readFileSync(path.join(docs,"agent-research.html"),"utf8");
 assert.match(html,/id="agentSourceStatus"/);assert.match(html,/src="\.\/agent-freshness\.js"/);
 const s=fs.readFileSync(path.join(docs,"agent-freshness.js"),"utf8");
 assert.match(s,/textContent/);assert.doesNotMatch(s,/innerHTML|placeOrder|broker\.buy/);
});
