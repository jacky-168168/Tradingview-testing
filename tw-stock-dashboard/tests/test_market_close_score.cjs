'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const dir=path.join(__dirname,'..','docs');
const market=require(path.join(dir,'market-command.js'));
const html=fs.readFileSync(path.join(dir,'index.html'),'utf8');
const today=new Date('2026-11-02T19:00:00+08:00');
const valid={quality:'official-twse-close-risk-v1',asOfDate:'2026-11-02',
 publishedAt:'2026-11-02T19:00:00+08:00',
 risk:{date:'2026-11-02',score:12,index:44920.14},
 source:{officialIndexClose:44920.14}};
assert.deepEqual(market.validatedOfficialClose(valid,today),valid,'official risk snapshot must be displayed if same-day');
assert.equal(market.validatedOfficialClose({...valid,quality:'unverified'},today),null);
assert.equal(market.validatedOfficialClose({...valid,asOfDate:'2026-11-01'},today),null);
assert.equal(market.validatedOfficialClose({...valid,risk:{...valid.risk,score:101}},today),null);
assert.equal(market.validatedOfficialClose({...valid,risk:{...valid.risk,score:null}},today),null);
assert.equal(market.validatedOfficialClose({...valid,source:{officialIndexClose:49000}},today),null);
assert.equal(market.validatedOfficialClose({...valid,publishedAt:'2026-11-03T19:00:00+08:00'},today),null);
assert.ok(html.includes('async function loadOfficialCloseRisk()'),'homepage needs standalone Risk Score fetch');
assert.ok(html.includes('await loadOfficialCloseRisk()'),'homepage must load it even if other data is stale');
assert.ok(html.includes('MarketCommand.applyOfficialClose(snap)'));
console.log('PASS official close Risk Score fallback source/date checks and homepage wiring');
