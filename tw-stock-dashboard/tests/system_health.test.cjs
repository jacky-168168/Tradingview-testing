const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.join(__dirname,'../docs');
const html=fs.readFileSync(path.join(root,'system-health.html'),'utf8');
const home=fs.readFileSync(path.join(root,'index.html'),'utf8');
const script=fs.readFileSync(path.join(root,'system-health.js'),'utf8');
test('independent health page navigation and JavaScript are present',()=>{
 assert.match(home,/href="\.\/system-health\.html"/);
 assert.match(html,/src="\.\/system-health\.js"/);
 new Function(script);
 for(const id of ['gState','newsState','actionsState','pagesState','summary','refresh'])
  assert.ok(html.includes('id="'+id+'"'),id);
});
function fakeNow(iso){
 return class FrozenDate extends Date{
  constructor(...a){super(...(a.length?a:[iso]))}
  static now(){return Date.parse(iso)}
 };
}
async function runScenario(nowIso,expected){
 const DateClass=fakeNow(nowIso),now=new DateClass();
 const toIso=age=>new Date(now.getTime()-age*60000).toISOString();
 const data={
  g:{asOfDate:"2026-10-21",publishedAt:toIso(20),quality:"intraday-provisional-allmarket",
      rows:[{code:"2330"}],coverage:{valid:1700,total:1983,
       exchange:{"上市":{valid:980,total:1090},"上櫃":{valid:720,total:893}}}},
  status:{asOfDate:"2026-10-21",status:"ok"},
  news:{status:"ok",generatedAt:toIso(20),feedsOk:12,feedsTotal:12,newestNewsAt:toIso(30)},
  actions:{workflow_runs:[{name:"TW Stock Dashboard",created_at:toIso(20),conclusion:"success",status:"completed"}]}
 };
 const nodes=new Map();
 const doc={getElementById(id){
  if(!nodes.has(id))nodes.set(id,{textContent:"",className:"",disabled:false,addEventListener(){}});
  return nodes.get(id);
 }};
 const fetch=async url=>{
  let payload;
  if(url.includes('raw.githubusercontent.com'))payload=data.g;
  else if(url.includes('actions/workflows'))payload=data.actions;
  else if(url.includes('g_intraday/latest.json'))payload=data.g;
  else if(url.includes('g_intraday/status.json'))payload=data.status;
  else if(url.includes('market_events/latest.json'))payload=data.news;
  else throw Error('Unexpected fetch path '+url);
  return {ok:true,json:async()=>payload};
 };
 const ctx={document:doc,Date:DateClass,Intl,fetch,console};
 vm.runInNewContext(script,ctx);
 await new Promise(resolve=>setImmediate(resolve));
 assert.match(nodes.get('gState').textContent,expected);
 assert.equal(nodes.get('refresh').disabled,false);
}
test('live healthy G accepted within session',async()=>{
 await runScenario("2026-10-21T02:30:00Z",/資料品質通過/);
});
test('weekend is not reported as stale G',async()=>{
 await runScenario("2026-10-24T03:30:00Z",/非盤中巡檢時段/);
});
