const test=require("node:test"),assert=require("node:assert/strict");
const core=require("../docs/position-sizing-core.js");
const market={valid:true,stale:false,risk:75,date:"2026-10-13",target:70};
const base={capital:1e6,otherHeld:0,code:"2340",type:"stock",group:"technology",price:100,priceDate:"2026-10-13",atrPct:5,zone:"normal",signal:"ss",entryConfirmed:true,positions:[],historyValidated:true,priceDate:"2026-10-13"};
test("risk budget, class and market caps all enter the minimum",()=>{
 const x=core.size(base,market);
 assert.equal(x.valid,true);assert.equal(x.limit,40000);
 assert.equal(x.firstShares,80);assert.equal(x.first,8000);
 assert.equal(x.riskAtMax,5000);
 assert.equal(x.ladder.length,4);
 assert.equal(x.ladder[0].budget,8000);
});
test("no signal or confirmation means zero authorized shares",()=>{
 assert.equal(core.size({...base,signal:"none"},market).firstShares,0);
 assert.equal(core.size({...base,entryConfirmed:false},market).firstShares,0);
 assert.equal(core.size({...base,code:""},market).canBuy,false);
});
test("market Risk OFF is not overridden by SS Bottom",()=>{
 const x=core.size(base,{...market,risk:36,target:25});
 assert.equal(x.canBuy,false);assert.equal(x.first,0);
 assert.ok(x.blocked.some(x=>x.includes("低於 60")));
});
test("stale or missing market locks authorized trades",()=>{
 assert.equal(core.size(base,{...market,stale:true}).first,0);
 assert.equal(core.size(base,{valid:false,stale:true,target:null}).limit,0);
});
test("symbol existing position uses remaining risk budget, not full fresh budget",()=>{
 const x=core.size({...base,positions:[{code:"2340",type:"stock",group:"technology",value:30000}]},market);
 assert.equal(x.limit,10000);assert.equal(x.first,2000);
});
test("technology exposure blocks overlapping tech stock or 0052 ETF",()=>{
 const positions=[{code:"0052",type:"sector-etf",group:"technology",value:250000}];
 const x=core.size({...base,positions},market);
 assert.equal(x.caps.sector,0);assert.equal(x.first,0);assert.equal(x.canBuy,false);
});
test("leveraged ETF uses lower single-name and risk caps",()=>{
 const x=core.size({...base,code:"00675L",type:"leveraged-etf",group:"market",zone:"value",price:100,atrPct:6,positions:[]},market);
 assert.equal(x.limit,15000);assert.equal(x.stressPct,.2);assert.equal(x.firstShares,30);
});
test("zero-risk class held fully prevents more tranche",()=>{
 const positions=[{code:"00675L",type:"leveraged-etf",group:"market",value:16000}];
 const x=core.size({...base,code:"00675L",type:"leveraged-etf",group:"market",positions},market);
 assert.equal(x.limit,0);
});
test("zone research needs 60 sequential closes and is never intrinsic valuation",()=>{
 assert.equal(core.parseSeries("100\n101\n102",100).ready,false);
 const z=core.parseSeries(Array.from({length:60},(_,i)=>100+i).join("\n"),159);
 assert.equal(z.ready,true);assert.equal(z.zone,"hot");
 assert.match(z.note,/非基本面/);
});
test("dated history rejects descending date and duplicate day",()=>{
 assert.throws(()=>core.parseSeries("2026-10-10,10\n2026-10-09,11",10),/由舊到新/);
});
test("hot technical zone prevents all initial tranche at that price",()=>{
 const x=core.size({...base,zone:"hot"},market);assert.equal(x.firstShares,0);
});
test("cash planning is capped by free market headroom",()=>{
 const positions=[{code:"TW-OTHER",type:"broad-etf",group:"market",value:680000}];
 const x=core.size({...base,positions},market);assert.equal(x.marketLeft,20000);assert.ok(x.limit<=20000);
});
test("original ETF registry distinguishes concentrated and leveraged",()=>{
 assert.equal(core.ETF["0056"].type,"sector-etf");
 assert.equal(core.ETF["0052"].group,"technology");
 assert.equal(core.ETF["00675L"].type,"leveraged-etf");
});
test("conservative grouping is proxy, not constituent correlation",()=>{
 assert.equal(core.guessGroup({industry:"半導體業"}),"technology");
 assert.equal(core.guessGroup({industry:"金融保險"}),"finance");
 assert.equal(core.guessGroup({industry:"食品業"}),"other");
});

test("market top veto separately blocks new entry even when Risk Score looks acceptable",()=>{
 const x=core.size(base,{...market,allowedNew:false});
 assert.equal(x.canBuy,false);assert.equal(x.first,0);
});
test("price without a known fresh date is shown only as potential sizing",()=>{
 const x=core.size({...base,priceDate:""},market);assert.equal(x.priceDated,false);assert.equal(x.canBuy,false);assert.equal(x.first,0);
});
test("known leveraged ETF cannot bypass caps by manual stock type",()=>{
 const x=core.size({...base,code:"00675L",group:"other",type:"stock"},market);
 assert.equal(x.kind,"leveraged-etf");assert.equal(x.group,"market");
});
