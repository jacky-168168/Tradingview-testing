'use strict';
/** Financial astrology research: deterministic geocentric tropical ECT ephemerides. */
const Astronomy = require('astronomy-engine');
const VERSION = '2.1.19';
const BODIES = Object.freeze(['Sun','Moon','Mercury','Venus','Mars','Jupiter','Saturn','Uranus','Neptune','Pluto']);
const SIGNS = Object.freeze(['牡羊','金牛','雙子','巨蟹','獅子','處女','天秤','天蠍','射手','摩羯','水瓶','雙魚']);
const ASPECTS = Object.freeze([['conjunction',0],['sextile',60],['square',90],['trine',120],['opposition',180]]);
const MS_HOUR = 3600000;
function wrap(x){return ((x % 360) + 360) % 360;}
function signed(x){return wrap(x+180)-180;}
function utc(input){
  const d = input instanceof Date ? new Date(input.getTime()) : new Date(input);
  if(!Number.isFinite(d.getTime())) throw new Error('Invalid UTC timestamp');
  return d;
}
function longitude(name,time){
  if(!BODIES.includes(name)) throw new Error('Unsupported body: '+name);
  const date=utc(time);
  // EclipticLongitude() is HELIOCENTRIC: deliberately not used.
  const ect=name==='Moon'
    ? Astronomy.EclipticGeoMoon(date)
    : Astronomy.Ecliptic(Astronomy.GeoVector(Astronomy.Body[name],date,true));
  const lon=name==='Moon'?ect.lon:ect.elon;
  const lat=name==='Moon'?ect.lat:ect.elat;
  if(!Number.isFinite(lon)||!Number.isFinite(lat)) throw new Error('Invalid ephemeris for '+name);
  return {lon:wrap(lon), lat};
}
function pos(name,time){
  const t=utc(time);
  const {lon,lat}=longitude(name,t);
  const before=longitude(name,new Date(t.getTime()-6*MS_HOUR)).lon;
  const after=longitude(name,new Date(t.getTime()+6*MS_HOUR)).lon;
  const speed=signed(after-before)/0.5;
  return {name,longitudeDeg:+lon.toFixed(6),latitudeDeg:+lat.toFixed(6),
    sign:SIGNS[Math.floor(lon/30)],signDegree:+(lon%30).toFixed(4),
    speedDegPerDay:+speed.toFixed(6),
    motion:Math.abs(speed)<0.015?'stationary':speed<0?'retrograde':'direct',
    previousEventUtc:null,nextEventUtc:null};
}
function aspectError(bodyA,bodyB,target,time){
  return signed(longitude(bodyA,time).lon-longitude(bodyB,time).lon-target);
}
function distance(bodyA,bodyB,time){
  return Math.abs(signed(longitude(bodyA,time).lon-longitude(bodyB,time).lon));
}
function aspectDifference(bodyA,bodyB,target,time){
  return Math.abs(distance(bodyA,bodyB,time)-target);
}
function bisectCross(a,b,f){
  let left=a.getTime(),right=b.getTime(),fa=f(a);
  for(let i=0;i<45 && right-left>1000;i++){
    const mid=Math.floor((left+right)/2),fm=f(new Date(mid));
    if(fa*fm<=0)right=mid; else {left=mid;fa=fm;}
  }
  return new Date(Math.floor((left+right)/2));
}
function findWindow(bodyA,bodyB,angle,exact,orb=2){
  const fn=(d)=>aspectDifference(bodyA,bodyB,angle,d)-orb;
  function boundary(direction){
    let at=exact,prev=at;
    for(let i=0;i<720;i++){
      const next=new Date(at.getTime()+direction*3*MS_HOUR);
      if(fn(next)>0){
        return bisectCross(direction<0?next:prev,direction<0?prev:next,fn).toISOString();
      }
      at=next;prev=at;
    }
    return null; // slow orbs may span beyond 90 days, never fabricate boundary.
  }
  return {windowStartUtc:boundary(-1),windowEndUtc:boundary(1)};
}
function findExact(bodyA,bodyB,angle,start,end,opts={}){
  const first=utc(start),last=utc(end),step=Number(opts.stepHours||6)*MS_HOUR;
  if(!(last>first) || step<=0 || step>24*MS_HOUR) throw new Error('Invalid scan range');
  const orientations=angle===0||angle===180?[angle]:[angle,360-angle];
  const out=[];let previous=first;
  for(let current=new Date(first.getTime()+step);current<=last;current=new Date(current.getTime()+step)){
    for(const target of orientations){
      const a=aspectError(bodyA,bodyB,target,previous),b=aspectError(bodyA,bodyB,target,current);
      if(a*b<=0 && Math.max(Math.abs(a),Math.abs(b))<22){
        const exact=bisectCross(previous,current,t=>aspectError(bodyA,bodyB,target,t));
        if(!out.some(e=>Math.abs(new Date(e.exactUtc)-exact)<2*MS_HOUR)){
          const item={id:[bodyA,bodyB,angle,exact.toISOString()].join(':'),bodyA,bodyB,
            aspect:ASPECTS.find(x=>x[1]===angle)?.[0]||'custom',angleDeg:angle,
            exactUtc:exact.toISOString(),orbDeg:opts.orbDeg||2,
            actualAngleDeg:+distance(bodyA,bodyB,exact).toFixed(6)};
          if(opts.windows!==false)Object.assign(item,findWindow(bodyA,bodyB,angle,exact,item.orbDeg));
          out.push(item);
        }
      }
    }
    previous=current;
  }
  return out.sort((a,b)=>a.exactUtc.localeCompare(b.exactUtc));
}
function liveAspects(time,orb=2){
  const t=utc(time),out=[];
  for(let i=0;i<BODIES.length;i++) for(let j=i+1;j<BODIES.length;j++){
    const a=BODIES[i],b=BODIES[j],sep=distance(a,b,t);
    for(const [name,angle] of ASPECTS){
      const error=Math.abs(sep-angle);
      if(error<=orb){
        const future=distance(a,b,new Date(t.getTime()+MS_HOUR));
        out.push({bodyA:a,bodyB:b,aspect:name,targetAngleDeg:angle,
          actualAngleDeg:+sep.toFixed(5),orbErrorDeg:+error.toFixed(5),
          applying:Math.abs(future-angle)<error,
          interpretation:'傳統象徵性解讀；尚未驗證價格預測能力'});
      }
    }
  }
  return out.sort((x,y)=>x.orbErrorDeg-y.orbErrorDeg);
}
function snapshot(time){
  const now=utc(time);
  const positions=BODIES.map(x=>pos(x,now));
  const phase=Astronomy.MoonPhase(now);
  return {schemaVersion:1,generatedAt:now.toISOString(),ephemeris:{library:'astronomy-engine',
    version:VERSION,origin:'geocentric',zodiac:'tropical',frame:'true-ecliptic-of-date',
    longitudeRange:'[0,360)',timeStandard:'UTC',apparentAberration:true},
    timezoneDefault:'Asia/Taipei',positions,moon:{phaseAngleDeg:+phase.toFixed(6),
      phaseLabel:phase<22.5||phase>=337.5?'新月附近':phase<157.5?'盈月':phase<202.5?'滿月附近':'虧月'},
    aspects:liveAspects(now,2),orbDeg:2,verifiedReturnSignal:false};
}
module.exports={VERSION,BODIES,SIGNS,ASPECTS,wrap,signed,utc,longitude,pos,distance,aspectError,
  aspectDifference,bisectCross,findExact,findWindow,liveAspects,snapshot};
