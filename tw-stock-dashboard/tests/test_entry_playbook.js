/* Regression tests for close-only entry guide and explicit fail-closed intraday behavior. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const {assess,checkedReport,parts}=require("../docs/entry-playbook.js");
const report={version:"MARKET_ENTRY_PLAYBOOK_2026_V1",source2025ValidationOnly:true,research:{marketDays:728},policy:{risk60:"minimum"},
  comparisons:{G20_RISK60:{validation:{n:93,meanNetPct:4.761},holdout:{meanNetPct:7.184}},
    D10_RISK60:{validation:{meanNetPct:1.478},holdout:{meanNetPct:1.727}}}};
const t=s=>new Date(s);
function market(score=85,breadth=65,top="⚪ Top Watch",day="2026-10-08"){
 const risk={date:day,score,breadth,topState:top,bottomState:"⚪ Bottom Watch"};
 return {dataDate:day,risk};
}
assert.equal(checkedReport(report),true);
assert.equal(checkedReport({...report,source2025ValidationOnly:false}),false);
assert.equal(parts(t("2026-10-12T08:58:00+08:00")).minute,538);
let x=assess(market(46),null,report,t("2026-10-11T15:25:00+08:00"));
assert.equal(x.tone,"stop");assert.equal(x.immediateBuyConfirmed,false);
x=assess(market(85),null,report,t("2026-10-11T15:25:00+08:00"));
assert.equal(x.tone,"ready");assert.equal(x.immediateBuyConfirmed,false);
x=assess(market(85),null,report,t("2026-10-12T09:30:00+08:00"));
assert.equal(x.tone,"watch");assert.equal(x.inCash,true);assert.equal(x.immediateBuyConfirmed,false);
assert.match(x.status,/盤中尚未確認/);assert.match(x.basis,/即時/);
x=assess(market(85),{valid:true,sourceDate:"2026-10-08",nextDate:"2026-10-12",base:85,pct:-1.305},
  report,t("2026-10-12T08:58:00+08:00"));
assert.equal(x.tone,"stop");assert.equal(x.nightDrop,true);
x=assess(market(85),{valid:true,sourceDate:"2026-10-07",nextDate:"2026-10-12",base:85,pct:-2},
  report,t("2026-10-12T08:58:00+08:00"));
assert.equal(x.nightDrop,false);assert.equal(x.immediateBuyConfirmed,false);
x=assess(market(90,30,"🟠 Top Reversal Attempt"),null,report,t("2026-10-11T15:30:00+08:00"));
assert.equal(x.tone,"stop");
x=assess(market(90,30),null,report,t("2026-10-11T15:30:00+08:00"));
assert.equal(x.tone,"watch");
x=assess(market(90,65),null,report,t("2026-10-26T15:30:00+08:00"));
assert.equal(x.tone,"unknown");assert.equal(x.immediateBuyConfirmed,false);
x=assess(market(90,65),null,null,t("2026-10-11T15:30:00+08:00"));
assert.equal(x.validStudy,false);assert.equal(x.immediateBuyConfirmed,false);
assert.ok(!fs.readFileSync("tw-stock-dashboard/docs/entry-playbook.js","utf8").includes("executeTrade("));
const page=fs.readFileSync("tw-stock-dashboard/docs/index.html","utf8");
const style=fs.readFileSync("tw-stock-dashboard/docs/entry-playbook.css","utf8");
for(const k of ["entryPlaybook","entryPlaybookStatus","entryPlaybookInstant","entryPlaybookTiming","entryPlaybookFacts","entryPlaybookResearch","EntryPlaybook.refresh(DATA)","EntryPlaybook.applyPremarket(x)"])assert.ok(page.includes(k),"Missing "+k);
assert.ok(page.indexOf('id="entryPlaybook"')<page.indexOf('id="marketCommand"'));
assert.ok(style.includes("@media(max-width:650px)"));
console.log("PASS 2026 market entry playbook: night-session timestamp, official-score gates, open-market no-live fail-closed, Top veto and homepage layout");
