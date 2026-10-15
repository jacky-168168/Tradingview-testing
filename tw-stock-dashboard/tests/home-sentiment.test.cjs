const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const core=require("../docs/market-sentiment.js");
const page=fs.readFileSync(path.join(__dirname,"../docs/index.html"),"utf8");
test("all five zones use the Chinese thresholds displayed in the design",()=>{
 assert.equal(core.band(0).label,"極度恐慌");assert.equal(core.band(24).label,"極度恐慌");
 assert.equal(core.band(25).label,"恐慌");assert.equal(core.band(44).label,"恐慌");
 assert.equal(core.band(45).label,"中性");assert.equal(core.band(55).label,"中性");
 assert.equal(core.band(56).label,"貪婪");assert.equal(core.band(74).label,"貪婪");
 assert.equal(core.band(75).label,"極度貪婪");assert.equal(core.band(100).label,"極度貪婪");
 assert.equal(core.band(null),null);assert.equal(core.band(""),null);assert.equal(core.band(-1),null);assert.equal(core.band(101),null);
});
test("history refuses missing score, deduplicates and sorts trading dates",()=>{
 const history=core.normalizeHistory([{date:"2026-10-13",riskScore:36},{date:"2026-10-15",riskScore:21},{date:"2026-10-15",riskScore:90},{date:"2026-10-14",riskScore:null},{date:"2026-10-12",riskScore:58}]);
 assert.deepEqual(history.map(x=>x.date),["2026-10-15","2026-10-13","2026-10-12"]);
 assert.equal(history[0].score,21);
});
test("history comparisons use real as-of dates without future data or invented values",()=>{
 const h=core.normalizeHistory([{date:"2026-10-15",riskScore:21},{date:"2026-10-14",riskScore:70},{date:"2026-10-13",riskScore:36},{date:"2026-10-12",riskScore:58},{date:"2026-10-08",riskScore:46}]);
 const c=core.comparisons(h,"2026-10-15");
 assert.deepEqual(c.map(x=>x.title),["前一交易日","一週前","3天前","5天前"]);
 assert.deepEqual(c.map(x=>x.record?.date),["2026-10-14","2026-10-08","2026-10-12","2026-10-08"]);
 assert.deepEqual(c.map(x=>x.record?.score),[70,46,58,46]);
 assert.equal(core.comparisons([],"2026-10-15")[0].record,null);
 assert.equal(core.dateOffset("2026-10-15",7),"2026-10-08");
});
test("gauge SVG displays true score in its assigned band",()=>{
 const svg=core.gaugeSVG(21);assert.match(svg,/大盤風險分數 21，極度恐慌/);assert.match(svg,/大盤風險分數/);assert.doesNotMatch(svg,/<script/);
 assert.match(core.gaugeSVG(null),/分數尚未取得/);
});
test("homepage preserves all original operational controls and displays real data visualization",()=>{
 for(const id of ["sentimentPanel","sentimentHistory","sentimentGauge","commandScore","commandGuideTitle","commandAction","dynamicExposure","buyRows","sellRows","themeRows","homeGStatus","homeGRows","revState","txfDetails","marketAdvanced","riskScore"])
  assert.ok(page.includes('id="'+id+'"'),id);
 for(const tab of ["overview","timeline"])assert.ok(page.includes('data-sentiment-tab="'+tab+'"'));
 assert.ok(page.indexOf('id="homeFocus"')<page.indexOf('id="dynamicExposure"'));
 assert.match(page,/market-sentiment\.js/);
});
