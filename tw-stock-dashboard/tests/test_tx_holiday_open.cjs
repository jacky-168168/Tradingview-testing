/* 2026/10/27: Friday 10/23 + Monday 10/26 not active trading sessions.
 * Do not reuse the 10/22 overnight move as 10/27 market-opening score.
 * A fresh same-day TX trade informs live monitoring, NOT official cash Risk Score. */
const assert=require("node:assert/strict"),logic=require("../docs/market-command.js"),fs=require("node:fs"),path=require("node:path");
const at=s=>new Date(s+"+08:00");
const t=at("2026-10-27T09:08:00");
const risk={date:"2026-10-22",score:11};
const old={asOfDate:"2026-10-22",contract:"202611",quality:"paired-day-night",
 day:{date:"20261022",contract:"202611",close:46272},
 night:{date:"20261022",contract:"202611",close:45654,reportQueryDate:"2026-10-27"},
 nightVsDayPct:-1.336};
assert.equal(logic.overnightRisk(old,risk,t),null,"Do not call the Oct 22 afterhours snapshot yesterday on Oct 27");
assert.equal(logic.verifiedNightPreview(risk,old,at("2026-10-27T08:58:00")),null,"A 5-day rollover cannot become today's premarket Risk Score");
const q={status:"ok",quality:"dated-third-party-snapshot",asOfDate:"2026-10-27",symbol:"WTX&",
 last:46809,reference:46234,changePoints:575,changePct:1.244,
 quoteTime:"2026-10-27T09:04:55+08:00",source:"Yahoo"};
const live=logic.verifiedTXIntraday(q,t);
assert.ok(live&&live.last===46809,"Today 09:04 TX is accepted");
assert.ok(Math.abs(live.pct-1.244)<0.002,"Today TX comparison is calculated against its documented reference");
const post=logic.postOpenState(risk,t,null,null,live);
assert.equal(post.baseline,null,"No fabricated 0/100 baseline");
assert.ok(post.flags.some(f=>f.code==="TODAY_TX_VERIFIED"),"Today TX appears in market status");
assert.match(post.headline,/今日 TX/);
assert.equal(post.level,"WAIT","Positive TX alone does not authorize new stock buys");
for(const wrong of [
 {...q,asOfDate:"2026-10-22"},{...q,quoteTime:"2026-10-22T09:04:55+08:00"},
 {...q,quoteTime:"2026-10-27T09:09:00+08:00"},{...q,status:"unavailable"},
 {...q,quoteTime:"2026-10-27T08:40:00+08:00"},
 {...q,reference:48000}])
 assert.equal(logic.verifiedTXIntraday(wrong,t),null,"Reject invalid/stale/inconsistent TX");
assert.equal(logic.verifiedTXIntraday(q,at("2026-10-27T09:31:00")),null,"Expire quote after 25 minutes");
const html=fs.readFileSync(path.join(__dirname,"../docs/index.html"),"utf8");
assert.match(html,/MarketCommand\.applyTXLive\(q\?TX_LIVE:null\)/);
assert.match(html,/MarketCommand\.applyTXLive\(null\)/);
assert.match(html,/lag>4/);
console.log("PASS 10/27 open TX is fresh, 10/22 stale night ignored, false 0/100 removed, outdated quotes rejected");
