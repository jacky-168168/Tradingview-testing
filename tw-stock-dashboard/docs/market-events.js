(function(){
"use strict";
var DATA=null,CATEGORY="all",SEARCH="",VISIBLE=20,URL="./data/market_events/latest.json";
var $=id=>document.getElementById(id);
function esc(s){return String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function safeUrl(s){return /^https:\/\//i.test(String(s||""))?s:"#"}
function dateTW(s){return String(s||"").slice(5,10).replace("-","/")}
function nowTW(){return new Intl.DateTimeFormat("en-CA",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date())}
function dateDiff(a,b){return Math.round((Date.parse(a+"T12:00:00+08:00")-Date.parse(b+"T12:00:00+08:00"))/86400000)}
function dateLabel(x,today){
 if(x.type==="event"){
  var end=x.endDate||x.date,n=dateDiff(x.date,today),done=dateDiff(end,today);
  if(n<=0&&done>=0)return "進行中｜"+dateTW(x.date)+"–"+dateTW(end);
  if(n>0)return n<=7?"還有 "+n+" 天｜"+dateTW(x.date)+"–"+dateTW(end):dateTW(x.date)+"–"+dateTW(end);
  return "已結束｜"+dateTW(end);
 }
 var stamp=String(x.publishedAt||"");
 return dateTW(x.date)+(stamp.length>=16?" "+stamp.slice(11,16):"");
}
function matches(x){
 if(CATEGORY==="event"&&x.type!=="event")return false;
 if(CATEGORY==="earnings"&&x.category!=="財報")return false;
 if(CATEGORY==="ai"&&!((x.category==="AI需求")||(x.themes||[]).some(v=>/AI|半導體|先進封裝|CPO|GPU|HBM|PCB|晶圓/i.test(v))))return false;
 if(CATEGORY==="prices"&&x.category!=="報價")return false;
 if(CATEGORY==="macro"&&x.category!=="總經")return false;
 // Historical "原物料" entries remain searchable in their matching commodity category.
 var legacy=x.category==="原物料",headline=String(x.title||"");
 if(CATEGORY==="energy"&&x.category!=="原油／能源"&&!(legacy&&/油價|原油|OPEC|WTI|布蘭特|天然氣/i.test(headline)))return false;
 if(CATEGORY==="metals"&&x.category!=="貴金屬"&&!(legacy&&/黃金|金價|白銀|銀價|鉑金|鈀金/i.test(headline)))return false;
 if(CATEGORY==="agriculture"&&x.category!=="農產品")return false;
 if(CATEGORY==="ptt"&&x.category!=="PTT轉載")return false;
 var query=SEARCH.trim().toLowerCase();
 return !query||[x.title,x.source,x.category,...(x.themes||[])].join(" ").toLowerCase().includes(query);
}
function card(x,today){
 var themes=(x.themes||[]).slice(0,4).map(t=>'<span class="theme">'+esc(t)+'</span>').join("");
 var stamp=dateLabel(x,today),category=x.type==="event"?"🗓 官方活動":esc(x.category||"新聞");
 var href=safeUrl(x.url);
 return '<article class="item '+(x.type==="event"?"event":"news")+'"><div class="meta"><span class="cat">'+category+'</span><time>'+esc(stamp)+'</time></div>'+
 '<h3><a href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">'+esc(x.title)+'</a></h3>'+
 '<div class="foot"><span class="source" title="'+esc(x.source)+'">'+esc(x.source)+'</span><a class="openlink" href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">來源 ↗</a></div>'+
 (themes?'<div class="themes" style="margin-top:10px">'+themes+'</div>':"")+'</article>';
}
// The feed may be cached or its workflow may be stuck. Never label old
// headlines as the newest news simply because a JSON file is still available.
var NEWS_MAX_AGE_MS=48*60*60*1000;
function newsIsFresh(x){
 var t=Date.parse(String(x.publishedAt||"")),age=Date.now()-t;
 return Number.isFinite(t)&&age>=-5*60*1000&&age<=NEWS_MAX_AGE_MS;
}
function render(){
 var items=Array.isArray(DATA&&DATA.items)?DATA.items:[],today=nowTW();
 var relevant=items.filter(x=>x&&x.title&&x.date&&x.source&&x.url&&matches(x));
 var events=relevant.filter(x=>x.type==="event"&&dateDiff(x.endDate||x.date,today)>=0).sort((a,b)=>a.date.localeCompare(b.date)).slice(0,12);
 var news=relevant.filter(x=>x.type==="news"&&newsIsFresh(x)).sort((a,b)=>String(b.publishedAt||"").localeCompare(String(a.publishedAt||"")));
 $("events").innerHTML=events.map(x=>card(x,today)).join("");
 $("news").innerHTML=news.slice(0,VISIBLE).map(x=>card(x,today)).join("");
 $("moreNews").hidden=news.length<=VISIBLE;
 $("moreNews").textContent="顯示更多（剩餘 "+Math.max(0,news.length-VISIBLE)+" 則） ↓";
 $("eventSection").hidden=!events.length;$("newsSection").hidden=!news.length;
 $("eventCount").textContent=events.length+" 件";$("newsCount").textContent=news.length+" 則";
 $("empty").hidden=events.length+news.length>0;
 $("empty").textContent="最近 48 小時沒有符合條件的重大新聞或未來活動；舊新聞不會冒充最新消息。";
 var generated=DATA&&DATA.generatedAt||"",state=DATA&&DATA.status||"";
 $("freshness").textContent=generated?"資料同步 "+dateTW(generated)+" "+generated.slice(11,16)+(DATA.newestNewsAt?"｜最新文章 "+dateTW(DATA.newestNewsAt)+" "+DATA.newestNewsAt.slice(11,16):""):"新聞資料尚未載入";
 var note="";
 if(state==="initializing")note="新聞同步尚未完成，以下僅為官方活動。";
 else if(state==="degraded")note="新聞來源暫時無法更新，僅供查看已保存資料。";
 else if(state==="partial")note="部分新聞來源暫時無法讀取。";
 else if(state==="empty")note="已完成新聞來源檢查，但沒有符合最近 48 小時條件的新文章。";
 if(generated&&Date.now()-Date.parse(generated)>36*3600000)note=(note?note+" ":"")+"⚠ 新聞超過 36 小時未更新。";
 if(!news.length&&items.some(x=>x.type==="news"))note=(note?note+" ":"")+"已隱藏超過 48 小時的舊新聞。";
 $("alert").textContent=note;$("alert").hidden=!note;
}
async function load(){
 try{
  var r=await fetch(URL+"?t="+Date.now(),{cache:"no-store"});
  if(!r.ok)throw Error("HTTP "+r.status);
  var j=await r.json();
  if(!j||!Array.isArray(j.items)||j.schema!==1)throw Error("invalid schema");
  DATA=j;render();
 }catch(e){
  if(DATA){$("alert").textContent="⚠ 更新失敗，顯示上次資料。";$("alert").hidden=false;return}
  $("freshness").textContent="資料暫時無法讀取";
  $("alert").textContent="⚠ 資料暫時無法讀取，請重新整理頁面。";$("alert").hidden=false;
 }
}
$("filters").addEventListener("click",e=>{
 var btn=e.target.closest("button[data-cat]");if(!btn)return;
 CATEGORY=btn.dataset.cat;VISIBLE=20;
 $("filters").querySelectorAll("button[data-cat]").forEach(b=>b.setAttribute("aria-pressed",b===btn?"true":"false"));
 render();
});
$("query").addEventListener("input",e=>{SEARCH=e.target.value;VISIBLE=20;render()});
$("moreNews").addEventListener("click",()=>{VISIBLE+=20;render()});
load();setInterval(load,15*60*1000);
})();
