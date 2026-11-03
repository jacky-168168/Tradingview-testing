const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const root=path.resolve(__dirname,'../docs');
const js=fs.readFileSync(path.join(root,'retail-survival.js'),'utf8');
const html=fs.readFileSync(path.join(root,'index.html'),'utf8');
const first=js.indexOf('function financingAmount(');
const last=js.indexOf('function updateStats(){',first);
assert(first>=0&&last>first,'margin safeguards must be present');
const funcs=new Function('ok','n',js.slice(first,last)+'return {financingAmount,suspiciousMargin,validRatios};')(
 v=>typeof v==='number'&&Number.isFinite(v),Number
);
const {financingAmount,suspiciousMargin,validRatios}=funcs;
const prev={date:'2026-11-02',indexClose:44920.14,listed:171.7,otc:167.23,overall:170.6,
 listedLoanTwd:622699365000,otcLoanTwd:204411530000,
 listedCollateralTwd:1069196079360,otcCollateralTwd:341828960260};
const curr={date:'2026-11-03',indexClose:43307.54,listed:178.27,otc:156.76,overall:172.96,
 listedLoanTwd:599774466000,otcLoanTwd:196562898000,
 listedCollateralTwd:1069196079360,otcCollateralTwd:308131456420};
test('market financing decreases by 307.74 億 despite rising but unverified maintenance ratio',()=>{
 const change=(financingAmount(curr,'overall')-financingAmount(prev,'overall'))/1e8;
 assert.equal(Math.round(change*100)/100,-307.74);
 assert.equal(Math.round((financingAmount(curr,'listed')-financingAmount(prev,'listed'))/1e6)/100,-229.25);
 assert.equal(Math.round((financingAmount(curr,'otc')-financingAmount(prev,'otc'))/1e6)/100,-78.49);
});
test('split market choices do not mix missing or partial balances',()=>{
 assert.equal(financingAmount(curr,'listed'),curr.listedLoanTwd);
 assert.equal(financingAmount(curr,'otc'),curr.otcLoanTwd);
 assert.equal(financingAmount({...curr,otcLoanTwd:null},'overall'),null);
});
test('suspicious yesterday collateral is not treated as verified today maintenance',()=>{
 assert.equal(suspiciousMargin(curr,prev,'listed'),true);
 assert.equal(suspiciousMargin(curr,prev,'overall'),true);
 assert.equal(suspiciousMargin(curr,prev,'otc'),false);
 assert.deepEqual(validRatios([prev,curr],'overall').map(r=>r.date),['2026-11-02']);
});
test('legitimate day with changed collateral is not suppressed',()=>{
 const fixed={...curr,listedCollateralTwd:973000000000,overall:160.44};
 assert.equal(suspiciousMargin(fixed,prev,'overall'),false);
 assert.deepEqual(validRatios([prev,fixed],'overall').map(r=>r.date),['2026-11-02','2026-11-03']);
});
test('homepage explicitly separates financing balance from maintenance-rate points',()=>{
 for(const id of ['retailLoan','retailLoanChange','retailLoanDate','retailCurrent','retailChange']){
  assert.match(html,new RegExp('id="'+id+'"'));
 }
 assert.match(html,/融資金額較前交易日/);
 assert.match(html,/維持率較前交易日/);
 assert.match(js,/融資金額增減與維持率變化是兩個不同指標/);
 assert.match(js,/疑似混用前一交易日/);
});
