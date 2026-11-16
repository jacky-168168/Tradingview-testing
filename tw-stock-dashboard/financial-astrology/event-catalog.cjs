'use strict';
/** Reproducible, predeclared additional hypotheses. Never tune to historical market returns. */
const A=require('astronomy-engine');
const astro=require('./astro-core.cjs');
const PERIODS=Object.freeze([
 {id:'mars_jupiter_conjunction',label:'火星與木星合相',group:'planetary',angle:0,
  bodies:['Mars','Jupiter'],hypothesis:'expansion/action'},
 {id:'venus_jupiter_conjunction',label:'金星與木星合相',group:'planetary',angle:0,
  bodies:['Venus','Jupiter'],hypothesis:'valuation/optimism'},
 {id:'mars_saturn_square',label:'火星與土星四分相',group:'planetary',angle:90,
  bodies:['Mars','Saturn'],hypothesis:'friction/constraint'},
 {id:'jupiter_saturn_conjunction',label:'木星與土星合相',group:'planetary',angle:0,
  bodies:['Jupiter','Saturn'],hypothesis:'long-cycle structure'},
 {id:'saturn_uranus_square',label:'土星與天王星四分相',group:'planetary',angle:90,
  bodies:['Saturn','Uranus'],hypothesis:'structure versus innovation'},
 {id:'new_moon',label:'新月',group:'lunar',angle:0,hypothesis:'lunar month new phase'},
 {id:'full_moon',label:'滿月',group:'lunar',angle:180,hypothesis:'lunar month full phase'},
 {id:'mercury_retrograde_start',label:'水星開始逆行',group:'station',
  body:'Mercury',hypothesis:'information-cycle stations'}
]);
const HOUR=3600000;
function zeroSigned(deg){return astro.signed(deg);}
function moonError(target,t){return zeroSigned(A.MoonPhase(t)-target);}
function moonEvents(target,start,end){
 const events=[],limit=astro.utc(end),step=12*HOUR;
 let last=astro.utc(start);
 for(let current=new Date(last.getTime()+step);current<=limit;current=new Date(current.getTime()+step)){
  const old=moonError(target,last),now=moonError(target,current);
  if(old*now<=0 && Math.max(Math.abs(old),Math.abs(now))<20){
   const exact=astro.bisectCross(last,current,d=>moonError(target,d));
   if(!events.some(e=>Math.abs(Date.parse(e.exactUtc)-exact.getTime())<3*86400000)){
    events.push({exactUtc:exact.toISOString(),actualAngleDeg:+A.MoonPhase(exact).toFixed(5),
      bodyA:'Sun',bodyB:'Moon',orbDeg:2,kind:'moonphase'});
   }
  }
  last=current;
 }
 return events;
}
function stationEvents(name,start,end){
 const events=[],limit=astro.utc(end),step=24*HOUR;
 let prev=astro.utc(start);
 for(let cur=new Date(prev.getTime()+step);cur<=limit;cur=new Date(cur.getTime()+step)){
  const a=astro.pos(name,prev).speedDegPerDay,b=astro.pos(name,cur).speedDegPerDay;
  // Retrograde START only (positive to negative), not every station.
  if(a>0 && b<=0){
   const exact=astro.bisectCross(prev,cur,d=>astro.pos(name,d).speedDegPerDay);
   if(!events.some(e=>Math.abs(Date.parse(e.exactUtc)-exact)<4*86400000)){
    events.push({exactUtc:exact.toISOString(),bodyA:name,bodyB:null,
      actualAngleDeg:null,orbDeg:null,kind:'retrograde-station'});
   }
  }
  prev=cur;
 }
 return events;
}
function catalog(start,end,{include=[]}={}){
 const records={};
 const requested=new Set(include.length?include:PERIODS.map(s=>s.id));
 for(const config of PERIODS){
  if(!requested.has(config.id))continue;
  let events;
  if(config.group==='planetary'){
   events=astro.findExact(config.bodies[0],config.bodies[1],config.angle,start,end,
     {stepHours:config.bodies.includes('Sun')?6:12,orbDeg:2,windows:false});
  }else if(config.group==='lunar'){
   events=moonEvents(config.angle,start,end);
  }else if(config.group==='station'){
   events=stationEvents(config.body,start,end);
  }
  events=events.map((e,i)=>({...e,id:config.id+':'+e.exactUtc,
    eventFamily:config.id,angleDeg:config.angle??null,
    uncertainty:'time root found from geocentric astronomical ephemeris'}));
  records[config.id]={id:config.id,label:config.label,group:config.group,
   hypothesis:config.hypothesis,method:'predeclared ephemeris exact events',
   status:'astronomical-events-computed-not-market-validated',
   events};
 }
 return {schemaVersion:1,computedAt:new Date().toISOString(),
  ephemeris:'Astronomy Engine 2.1.19, geocentric tropical true ecliptic-of-date',
  startUtc:astro.utc(start).toISOString(),endUtc:astro.utc(end).toISOString(),
  studyStatus:'research-only',noTradingSignal:true,studyFamilies:records};
}
module.exports={PERIODS,moonError,moonEvents,stationEvents,catalog};
