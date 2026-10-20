/* Completed US-session freshness, not an intraday quote feed. */
(function(scope){
"use strict";
function easternParts(now=new Date()){
 const parts=new Intl.DateTimeFormat("en-US",{timeZone:"America/New_York",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",hourCycle:"h23"}).formatToParts(now);
 const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
 return {year:Number(p.year),month:Number(p.month),day:Number(p.day),hour:Number(p.hour)};
}
function expectedSession(now=new Date()){
 const p=easternParts(now);
 const d=new Date(Date.UTC(p.year,p.month-1,p.day,12));
 // Allow up to four hours after the 16:00 New York cash close for publishing.
 if(p.hour<20)d.setUTCDate(d.getUTCDate()-1);
 while(d.getUTCDay()===0||d.getUTCDay()===6)d.setUTCDate(d.getUTCDate()-1);
 return d.toISOString().slice(0,10);
}
function warning(actualDate,now=new Date()){
 const expected=expectedSession(now);
 if(!/^\d{4}-\d\d-\d\d$/.test(String(actualDate||"")))return {stale:true,expected,message:"⚠ 尚無具日期的美股收盤資料，不能視為即時行情。"};
 const stale=actualDate<expected;
 return {stale,expected,message:stale?"⚠ 美股資料待更新：最後已確認 "+actualDate+"，預期最近完成交易日 "+expected+"。可能是資料來源延遲、更新排程未完成，或美股休市；這不是即時行情。":""};
}
const api={expectedSession,warning};
scope.USMarketFreshness=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof window!=="undefined"?window:globalThis);
