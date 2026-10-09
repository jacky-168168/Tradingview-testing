// 2026 model × execution history. Read-only: this code never produces orders.
(function(){
"use strict";
const by=id=>document.getElementById(id),root=by("executionResearchView");
if(!root)return;
const rootpath="./data/research/model_execution_2026/";
const names={A:"A 原始多因子",D:"D 技術強勢",F:"F 固定大盤",F2:"F2 動態大盤",G_BASE:"G_BASE 原始強勢",G_RELAXED:"G_RELAXED 寬鬆版",G_STRICT:"G_STRICT 嚴格強勢",G_BROAD:"G_BROAD 廣泛強勢",G_CANDLE:"G_CANDLE 3D/18D",G_TRIGGER:"G_TRIGGER K棒觸發",G_3D_BREAK:"G_3D_BREAK 3D突破",G_18D_BREAK:"G_18D_BREAK 18D突破",G_DOUBLE_BREAK:"G_DOUBLE_BREAK 雙突破",G_ENGULF:"G_ENGULF 吞噬形態",G_PERSIST:"G_PERSIST 持續強勢",G_DOUBLE_PERSIST:"G_DOUBLE_PERSIST 主模型",H5_FRESH_BREAK:"H5 高週轉突破"};
const archiveLinks={
 g:'<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/actions/runs/37833390271">G 原始完整逐筆資料及執行紀錄 ↗</a>',
 h:'<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/actions/runs/37801819940">H5 五段加碼原始執行紀錄 ↗</a>',
 risk:'<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/g_strict_stop_diagnostic_2026.json">大盤位階 × 停損原始研究 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/actions/runs/37839334095">GitHub 實際研究執行紀錄 ↗</a>',
 timing:'<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/g_strict_ma20_entry_2026.json">下載 G_STRICT MA20 進場比較 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/g_strict_ma20_entry_trades_2026.json">下載全部逐筆交易 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/actions/runs/37848392034">成功回測 GitHub Actions ↗</a>',
 reinvest:'<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/00675l_reinvestment_summary.json">00675L 三種資金配置統計 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/00675l_reinvestment_trades_equity.json">完整逐筆交易與現金權益曲線 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/actions/runs/37865188346">研究與驗證執行紀錄 ↗</a>',
 extended00675:'<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/00675l_extended_2020_2026_summary.json">2020～2026 完整資金與年度風險統計 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/00675l_extended_2020_2026_daily_equity.json">全部逐日現金曲線與交易紀錄 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/actions/runs/37870828816">GitHub 2020～2026 驗算紀錄 ↗</a>',
 trend00675:'<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/00675l_regime_capture_summary.json">1091組趨勢輪動研究 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/00675l_regime_capture_stress.json">滑價與延後成交壓測 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/00675l_trend_capture_summary.json">925組交叉驗算 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/actions/runs/37867769770">驗證流程 ↗</a>',
 tp:'<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/g_tp_sl_2026_summary.json">108組停利／停損研究統計 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/g_tp_sl_2026_equity_curves.json">108組逐日帳戶權益曲線 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/actions/runs/37856646898">回測及驗證執行紀錄 ↗</a>',
 capacity:'<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/g_capital_2026_summary.json">全部 36 組 2026 資金限制回測 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/g_capital_2026_equity_curves.json">下載每日資金曲線 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/actions/runs/37850943950">原始 GitHub 研究執行紀錄 ↗</a>',
 legacy:'<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/h1_2026.json">H1 歷史 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/h2_2026.json">H2 歷史 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/blob/research/h-v5-limit-pullback-2026/tw-stock-dashboard/H_2026_research_consolidated_H2_H5.md">H2～H5 原始研究報告 ↗</a>'};
const e=x=>String(x==null?"":x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const n=(v,d=2)=>v==null||!Number.isFinite(Number(v))?"—":Number(v).toFixed(d);
const pct=(v,d=2)=>v==null?"—":n(v,d)+"%";
const clr=v=>v==null?"":Number(v)>=0?"research-positive":"research-negative";
const perf=v=>'<span class="'+clr(v)+'">'+pct(v,3)+'</span>';
const type=x=>x==="ma"?"B 均線觸價":"A 固定下跌";
const full=x=>names[x]||x;
let main=null,h5=null,g=null,risk=null,timing=null,timingTrades=null,timingMode="",timingGate="",timingPage=0,capacity=null,capacityCurves=null,capacitySelected=null,capacityToken=0,tpSensi=null,tpCurves=null,tpToken=0,reinvest=null,reinvestTrades=null,reinvestToken=0,regime00675=null,regime00675Stress=null,regime00675Cross=null,regime00675Equity=null,regime00675Token=0,extended00675=null,extended00675Equity=null,extended00675Token=0,loading=null,current=null,activeArchive="g",modelTrades=null,tradeIdentity="",run=0,tradePage=0;
async function get(path){const u=path+"?v=20261009g",r=await fetch(u,{cache:"no-cache"});if(!r.ok)throw Error("資料 HTTP "+r.status+"："+path);return r.json();}
function visible(){by("legacyView").style.display="none";by("gView").style.display="none";root.style.display="block";document.querySelectorAll("#modelTabs button").forEach(b=>b.classList.toggle("on",b.id==="RESEARCH"));if(main)render();else load();}
function close(){root.style.display="none";}
for(const id of ["G","D","F","F2","A"])by(id)?.addEventListener("click",close);
by("RESEARCH").addEventListener("click",visible);
async function load(){
 if(loading)return loading;
 by("researchMeta").textContent="正在讀取 2026 研究檔案…";
 loading=(async()=>{
  try{
   main=await get(rootpath+"selector_execution_2026_summary.json");
   if(!main.allModelStatistics||!main.period)throw Error("研究檔案不完整");
   const sel=by("researchModel");
   sel.innerHTML='<option value="all">全部 '+Object.keys(main.allModelStatistics).length+' 種模型</option>'+Object.keys(main.allModelStatistics).map(z=>'<option value="'+e(z)+'">'+e(full(z))+'</option>').join("");
   by("researchMeta").textContent=main.period.start+" ～ "+main.period.end+"｜"+Object.keys(main.allModelStatistics).length+" 個模型 × 2 種進場 × 3 週期｜資料產出 "+(main.generatedAt||"—");
   const [gResult,hResult,riskResult,timingResult,capacityResult,tpSensiResult,reinvestResult,regimeResult,regimeStressResult,regimeCrossResult,extendedResult]=await Promise.allSettled([get(rootpath+"g_ladder_vs_ma_2026.json"),get(rootpath+"h5_ladder_2026.json"),get(rootpath+"g_strict_stop_diagnostic_2026.json"),get(rootpath+"g_strict_ma20_entry_2026.json"),get(rootpath+"g_capital_2026_summary.json"),get(rootpath+"g_tp_sl_2026_summary.json"),get(rootpath+"00675l_reinvestment_summary.json"),get(rootpath+"00675l_regime_capture_summary.json"),get(rootpath+"00675l_regime_capture_stress.json"),get(rootpath+"00675l_trend_capture_summary.json"),get(rootpath+"00675l_extended_2020_2026_summary.json")]);
   g=gResult.status==="fulfilled"?gResult.value:null;h5=hResult.status==="fulfilled"?hResult.value:null;risk=riskResult.status==="fulfilled"?riskResult.value:null;timing=timingResult.status==="fulfilled"?timingResult.value:null;capacity=capacityResult.status==="fulfilled"?capacityResult.value:null;tpSensi=tpSensiResult.status==="fulfilled"?tpSensiResult.value:null;reinvest=reinvestResult.status==="fulfilled"?reinvestResult.value:null;regime00675=regimeResult.status==="fulfilled"?regimeResult.value:null;regime00675Stress=regimeStressResult.status==="fulfilled"?regimeStressResult.value:null;regime00675Cross=regimeCrossResult.status==="fulfilled"?regimeCrossResult.value:null;extended00675=extendedResult.status==="fulfilled"?extendedResult.value:null;
   by("researchWarnings").textContent=(main.warnings||[]).slice(0,4).join(" ｜ ");
   render();
  }catch(err){by("researchMeta").textContent="載入失敗："+err.message;by("researchRankRows").innerHTML='<tr><td colspan="12">研究資料未發佈或網路有問題。請稍後重新整理。</td></tr>'}
  finally{loading=null}
 })();
 return loading;
}
function rows(){
 const hold=by("researchHold").value,method=by("researchMethod").value,model=by("researchModel").value,min=Math.max(0,Number(by("researchMinFills").value)||0),sort=by("researchSort").value;
 const out=[];
 for(const [name,periods]of Object.entries(main?.allModelStatistics||{})){
  if(model!=="all"&&name!==model)continue;
  for(const [h,methods]of Object.entries(periods)){
   if(hold!=="all"&&h!==hold)continue;
   for(const [m,st]of Object.entries(methods)){
    if(method!=="all"&&m!==method||!st||st.filled<min)continue;
    out.push({name,h,m,st});
   }
  }
 }
 const val=r=>sort==="hit"?r.st.takeProfitPct:sort==="stop"?-r.st.stopPct:sort==="fills"?r.st.filled:r.st.avgNetOnReservedPct;
 out.sort((a,b)=>(Number(val(b))||0)-(Number(val(a))||0)||(b.st.filled||0)-(a.st.filled||0)||a.name.localeCompare(b.name));
 return out;
}
function render(){
 if(!main)return;
 const a=rows(),all=Object.keys(main.allModelStatistics||{}).length;
 by("researchNModels").textContent=all;
 by("researchNRows").textContent=a.length;
 by("researchMaxHit").textContent=a.length?pct(Math.max(...a.map(x=>x.st.takeProfitPct||0))):"—";
 by("researchMaxNet").textContent=a.length?pct(Math.max(...a.map(x=>x.st.avgNetOnReservedPct||0)),3):"—";
 by("researchRankRows").innerHTML=a.map((x,i)=>{
  const s=x.st,k=[x.name,x.h,x.m].join("|"),active=current&&[current.name,current.h,current.m].join("|")===k;
  return '<tr data-model="'+e(x.name)+'" data-h="'+e(x.h)+'" data-mode="'+e(x.m)+'"'+(active?' class="chosen"':'')+'><td><b>'+e(full(x.name))+'</b></td><td>'+type(x.m)+'</td><td>'+e(x.h)+'D</td><td>'+n(s.signalEvents,0)+'</td><td>'+n(s.filled,0)+'</td><td><b>'+pct(s.takeProfitPct)+'</b></td><td>'+pct(s.stopPct)+'</td><td>'+perf(s.avgNetOnDeployedPct)+'</td><td>'+perf(s.avgNetOnReservedPct)+'</td><td>'+n(s.profitFactor,2)+'</td><td>'+n(s.avgTranches,2)+'</td><td>'+n(s.timeSlices?.late?.filled,0)+'</td></tr>';
 }).join("")||'<tr><td colspan="12">此篩選沒有足夠樣本；可將最低成交筆數調低。</td></tr>';
 if(!current||!a.some(x=>x.name===current.name&&x.h===current.h&&x.m===current.m)){current=a[0]||null;modelTrades=null;tradeIdentity="";tradePage=0;by("researchTradeRows").innerHTML='<tr><td colspan="9">選定一列，再按「載入逐筆交易」</td></tr>'}
 if(current)detail();else{by("researchSelectedTitle").textContent="沒有符合條件的模型";by("researchSlices").innerHTML="";}
 archive(activeArchive);
}
function detail(){
 const {name,h,m,st}=current;
 by("researchSelectedTitle").textContent=full(name)+" × "+type(m)+" × "+h+"D";
 by("researchTradeFullJson").href=rootpath+"trades/"+encodeURIComponent(name)+".json";
 by("researchSelectedSummary").textContent="實際開倉 "+st.filled+" 筆｜未成交 "+st.unfilled+"｜排除重複訊號 "+st.duplicateSuppressed+"｜停利 "+st.takeProfitN+" 筆｜停損 "+st.stopN+" 筆｜淨勝率 "+pct(st.netWinPct)+"｜預留資金平均淨報酬 "+pct(st.avgNetOnReservedPct,3)+"｜平均加碼 "+n(st.avgTranches,2)+" 次";
 const captions={early:"1–4月",middle:"5–7月",late:"8–10月"};
 by("researchSlices").innerHTML=Object.entries(st.timeSlices||{}).map(([key,v])=>'<tr><td>'+captions[key]+'</td><td>'+n(v.filled,0)+'</td><td>'+pct(v.tpPct)+'</td><td>'+perf(v.avgNetReservedPct)+'</td><td>'+n(v.signals,0)+'</td></tr>').join("");
 const more=m==="ma"?"｜均線實際觸發 MA5 "+(st.maFillCounts?.["5"]||0)+"、MA10 "+(st.maFillCounts?.["10"]||0)+"、MA20 "+(st.maFillCounts?.["20"]||0)+"、MA60 "+(st.maFillCounts?.["60"]||0)+"。":"｜第一筆以訊號日收盤價-2.5%掛買，成交後4次按首筆成交價依序-2%、-4%、-6%、-8%。";
 by("researchRules").textContent="首筆最多等待5個交易日；從首筆成交日起算"+h+"個交易日內，平均成本+7%停利/-15%停損。費用已列入買賣券商費、證交稅、滑價。"+more;
}
by("researchRankRows").addEventListener("click",ev=>{
 const tr=ev.target.closest("tr[data-model]");if(!tr||!main)return;
 const name=tr.dataset.model,h=tr.dataset.h,m=tr.dataset.mode,st=main.allModelStatistics?.[name]?.[h]?.[m];
 if(!st)return;
 current={name,h,m,st};by("researchRankRows").querySelectorAll("tr").forEach(row=>row.classList.toggle("chosen",row===tr));
 detail();modelTrades=null;tradeIdentity="";by("researchTradeRows").innerHTML='<tr><td colspan="9">按「載入所選模型逐筆交易」查看此組訊號</td></tr>';by("researchTradeCount").textContent="尚未載入";
});
for(const id of ["researchHold","researchMethod","researchModel","researchSort","researchMinFills"])
 by(id).addEventListener("change",render);
by("researchRefresh").addEventListener("click",()=>{main=null;h5=null;g=null;risk=null;timing=null;timingTrades=null;timingMode="";timingGate="";capacity=null;capacityCurves=null;capacitySelected=null;tpSensi=null;tpCurves=null;reinvest=null;reinvestTrades=null;current=null;loading=null;load();});
function tradeRows(){
 if(!modelTrades||!current)return;
 const q=by("researchTradeQuery").value.trim().toLowerCase();
 const all=(modelTrades[current.h]?.[current.m]||[]).filter(x=>String((x.code||"")+" "+(x.name||"")).toLowerCase().includes(q));
 const pages=Math.max(1,Math.ceil(all.length/100));tradePage=Math.max(0,Math.min(tradePage,pages-1));const rows=all.slice().sort((x,y)=>String(y.date||"").localeCompare(String(x.date||""))||x.rank-y.rank).slice(tradePage*100,(tradePage+1)*100);
 by("researchTradeCount").textContent=all.length+" 筆事件（含未成交）｜第 "+(tradePage+1)+" / "+pages+" 頁";by("researchTradePrev").disabled=tradePage===0;by("researchTradeNext").disabled=tradePage>=pages-1;
 by("researchTradeRows").innerHTML=rows.map(x=>'<tr><td>'+e(x.date)+'</td><td><b>'+e(x.code)+" "+e(x.name)+'</b></td><td>'+n(x.rank,0)+'</td><td>'+e(x.firstEntryDate||"未成交")+'</td><td>'+e(x.exitDate||"—")+'</td><td>'+n(x.tranches,0)+'</td><td>'+e(x.reason||x.status)+'</td><td>'+perf(x.netOnDeployedPct)+'</td><td>'+perf(x.netOnReservedPct)+'</td></tr>').join("")||'<tr><td colspan="9">找不到相符的交易</td></tr>';
}
by("researchTradesLoad").addEventListener("click",async()=>{
 if(!current)return;const token=++run,model=current.name;by("researchTradeCount").textContent="正在載入 "+model+" 逐筆資料…";
 try{
  const d=await get(rootpath+"trades/"+encodeURIComponent(model)+".json");
  if(token!==run)return;
  modelTrades=d;tradeIdentity=model;tradePage=0;tradeRows();
 }catch(err){by("researchTradeCount").textContent="載入失敗："+err.message}
});
by("researchTradeQuery").addEventListener("input",()=>{tradePage=0;tradeRows()});
by("researchTradePrev").addEventListener("click",()=>{tradePage=Math.max(0,tradePage-1);tradeRows()});
by("researchTradeNext").addEventListener("click",()=>{tradePage++;tradeRows()});
const hLegacy=[
 ["H1", "高週轉原版（5D -4%停損）", "475", "34.50", "-0.750", "2026全年，非樣本外"],
 ["H2", "高週轉＋盤整突破", "47", "21.28", "-1.466", "2026年全年，5D"],
 ["H3", "7種價量型態驗證", "2", "50.00", "1.054", "後段僅2筆，不足"],
 ["H4", "ML價量模型", "204", "27.45", "-1.246", "2026後段驗證"],
 ["H5 0%", "次日前收盤限價", "83", "37.35", "-0.204", "2026後段驗證"],
 ["H5 -1%", "次日-1%限價", "42", "38.10", "-0.035", "2026後段驗證"],
 ["H5 -2%", "次日-2%限價", "38", "31.58", "-0.254", "2026後段驗證"],
 ["H5 -3%", "次日-3%限價", "13", "30.77", "+0.257", "樣本不足"]
];
function archive(which){
 activeArchive=which;
 document.querySelectorAll("[data-archive]").forEach(b=>b.classList.toggle("active",b.dataset.archive===which));
 const head=by("researchArchiveHead"),tbody=by("researchArchiveRows"),note=by("researchArchiveNote");
 by("researchArchiveLinks").innerHTML=archiveLinks[which]||"";
 by("researchTimingTradeSection").style.display=which==="timing"?"block":"none";
 by("researchCapacityDetail").style.display=(which==="capacity"||which==="tp"||which==="reinvest"||which==="trend00675"||which==="extended00675")?"block":"none";
 if(which==="tp"||which==="reinvest"||which==="trend00675"||which==="extended00675"){by("researchCapacityTitle").textContent="請點選表格中的策略查看逐月報酬與每日資金曲線";by("researchCapacityStats").innerHTML="";by("researchCapacityStatus").textContent="";by("researchCapacityCurve").innerHTML="";by("researchCapacityMonths").innerHTML="";}
 if(which==="g"){
  head.innerHTML="<tr><th>期限</th><th>進場方式</th><th>開倉</th><th>+7%達標</th><th>停損率</th><th>預留資金淨報酬</th></tr>";
  note.textContent="先前 G_DOUBLE_PERSIST Top3 兩種加碼法對照；與17模型比較的一致範圍，但獨立執行的歷史歸檔。";
  tbody.innerHTML=g?.statistics?Object.entries(g.statistics).flatMap(([h,ms])=>Object.entries(ms).map(([m,x])=>'<tr><td>'+e(h)+'D</td><td>'+type(m)+'</td><td>'+n(x.filled,0)+'</td><td>'+pct(x.takeProfitPct)+'</td><td>'+pct(x.stopPct)+'</td><td>'+perf(x.avgNetOnReservedPct)+'</td></tr>')).join(""):'<tr><td colspan="6">研究檔案未載入</td></tr>';
 }else if(which==="h"){
  head.innerHTML="<tr><th>期限</th><th>首筆折價</th><th>開倉</th><th>+7%達標</th><th>停損率</th><th>已投入資金淨報酬</th><th>預留資金淨報酬</th></tr>";
  note.textContent="H5 的固定突破選股不變，測試首筆限價-2%、-2.5%、-3%，之後4筆每下跌首筆成交價2%加碼。此研究的首筆委託僅下一交易日有效，與上方17模型5日等待版不同，不可直接同比。";
  tbody.innerHTML=h5?.results?Object.entries(h5.results).flatMap(([h,discount])=>Object.entries(discount).map(([off,s])=>'<tr><td>'+e(h)+'D</td><td>-'+e(off)+'%</td><td>'+n(s.filled,0)+'</td><td>'+pct(s.targetHitPct)+'</td><td>'+pct(s.stopHitPct)+'</td><td>'+perf(s.avgNetOnDeployedPct)+'</td><td>'+perf(s.avgNetOnFiveTrancheBudgetPct)+'</td></tr>')).join(""):'<tr><td colspan="7">研究檔案未載入</td></tr>';
 }else if(which==="extended00675"){
  head.innerHTML="<tr><th>00675L 資金策略</th><th>2020</th><th>2022</th><th>2026</th><th>全期淨報酬</th><th>期末資產</th><th>最大回撤</th><th>賣出／買回</th></tr>";
  note.textContent="2020/1/2～2026/10/7，1642個交易日｜起始100萬元，獲利全數複投，不跨年重置。固定之前2024～26研究參數；這次新增2020疫情、2022空頭行情，未利用2020～23重新挑門檻。每筆使用隔日開盤模擬成交，費稅、ETF賣稅、雙向滑價皆計入。SMA10是簡單移動平均，EMA10為另外列出的實驗版本，並不相同。按歷史回報排序只為便於對照，不代表未來建議排名。點選一列查看完整每日現金曲線與逐月報酬。";
  const label={
   "BUY_HOLD":"全程買進持有",
   "SMA_twii_10_O0.02_R0.01_C3_W0.0":"台指 SMA10（連3天跌破2%，站回+1%）",
   "MA_twii_10_O0.02_R0.01_C3_W0.0":"台指 EMA10（探索版）",
   "MA_close_10_O0.04_R0.02_C3_W0.0":"00675L EMA10（探索版）",
   "SMA_close_10_O0.04_R0.02_C3_W0.0":"00675L SMA10（連3天跌破4%）",
   "TRAIL_20_0.16_RE10_W0.0":"20日高點回撤16%，EMA10買回",
   "CRASH_3_0.1_RE10_Gtwii_below60_W0.0":"急跌10%＋台指偏弱",
   "MA_twii_20_O0.03_R0.0_C1_W0.0":"台指 EMA20 跌破3%",
   "CRASH_3_0.1_RE10_Gall_W0.0":"無大盤濾網急跌10%",
   "DUAL_twii_120_20_RE10_W0.5":"台指雙均線減碼一半",
   "EMA10_TWII20_TP10_SL7":"短波段 EMA10，固定10%停利"};
  const raw=extended00675?[extended00675.baseline,...extended00675.comparison].sort((a,b)=>b.continuous.returnPct-a.continuous.returnPct):[];
  tbody.innerHTML=raw.length?raw.map(z=>{
    const c=z.continuous,y=z.compoundedCalendarYears;
    return '<tr style="cursor:pointer" data-extended00675="'+e(z.id)+'"><td>'+e(label[z.id]||z.id)+'</td><td>'+perf(y["2020"].calendarReturnPct)+'</td><td>'+perf(y["2022"].calendarReturnPct)+'</td><td>'+perf(y["2026"].calendarReturnPct)+'</td><td>'+perf(c.returnPct)+'</td><td>'+e(n(c.endNTD/10000,2))+'萬</td><td>'+perf(c.mddPct)+'</td><td>'+e(c.riskOffSells==null?"短線 "+(c.trades||0)+" 筆":c.riskOffSells+"／"+c.riskOnReentries)+'</td></tr>';
  }).join(""):'<tr><td colspan="8">2020～2026 研究尚未載入，請檢查資料 JSON。</td></tr>';
  }else if(which==="trend00675"){
  head.innerHTML="<tr><th>00675L 交易方法</th><th>2024 淨報酬</th><th>2025 淨報酬</th><th>2026 淨報酬</th><th>連續 2024～26</th><th>最後資產</th><th>最大回撤</th><th>完整賣出／買回</th><th>風險空手交易日</th></tr>";
  note.textContent="2024～2026/10/7，100萬元起始、獲利100%複投、ETF買賣費稅與雙邊滑價。先依2024～25年選候選，再評估2026年；但2026行情先前已多次被研究，不是全新獨立驗證。1091組參數中選出實際多次完整出場與重新買回的7種，對照長抱。表格按完整歷史報酬排序僅供閱讀，不能把它當未來績效排名。點選策略可查看每日資金曲線與月報酬。";
  const label={
   "CRASH_3_0.1_RE10_Gtwii_below60_W0.0":"急跌10%＋大盤偏弱；站回EMA10",
   "CRASH_5_0.1_RE10_Gtwii_below60_W0.0":"5日急跌風控；站回EMA10",
   "MA_twii_20_O0.03_R0.0_C1_W0.0":"台指跌破MA20達3%；站回MA20",
   "TRAIL_20_0.16_RE10_W0.0":"20日高點回撤16%；站回EMA10",
   "CRASH_3_0.1_RE10_Gall_W0.0":"急跌10%出場，無大盤濾網",
   "DUAL_twii_120_20_RE10_W0.5":"台指雙均線，減碼一半",
   "CRASH_5_0.06_RE20_Gall_W0.0":"急跌6%出場；站回EMA20"
  };
  const baseline=regime00675?.baseline;
  const bh=baseline?[{id:"BUY_HOLD",continuous:baseline.continuous,2024:baseline["2024"],2025:baseline["2025"],2026:baseline["2026"]}]:[];
  const cases=[...(regime00675?.frozenComparisons||[])].sort((a,b)=>b.continuous.returnPct-a.continuous.returnPct);
  tbody.innerHTML=baseline?[...bh,...cases].map(v=>{
    const id=v.id,c=v.continuous;
    const sells=c.riskOffSells||0,buys=c.riskOnReentries||0,empty=c.riskOffSessions||0;
    return '<tr '+(id==="BUY_HOLD"?'':'style="cursor:pointer"')+' data-trend00675="'+e(id)+'"><td>'+e(id==="BUY_HOLD"?"買進長抱（基準）":(label[id]||id))+'</td><td>'+perf(v["2024"].returnPct)+'</td><td>'+perf(v["2025"].returnPct)+'</td><td>'+perf(v["2026"].returnPct)+'</td><td>'+perf(c.returnPct)+'</td><td>'+e(n(c.endNTD/10000,2))+'萬</td><td>'+perf(c.mddPct)+'</td><td>'+sells+'/'+buys+'</td><td>'+empty+'日</td></tr>';
  }).join(""):'<tr><td colspan="9">趨勢輪動研究資料未載入，請檢查資料連結。</td></tr>';
  }else if(which==="reinvest"){
  head.innerHTML="<tr><th>投入模式</th><th>回測區間</th><th>起始資金</th><th>結束資產</th><th>累積淨%</th><th>最大回撤</th><th>交易數</th><th>最大單筆投入</th></tr>";
  note.textContent="00675L 台指收盤站上 MA20＋ETF站回 EMA10；隔日開盤買進，+10% 毛停利／-7% 毛停損／20D上限。固定100萬＝每筆新交易最多用原始100萬，額外獲利留在帳戶不投入；半複利＝最多100萬加上累計盈餘的一半；全複利＝當下可用現金全部投入。連續區間從2024年一次給100萬，從未每年重新注資，其他各年則單獨從100萬開始。2026已扣ETF交易費稅滑價。";
  const names={fixed_100m:"固定最多100萬",half_profit_reinvest:"獲利複投50%",all_profit_reinvest:"獲利複投100%"};
  const periods={2024:"單獨2024",2025:"單獨2025",2026:"單獨2026",continuous_2024_2026:"2024至2026連續複投"};
  tbody.innerHTML=reinvest?.comparison?Object.entries(reinvest.comparison).flatMap(([mode,obj])=>Object.entries(obj.byPeriod).map(([period,z])=>
   '<tr style="cursor:pointer" data-reinv-mode="'+e(mode)+'" data-reinv-period="'+e(period)+'"><td>'+e(names[mode])+'</td><td>'+e(periods[period])+'</td><td>100.00 萬</td><td>'+e(n(z.endingEquityNTD/10000,2))+' 萬</td><td>'+perf(z.returnPct)+'</td><td>'+perf(z.maxDrawdownPct)+'</td><td>'+n(z.trades,0)+'</td><td>'+e(n(z.maxSingleTradeCostNTD/10000,2))+' 萬</td></tr>'
  )).join(""):'<tr><td colspan="8">00675L 複利研究尚未載入，請使用上方來源 JSON 連結。</td></tr>';
  }else if(which==="tp"){
  head.innerHTML="<tr><th>選股版本</th><th>加碼模式</th><th>大盤進場</th><th>上限</th><th>停利／停損</th><th>成交筆數</th><th>停利率</th><th>停損率</th><th>淨勝率</th><th>平均淨報酬</th><th>帳戶淨報酬</th><th>最大回撤</th><th>平均持有</th></tr>";
  note.textContent="2026/1～10/7｜2026 歷史 108 組回測。100萬元、無槓桿、五段固定低接或MA觸價，10D上限；成本含雙向券商手續費、賣出交易稅及雙邊滑價。3%為股價平均成本的毛停利，絕非實拿3%。使用日K而非Bottom／Top兩分鐘訊號。點擊一列查看逐日資金曲線、月報酬。";
  const names={baseline:"不設大盤",signal_ma20:"訊號日MA20",wait_ma20:"等待MA20"};
  const targets={tp3_sl10:"+3% / -10%",tp5_sl10:"+5% / -10%",tp7_sl15:"+7% / -15%"};
  tbody.innerHTML=tpSensi?.statistics?["G_STRICT","G_DOUBLE_PERSIST"].flatMap(sel=>["ladder","ma"].flatMap(mode=>["baseline","signal_ma20","wait_ma20"].flatMap(gate=>["3","5","10"].flatMap(slot=>["tp3_sl10","tp5_sl10","tp7_sl15"].map(rule=>{
   const z=tpSensi.statistics[sel]?.[mode]?.[gate]?.[rule]?.[slot];if(!z)return "";
   return '<tr data-tp-selector="'+e(sel)+'" data-tp-mode="'+e(mode)+'" data-tp-gate="'+e(gate)+'" data-tp-rule="'+e(rule)+'" data-tp-slots="'+e(slot)+'" style="cursor:pointer"><td>'+e(sel)+'</td><td>'+type(mode)+'</td><td>'+e(names[gate])+'</td><td>'+e(slot)+'</td><td>'+e(targets[rule])+'</td><td>'+n(z.filled,0)+'</td><td>'+pct(z.tpPct)+'</td><td>'+pct(z.stopPct)+'</td><td>'+pct(z.netWinPct)+'</td><td>'+perf(z.averageNetReservedPct)+'</td><td>'+perf(z.totalReturnPct)+'</td><td>'+perf(z.maxDrawdownPct)+'</td><td>'+n(z.avgHoldDays,2)+'D</td></tr>';
  }))))).join(""):'<tr><td colspan="13">尚未載入停利3%／停損10%研究檔案，請查詢原始 JSON。</td></tr>';
  }else if(which==="capacity"){
  head.innerHTML="<tr><th>模型</th><th>加碼方式</th><th>大盤進場條件</th><th>同時預留</th><th>已成交</th><th>資金不足跳過</th><th>停損率</th><th>帳戶累積淨%</th><th>最大回撤</th><th>7月淨%</th><th>最多連續虧損</th></tr>";
  note.textContent="2026/1～10/7｜100萬模擬現金帳戶、無槓桿。等待中的買單也會預留一組名額，滿額時不允許新股票入場。同股不可重複持有。資金曲線每日依市價重估已成交股票，扣模擬手續費、稅及滑價。非券商級成交、非樣本外結果。點選資料列查看逐月績效及每日權益曲線。";
  const gatelabel={baseline:"不看大盤",signal_ma20:"訊號日站上MA20",wait_ma20:"最多5日等站回MA20"};
  tbody.innerHTML=capacity?.statistics?["G_STRICT","G_DOUBLE_PERSIST"].flatMap(sel=>["ladder","ma"].flatMap(mode=>["baseline","signal_ma20","wait_ma20"].flatMap(gate=>["3","5","10"].map(slots=>{
   const z=capacity.statistics[sel]?.[mode]?.[gate]?.[slots];if(!z)return "";
   return '<tr data-cap-selector="'+e(sel)+'" data-cap-mode="'+e(mode)+'" data-cap-gate="'+e(gate)+'" data-cap-slots="'+e(slots)+'" style="cursor:pointer"><td>'+e(sel)+'</td><td>'+type(mode)+'</td><td>'+e(gatelabel[gate])+'</td><td>'+e(slots)+'</td><td>'+n(z.filled,0)+'</td><td>'+n(z.skipped?.capacity,0)+'</td><td>'+pct(z.stopPct)+'</td><td>'+perf(z.totalReturnPct)+'</td><td>'+perf(z.maxDrawdownPct)+'</td><td>'+perf(z.julyReturnPct)+'</td><td>'+n(z.maxConsecutiveLosses,0)+'</td></tr>';
  })))).join(""):'<tr><td colspan="11">完整資金限制研究尚未載入，請查詢原始 JSON。</td></tr>';
  }else if(which==="timing"){
  head.innerHTML="<tr><th>進場方式</th><th>大盤 MA20 首筆限制</th><th>已成交</th><th>+7% 停利率</th><th>-15% 停損率</th><th>淨勝率</th><th>預留資金淨報酬</th><th>PF</th><th>平均等待日</th></tr>";
  note.textContent="G_STRICT 2026 Top3｜10D｜+7%停利、-15%停損。各方案重新模擬同股票重複入選、等待下單、交易成本與出場。僅用交易前已收盤大盤日K，仍非獨立樣本外驗證；非完整資金曲線。點選任一列可翻閱全部逐筆事件。";
  const gates=[["baseline","不設大盤條件"],["signal_ma20","訊號日大盤收在MA20上"],["wait_ma20","5日內等待大盤站回MA20"],["wait_ma20_twoday","等待連續2日站上MA20"],["wait_ma20_rising","等待站回MA20且MA20向上"]];
  tbody.innerHTML=timing?.statistics?.["10"]?["ladder","ma"].flatMap(mode=>gates.map(([key,label])=>{
   const z=timing.statistics["10"]?.[mode]?.[key];if(!z)return "";
   return '<tr data-market-mode="'+e(mode)+'" data-market-gate="'+e(key)+'" style="cursor:pointer"><td>'+type(mode)+'</td><td>'+e(label)+'</td><td>'+n(z.filled,0)+'</td><td>'+pct(z.takeProfitPct)+'</td><td>'+pct(z.stopPct)+'</td><td>'+pct(z.netWinPct)+'</td><td>'+perf(z.avgNetOnReservedPct)+'</td><td>'+n(z.profitFactor,2)+'</td><td>'+n(z.avgSignalToEntryDays,2)+'</td></tr>';
  })).join(""):'<tr><td colspan="9">進場等待研究尚未載入，請查看資料 JSON。</td></tr>';
 }else if(which==="risk"){
  head.innerHTML="<tr><th>進場法</th><th>訊號當日大盤條件</th><th>成交</th><th>+7% 停利</th><th>-15% 停損</th><th>避免停損</th><th>錯過停利</th><th>預留資金淨%</th><th>7月成交</th><th>7月停損</th></tr>";
  note.textContent="G_STRICT 10D 固定向下／均線加碼，用「選股訊號日已完成的加權指數日K」判斷大盤位階。只從已完成歷史交易中剔除不符條件的訊號；未重選候補股票、未模擬同股票後續掛單或共享帳戶資金。2026年樣本內探索，不是因果證明。";
  const gates=[["All","不看大盤"],["indexAboveMA20","加權指數收在MA20以上"],["indexAboveMA60","加權指數收在MA60以上"],["indexPosition60ge50","60日區間位階≥50"],["indexPosition120ge50","120日區間位階≥50"],["indexFavorable","MA20以上＋MA20向上＋60日位階≥50"],["indexNotDown2Pct5D","加權指數5日跌幅不超過2%"]];
  tbody.innerHTML=risk?.modes?["ladder","ma"].flatMap(mode=>gates.map(([key,label])=>{
    const a=risk.modes[mode]?.filters?.[key];if(!a)return "";
    const z=a.accepted,j=a.july;return '<tr><td>'+type(mode)+'</td><td>'+e(label)+'</td><td>'+n(z.filled,0)+'</td><td>'+pct(z.tpPct)+'</td><td>'+pct(z.stopPct)+'</td><td>'+pct(a.fractionStopsAvoided)+'</td><td>'+n(a.profitTakingSignalsLost,0)+'筆</td><td>'+perf(z.avgNetReservedPct)+'</td><td>'+n(j?.filled,0)+'</td><td>'+n(j?.stopN,0)+'筆</td></tr>';
  })).join(""):'<tr><td colspan="10">大盤位階研究檔案未載入，請重新載入或檢查 GitHub Pages JSON。</td></tr>';
 }else{
  head.innerHTML="<tr><th>版本</th><th>方法</th><th>成交</th><th>+7%停利率</th><th>每筆平均淨報酬</th><th>備註</th></tr>";
  note.textContent="原始 H1～H5：5日內 +7% 毛停利；H1 停損 -4%，H2～H5 停損 -3.5%；不可直接和新版五段加碼、-15% 停損的命中率比較。";
  tbody.innerHTML=hLegacy.map(x=>'<tr>'+x.map((v,i)=>'<td>'+((i===3||i===4)?e(v)+"%":e(v))+'</td>').join("")+'</tr>').join("");
 }
}
async function selectTimingTrades(mode,gate){
 timingMode=mode;timingGate=gate;timingPage=0;
 by("researchTimingTradeTitle").textContent="G_STRICT "+type(mode)+"｜"+gate;
 by("researchTimingTradeCount").textContent="逐筆 JSON 讀取中…";
 try{
  if(!timingTrades)timingTrades=await get(rootpath+"g_strict_ma20_entry_trades_2026.json");
  timingRenderTrades();
 }catch(err){by("researchTimingTradeCount").textContent="載入失敗："+err.message;}
}
function timingRenderTrades(){
 if(!timingTrades||!timingMode||!timingGate)return;
 const q=by("researchTimingTradeSearch").value.trim().toLowerCase();
 const all=(timingTrades["10"]?.[timingMode]?.[timingGate]||[]).filter(x=>String((x.code||"")+" "+(x.name||"")).toLowerCase().includes(q));
 const pages=Math.max(1,Math.ceil(all.length/100));timingPage=Math.max(0,Math.min(pages-1,timingPage));
 const rows=all.slice().sort((a,b)=>String(b.date).localeCompare(String(a.date))).slice(timingPage*100,(timingPage+1)*100);
 by("researchTimingTradeCount").textContent=all.length+" 筆事件｜第 "+(timingPage+1)+"/"+pages+" 頁";
 by("researchTimingTradePrev").disabled=timingPage===0;by("researchTimingTradeNext").disabled=timingPage>=pages-1;
 by("researchTimingTradeRows").innerHTML=rows.map(x=>'<tr><td>'+e(x.date)+'</td><td>'+e(x.code)+' '+e(x.name||"")+'</td><td>'+n(x.rank,0)+'</td><td>'+e(x.status)+'</td><td>'+e(x.firstEntryDate||"—")+'</td><td>'+e(x.exitDate||"—")+'</td><td>'+n(x.tranches,0)+'</td><td>'+e(x.reason||"—")+'</td><td>'+perf(x.netOnDeployedPct)+'</td><td>'+perf(x.netOnReservedPct)+'</td></tr>').join("")||'<tr><td colspan="10">沒有符合條件的紀錄</td></tr>';
}
by("researchArchiveRows").addEventListener("click",ev=>{
 const tr=ev.target.closest("tr[data-market-mode]");if(!tr)return;
 selectTimingTrades(tr.dataset.marketMode,tr.dataset.marketGate);
});
by("researchTimingTradeSearch").addEventListener("input",()=>{timingPage=0;timingRenderTrades();});
by("researchTimingTradePrev").addEventListener("click",()=>{timingPage=Math.max(0,timingPage-1);timingRenderTrades();});
by("researchTimingTradeNext").addEventListener("click",()=>{timingPage++;timingRenderTrades();});
const capGateLabel={baseline:"不看大盤",signal_ma20:"訊號日大盤高於MA20",wait_ma20:"等待大盤重回MA20"};
async function selectCapacity(selector,mode,gate,slots){
  const token=++capacityToken;
  capacitySelected={selector,mode,gate,slots};
  const stats=capacity?.statistics?.[selector]?.[mode]?.[gate]?.[slots];
  if(!stats)return;
  by("researchCapacityTitle").textContent=selector+"｜"+type(mode)+"｜"+capGateLabel[gate]+"｜最多 "+slots+" 組";
  by("researchCapacityStats").innerHTML=[
   ["最終累積淨報酬",pct(stats.totalReturnPct)],
   ["最大回撤",pct(stats.maxDrawdownPct)],
   ["已成交",n(stats.filled,0)+" 筆"],
   ["最高同時資金預留",n(stats.maxConcurrentReservations,0)+" 組"]]
   .map(([k,v])=>'<div><span class="muted">'+e(k)+'</span><strong>'+e(v)+'</strong></div>').join("");
  by("researchCapacityMonths").innerHTML=Object.entries(stats.monthlyReturnsPct||{}).map(([m,p])=>'<tr><td>'+e(m)+'</td><td>'+perf(p)+'</td></tr>').join("");
  by("researchCapacityStatus").textContent="正在讀取逐日現金權益資料…";
  try{
    if(!capacityCurves)capacityCurves=await get(rootpath+"g_capital_2026_equity_curves.json");
    if(token!==capacityToken)return;
    const curve=capacityCurves.daily?.[selector]?.[mode]?.[gate]?.[slots]||[];
    if(curve.length<2)throw Error("此策略無每日曲線");
    const w=760,h=170,pad=15,ys=curve.map(p=>Number(p.equity)),lo=Math.min(...ys),hi=Math.max(...ys),range=Math.max(1,hi-lo);
    const pts=curve.map((p,i)=>(pad+(w-2*pad)*i/(curve.length-1)).toFixed(2)+","+(pad+(h-2*pad)*(hi-Number(p.equity))/range).toFixed(2)).join(" ");
    by("researchCapacityCurve").innerHTML='<div class="muted">每日權益曲線｜最低 '+e(n(lo,0))+' 元 / 最高 '+e(n(hi,0))+' 元（2026/1～10）</div><svg role="img" aria-label="每日現金權益曲線" viewBox="0 0 '+w+' '+h+'" style="width:100%;height:auto;min-width:350px;margin-top:6px"><line x1="0" y1="'+(h-10)+'" x2="'+w+'" y2="'+(h-10)+'" stroke="#94a3b8" stroke-width="1"/><polyline points="'+pts+'" fill="none" stroke="#2563eb" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>';
    by("researchCapacityStatus").textContent=curve.length+" 個交易日";
  }catch(err){if(token!==capacityToken)return;by("researchCapacityStatus").textContent="無法顯示每日曲線："+err.message;by("researchCapacityCurve").innerHTML="";}
}
by("researchArchiveRows").addEventListener("click",ev=>{
 const row=ev.target.closest("tr[data-cap-selector]");if(!row)return;
 selectCapacity(row.dataset.capSelector,row.dataset.capMode,row.dataset.capGate,row.dataset.capSlots);
});
async function selectTPSensitivity(selector,mode,gate,rule,slots){
 const token=++tpToken;
 const stats=tpSensi?.statistics?.[selector]?.[mode]?.[gate]?.[rule]?.[slots];
 if(!stats)return;
 const names={baseline:"不設大盤",signal_ma20:"訊號日MA20",wait_ma20:"等站回MA20"};
 const rules={tp3_sl10:"+3%停利／-10%停損",tp5_sl10:"+5%停利／-10%停損",tp7_sl15:"+7%停利／-15%停損"};
 by("researchCapacityTitle").textContent=selector+"｜"+type(mode)+"｜"+names[gate]+"｜"+slots+"組｜"+rules[rule];
 by("researchCapacityStats").innerHTML=[
  ["100萬元帳戶最終淨報酬",pct(stats.totalReturnPct)],
  ["最大回撤",pct(stats.maxDrawdownPct)],
  ["停利／停損",stats.tpN+"／"+stats.stopN+" 筆"],
  ["平均持有",n(stats.avgHoldDays,2)+" 個交易日"],
  ["Profit Factor",n(stats.profitFactor,3)]]
  .map(([k,v])=>'<div><span class="muted">'+e(k)+'</span><strong>'+e(v)+'</strong></div>').join("");
 by("researchCapacityMonths").innerHTML=Object.entries(stats.monthlyReturnsPct||{}).map(([m,p])=>'<tr><td>'+e(m)+'</td><td>'+perf(p)+'</td></tr>').join("");
 by("researchCapacityStatus").textContent="正在讀取完整 108 組逐日權益曲線…";
 try{
  if(!tpCurves)tpCurves=await get(rootpath+"g_tp_sl_2026_equity_curves.json");
  if(token!==tpToken||activeArchive!=="tp")return;
  const curve=tpCurves.daily?.[selector]?.[mode]?.[gate]?.[rule]?.[slots]||[];
  if(curve.length<2)throw Error("此策略缺少每日資料");
  const w=760,h=170,pad=15,ys=curve.map(p=>Number(p.equity)),lo=Math.min(...ys),hi=Math.max(...ys),range=Math.max(1,hi-lo);
  const pts=curve.map((p,i)=>(pad+(w-2*pad)*i/(curve.length-1)).toFixed(2)+","+(pad+(h-2*pad)*(hi-Number(p.equity))/range).toFixed(2)).join(" ");
  by("researchCapacityCurve").innerHTML='<div class="muted">每日現金權益曲線｜最低 '+e(n(lo,0))+' 元／最高 '+e(n(hi,0))+' 元</div><svg role="img" aria-label="2026 TP SL 每日資金曲線" viewBox="0 0 '+w+' '+h+'" style="width:100%;height:auto;min-width:350px;margin-top:6px"><line x1="0" y1="'+(h-10)+'" x2="'+w+'" y2="'+(h-10)+'" stroke="#94a3b8" stroke-width="1"/><polyline points="'+pts+'" fill="none" stroke="#2563eb" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>';
  by("researchCapacityStatus").textContent=curve.length+" 個交易日";
 }catch(err){if(token!==tpToken||activeArchive!=="tp")return;by("researchCapacityStatus").textContent="曲線載入失敗："+err.message;by("researchCapacityCurve").innerHTML="";}
}
by("researchArchiveRows").addEventListener("click",ev=>{
 const row=ev.target.closest("tr[data-tp-selector]");if(!row)return;
 selectTPSensitivity(row.dataset.tpSelector,row.dataset.tpMode,row.dataset.tpGate,row.dataset.tpRule,row.dataset.tpSlots);
});
async function selectReinvestment(mode,period){
 const token=++reinvestToken;
 const stats=reinvest?.comparison?.[mode]?.byPeriod?.[period];
 if(!stats)return;
 const names={fixed_100m:"每筆最多100萬",half_profit_reinvest:"50%獲利複投",all_profit_reinvest:"100%獲利複投"};
 const periods={2024:"2024單獨",2025:"2025單獨",2026:"2026單獨",continuous_2024_2026:"2024至2026連續"};
 by("researchCapacityTitle").textContent="00675L｜"+names[mode]+"｜"+periods[period];
 by("researchCapacityStats").innerHTML=[
 ["期末資產",n(stats.endingEquityNTD/10000,2)+"萬元"],
 ["帳戶累積淨報酬",pct(stats.returnPct)],
 ["最大回撤",pct(stats.maxDrawdownPct)],
 ["最大單筆投入",n(stats.maxSingleTradeCostNTD/10000,2)+"萬元"],
 ["交易次數",n(stats.trades,0)+"筆"]]
 .map(([k,v])=>'<div><span class="muted">'+e(k)+'</span><strong>'+e(v)+'</strong></div>').join("");
 by("researchCapacityStatus").textContent="正在讀取逐筆交易及每日帳戶資料…";
 try{
  if(!reinvestTrades)reinvestTrades=await get(rootpath+"00675l_reinvestment_trades_equity.json");
  if(token!==reinvestToken||activeArchive!=="reinvest")return;
  const record=reinvestTrades.tradesAndEquity?.[mode]?.[period];
  const curve=record?.dailyEquity||[];
  if(curve.length<2)throw Error("無可用權益資料");
  const w=760,h=170,pad=15,ys=curve.map(x=>Number(x.equity)),lo=Math.min(...ys),hi=Math.max(...ys),range=Math.max(1,hi-lo);
  const pts=curve.map((p,i)=>(pad+(w-2*pad)*i/(curve.length-1)).toFixed(2)+","+(pad+(h-2*pad)*(hi-Number(p.equity))/range).toFixed(2)).join(" ");
  by("researchCapacityCurve").innerHTML='<div class="muted">每日現金權益曲線｜低 '+e(n(lo,0))+'元／高 '+e(n(hi,0))+'元</div><svg role="img" aria-label="00675L 複投現金權益" viewBox="0 0 '+w+' '+h+'" style="width:100%;height:auto;min-width:350px;margin-top:6px"><line x1="0" y1="'+(h-10)+'" x2="'+w+'" y2="'+(h-10)+'" stroke="#94a3b8" stroke-width="1"/><polyline points="'+pts+'" fill="none" stroke="#2563eb" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>';
  const months={};for(const x of curve)months[x.date.slice(0,7)]=Number(x.equity);
  let prev=1000000;
  by("researchCapacityMonths").innerHTML=Object.entries(months).map(([month,last])=>{const ret=100*(last/prev-1);prev=last;return '<tr><td>'+e(month)+'</td><td>'+perf(ret)+'</td></tr>';}).join("");
  by("researchCapacityStatus").textContent=curve.length+"個交易日｜"+(record.events||[]).length+"筆已完成交易";
 }catch(err){if(token!==reinvestToken||activeArchive!=="reinvest")return;by("researchCapacityStatus").textContent="無法載入複投曲線："+err.message;by("researchCapacityCurve").innerHTML="";}
}
by("researchArchiveRows").addEventListener("click",ev=>{
 const row=ev.target.closest("tr[data-reinv-mode]");if(!row)return;
 selectReinvestment(row.dataset.reinvMode,row.dataset.reinvPeriod);
});
async function select00675Trend(id){
 const token=++regime00675Token;
 const caseData=(regime00675?.frozenComparisons||[]).find(x=>x.id===id);
 if(!caseData)return;
 const c=caseData.continuous;
 by("researchCapacityTitle").textContent="00675L 2024～2026／趨勢輪動｜"+id;
 let vals=[["期末資產",n(c.endNTD/10000,2)+"萬元"],["累積淨報酬",pct(c.returnPct)],
     ["最大回撤",pct(c.mddPct)],["完整賣出／買回",c.riskOffSells+"／"+c.riskOnReentries],
     ["不持有 ETF 日數",c.riskOffSessions+"日"]];
 const model=regime00675Stress?.transactionCostSensitivity?.stats;
 const stressed=model?.["0.005"]?.[id]?.continuous;
 if(stressed)vals.push(["雙向滑價各0.5%",pct(stressed.returnPct)]);
 const delayed=regime00675Stress?.delaySensitivity?.stats?.["1"]?.[id]?.continuous;
 if(delayed)vals.push(["延遲1日進出",pct(delayed.returnPct)]);
 by("researchCapacityStats").innerHTML=vals.map(([k,v])=>'<div><span class="muted">'+e(k)+'</span><strong>'+e(v)+'</strong></div>').join("");
 by("researchCapacityStatus").textContent="正在讀取股數、現金與每日帳戶資料…";
 try{
  if(!regime00675Equity)regime00675Equity=await get(rootpath+"00675l_regime_capture_equity.json");
  if(activeArchive!=="trend00675"||token!==regime00675Token)return;
  const rec=(regime00675Equity.models||[]).find(z=>z.id===id),curve=rec?.equity||[];
  if(curve.length<2)throw Error("目前無每日權益曲線");
  const w=760,h=170,pad=15,ys=curve.map(x=>Number(x.equity));
  const lo=Math.min(...ys),hi=Math.max(...ys),range=Math.max(1,hi-lo);
  const pts=curve.map((p,i)=>(pad+(w-2*pad)*i/(curve.length-1)).toFixed(2)+","+(pad+(h-2*pad)*(hi-Number(p.equity))/range).toFixed(2)).join(" ");
  by("researchCapacityCurve").innerHTML='<div class="muted">每日現金權益｜低 '+e(n(lo,0))+'元／高 '+e(n(hi,0))+'元</div><svg role="img" aria-label="00675L 趨勢輪動每日帳戶權益" viewBox="0 0 '+w+' '+h+'" style="width:100%;height:auto;min-width:350px;margin-top:6px"><line x1="0" y1="'+(h-10)+'" x2="'+w+'" y2="'+(h-10)+'" stroke="#94a3b8"/><polyline points="'+pts+'" fill="none" stroke="#2563eb" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>';
  const months={};for(const t of curve)months[t.date.slice(0,7)]=Number(t.equity);
  let previous=1000000;
  by("researchCapacityMonths").innerHTML=Object.entries(months).map(([month,now])=>{const ret=100*(now/previous-1);previous=now;return '<tr><td>'+e(month)+'</td><td>'+perf(ret)+'</td></tr>';}).join("");
  by("researchCapacityStatus").textContent=curve.length+"個交易日，出場"+c.riskOffSells+"次、買回"+c.riskOnReentries+"次；詳細訂單 "+(rec.orders||[]).length+" 筆。";
 }catch(err){if(activeArchive!=="trend00675"||token!==regime00675Token)return;by("researchCapacityStatus").textContent="無法載入權益曲線："+err.message;by("researchCapacityCurve").innerHTML="";}
}
by("researchArchiveRows").addEventListener("click",ev=>{
 const row=ev.target.closest("tr[data-trend00675]");if(!row)return;
 if(row.dataset.trend00675==="BUY_HOLD"){by("researchCapacityTitle").textContent="00675L 2024～2026 買進持有：100萬→592.54萬、+492.54%、最大回撤-55.24%；未設每日資金曲線。";by("researchCapacityCurve").innerHTML="";by("researchCapacityMonths").innerHTML="";by("researchCapacityStats").innerHTML="";by("researchCapacityStatus").textContent="請點選來回操作策略查看逐日曲線。";return;}
 select00675Trend(row.dataset.trend00675);
});
async function selectExtended00675(id){
 const token=++extended00675Token;
 const model=[extended00675?.baseline,...(extended00675?.comparison||[])].find(x=>x?.id===id);
 if(!model)return;
 const c=model.continuous,yr=model.compoundedCalendarYears;
 by("researchCapacityTitle").textContent="00675L｜2020～2026 不重置本金｜"+id;
 const vals=[["最後總資產",n(c.endNTD/10000,2)+"萬元"],
   ["全期淨報酬",pct(c.returnPct)],["最大回撤",pct(c.mddPct)],
   ["2020年度",pct(yr["2020"].calendarReturnPct)],["2022年度",pct(yr["2022"].calendarReturnPct)],
   ["2026年度",pct(yr["2026"].calendarReturnPct)],
   ["風險出場",c.riskOffSells==null?c.trades+"筆短線":c.riskOffSells+"次"]];
 const stress=extended00675?.stress;
 const slip=stress?.slippageEachSide?.["0.005"]?.[id];
 if(slip)vals.push(["買賣各0.5%滑價",pct(slip.returnPct)]);
 const lag=stress?.additionalDecisionSessionLag?.["1"]?.[id];
 if(lag)vals.push(["延後1交易日執行",pct(lag.returnPct)]);
 by("researchCapacityStats").innerHTML=vals.map(([key,value])=>'<div><span class="muted">'+e(key)+'</span><strong>'+e(value)+'</strong></div>').join("");
 by("researchCapacityStatus").textContent="載入完整 1642 日資金曲線及交易紀錄…";
 try{
  if(!extended00675Equity)extended00675Equity=await get(rootpath+"00675l_extended_2020_2026_daily_equity.json");
  if(token!==extended00675Token||activeArchive!=="extended00675")return;
  const m=extended00675Equity.cases?.[id],points=m?.dailyAccountEquity||[];
  if(points.length<2)throw Error("缺少完整每日資金曲線");
  const w=760,h=180,p=16,vs=points.map(z=>Number(z.equity));
  const lo=Math.min(...vs),hi=Math.max(...vs),spread=Math.max(1,hi-lo);
  const poly=points.map((z,i)=>(p+(w-2*p)*i/(points.length-1)).toFixed(2)+","+(p+(h-2*p)*(hi-Number(z.equity))/spread).toFixed(2)).join(" ");
  by("researchCapacityCurve").innerHTML='<div class="muted">每日帳戶權益｜低 '+e(n(lo,0))+'元／高 '+e(n(hi,0))+'元</div><svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="00675L 2020年至2026年真實日線資金回測" style="width:100%;height:auto;min-width:350px;margin-top:6px"><line x1="0" y1="'+(h-10)+'" x2="'+w+'" y2="'+(h-10)+'" stroke="#94a3b8"/><polyline points="'+poly+'" fill="none" stroke="#2563eb" stroke-width="2.5" vector-effect="non-scaling-stroke"/></svg>';
  const months={};for(const z of points)months[z.date.slice(0,7)]=Number(z.equity);
  let prev=1000000;
  by("researchCapacityMonths").innerHTML=Object.entries(months).map(([month,now])=>{const ret=100*(now/prev-1);prev=now;return '<tr><td>'+e(month)+'</td><td>'+perf(ret)+'</td></tr>';}).join("");
  by("researchCapacityStatus").textContent=points.length+"個交易日，完整訂單 "+(m.transactions||[]).length+" 筆。";
 }catch(err){if(token!==extended00675Token||activeArchive!=="extended00675")return;by("researchCapacityStatus").textContent="完整資金曲線載入失敗："+err.message;by("researchCapacityCurve").innerHTML="";}
}
by("researchArchiveRows").addEventListener("click",ev=>{
 const row=ev.target.closest("tr[data-extended00675]");if(row)selectExtended00675(row.dataset.extended00675);
});
document.querySelectorAll("[data-archive]").forEach(b=>b.addEventListener("click",()=>archive(b.dataset.archive)));
})();
