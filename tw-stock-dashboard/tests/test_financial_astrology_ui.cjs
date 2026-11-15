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
assert.match(page,/financial-astrology-explain\\.js/);
assert.match(page,/id="astroReadingOverview"/);
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
assert.equal(interpret.describe(null).status,'unavailable');
assert.match(page,/沒有經驗證的因果預測力/);
assert.match(js,/textContent/);
assert.doesNotMatch(js,/eval\(|localStorage|fetch\(\s*['"]https:\/\/|fetch\(\s*['"]http:\/\//);
console.log('Financial astrology UI separation and legacy anchors OK');
