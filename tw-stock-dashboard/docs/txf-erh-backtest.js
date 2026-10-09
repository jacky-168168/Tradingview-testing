(function(){"use strict";
const $=id=>document.getElementById(id),root="./data/research/txf_extreme_reversal_2m_5m_2025_2026/";
const escape=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=(n,d=2)=>n==null||!Number.isFinite(Number(n))?"—":Number(n).toLocaleString("zh-TW",{minimumFractionDigits:d,maximumFractionDigits:d});
const money=n=>'<span class="'+(Number(n)>=0?"good":"bad")+'">'+fmt(n,0)+'</span>';
const pct=n=>'<span class="'+(Number(n)>=0?"good":"bad")+'">'+fmt(n,2)+'%</span>';
const strategy={
 long_top:"BOTTOM 做多 → TOP 出場",
 strong_top:"Trend70＋BOTTOM 做多 → TOP 出場",
 long_atr:"BOTTOM 做多＋ATR2 停損／3R 停利",
 strong_atr:"Trend70＋BOTTOM＋ATR2 停損／3R 停利",
 both_top:"BOTTOM 做多／TOP 做空，反向出場",
 both_atr:"BOTTOM 做多／TOP 做空，ATR 停損停利"
};
const exitNames={day_flat:"當日日盤收盤平倉",opposite_signal:"反向訊號／反手",ATR2_stop:"2 ATR 停損（含 TP1 保本）",TP3_hit:"3R 目標停利"};
let data=null,selection=null,rows=[],caseId=0;
const fetchJson=async p=>{const r=await fetch(p+"?v=20261009txf2",{cache:"no-cache"});if(!r.ok)throw Error("研究資料 "+r.status);return r.json();};
function windowFor(y){return y==="2025"?["2025-01-02","2025-12-31"]:y==="2026"?["2026-01-01","2026-08-31"]:["2025-01-02","2026-08-31"]}
function refresh(){
 const p=windowFor($("period").value);
 rows=data.results.filter(x=>x.segment[0]===p[0]&&x.segment[1]===p[1]);
 const sort=$("sort").value;
 rows.sort(sort==="dd"?(a,b)=>b.maxDrawdownPct-a.maxDrawdownPct:
   sort==="pf"?(a,b)=>(b.profitFactor??0)-(a.profitFactor??0):
   (a,b)=>b.netPnlTWD-a.netPnlTWD);
 const full=x=>x.timeframeMin+"m_"+x.mode;
 $("rankRows").innerHTML=rows.map(x=>
  '<tr data-case="'+escape(full(x))+'"'+(selection===full(x)?' class="selected"':"")+'>'+
  '<td><b>'+escape(strategy[x.mode]||x.mode)+'</b></td><td>'+x.timeframeMin+' 分</td>'+
  '<td>'+fmt(x.trades,0)+'</td><td>'+fmt(x.winRatePct,2)+'%</td><td>'+fmt(x.profitFactor,3)+'</td>'+
  '<td>'+money(x.avgNetTWD)+'</td><td>'+money(x.netPnlTWD)+'</td><td>'+pct(x.returnPct)+'</td><td>'+pct(x.maxDrawdownPct)+'</td></tr>').join("");
 const same=rows.find(x=>full(x)===selection);
 if(same)select(same);else select(rows.find(x=>x.timeframeMin===2&&x.mode==="both_top")||rows[0]);
}
function svgFor(xs){
 if(!xs?.length)return "<p>無每日資金曲線。</p>";
 const w=980,h=275,pL=68,pR=13,pT=21,pB=30;
 const vals=xs.map(x=>Number(x[1])),lo=Math.min(...vals,1e6),hi=Math.max(...vals,1e6),span=Math.max(1,hi-lo);
 const xx=i=>pL+(w-pL-pR)*i/Math.max(1,xs.length-1);
 const yy=v=>pT+(hi-v)/span*(h-pT-pB);
 let grid="";
 for(let i=0;i<=4;i++){const val=lo+span*i/4,y=yy(val);grid+='<line x1="'+pL+'" x2="'+(w-pR)+'" y1="'+y+'" y2="'+y+'" stroke="#e2e8f0"/><text font-size="12" text-anchor="end" x="'+(pL-8)+'" y="'+(y+4)+'" fill="#64748b">'+escape(fmt(val/10000,0))+'萬</text>';}
 const path=xs.map((a,i)=>xx(i).toFixed(2)+","+yy(Number(a[1])).toFixed(2)).join(" ");
 const mid=Math.floor((xs.length-1)/2);
 const label=[0,mid,xs.length-1].map((i,j)=>'<text font-size="12" text-anchor="'+(j===0?"start":j===1?"middle":"end")+'" x="'+xx(i)+'" y="'+(h-8)+'" fill="#64748b">'+escape(xs[i][0])+'</text>').join("");
 return '<svg viewBox="0 0 '+w+' '+h+'" role="img" aria-label="新臺幣每日日終帳戶權益">'+grid+
  '<polyline fill="none" stroke="#2563eb" stroke-width="2.3" points="'+path+'"/>'+label+'</svg>';
}
function select(x){
 selection=x.timeframeMin+"m_"+x.mode;
 $("rankRows").querySelectorAll("[data-case]").forEach(t=>t.classList.toggle("selected",t.dataset.case===selection));
 $("detailName").textContent=x.timeframeMin+" 分 K｜"+strategy[x.mode];
 $("detailStats").innerHTML=[["淨損益（NT$）",money(x.netPnlTWD)],["報酬率",pct(x.returnPct)],["最大回撤",pct(x.maxDrawdownPct)],["完整交易",fmt(x.trades,0)]].map(([k,v])=>'<div class="stat"><small>'+escape(k)+'</small><strong>'+v+'</strong></div>').join("");
 $("detailCaption").textContent="回測："+x.segment.join(" ～ ")+"｜勝率 "+fmt(x.winRatePct,2)+"%｜PF "+fmt(x.profitFactor,3)+"｜單筆平均淨損益 "+fmt(x.avgNetTWD,0)+" 元。";
 $("curveChart").innerHTML="<p class='muted'>正在讀取每日曲線…</p>";
 $("curveMeta").textContent="";
 $("tradeRows").innerHTML="";
 $("tradeStats").textContent="正在讀取完整交易紀錄…";
 $("rawCase").href=root+"cases/"+selection+".json";
 $("studySource").href=data.provenance.sourceSummary;
 loadDetail(x,++caseId);
}
async function loadDetail(x,token){
 try{
  const id=x.timeframeMin+"m_"+x.mode;
  const v=await fetchJson(root+"cases/"+id+".json");
  if(token!==caseId)return;
  const period=x.segment;
  const dates=v.dailyEquityTWD.filter(t=>t[0]>=period[0]&&t[0]<=period[1]);
  const txs=v.simulatedTrades.filter(t=>t.exit.slice(0,10)>=period[0]&&t.exit.slice(0,10)<=period[1]);
  $("curveChart").innerHTML=svgFor(dates);
  $("curveMeta").textContent="此圖為當日日終帳戶淨值（新臺幣），不顯示日內最高或最低。表格最大回撤來自完整回測，不是以這張日終圖重新計算。";
  $("tradeRows").innerHTML=txs.map(t=>'<tr><td>'+escape(t.entry)+'</td><td>'+escape(t.exit)+'</td><td>'+((t.dir>0)?"做多":"做空")+'</td><td>'+money(t.netTWD)+'</td><td>'+escape(exitNames[t.reason]||t.reason)+'</td></tr>').join("")||'<tr><td colspan="5">本段期間沒有交易</td></tr>';
  $("tradeStats").textContent=txs.length+" 筆模擬完整交易，已扣除假設的手續費、交易稅與滑價；用當根 K 棒 OHLC 判斷停損順序採保守假設。";
 }catch(e){if(token!==caseId)return;$("curveChart").textContent="載入曲線失敗："+e.message;$("tradeStats").textContent="交易紀錄載入失敗："+e.message;}
}
$("rankRows").addEventListener("click",e=>{
 const tr=e.target.closest("[data-case]");if(!tr)return;
 const z=rows.find(x=>tr.dataset.case===x.timeframeMin+"m_"+x.mode);if(z)select(z);
});
$("period").addEventListener("change",refresh);
$("sort").addEventListener("change",refresh);
(async()=>{
 try{
  data=await fetchJson(root+"summary.json");
  if(data.version!=="TXF_EXTREME_REVERSAL_TREND70_2M_5M_V1")throw Error("版本檢查失敗");
  $("sourceMeta").textContent="研究資料 "+data.data.start+" ～ "+data.data.end+"｜2024 年預熱｜TXF 1 口固定交易、初始 100 萬元、點值 200 元、每側手續費 60 元及滑價 1 點。資料建立："+data.generated+"。";
  const a=data.data.dataQuality;$("signalCounts").textContent="2 分：BOTTOM "+a[0].bottoms+"、TOP "+a[0].tops+"、強勢 BOTTOM "+a[0].strongBottoms+"；5 分：BOTTOM "+a[1].bottoms+"、TOP "+a[1].tops+"、強勢 BOTTOM "+a[1].strongBottoms;
  $("riskNotes").textContent="原 Pine Trend70 只附加在 BOTTOM；同一組參數回測 2 分與 5 分，並比較原訊號、Trend70、ATR 停損停利與雙向反手。"+data.evaluationWarnings.slice(0,3).join(" ");
  refresh();
 }catch(err){$("sourceMeta").textContent="載入失敗："+err.message;}
})();
})();