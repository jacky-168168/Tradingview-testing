"use strict";
const assert=require("node:assert/strict");
const {audit,reason}=require("./audit_recognition.cjs");
const now=new Date("2026-11-09T08:00:00Z");
function news(id,title,category="總經"){return {id,title,category,type:"news",url:"https://example.org/"+id,source:"Sample"}}
const records=[
 news("m1","產業：DRAM報價上週五普遍下跌，其中DDR5 16Gb均價為60.167美元，跌幅0.82%","報價"),
 news("m2","Gold rises 2% after market close","貴金屬"),
 news("m3","Israel’s president gives Eisenkot the first chance to form the next government"),
 news("m4","An unrelated note about household furniture","AI需求"),
 news("m5","No known financial or political event behind this title","無資料"),
 news("m6","美伊和談傳進展 國際油價整周暴跌逾10%","原油／能源"),
 news("m7","AI熱潮點燃先進封裝軍備競賽 全球砸近280億美元擴產","AI需求"),
 news("duplicate","產業：DRAM報價上週五普遍下跌，其中DDR5 16Gb均價為60.167美元，跌幅0.82%","報價")
];
const data=audit({generatedAt:"2026-11-09T09:45:36+08:00",status:"ok",items:records},now);
assert.equal(data.schema,1);
assert.equal(data.newsCount,7,"duplicate titles must never inflate coverage");
assert.equal(data.classifierVersion,"2026-11-09-v1.3");
assert.ok(data.directionalHeadlineCount>=2);
assert.ok(data.reportedMarketMoveCount>=2);
assert.ok(data.contextOrEventOnlyCount>=1);
assert.ok(data.sourceCategoryFallbackCount>=1);
assert.equal(data.notAccuracy,true);
assert.equal(data.notHitRate,true);
assert.ok(data.unresolved.every(r=>r.reason!=="conditional_direction"));
assert.equal(reason({impacts:[],observations:[],hits:[],topics:[],topicEvidence:"none"}),"unrecognized");
console.log("recognition audit distinguishes model direction, observed move, ambiguous event and weak source topic");
