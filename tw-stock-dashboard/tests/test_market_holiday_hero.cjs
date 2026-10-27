/* UI regression for 2026-10-27 reopen following Friday/holiday shutdown.
 * A current 09:04 TX trade must NOT leave primary risk hero at false 0/100. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const code=fs.readFileSync('tw-stock-dashboard/docs/market-command.js','utf8'),stamp=Date.parse('2026-10-27T09:08:00+08:00');
class FixedDate extends Date{constructor(...args){super(...(args.length?args:[stamp]))}static now(){return stamp}}
const elements=new Map(),element=id=>{
 if(!elements.has(id))elements.set(id,{id,textContent:'',dataset:{},style:{},className:'',hidden:false,href:'',children:[],
  replaceChildren(){this.children=[]},appendChild(node){this.children.push(node)}});
 return elements.get(id);
};
const doc={getElementById:element,createElement:tag=>element('temp-'+tag+'-'+elements.size)};
const scope={},ctx={window:scope,document:doc,Date:FixedDate,Intl,console,fetch:async()=>{throw Error('No network in regression')}};
vm.runInNewContext(code,ctx,{filename:'market-command.js'});
const app=scope.MarketCommand;
const r={date:'2026-10-22',score:11,breadth:24.6},snap={dataDate:r.date,risk:r};
const old={asOfDate:'2026-10-22',contract:'202611',quality:'paired-day-night',nightVsDayPct:-1.336,
 day:{date:'20261022',contract:'202611',close:46272},
 night:{date:'20261022',contract:'202611',close:45654,reportQueryDate:'2026-10-27'}};
const q={status:'ok',quality:'dated-third-party-snapshot',asOfDate:'2026-10-27',symbol:'WTX&',
 last:46809,reference:46234,changePoints:575,changePct:1.244,quoteTime:'2026-10-27T09:04:55+08:00'};
(async()=>{
 await app.refresh(snap);
 app.applyFutures(old);
 assert.equal(element('commandScore').textContent,'—','Old Oct 22 report must not generate 0/100 on Oct 27');
 assert.doesNotMatch(element('commandCashReference').textContent,/昨夜台指|盤前基準 0\/100/);
 app.applyTXLive(q);
 assert.equal(element('commandScore').textContent,'—','Live TX +1.24% is not an independent formal cash Risk Score');
 assert.match(element('commandStatus').textContent,/今日 TX \+1\.24%/);
 assert.match(element('commandCashReference').textContent,/46,809/);
 assert.match(element('commandCashReference').textContent,/10\/22|2026-10-22/);
 assert.match(element('commandScoreDescription').textContent,/當日台指報價已驗證/);
 assert.equal(element('marketCommand').dataset.level,'WAIT','Positive TX must not grant unconditional stock buying');
 assert.equal(element('commandScoreFill').style.width,'0%','Unknown score fills no score gauge');
 assert(!element('commandFullFlags').children.some(x=>/盤前基準 0/.test(x.children?.[0]?.textContent||'')),'No stale zero-score chip');
 app.applyTXLive({...q,quoteTime:'2026-10-22T09:04:55+08:00'});
 assert.doesNotMatch(element('commandCashReference').textContent,/46,809/,'Old TX is refused');
 console.log('PASS 10/27 actual hero renders pending, verified current TX +1.24%, no old overnight zero');
})().catch(e=>{console.error(e);process.exitCode=1});
