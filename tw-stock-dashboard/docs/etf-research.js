/* Archived and independently verified ETF research (read-only; not a live signal engine). */
(function(){
"use strict";
const by=id=>document.getElementById(id),root=by("etfHistoryView"),tab=by("ETF_HISTORY");
if(!root||!tab)return;
const rootPath="./data/research/etf_history/";
const esc=v=>String(v==null?"":v).replace(/[&<>"']/g,k=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[k]));
const num=(x,n=2)=>x==null||!Number.isFinite(Number(x))?"—":Number(x).toLocaleString("zh-TW",{minimumFractionDigits:n,maximumFractionDigits:n});
const cls=x=>Number(x)>=0?"etf-green":"etf-red";
const p=x=>'<span class="'+cls(x)+'">'+num(x,2)+'%</span>';
const twd=x=>num(Number(x)/10000,2)+" 萬";
let index=null,study=null,selected=null,filter="",grid=null,gridPage=0,loadPromise=null,curveRequest=0,curves={};
async function json(path){const res=await fetch(path+"?v=20261009sma5exit7",{cache:"no-cache"});if(!res.ok)throw Error("HTTP "+res.status+"："+path);return await res.json();}
function show(){
  ["legacyView","gView","executionResearchView"].forEach(id=>{const e=by(id);if(e)e.style.display="none";});
  root.style.display="block";
  document.querySelectorAll("#modelTabs button").forEach(b=>b.classList.toggle("on",b===tab));
  if(index)renderStudy();else load();
}
tab.addEventListener("click",show);
if(new URLSearchParams(window.location.search).has("study"))show();
["G","D","F2","F","A","RESEARCH"].forEach(id=>by(id)?.addEventListener("click",()=>{root.style.display="none";}));
async function load(){
  if(loadPromise)return loadPromise;
  by("etfStatus").textContent="正在載入永久存檔…";
  loadPromise=(async()=>{
    try{
      index=await json(rootPath+"index.json");
      if(!index.studies?.length)throw Error("ETF 研究資料尚未建置");
      by("etfStudy").innerHTML=index.studies.map(x=>'<option value="'+esc(x.id)+'">'+esc(x.title)+'</option>').join("");
      by("etfStudy").value=study?.id||new URLSearchParams(window.location.search).get("study")||"00675_2018";
      by("etfStatus").textContent=index.studies.length+" 組研究存檔，"+index.studies.reduce((a,s)=>a+s.models.length,0)+" 組已驗證策略；每份回測都保留年度報酬和逐日曲線。";
      by("etfAssumptions").textContent=index.assumptions+" "+index.currencyPolicy+" 此為歷史模擬，不代表未來可實現報酬。";
      by("etfAllocation").textContent=index.allocationBacktestStatus;
      renderStudy();
    }catch(err){by("etfStatus").textContent="ETF 存檔載入失敗："+err.message+"。請按重新整理再試。";}
    finally{loadPromise=null}
  })();
  return loadPromise;
}
function renderStudy(){
  if(!index)return;
  study=index.studies.find(x=>x.id===by("etfStudy").value)||index.studies[0];
  by("etfDescription").textContent=study.description;
  by("etfStudyPeriod").textContent=study.period.join(" ～ ")+"｜"+num(study.sessions,0)+" 個交易日｜"+study.models.length+" 套完整驗證策略";
  by("etfQuality").textContent=study.dataQuality||"所有研究皆已封存，不能視為未來行情預測。";
  by("etfWarnings").textContent=study.warnings.slice(0,3).join("　｜　");
  by("etfSources").innerHTML='<a href="'+esc(study.sourceSummary)+'" target="_blank" rel="noopener">研究原始統計 ↗</a>'+
    '<a href="'+esc(study.sourceExecution)+'" target="_blank" rel="noopener">回測驗證紀錄 ↗</a>'+
    (study.extraSource?'<a href="'+esc(study.extraSource)+'" target="_blank" rel="noopener">參數穩定性測試 ↗</a>':"");
  by("etfGridPanel").style.display=study.trainingGrid?"block":"none";
  by("etfGridTable").innerHTML="";
  const isRiskStudy=study.id==="00675_risk_v2";
  by("etfGridTitle").textContent=isRiskStudy?"🔎 00675L｜270 組進出場參數穩健性測試":"🔎 00675L｜4,320 組均線參數訓練期存檔";
  by("etfGridLoad").textContent=isRiskStudy?"載入 270 組完整分段績效":"載入 4,320 組原始訓練結果";
  by("etfGridHead").innerHTML=isRiskStudy?
   ["參數組合 ID","SMA 週期","出場幅度","買回幅度","出場確認","急跌保護","2018–23 訓練報酬","訓練 MDD","2024–25 驗證報酬","2026 回顧報酬"].map(x=>"<th>"+esc(x)+"</th>").join(""):
   ["參數組合 ID","訊號來源","均線週期","出場幅度","買回幅度","確認天數","訓練段收益","訓練段 MDD","賣出次數","訓練評分"].map(x=>"<th>"+esc(x)+"</th>").join("");
  by("etfGridMeta").textContent=study.trainingGrid?(isRiskStudy?"270 組參數都包含2018–23訓練、2024–25驗證及2026回顧資料。2026曾經在其他研究使用，不能視為全新樣本。":"4,320 組僅包含2020～2023訓練期結果；按「載入訓練結果」後可依名稱搜尋。"):"";
  if(study.trainingGrid){grid=null;gridPage=0;}
  filter="";
  by("etfFilter").value="";
  selected=study.models.find(x=>x.id==="SMA10_index_original_2_1"||x.id==="SMA_twii_N10_OUT2_RE1_C3"||x.id==="BUY_HOLD_QLD"||x.id==="QQQ__BUY_HOLD")||study.models[0];
  renderModels();select(selected.id);
}
function renderModels(){
  if(!study)return;
  const rows=study.models.filter(x=>(x.name+" "+x.id+" "+x.group).toLowerCase().includes(filter.toLowerCase()))
    .sort((a,b)=>b.returnPct-a.returnPct);
  by("etfModelCount").textContent="符合 "+rows.length+"／"+study.models.length+" 套策略；點選任一列可查看年度績效、曲線和逐筆交易。";
  by("etfModelRows").innerHTML=rows.map(x=>
    '<tr data-etf-model="'+esc(x.id)+'"'+(selected?.id===x.id?' class="etf-active"':'')+'>'+
    '<td><b>'+esc(x.name)+'</b></td><td>'+esc(x.group||"—")+'</td><td>'+p(x.returnPct)+'</td>'+
    '<td>'+twd(x.endTWD)+'</td><td>'+p(x.mddPct)+'</td><td>'+num(x.sells,0)+'／'+num(x.rebuys,0)+'</td>'+
    '<td>'+num(x.cashDays,0)+'</td></tr>').join("")||'<tr><td colspan="7" class="etf-empty">沒有符合搜尋條件的策略</td></tr>';
}
function stat(name,value){return '<div class="etf-stat"><span>'+esc(name)+'</span><strong>'+value+'</strong></div>';}
function select(id){
  const x=study?.models.find(t=>t.id===id);
  if(!x)return;
  selected=x;
  renderModels();
  by("etfSelectedName").textContent=x.name+"｜"+study.title;
  by("etfSelectedNote").textContent=x.notes||study.description;
  by("etfStats").innerHTML=stat("期末資產（台幣）",twd(x.endTWD))+stat("累積淨報酬",p(x.returnPct))+
   stat("最大回撤（台幣）",p(x.mddPct))+stat("風險出場／買回",num(x.sells,0)+"／"+num(x.rebuys,0));
  by("etfAnnualRows").innerHTML=x.annual.map(y=>'<tr><td>'+esc(y.year)+'</td>'+
    '<td>'+p(y.pct)+'</td><td>'+twd(y.wealthTWD)+'</td>'+
    '<td>'+(y.usdPct==null?"—":p(y.usdPct))+'</td></tr>').join("");
  by("etfCurveStatus").textContent="載入 "+num(x.sessions,0)+" 個交易日的完整帳戶曲線…";
  by("etfCurve").innerHTML="";
  by("etfTradeRows").innerHTML='<tr><td colspan="7">正在讀取逐筆交易…</td></tr>';
  by("etfTradeMeta").textContent="";
  by("etfCurveDownload").href=rootPath+x.curve;
  showCurve(x,++curveRequest);
}
async function showCurve(x,token){
  try{
    const raw=curves[x.curve]||(curves[x.curve]=await json(rootPath+x.curve));
    if(token!==curveRequest||!study?.models.find(z=>z.id===x.id)||selected?.id!==x.id)return;
    if(raw.id!==x.id||!Array.isArray(raw.points)||raw.points.length!==x.sessions)throw Error("曲線與策略統計不一致");
    const points=raw.points,usd=raw.currency==="USD",currency=usd?"美元":"新臺幣",vals=points.map(z=>Number(z[1]));
    const w=970,h=275,left=54,right=16,top=20,bottom=31;
    const lo=Math.min(...vals),hi=Math.max(...vals),span=Math.max(.00001,hi-lo);
    const y=v=>top+(hi-v)/span*(h-top-bottom),px=i=>left+i*(w-left-right)/(points.length-1);
    const poly=points.map((z,i)=>px(i).toFixed(2)+","+y(vals[i]).toFixed(2)).join(" ");
    const dates=[points[0][0],points[Math.floor(points.length/2)][0],points.at(-1)[0]];
    const lines=[0,1,2,3,4].map(j=>{const value=lo+(hi-lo)*j/4,yy=y(value);return '<line x1="'+left+'" x2="'+(w-right)+'" y1="'+yy+'" y2="'+yy+'" stroke="#e2e8f0"/><text x="'+(left-6)+'" y="'+(yy+4)+'" text-anchor="end" fill="#64748b" font-size="11">'+esc(num(value/1000,0))+'k</text>'}).join("");
    const texts=[0,1,2].map((j,i)=>{const v=[0,Math.floor((points.length-1)/2),points.length-1][i];return '<text x="'+px(v)+'" y="'+(h-8)+'" text-anchor="'+(i===0?"start":i===1?"middle":"end")+'" fill="#64748b" font-size="12">'+esc(dates[i])+'</text>'}).join("");
    by("etfCurve").innerHTML='<svg class="etf-curve" viewBox="0 0 '+w+' '+h+'" role="img" aria-label="'+esc(x.name)+"｜"+esc(currency)+'逐日複利帳戶曲線"><g>'+lines+
      '<polyline fill="none" stroke="#2563eb" stroke-width="2.6" vector-effect="non-scaling-stroke" points="'+poly+'"/>'+texts+'</g></svg>';
    by("etfCurveStatus").textContent=points.length+" 個交易日｜曲線為"+currency+"帳戶淨值；"+(usd?"美股的期末總資產與年度表另外以各日匯率換算台幣。":"每個月底不是重置100萬，而是本金與獲利持續複投。");
    const orders=raw.trades||[];
    by("etfTradeMeta").textContent="完整模擬訂單 "+orders.length+" 筆。最後一筆「period_end」為回測截止日假設平倉，不一定是策略賣出訊號。";
    by("etfTradeRows").innerHTML=orders.map(t=>'<tr>'+
      '<td>'+esc(t[0])+'</td><td class="'+(t[1]==="BUY"?"etf-green":"etf-red")+'">'+esc(t[1])+'</td>'+
      '<td>'+esc(t[2])+'</td><td>'+num(t[3],0)+'</td><td>'+num(t[4],3)+'</td><td>'+num(t[5],2)+'</td><td>'+num(t[6],2)+'</td></tr>').join("")||'<tr><td colspan="7">買進持有策略只有期初買入與回測期末平倉</td></tr>';
  }catch(err){if(token!==curveRequest)return;by("etfCurveStatus").textContent="每日資料載入失敗："+err.message;by("etfTradeRows").innerHTML='<tr><td colspan="7">無法讀取交易紀錄，請檢查原始存檔。</td></tr>';}
}
by("etfModelRows").addEventListener("click",event=>{const row=event.target.closest("tr[data-etf-model]");if(row)select(row.dataset.etfModel);});
by("etfFilter").addEventListener("input",e=>{filter=e.target.value;renderModels();});
by("etfStudy").addEventListener("change",renderStudy);
by("etfReload").addEventListener("click",()=>{index=null;curves={};grid=null;load();});
async function loadGrid(){
  if(!study?.trainingGrid)return;
  const risk=study.id==="00675_risk_v2",expected=risk?270:4320;
  by("etfGridMeta").textContent="正在載入全部 "+expected+" 組回測資料…";
  try{
    grid=grid||await json(rootPath+study.trainingGrid);
    if(!Array.isArray(grid.rows)||grid.rows.length!==expected)throw Error("參數資料不完整");
    by("etfGridMeta").textContent=risk?"270 組完整分段績效；排名按2018–23訓練分數，不利用2024–26結果選參數。":grid.note;
    gridPage=0;renderGrid();
  }catch(err){by("etfGridMeta").textContent="載入參數結果失敗："+err.message;}
}
function renderGrid(){
  if(!grid)return;
  const risk=study?.id==="00675_risk_v2";
  const q=by("etfGridQuery").value.toLowerCase().trim();
  const xs=grid.rows.filter(x=>!q||String(risk?x.id:x[0]).toLowerCase().includes(q))
    .sort((a,b)=>risk?Number(b.trainScore)-Number(a.trainScore):Number(b[10])-Number(a[10]));
  const pages=Math.max(1,Math.ceil(xs.length/40));gridPage=Math.min(Math.max(0,gridPage),pages-1);
  const list=xs.slice(gridPage*40,(gridPage+1)*40);
  by("etfGridCount").textContent=(risk?"2018–26完整參數":"2020–23訓練期")+" "+xs.length+"／"+grid.rows.length+" 組，第 "+(gridPage+1)+"/"+pages+" 頁";
  by("etfGridTable").innerHTML=(risk?
    list.map(x=>'<tr><td>'+esc(x.id)+'</td><td>'+num(x.n,0)+'D</td><td>'+num(x.exitPct,1)+'%</td><td>'+num(x.entryPct,1)+'%</td>'+
      '<td>'+num(x.exitDays,0)+'日</td><td>'+num(x.panicPct,1)+'%</td><td>'+p(x.train.returnPct)+'</td><td>'+p(x.train.mddPct)+'</td>'+
      '<td>'+p(x.validation2024_2025.returnPct)+'</td><td>'+p(x.audit2026.returnPct)+'</td></tr>'):
    list.map(x=>'<tr><td>'+esc(x[0])+'</td><td>'+esc(x[2])+'</td><td>'+x[3]+'D</td>'+
      '<td>'+x[4]+'%</td><td>'+x[5]+'%</td><td>'+x[6]+'</td><td>'+p(x[7])+'</td><td>'+p(x[8])+'</td><td>'+num(x[9],0)+'</td><td>'+num(x[10],2)+'</td></tr>')).join("")||'<tr><td colspan="10">無符合資料</td></tr>';
  by("etfGridPrev").disabled=gridPage===0;by("etfGridNext").disabled=gridPage>=pages-1;
}
by("etfGridLoad").addEventListener("click",loadGrid);
by("etfGridQuery").addEventListener("input",()=>{gridPage=0;renderGrid();});
by("etfGridPrev").addEventListener("click",()=>{gridPage--;renderGrid();});
by("etfGridNext").addEventListener("click",()=>{gridPage++;renderGrid();});
})();
