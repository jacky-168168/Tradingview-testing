// Independent Cloudflare clock, separate from GitHub Actions scheduling.
// Does not trade or modify stock data. Dispatches an existing GitHub Workflow.
const API="https://api.github.com/repos/jacky-168168/Tradingview-testing";
const CLOSED_2026=new Set("01-01 02-12 02-13 02-16 02-17 02-18 02-19 02-20 02-27 04-03 04-06 05-01 06-19 09-25 09-28 10-09 10-26 12-25".split(" "));
export function taipeiParts(now){
 const fmt=new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23",weekday:"short"});
 const p=Object.fromEntries(fmt.formatToParts(now).filter(x=>x.type!=="literal").map(x=>[x.type,x.value]));
 return {date:p.year+"-"+p.month+"-"+p.day,year:Number(p.year),mmdd:p.month+"-"+p.day,
    weekday:p.weekday,minutes:Number(p.hour)*60+Number(p.minute)};
}
export function inTradingWindow(now){
 const p=taipeiParts(now);
 return !["Sat","Sun"].includes(p.weekday) &&
   !(p.year===2026&&CLOSED_2026.has(p.mmdd)) &&
   p.minutes>=9*60+35&&p.minutes<=13*60+42;
}
export function decide(now,latest,status,runs){
 if(!inTradingWindow(now))return {dispatch:false,reason:"outside-trading-window"};
 const tw=taipeiParts(now),published=Date.parse(latest?.publishedAt||""),
   age=Number.isFinite(published)?(now.getTime()-published)/60000:null;
 const c=latest?.coverage, rows=latest?.rows;
 const valid=Array.isArray(rows)&&rows.length>=1&&rows.length<=20&&rows.every(r=>/^[0-9]{4}$/.test(String(r.code||"")));
 const coverage=!!(c&&c.total>=1000&&c.valid>=1000&&c.valid/c.total>=.65&&
   ["上市","上櫃"].every(m=>c.exchange?.[m]?.total>=500&&c.exchange[m].valid/c.exchange[m].total>=.6));
 const ok=(latest?.asOfDate===tw.date&&latest?.quality==="intraday-provisional-allmarket"&&valid&&coverage&&
   age!==null&&age>=0&&age<=55);
 const unavailable=(status?.status==="unavailable"&&status?.asOfDate===tw.date&&
   Number.isFinite(Date.parse(status.checkedAt||""))&&
   (!Number.isFinite(published)||Date.parse(status.checkedAt)>published));
 if(ok&&!unavailable)return {dispatch:false,reason:"fresh-G"};
 for(const run of runs||[]){
   if(run.name!=="TW Stock Dashboard")continue;
   const started=Date.parse(run.created_at||"");if(!Number.isFinite(started))continue;
   const since=(now.getTime()-started)/60000;
   if(since>=0&&since<20)return {dispatch:false,reason:"dashboard-recently-started"};
   if(since>=0&&since<95&&["queued","waiting","in_progress","pending","requested"].includes(run.status))
     return {dispatch:false,reason:"dashboard-in-progress"};
 }
 return {dispatch:true,reason:unavailable?"newer-unavailable":"missing-or-expired-G"};
}
async function json(url,token){
 const r=await fetch(url,{headers:{"Accept":"application/vnd.github+json","User-Agent":"tw-loop-cloudflare-clock",
   ...(token?{"Authorization":"Bearer "+token}:{}),"Cache-Control":"no-cache"}});
 if(!r.ok)throw Error("GitHub HTTP "+r.status);
 return r.json();
}
export async function tick(now,env,client={json}){
 if(!inTradingWindow(now))return {dispatch:false,reason:"outside-trading-window"};
 const token=env.GITHUB_DISPATCH_TOKEN;
 if(!token)return {dispatch:false,reason:"missing-deployment-secret"};
 const [latest,status,runs]=await Promise.all([
   client.json(API+"/contents/tw-stock-dashboard/docs/data/g_intraday/latest.json?ref=main",token),
   client.json(API+"/contents/tw-stock-dashboard/docs/data/g_intraday/status.json?ref=main",token),
   client.json(API+"/actions/workflows/tw-stock-dashboard.yml/runs?per_page=20",token)
 ]);
 const decoder=raw=>JSON.parse(atob(raw.content.replace(/\s/g,"")));
 const decision=decide(now,decoder(latest),decoder(status),runs.workflow_runs||[]);
 if(!decision.dispatch)return decision;
 const r=await fetch(API+"/actions/workflows/tw-stock-dashboard.yml/dispatches",{
   method:"POST",headers:{"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
     "Content-Type":"application/json","User-Agent":"tw-loop-cloudflare-clock"},
   body:JSON.stringify({ref:"main",inputs:{mode:"intraday"}})
 });
 if(r.status!==204)throw Error("workflow_dispatch rejected with HTTP "+r.status);
 return {dispatch:true,reason:decision.reason,accepted:true};
}
export default {
 async scheduled(controller,env,ctx){
   const now=new Date(controller.scheduledTime||Date.now());
   ctx.waitUntil(tick(now,env).then(x=>console.log("CLOUDFLARE_G_CLOCK",JSON.stringify(x)))
     .catch(e=>console.error("CLOUDFLARE_G_CLOCK_ERROR",String(e))));
 },
 async fetch(){return new Response("Scheduled-only G recovery; no public trigger.",{status:404})}
};
