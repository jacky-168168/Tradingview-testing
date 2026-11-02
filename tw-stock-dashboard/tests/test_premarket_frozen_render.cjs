/* Regression: keep a dated premarket snapshot as ONE hero score from 08:35 through night.
 * Official 11/03 close, provisional breadth and futures must NEVER overwrite it. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const dir='tw-stock-dashboard/docs/';
const html=fs.readFileSync(dir+'index.html','utf8');
const frozenNow=Date.parse('2026-11-03T20:44:00+08:00');
class FixedDate extends Date{
 constructor(...a){super(...(a.length?a:[frozenNow]))}
 static now(){return frozenNow}
}
const elements=new Map();
function el(id){
 if(!elements.has(id))elements.set(id,{id,textContent:'',dataset:{},
  hidden:false,className:'',style:{},children:[],href:'',
  replaceChildren(){this.children=[]},appendChild(v){this.children.push(v)}});
 return elements.get(id);
}
const document={getElementById:el,createElement:tag=>el(tag+elements.size)};
const scope={};
const runtime={window:scope,document,Date:FixedDate,Intl,console,
 fetch:async()=>{throw Error('test: external search not used')}};
vm.runInNewContext(fs.readFileSync(dir+'market-compact.js','utf8'),runtime,{filename:'market-compact.js'});
vm.runInNewContext(fs.readFileSync(dir+'market-command.js','utf8'),runtime,{filename:'market-command.js'});
el('compactMarketSummary').dataset.fixedPremarket='true';
const app=scope.MarketCommand;
const prior={dataDate:'2026-11-02',risk:{date:'2026-11-02',score:12,breadth:53.7,dayRet:-.65}};
const p={quality:'fixed-premarket-reference-v1',targetDate:'2026-11-03',lockedForTradingDate:'2026-11-03',
 publishedAt:'2026-11-03T08:35:00+08:00',score:12,baseScore:12,baseDate:'2026-11-02',
 adjustment:0,txPct:null,source:'前一交易日正式分數，無合格TX夜盤'};
const complete={dataDate:'2026-11-03',risk:{date:'2026-11-03',score:72,breadth:69,dayRet:2.1}};
(async()=>{
 await app.refresh(prior);
 assert.equal(el('compactScore').textContent,'—','No valid morning reference must not fall back to 11/02 Risk Score');
 assert.match(el('compactAction').textContent,/盤前基準未建立/);
 assert.equal(app.applyFrozenPremarket(p),true);
 assert.equal(el('compactScore').textContent,'12','Daily morning snapshot must show as only hero score');
 assert.match(el('compactScoreType').textContent,/固定基準/);
 assert.equal(app.applyFrozenPremarket({...p,asOfDate:'2026-11-02',targetDate:'2026-11-02'}),false);
 assert.equal(el('compactScore').textContent,'12','Mismatched date must not replace locked score');
 app.applyIntraday({quality:'intraday-provisional-allmarket',asOfDate:'2026-11-03'});
 app.applyFutures(null);
 app.applyTXLive(null);
 assert.equal(el('compactScore').textContent,'12','Other sources must not overwrite premarket snapshot');
 await app.refresh(complete);
 assert.equal(el('compactScore').textContent,'12','Different officially completed close score cannot replace morning reference');
 const official={quality:'official-twse-close-risk-v1',asOfDate:'2026-11-03',publishedAt:'2026-11-03T19:30:00+08:00',
  risk:{date:'2026-11-03',score:72,index:45321},source:{officialIndexClose:45321}};
 assert.equal(app.applyOfficialClose(official),true);
 assert.equal(el('compactScore').textContent,'12','Evening official 72 must not replace locked morning 12');
 assert.equal(el('commandScore').textContent,'12','Detailed command score must match frozen morning');
 assert.equal(el('marketCommand').dataset.premarket,'true');
 assert.match(el('compactSession').textContent,/2026-11-03/);
 assert.ok(html.includes('data-fixed-premarket="true"'));
 assert.ok(html.includes('await loadFrozenPremarket()'));
 console.log('PASS PREMARKET IMMUTABLE: 08:35 score 12 stays 12 through 20:44 despite 72 close');
})().catch(e=>{console.error(e);process.exitCode=1});
