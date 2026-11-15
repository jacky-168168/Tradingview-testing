'use strict';
/* Financial Astrology Lab: astronomical calculations only, NOT market predictions.
 * Astronomy Engine v2.1.19, geocentric EQJ -> true ecliptic-of-date (ECT).
 * Never use EclipticLongitude() here: that API is heliocentric for most bodies.
 */
const Astronomy=require('astronomy-engine');
const VERSION='1.0.0', EPHEMERIS_VERSION='astronomy-engine@2.1.19';
const BODIES=['Sun','Moon','Mercury','Venus','Mars','Jupiter','Saturn','Uranus','Neptune','Pluto'];
const SIGNS=['牡羊','金牛','雙子','巨蟹','獅子','處女','天秤','天蠍','射手','摩羯','水瓶','雙魚'];
const ASPECTS=[['合相',0],['六分相',60],['四分相',90],['三分相',120],['對分相',180]];
const PHASES=['新月','盈眉月','上弦月','盈凸月','滿月','虧凸月','下弦月','殘月'];
const DAY=86400000;
const mod=x=>(x%360+360)%360;
const signed=x=>((x+540)%360)-180;
function toDate(x){const d=x instanceof Date?new Date(x.getTime()):new Date(x);if(!Number.isFinite(d.getTime()))throw Error('invalid UTC time');return d;}
function position(body,time){
  if(!BODIES.includes(body))throw Error('unsupported body');
  const d=toDate(time), geo=Astronomy.GeoVector(body,d,true), ecl=Astronomy.Ecliptic(geo);
  return {longitude:mod(ecl.elon),latitude:ecl.elat};
}
function velocity(body,time){
  const t=toDate(time).getTime(),h=3*3600000;
  return signed(position(body,t+h).longitude-position(body,t-h).longitude)/(2*h/DAY);
}
function ephemeris(time){
  const d=toDate(time);
  return BODIES.map(body=>{
    const p=position(body,d),v=velocity(body,d),index=Math.floor(p.longitude/30);
    return {body,sign:SIGNS[index],longitude:+p.longitude.toFixed(5),
      signDegree:+(p.longitude%30).toFixed(5),latitude:+p.latitude.toFixed(5),
      velocityDegPerDay:+v.toFixed(6),motion:Math.abs(v)<0.00005?'stationary':v<0?'retrograde':'direct'};
  });
}
function phase(time){
  const angle=mod(Astronomy.MoonPhase(toDate(time)));
  return {angle:+angle.toFixed(4),name:PHASES[Math.floor((angle+22.5)/45)%8]};
}
function separation(a,b){const diff=Math.abs(signed(a-b));return Math.min(diff,360-diff);}
function error(a,b,target){return Math.abs(separation(a,b)-target);}
function snapshot(time){
  const d=toDate(time),positions=ephemeris(d),aspects=[];
  for(let i=0;i<positions.length;i++)for(let j=i+1;j<positions.length;j++)
    for(const [name,angle] of ASPECTS){
      const orb=error(positions[i].longitude,positions[j].longitude,angle);
      if(orb<=2)aspects.push({first:positions[i].body,second:positions[j].body,
        type:name,angle,orb:+orb.toFixed(4),applying:orbAt(i,j,d.getTime()+3600000)<orb?'applying':'separating'});
    }
  function orbAt(i,j,t){return Math.min(...ASPECTS.filter(a=>aspects.some(e=>e.first===positions[i].body&&e.second===positions[j].body&&e.angle===a[1])).map(a=>error(position(positions[i].body,t).longitude,position(positions[j].body,t).longitude,a[1])).concat([999]));}
  return {at:d.toISOString(),positions,moonPhase:phase(d),aspects:aspects.sort((a,b)=>a.orb-b.orb)};
}
// Precise aspect minima: bracket by sampled local minima, refine golden-section
// in UTC. Event identity is based on nearest minute; no fake "exact time" daily bins.
function goldenMin(fn,a,b){
  const phi=(Math.sqrt(5)-1)/2;
  let x=b-phi*(b-a),y=a+phi*(b-a),fx=fn(x),fy=fn(y);
  for(let i=0;i<43;i++){
    if(fx<fy){b=y;y=x;fy=fx;x=b-phi*(b-a);fx=fn(x);}
    else{a=x;x=y;fx=fy;y=a+phi*(b-a);fy=fn(y);}
  }
  return (a+b)/2;
}
function findAspects(start,days=90){
  const begin=toDate(start).getTime(),step=12*3600000,N=Math.ceil(days*DAY/step);
  if(days<1||days>370)throw Error('event horizon must be 1..370 days');
  const frames=Array.from({length:N+3},(_,k)=>BODIES.map(b=>position(b,begin+k*step-step).longitude));
  const result=[];
  for(let i=0;i<BODIES.length;i++)for(let j=i+1;j<BODIES.length;j++)for(const [name,angle] of ASPECTS){
    const e=frames.map(f=>error(f[i],f[j],angle));
    for(let k=1;k<=N;k++){
      if(e[k]>e[k-1]||e[k]>e[k+1]||e[k]>7.5)continue;
      const f=t=>error(position(BODIES[i],t).longitude,position(BODIES[j],t).longitude,angle);
      const time=goldenMin(f,begin+(k-1)*step-step,begin+(k+1)*step-step);
      if(time<begin||time>begin+days*DAY||f(time)>0.06)continue;
      const iso=new Date(Math.round(time/60000)*60000).toISOString();
      const event={id:[BODIES[i],BODIES[j],angle,iso].join('-'),kind:'aspect',
        first:BODIES[i],second:BODIES[j],name,angle,utc:iso,orbAtMinimum:+f(time).toFixed(5)};
      if(!result.some(p=>p.first===event.first&&p.second===event.second&&p.angle===event.angle&&Math.abs(Date.parse(p.utc)-time)<2*DAY))result.push(event);
    }
  }
  return result.sort((a,b)=>a.utc.localeCompare(b.utc));
}
function findStations(start,days=90){
  const begin=toDate(start).getTime(),out=[];
  for(const body of BODIES.slice(2)){
    let a=begin,va=velocity(body,a);
    for(let b=begin+DAY;b<=begin+days*DAY;b+=DAY){
      const vb=velocity(body,b);
      if(va*vb<0){
        let lo=a,hi=b,vl=va;
        for(let n=0;n<35;n++){const mid=(lo+hi)/2,vm=velocity(body,mid);if(vm*vl<=0)hi=mid;else{lo=mid;vl=vm;}}
        const iso=new Date(Math.round((lo+hi)/120000)*60000).toISOString();
        out.push({id:body+'-station-'+iso,kind:'station',body,utc:iso,motionAfter:vb<0?'retrograde':'direct'});
      }
      a=b;va=vb;
    }
  }
  return out.sort((a,b)=>a.utc.localeCompare(b.utc));
}
function futureEvents(start,days=90){
  const d=toDate(start),all=[...findAspects(d,days),...findStations(d,days)];
  let q=Astronomy.SearchMoonQuarter(d);
  while(q?.time?.date?.getTime()<=d.getTime()+days*DAY){
    const t=q.time.date.toISOString();
    all.push({kind:'moon-quarter',id:'moon-quarter-'+t,utc:t,name:['新月','上弦月','滿月','下弦月'][q.quarter]});
    q=Astronomy.NextMoonQuarter(q);
  }
  return all.sort((a,b)=>a.utc.localeCompare(b.utc));
}
function build(now=new Date(),days=90){
  const date=toDate(now);
  return {schema:1,version:VERSION,source:EPHEMERIS_VERSION,coord:'geocentric true ecliptic of date (ECT), tropical',
    timeBasis:'UTC',generatedAt:date.toISOString(),validUntil:new Date(date.getTime()+36*3600000).toISOString(),
    snapshot:snapshot(date),events:futureEvents(date,days),traditionalInterpretationStatus:'tradition-only-not-validated',
    statisticalStatus:'unavailable-no-approved-price-history',
    disclaimer:'天文運算不代表市場預測。歷史統計與交易訊號必須獨立驗證。'};
}
module.exports={BODIES,SIGNS,ASPECTS,DAY,mod,signed,separation,error,position,velocity,phase,ephemeris,snapshot,goldenMin,findAspects,findStations,futureEvents,build};
if(require.main===module){const fs=require('node:fs'),path=require('node:path');const d=process.env.ASTRO_FIXED_NOW?new Date(process.env.ASTRO_FIXED_NOW):new Date();const out=path.resolve(__dirname,'../../docs/data/financial_astrology/latest.json');fs.mkdirSync(path.dirname(out),{recursive:true});fs.writeFileSync(out,JSON.stringify(build(d,90),null,2)+'\n');process.stdout.write('Generated '+out+'\n');}
