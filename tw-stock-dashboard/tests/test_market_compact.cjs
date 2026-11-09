/* Regression: compact homepage must present 41 (cash), 26 (independent correction), 16 (cash+night) without mixing formulas. */
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const ids=["compactMarketSummary","compactAction","compactScore","compactBand","compactScoreType","compactSession","compactOfficial","compactAdjusted","compactNight","compactNightCell","compactEquation","compactScoreFootnote","compactPattern","compactResearch"];
const elements=Object.fromEntries(ids.map(id=>[id,{textContent:"",hidden:false,dataset:{}}]));
global.document={getElementById:id=>elements[id]||null};
global.MarketCommand={scoreBand:score=>({label:score<25?"極度偏空":score<45?"偏空觀察":"中性觀望"})};
const logic=require("../docs/market-compact.js");
assert.equal(logic.safeScore(null),"—");
assert.equal(logic.safeScore(16.4),"16");
assert.equal(logic.validScore(NaN),false);
global.MarketCompact.render({score:16,officialScore:41,officialDate:"2026-10-16",date:"2026-10-19",level:"STOP",reference:true,delta:-25});
assert.equal(elements.compactScore.textContent,"16");
assert.equal(elements.compactOfficial.textContent,"41");
assert.equal(elements.compactNight.textContent,"-25");
assert.equal(elements.compactAction.textContent,"暫緩新倉");
assert.equal(elements.compactBand.textContent,"極度偏空");
assert.equal(elements.compactNightCell.hidden,false);
assert.ok(elements.compactEquation.textContent.includes("不參與此運算"));
global.MarketCompact.review({valid:true,adjusted:26,status:"rebound"},{name:"超跌觀察｜反轉未確認"});
assert.equal(elements.compactAdjusted.textContent,"26");
assert.equal(elements.compactPattern.hidden,false);
global.MarketCompact.render({score:null,officialScore:41,officialDate:"2026-10-16",date:"2026-10-20",level:"STOP",reference:false,delta:null,post:true});
assert.equal(elements.compactScore.textContent,"—");
assert.equal(elements.compactNightCell.hidden,true);
assert.equal(elements.compactOfficial.textContent,"41");
assert.equal(elements.compactAction.textContent,"暫緩新倉");
assert.match(elements.compactSession.textContent,/前次正式資料日 2026-10-16/);
assert.match(elements.compactEquation.textContent,/前次收盤 41 分/);
global.MarketCompact.render({score:null,officialScore:52,officialDate:"2026-10-21",date:"2026-10-22",level:"WAIT",reference:false,post:true});
assert.equal(elements.compactScore.textContent,"—");
assert.equal(elements.compactOfficial.textContent,"52");
assert.equal(elements.compactAction.textContent,"今日盤中待確認");
assert.match(elements.compactSession.textContent,/前次正式資料日 2026-10-21/);
assert.match(elements.compactEquation.textContent,/前次收盤 52 分/);
global.MarketCompact.render({score:15,officialScore:11,officialDate:"2026-10-22",date:"2026-10-27",level:"WAIT",reference:true,provisional:true,delta:4,post:true});
assert.equal(elements.compactScore.textContent,"15");
assert.equal(elements.compactOfficial.textContent,"11");
assert.equal(elements.compactNight.textContent,"+4");
assert.match(elements.compactScoreType.textContent,/今日 TX 盤中參考試算/);
assert.match(elements.compactEquation.textContent,/未經樣本外回測/);
assert.match(elements.compactScoreFootnote.textContent,/不授權交易/);
assert.match(elements.compactSession.textContent,/前次正式 2026-10-22/);
// Today's quote-breadth score is not the previous-session official Risk Score.
global.MarketCompact.render({score:48,officialScore:0,officialDate:"2026-10-30",
 date:"2026-11-02",level:"WAIT",reference:false,post:true,
 breadthProvisional:true,breadthSample:1518,breadthProxy:1403});
assert.equal(elements.compactScore.textContent,"48");
assert.equal(elements.compactOfficial.textContent,"0");
assert.match(elements.compactScoreType.textContent,/非正式 Risk Score/);
assert.match(elements.compactBand.textContent,/市場報價偏弱/);
assert.match(elements.compactEquation.textContent,/委託價估計/);
assert.match(elements.compactScoreFootnote.textContent,/不授權交易/);
// Provisional grade must use same-day validated sample and reject stale or old quotes.
const {indicativeMarketBreadthScore}=require("../docs/market-command.js");
const live=JSON.parse(fs.readFileSync(path.join(__dirname,"../docs/data/g_intraday/latest.json"),"utf8"));
if(live.indicativeQuoteBreadth?.quality==="indicative-price-with-orderbook-proxy"){
 const published=new Date(live.publishedAt),now=new Date(published.getTime()+2*60000);
 const grade=indicativeMarketBreadthScore(live,now);
 const summary=live.indicativeQuoteBreadth.total;
 assert.ok(grade,"today's validated breadth should yield a provisional numeric score");
 assert.equal(grade.score,Math.round(summary.up*100/summary.sample));
 assert.equal(grade.sample,summary.sample);
 assert.equal(indicativeMarketBreadthScore(live,new Date(published.getTime()+70*60000)),null);
 assert.equal(indicativeMarketBreadthScore({...live,asOfDate:"1999-01-01"},now),null);
}
const html=fs.readFileSync(path.join(__dirname,"../docs/index.html"),"utf8");
for(const id of ids)assert.ok(html.includes('id="'+id+'"'),"missing compact node "+id);
assert.ok(html.indexOf('id="compactMarketSummary"')<html.indexOf('id="marketRiskDetails"'));
assert.ok(html.indexOf('id="commandReasons"')<html.indexOf('id="marketRiskDetails"'));
console.log("compact market score UX: formal vs independent correction vs night and stale handling OK");
