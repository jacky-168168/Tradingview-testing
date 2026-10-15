/* Regression: actually render top Risk Score on 10/15 09:28, not just calculate model.
 * In-browser JavaScript from GitHub Pages must display 55, NOT '--' or yesterday's 70.
 * Uses frozen Taiwan time & dated futures fixture, never mutable latest.json. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ui=fs.readFileSync('tw-stock-dashboard/docs/market-command.js','utf8');
const html=fs.readFileSync('tw-stock-dashboard/docs/index.html','utf8');
const timestamp=Date.parse('2026-10-15T09:28:00+08:00');
class FixedDate extends Date{constructor(...args){super(...(args.length?args:[timestamp]))}static now(){return timestamp}}
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{id,textContent:'',dataset:{},style:{},className:'',hidden:false,href:'',children:[],
 replaceChildren(){this.children=[]},appendChild(v){this.children.push(v)}});return elements.get(id)}
const doc={getElementById:element,createElement:tag=>element('temp-'+tag+'-'+elements.size)};
const scope={};const ctx={window:scope,document:doc,Date:FixedDate,Intl,console,fetch:async()=>{throw Error('Fake remote unavailable')}};
vm.runInNewContext(ui,ctx,{filename:'market-command.js'});
const app=scope.MarketCommand;
assert(app,'MarketCommand must attach to window');
const futures={asOfDate:'2026-10-14',contract:'202610',quality:'paired-day-night',nightVsDayPct:-1.736,
 day:{date:'20261014',contract:'202610',close:48792},
 night:{date:'20261014',contract:'202610',close:47945,reportQueryDate:'2026-10-15'}};
const snapshot={dataDate:'2026-10-14',risk:{date:'2026-10-14',score:70,breadth:75.5,dayRet:.59}};
(async()=>{
 await app.refresh(snapshot);
 assert.equal(element('commandScore').textContent,'—','No valid night data must never inherit stale primary 70');
 app.applyFutures(futures);
 assert.equal(element('commandScore').textContent,'55','PUBLISHED PAGE MUST RENDER 55/100 at 09:28');
 assert.match(element('commandGuideTitle').textContent,/暫緩新倉.*55/,'The main page must show a visible action for 55');
 assert.match(element('commandGuideText').textContent,/風險警示/);
 assert.equal(element('commandTradeGuide').dataset.tone,'stop');
 assert.equal(element('commandGuideCompare').children.length,2,'Show prior 70 and today 55 side by side');
 assert.equal(element('commandGuideCompare').children[0].children[1].textContent,'70/100');
 assert.equal(element('commandGuideCompare').children[1].children[1].textContent,'55/100');
 assert.match(element('commandScoreDescription').textContent,/昨收＋夜盤/);
 assert.match(element('commandCashReference').textContent,/70\/100/);
 assert.match(element('commandCashReference').textContent,/-15 分/);
 assert.match(element('commandCashReference').textContent,/55\/100/);
 assert.equal(element('commandScoreFill').style.width,'55%');
 assert.equal(element('marketCommand').dataset.level,'STOP');
 assert.match(element('commandStatus').textContent,/昨夜台指期/);
 assert.equal(element('commandBreadth').textContent,'—','Previous 75.5 percent cannot masquerade as today');
 app.applyIntraday({asOfDate:'2026-10-15',publishedAt:'2026-10-15T09:15:00+08:00',quality:'intraday-provisional-allmarket',
  coverage:{valid:1600,total:1982,exchange:{上市:{valid:900,total:1089},上櫃:{valid:700,total:893}}},
  marketBreadth:{quality:'verified-trade-only',total:{sample:134,up:31,down:90,flat:13},exchange:{上市:{sample:82},上櫃:{sample:52}}}});
 assert.equal(element('commandScore').textContent,'55','Sparse provisional breadth must not erase fixed 55 baseline');
 assert.equal(element('commandBreadth').textContent,'—','Sparse 134 samples cannot be shown as all-market confirmed');
 app.applyFutures({...futures,night:{...futures.night,reportQueryDate:'2026-10-14'}});
 assert.equal(element('commandScore').textContent,'—','Wrong-night date must fail closed');
 app.applyFutures(futures);
 assert.equal(element('commandScore').textContent,'55','Restoring dated futures restores baseline');
 await app.refresh({dataDate:'2026-10-15',risk:{date:'2026-10-15',score:44,breadth:30}});
 assert.equal(element('commandScore').textContent,'44','Verified same-day official close replaces TX baseline');
 assert.match(element('commandGuideTitle').textContent,/暫緩新倉/,'Risk score 44 with a STOP signal means risk-off');
 assert.equal(element('commandGuideCompare').hidden,true,'Historic/premarket comparison hidden for confirmed official close');
 for(const [score,band] of [[0,'0～24'],[24,'0～24'],[25,'25～44'],[44,'25～44'],[45,'45～59'],[49,'45～59'],[50,'45～59'],[55,'45～59'],[59,'45～59'],[60,'60～74'],[70,'60～74'],[74,'60～74'],[75,'75～100'],[80,'75～100'],[100,'75～100']])
  assert.equal(app.scoreBand(score).band,band,'Risk band threshold '+score);
 assert.match(app.scoreGuidance(70,{level:'READY'}).title,/小部位/,'Yesterday 70 is conditional, not all-in');
 assert.match(app.scoreGuidance(55,{reference:true,level:'STOP'}).title,/暫緩新倉/);
 assert.match(app.scoreGuidance(49,{level:'STOP'}).title,/暫緩新倉/);
 assert.match(app.scoreGuidance(50,{level:'WAIT'}).title,/觀望/);
 assert.match(app.scoreGuidance(85,{reference:true,level:'WAIT'}).text,/未經獨立回測/,'Unvalidated TX baseline must never authorize high-score auto buys');
 assert.match(html,/<script src="\.\/market-command\.js\?v=[^"]+"><\/script>/,'Versioned script prevents stale cache');
 for(const label of ['75～100｜強勢偏多','60～74｜偏多觀察','45～59｜中性觀望','25～44｜風險偏高','0～24｜極高風險'])
  assert(html.includes(label),'Visible homepage score bands: '+label);
 assert(html.includes('id="commandGuideTitle"')&&html.includes('id="commandGuideCompare"'),'Homepage must include an always-visible score guidance action');
 assert(html.includes('url.searchParams.set("appRefresh",String(Date.now()))'),'Reload must refresh script, not only JSON');
 console.log('PASS REAL rendered hero 10/15 09:28:55/100, yesterday70 history, no stale 75.5%, recovery after mismatches, live 134-sample protection');
})().catch(e=>{console.error(e);process.exitCode=1});
