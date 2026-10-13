const test=require("node:test"),assert=require("node:assert/strict");
const e=require("../docs/capital-water-backtest-engine.js");
function mock(n=300){return Array.from({length:n},(_,i)=>({date:new Date(Date.UTC(2023,0,2+i)).toISOString().slice(0,10),index:100+i/10,score:75,ma20:100+i/10,topState:""}))}
test("merge refuses fake/missing data and sorts distinct dates",()=>{
 assert.throws(()=>e.mergeSeries([1,2,3]),/130/);
 const b=mock(140);b.reverse();
 const x=e.mergeSeries(b,[{...b[0],index:123}]);assert.equal(x.length,140);
 assert.ok(x[0].date<x.at(-1).date);
});
test("model is countercyclical when the same previous high is fixed",()=>{
 const r=mock(130);for(let i=0;i<129;i++)r[i].index=100;r[129].index=100;
 let x=e.targetAt(r,129,"original_v2");
 assert.equal(x.target,30);
 r[129].index=94;
 x=e.targetAt(r,129,"original_v2");
 assert.equal(x.target,50);
 r[129].index=84;
 x=e.targetAt(r,129,"original_v2");
 assert.equal(x.target,80);
});
test("high MA20 gap activates cash protection",()=>{
 const r=mock(130);r[129].index=100;r[129].ma20=90;
 assert.equal(e.targetAt(r,129,"original_v2").target,25);
});
test("signal uses prior-day close and does not trade the same signal day",()=>{
 const r=mock(150);
 r[121].index=100;r[122].index=80;r[123].index=120;
 const a=e.targetAt(r,121,"original_v2");
 const b=e.targetAt(r,122,"original_v2");
 assert.ok(b.target>a.target);
 const p=e.simulate(r,"original_v2",{start:r[122].date,end:r[123].date});
 assert.equal(p.series[0].target,a.target);
 assert.equal(p.series[1].target,b.target);
});
test("risk gate forbids buys but allows reductions",()=>{
 const r=mock(150);for(let i=120;i<150;i++)r[i].score=20;
 const s=e.simulate(r,"original_gate",{start:r[125].date,end:r[140].date});
 assert.equal(s.tradeCount,0);assert.equal(s.final,s.initial);
});
test("no transaction fees gives weakly better than default in a rising market",()=>{
 const r=mock(180);
 const free=e.simulate(r,"original_v2",{start:r[130].date,end:r[170].date,buyFee:0,sellFee:0});
 const charged=e.simulate(r,"original_v2",{start:r[130].date,end:r[170].date});
 assert.ok(free.final>=charged.final);assert.ok(charged.fees>0);
});
test("higher trade band reduces churn for oscillating target",()=>{
 const r=mock(210);
 for(let i=120;i<210;i++)r[i].index= i%2===0?100:94;
 const a=e.simulate(r,"original_v2",{start:r[125].date,end:r[209].date,band:.05});
 const b=e.simulate(r,"original_v2",{start:r[125].date,end:r[209].date,band:.15});
 assert.ok(a.tradeCount>=b.tradeCount);
});
test("missing warmup excludes observations rather than retroactively inventing highs",()=>{
 const r=mock(180);
 assert.throws(()=>e.targetAt(r,130,"badmodel"));
 assert.throws(()=>e.simulate(r,"long_250",{start:r[130].date,end:r[175].date}),/Insufficient rolling-history warmup/);
});
