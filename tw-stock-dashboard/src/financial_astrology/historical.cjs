'use strict';
/* Offline historical event catalogue, generated only by explicit workflow dispatch.
 * Annual chunks prevent oversized repeated daily workflow runs.
 * No market data is generated in this file.
 */
const fs=require('node:fs'),path=require('node:path');
const {findAspects,findStations,DAY}=require('./engine.cjs');
function history(startYear=2000,endYear=new Date().getUTCFullYear()){
 if(!Number.isInteger(startYear)||!Number.isInteger(endYear)||startYear<1900||endYear>2100||endYear<startYear||endYear-startYear>40)
   throw Error('bad year range');
 const events=[];
 for(let year=startYear;year<=endYear;year++){
   const start=Date.UTC(year,0,1),end=Date.UTC(year+1,0,1),days=(end-start)/DAY;
   const e=[...findAspects(new Date(start),days),...findStations(new Date(start),days)];
   for(const item of e)if(Date.parse(item.utc)<end)events.push(item);
 }
 const unique=new Map(events.map(e=>[e.id,e]));
 const doc={schema:1,generatedAt:new Date().toISOString(),startYear,endYear,
  coord:'geocentric true ecliptic of date',source:'astronomy-engine@2.1.19',
  events:[...unique.values()].sort((a,b)=>a.utc.localeCompare(b.utc)),
  note:'Astronomical event catalogue only. Contains no historical market returns.'};
 return doc;
}
if(require.main===module){
 const start=Number(process.env.ASTRO_START_YEAR||2000),end=Number(process.env.ASTRO_END_YEAR||new Date().getUTCFullYear());
 const output=path.resolve(__dirname,'../../research/financial_astrology/historical-events.json');
 const doc=history(start,end);fs.mkdirSync(path.dirname(output),{recursive:true});
 fs.writeFileSync(output,JSON.stringify(doc,null,2)+'\n');
 console.log('Created '+doc.events.length+' historical astronomical events');
}
module.exports={history};