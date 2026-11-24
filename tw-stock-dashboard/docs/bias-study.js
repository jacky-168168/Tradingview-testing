// BIAS10/20 轉折研究：純歷史事件研究，不含下單與即時訊號。
(function(){
"use strict";
const el=id=>document.getElementById(id),root=el("biasStudyView"),tab=el("BIAS_STUDY");
if(!root||!tab)return;
let data=null,selected=null,promise=null;
const esc=x=>String(x==null?"":x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const v=(x,d=2)=>x==null||!Number.isFinite(Number(x))?"—":Number(x).toFixed(d);
const pct=(x,d=2)=>x==null?"—":v(x,d)+"%";
const signed=(x,d=2)=>x==null?"—":(Number(x)>0?"+":"")+pct(x,d);
const score=x=>x==null?"":x>=0?"good":"bad";
function show(){
  ["legacyView","gView","executionResearchView","etfHistoryView"].forEach(id=>{if(el(id))el(id).style.display="none";});
  root.style.display="block";
  document.querySelectorAll("#modelTabs button").forEach(b=>b.classList.toggle("on",b===tab));
  if(!data)load();else render();
}
tab.addEventListener("click",show);
document.querySelectorAll("#modelTabs button").forEach(b=>{if(b!==tab)b.addEventListener("click",()=>{root.style.display="none";});});
async function load(){
  if(promise)return promise;
  el("biasStudyStatus").textContent="讀取長期 BIAS 事件研究資料中…";
  promise=(async()=>{
    try{
      const r=await fetch("./data/research/bias_turning_points/latest.json?v=20261124a",{cache:"no-cache"});
      if(!r.ok)throw Error("HTTP "+r.status);
      const j=await r.json();
      if(!Array.isArray(j.tests)||!j.coverage)throw Error("研究資料格式錯誤");
      data=j;render();
    }catch(e){el("biasStudyStatus").textContent="研究資料載入失敗："+e.message;}
    finally{promise=null;}
  })();
  return promise;
}
function render(){
 if(!data)return;
 const c=data.coverage,b=data.baseline.indexCloseForward;
 el("biasStudyStatus").textContent="資料 "+c.from+"～"+c.to+"｜"+c.distinctDailyBars.toLocaleString("zh-TW")+" 根日 K｜研究版本 "+data.version+"｜未納入2026/10/09～11/23";
 el("biasStudyBaseline").textContent="全體日線基準：後5日 "+signed(b.d5.meanPct)+" / 上漲 "+pct(b.d5.winPct,1)+"｜後20日 "+signed(b.d20.meanPct)+" / 上漲 "+pct(b.d20.winPct,1)+"｜後60日 "+signed(b.d60.meanPct)+"。";
 let p=Number(el("biasStudyPeriod").value),type=el("biasStudySide").value;
 let rows=data.tests.filter(t=>t.period===p&&(type==="all"||(type==="low"?t.threshold<0:t.threshold>0)));
 el("biasStudyRows").innerHTML=rows.map(t=>{
  const r=t.signalCloseForward,c=t.confirmation;
  return '<tr data-bias-period="'+t.period+'" data-bias-threshold="'+t.threshold+'" style="cursor:pointer"'+(selected&&selected.period===t.period&&selected.threshold===t.threshold?' class="bias-picked"':'')+'><td><b>BIAS'+t.period+' '+(t.threshold<0?"≤ ":"≥ ")+pct(t.threshold,0)+'</b></td><td>'+t.sampleCount+'</td><td class="'+score(r.d5.meanPct)+'">'+signed(r.d5.meanPct)+'</td><td class="'+score(r.d20.meanPct)+'">'+signed(r.d20.meanPct)+'</td><td>'+pct(r.d20.winPct,1)+'</td><td class="'+score(r.d20.worstPct)+'">'+signed(r.d20.worstPct)+'</td><td class="'+score(r.d60.meanPct)+'">'+signed(r.d60.meanPct)+'</td><td>'+(c?c.confirmedCount+"/"+t.sampleCount:"—")+'</td><td>'+(c?c.meanLagTradingDays+"日":"—")+'</td><td class="'+(c?score(c.nextCloseForward.d20.meanPct):"")+'">'+(c?signed(c.nextCloseForward.d20.meanPct):"—")+'</td><td>'+(c?pct(c.nextCloseForward.d20.winPct,1):"—")+'</td></tr>';
 }).join("")||'<tr><td colspan="11">沒有符合條件的研究資料</td></tr>';
 const still=rows.find(x=>selected&&x.period===selected.period&&x.threshold===selected.threshold);
 if(!still)selected=rows.find(x=>x.threshold===-10)||rows[0]||null;
 const chosen=selected;
 el("biasStudyRows").querySelectorAll("tr[data-bias-period]").forEach(tr=>{tr.classList.toggle("bias-picked",chosen&&Number(tr.dataset.biasPeriod)===chosen.period&&Number(tr.dataset.biasThreshold)===chosen.threshold);});
 showDetail(chosen);
}
function showDetail(t){
 if(!t){el("biasStudyEvents").innerHTML="<tr><td colspan='10'>尚無事件</td></tr>";return;}
 el("biasStudySelected").textContent="BIAS"+t.period+" "+(t.threshold<0?"≤ ":"≥ ")+pct(t.threshold,0)+"｜共 "+t.sampleCount+" 次事件（點選上方其他條件可切換）";
 let eventRows=t.events||[];
 el("biasStudyEvents").innerHTML=eventRows.map(e=>{
  const r=e.forward||{},c=e.confirmation;
  return '<tr><td>'+esc(e.date)+'</td><td>'+v(e.close,2)+'</td><td>'+pct(e.bias10Pct)+'</td><td>'+pct(e.bias20Pct)+'</td><td class="'+score(r.d5)+'">'+signed(r.d5)+'</td><td class="'+score(r.d20)+'">'+signed(r.d20)+'</td><td class="'+score(r.d60)+'">'+signed(r.d60)+'</td><td>'+(c?esc(c.date):"未確認")+'</td><td>'+(c?v(c.lagTradingDays,0):"—")+'</td><td class="'+(c?score(c.nextCloseForward?.d20):"")+'">'+(c?signed(c.nextCloseForward?.d20):"—")+'</td></tr>';
 }).join("")||'<tr><td colspan="10">此條件沒有符合的歷史事件</td></tr>';
}
el("biasStudyRows").addEventListener("click",e=>{const tr=e.target.closest("tr[data-bias-period]");if(!tr||!data)return;selected=data.tests.find(t=>t.period===+tr.dataset.biasPeriod&&t.threshold===+tr.dataset.biasThreshold)||null;render();});
el("biasStudyPeriod").addEventListener("change",()=>{selected=null;render();});
el("biasStudySide").addEventListener("change",()=>{selected=null;render();});
el("biasStudyRefresh").addEventListener("click",()=>{data=null;load();});
if(!el("modelTabs")||(typeof location!=="undefined"&&location.hash==="#bias-study"))show();
})();
