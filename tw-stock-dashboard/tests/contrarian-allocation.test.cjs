const test=require("node:test"),assert=require("node:assert/strict");
const {calculateContrarian}=require("../docs/dynamic-exposure.js");
const now=new Date("2026-10-13T17:31:00+08:00");
const m=(index=100,score=70,ma20=index)=>({risk:{date:"2026-10-13",score,index,ma20,priorHigh120:100,topState:"⚪ Normal"}});
test("rallying toward high raises cash allocation, lower index releases cash",()=>{
 const near=calculateContrarian(m(100),now),down5=calculateContrarian(m(94),now),down15=calculateContrarian(m(84),now);
 assert.ok(near.cash>down5.cash);assert.ok(down5.cash>down15.cash);
 assert.deepEqual([near.target,down5.target,down15.target],[30,50,80]);
});
test("high MA20 stretch overrides raw target to protect cash",()=>{
 const x=calculateContrarian(m(99,78,90),now);assert.equal(x.target,25);assert.equal(x.cash,75);
});
test("Risk OFF does not erase reserve budget but stops new buying",()=>{
 const x=calculateContrarian(m(94,36),now);assert.equal(x.target,50);assert.equal(x.allowedNew,false);
 assert.match(x.reason,/Risk Score <60/);
});
test("confirmed market top is distinct from a non-confirmed Top Watch",()=>{
 const confirmed=m(94,79);confirmed.risk.topState="🔴 Strong Top Reversal";
 const wait=m(94,79);wait.risk.topState="⚪ Top Watch";
 assert.equal(calculateContrarian(confirmed,now).allowedNew,false);
 assert.equal(calculateContrarian(wait,now).allowedNew,true);
});
test("stale market data never enables new buying, even with high Score",()=>{
 const x=calculateContrarian(m(94),new Date("2026-10-15T17:31:00+08:00"));
 assert.equal(x.stale,true);assert.equal(x.allowedNew,false);
});
test("missing historical high does not convert score into made-up valuation",()=>{
 const x=m(95);delete x.risk.priorHigh120;
 assert.equal(calculateContrarian(x,now).valid,false);
});
test("price midpoint is informational proxy, not a proprietary ARK formula",()=>{
 const x=calculateContrarian(m(97),now);assert.ok(x.method.includes("跌幅"));assert.ok(x.source.includes("前120日高點"));
});
