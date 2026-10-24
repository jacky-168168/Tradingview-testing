#!/usr/bin/env node
/* Generate a bounded, read-only six-agent audit artifact using committed data.
 * This script NEVER fetches outside data, writes brokerage orders or changes G ranks.
 * An artifact is evidence of research state, not a backtest or live trading result.
 */
"use strict";
const fs=require("node:fs"),path=require("node:path");
const {analyze}=require("../docs/agent-research-core.js");
const docs=path.resolve(__dirname,"../docs");
const get=p=>{try{return JSON.parse(fs.readFileSync(path.join(docs,p),"utf8"))}catch(e){
 console.error("SOURCE_UNAVAILABLE",p,e.code||e.message);return {};
}};
function report(now=new Date()){
 const data={
   daily:get("data/latest.json"),intraday:get("data/g_intraday/latest.json"),
   status:get("data/g_intraday/status.json"),news:get("data/market_events/latest.json")
 };
 const out=analyze(data,now);
 // The report is a reproducible audit: preserve per-agent facts, not arbitrary AI prose.
 return {
  ...out,
  provenance:{sources:["tw-stock-dashboard/docs/data/latest.json",
    "tw-stock-dashboard/docs/data/g_intraday/latest.json",
    "tw-stock-dashboard/docs/data/g_intraday/status.json",
    "tw-stock-dashboard/docs/data/market_events/latest.json"],
    generatedBy:"deterministic Node.js rule engine; NOT language model",execution:"paper research only",
    historyAvailable:false,performanceClaim:null,noBrokerExecution:true}
 };
}
if(require.main===module){
 const out=report();
 const destination=process.argv[2]||"six-agent-snapshot.json";
 fs.writeFileSync(destination,JSON.stringify(out,null,2)+"\n","utf8");
 console.log("SIX_AGENT_RESEARCH",JSON.stringify({checkedAt:out.checkedAt,
  asOfDate:out.asOfDate,mode:out.mode,stocks:out.counts.candidates,
  veto:out.counts.veto,review:out.counts.review,live:out.liveVerified}));
}
module.exports={report};