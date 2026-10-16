/* Regression: pinned 10/08 risk snapshot plus a SYNTHETIC 10/08 paired TX
 * night scenario (-1.305%) and separate current, real TX publication checks.
 * Never confuse a completed night with a live 08:58 quote.
 */
const assert=require("assert"),fs=require("fs"),path=require("path");
const root=path.resolve(__dirname,".."),base=path.join(root,"docs");
const model=require(path.join(base,"market-command.js"));
const html=fs.readFileSync(path.join(base,"index.html"),"utf8");
const latest=JSON.parse(fs.readFileSync(path.join(base,"data/daily/2026-10-08.json"),"utf8"));
const publishedFutures=JSON.parse(fs.readFileSync(path.join(base,"data/futures/latest.json"),"utf8"));
assert(["paired-day-night","day-only"].includes(publishedFutures.quality),"Only verified TX sessions may publish");
assert.strictEqual(publishedFutures.day.date,publishedFutures.asOfDate.replace(/-/g,""));
if(publishedFutures.quality==="paired-day-night"){
 assert.strictEqual(publishedFutures.night.date,publishedFutures.day.date);
 assert.strictEqual(publishedFutures.night.contract,publishedFutures.day.contract);
}else assert.strictEqual(publishedFutures.night,null,"Pending official night must not use fabricated values");
const future={asOfDate:"2026-10-08",contract:"202610",quality:"paired-day-night",
 day:{date:"20261008",contract:"202610",close:10000},
 night:{date:"20261008",contract:"202610",close:9869.5,reportQueryDate:"2026-10-12"}};
const begin=html.indexOf("function sameContractTX(f)"),end=html.indexOf("function renderOpeningPreview(){",begin);
assert(begin>0&&end>begin,"Original same-contract daily/overnight rule must still be present");
const extract=new Function("MarketCommand",html.slice(begin,end)+"\nreturn {sameContractTX,overnightPreviewModel};");
const fns=extract(model);
const c=fns.sameContractTX(future);
assert(c,"Synthetic fixture must pair 10/08 same-contract TX day and night");
assert.strictEqual(future.asOfDate,"2026-10-08");
assert.strictEqual(future.night.reportQueryDate,"2026-10-12");
assert(Math.abs(c.pct-(-1.305))<.01,c.pct);
assert.strictEqual(latest.risk.score,46);
const estimate=fns.overnightPreviewModel(latest.risk,future,"2026-10-12",8*60+58);
assert(estimate.valid,estimate.reason);
assert.strictEqual(estimate.base,46);
assert.strictEqual(estimate.adjustment,-15);
assert.strictEqual(estimate.score,31);
const at=(hour,min,day="2026-10-12")=>new Date(day+"T"+String(hour).padStart(2,"0")+":"+String(min).padStart(2,"0")+":00+08:00");
const prem=model.marketPremarket(latest.risk,estimate,at(8,58));
assert(prem&&prem.score===31&&prem.level==="STOP",prem);
assert.strictEqual(prem.source,"已完成TX夜盤，非08:58即時報價");
assert.strictEqual(model.marketPremarket(latest.risk,estimate,at(8,29)),null);
assert.strictEqual(model.marketPremarket(latest.risk,estimate,at(9,0)),null);
const sunday=model.marketPremarket(latest.risk,estimate,at(8,58,"2026-10-11"));
assert(sunday&&sunday.weekendPreview&&sunday.targetDate==="2026-10-12"&&sunday.score===31,"Friday night should be visible on weekend as next-session preview");
assert.strictEqual(model.marketPremarket(latest.risk,estimate,at(8,58,"2026-10-13")),null);
assert.strictEqual(model.marketPremarket(latest.risk,{...estimate,nextDate:"2026-10-13"},at(8,58)),null);
assert.strictEqual(model.marketPremarket(latest.risk,{...estimate,sourceDate:"2026-10-07"},at(8,58)),null);
assert.strictEqual(model.marketPremarket(latest.risk,{...estimate,score:80},at(8,58)),null);
assert.strictEqual(model.marketPremarket(latest.risk,{...estimate,valid:false},at(8,58)),null);
const pos=model.marketPremarket({score:55,date:"2026-10-08"},{...estimate,base:55,score:65,adjustment:10,pct:2.1},at(8,58));
assert(pos&&pos.level==="WAIT"&&pos.score===65,"positive TX does not upgrade weak cash to auto BUY");
const negative=model.marketPremarket({score:90,date:"2026-10-08"},{...estimate,base:90,score:75,adjustment:-15,pct:-1.3},at(8,58));
assert(negative&&negative.level==="STOP","overnight selloff must veto even original high cash score");
// 2026/10/16 Friday 15:00 -> 2026/10/17 05:00 night, next cash is Monday 10/19.
const friCash={date:"2026-10-16",score:41,f2Gate:{reason:"MARKET_BLOCK"}};
const fridayCrash={asOfDate:"2026-10-16",contract:"202610",quality:"paired-day-night",
 day:{date:"20261016",contract:"202610",close:47242},
 night:{date:"20261016",contract:"202610",close:46200,reportQueryDate:"2026-10-19"}};
