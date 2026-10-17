/* US DIX / SPX / GEX display contract, with no forward-looking synthetic data. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {validate,recent,dailyAnalysis}=require("../docs/us-options-risk.js");
const rows=Array.from({length:370},(_,i)=>{
 const dt=new Date(Date.UTC(2025,0,1+i)).toISOString().slice(0,10);
 return [dt,5000+i,42+i*0.01,10000000+i*1000];
});
const data={columns:["date","spx","dixPct","gex"],asOf:rows[rows.length-1][0],rows};
assert.deepEqual(validate(data),rows);
assert.equal(recent(rows,"max").length,370);
assert.ok(recent(rows,"2y").length===370);
assert.ok(recent(rows,"6m").length<200&&recent(rows,"6m").length>160);
assert.throws(()=>validate({...data,asOf:"2027-01-01"}),/日期/);
assert.throws(()=>validate({...data,columns:["date","spx","gex","dixPct"]}),/格式/);
assert.throws(()=>validate({...data,rows:[...rows.slice(0,100),rows[100],rows[100],...rows.slice(101)]}),/順序/);
assert.throws(()=>validate({...data,rows:rows.map((r,i)=>i===3?[r[0],-1,43,0]:r)}),/數值/);
assert.equal(dailyAnalysis(rows.slice(0,21)),null,"Short data must not invent a signal");
const synthetic=dailyAnalysis(rows);
assert.equal(synthetic.date,rows[rows.length-1][0]);
assert.equal(synthetic.lines.length,3);
assert.ok(synthetic.lines[0].includes("S&P 500")&&synthetic.lines[1].includes("DIX")&&synthetic.lines[2].includes("GEX"));
const live=JSON.parse(fs.readFileSync(path.join(__dirname,"../docs/data/research/us_options/history.json"),"utf8"));
const real=dailyAnalysis(validate(live));
assert.equal(real.date,live.asOf);
assert.equal(real.lines.length,3);
if(live.asOf==="2026-10-16"){
 assert.match(real.headline,/短線偏弱/);
 assert.match(real.lines[0],/單日 -1\.09%.*近5日 -1\.95%/);
 assert.match(real.lines[1],/44\.65%.*\+3\.14.*-2\.67/);
 assert.ok(real.metrics.gexRelative<0.02,"GEX collapse must not be described as strong market stabilization");
 assert.ok(real.lines[2].includes("緩和波動的效果可能減弱"));
}
assert.ok(real.disclaimer.includes("非漲跌方向預測"));
const home=fs.readFileSync(path.join(__dirname,"../docs/index.html"),"utf8");
const js=fs.readFileSync(path.join(__dirname,"../docs/us-options-risk.js"),"utf8");
const py=fs.readFileSync(path.join(__dirname,"../src/update_us_options.py"),"utf8");
for(const id of ["usOptionsRisk","usopChart","usopChartWrap","usopDate","usopStatus","usopMessage","usopDailyAnalysis","usopDailyTitle","usopDailyList","usopDailyMeta","usopValuedix","usopValuespx","usopValuegex"])assert.ok(home.includes('id="'+id+'"'),"Missing chart DOM "+id);
for(const range of ["6m","2y","max"])assert.ok(home.includes('data-usop-range="'+range+'"'));
for(const key of ["dix","spx","gex"])assert.ok(home.includes('data-usop-series="'+key+'"'));
assert.ok(home.includes('href="./us-options-risk.css?v=')&&home.includes('src="./us-options-risk.js?v='));
assert.ok(!home.includes('<details class="card" id="usOptionsRisk"'),"Chart cannot be hidden behind collapsed details");
assert.ok(js.includes('pointermove')&&js.includes('ArrowLeft')&&js.includes('pointerdown'));
assert.ok(py.includes('def history_chart(us)')&&py.includes('DATA/"history.json"'));
assert.ok(!js.includes("RiskScore=")&&!js.includes("DATA.risk.score="),"Historical chart must not modify market scoring");
console.log("Interactive three-series US options chart DOM, validation, date ranges, no placeholders: OK");
