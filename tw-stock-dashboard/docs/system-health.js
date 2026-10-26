(function(){
"use strict";
const REPO="jacky-168168/Tradingview-testing";
const HOLIDAYS=new Set("01-01 02-12 02-13 02-16 02-17 02-18 02-19 02-20 02-27 04-03 04-06 05-01 06-19 09-25 09-28 10-09 10-26 12-25".split(" "));
const $=id=>document.getElementById(id);
const dateAt=s=>{const n=Date.parse(s||"");return Number.isFinite(n)?n:null};
const minutesAgo=(stamp,now)=>{const d=dateAt(stamp);return d===null?null:(now.getTime()-d)/60000};
const apiPath=f=>"https://api.github.com/repos/"+REPO+"/actions/workflows/"+f+"/runs?per_page=10";
function localParts(now){
 const parts=new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23",weekday:"short"}).formatToParts(now);
 const p=Object.fromEntries(parts.filter(x=>x.type!=="literal").map(x=>[x.type,x.value]));
 return {date:p.year+"-"+p.month+"-"+p.day,mmdd:p.month+"-"+p.day,year:Number(p.year),weekday:p.weekday,minute:Number(p.hour)*60+Number(p.minute)};
}
function isGSession(now){
 const p=localParts(now);
 return !["Sat","Sun"].includes(p.weekday)&&!(p.year===2026&&HOLIDAYS.has(p.mmdd))&&p.minute>=590&&p.minute<825;
}
function show(id,title,detail,kind){
 const el=$(id+"State");
 el.textContent=title;el.className="status "+(kind||"");
 $(id+"Detail").textContent=detail;
}
async function read(url){
 const r=await fetch(url+(url.includes("?")?"&":"?")+"nocache="+Date.now(),{cache:"no-store"});
 if(!r.ok)throw Error("HTTP "+r.status);
 return r.json();
}
function validG(data,now){
 const p=localParts(now),r=data?.rows,c=data?.coverage,age=minutesAgo(data?.publishedAt,now);
 return data?.asOfDate===p.date&&data?.quality==="intraday-provisional-allmarket"&&
 Array.isArray(r)&&r.length>=1&&r.length<=20&&r.every(x=>/^[0-9]{4}$/.test(String(x.code||"")))&&
 age!==null&&age>=0&&age<=65&&c&&c.valid>=1000&&c.total>=1000&&c.valid/c.total>=.65&&
 ["上市","上櫃"].every(m=>c.exchange?.[m]?.total>0&&c.exchange[m].valid/c.exchange[m].total>=.6);
}
async function run(){
 $("refresh").disabled=true;
 const now=new Date(),parts=localParts(now),session=isGSession(now);
 $("summary").textContent="查核時間（臺灣） "+new Intl.DateTimeFormat("zh-TW",{timeZone:"Asia/Taipei",dateStyle:"long",timeStyle:"medium"}).format(now)+
   (session?"｜目前是 G 盤中巡檢時段":"｜休市或非 G 盤中巡檢時段；歷史榜單不視為當日故障");
 const G="./data/g_intraday/latest.json",S="./data/g_intraday/status.json",N="./data/market_events/latest.json";
 const [g,status,news,actions,mainG]=await Promise.allSettled([
    read(G),read(S),read(N),read(apiPath("tw-stock-dashboard.yml")),
    read("https://raw.githubusercontent.com/"+REPO+"/main/tw-stock-dashboard/docs/data/g_intraday/latest.json")
 ]);
 if(g.status==="fulfilled"){
   const d=g.value,age=minutesAgo(d.publishedAt,now),cov=d.coverage;
   const text="榜單日期："+(d.asOfDate||"未知")+"\n發布："+(d.publishedAt||"未知")+
     "\n距今："+(age===null?"未知":Math.round(age)+" 分鐘")+"\n股票："+(d.rows?.length??"未知")+
     "\n有效報價："+(cov?cov.valid+"/"+cov.total:"未知");
   if(!session)show("g","非盤中巡檢時段",text,"");
   else if(validG(d,now)){
     const fail=status.status==="fulfilled"&&status.value?.status==="unavailable"&&status.value?.asOfDate===parts.date&&
       dateAt(status.value.checkedAt)>dateAt(d.publishedAt);
     show("g",fail?"最新重選失敗":"資料品質通過",text+(fail?"\n狀態："+status.value.message:""),fail?"bad":"good");
   }else show("g","盤中資料過期或品質不足",text,"bad");
 }else show("g","資料無法驗證","G JSON 讀取失敗；不代表最新資料一定異常。","");
 if(news.status==="fulfilled"){
   const d=news.value,age=minutesAgo(d.generatedAt,now);
   const ok=age!==null&&age>=0&&age<=36*60&&["ok","partial","empty"].includes(d.status);
   show("news",ok?"新聞資料已同步":"新聞待更新／來源異常",
     "同步："+(d.generatedAt||"未知")+"\n最新文章："+(d.newestNewsAt||"未知")+
     "\n來源："+(d.feedsOk??"?")+"/"+(d.feedsTotal??"?")+"\n狀態："+(d.status||"未知"),ok?"good":"bad");
 }else show("news","新聞無法驗證","新聞 JSON 讀取失敗。","");
 if(actions.status==="fulfilled"){
   const rs=actions.value.workflow_runs||[],fresh=rs.filter(x=>{const age=minutesAgo(x.created_at,now);return age!==null&&age>=0&&age<=95});
   const failed=fresh.length>0&&fresh.every(x=>x.conclusion==="failure");
   show("actions",session&&(!fresh.length||failed)?"更新排程有異常":!session?"非盤中巡檢時段":"查到近期執行",
     "最近一次："+(rs[0]?.created_at||"未知")+"\n結果："+(rs[0]?.conclusion||rs[0]?.status||"未知")+
     "\n詳見 GitHub Actions；workflow_dispatch 與 schedule 需分別判斷。",session&&(!fresh.length||failed)?"bad":"");
 }else show("actions","Actions 無法驗證","GitHub 公開 API 暫時無法讀取；請查看 Actions 網頁。","");
 if(g.status==="fulfilled"&&mainG.status==="fulfilled"){
   const local=g.value.publishedAt,origin=mainG.value.publishedAt,age=minutesAgo(origin,now);
   const behind=dateAt(local)!==null&&dateAt(origin)!==null&&dateAt(local)<dateAt(origin);
   const lag=behind&&age!==null&&age>25;
   show("pages",lag?"GitHub Pages 發布落後":behind?"Pages 同步中（25 分鐘寬限）":"Pages 與 main 核對完成",
     "Pages："+(local||"未知")+"\nmain："+(origin||"未知")+
     "\n"+(lag?"主分支已發布超過25分鐘，但網站仍顯示舊榜單。":"未查到超過25分鐘的落後。"),lag?"bad":behind?"":"good");
 }else show("pages","網站同步無法驗證","Pages 或 main JSON 無法讀取，不能宣稱部署成功。","");
 $("refresh").disabled=false;
}
$("refresh").addEventListener("click",()=>run());
run().catch(e=>{$("summary").textContent="巡檢遭遇不可預期的錯誤："+String(e);$("refresh").disabled=false});
})();