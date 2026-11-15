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
assert.match(conclusion.reason,/火星代表行動/);
assert.match(conclusion.market,/單靠星盤無法可靠判斷股票漲跌/);
assert.match(conclusion.watch,/成交量/);
const emptyConclusion=interpret.plainLanguageConclusion({positions:[
 {name:'Sun',sign:'牡羊',motion:'direct',signDegree:3}
],aspects:[]});
assert.match(emptyConclusion.headline,/沒有特別接近的主要行星角度/);
assert.equal(interpret.plainLanguageConclusion(null).status,'unavailable');
assert.equal(interpret.describe(null).status,'unavailable');
assert.match(page,/沒有經驗證的因果預測力/);
assert.match(js,/textContent/);
assert.doesNotMatch(js,/eval\(|localStorage|fetch\(\s*['"]https:\/\/|fetch\(\s*['"]http:\/\//);
console.log('Financial astrology UI separation and legacy anchors OK');

assert.doesNotMatch(page,/id="astroReadingRecapHeadline"/);
assert.doesNotMatch(page,/id="astroReadingRecapMarket"/);
assert.match(page,/id="astroConclusionHeadline"/);
assert(page.includes('financial-astrology-explain.js?v=1.3'));
assert.match(explain,/astroConclusionHeadline/);
assert.match(page,/astro-research-body/);
const reading=interpret.plainLanguageConclusion({
 positions:[
  {name:'Sun',sign:'天蠍',longitudeDeg:228,signDegree:18,motion:'direct'},
  {name:'Moon',sign:'摩羯',longitudeDeg:278,signDegree:8,motion:'direct'},
  {name:'Mars',sign:'獅子',longitudeDeg:130,signDegree:10,motion:'direct'},
  {name:'Jupiter',sign:'獅子',longitudeDeg:130.4,signDegree:10.4,motion:'direct'}],
 aspects:[{bodyA:'Mars',bodyB:'Jupiter',aspect:'conjunction',actualAngleDeg:.4,orbErrorDeg:.4,applying:true}]
});
assert.match(reading.headline,/行動與擴張/);
assert.match(reading.market,/單靠星盤無法可靠判斷股票漲跌/);

const firstScreen=page.slice(0,page.indexOf('id="astroWheel"'));
assert(firstScreen.includes('id="astroConclusionHeadline"'),'final conclusion appears before wheel');
assert(firstScreen.includes('台灣時間 UTC+8'),'date field is plain Taiwan time');
assert(page.indexOf('id="astroQueryTime"')<page.indexOf('id="astroConclusionHeadline"'));
assert(page.indexOf('id="astroConclusionHeadline"')<page.indexOf('id="astroWheel"'));
assert.doesNotMatch(page,/id="astroReadingHighlights"/);
assert.match(page,/<details class="astro-guide astro-advanced"/);
assert.match(page,/<details class="panel astro-research"/);
assert.match(page,/<summary>研究方法、資料來源與限制<\/summary>/);
assert.match(page,/<summary>進階資料：行星角度與移動速度<\/summary>/);
assert.match(js,/new Date\(input\+':00\+08:00'\)/);
assert.match(js,/showEvidence\(r.sampleSize<30/);
const voids=new Set(['meta','link','input','img','br','hr','source','area','base','embed','wbr']);
const stack=[];const errors=[];
for(const m of page.matchAll(/<(\/?)(([a-zA-Z][\w-]*))(?:\s[^>]*?)?>/g)){
  const name=m[2].toLowerCase();
  if(voids.has(name))continue;
  if(m[1]){
    if(stack.pop()!==name)errors.push('unexpected closing '+name);
  }else stack.push(name);
}
assert.deepStrictEqual(errors,[],'HTML tags must be properly nested');
assert.deepStrictEqual(stack,[],'HTML should have no unclosed tags');
