import test from "node:test";
import assert from "node:assert/strict";
import {decide,inTradingWindow,taipeiParts,tick} from "./worker.mjs";
const t=iso=>new Date(iso);
const NOW=t("2026-10-21T02:30:00Z"); // 10:30 Taipei
const stamp=m=>new Date(NOW.getTime()-m*60000).toISOString();
const fresh=(age=20)=>({asOfDate:"2026-10-21",publishedAt:stamp(age),
  quality:"intraday-provisional-allmarket",rows:[{code:"2330"}],
  coverage:{valid:1710,total:1983,exchange:{"上市":{valid:980,total:1090},"上櫃":{valid:730,total:893}}}});
test("Taipei date and session holiday gating",()=>{
 assert.equal(taipeiParts(NOW).date,"2026-10-21");
 assert.equal(inTradingWindow(NOW),true);
 assert.equal(inTradingWindow(t("2026-10-26T03:00:00Z")),false);
 assert.equal(inTradingWindow(t("2026-10-24T03:00:00Z")),false);
 assert.equal(inTradingWindow(t("2026-10-21T01:05:00Z")),false);
 assert.equal(inTradingWindow(t("2026-10-21T05:43:00Z")),false);
});
test("healthy snapshot is not dispatched",()=>assert.equal(decide(NOW,fresh(),{},[]).dispatch,false));
test("yesterday snapshot is dispatched",()=>{
 const data=fresh();data.asOfDate="2026-10-20";
 assert.equal(decide(NOW,data,{},[]).dispatch,true);
});
test("same-day unavailable newer than latest is dispatched",()=>{
 assert.equal(decide(NOW,fresh(),{asOfDate:"2026-10-21",status:"unavailable",checkedAt:stamp(1)},[]).dispatch,true);
});
test("valid coverage and current timestamp required",()=>{
 assert.equal(decide(NOW,{...fresh(),publishedAt:stamp(-3)},{},[]).dispatch,true);
 const d=fresh();d.coverage.exchange["上櫃"].valid=50;
 assert.equal(decide(NOW,d,{},[]).dispatch,true);
});
test("running job suppresses duplicate dispatch",()=>{
 const runs=[{name:"TW Stock Dashboard",status:"in_progress",created_at:stamp(28)}];
 assert.equal(decide(NOW,fresh(90),{},runs).dispatch,false);
});
test("missing secret is safe and never dispatches",async()=>{
 assert.deepEqual(await tick(NOW,{},{}),{dispatch:false,reason:"missing-deployment-secret"});
});
