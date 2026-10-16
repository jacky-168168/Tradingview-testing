const test=require('node:test'),assert=require('node:assert/strict');
let mod;
async function worker(){mod??=await import('../infra/g-intraday-cron/worker.mjs');return mod}
function mockAPI(data,runs=[]){
 let dispatched=0;
 const prev=global.fetch;
 global.fetch=async(url,opts)=>{
  if(url.includes('/contents/')){
   const content=Buffer.from(JSON.stringify(data)).toString('base64');
   return {ok:true,status:200,json:async()=>({content})};
  }
  if(url.includes('/runs?'))return {ok:true,status:200,json:async()=>({workflow_runs:runs})};
  if(url.includes('/dispatches')){dispatched++;return {ok:true,status:204}};
  throw Error('Unexpected URL '+url);
 };
 return {count:()=>dispatched,restore:()=>{global.fetch=prev}};
}
test('timezone and stock-exchange session guard',async()=>{
 const {localSlot}=await worker();
 assert.equal(localSlot(new Date('2026-10-16T01:04:00Z')).hhmm,'09:00');
 assert.equal(localSlot(new Date('2026-10-16T05:34:00Z')).hhmm,'13:30');
 assert.equal(localSlot(new Date('2026-10-16T06:04:00Z')),null);
 assert.equal(localSlot(new Date('2026-10-17T01:04:00Z')),null);
 assert.equal(localSlot(new Date('2026-10-26T01:04:00Z')),null);
});
test('fresh scan causes no duplicate workflow dispatch',async()=>{
 const {runBackup}=await worker(),now=new Date('2026-10-16T01:19:00Z');
 const m=mockAPI({asOfDate:'2026-10-16',publishedAt:'2026-10-16T09:05:00+08:00',quality:'intraday-provisional-allmarket',rows:[{code:'3535'}]});
 try{const res=await runBackup(now,{GH_ACTIONS_TOKEN:'test'},now);assert.equal(res.action,'skip');assert.equal(m.count(),0)}
 finally{m.restore()}
});
test('missing scan dispatches exactly one recovery',async()=>{
 const {runBackup}=await worker(),now=new Date('2026-10-16T01:19:00Z');
 const m=mockAPI({asOfDate:'2026-10-15',publishedAt:'2026-10-15T13:19:00+08:00',quality:'intraday-provisional-allmarket',rows:[{code:'3535'}]});
 try{const res=await runBackup(now,{GH_ACTIONS_TOKEN:'test'},now);assert.equal(res.action,'dispatched');assert.equal(m.count(),1)}
 finally{m.restore()}
});
test('running GitHub task prevents redundant recovery',async()=>{
 const {runBackup}=await worker(),now=new Date('2026-10-16T01:19:00Z');
 const runs=[{name:'TW Stock Dashboard',created_at:'2026-10-16T01:05:00Z',status:'in_progress'}];
 const m=mockAPI({asOfDate:'2026-10-15',quality:'intraday-provisional-allmarket',rows:[]},runs);
 try{const res=await runBackup(now,{GH_ACTIONS_TOKEN:'test'},now);assert.equal(res.action,'skip');assert.equal(m.count(),0)}
 finally{m.restore()}
});
test('late trigger and missing secret fail closed',async()=>{
 const {runBackup}=await worker(),now=new Date('2026-10-16T01:19:00Z');
 assert.equal((await runBackup(now,{},new Date('2026-10-16T01:03:00Z'))).action,'skip');
 await assert.rejects(()=>runBackup(now,{},now),/Missing GH_ACTIONS_TOKEN/);
});
