"use strict";
const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const {validate,recent,zone,explain}=require("../docs/fear-greed-home.js");
const dates=Array.from({length:400},(_,i)=>new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10));
const rows=dates.map((d,i)=>[d,35+i%45,5000+i*2]);
const doc={version:"US_CNN_FEAR_GREED_SPX_V1",columns:["date","fearGreed","spx"],asOf:dates.at(-1),rows};
test("trustworthy dated data only",()=>{
 assert.equal(validate(doc).length,400);
 assert.throws(()=>validate({...doc,asOf:"2028-05-01"}),/日期/);
 assert.throws(()=>validate({...doc,rows:rows.map((r,i)=>i===5?[r[0],101,r[2]]:r)}),/範圍/);
 assert.throws(()=>validate({...doc,columns:["date","spx","fearGreed"]}),/格式/);
 assert.throws(()=>validate({...doc,rows:[rows[0],rows[0],...rows.slice(1)]}),/異常/);
 assert.throws(()=>validate({...doc,rows:rows.map((r,i)=>i===6?[r[0],r[1],0]:r)}),/範圍/);
});
test("independent missing values display as gaps rather than invented numbers",()=>{
 const partial={...doc,version:"US_CNN_FEAR_GREED_SPX_V2",rows:rows.map((r,i)=>i===399?[r[0],r[1],null]:r)};
 assert.equal(validate(partial).at(-1)[2],null);
 const reverse={...partial,rows:rows.map((r,i)=>i===399?[r[0],null,r[2]]:r)};
 assert.equal(validate(reverse).at(-1)[1],null);
 assert.throws(()=>validate({...partial,rows:rows.map((r,i)=>i===399?[r[0],null,null]:r)}),/範圍/);
});
test("zone labels and range choices",()=>{
 assert.equal(zone(0).label,"極度恐懼");
 assert.equal(zone(24.99).label,"極度恐懼");
 assert.equal(zone(25).label,"恐懼");
 assert.equal(zone(45).label,"中立");
 assert.equal(zone(75).label,"極度貪婪");
 assert.equal(recent(rows,"max").length,400);
 assert.ok(recent(rows,"6m").length>150&&recent(rows,"6m").length<200);
 assert.equal(recent(rows,"2y").length,400);
});
test("explanation uses only past data without automatic buy/sell",()=>{
 assert.equal(explain(rows.slice(0,21)),null);
 const r=explain(rows);
 assert.equal(r.date,dates.at(-1));
 assert.ok(r.title&&r.guide&&r.risk);
 const severe=rows.slice();severe[399]=[dates.at(-1),12,4800];
 const q=explain(severe);assert.equal(q.zone.label,"極度恐懼");
 assert.match(q.guide,/不要只因分數低/);
});
test("homepage replaces triple DIX chart but retains study reference",()=>{
 const html=fs.readFileSync(path.join(__dirname,"../docs/index.html"),"utf8");
 assert.match(html,/id="fearGreedPanel"/);
 assert.match(html,/fear-greed-home.js/);
 assert.match(html,/fear-greed-home.css/);
 assert.match(html,/原 DIX／GEX 研究/);
 assert.doesNotMatch(html,/id="usOptionsRisk"/);
});
