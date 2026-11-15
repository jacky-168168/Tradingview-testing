'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const astro=require('../astro-core.cjs');

test('angle wrap and zero boundary retain signed local motion',()=>{
  assert.equal(astro.wrap(361),1);
  assert.equal(astro.wrap(-1),359);
  assert.equal(astro.signed(2-359),3);
  assert.equal(astro.signed(359-2),-3);
});
test('ten geocentric bodies produce finite, normalized, reproducible ECT coordinates',()=>{
  const stamp='2024-03-20T03:06:00.000Z';
  const out=astro.snapshot(stamp);
  assert.equal(out.positions.length,10);
  assert.equal(out.generatedAt,stamp);
  assert.equal(out.verifiedReturnSignal,false);
  for(const item of out.positions){
    assert.ok(item.longitudeDeg>=0&&item.longitudeDeg<360,item.name);
    assert.ok(Number.isFinite(item.latitudeDeg),item.name);
    assert.ok(Number.isFinite(item.speedDegPerDay),item.name);
  }
  // Sun near 0° Aries at March equinox; rejects accidental HELIOCENTRIC use.
  const sun=out.positions.find(x=>x.name==='Sun');
  assert.ok(sun.longitudeDeg<1||sun.longitudeDeg>359);
});
test('Mars–Jupiter 2024 exact conjunction is root-found, not a daily estimate',()=>{
  const found=astro.findExact('Mars','Jupiter',0,'2024-08-01T00:00:00.000Z',
    '2024-08-31T00:00:00.000Z',{stepHours:6,orbDeg:2});
  assert.ok(found.length>=1,'expected mid-August 2024 conjunction');
  for(const event of found){
    assert.ok(event.actualAngleDeg<0.002,'root precision should be <0.002°');
    assert.ok(new Date(event.windowStartUtc)<new Date(event.exactUtc));
    assert.ok(new Date(event.windowEndUtc)>new Date(event.exactUtc));
  }
});
test('date, range, and body errors do not silently create future data',()=>{
  assert.throws(()=>astro.snapshot('not-a-timestamp'));
  assert.throws(()=>astro.pos('X','2024-01-01T00:00:00Z'));
  assert.throws(()=>astro.findExact('Mars','Jupiter',0,'2026-02-01','2026-01-01'));
});
