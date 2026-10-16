/* Historical G intraday scans: arrows move between actual successful runs, never invented slots. */
(function(){
"use strict";
var root="./data/g_intraday/archive/",dates=[],day="",entries=[],selected=null,pinned=false,chosen="",latest=null,seq=0,error="";
function valid(g){return !!(g&&g.quality==="intraday-provisional-allmarket"&&Array.isArray(g.rows)&&/^20\\d{2}-\\d{2}-\\d{2}$/.test(g.asOfDate||"")&&Number.isFinite(Date.parse(g.publishedAt)))}
async function json(url){var r=await fetch(url+(url.indexOf("?")>=0?"&":"?")+"t="+Date.now(),{cache:"no-store"});if(!r.ok)throw Error("HTTP "+r.status);return r.json()}
function render(){if(typeof renderTable==="function")renderTable();if(typeof renderMeta==="function")renderMeta()}
function current(fallback){return selected||fallback||latest}
function historical(g){return !!(g&&(pinned||g.asOfDate!==taipeiDate()||(latest&&g.publishedAt!==latest.publishedAt)))}
function options(){
 var el=document.getElementById("gHistoryDate");if(!el)return;
 el.innerHTML=dates.map(function(d){return '<option value="'+d+'">'+d+'</option>'}).join("");
 el.value=day;
}
function refresh(){
 var prev=document.getElementById("gHistoryPrev"),next=document.getElementById("gHistoryNext"),jump=document.getElementById("gHistoryLatest"),label=document.getElementById("gHistoryLabel"),note=document.getElementById("gHistoryNote");
 if(!prev)return;
 options();
 var at=entries.findIndex(function(x){return x.file===chosen}),g=current(latest),n=entries.length;
 prev.disabled=at<=0;next.disabled=at<0||at>=n-1;jump.disabled=!pinned&&at===n-1;
 var clock=g&&g.publishedAt?g.publishedAt.slice(11,19):"--:--";
 label.textContent=(day||"尚無日期")+"　"+clock+"　"+(n?(at+1)+"/"+n+" 輪":"尚無快照")+(historical(g)?"｜歷史":"｜最新");
 note.textContent=(error?error+"｜":"")+"箭頭只顯示實際成功存檔的輪次，缺跑不會補假榜單；選擇舊輪次後不會被90秒自動更新跳回最新。";
}
async function sync(g){
 latest=valid(g)?g:null;var id=++seq;error="";
 var catalog;
 try{catalog=await json(root+"index.json")}catch(_){catalog=null}
 if(id!==seq)return;
 dates=Array.isArray(catalog&&catalog.dates)?catalog.dates.filter(function(d){return /^20\\d{2}-\\d{2}-\\d{2}$/.test(d)}):[];
 if(latest&&dates.indexOf(latest.asOfDate)<0)dates.push(latest.asOfDate);
 dates.sort().reverse();
 if(!pinned||!day||dates.indexOf(day)<0){day=dates[0]||"";pinned=false;chosen=""}
 var manifest=null;
 if(day){try{manifest=await json(root+day+"/index.json")}catch(_){}}
 if(id!==seq)return;
 entries=manifest&&manifest.date===day&&Array.isArray(manifest.snapshots)?manifest.snapshots.filter(function(x){return x&&/^\\d{6}(?:-\\d+)?\\.json$/.test(x.file||"")&&Number.isFinite(Date.parse(x.publishedAt))}):[];
 entries.sort(function(a,b){return a.publishedAt.localeCompare(b.publishedAt)||a.file.localeCompare(b.file)});
 if(latest&&day===latest.asOfDate&&!entries.some(function(x){return x.publishedAt===latest.publishedAt})){
   entries.push({file:"__latest__",publishedAt:latest.publishedAt,count:latest.rows.length});
 }
 var item=pinned?entries.find(function(x){return x.file===chosen}):entries[entries.length-1];
 if(pinned&&!item){error="原先選取的輪次已無法取得，已恢復最新";pinned=false;item=entries[entries.length-1]}
 chosen=item?item.file:"";selected=null;
 if(item){
   if(item.file==="__latest__"&&latest){selected=latest}
   else try{
     var snap=await json(root+day+"/"+item.file);
     if(valid(snap)&&snap.asOfDate===day&&snap.publishedAt===item.publishedAt)selected=snap;
     else error="歷史快照內容校驗失敗";
   }catch(_){error="歷史快照讀取失敗"}
 }
 if(id!==seq)return;
 if(!selected&&latest&&!pinned&&day===latest.asOfDate){selected=latest}
 refresh();
}
async function move(n){
 var at=entries.findIndex(function(x){return x.file===chosen}),target=entries[at+n];
 if(!target)return;
 chosen=target.file;pinned=true;
 await sync(latest);render();
}
async function chooseDate(d){
 if(dates.indexOf(d)<0)return;
 day=d;pinned=true;chosen="";
 // Use the last actual snapshot of the selected date, never synthesize expected times.
 await sync(latest);render();
}
async function newest(){pinned=false;chosen="";day="";await sync(latest);render()}
function init(){
 var p=document.getElementById("gHistoryPrev"),n=document.getElementById("gHistoryNext"),j=document.getElementById("gHistoryLatest"),d=document.getElementById("gHistoryDate");
 if(!p||!n||!j||!d)return;
 p.onclick=function(){move(-1)};n.onclick=function(){move(1)};j.onclick=function(){newest()};d.onchange=function(){chooseDate(d.value)};
 refresh();
}
window.GIntradayTimeline={sync:sync,current:current,historical:historical,init:init};
})();
