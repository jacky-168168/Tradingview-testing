/* G intraday historical browser. No invented time slots, no stale quote presented as live. */
(function(){
"use strict";
var root="./data/g_intraday/archive/",dates=[],day="",entries=[],selected=null,latest=null,pinned=false,chosen="",error="",seq=0,busy=false;
var memo=new Map(),initialised=false,DAY_MS=86400000;
function valid(g){return !!(g&&g.quality==="intraday-provisional-allmarket"&&Array.isArray(g.rows)&&/^20\d{2}-\d{2}-\d{2}$/.test(g.asOfDate||"")&&Number.isFinite(Date.parse(g.publishedAt)))}
function clock(t){return typeof t==="string"?t.slice(11,19):"--:--:--"}
function zoneToday(){return typeof taipeiDate==="function"?taipeiDate():new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date())}
function todayMinutes(){var parts=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Taipei",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(new Date());return Number(parts.find(x=>x.type==="hour").value)*60+Number(parts.find(x=>x.type==="minute").value)}
function slot(t){var v=Number(String(t||"").slice(11,13))*60+Number(String(t||"").slice(14,16));return Math.max(540,Math.min(810,Math.floor(v/30)*30))}
function slotText(min){return String(Math.floor(min/60)).padStart(2,"0")+":"+String(min%60).padStart(2,"0")}
function missing(){
 if(!day)return [];
 var current=day===zoneToday(),limit=current?Math.min(810,todayMinutes()-15):810;
 if(current&&todayMinutes()<555)return [];
 var seen=new Set(entries.map(x=>x.sessionSlot&&/^\d{2}:\d{2}$/.test(x.sessionSlot)?Number(x.sessionSlot.slice(0,2))*60+Number(x.sessionSlot.slice(3,5)):slot(x.publishedAt)));
 var missingSlots=[];for(var m=540;m<=limit;m+=30)if(!seen.has(m))missingSlots.push(slotText(m));
 return missingSlots;
}
async function json(url){var r=await fetch(url+(url.includes("?")?"&":"?")+"t="+Date.now(),{cache:"no-store"});if(!r.ok)throw Error("HTTP "+r.status);return r.json()}
function render(){if(typeof renderTable==="function")renderTable();if(typeof renderMeta==="function")renderMeta()}
function current(fallback){return selected||fallback||latest}
function historical(g){return !!(g&&(pinned||g.asOfDate!==zoneToday()||Date.now()-Date.parse(g.publishedAt)>110*60000||(latest&&g.publishedAt!==latest.publishedAt)))}
function options(){
 var el=document.getElementById("gHistoryDate");if(!el)return;
 var choices=dates.map(d=>'<option value="'+d+'">'+d+'</option>').join("");
 if(el.innerHTML!==choices)el.innerHTML=choices;
 el.value=day;
}
function paint(){
 var prev=document.getElementById("gHistoryPrev"),next=document.getElementById("gHistoryNext"),jump=document.getElementById("gHistoryLatest"),label=document.getElementById("gHistoryLabel"),note=document.getElementById("gHistoryNote"),health=document.getElementById("gHistoryHealth");
 if(!prev)return;
 options();
 var idx=entries.findIndex(x=>x.file===chosen),g=current(latest),n=entries.length,arch=historical(g),gap=missing();
 prev.disabled=busy||idx<=0;next.disabled=busy||idx<0||idx>=n-1;jump.disabled=busy||(!pinned&&idx===n-1);
 var tick=g?(g.sessionSlot||slotText(slot(g.scanStartedAt||g.publishedAt))):"--:--";
 label.textContent=(g?tick+" 時段｜"+clock(g.publishedAt)+" 實際完成":"尚無有效快照")+"　"+(n?(idx+1)+"/"+n+" 輪":"");
 if(health){
  var mark=arch?"歷史回看":(!g?"資料未就緒":"最新資料");
  if(!arch&&g&&Date.now()-Date.parse(g.publishedAt)>45*60000)mark="更新延遲";
  health.textContent=mark;
  health.className="g-history-state "+(arch?"archive":mark==="更新延遲"?"warning":"");
 }
 note.textContent=(error?"⚠ "+error+"。":"")+(gap.length?"⚠ 未留存的時段："+gap.join("、")+"；不能視為當時無股票入選。":"")+"僅提供成功儲存的實際榜單，頁面每90秒同步；查看歷史不會跳回最新。";
}
async function readEntry(item,d){
 if(!item)return null;
 if(item.file==="__latest__")return latest&&latest.asOfDate===d?latest:null;
 var key=d+"/"+item.file;
 if(memo.has(key))return memo.get(key);
 var snap=await json(root+key);
 if(!valid(snap)||snap.asOfDate!==d||snap.publishedAt!==item.publishedAt)throw Error("歷史檔案校驗不符");
 memo.set(key,snap);
 if(memo.size>28)memo.delete(memo.keys().next().value);
 return snap;
}
async function sync(g){
 if(valid(g))latest=g;
 var id=++seq,oldDay=day,oldChoice=chosen,wasPinned=pinned;error="";busy=true;paint();
 try{
  var cat=null;try{cat=await json(root+"index.json")}catch(e){error="歷史日期索引暫時無法讀取"}
  if(id!==seq)return;
  var found=Array.isArray(cat&&cat.dates)?cat.dates.filter(d=>/^20\d{2}-\d{2}-\d{2}$/.test(d)):[];
  if(latest&&!found.includes(latest.asOfDate))found.push(latest.asOfDate);
  dates=[...new Set(found)].sort().reverse();
  if(!wasPinned||!oldDay||!dates.includes(oldDay)){day=dates[0]||"";pinned=false;chosen=""}else{day=oldDay;chosen=oldChoice}
  var catalog=null;
  if(day)try{catalog=await json(root+day+"/index.json")}catch(e){error="當日歷史索引暫時無法讀取"}
  if(id!==seq)return;
  entries=(catalog&&catalog.date===day&&Array.isArray(catalog.snapshots)?catalog.snapshots:[])
    .filter(x=>x&&/^\d{6}(?:-\d+)?\.json$/.test(x.file||"")&&Number.isFinite(Date.parse(x.publishedAt)))
    .sort((a,b)=>a.publishedAt.localeCompare(b.publishedAt)||a.file.localeCompare(b.file));
  if(latest&&day===latest.asOfDate&&!entries.some(x=>x.publishedAt===latest.publishedAt))
   entries.push({file:"__latest__",publishedAt:latest.publishedAt,sessionSlot:latest.sessionSlot,count:latest.rows.length});
  var item=pinned?(chosen?entries.find(x=>x.file===chosen):entries[entries.length-1]):entries[entries.length-1];
  if(pinned&&chosen&&!item){error="舊輪次索引變動，保留原顯示；可按「回最新」";item=null}
  if(item){
   try{var loaded=await readEntry(item,day);if(id!==seq)return;selected=loaded;chosen=item.file}
   catch(e){error="該輪快照無法取得，已保留先前資料";if(!selected)chosen=""}
  }else if(!pinned){selected=latest&&latest.asOfDate===day?latest:null;chosen=""}
 }catch(e){if(id===seq)error="更新失敗，仍保留上一份已確認資料"}
 finally{if(id===seq){busy=false;paint()}}
}
async function changeTo(item){
 if(!item||busy)return;
 var id=++seq,previous=selected;busy=true;error="";paint();
 try{var snap=await readEntry(item,day);if(id!==seq)return;selected=snap;chosen=item.file;pinned=true}
 catch(e){selected=previous;error="這輪歷史檔案無法讀取，仍保留原榜單"}
 finally{if(id===seq){busy=false;paint();render()}}
}
async function move(n){var i=entries.findIndex(x=>x.file===chosen);return changeTo(entries[i+n])}
async function chooseDate(d){
 if(!dates.includes(d)||busy)return;
 day=d;pinned=true;chosen="";await sync(latest);render();
}
async function newest(){if(busy)return;pinned=false;chosen="";day="";await sync(latest);render()}
function init(){
 if(initialised)return;initialised=true;
 var p=document.getElementById("gHistoryPrev"),n=document.getElementById("gHistoryNext"),j=document.getElementById("gHistoryLatest"),d=document.getElementById("gHistoryDate");
 if(!p||!n||!j||!d)return;
 p.onclick=()=>move(-1);n.onclick=()=>move(1);j.onclick=()=>newest();d.onchange=()=>chooseDate(d.value);paint();
}
window.GIntradayTimeline={sync,current,historical,init,missing};
})();
