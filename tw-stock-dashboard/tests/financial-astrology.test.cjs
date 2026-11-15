'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
let engine=null;
try{require.resolve('astronomy-engine',{paths:[__dirname]});engine=require('../src/financial_astrology/engine.cjs');}
catch(e){if(e.code!=='MODULE_NOT_FOUND')throw e;}
// Existing TW Stock Python CI runs all *.test.cjs without npm install. Astronomy-only
// cases are skipped there; dedicated Financial Astrology Research CI must install npm
// and execute them. UI and event-study regressions still run everywhere.
const research=require('../src/financial_astrology/research.cjs');
const root=path.resolve(__dirname,'../docs');
test('geocentric tropical ecliptic positions have finite degrees and the known 2024 April Sun position',{skip:!engine},()=>{
 const at='2024-04-08T18:00:00Z',p=engine.position('Sun',at);
 assert(p.longitude>15&&p.longitude<25,JSON.stringify(p)); // Sun ~19 Aries
 const e=engine.ephemeris(at);assert.equal(e.length,10);
 for(const b of e){assert(b.longitude>=0&&b.longitude<360);assert(Number.isFinite(b.velocityDegPerDay));}
});
test('known April 8 2024 new moon phase near zero; wrap interpolation is safe',{skip:!engine},()=>{
 const p=engine.phase('2024-04-08T18:21:00Z');
 assert(Math.min(p.angle,360-p.angle)<2,p.angle);
 assert.equal(engine.signed(1-359),2);
 assert.equal(engine.separation(1,359),2);
});
test('aspect errors, invalid horizon and planet are rejected',{skip:!engine},()=>{
 assert.equal(engine.error(359,1,0),2);
 assert.equal(engine.error(359,1,180),178);
 assert.throws(()=>engine.position('Earth','2026-11-15'));
 assert.throws(()=>engine.findAspects('2026-11-15',400));
});
test('live catalogue timestamps are UTC, events ordered, unique and in requested horizon',{skip:!engine},()=>{
 const start='2026-11-15T00:00:00Z',s=engine.build(start,5),ids=new Set();
 assert.equal(s.schema,1);assert.equal(s.snapshot.positions.length,10);
 for(const event of s.events){
   assert(event.utc.endsWith('Z'));assert(Date.parse(event.utc)>=Date.parse(start));
   assert(Date.parse(event.utc)<=Date.parse(start)+5*engine.DAY);
   assert(!ids.has(event.id),'duplicate event '+event.id);ids.add(event.id);
 }
});
test('CSV and exchange calendar reject bad data and support correct timezone',()=>{
 assert.equal(research.localDate('2026-03-09T02:00:00Z','America/New_York'),'2026-03-08');
 assert.throws(()=>research.readPrices('date,close\n2026-01-02,1\n2026-01-02,2'));
 assert.throws(()=>research.readPrices('date,close\n2026-01-03,-1'));
 const p=research.readPrices('date,close\n2026-01-02,100\n2026-01-05,101');
 assert.equal(p.length,2);
});
test('backtest is exploratory and cannot invent verified predictive edge',()=>{
 const prices=Array.from({length:250},(_,i)=>({date:new Date(Date.UTC(2026,0,1+i)).toISOString().slice(0,10),close:100+i}));
 const events=Array.from({length:20},(_,i)=>({id:'fixture-'+i,utc:new Date(Date.UTC(2026,0,1+i*8)).toISOString()}));
 const r=research.study(events,prices,'Asia/Taipei',5);
 assert.equal(r.status,'exploratory');assert.equal(r.oosVerified,false);
 assert.equal(r.sampleCount,20);assert(Number.isFinite(r.meanReturnPct));
 assert.equal(research.study(events.slice(0,2),prices,'Asia/Taipei',5).status,'insufficient');
});
test('page uses safe no-data research defaults and does not alter market risk score',()=>{
 const html=fs.readFileSync(path.join(root,'financial-astrology.html'),'utf8');
 const ui=fs.readFileSync(path.join(root,'financial-astrology-ui.js'),'utf8');
 const index=fs.readFileSync(path.join(root,'index.html'),'utf8');
 assert(html.includes('site-access.js'));
 assert(html.includes('historical')||html.includes('歷史實證'));
 assert(ui.includes('status!==\'verified\'')||ui.includes('oosVerified'));
 assert(!ui.includes('market-command.js'));assert(index.includes('financial-astrology.html'));
 assert(index.includes('market-command.js'),'existing market risk module missing');
});