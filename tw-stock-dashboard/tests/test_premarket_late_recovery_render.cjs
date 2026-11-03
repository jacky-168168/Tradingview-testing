/* Verify 11/03 10:37 late recovery instead of blank, and missing-cron browser fallback. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root='tw-stock-dashboard/docs/';
const html=fs.readFileSync(root+'index.html','utf8');
const stamp=Date.parse('2026-11-03T10:45:00+08:00');
class FixedDate extends Date{
  constructor(...args){super(...(args.length?args:[stamp]))}
  static now(){return stamp}
}
const els=new Map();
function el(id){
  if(!els.has(id))els.set(id,{id,textContent:'',dataset:{},style:{},hidden:false,
    className:'',children:[],replaceChildren(){this.children=[]},appendChild(x){this.children.push(x)}});
  return els.get(id);
}
const document={getElementById:el,createElement:tag=>el('tmp'+tag+els.size)};
const scope={};
const runtime={window:scope,document,Date:FixedDate,Intl,console,
 fetch:async()=>{throw Error('Synthetic test does not use external feeds')}};
vm.runInNewContext(fs.readFileSync(root+'market-compact.js','utf8'),runtime);
vm.runInNewContext(fs.readFileSync(root+'market-command.js','utf8'),runtime);
el('compactMarketSummary').dataset.fixedPremarket='true';
const app=scope.MarketCommand;
const old={dataDate:'2026-10-30',risk:{date:'2026-10-30',score:0,breadth:8.9}};
const late={quality:'fixed-premarket-reference-v1',targetDate:'2026-11-03',
 lockedForTradingDate:'2026-11-03',publishedAt:'2026-11-03T10:37:41+08:00',
 calculationMode:'late-recovery',score:12,baseScore:12,baseDate:'2026-11-02',
 adjustment:0,txPct:null,txSource:null,method:'FIXED_REFERENCE_NOT_OFFICIAL_INTRADAY_RISK'};
const proof={quality:'official-twse-close-risk-v1',asOfDate:'2026-11-02',
 publishedAt:'2026-11-02T21:00:00+08:00',risk:{date:'2026-11-02',score:12,index:44920.14},
 source:{officialIndexClose:44920.14}};
(async()=>{
 await app.refresh(old);
 assert.equal(String(el('compactScore').textContent),'—','No verified data should not show stale 10/30');
 assert.equal(app.applyFrozenPremarket(late),true,'10:37 late recovery should pass source and timestamp validation');
 assert.equal(String(el('compactScore').textContent),'12','Real homepage hero must show 12/100');
 assert.equal(String(el('commandScore').textContent),'12','Full Risk Score section must match');
 assert.match(String(el('compactSession').textContent),/排程失效後補建/);
 assert.match(String(el('compactEquation').textContent),/事後依前收盤補建/);
 const fallback=app.recoverFrozenFromOfficial(proof,new FixedDate());
 assert.ok(fallback,'Official 11/02 close should recover 11/03 if scheduling never fires');
 assert.equal(fallback.score,12);
 assert.equal(fallback.targetDate,'2026-11-03');
 assert.equal(fallback.calculationMode,'browser-recovery');
 assert.equal(app.validateFrozenPremarket(fallback,new FixedDate()),fallback,'Recovered data must also pass model validator');
 assert.equal(app.applyFrozenPremarket(fallback),true);
 assert.equal(String(el('compactScore').textContent),'12','Further fallback cannot overwrite once frozen');
 const prebuilt={...late,publishedAt:'2026-11-02T21:30:00+08:00',calculationMode:'after-close-prebuild'};
 assert.equal(app.validateFrozenPremarket(prebuilt,new FixedDate()),prebuilt,'Prior night prebuild must be accepted next day');
 const future={...late,publishedAt:'2026-11-03T19:00:00+08:00'};
 assert.equal(app.validateFrozenPremarket(future,new FixedDate()),null,'Future delayed recovery must be rejected');
 assert.match(html,/data\/market_premarket\/"\+today\+"\.json/,'Homepage must fetch immutable date-keyed archive');
 assert.ok(html.includes('recoverFrozenFromOfficial(proof)'), 'Homepage fallback must use verified official close');
 console.log('PASS 2026-11-03 10:45 HERO 12/100 LATE RECOVERY; PREBUILT & BROWSER FAILSAFE VERIFIED');
})().catch(e=>{console.error(e);process.exitCode=1});
