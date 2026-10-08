// G 2026 統一回測面板：僅移除首頁研究入口，原始研究頁及 JSON 不刪除。
(function(){
"use strict";
const el=id=>document.getElementById(id), root=el("gView");
if(!root)return;
const defs=[
{id:"G_DOUBLE_PERSIST",name:"G 雙突破＋持續度（現行主模型）",source:"persistence"},
{id:"G_PERSIST",name:"G 強勢持續度",source:"persistence"},
{id:"G_BASE",name:"G_BASE 原始強勢",source:"original"},
{id:"G_RELAXED",name:"G_RELAXED 寬鬆版",source:"original"},
{id:"G_STRICT",name:"G_STRICT 嚴格版",source:"original"}
];
const data={},loadErrors={};let selected=defs[0].id,initialized=false;
const esc=v=>String(v==null?"":v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const n=(v,d=2)=>v==null||v===""||!Number.isFinite(Number(v))?"—":Number(v).toFixed(d);
const pct=(v,d=2)=>v==null||!Number.isFinite(Number(v))?"—":n(v,d)+"%";
const tint=v=>v==null||!Number.isFinite(Number(v))?"":Number(v)>0?"good":Number(v)<0?"bad":"";
const ret=v=>'<span class="'+tint(v)+'">'+pct(v)+'</span>';
const val=(v)=>v==null?"—":esc(v);
const current=()=>defs.find(x=>x.id===selected);
const currentData=()=>data[current().source]||null;
const currentModel=()=>currentData()?.models?.[selected]||null;
const txt=(id,s)=>el(id).textContent=s;
function showG(){
el("legacyView").style.display="none";root.style.display="block";
document.querySelectorAll("#modelTabs button").forEach(b=>b.classList.toggle("on",b.id==="G"));
if(!initialized){initialized=true;reload()}else render();
}
function render(){
const d=currentData(),m=currentModel(),def=current();
document.querySelectorAll("[data-gmodel]").forEach(b=>b.classList.toggle("on",b.dataset.gmodel===selected));
txt("gCurrent",def.name);
const failed=Object.values(loadErrors).filter(Boolean);
txt("gStatus",failed.join(" ｜ "));
if(!m){
txt("gMeta", "模型資料尚未取得，請檢查回測工作流程是否已產出 2026 JSON。");
for(const id of ["gDays","gCandidates","gThree","gHit20","gHit3","gTen"])txt(id,"—");
el("gPerformance").innerHTML='<tr><td colspan="12">回測資料尚未載入</td></tr>';
el("gAudits").innerHTML=el("gTrades").innerHTML='<tr><td colspan="12">尚無資料</td></tr>';
el("gPocketSection").style.display="none";el("gDedupSection").style.display="none";return;
}
const audit=def.source==="persistence"?m.sampleAudit:d.sampleAudit?.[selected],s10=m.summary?.find(x=>x.horizon===10),c=m.candidateStats||{};
txt("gMeta","期間："+val(d.period?.start)+" ～ "+val(d.period?.end)+" ｜ 更新："+val(d.generatedAt)+" ｜ 版本："+val(d.version)+" ｜ K線錯誤："+val(d.historyErrors));
txt("gDays",val(d.signalDays));txt("gCandidates",n(c.avg,1));txt("gThree",val(c.days3)+"/"+val(c.days??c.totalDays));
txt("gHit20",audit?val(audit.top20)+"/"+val(audit.total??audit.n):"—");
txt("gHit3",audit?val(audit.top3)+"/"+val(audit.total??audit.n):"—");
txt("gTen",pct(s10?.top3Daily?.avg));
txt("gNotes",(d.notes||[]).join(" ｜ "));
renderPerformance();renderAudits(audit);renderTrades();renderPersistence();
}
function splitPnL(m,h){
const profits=[],losses=[];for(const x of m.signals||[]){
const v=x["ret"+h];if(v==null||!Number.isFinite(Number(v)))continue;
if(Number(v)>0)profits.push(Number(v));else if(Number(v)<0)losses.push(Number(v));
}
const avg=a=>a.length?a.reduce((s,v)=>s+v,0)/a.length:null;
return {np:profits.length,ap:avg(profits),nl:losses.length,al:avg(losses)};
}
function renderPerformance(){
const rows=[];
for(const def of defs){
const d=data[def.source],m=d?.models?.[def.id];
if(!m)continue;
for(const v of m.summary||[]){
const a=v.top3Daily||{},q=v.phasePortfolio||{},pn=splitPnL(m,v.horizon);
rows.push('<tr'+(def.id===selected?' class="g-selected"':'')+'><td><b>'+esc(def.id)+'</b></td><td>'+v.horizon+'D</td><td>'+(a.n??"—")+'</td><td>'+ret(a.avg)+'</td><td>'+pct(a.median)+'</td><td>'+pct(a.win,1)+'</td><td>'+pn.np+'</td><td>'+ret(pn.ap)+'</td><td>'+pn.nl+'</td><td>'+ret(pn.al)+'</td><td>'+ret(q.meanTotalReturn)+'</td></tr>');
}
}
el("gPerformance").innerHTML=rows.join("")||'<tr><td colspan="11">尚無績效資料</td></tr>';
}
function renderAudits(audit){
const xs=audit?.checks||[];
el("gAudits").innerHTML=xs.map(x=>{
const p=x.percentiles||{};
return '<tr><td>'+esc(x.postDate||x.date||"")+' '+esc(x.postTime||"")+'</td><td><b>'+esc(x.code||"")+' '+esc(x.name||"")+'</b></td><td>'+esc(x.anchorDate||"")+'</td><td>'+val(x.rank??"未入選")+'</td><td>'+pct(p.ret20P)+'</td><td>'+pct(p.slopeP)+'</td><td>'+pct(p.range20P)+'</td><td>'+esc((x.failures||[]).join("、")||"—")+'</td></tr>';
}).join("")||'<tr><td colspan="8">沒有歷史訊號稽核資料</td></tr>';
}
function renderTrades(){
const m=currentModel();if(!m)return;
const q=el("gSearch").value.trim().toLowerCase();
const xs=(m.signals||[]).filter(x=>((x.code||"")+" "+(x.name||"")).toLowerCase().includes(q)).slice().sort((a,b)=>(b.signalDate||"").localeCompare(a.signalDate||"")||a.rank-b.rank);
txt("gTradeCount","共 "+xs.length+" 筆（最多顯示最新500筆；同股不同訊號日可能重複）");
el("gTrades").innerHTML=xs.slice(0,500).map(x=>'<tr><td>'+esc(x.signalDate)+'</td><td>'+val(x.rank)+'</td><td><b>'+esc(x.code)+' '+esc(x.name)+'</b></td><td>'+n(x.score)+'</td><td>'+pct(x.breakoutPct)+'</td>'+[1,3,5,10,20].map(h=>'<td>'+ret(x["ret"+h])+'</td>').join("")+'</tr>').join("")||'<tr><td colspan="10">沒有相符資料</td></tr>';
}
function renderPersistence(){
const m=currentModel();const isP=current().source==="persistence";
el("gPocketSection").style.display=isP?"block":"none";el("gDedupSection").style.display=isP?"block":"none";
if(!isP||!m)return;
txt("gPocketDate",val(m.latestPocket?.date));
const rows=(m.latestPocket?.rows||[]).slice(0,20);
el("gPockets").innerHTML=rows.map(x=>'<tr><td>'+val(x.rank)+'</td><td><b>'+esc(x.code)+' '+esc(x.name)+'</b></td><td>'+n(x.score)+'</td><td>'+n(x.persistence?.strength,1)+'</td><td>'+val(x.persistence?.past10Top20)+'</td><td>'+val(x.persistence?.priorStreak)+'</td><td>'+[x.flags?.break3?"3D突破":"",x.flags?.break18?"18D突破":""].filter(Boolean).join("＋")+'</td></tr>').join("")||'<tr><td colspan="7">當日沒有符合的 G 口袋名單</td></tr>';
el("gDedup").innerHTML=[5,10,20].map(h=>{
const a=m.repeatAudit?.noDoubleBuy?.[String(h)]||{};
return '<tr><td>'+h+'D</td><td>'+val(a.raw?.n)+'</td><td>'+val(a.newTrades?.n)+'</td><td>'+val(a.overlappingSignalsSuppressed)+'</td><td>'+ret(a.newTrades?.avgGross)+'</td><td>'+pct(a.newTrades?.win)+'</td></tr>';
}).join("");
}
async function get(url){
const r=await fetch(url+"?t="+Date.now(),{cache:"no-store"});if(!r.ok)throw Error("HTTP "+r.status);
const d=await r.json();if(!d.period||!d.models||!String(d.period.start).startsWith("2026"))throw Error("不是有效的 2026 年 G 回測檔");return d;
}
async function reload(){
txt("gStatus","載入 G 2026 回測中…");
const urls={persistence:"./data/backtest_g/g_persistence_2026.json",original:"./data/backtest_g/2026-01-01_2026-10-07.json"};
await Promise.all(Object.entries(urls).map(async([key,url])=>{
try{data[key]=await get(url);loadErrors[key]="";}
catch(e){loadErrors[key]=key+" 讀取失敗："+e.message;}
}));
render();
}
el("G").onclick=showG;
document.querySelectorAll("[data-gmodel]").forEach(b=>b.onclick=()=>{selected=b.dataset.gmodel;render();});
el("gSearch").oninput=renderTrades;el("gReload").onclick=reload;
showG();
})();