/* Optional, independently hosted Cloudflare cron backup for Taiwan G scans.
 * Requires GH_ACTIONS_TOKEN (fine-grained token: only this repo, Actions write).
 * Never exposes an HTTP handler, a token or a public dispatch endpoint.
 */
const API="https://api.github.com/repos/jacky-168168/Tradingview-testing";
const HOLIDAYS_2026=new Set("01-01 02-12 02-13 02-16 02-17 02-18 02-19 02-20 02-27 04-03 04-06 05-01 06-19 09-25 09-28 10-09 10-26 12-25".split(" "));
function taipeiParts(now){
 const p=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",weekday:"short",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(now);
 return Object.fromEntries(p.filter(v=>v.type!=="literal").map(v=>[v.type,v.value]));
}
function localSlot(now){
 const p=taipeiParts(now),mins=Number(p.hour)*60+Number(p.minute);
 const localDate=p.year+"-"+p.month+"-"+p.day;
 if(["Sat","Sun"].includes(p.weekday)||(p.year==="2026"&&HOLIDAYS_2026.has(p.month+"-"+p.day))||mins<544||mins>817)return null;
 const slot=Math.max(540,Math.min(810,Math.floor(mins/30)*30));
 return {date:localDate,slot,hhmm:String(Math.floor(slot/60)).padStart(2,"0")+":"+String(slot%60).padStart(2,"0")};
}
function isComplete(info,slot){
 if(!info||info.asOfDate!==slot.date||info.quality!=="intraday-provisional-allmarket"||!Array.isArray(info.rows))return false;
 const t=Date.parse(info.publishedAt);if(!Number.isFinite(t))return false;
 const p=taipeiParts(new Date(t));
 return p.year+"-"+p.month+"-"+p.day===slot.date&&Number(p.hour)*60+Number(p.minute)>=slot.slot;
}
async function api(path,token,init={}){
 const res=await fetch(API+path,{...init,headers:{"Accept":"application/vnd.github+json","Authorization":"Bearer "+token,"User-Agent":"g-intraday-backup-cron","X-GitHub-Api-Version":"2022-11-28",...(init.headers||{})},signal:AbortSignal.timeout(8500)});
 if(!res.ok)throw new Error("GitHub HTTP "+res.status+" on "+path.split("?")[0]);
 return res.status===204?null:res.json();
}
async function latest(token){
 const c=await api("/contents/tw-stock-dashboard/docs/data/g_intraday/latest.json?ref=main",token);
 const chars=Uint8Array.from(atob(c.content.replace(/\s/g,"")),x=>x.charCodeAt(0));
 return JSON.parse(new TextDecoder().decode(chars));
}
function activeForSlot(runs,now,slot){
 const zero=new Date(slot.date+"T"+slot.hhmm+":00+08:00").getTime();
 return (runs||[]).some(r=>r.name==="TW Stock Dashboard"&&
   r.created_at&&Date.parse(r.created_at)>=zero&&Date.parse(r.created_at)<=now.getTime()&&
   ["queued","waiting","in_progress","pending","requested"].includes(r.status));
}
async function runBackup(now,env,scheduledAt=now){
 const slot=localSlot(now);
 if(!slot)return {action:"skip",reason:"outside trading session"};
 if(Math.abs(now.getTime()-scheduledAt.getTime())>12*60000)return {action:"skip",reason:"trigger too late"};
 if(!env.GH_ACTIONS_TOKEN)throw new Error("Missing GH_ACTIONS_TOKEN Worker secret");
 const token=env.GH_ACTIONS_TOKEN;
 let info=null,readProblem="";
 try{info=await latest(token)}catch(e){readProblem=String(e)}
 if(isComplete(info,slot))return {action:"skip",reason:"scan already published",slot:slot.hhmm};
 const data=await api("/actions/workflows/tw-stock-dashboard.yml/runs?per_page=30",token);
 if(activeForSlot(data.workflow_runs,now,slot))return {action:"skip",reason:"existing job still running",slot:slot.hhmm};
 await api("/actions/workflows/tw-stock-dashboard.yml/dispatches",token,{
   method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({ref:"main",inputs:{mode:"intraday"}})
 });
 return {action:"dispatched",slot:slot.hhmm,warning:readProblem||undefined};
}
export default {
 async scheduled(controller,env){
  const now=new Date();
  const result=await runBackup(now,env,new Date(controller.scheduledTime));
  console.log(JSON.stringify(result));
 }
};
export {runBackup,localSlot,isComplete,activeForSlot};
