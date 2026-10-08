/* Research archive integrated into the existing Backtest/Edge page.
 * Data is archived in Pages, never fetched from expiring Actions artifacts.
 * Does NOT modify any G/D/F/A production screener logic.
 */
(()=>{"use strict";
const $=id=>document.getElementById(id),root=$("researchArchive");if(!root)return;
const BASE="./data/research_archive/",MODEL_LABELS={A:"A 原始多因子",D:"D 技術強勢",G_BROAD:"G 廣義強勢",G_3D_BREAK:"G 3D突破",G_18D_BREAK:"G 18D突破",G_DOUBLE_BREAK:"G 雙突破",G_TRIGGER:"G K線觸發",G_ENGULF:"G 吞噬K",G_PERSIST:"G 持續強勢",G_DOUBLE_PERSIST:"G 雙突破＋持續度（主模型）",H5_FRESH_BREAK:"H5 高週轉放量突破"};
const escape=v=>String(v??"—").replace(/[&<>"']/g,ch=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[ch]));
const fixed=(v,n=2)=>v==null||!Number.isFinite(Number(v))?"—":Number(v).toFixed(n);
const signed=(v,n=2)=>v==null||!Number.isFinite(Number(v))?"—":((Number(v)>0?"+":"")+fixed(v,n)+"%");
const color=v=>v==null||!Number.isFinite(Number(v))?"":Number(v)>0?"good":Number(v)<0?"bad":"";
const p=(v,n=2)=>v==null?"—":fixed(v,n)+"%";
let matrix=null,manifest=null,gCompare=null,h5=null,h1=null,h2=null,gPersist=null,tradeDetails=null;
let section="matrix",sortKey="perEligibleSignalAvgNetOnReservedPct",page=0,pageSize=100;
const status=(message,error=false)=>{const x=$("raStatus");x.textContent=message;x.className="muted "+(error?"bad":"");};
async function json(url){const r=await fetch(url,{cache:"no-store"});if(!r.ok)throw Error(url+" HTTP "+r.status);return r.json();}
const dataPath=name=>BASE+(manifest?.files?.[name]||name);
const makeLink=(name,label)=>'<a href="'+escape(BASE+name)+'" target="_blank" rel="noopener">'+escape(label)+'</a>';
function sectionTo(s){section=s;root.querySelectorAll("[data-ra-section]").forEach(x=>x.hidden=x.dataset.raSection!==s);root.querySelectorAll("[data-ra-tab]").forEach(x=>{const on=x.dataset.raTab===s;x.classList.toggle("on",on);x.setAttribute("aria-selected",on?"true":"false")});if(s==="matrix")renderMatrix();if(s==="h")renderH();if(s==="g")renderG();if(s==="trades")renderTrades();if(s==="annual")renderAnnual();}
function metricCards(rows){const all=rows.filter(x=>x.r?.filled),minCount=Math.min(...all.map(x=>x.r?.filled??0));const winner=all.slice().sort((a,b)=>(b.r?.perEligibleSignalAvgNetOnReservedPct??-1e9)-(a.r?.perEligibleSignalAvgNetOnReservedPct??-1e9))[0];return {num:rows.length,win:winner,low:minCount===Infinity?0:minCount};}
function renderMatrix(){
 if(!matrix)return;
 const model=$("raModel").value,style=$("raStyle").value,h=$("raHorizon").value;
 const rows=[];
 for(const [name,periods] of Object.entries(matrix.results||{})){
  if(model!=="all"&&model!==name)continue;
  for(const [days,methods] of Object.entries(periods||{})){
   if(h!=="all"&&h!==days)continue;
   for(const [type,r] of Object.entries(methods||{})){
    if(style!=="all"&&style!==type)continue;
    rows.push({name,days:+days,type,r});
   }
  }
 }
 const fn=x=>x?.r?.[sortKey],sorted=rows.sort((a,b)=>sortKey==="filled"?(Number(fn(b)||0)-Number(fn(a)||0)):(Number(fn(b)??-1e9)-Number(fn(a)??-1e9)));
 const top=metricCards(sorted);$("raCount").textContent=sorted.length+" 組";$("raBest").textContent=top.win?(MODEL_LABELS[top.win.name]||top.win.name)+" · "+top.win.days+"D · "+(top.win.type==="ladder"?"固定低接":"均線"):"—";$("raBestNet").textContent=top.win?signed(top.win.r.perEligibleSignalAvgNetOnReservedPct,3):"—";
 $("raMatrixBody").innerHTML=sorted.map(({name,days,type,r})=>{
 const v=r.perEligibleSignalAvgNetOnReservedPct;
 return '<tr><td><b>'+escape(MODEL_LABELS[name]||name)+'</b></td><td>'+(type==="ladder"?"五段低接":"均線加碼")+'</td><td>'+days+'D</td><td>'+fixed(r.allEligibleEvents,0)+'</td><td>'+fixed(r.filled,0)+'</td><td>'+p(r.fillPct)+'</td><td>'+p(r.takeProfitPct)+'</td><td>'+p(r.stopPct)+'</td><td class="'+color(r.avgNetOnDeployedPct)+'">'+signed(r.avgNetOnDeployedPct,3)+'</td><td class="'+color(r.avgNetOnReservedPct)+'">'+signed(r.avgNetOnReservedPct,3)+'</td><td class="'+color(v)+'"><b>'+signed(v,3)+'</b></td><td>'+fixed(r.avgTranches,2)+'</td><td class="'+color(r.earlyJanMay?.meanNetOnReservedPct)+'">'+signed(r.earlyJanMay?.meanNetOnReservedPct,3)+'</td><td class="'+color(r.laterJuneOct?.meanNetOnReservedPct)+'">'+signed(r.laterJuneOct?.meanNetOnReservedPct,3)+'</td><td><button type="button" class="btn ra-detail" data-ra-model="'+escape(name)+'" data-ra-mode="'+escape(type)+'" data-ra-days="'+days+'">逐筆</button></td></tr>';
 }).join("")||'<tr><td colspan="15">沒有符合條件的回測組合</td></tr>';
 $("raMatrixBody").querySelectorAll(".ra-detail").forEach(btn=>btn.onclick=()=>{$("raTradeModel").value=btn.dataset.raModel;$("raTradeStyle").value=btn.dataset.raMode;$("raTradeHorizon").value=btn.dataset.raDays;page=0;sectionTo("trades")});
 $("raMatrixNote").textContent="停利率＝實際成交後，平均成本＋7%先於停損觸發的事件比例；預留資金每訊號淨%＝未成交視為0%後的平均事件淨報酬；非帳戶累積報酬。不同模型與時間段的訊號數不相同，2026年已被研究使用，請勿視為樣本外勝率。";
}
function renderH(){
 if(!h5||!h1||!h2)return;
 const base=h1.comparison?.["5"]?.H||{},second=h2.summary?.["5"]||{},singleRows=[
 ["H1 高週轉原版","+7% / -4%","5D",base.trades,base.targetHitPct,base.tradeNet?.avg,"原始研究"],
 ["H2 盤整收斂突破","+7% / -3.5%","5D",second.filledTrades,second.targetHitPct,second.tradeNet?.average,"47筆；歷史研究"],
 ["H3 七類價量條件","+7% / -3.5%","5D",2,50,1.054,"樣本外僅2筆，不可信"],
 ["H4 機器學習","+7% / -3.5%","5D",204,27.45,-1.246,"2026後段驗證"],
 ["H5 單筆限價(-1%)","+7% / -3.5%","5D",42,38.10,-.035,"2026後段驗證"]
 ];
 const htr=h5.results||{};
 $("raHHistory").innerHTML=singleRows.map(x=>'<tr><td>'+escape(x[0])+'</td><td>'+escape(x[1])+'</td><td>'+x[2]+'</td><td>'+fixed(x[3],0)+'</td><td>'+p(x[4])+'</td><td class="'+color(x[5])+'">'+signed(x[5],3)+'</td><td>'+escape(x[6])+'</td></tr>').join("");
 const chunks=[];
 for(const [h,methods] of Object.entries(htr))for(const [off,r]of Object.entries(methods)){chunks.push({h:+h,off:+off,r});}
 $("raH5Table").innerHTML=chunks.sort((a,b)=>a.h-b.h||a.off-b.off).map(x=>'<tr><td>'+x.h+'D</td><td>收盤 -'+x.off+'%</td><td>'+x.r.signals+'</td><td>'+x.r.filled+'</td><td>'+p(x.r.targetHitPct)+'</td><td>'+p(x.r.stopHitPct)+'</td><td>'+fixed(x.r.avgTranches,2)+'</td><td class="'+color(x.r.avgNetOnDeployedPct)+'">'+signed(x.r.avgNetOnDeployedPct,3)+'</td><td class="'+color(x.r.avgNetOnFiveTrancheBudgetPct)+'"><b>'+signed(x.r.avgNetOnFiveTrancheBudgetPct,3)+'</b></td></tr>').join("");
}
async function renderG(){
 if(!gCompare){try{gCompare=await json(dataPath("gCompare"));}catch(e){$("raGStatus").textContent="G 加碼回測讀取失敗："+e.message;return}}
 $("raGStatus").textContent="G_DOUBLE_PERSIST（原網站 G 主模型）｜2026 年｜已含同股票重複訊號去重";
 const list=[];for(const [h,models]of Object.entries(gCompare.statistics||{}))for(const [style,r]of Object.entries(models))list.push({h,style,r});
 $("raGCompare").innerHTML=list.map(({h,style,r})=>'<tr><td>'+h+'D</td><td>'+(style==="ma"?"MA5/10/20/60":"五段向下")+'</td><td>'+r.filled+'</td><td>'+p(r.takeProfitPct)+'</td><td>'+p(r.stopPct)+'</td><td>'+fixed(r.avgTranches,2)+'</td><td class="'+color(r.avgNetOnReservedPct)+'">'+signed(r.avgNetOnReservedPct,3)+'</td><td>'+r.duplicateSuppressed+'</td></tr>').join("");
 if(!gPersist){try{gPersist=await json("./data/backtest_g/g_persistence_2026.json")}catch(e){$("raGRepeat").innerHTML='<tr><td colspan="6">'+escape(e.message)+'</td></tr>';return}}
 const tuples=[];for(const [m,d]of Object.entries(gPersist.models||{}))for(const [h,groups]of Object.entries(d.repeatAudit?.pocketSegments||{}))for(const [group,s]of Object.entries(groups))tuples.push({m,h,group,s});
 $("raGRepeat").innerHTML=tuples.map(({m,h,group,s})=>'<tr><td>'+escape(MODEL_LABELS[m]||m)+'</td><td>'+h+'D</td><td>'+(group==="fresh"?"前10日零次":group==="emerging_1_3"?"前10日 1～3次":"前10日 ≥4次")+'</td><td>'+s.n+'</td><td class="'+color(s.avgGross)+'">'+signed(s.avgGross)+'</td><td>'+p(s.win,1)+'</td></tr>').join("");
}
const tradeLabel=t=>{const z=t?.fills||[];return z.map(q=>q.type+"@"+fixed(q.price)).join("、")||"—"};
async function renderTrades(){
 if(!matrix)return;
 if(!tradeDetails){
  $("raTradeStatus").textContent="第一次查看逐筆明細，載入完整交易紀錄中…";
  try{tradeDetails=await json(dataPath("matrixTrades"));}catch(e){$("raTradeStatus").textContent="讀取失敗："+e.message;return}
 }
 const model=$("raTradeModel").value,h=$("raTradeHorizon").value,mode=$("raTradeStyle").value,q=$("raTradeSearch").value.trim().toLowerCase();
 const all=tradeDetails?.[model]?.[h]?.[mode]||[];
 const rows=all.filter(t=>!q||((t.code||"")+" "+(t.name||"")).toLowerCase().includes(q));
 const max=Math.max(0,Math.ceil(rows.length/pageSize)-1);page=Math.min(page,max);const part=rows.slice(page*pageSize,(page+1)*pageSize);
 $("raTradeStatus").textContent=(MODEL_LABELS[model]||model)+" · "+h+"D · "+(mode==="ladder"?"固定低接":"均線加碼")+"｜共 "+rows.length+" 筆事件（含未成交）；第 "+(page+1)+"/"+(max+1)+" 頁";
 $("raTradeBody").innerHTML=part.map(t=>'<tr><td>'+escape(t.date)+'</td><td><b>'+escape(t.code)+" "+escape(t.name)+'</b></td><td>'+fixed(t.rank,0)+'</td><td>'+escape(t.status)+'</td><td>'+escape(t.firstEntryDate)+'</td><td>'+escape(t.exitDate)+'</td><td>'+escape(t.reason)+'</td><td>'+fixed(t.tranches,0)+'</td><td>'+fixed(t.avgCost)+'</td><td class="'+color(t.netOnDeployedPct)+'">'+signed(t.netOnDeployedPct,3)+'</td><td class="'+color(t.netOnReservedPct)+'">'+signed(t.netOnReservedPct,3)+'</td><td>'+escape(tradeLabel(t))+'</td></tr>').join("")||'<tr><td colspan="12">本頁沒有相符的交易紀錄</td></tr>';
 $("raPrev").disabled=page===0;$("raNext").disabled=page>=max;
}
function renderAnnual(){
 $("raAnnualNote").textContent="既有 A／D／F／G 長期回測原本就可在本頁下方的回測分頁檢視，年度資料檔仍保留在 GitHub Pages。新增的研究檔是凍結歷史結果，不會冒充每天最新選股。";
}
async function start(){
 status("正在載入已保存的回測資料…");
 try{
  manifest=await json(BASE+"index.json");
  matrix=await json(dataPath("matrix"));
  if(!matrix.results||Object.keys(matrix.results).length!==11||!matrix.results.G_DOUBLE_PERSIST)throw Error("研究回測 JSON 結構不符");
  const sumCells=Object.values(matrix.results).reduce((n,m)=>n+Object.values(m).reduce((k,x)=>k+Object.keys(x).length,0),0);
  if(sumCells!==66)throw Error("預期66組，實際"+sumCells);
  const models=Object.keys(matrix.results);
  const sel=$("raModel"),ts=$("raTradeModel");
  for(const name of models){for(const node of [sel,ts]){const opt=document.createElement("option");opt.value=name;opt.textContent=MODEL_LABELS[name]||name;node.appendChild(opt)}}
  ts.value="H5_FRESH_BREAK";
  const group=await Promise.allSettled([json(dataPath("h5")),json(dataPath("h1")),json(dataPath("h2"))]);
  [h5,h1,h2]=group.map(z=>z.status==="fulfilled"?z.value:null);
  const issue=group.filter(z=>z.status==="rejected");$("raPeriod").textContent=manifest.period.start+"～"+manifest.period.end+"｜"+manifest.comparisonCells+"組完整研究";
  status("已載入 "+sumCells+" 組回測結果（11種選股 × 2種加碼法 × 3個持有期限）"+(issue.length?"｜另有部分舊研究檔載入失敗":""));
  renderMatrix();
 }catch(e){status("研究資料無法載入："+e.message+"。請確認 GitHub Pages 已部署最新的 JSON 檔。",true)}
}
root.querySelectorAll("[data-ra-tab]").forEach(b=>b.onclick=()=>sectionTo(b.dataset.raTab));
for(const id of ["raModel","raStyle","raHorizon","raSort"])$(id).addEventListener("change",()=>{if(id==="raSort")sortKey=$("raSort").value;renderMatrix()});
for(const id of ["raTradeModel","raTradeStyle","raTradeHorizon","raTradeSearch"])$(id).addEventListener(id==="raTradeSearch"?"input":"change",()=>{page=0;renderTrades()});
$("raPrev").onclick=()=>{page=Math.max(0,page-1);renderTrades()};
$("raNext").onclick=()=>{page++;renderTrades()};
$("raReload").onclick=()=>{matrix=null;tradeDetails=null;gCompare=null;gPersist=null;start()};
if(location.hash==="#researchArchive")root.scrollIntoView({block:"start",behavior:"auto"});
start();
})();
