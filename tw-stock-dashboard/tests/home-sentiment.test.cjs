const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const core=require("../docs/market-sentiment.js");
const page=fs.readFileSync(path.join(__dirname,"../docs/index.html"),"utf8");
test("all five zones use the Chinese thresholds displayed in the design",()=>{
 assert.equal(core.band(0).label,"極高風險");assert.equal(core.band(24).label,"極高風險");
 assert.equal(core.band(25).label,"風險偏高");assert.equal(core.band(44).label,"風險偏高");
 assert.equal(core.band(45).label,"中性觀望");assert.equal(core.band(55).label,"中性觀望");
 assert.equal(core.band(56).label,"中性觀望");assert.equal(core.band(59).label,"中性觀望");assert.equal(core.band(60).label,"偏多觀察");assert.equal(core.band(74).label,"偏多觀察");
 assert.equal(core.band(75).label,"強勢偏多");assert.equal(core.band(100).label,"強勢偏多");
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
 const svg=core.gaugeSVG(21);assert.match(svg,/大盤風險分數 21，極高風險/);assert.match(svg,/大盤風險分數/);assert.doesNotMatch(svg,/<script/);
 assert.match(core.gaugeSVG(null),/分數尚未取得/);
});
test("homepage preserves all original operational controls and displays real data visualization",()=>{
 for(const id of ["sentimentPanel","sentimentHistory","sentimentGauge","sentimentRiskReview","sentimentAdjusted","sentimentPattern","commandReboundWarning","commandScore","commandGuideTitle","commandAction","dynamicExposure","buyRows","sellRows","themeRows","homeGStatus","homeGRows","revState","txfDetails","marketAdvanced","riskScore"])
  assert.ok(page.includes('id="'+id+'"'),id);
 for(const tab of ["overview","timeline"])assert.ok(page.includes('data-sentiment-tab="'+tab+'"'));
 assert.ok(page.indexOf('id="homeFocus"')<page.indexOf('id="dynamicExposure"'));
 assert.match(page,/market-sentiment\.js/);
});

test("10/14 70 keeps original raw score but flags incomplete rebound at experimental 55",()=>{
 const previous={date:"2026-10-13",score:36,dayRet:-1.95},current={date:"2026-10-14",score:70,dayRet:0.59,ret5:-2.4,foreign:-200.4};
 const v=core.reboundReview(current,previous);
 assert.equal(v.valid,true);assert.equal(v.status,"rebound");assert.equal(v.adjusted,55);assert.equal(v.penalty,15);
 assert.equal(current.score,70);assert.match(v.message,/反彈待確認/);
});
test("10/15 score 21 is extreme risk, independently an oversold watch not a confirmed Bottom",()=>{
 const d={date:"2026-10-15",score:21,dayRet:-3.41,ret5:-5.70,foreign:-3025.6,mode:"BOTTOM",bottomState:"🟣 Oversold Watch",bottomConfirmScore:0,oversoldScore:4};
 assert.equal(core.band(d.score).label,"極高風險");
 assert.equal(core.reboundReview(d,{date:"2026-10-14",dayRet:0.59}).status,"clear");
 const p=core.specialPattern(d);assert.match(p.name,/超跌觀察/);assert.match(p.detail,/底部確認 0 分/);
});
test("unverified prior date never pretends rebound guard is clear",()=>{
 const d={date:"2026-10-14",score:70,dayRet:0.59,ret5:-2.4,foreign:-200.4};
 for(const p of [null,{date:"2026-10-15",dayRet:-1.95},{date:"2026-10-14",dayRet:-1.95}])
  assert.equal(core.reboundReview(d,p).status,"pending");
});
test("reversal guard leaves normal rebounds alone; only discount with sufficient evidence",()=>{
 const p={date:"2026-10-13",dayRet:-1.95},r={date:"2026-10-14",score:70,dayRet:0.59,ret5:-2.4,foreign:-200.4};
 assert.equal(core.reboundReview({...r,dayRet:2.1},p).adjusted,70);
 assert.equal(core.reboundReview({...r,ret5:0.1},p).adjusted,70);
 assert.equal(core.reboundReview({...r,foreign:15},p).adjusted,60);
 assert.equal(core.reboundReview({...r,dayRet:-0.2},p).adjusted,70);
});
