const test=require("node:test"),assert=require("node:assert/strict"),fs=require("fs"),path=require("path");
const lib=require("../docs/margin-short-research-engine.js");
const raw=JSON.parse(fs.readFileSync(path.join(__dirname,"../docs/data/research/margin_short_audit/screenshot_20260908_20261013.json"),"utf8"));
const a=lib.fromScreenshot(raw);
test("23 screenshot days sorted and validated",()=>{assert.equal(a.length,23);assert.equal(a[0].date,"2026-09-08");assert.equal(a.at(-1).date,"2026-10-13")});
test("same-day financing flow and next-day returns are different",()=>{
 const r=lib.audit(a),same=r.metrics.find(x=>x.field==="margin_delta_100m_twd"&&x.horizon===0),next=r.metrics.find(x=>x.field==="margin_delta_100m_twd"&&x.horizon===1);
 assert.ok(Math.abs(same.r-.405)<.003);assert.ok(Math.abs(next.r-.036)<.003);assert.equal(same.role,"SAME_DAY_NON_TRADEABLE");
 assert.equal(next.role,"EOD_TO_FUTURE");
});
test("do not treat untested same-day correlation as predictive edge",()=>{
 const x=lib.audit(a);assert.equal(x.decision,"OBSERVATION_ONLY");assert.ok(x.metrics.every(r=>!r.eligibleToPromote&&r.predictiveClaimPermitted===false));
 assert.ok(x.metrics.filter(r=>r.horizon===1).every(r=>r.n===22));
 assert.ok(x.metrics.filter(r=>r.horizon===5).every(r=>r.n===18));
});
test("comparison of adjacent balances flags actual revisional mismatches",()=>{
 const x=lib.audit(a).integrityWarnings;assert.ok(x.find(z=>z.date==="2026-10-01"&&z.field==="margin_delta_100m_twd"));
 assert.ok(x.find(z=>z.date==="2026-09-17"&&z.field==="short_delta_lots"));
});
test("a mismatched official index close is blocked",()=>{
 const h=a.map(x=>({date:x.date,index:x.taiex_close}));h[0].index+=20;
 assert.throws(()=>lib.joinIndex(a,h),/mismatch or incomplete/);
 assert.equal(lib.joinIndex(a,h,false).conflicts.length,1);
});
test("missing reports do not silently use later observed day as T+1",()=>{
 const h=a.map(x=>({date:x.date,index:x.taiex_close}));h.pop();
 assert.throws(()=>lib.joinIndex(a,h),/incomplete/);
});
