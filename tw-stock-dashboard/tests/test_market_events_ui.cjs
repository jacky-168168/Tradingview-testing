const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),vm=require('node:vm');
const root=path.join(__dirname,'../docs');
const html=fs.readFileSync(path.join(root,'market-events.html'),'utf8');
const main=fs.readFileSync(path.join(root,'index.html'),'utf8');
const rankings=fs.readFileSync(path.join(root,'selections.html'),'utf8');
const script=fs.readFileSync(path.join(root,'market-events.js'),'utf8');
new Function(script);
assert(main.includes('href="./market-events.html"'),'homepage must expose major-events entry');
assert(rankings.includes('href="./market-events.html"'),'G rankings must expose major-events entry');
for(const category of ["energy","metals","agriculture","ptt"])
 assert(html.includes('data-cat="'+category+'"'),'market events missing '+category+' tab');
for(const id of ['events','news','eventCount','newsCount','alert','freshness','filters','query','eventSection','newsSection','empty'])
 assert(html.includes('id="'+id+'"'),'missing '+id);
const archived=JSON.parse(fs.readFileSync(path.join(root,'data/market_events/latest.json'),'utf8'));
assert.equal(archived.schema,1);
assert(Array.isArray(archived.items),'rolling official-news dataset must contain an items array');
// The official feed rotates events out as they expire. Use a fixed dated fixture
// for the ended-event regression, not a permanently pinned historical event.
const endedExhibition={id:'fixture-ended-exhibition',type:'event',category:'展覽',
 title:'TPCA Show 2026｜已結束測試',date:'2026-10-20',endDate:'2026-10-22',
 source:'測試官方展覽',url:'https://example.com/test-ended',confirmed:true,themes:['PCB']};
const upcomingRateMeeting={id:'fixture-fomc',type:'event',category:'總經',
 title:'FOMC 2026｜即將舉行測試',date:'2026-10-28',endDate:'2026-10-29',
 source:'測試聯準會',url:'https://example.com/test-fomc',confirmed:true,themes:['升降息']};
assert(!archived.items.some(x=>x.type==='news'&&x.confirmed),'unverified news cannot be confirmed');
// Run at a FIXED future date: an ended exhibition must not fail the entire
// scheduled news publishing workflow. Never assert that old events must render.
const FIXED_NOW='2026-10-24T06:00:00Z';
class FixedDate extends Date{
 constructor(...a){super(...(a.length?a:[FIXED_NOW]))}
 static now(){return Date.parse(FIXED_NOW)}
}
const fresh=Array.from({length:23},(_,i)=>({
 id:'test-fresh-'+i,type:'news',category:'AI需求',title:'測試近期半導體新聞 '+i,
 date:'2026-10-24',publishedAt:new Date(Date.parse(FIXED_NOW)-(i+1)*60000).toISOString(),
 source:'測試媒體',url:'https://example.com/test/'+i,themes:['AI'],confirmed:false
}));
const commodities=[
 {id:'fixture-oil',type:'news',category:'原油／能源',title:'WTI 原油最新產量上升',
  date:'2026-10-24',publishedAt:'2026-10-24T05:00:00Z',source:'測試能源新聞',
  url:'https://example.com/oil',themes:['WTI'],confirmed:false},
 {id:'fixture-silver',type:'news',category:'貴金屬',title:'白銀報價最新上升',
  date:'2026-10-24',publishedAt:'2026-10-24T05:00:00Z',source:'測試金屬新聞',
  url:'https://example.com/silver',themes:['白銀'],confirmed:false},
 {id:'fixture-ptt',type:'news',category:'PTT轉載',title:'[新聞] 台股明開盤恐補跌千點',
  date:'2026-10-24',publishedAt:'2026-10-24T05:00:00Z',source:'PTT 股票板（新聞轉載）',
  url:'https://www.ptt.cc/bbs/Stock/M.1792918324.A.BBD.html',themes:['PTT'],confirmed:false},
 {id:'fixture-crops',type:'news',category:'農產品',title:'黃豆 USDA 最新收成預估',
  date:'2026-10-24',publishedAt:'2026-10-24T05:00:00Z',source:'測試農產品新聞',
  url:'https://example.com/crops',themes:['黃豆'],confirmed:false}
];
const sample={...archived,generatedAt:'2026-10-21T00:00:00+08:00',
 items:[endedExhibition,upcomingRateMeeting,...archived.items.filter(x=>x.type!=='event'),...fresh,...commodities]};
const nodes=new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',hidden:false,value:'',fn:null,
 addEventListener(type,fn){this.fn=fn},querySelectorAll(){return []}
});return nodes.get(id)}
const document={getElementById:node};
const ctx={document,fetch:async()=>({ok:true,json:async()=>sample}),setInterval:()=>{},Date:FixedDate,Intl,console};
vm.runInNewContext(script,ctx);
setImmediate(()=>{
 assert(!node('events').innerHTML.includes('TPCA Show 2026'),'ended exhibit must not appear');
 assert(node('events').innerHTML.includes('FOMC'),'future official event must appear');
 assert(!node('news').innerHTML.includes('台股反彈全看這波'),'stale 10/21 headline cannot be latest on 10/24');
 assert.equal((node('news').innerHTML.match(/<article /g)||[]).length,20,'first page must show 20 genuinely fresh articles');
 assert.equal(node('moreNews').hidden,false,'load more must appear for 23 fresh articles');
 node('moreNews').fn();
 const freshTotal=sample.items.filter(x=>x.type==='news'&&Number.isFinite(Date.parse(x.publishedAt))&&
   Date.parse(FIXED_NOW)-Date.parse(x.publishedAt)>=-5*60000&&
   Date.parse(FIXED_NOW)-Date.parse(x.publishedAt)<=48*3600000).length;
 assert.equal((node('news').innerHTML.match(/<article /g)||[]).length,Math.min(40,freshTotal),
    'load more adds only fresh items, regardless of live fixture size');
 assert(node('alert').textContent.includes('新聞超過 36 小時未更新'),'stale dataset must show warning');
 assert(!node('events').innerHTML.includes('<script>'),'event output must be escaped');
 for(const [filter,expected,excluded] of [
  ['energy','WTI 原油','白銀報價'],['metals','白銀報價','黃豆 USDA'],
  ['agriculture','黃豆 USDA','WTI 原油'],['ptt','台股明開盤恐補跌','黃豆 USDA']]){
  node('filters').fn({target:{closest:()=>({dataset:{cat:filter}})}});
  assert(node('news').innerHTML.includes(expected),filter+' news filter should show own items');
  assert(!node('news').innerHTML.includes(excluded),filter+' filter should hide unrelated items');
  assert.equal(node('eventSection').hidden,true,'topic filters should not contain unrelated events');
 }
 console.log('PASS ended events filtered, only fresh news rendered, pagination and stale dataset warning');
});
