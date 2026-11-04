const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const root=path.resolve(__dirname,"../docs");
const home=require("../docs/tw-vix-home.js");
const sample=JSON.parse(fs.readFileSync(path.join(root,"data/research/tw_vix/latest.json"),"utf8"));
const html=fs.readFileSync(path.join(root,"index.html"),"utf8");

test("homepage official Taiwan VIX card and links have correct units",()=>{
 for(const id of ["twVixPanel","twVixValue","twVixChange","twVixP20","twVixP60","twVixAt","twVixMood","twVixStatus","twVixRetry","twVixChart","twVixGuide"])
  assert.match(html,new RegExp('id="'+id+'"'),id);
 assert.ok(html.includes('src="./tw-vix-home.js'));
 assert.ok(html.includes('href="./tw-vix-home.css'));
 assert.ok(html.includes("官方 13:45 日收盤"));
 assert.ok(html.includes("https://www.taifex.com.tw/cht/7/vixDaily3MNew"));
 assert.ok(html.indexOf('id="twVixPanel"')<html.indexOf('id="retailSurvival"'));
});
test("source must be official and the daily change must reconcile",()=>{
 const rows=home.check(sample);
 assert.equal(rows.length,2);
 assert.equal(rows.at(-1).value,36.83);
 assert.equal(rows.at(-1).change,5.53);
 assert.throws(()=>home.check({...sample,version:"TW_VIX_WANTGOO_QUOTES_V1"}));
 assert.throws(()=>home.check({...sample,sourceUrl:"https://www.wantgoo.com/index/vixtwn"}));
 assert.throws(()=>home.check({...sample,rows:[sample.rows[0],{...sample.rows[1],changePct:88}]}));
});
test("market VIX high cannot directly overwrite the original Risk Score",()=>{
 const src=fs.readFileSync(path.join(root,"tw-vix-home.js"),"utf8");
 assert.ok(!src.includes("risk.score="));
 assert.ok(src.includes("高 VIX 不代表底部已確認"));
});
test("20d/60d percentiles need 20/60 real dated sessions",()=>{
 assert.equal(home.percentile(sample.rows,20),null);
 assert.equal(home.percentile(sample.rows,60),null);
 const rows=Array.from({length:60},(_,i)=>({value:15+i/2}));
 assert.equal(home.percentile(rows,20),100);
 assert.equal(home.percentile(rows,60),100);
});
test("risk guidance reports volatility, never promises long entry",()=>{
 assert.equal(home.mood(sample.rows.at(-1)).label,"波動升溫");
 assert.match(home.mood({...sample.rows.at(-1),change:-.8}).text,/不能單獨當作進場信號/);
 assert.equal(home.mood(sample.rows[0]).label,"前日無資料");
});
test("previous official close is labelled, not simulated as intraday quote",()=>{
 const now=new Date("2026-11-04T02:00:00Z");
 const info=home.timeStatus(sample,now);
 assert.equal(info.stale,false);
 assert.match(info.text,/非盤中即時 VIX/);
 assert.match(info.text,/收盤尚未取得/);
 const future={...sample,sourceObservationAt:"2026-11-05T13:45:00+08:00"};
 assert.equal(home.timeStatus(future,now).stale,true);
});
