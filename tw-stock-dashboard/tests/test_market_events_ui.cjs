const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),vm=require('node:vm');
const root=path.join(__dirname,'../docs');
const html=fs.readFileSync(path.join(root,'market-events.html'),'utf8');
const main=fs.readFileSync(path.join(root,'index.html'),'utf8');
const rankings=fs.readFileSync(path.join(root,'selections.html'),'utf8');
const script=fs.readFileSync(path.join(root,'market-events.js'),'utf8');
new Function(script);
assert(main.includes('href="./market-events.html"'),'homepage must expose major-events entry');
assert(rankings.includes('href="./market-events.html"'),'G rankings must expose major-events entry');
for(const id of ['events','news','eventCount','newsCount','alert','freshness','filters','query','eventSection','newsSection','empty'])
 assert(html.includes('id="'+id+'"'),'missing '+id);
const archived=JSON.parse(fs.readFileSync(path.join(root,'data/market_events/latest.json'),'utf8'));
assert.equal(archived.schema,1);
assert(archived.items.some(x=>x.id==='event-tpca-show-2026'&&x.confirmed&&x.endDate==='2026-10-22'));
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
const sample={...archived,generatedAt:'2026-10-21T00:00:00+08:00',items:[...archived.items,...fresh]};
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
 console.log('PASS ended events filtered, only fresh news rendered, pagination and stale dataset warning');
});