const fridayEstimate=fns.overnightPreviewModel(friCash,fridayCrash,"2026-10-17",8*60);
assert(fridayEstimate.valid&&fridayEstimate.score===16&&fridayEstimate.adjustment===-25,fridayEstimate);
for(const dat of ["2026-10-17","2026-10-18"]){
 const outlook=model.marketPremarket(friCash,fridayEstimate,at(9,15,dat));
 assert(outlook&&outlook.weekendPreview&&outlook.score===16&&outlook.level==="STOP"&&outlook.targetDate==="2026-10-19",outlook);
}
const mondayOpen=model.marketPremarket(friCash,fridayEstimate,at(8,58,"2026-10-19"));
assert(mondayOpen&&!mondayOpen.weekendPreview&&mondayOpen.score===16,mondayOpen);
assert.strictEqual(model.marketPremarket(friCash,fridayEstimate,at(9,0,"2026-10-19")),null);
assert.strictEqual(model.marketPremarket(friCash,fridayEstimate,at(8,58,"2026-10-20")),null);
const after=model.postOpenState(latest.risk,at(9,0));
assert(after&&after.level==="WAIT","preview must expire after 09:00");
assert.strictEqual(model.postOpenState({...latest.risk,date:"2026-10-12"},at(9,0)),null);
assert(html.includes('id="commandCashReference"'),"Keep official 46 visibly separate");
assert(html.includes("MarketCommand.applyPremarket(x)"),"Completed overnight preview must reach top hero");
assert(html.includes("m>=510&&m<540"),"Preview refresh before 09:00");
// At 16:51 on Monday 10/12, 10/08 is a HISTORICAL score, not today's STOP/READY.
const oldAtClose=model.evaluate(latest.risk,latest.marketIntelligence,at(16,51));
assert.strictEqual(oldAtClose.stale,true);
assert.strictEqual(oldAtClose.closePending,true);
assert.strictEqual(oldAtClose.decision.level,"UNKNOWN");
assert(oldAtClose.decision.headline.includes("資料尚未更新"));
const beforeOpen=model.evaluate(latest.risk,latest.marketIntelligence,at(8,58));
assert.strictEqual(beforeOpen.stale,false,"Prior complete cash session remains the valid preopen baseline");
const pendingAtNine=model.postOpenState(latest.risk,at(9,0));
assert(pendingAtNine&&pendingAtNine.level==="WAIT");
const pendingAtTwo=model.postOpenState(latest.risk,at(14,0));
assert(pendingAtTwo&&pendingAtTwo.level==="WAIT");
assert.strictEqual(model.postOpenState(latest.risk,at(14,30)),null);
const validToday=model.evaluate({...latest.risk,date:"2026-10-12"},null,at(16,51));
assert.strictEqual(validToday.stale,false,"Matching official cash date is current");
console.log("PASS pinned cash risk46 + synthetic TX -1.305 -> preopen31; live futures date parity, stale/mismatch and positive-buy guardrails");
