/* Regression: a verified 2026/10/16 Fri TX night must remain a 16-point
 * next-session risk scenario on 10/17, including after refresh() resets
 * the separate preview callback. No unverified data may silently promote 41.
 */
const assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
const src=fs.readFileSync(path.join(__dirname,"../docs/market-command.js"),"utf8");
const fix=new Date("2026-10-17T18:56:00+08:00");
const mod=require("../docs/market-command.js");
const risk={date:"2026-10-16",score:41,breadth:70.5,dayRet:.30};
const f={
 asOfDate:"2026-10-16",contract:"202610",quality:"paired-day-night",nightVsDayPct:-2.333,
 day:{date:"20261016",contract:"202610",close:47242},
 night:{date:"20261016",contract:"202610",close:46140,reportQueryDate:"2026-10-19"}
};
const preview=mod.marketPremarketFromFutures(risk,f,fix);
assert.ok(preview?.weekendPreview, "Verified Friday-night TX must be available on Saturday");
assert.equal(preview.score,16);
assert.equal(preview.level,"STOP");
assert.equal(preview.adjustment,-25);
assert.equal(preview.targetDate,"2026-10-19");
assert.equal(mod.marketPremarketFromFutures(risk,f,new Date("2026-10-18T18:56:00+08:00")).score,16);
assert.equal(mod.marketPremarketFromFutures(risk,f,new Date("2026-10-19T08:58:00+08:00")).score,16);
assert.equal(mod.marketPremarketFromFutures(risk,f,new Date("2026-10-19T09:00:00+08:00")),null);
assert.equal(mod.marketPremarketFromFutures(risk,{...f,nightVsDayPct:-0.01},fix),null);
assert.equal(mod.marketPremarketFromFutures(risk,{...f,quality:"day-only"},fix),null);
assert.equal(mod.marketPremarketFromFutures(risk,{...f,night:{...f.night,reportQueryDate:"2026-10-17"}},fix),null);
assert.equal(mod.marketPremarketFromFutures({...risk,date:"2026-10-15"},f,fix),null);
class Now extends Date{constructor(...args){super(...(args.length?args:[fix.getTime()]))}static now(){return fix.getTime()}}
const nodes=new Map();
function node(id){if(!nodes.has(id)){const item={id,textContent:"",className:"",style:{},dataset:{},hidden:false,children:[],href:"",
replaceChildren(){this.children=[]},appendChild(el){this.children.push(el)},append(...els){this.children.push(...els)}};nodes.set(id,item)}return nodes.get(id)}
let compact=null;
const scope={MarketCompact:{render:s=>{compact=s}},MarketSentiment:{render(){}}};
const ctx={window:scope,document:{getElementById:node,createElement:tag=>node("temp-"+tag+"-"+nodes.size)},Date:Now,Intl,console,fetch:async()=>{throw Error("Fixture: no remote")}};
vm.runInNewContext(src,ctx,{filename:"market-command.js"});
const app=scope.MarketCommand;
(async()=>{
 const snap={dataDate:"2026-10-16",risk,generatedAt:"2026-10-16T23:27:00"};
 await app.refresh(snap);
 assert.equal(node("commandScore").textContent,"—","Before TX is fetched, Friday's 41 must not masquerade as Monday");
 assert.equal(compact.pendingPreview,true);
 app.applyFutures(f);
 assert.equal(node("commandScore").textContent,"16","TX direct source must restore Monday 16 without a second UI callback");
 assert.equal(compact.score,16);
 assert.equal(compact.reference,true);
 assert.equal(compact.delta,-25);
 await app.refresh(snap);
 assert.equal(node("commandScore").textContent,"16","Auto refresh resets preview callback but must keep verified futures result");
 assert.equal(compact.score,16);
 app.applyPremarket(null);
 assert.equal(node("commandScore").textContent,"16","Transient invalid callback must not erase validated futures baseline");
 app.applyFutures({...f,nightVsDayPct:-.1});
 assert.equal(node("commandScore").textContent,"—","Mismatched futures cannot retain previous 16 as current");
 assert.equal(compact.pendingPreview,true);
 app.applyFutures(f);
 assert.equal(node("commandScore").textContent,"16","Returning verified night must restore safe 16");
 app.applyFutures(null);
 assert.equal(node("commandScore").textContent,"—","No night feed must not silently show 41 as Monday score");
 console.log("PASS Friday 41 + TX -25 = Monday 16, across refresh / callbacks / invalid-feed transitions.");
})().catch(e=>{console.error(e);process.exitCode=1});
