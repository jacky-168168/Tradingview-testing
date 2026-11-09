"use strict";
// Regression tests for real screenshot items + false-positive guards.
// Run: node tw-stock-dashboard/news-impact/test_sector.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const analyzer = require("../docs/news-impact-sector.js");
const classify = title => analyzer.examine({title});

function rule(title,id){
 return classify(title).rules.find(x=>x.id===id);
}
const dram="產業：DRAM報價上週五普遍下跌，其中DDR5 16Gb均價為60.167美元，跌幅0.82%";
const israel="Israel’s president gives Eisenkot the first chance to form the next government - AP News";
const nzd="New Zealand Dollar Advances as Ruling Party Gets Election Edge";

// The primary screenshot should be tagged with scope-limited price pressure.
const memory = rule(dram,"memory-price-down");
assert.ok(memory,"failed to recognize quoted DRAM spot price decline");
assert.equal(memory.impact["台股記憶體供應端"],-35);
assert.equal(memory.impact["台股"],undefined,"a component price fall must not imply broad Taiwan index decline");
assert.equal(memory.impact["NASDAQ"],undefined);
assert.equal(rule("記憶體DRAM報價上漲2%","memory-price-up").impact["台股記憶體供應端"],35);
assert.equal(rule("記憶體DRAM報價下跌2%但其他報價上漲1%","memory-price-down"),undefined);
assert.ok(rule("記憶體DRAM報價下跌2%但其他報價上漲1%","memory-price-mixed"));
assert.equal(classify("DRAM股票報價下跌2%").rules.some(x=>x.id==="memory-price-down"),true);
// Don't treat historical/intraday stock-price movement as an industry product quotation.
assert.equal(classify("DRAM相關股票下跌5%").rules.length,0);
assert.equal(classify("記憶體設計廠前三季EPS創高、毛利率77%").rules.length,0);
assert.equal(classify("傳聞DRAM報價明天可能下跌").rules.length,0);

// Coalition appointment is a confirmed political event, not verified commodity direction.
const coalition=rule(israel,"israel-coalition");
assert.ok(coalition);
assert.deepEqual(coalition.impact,{});
assert.equal(classify("Israel missile strikes oil shipment").rules.some(x=>x.id==="israel-coalition"),false);

// This headline reports an already-observed NZD rise; it does not forecast NZD.
const fx=rule(nzd,"nzd-election");
assert.ok(fx);
assert.deepEqual(fx.impact,{});
assert.deepEqual(classify(nzd).observations,[{asset:"紐元NZD",label:"新聞稱已走強"}]);
assert.equal(classify("New Zealand Dollar falls after election").observations[0].label,"新聞稱已走弱");
assert.deepEqual(classify("New Zealand election uncertainty deepens").observations,[]);

// Live UI script must include the module before core classifier.
const page=fs.readFileSync(path.resolve(__dirname,"../docs/news-impact.html"),"utf8");
const iModule=page.indexOf('src="./news-impact-sector.js"');
const iCore=page.indexOf('src="./news-impact.js"');
assert.ok(iModule>=0&&iCore>iModule,"sector plugin must load before core classifier");
assert.ok(page.includes("<option>台股記憶體供應端</option>"));
assert.ok(page.includes("<option>紐元NZD</option>"));
console.log("news-impact sector classification and UI dependency tests passed");
