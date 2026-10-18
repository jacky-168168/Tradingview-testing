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
const {calculate,plainLanguage}=require("../docs/us-options-daily-report.js");
assert.equal(calculate(rows.slice(0,50)),null,"Insufficient six-month sample cannot produce a fabricated classification");
const detailed=calculate(rows);
assert.equal(detailed.date,rows.at(-1)[0]);
assert.equal(detailed.rows.length,3,"DIX, S&P500 and GEX");
assert.equal(detailed.points.length,4);
assert.ok(detailed.watch.length>=2&&detailed.watch.length<=3);
assert.ok(["red","orange","yellow","green","white"].includes(detailed.status.code));
assert.ok(detailed.compare&&detailed.compare.date===rows.at(-2)[0],"Compare prior close under identical rules");
assert.ok(detailed.rows.every(x=>x.where&&x.direction));
const easy=plainLanguage(detailed);
assert.equal(easy.cards.length,3);
assert.deepEqual(easy.cards.map(x=>x.id),["spx","dix","gex"]);
assert.ok(easy.summary.length<80,"Above fold summary should be brief");
assert.ok(easy.cards[1].detail.includes("不等於大戶正在買超"),"DIX must not be sold as net buy volume");
assert.ok(easy.cards[2].detail.includes("不能直接預測股價漲跌"),"GEX is not a direction oracle");
assert.equal(easy.watch.length,2);
const realDetailed=calculate(validate(live));
assert.equal(realDetailed.date,live.asOf);
const plainLive=plainLanguage(realDetailed);
assert.equal(plainLive.cards.length,3);
assert.ok(plainLive.summary.length>18&&plainLive.watch.every(x=>x.length<70));

assert.ok(realDetailed.points.length>=3&&realDetailed.points.length<=5);
assert.ok(realDetailed.stats.positions.every(x=>x>=0&&x<=1));
if(live.asOf==="2026-10-16"){
 assert.equal(realDetailed.status.code,"red","All three five-day trends fall in verified 10/16 sample");
 assert.equal(realDetailed.stats.gexStrength,"弱");
 assert.match(realDetailed.resonance,/偏空共振/);
 assert.ok(realDetailed.rows.some(x=>x.name==="DIX"&&x.value==="44.65%"));
}
assert.equal(calculate(validate(live).slice(0,-1)).date,live.rows.at(-2)[0],"Never leak tomorrow's reading into previous day's analysis");
const home=fs.readFileSync(path.join(__dirname,"../docs/index.html"),"utf8");
const js=fs.readFileSync(path.join(__dirname,"../docs/us-options-risk.js"),"utf8");
const py=fs.readFileSync(path.join(__dirname,"../src/update_us_options.py"),"utf8");
// DIX/GEX is retained as a historical research module, not displayed on the home page.
for(const id of ["fearGreedPanel","fgChart","fgSpxChart","fgReportTitle","fgReportBody"])
 assert.ok(home.includes('id="'+id+'"'),"Missing new CNN chart DOM "+id);
assert.ok(home.includes('fear-greed-home.css')&&home.includes('fear-greed-home.js'));
assert.ok(home.includes('原 DIX／GEX 研究'),"Archive reference must stay available");
assert.ok(!home.includes('id="usOptionsRisk"'),"Retired DIX/GEX home chart must not persist");
assert.ok(js.includes('pointermove')&&js.includes('ArrowLeft')&&js.includes('pointerdown'));
assert.ok(py.includes('def history_chart(us)')&&py.includes('DATA/"history.json"'));
assert.ok(js.includes('renderDailyAnalysis(rows,stale)'));
assert.ok(!js.includes("RiskScore=")&&!js.includes("DATA.risk.score="),"Historical chart must not modify market scoring");
console.log("DIX/GEX archived research validated; CNN Fear Greed is primary home US chart: OK");
