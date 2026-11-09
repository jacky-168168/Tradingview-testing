(function(){
"use strict";
const $=id=>document.getElementById(id);
const esc=x=>String(x==null?"":x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let data=null;
function pct(x){return typeof x==="number"&&Number.isFinite(x)?x.toFixed(1)+"%":"—（樣本不足）"}
function render(){
 if(!data)return;
 const asset=$("asset").value;
 $("predictions").textContent=data.predictionRecords??"—";
 $("matured").textContent=data.audit?.maturedObservationCount??"—";
 $("pending").textContent=data.audit?.pendingHorizonCount??"—";
 $("excluded").textContent=data.audit?.excludedLateHorizonCount??"—";
 const rows=(data.byAsset||[]).filter(x=>x.asset===asset);
 $("byAsset").innerHTML=rows.length?rows.map(x=>
  '<tr><td>'+esc(x.horizon)+'</td><td>'+x.n+'</td><td>'+x.wins+
  '</td><td>'+x.losses+'</td><td>'+x.flat+'</td><td>'+pct(x.winRatePct)+
  (x.winRatePct==null?'<div><small class="warn">需 ≥'+(data.minN||30)+' 筆且 ≥'+(data.minIndependentPublishingDates||20)+' 個不同發文日</small></div>':'')+
  '</td><td>'+(x.wilson95Pct?x.wilson95Pct.map(v=>v.toFixed(1)+"%").join(" ～ "):"—")+'</td></tr>').join("")
  :'<tr><td colspan="7">尚無成熟的行情觀測資料。</td></tr>';
 const rules=(data.byRule||[]).filter(x=>x.asset===asset).sort((a,b)=>b.n-a.n||a.ruleId.localeCompare(b.ruleId)).slice(0,80);
 $("byRule").innerHTML=rules.length?rules.map(x=>
  '<tr><td><code>'+esc(x.ruleId)+'</code></td><td>'+esc(x.asset)+'</td><td>'+esc(x.horizon)+
  '</td><td>'+x.wins+'／'+x.losses+'</td><td>'+pct(x.winRatePct)+'</td></tr>').join("")
  :'<tr><td colspan="5">此資產尚無符合條件且已成熟的規則觀測；不填寫虛構勝率。</td></tr>';
}
async function boot(){
 try{
  const r=await fetch("./data/news_impact/scorecard.json?t="+Date.now(),{cache:"no-store"});
  if(!r.ok)throw Error("HTTP "+r.status);
  const j=await r.json();
  if(j.schema!==1||!Array.isArray(j.byAsset)||!j.audit)throw Error("驗證紀錄格式無效");
  data=j;
  $("meta").textContent="最後更新："+(j.generatedAt||"未知")+
   " ｜版本："+(j.predictionVersionCurrent||"未知")+
   " ｜狀態："+(j.status==="insufficient_matured_signals"?"尚無足量成熟樣本":j.status||"待確認")+
   " ｜有效方向試算：已成熟後才統計，並排除過晚保存的訊號";
  render();
 }catch(e){
  $("meta").textContent="⚠ 前瞻驗證資料暫時未完成："+e.message;
  $("byAsset").innerHTML='<tr><td colspan="7">目前無已核對的勝率結果。</td></tr>';
  $("byRule").innerHTML='<tr><td colspan="5">請檢查 GitHub Actions「Global Market News Impact」。</td></tr>';
 }
}
$("asset").addEventListener("change",render);
boot();
})();