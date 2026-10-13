const test=require("node:test"),assert=require("node:assert/strict");
const {calculate,sizePlan,holdingGuidance,ageStatus,candidateList}=require("../docs/dynamic-exposure.js");
const at=(date,hour=17)=>new Date(date+"T"+String(hour).padStart(2,"0")+":00:00+08:00");
const mk=(score=70)=>({dataDate:"2026-10-12",risk:{date:"2026-10-12",score,breadth:55,index:21500,ma20:21000,foreign:100,topState:"⚪ Normal",bottomState:"⚪ Inactive"},marketIntelligence:{asOf:"2026-10-12",riskScore:score,marketHealth:{volatilityHistoryPercentile:30,indexBreadthDivergence:false}}});
test("fully sourced factors sum to 100 and produce reasonable allocation",()=>{
 const m=calculate(mk(70),at("2026-10-12"));
 assert.equal(m.valid,true);assert.equal(m.coverage,100);assert.ok(m.target>=10&&m.target<=85);
 assert.equal(m.factors.length,5);assert.equal(m.stale,false);
});
test("primary risk below 60 hard caps illustrative allocation and cannot unblock entry",()=>{
 const m=calculate(mk(59),at("2026-10-12"));assert.ok(m.target<=40);assert.ok(m.flags.some(x=>x.includes("不等於允許進場")));
});
test("very weak risk and confirmed market Top apply tighter caps",()=>{
 const m=mk(42);m.risk.topState="🔴 Strong Top Reversal";
 const x=calculate(m,at("2026-10-12"));assert.ok(x.target<=20);
});
test("Top Watch is not equivalent to confirmed Top",()=>{
 const m=mk(77);m.risk.topState="⚪ Top Watch";
 const x=calculate(m,at("2026-10-12"));assert.ok(x.cap>35);
});
test("original diagnostic score must match original risk date and score",()=>{
 const m=mk(65);m.marketIntelligence.riskScore=64;
 const x=calculate(m,at("2026-10-12"));assert.equal(x.valid,true);
 assert.equal(x.coverage,85);assert.equal(x.factors.some(f=>f.key==="volatility"),false);
});
test("not enough independent actual fields fails closed",()=>{
 const m=mk();delete m.risk.index;delete m.risk.breadth;delete m.risk.foreign;
 const x=calculate(m,at("2026-10-12"));assert.equal(x.valid,false);assert.equal(x.target,null);
});
test("yesterday's data are stale on a new trading day after 14:30",()=>{
 const m=calculate(mk(70),at("2026-10-13",17));assert.equal(m.stale,true);
 const p=sizePlan(m,{capital:1000000,stock:{close:100,atrPct:4,ret20:5}});assert.equal(p.canBuy,false);
});
test("previous session before afternoon closing is reference, not fresh intraday",()=>{
 assert.equal(ageStatus("2026-10-12",at("2026-10-13",9)).stale,false);
 assert.equal(ageStatus("2026-10-12",at("2026-10-13",17)).stale,true);
});
test("weekend Friday close remains recent, not Saturday stale",()=>{
 assert.equal(ageStatus("2026-10-09",at("2026-10-11",17)).stale,false);
});
test("per-stock first batch shrinks under hot momentum, zero funds when fully invested",()=>{
 const m=calculate(mk(75),at("2026-10-12"));
 const normal=sizePlan(m,{capital:1000000,held:0,stocks:5,stock:{close:100,atrPct:4,ret20:5}});
 const hot=sizePlan(m,{capital:1000000,held:0,stocks:5,stock:{close:100,atrPct:8,ret20:60}});
 assert.equal(normal.firstPct,25);assert.equal(hot.firstPct,10);assert.ok(hot.firstBudget<normal.firstBudget);
 const full=sizePlan(m,{capital:1000000,held:1000000,stocks:5,stock:{close:100}});
 assert.equal(full.headroom,0);assert.equal(full.canBuy,false);
});
test("no candidate selected does not fabricate quantity or trade",()=>{
 const m=calculate(mk(),at("2026-10-12"));
 const x=sizePlan(m,{capital:1000000,held:0,stocks:5});assert.equal(x.canBuy,false);assert.equal(x.shares,null);
});
test("G model candidates remain opt-in, only known codes",()=>{
 const data={models:{G:[{code:"2340",name:"A"},{code:"2340",name:"Duplicate"},{code:"2002",name:"B"},{code:"N/A"}]}};
 assert.deepEqual(candidateList(data).map(s=>s.code),["2340","2002"]);
});

test("holding 500k versus 400k capital target displays over-allocation without forced sell",()=>{
 const market={valid:true,date:"2026-10-13",stale:false,risk:36,target:40,allowedNew:false};
 const plan=sizePlan(market,{capital:1000000,held:500000,stocks:5});
 const g=holdingGuidance(market,plan);
 assert.equal(plan.excess,100000);assert.equal(plan.headroom,0);
 assert.equal(g.tone,"over");assert.equal(g.gap,"超出 100,000 元");
 assert.equal(g.actualExposure,"50.0%");assert.equal(g.cashUninvested,"500,000 元");assert.equal(g.todayBudget,"0 元");
 assert.match(g.next,/不代表需要立刻賣出/);assert.match(g.next,/一般新倉暫停/);
});
test("below target explains spare future allocation without granting a buy",()=>{
 const m={valid:true,stale:false,risk:36,target:40,allowedNew:false};
 const g=holdingGuidance(m,sizePlan(m,{capital:1000000,held:300000}));
 assert.equal(g.gap,"還差 100,000 元");assert.equal(g.todayBudget,"0 元");
 assert.match(g.next,/不是今天一定要買入/);
});
test("up-to-date risk-ON still requires individual entry signal",()=>{
 const m={valid:true,stale:false,risk:75,target:60,allowedNew:true};
 const g=holdingGuidance(m,sizePlan(m,{capital:1000000,held:400000}));
 assert.equal(g.todayBudget,"0 元");assert.match(g.next,/Bottom／SS Bottom/);
});
test("expired or invalid market never tells users to trade",()=>{
 const m={valid:true,stale:true,risk:75,target:40,allowedNew:false};
 const stale=holdingGuidance(m,sizePlan(m,{capital:1000000,held:300000}));
 assert.match(stale.next,/資料未更新/);assert.equal(stale.todayBudget,"0 元");
 const invalid=holdingGuidance({valid:false},sizePlan({valid:false},{capital:1000000,held:0}));
 assert.equal(invalid.tone,"invalid");assert.equal(invalid.todayBudget,"0 元");
});
