'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {classifyLocalAssetError}=require('./local_asset_404_policy.cjs');
const root='/repo/docs',missing=()=>false,present=()=>true;
test('unpublished optional premarket snapshot may return 404',()=>{
  assert.equal(classifyLocalAssetError({url:'data/market_premarket/latest.json',code:404},root,missing),'optional-unpublished-premarket');
});
test('published premarket snapshot must be served successfully',()=>{
  assert.equal(classifyLocalAssetError({url:'data/market_premarket/latest.json',code:404},root,present),'unexpected');
});
test('premarket server errors are never ignored',()=>{
  assert.equal(classifyLocalAssetError({url:'data/market_premarket/latest.json',code:500},root,missing),'unexpected');
  assert.equal(classifyLocalAssetError({url:'data/market_premarket/latest.json',code:403},root,missing),'unexpected');
});
test('unrelated missing assets still fail the audit',()=>{
  for(const url of ['data/latest.json','data/market_risk_close/latest.json','data/market_premarket/other.json','index.html'])
    assert.equal(classifyLocalAssetError({url,code:404},root,missing),'unexpected');
});
test('URL lookalikes do not bypass missing-asset checks',()=>{
  for(const url of ['/data/market_premarket/latest.json','data/market_premarket/latest.json/extra','data/market_premarket/latest.json?x=1'])
    assert.equal(classifyLocalAssetError({url,code:404},root,missing),'unexpected');
});
