'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const base='tw-stock-dashboard/docs/';
const compact=fs.readFileSync(base+'market-compact.js','utf8');
const market=fs.readFileSync(base+'market-command.js','utf8');
const stamp=Date.parse('2026-11-02T19:15:00+08:00');
class FixedDate extends Date{
  constructor(...args){super(...(args.length?args:[stamp]))}
  static now(){return stamp}
}
const els=new Map();
function el(id){
 if(!els.has(id))els.set(id,{id,textContent:'',dataset:{},style:{},className:'',hidden:false,
    children:[],replaceChildren(){this.children=[]},appendChild(v){this.children.push(v)}});
 return els.get(id);
}
const document={getElementById:el,createElement:tag=>el('temporary_'+tag+'_'+els.size)};
const window={};
const runtime={window,document,Date:FixedDate,Intl,console,
 fetch:async()=>{throw Error('Deliberately offline mocked extra research data')}};
vm.runInNewContext(compact,runtime,{filename:'market-compact.js'});
vm.runInNewContext(market,runtime,{filename:'market-command.js'});
const app=window.MarketCommand;
assert(app&&app.applyOfficialClose,'Fast official close display function must exist');
const old={dataDate:'2026-10-30',risk:{date:'2026-10-30',score:0,breadth:8.9,dayRet:-2.49}};
const official={quality:'official-twse-close-risk-v1',asOfDate:'2026-11-02',
 publishedAt:'2026-11-02T19:08:36+08:00',
 risk:{date:'2026-11-02',score:12,index:44920.14,breadth:53.7,foreign:-735.2,ret5:-2.44,ret20:-6.3,state:'🔴 Risk OFF'},
 source:{officialIndexClose:44920.14,observedIndexClose:44920.14}};
(async()=>{
 await app.refresh(old);
 assert.equal(el('compactScore').textContent,'—','Previous 10/30 0 must not be shown as 11/2');
 assert.equal(app.applyOfficialClose(official),true);
 assert.equal(el('compactScore').textContent,'12','Actual homepage hero must show 11/2 official 12');
 assert.equal(el('commandScore').textContent,'12','Detailed command Risk Score must match same-day official');
 assert.match(el('compactScoreType').textContent,/TWSE/);
 assert.match(el('compactSession').textContent,/2026-11-02/);
 app.applyIntraday(null);
 app.applyFutures(null);
 assert.equal(el('compactScore').textContent,'12','Futures/breadth refresh cannot erase confirmed official close');
 assert.equal(app.applyOfficialClose({...official,asOfDate:'2026-11-01'}),false);
 assert.equal(el('compactScore').textContent,'12','Bad fallback cannot erase valid official score');
 await app.refresh({dataDate:'2026-11-02',risk:{date:'2026-11-02',score:18,breadth:55,dayRet:0}});
 assert.equal(el('compactScore').textContent,'18','Full same-date official dashboard must supersede standalone fallback');
 console.log('PASS RENDERED HOMEPAGE: 11/02 19:15 shows 12/100 and recovers from historical pending');
})().catch(error=>{console.error(error);process.exitCode=1});
