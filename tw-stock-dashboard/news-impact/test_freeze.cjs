"use strict";
const assert=require("node:assert/strict");
const {freeze}=require("./freeze_signals.cjs");
const when=new Date("2026-11-09T04:00:00.000Z");
const news=(id,title,publishedAt="2026-11-09T02:00:00Z")=>({id,title,publishedAt,source:"official headline sample"});
const records=[
 news("o1","OPEC announces oil production cuts"),
 news("o2","OPEC announces oil production cuts"), // duplicate same-day title
 news("o3","Oil falls on open as Trump says fresh Iran attacks 'unlikely'"), // observed, not future
 news("o4","DRAM報價下跌1%"), // sector proxy has no tradeable benchmark in 9-asset scorecard
 news("o5","Fed will not hike rates"), // negated
 news("o6","OPEC announces oil production cuts","2026-10-01T00:00:00Z") // expired
];
const first=freeze({records:[]},records,when);
assert.equal(first.records.length,1,"only one pre-outcome commodity scenario should freeze");
assert.equal(first.records[0].id,"o1");
assert.ok(first.records[0].signals.some(s=>s.asset==="WTI原油"&&s.direction===1));
assert.equal(first.records[0].classifierVersion,"2026-11-09-v1.3");
assert.equal(first.records[0].signals[0].predictionIsProbability,undefined);
const again=freeze(first,[...records,news("new","OPEC announces oil production cuts")],new Date("2026-11-09T06:00:00Z"));
assert.equal(again.records.length,1);
assert.deepEqual(again.records[0].signals,first.records[0].signals);
assert.equal(again.records[0].frozenAt,first.records[0].frozenAt);
const unseen=freeze({records:[]},[news("x","OPEC announces oil production cuts","2026-11-09T04:30:00Z")],when);
assert.equal(unseen.records.length,0,"future articles must not create predictions");
console.log("frozen directional signals: replay, duplicate, leak and observation tests passed");
