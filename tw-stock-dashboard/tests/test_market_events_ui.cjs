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
const sample=JSON.parse(fs.readFileSync(path.join(root,'data/market_events/latest.json'),'utf8'));
assert.equal(sample.schema,1);
const tpca=sample.items.find(x=>x.id==='event-tpca-show-2026');
assert(tpca&&tpca.confirmed&&tpca.date==='2026-10-20'&&tpca.endDate==='2026-10-22');
assert(!sample.items.some(x=>x.type==='news'&&x.confirmed),'unverified news cannot be confirmed');
const nodes=new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',hidden:false,value:'',fn:null,
  addEventListener(type,fn){this.fn=fn},
  querySelectorAll(){return []}
});return nodes.get(id)}
const document={getElementById:node};
const ctx={document,fetch:async()=>({ok:true,json:async()=>sample}),setInterval:()=>{},Date,Intl,console};
vm.runInNewContext(script,ctx);
setImmediate(()=>{
 assert(node('events').innerHTML.includes('TPCA Show 2026'),'confirmed TPCA must render');
 assert(!node('news').innerHTML.includes('TPCA Show'),'events cannot be faked as news');
 if(sample.status==='initializing')assert(node('alert').textContent.includes('同步尚未完成'),'initializing must be shown');
else if(sample.status==='ok')assert(node('news').innerHTML.length>0,'live news must render');
else assert(!node('alert').hidden,'partial/degraded source must show warning');
 assert(!node('events').innerHTML.includes('<script>'),'event output must be escaped');
 console.log('PASS verified event, isolated media claims, search UI, stock dashboard navigation');
});
