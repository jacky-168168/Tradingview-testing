/* Regression for the 2026-10-17 Saturday 18:56 screenshot:
 * Friday cash 41, verified Friday TX -2.33%, Monday 10/19 preview 16.
 * The main card must NOT temporarily or permanently masquerade 41 as Monday risk.
 * This test deliberately never calls the secondary opening-preview component.
 */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm"),path=require("node:path");
const root=path.resolve(__dirname,"../docs");
const market=fs.readFileSync(path.join(root,"market-command.js"),"utf8");
const compact=fs.readFileSync(path.join(root,"market-compact.js"),"utf8");
// Freeze the original 2026-10-17 regression scenario. Never import mutable
// live snapshots here: their dates MUST advance as markets update.
const snap={dataDate:"2026-10-16",risk:{date:"2026-10-16",score:41},marketIntelligence:null};
const fut={quality:"paired-day-night",asOfDate:"2026-10-16",contract:"202610",
 day:{date:"20261016",contract:"202610",close:50000},
 night:{date:"20261016",contract:"202610",close:48833.5,reportQueryDate:"2026-10-19"},
 nightVsDayPct:-2.333};
assert.equal(snap.risk.date,"2026-10-16");
assert.equal(snap.risk.score,41);
assert.equal(fut.asOfDate,"2026-10-16");
assert.equal(fut.night.reportQueryDate,"2026-10-19");
assert.equal(fut.quality,"paired-day-night");
const t=Date.parse("2026-10-17T18:56:00+08:00");
class FixedDate extends Date{constructor(...args){super(...(args.length?args:[t]))}static now(){return t}}
const elems=new Map();
const el=id=>{if(!elems.has(id))elems.set(id,{id,textContent:"",style:{},dataset:{},hidden:false,children:[],className:"",
  replaceChildren(){this.children=[]},appendChild(v){this.children.push(v)}});return elems.get(id)};
const scope={};
const ctx={window:scope,document:{getElementById:el,createElement:tag=>el("temp-"+tag+"-"+elems.size)},Date:FixedDate,Intl,console,fetch:async()=>{throw Error("network fixture disabled")}};
vm.runInNewContext(compact,ctx,{filename:"market-compact.js"});
vm.runInNewContext(market,ctx,{filename:"market-command.js"});
const app=scope.MarketCommand;
(async()=>{
 await app.refresh({dataDate:snap.dataDate,risk:snap.risk,marketIntelligence:snap.marketIntelligence});
 assert.equal(el("compactScore").textContent,"—","Do not temporarily present 41 as Monday's risk while TX loads");
 assert.equal(el("compactOfficial").textContent,"41","Keep official cash score distinct");
 assert.match(el("compactScoreType").textContent,/盤前.*待核對/);
 const checked=app.verifiedNightPreview(snap.risk,fut,new FixedDate());
 assert.ok(checked,"Direct futures preview requires source date, contract, report date and price agreement");
 assert.equal(checked.adjustment,-25);
 assert.equal(checked.score,16);
 const estimate=app.marketPremarket(snap.risk,checked,new FixedDate());
 assert.equal(estimate.score,16);
 app.applyFutures(fut);
 assert.equal(el("compactScore").textContent,"16","Main card must directly derive Monday preview from verified TX");
 assert.equal(el("compactOfficial").textContent,"41");
 assert.equal(el("compactNight").textContent,"-25");
 assert.equal(el("compactNightCell").hidden,false);
 assert.equal(el("compactBand").textContent,"極度偏空");
 assert.equal(el("commandScore").textContent,"16","Collapsed expert card must agree with main card");
 assert.equal(el("marketCommand").dataset.premarket,"true");
 app.applyFutures({...fut,night:{...fut.night,contract:"202611"}});
 assert.equal(el("compactScore").textContent,"—","Wrong contract must fail closed");
 assert.equal(el("compactOfficial").textContent,"41");
 app.applyFutures({...fut,nightVsDayPct:-.1});
 assert.equal(el("compactScore").textContent,"—","Published percent mismatch must fail closed");
 app.applyFutures({...fut,night:{...fut.night,reportQueryDate:"2026-10-18"}});
 assert.equal(el("compactScore").textContent,"—","Invalid next session must fail closed");
 app.applyFutures(fut);
 assert.equal(el("compactScore").textContent,"16","Restoring valid TX must restore 16 without page reload");
 console.log("PASS 2026/10/17 Sat 18:56: cash41 + official TX -2.333% => Monday16, never revert to cash41");
})().catch(e=>{console.error(e);process.exitCode=1});
