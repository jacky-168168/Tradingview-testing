/* 10/15 09:07 case: yesterday's official Risk Score 70 is not today's green-light.
 * No overnight or MIS observation is allowed to fabricate a realtime Risk Score. */
const assert=require('node:assert/strict'),fs=require('node:fs');
const logic=require('../docs/market-command.js');
const data=JSON.parse(fs.readFileSync('tw-stock-dashboard/docs/data/latest.json','utf8'));
const futures=JSON.parse(fs.readFileSync('tw-stock-dashboard/docs/data/futures/latest.json','utf8'));
const at=(h,m,day='2026-10-15')=>new Date(day+'T'+String(h).padStart(2,'0')+':'+String(m).padStart(2,'0')+':00+08:00');
const now=at(9,7),risk={date:'2026-10-14',score:70};
const night=logic.overnightRisk(futures,risk,now);
assert(night&&night.pct< -1.7&&night.pct> -1.8,'Official same-month overnight fall must be verified');
assert.strictEqual(logic.overnightRisk({...futures,night:{...futures.night,reportQueryDate:'2026-10-14'}},risk,now),null,'No reuse of other-day futures');
assert.strictEqual(logic.overnightRisk({...futures,day:{...futures.day,contract:'202611'}},risk,now),null,'No cross-contract');
const opened=logic.postOpenState(risk,now,night,null);
assert.equal(opened.level,'STOP');
assert.match(opened.headline,/夜/);
assert(opened.flags.some(x=>x.code==='PENDING_LIVE_BREADTH'));
assert.equal(logic.postOpenState(risk,at(8,58),night,null),null,'Open signal cannot pretend to exist before 9AM');
assert.equal(logic.postOpenState(risk,at(14,30),night,null),null,'Old close cannot masquerade as real open risk outside session');
function snapshot(date='2026-10-15',publishedAt='2026-10-15T09:15:00+08:00',pct=20){
 const sample=1400,up=Math.round(pct/100*sample),down=sample-up;
 return {asOfDate:date,publishedAt,quality:'intraday-provisional-allmarket',
 coverage:{valid:1600,total:1982,exchange:{'上市':{valid:900,total:1089},'上櫃':{valid:700,total:893}}},
 marketBreadth:{quality:'verified-trade-only',total:{up,down,flat:0,sample,upPct:pct},exchange:{'上市':{sample:800},'上櫃':{sample:600}}}};
}
const breadth=logic.tradedBreadth(snapshot(),at(9,18));
assert(breadth&&breadth.pct===20&&breadth.sample===1400);
assert.equal(logic.postOpenState(risk,at(9,18),night,breadth).level,'STOP','Broad intraday sell-off must warn');
assert.equal(logic.postOpenState(risk,at(9,18),night,logic.tradedBreadth(snapshot('2026-10-15','2026-10-15T09:15:00+08:00',72),at(9,18))).level,'WAIT','Even broad recovery cannot invent official green light');
assert.equal(logic.tradedBreadth(snapshot('2026-10-14'),at(9,18)),null,'Yesterday data forbidden');
assert.equal(logic.tradedBreadth(snapshot('2026-10-15','2026-10-15T07:00:00+08:00'),at(9,18)),null,'Old quote forbidden');
const sparse=snapshot();sparse.marketBreadth.total.sample=10;assert.equal(logic.tradedBreadth(sparse,at(9,18)),null,'Partial quote quality forbidden');
assert.equal(logic.postOpenState(risk,now,null,null).level,'WAIT','Neutral unknown market stays cautious');
const html=fs.readFileSync('tw-stock-dashboard/docs/index.html','utf8'),ui=fs.readFileSync('tw-stock-dashboard/docs/market-command.js','utf8');
for(const needle of ['MarketCommand.applyIntraday(snap)','MarketCommand.applyFutures(d)','await loadIntradayMarketBreadth()'])assert(html.includes(needle),'Missing UI integration: '+needle);
assert(ui.includes('post||x.stale?"—"'),'Yesterday\'s primary score must be blank after cash open');
assert(ui.includes('post?(post.breadth?'),'Historical 75.5% breadth may not be presented as today');
assert(ui.includes('昨日')||ui.includes('昨收'));
console.log('PASS October 15 selloff: stale 70 hidden as primary, verified -1.74% TX risk, quality/date-gated live MIS breadth, no fabricated cash score');
