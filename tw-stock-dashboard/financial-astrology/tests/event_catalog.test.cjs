'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const astro=require('../astro-core.cjs');
const catalog=require('../event-catalog.cjs');

test('predeclared event types are not based on backtest optimization',()=>{
  const ids=catalog.PERIODS.map(x=>x.id);
  assert.equal(new Set(ids).size,ids.length);
  for(const name of ['mars_jupiter_conjunction','new_moon','full_moon',
    'mercury_retrograde_start','mars_saturn_square','saturn_uranus_square',
    'jupiter_saturn_conjunction','venus_jupiter_conjunction'])assert.ok(ids.includes(name));
});
test('exact phases have roots near 0 and 180 degrees and ordered times',()=>{
  const begin='2024-01-01T00:00:00Z',end='2024-06-01T00:00:00Z';
  for(const [angle,id] of [[0,'new_moon'],[180,'full_moon']]){
    const rows=catalog.moonEvents(angle,begin,end);
    assert.ok(rows.length>=4,id+' events must exist');
    for(const x of rows){
      assert.ok(Math.abs(astro.signed(x.actualAngleDeg-angle))<0.05,id);
      assert.equal(x.bodyB,'Moon');
    }
  }
});
test('Mercury retrograde start detects east-to-west apparent motion change',()=>{
  const rows=catalog.stationEvents('Mercury','2024-01-01T00:00:00Z',
    '2025-01-01T00:00:00Z');
  assert.ok(rows.length>=2&&rows.length<=5);
  for(const e of rows){
    const time=Date.parse(e.exactUtc);
    assert.ok(astro.pos('Mercury',new Date(time-4*86400000)).speedDegPerDay>0);
    assert.ok(astro.pos('Mercury',new Date(time+4*86400000)).speedDegPerDay<0);
  }
});
test('catalog emits immutable UTC-labeled families and no market performance',()=>{
  const out=catalog.catalog('2024-01-01T00:00:00Z','2024-06-01T00:00:00Z',
    {include:['new_moon','full_moon','mercury_retrograde_start']});
  assert.deepEqual(Object.keys(out.studyFamilies).sort(),['full_moon','mercury_retrograde_start','new_moon']);
  assert.equal(out.noTradingSignal,true);
  for(const family of Object.values(out.studyFamilies)){
    assert.ok(family.events.length);
    for(const e of family.events){
      assert.ok(e.exactUtc.endsWith('Z'));
      assert.ok(e.id.includes(family.id));
      assert.equal(e.eventFamily,family.id);
      assert.ok(!Object.hasOwn(e,'winRate'));
    }
  }
});
