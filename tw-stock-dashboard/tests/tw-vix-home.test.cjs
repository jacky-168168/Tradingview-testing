const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const root=path.resolve(__dirname,"../docs");
const home=require("../docs/tw-vix-home.js");
const sample=JSON.parse(fs.readFileSync(path.join(root,"data/research/tw_vix/latest.json"),"utf8"));
const html=fs.readFileSync(path.join(root,"index.html"),"utf8");

test("homepage Taiwan VIX card and timestamp/source links are present",()=>{
 for(const id of ["twVixPanel","twVixValue","twVixChange","twVixP20","twVixP60","twVixAt","twVixMood","twVixStatus","twVixRetry","twVixChart","twVixGuide"])
  assert.match(html,new RegExp('id="'+id+'"'),id);
 assert.ok(html.includes('src="./tw-vix-home.js'));
 assert.ok(html.includes('href="./tw-vix-home.css'));
 assert.ok(html.includes('https://www.wantgoo.com/index/vixtwn'));
 assert.ok(html.includes('https://www.taifex.com.tw/cht/7/vixDaily3MNew'));
 assert.ok(html.indexOf('id="twVixPanel"')<html.indexOf('id="retailSurvival"'));
});
test("verified VIXTWN source record is valid and separate from Cboe VIX",()=>{
 const rows=home.check(sample);
 assert.equal(rows.length,1);
 assert.equal(rows[0].value,39.92);
 assert.equal(rows[0].change,3.09);
 assert.equal(sample.sourceName.includes("非期交所正式收盤"),true);
 assert.throws(()=>home.check({...sample,version:"CBOE_VIX_DAILY_V1"}));
});
test("market VIX high cannot become arbitrary same-day Risk Score",()=>{
 const src=fs.readFileSync(path.join(root,"tw-vix-home.js"),"utf8");
 assert.ok(!src.includes("risk.score="));
 assert.ok(src.includes("非底部"));
});
test("20d and 60d percentiles require complete unique market sessions",()=>{
 assert.equal(home.percentile(sample.rows,20),null);
 assert.equal(home.percentile(sample.rows,60),null);
 const rows=Array.from({length:60},(_,i)=>({value:15+i/2}));
 assert.equal(home.percentile(rows,20),100);
 assert.equal(home.percentile(rows,60),100);
});
test("fear classification is descriptive only and falling VIX cannot authorize entries",()=>{
 assert.equal(home.mood(sample.rows[0]).label,"波動升溫");
 assert.match(home.mood({...sample.rows[0],change:-.8}).text,/不能單獨當作進場信號/);
});
test("older day in market hours is marked stale, not recast as live VIX",()=>{
 const today=new Date("2026-11-04T02:00:00Z"); // 10:00 Taipei
 const old={...sample,sourceObservationAt:"2026-11-03T13:40:00+08:00",rows:[{...sample.rows[0],date:"2026-11-03",time:"13:40"}],asOfDate:"2026-11-03"};
 assert.equal(home.timeStatus(old,today).stale,true);
 assert.equal(home.timeStatus(sample,new Date("2026-11-04T05:00:00Z")).stale,false);
});
