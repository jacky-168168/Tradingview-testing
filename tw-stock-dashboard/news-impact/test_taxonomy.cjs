"use strict";
const assert=require("node:assert/strict");
global.window={
 NewsImpactSector:require("../docs/news-impact-sector.js"),
 NewsImpactTaxonomy:require("../docs/news-impact-taxonomy.js")
};
const {classify,VERSION}=require("../docs/news-impact.js");
const c=title=>classify({title,source:"Representative archived news",category:"總經"});
function has(x,id){return x.hits.some(r=>r.id===id)}
function obs(x,asset){return x.observations.find(o=>o.asset===asset)}
function score(x,asset){return x.impacts.find(i=>i.asset===asset)?.score}
assert.equal(VERSION,"2026-11-09-v1.3");
// Fed references without a confirmed decision must NOT become a hawkish shock.
let x=c("星展銀行指稱，聯準會升息押注降溫，套利交易平倉料將推高港幣匯率");
assert.ok(has(x,"hike-bets-cool"));assert.equal(has(x,"rate-hawk"),false);
assert.equal(score(x,"美元"),-15);
x=c("美經濟恐放緩Fed升息兩難");
assert.equal(has(x,"rate-hawk"),false);
x=c("AI股才剛反彈又遇升息炸彈！美國就業太強成利空");
assert.equal(has(x,"rate-hawk"),false);
// Quoted USD price units are not evidence that the dollar index rose.
x=c("產業：DRAM報價上週五普遍下跌，其中DDR5 16Gb均價為60.167美元，跌幅0.82%");
assert.equal(score(x,"台股記憶體供應端"),-35);
assert.equal(obs(x,"美元"),undefined);
x=c("金價：台北時間9:30亞洲金價位為4106.02美元，較上週五紐約收盤上漲35.22美元");
assert.ok(obs(x,"黃金"),"reported gold price increase must be visible");
assert.equal(obs(x,"美元"),undefined);
assert.equal(score(x,"黃金"),undefined,"reported gold price isn't a forecast");
x=c("Oil falls on open as Trump says fresh Iran attacks 'unlikely'");
assert.ok(obs(x,"WTI原油"));
assert.equal(has(x,"war-up"),false);
x=c("Production suspended at Iraq's Khor Mor gas field after drone attack, sources say");
assert.equal(score(x,"天然氣價格"),35);
assert.equal(score(x,"WTI原油"),undefined);
x=c("New Zealand Dollar Advances as Ruling Party Gets Election Edge");
assert.ok(obs(x,"紐元NZD"));
assert.equal(obs(x,"美元"),undefined);
assert.equal(x.impacts.length,0);
x=c("AI熱潮點燃先進封裝軍備競賽 全球砸近280億美元擴產");
assert.equal(score(x,"AI／半導體設備"),25);
x=c("國際產經：微軟傳逐步終止租用甲骨文AI算力，舊世代GPU需求與雲端合約受考驗");
assert.equal(score(x,"雲端算力租賃"),-20);
x=c("COP31 to open in Turkey, with climate goals under pressure from war and AI");
assert.ok(x.topics.length>0);assert.equal(x.impacts.length,0);
x=c("Trump says 'only kidding' about naming UFC CEO as White House press secretary");
assert.ok(x.topics.length>0);assert.equal(x.impacts.length,0);
x=c("金市前瞻：黃金可能下跌10%");
assert.equal(obs(x,"黃金"),undefined,"a future/forecast cannot be observed price");
x=c("油價暴跌20%，金價為何逆勢大漲？");
assert.ok(obs(x,"WTI原油"));assert.ok(obs(x,"黃金"));
console.log("taxonomy: scoped macro, USD quote, FX, industry, negation, observations passed");
