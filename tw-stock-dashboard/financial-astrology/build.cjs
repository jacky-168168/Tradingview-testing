'use strict';
const fs=require('node:fs');
const path=require('node:path');
const astro=require('./astro-core.cjs');
const argv=process.argv.slice(2);
const opt=(key,def)=>argv.find(x=>x.startsWith(key+'='))?.slice(key.length+1)??def;
const now=astro.utc(opt('--now',new Date().toISOString()));
const root=path.resolve(opt('--output',path.join(__dirname,'../docs/data/financial_astrology')));
const write=(name,data)=>{
  fs.mkdirSync(root,{recursive:true});
  fs.writeFileSync(path.join(root,name),JSON.stringify(data,null,2)+'\n','utf8');
};
const events=astro.findExact('Mars','Jupiter',0,'1990-01-01T00:00:00.000Z',
  new Date(now.getTime()+100*86400000),{orbDeg:2,stepHours:6});
const futurePairs=[['Sun','Moon'],['Sun','Mercury'],['Sun','Mars'],['Mercury','Venus'],
  ['Venus','Mars'],['Mars','Jupiter'],['Jupiter','Saturn'],['Saturn','Uranus']];
const forwardStart=new Date(now.getTime()-2*86400000);
const forwardEnd=new Date(now.getTime()+90*86400000);
const calendar=[];
for(const [a,b] of futurePairs) for(const [,angle] of astro.ASPECTS){
  calendar.push(...astro.findExact(a,b,angle,forwardStart,forwardEnd,{windows:false,stepHours:6,orbDeg:2}));
}
calendar.sort((a,b)=>a.exactUtc.localeCompare(b.exactUtc));
const live=astro.snapshot(now);
const prev=new Date(now.getTime()-90*86400000);
for(const p of live.positions){
  const past=calendar.filter(x=>(x.bodyA===p.name||x.bodyB===p.name)&&new Date(x.exactUtc)<=now);
  const next=calendar.find(x=>(x.bodyA===p.name||x.bodyB===p.name)&&new Date(x.exactUtc)>now);
  p.previousEventUtc=past.length?past.at(-1).exactUtc:null;
  p.nextEventUtc=next?next.exactUtc:null;
}
write('latest.json',live);
write('calendar.json',{schemaVersion:1,generatedAt:now.toISOString(),
  note:'天文事件，非已驗證交易訊號',orbDeg:2,events:calendar});
write('mars_jupiter_conjunction.json',{schemaVersion:1,generatedAt:now.toISOString(),
  bodyA:'Mars',bodyB:'Jupiter',aspect:'conjunction',angleDeg:0,orbDeg:2,
  source:'Astronomy Engine 2.1.19, geocentric tropical ECT',events});
process.stdout.write(JSON.stringify({generatedAt:now.toISOString(),events:events.length,
  calendar:calendar.length,root})+'\n');
