'use strict';
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=__dirname+'/../docs/';
const html=fs.readFileSync(root+'index.html','utf8');
const page=fs.readFileSync(root+'financial-astrology.html','utf8');
const js=fs.readFileSync(root+'financial-astrology.js','utf8');
const explain=fs.readFileSync(root+'financial-astrology-explain.js','utf8');
const interpret=require(root+'financial-astrology-explain.js');
assert.match(html,/id="financialAstrologyHome"/);
assert.match(html,/href="\.\/financial-astrology\.html"/);
assert.match(html,/financial-astrology-home\.js/);
assert.match(html,/id="marketCommand"/);
assert.match(html,/id="sentimentPanel"/);
assert.match(html,/id="twVixPanel"/);
assert.match(page,/site-access\.js/);
assert.match(page,/id="astroMarket"/);
assert.match(page,/id="astroHorizon"/);
assert.match(page,/id="astroTimezone"/);
assert.match(page,/id="astroQueryTime"/);
assert.match(page,/id="astroWheel"/);
assert.match(page,/financial-astrology-vendor\.js/);
assert.match(js,/snapshotClient/);
assert.match(js,/drawWheel/);
assert.match(page,/financial-astrology-explain\.js/);
assert.match(page,/id="astroReadingOverview"/);
assert.match(page,/id="astroConclusionHeadline"/);
assert.match(page,/id="astroConclusionMarket"/);
assert.match(page,/id="astroConclusionEvidence"/);
assert.ok(page.indexOf('id="astroConclusion"')<page.indexOf('id="astroWheel"'),'plain-language conclusion must be above the chart');
assert.match(page,/id="astroReadingPlanets"/);
assert.match(page,/id="astroReadingAspects"/);
assert.match(page,/id="astroReadingCategories"/);
assert.match(page,/《占星其實很簡單/);
assert.match(explain,/十星|十大|行星|Moon/);
assert.equal(Object.keys(interpret.PLANETS).length,10);
assert.equal(Object.keys(interpret.SIGNS).length,12);
assert.equal(Object.keys(interpret.ASPECTS).length,5);
const example=interpret.describe({
  positions:[
    {name:'Mars',sign:'獅子',longitudeDeg:127,signDegree:7,motion:'direct',speedDegPerDay:0.5},
    {name:'Jupiter',sign:'獅子',longitudeDeg:128,signDegree:8,motion:'direct',speedDegPerDay:0.2},
    {name:'Sun',sign:'天蠍',longitudeDeg:230,signDegree:20,motion:'direct',speedDegPerDay:1},
    {name:'Moon',sign:'摩羯',longitudeDeg:280,signDegree:10,motion:'direct',speedDegPerDay:13}
  ],
  aspects:[{bodyA:'Mars',bodyB:'Jupiter',aspect:'conjunction',actualAngleDeg:1,orbErrorDeg:1,applying:true}],
  moon:{phaseLabel:'盈月'}
});
assert.equal(example.status,'ok');
assert.equal(example.planets.length,4);
assert.equal(example.aspects[0].kind,'合相');
assert.match(example.aspects[0].interpretation,/行動|競爭/);
assert.match(example.summary,/太陽位於天蠍座/);
assert.match(example.categories,/四元素分布/);
assert.match(example.bookScope,/不計上升|不計.*十二宮/);
assert.doesNotMatch(example.summary,/明天必漲|明天必跌/);
const conclusion=interpret.plainLanguageConclusion({
  positions:[
    {name:'Mars',sign:'獅子',longitudeDeg:127,signDegree:7,motion:'direct',speedDegPerDay:0.5},
    {name:'Jupiter',sign:'獅子',longitudeDeg:128,signDegree:8,motion:'direct',speedDegPerDay:0.2},
    {name:'Sun',sign:'天蠍',longitudeDeg:230,signDegree:20,motion:'direct',speedDegPerDay:1},
    {name:'Moon',sign:'摩羯',longitudeDeg:280,signDegree:10,motion:'direct',speedDegPerDay:13}
  ],
  aspects:[{bodyA:'Mars',bodyB:'Jupiter',aspect:'conjunction',actualAngleDeg:1,orbErrorDeg:1,applying:true}]
});
assert.match(conclusion.headline,/行動與擴張/);
assert.match(conclusion.reason,/火星與木星合相/);
assert.match(conclusion.market,/無法根據星盤判斷偏多或偏空/);
assert.match(conclusion.watch,/ATR/);
const emptyConclusion=interpret.plainLanguageConclusion({positions:[
 {name:'Sun',sign:'牡羊',motion:'direct',signDegree:3}
],aspects:[]});
assert.match(emptyConclusion.headline,/沒有特別接近的五大行星相位/);
assert.equal(interpret.plainLanguageConclusion(null).status,'unavailable');
assert.equal(interpret.describe(null).status,'unavailable');
assert.match(page,/沒有經驗證的因果預測力/);
assert.match(js,/textContent/);
assert.doesNotMatch(js,/eval\(|localStorage|fetch\(\s*['"]https:\/\/|fetch\(\s*['"]http:\/\//);
console.log('Financial astrology UI separation and legacy anchors OK');

assert.match(page,/id="astroReadingRecapHeadline"/);
assert.match(page,/id="astroReadingRecapMarket"/);
assert.match(page,/id="astroConclusionHeadline"/);
assert(page.includes('financial-astrology-explain.js?v=1.2'));
assert.match(explain,/astroReadingRecapHeadline/);
assert.match(explain,/astroReadingRecapMarket/);
const reading=interpret.plainLanguageConclusion({
 positions:[
  {name:'Sun',sign:'天蠍',longitudeDeg:228,signDegree:18,motion:'direct'},
  {name:'Moon',sign:'摩羯',longitudeDeg:278,signDegree:8,motion:'direct'},
  {name:'Mars',sign:'獅子',longitudeDeg:130,signDegree:10,motion:'direct'},
  {name:'Jupiter',sign:'獅子',longitudeDeg:130.4,signDegree:10.4,motion:'direct'}],
 aspects:[{bodyA:'Mars',bodyB:'Jupiter',aspect:'conjunction',actualAngleDeg:.4,orbErrorDeg:.4,applying:true}]
});
assert.match(reading.headline,/行動與擴張/);
assert.match(reading.market,/無法根據星盤判斷偏多或偏空/);

const vm=require('node:vm');
const homepageScript=fs.readFileSync(root+'financial-astrology-home.js','utf8');
assert(html.includes('financial-astrology-vendor.js?v=2.1.19'),'homepage must load astronomy engine before live summary');
assert(html.includes('financial-astrology-home.js?v=2'),'homepage live script must bust stale cache');
assert.doesNotMatch(homepageScript,/latest\\.json/,'homepage must not rely on a possibly stale JSON snapshot');
assert.match(homepageScript,/setInterval\\(refresh,60000\\)/,'homepage must refresh each minute');
assert.match(js,/liveMode:true/,'detailed page defaults to current sky');
assert.match(js,/setInterval\\(\\(\\)=>\\{if\\(state\\.liveMode\\)refreshLiveChart\\(\\);\\},60000\\)/);
assert.match(js,/visibilitychange/,'returning to page must refresh live chart');
assert.match(js,/state\\.liveMode=false/,'historical date selection must pause automatic refresh');
assert.match(js,/new Date\\(input\\+':00\\+08:00'\\)/,'input is Taiwan UTC+8');
assert.doesNotMatch(js,/load\\('latest\\.json'\\)/,'do not overwrite live charts using old snapshots');
assert.match(page,/即時地心星盤（顯示當前日期）/);
assert.match(page,/financial-astrology\\.js\\?v=1\\.4/);

// Fixed clock regression: the home preview crosses Taiwan midnight while user is on the page.
let clock=Date.parse('2026-11-15T15:59:00.000Z');
class FixedDate extends Date{
  constructor(...args){super(...(args.length?args:[clock]));}
  static now(){return clock;}
}
const ui={state:{textContent:''},event:{textContent:''},evidence:{textContent:''}};
let tick=null;
const rootElement={querySelector(key){
  if(key==='[data-astro-state]')return ui.state;
  if(key==='[data-astro-event]')return ui.event;
  if(key==='[data-astro-evidence]')return ui.evidence;
  throw new Error('Unknown selector '+key);
}};
const sandbox={
  document:{getElementById(id){return id==='financialAstrologyHome'?rootElement:null;},addEventListener(){}},
  window:{Astronomy:{
    Body:{Mars:'Mars',Jupiter:'Jupiter'},
    GeoVector(body){return {body};},
    Ecliptic(vector){return {elon:vector.body==='Mars'?120:121};}
  },addEventListener(){}},
  Date:FixedDate,Intl,Math,Number,Error,
  fetch:async()=>({ok:false}),
  setInterval(fn,ms){assert.equal(ms,60000);tick=fn;return 1;}
};
vm.runInNewContext(homepageScript,sandbox);
assert.match(ui.state.textContent,/2026\\/11\\/15|2026\\/11\\/16/);
assert.match(ui.state.textContent,/23:59/,'UTC 15:59 must be Taiwan 23:59');
clock=Date.parse('2026-11-15T16:01:00.000Z');
assert.equal(typeof tick,'function');
tick();
assert.match(ui.state.textContent,/2026\\/11\\/16/,'live chart must advance to new Taiwan date');
assert.match(ui.state.textContent,/00:01/,'live chart must advance with time, not stale data');
assert.match(ui.event.textContent,/接近合相/);
