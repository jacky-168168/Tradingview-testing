"use strict";
const assert=require("node:assert/strict");
global.window={
 NewsImpactSector:require("../docs/news-impact-sector.js"),
 NewsImpactTaxonomy:require("../docs/news-impact-taxonomy.js")
};
const {classify,VERSION}=require("../docs/news-impact.js");
const classifyHeadline=(title,category="總經")=>classify({title,category,source:"archived representative media"});
const rule=(c,id)=>c.hits.some(r=>r.id===id);
const impact=(c,a)=>c.impacts.find(x=>x.asset===a)?.score;
const observation=(c,a)=>c.observations.find(x=>x.asset===a);
assert.equal(VERSION,"2026-11-09-v1.3");
// No future prices nor product-customer inventory as proven memory price rise.
for(const t of [
 "AI拉高記憶體成本！任天堂公布庫存充足：Switch 2售價短期內凍漲",
 "蘋果財測有壓 CEO 示警記憶體明年還會漲 牽動本季營收與毛利率",
 "記憶體Q3每股獲利王出爐！台廠看缺貨2027更嚴重 低價庫存見底藏隱憂"
]){
 const x=classifyHeadline(t,"報價");
 assert.equal(impact(x,"台股記憶體供應端"),undefined,t);
 assert.ok(rule(x,"memory-outlook"),"future memory news must be classified as conditional context");
}
const dram=classifyHeadline("產業：DRAM報價上週五普遍下跌，其中DDR5 16Gb均價為60.167美元，跌幅0.82%","報價");
assert.equal(impact(dram,"台股記憶體供應端"),-35);
assert.equal(impact(dram,"台股"),undefined);
const memory=classifyHeadline("DRAM缺貨漲價效益大爆發！「記憶體設計廠」前三季EPS衝64.54元","報價");
assert.equal(impact(memory,"台股記憶體供應端"),20);
// Neither rumors of talks nor oil's already observed fall is a forward forecast.
for(const t of [
 "美伊和談希望再起 國際油價跌幅擴大至逾6%",
 "美伊和談傳進展 國際油價整周暴跌逾10%"
]){
 const x=classifyHeadline(t,"原油／能源");
 assert.ok(rule(x,"iran-talks-watch"),"peace talks should be recognized as diplomacy context");
 assert.equal(impact(x,"WTI原油"),undefined);
 assert.ok(observation(x,"WTI原油"),"oil price change was reported, not predicted");
}
// Reported / expected FX must be kept separate.
assert.equal(observation(classifyHeadline("美國非農就業報告報喜 美元走揚強化升息預期"),"美元")?.label,"新聞稱已上漲");
const hongKong=classifyHeadline("銀行估計升息押注降溫，套利平倉料將推高港幣匯率");
assert.equal(observation(hongKong,"港幣HKD"),undefined,"forecast is not observed");
const hkdDone=classifyHeadline("港幣匯率今日走強1%");
assert.equal(observation(hkdDone,"港幣HKD")?.label,"新聞稱已上漲");
// Natural-gas outage is potential *price* upside, NOT a supply improvement.
const gas=classifyHeadline("Production suspended at Iraq's Khor Mor gas field after drone attack, sources say");
assert.equal(impact(gas,"天然氣價格"),35);
assert.equal(impact(gas,"天然氣供應"),undefined);
assert.equal(impact(gas,"WTI原油"),undefined);
// Topic recognition should disclose source-category-only fallback.
const fallback=classifyHeadline("An unrelated product launch note","AI需求");
assert.equal(fallback.topicEvidence,"source_category_only");
assert.ok(fallback.topics.length>0);
const longTerm=classifyHeadline("2035年腰果奶市場預測：咖啡店奶精需求帶動成長","農產品");
assert.ok(longTerm.topics.includes("長期市場展望（非當日商品行情）"));
assert.equal(longTerm.impacts.length,0);
console.log("news-impact V1.3 logic guards passed: rumors, forecasts, quotation vs FX, gas price and topic evidence");
