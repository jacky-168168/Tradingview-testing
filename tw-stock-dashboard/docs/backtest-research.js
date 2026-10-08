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
 legacy:'<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/h1_2026.json">H1 歷史 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="./data/research/model_execution_2026/h2_2026.json">H2 歷史 JSON ↗</a>　<a class="research-link" target="_blank" rel="noopener" href="https://github.com/jacky-168168/Tradingview-testing/blob/research/h-v5-limit-pullback-2026/tw-stock-dashboard/H_2026_research_consolidated_H2_H5.md">H2～H5 原始研究報告 ↗</a>'};
const e=x=>String(x==null?"":x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const n=(v,d=2)=>v==null||!Number.isFinite(Number(v))?"—":Number(v).toFixed(d);
const pct=(v,d=2)=>v==null?"—":n(v,d)+"%";
const clr=v=>v==null?"":Number(v)>=0?"research-positive":"research-negative";
const perf=v=>'<span class="'+clr(v)+'">'+pct(v,3)+'</span>';
const type=x=>x==="ma"?"B 均線觸價":"A 固定下跌";
const full=x=>names[x]||x;
let main=null,h5=null,g=null,loading=null,current=null,activeArchive="g",modelTrades=null,tradeIdentity="",run=0,tradePage=0;
async function get(path){const u=path+"?v=20261009a",r=await fetch(u,{cache:"no-cache"});if(!r.ok)throw Error("資料 HTTP "+r.status+"："+path);return r.json();}
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
   const [gResult,hResult]=await Promise.allSettled([get(rootpath+"g_ladder_vs_ma_2026.json"),get(rootpath+"h5_ladder_2026.json")]);
   g=gResult.status==="fulfilled"?gResult.value:null;h5=hResult.status==="fulfilled"?hResult.value:null;
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
by("researchRefresh").addEventListener("click",()=>{main=null;h5=null;g=null;current=null;loading=null;load();});
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
 if(which==="g"){
  head.innerHTML="<tr><th>期限</th><th>進場方式</th><th>開倉</th><th>+7%達標</th><th>停損率</th><th>預留資金淨報酬</th></tr>";
  note.textContent="先前 G_DOUBLE_PERSIST Top3 兩種加碼法對照；與17模型比較的一致範圍，但獨立執行的歷史歸檔。";
  tbody.innerHTML=g?.statistics?Object.entries(g.statistics).flatMap(([h,ms])=>Object.entries(ms).map(([m,x])=>'<tr><td>'+e(h)+'D</td><td>'+type(m)+'</td><td>'+n(x.filled,0)+'</td><td>'+pct(x.takeProfitPct)+'</td><td>'+pct(x.stopPct)+'</td><td>'+perf(x.avgNetOnReservedPct)+'</td></tr>')).join(""):'<tr><td colspan="6">研究檔案未載入</td></tr>';
 }else if(which==="h"){
  head.innerHTML="<tr><th>期限</th><th>首筆折價</th><th>開倉</th><th>+7%達標</th><th>停損率</th><th>已投入資金淨報酬</th><th>預留資金淨報酬</th></tr>";
  note.textContent="H5 的固定突破選股不變，測試首筆限價-2%、-2.5%、-3%，之後4筆每下跌首筆成交價2%加碼。此研究的首筆委託僅下一交易日有效，與上方17模型5日等待版不同，不可直接同比。";
  tbody.innerHTML=h5?.results?Object.entries(h5.results).flatMap(([h,discount])=>Object.entries(discount).map(([off,s])=>'<tr><td>'+e(h)+'D</td><td>-'+e(off)+'%</td><td>'+n(s.filled,0)+'</td><td>'+pct(s.targetHitPct)+'</td><td>'+pct(s.stopHitPct)+'</td><td>'+perf(s.avgNetOnDeployedPct)+'</td><td>'+perf(s.avgNetOnFiveTrancheBudgetPct)+'</td></tr>')).join(""):'<tr><td colspan="7">研究檔案未載入</td></tr>';
 }else{
  head.innerHTML="<tr><th>版本</th><th>方法</th><th>成交</th><th>+7%停利率</th><th>每筆平均淨報酬</th><th>備註</th></tr>";
  note.textContent="原始 H1～H5：5日內 +7% 毛停利；H1 停損 -4%，H2～H5 停損 -3.5%；不可直接和新版五段加碼、-15% 停損的命中率比較。";
  tbody.innerHTML=hLegacy.map(x=>'<tr>'+x.map((v,i)=>'<td>'+((i===3||i===4)?e(v)+"%":e(v))+'</td>').join("")+'</tr>').join("");
 }
}
document.querySelectorAll("[data-archive]").forEach(b=>b.addEventListener("click",()=>archive(b.dataset.archive)));
})();
