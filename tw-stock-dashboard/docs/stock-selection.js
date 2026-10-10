var DATA=null,MODEL="G",TABLE_COMPACT=true;
function N(x,n){var v=Number(x);return Number.isFinite(v)?v.toFixed(n==null?2:n):"--"}
function P(x,n){return Number.isFinite(Number(x))?N(x,n==null?2:n)+"%":"--"}
function C(x){return Number(x)>=0?"pos":"neg"}
function esc(x){return String(x==null?"":x).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function tvStockLink(x){var code=String(x.code||"").trim().toUpperCase(),market=String(x.market||"").trim(),ex=market==="上市"?"TWSE":market==="上櫃"?"TPEX":"",label=esc(code+" "+(x.name||""));if(!ex||!/^[0-9A-Z]{4,8}$/.test(code))return label;var symbol=ex+":"+code;return '<a class="tv-link" href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(symbol)+'" target="_blank" rel="noopener noreferrer" title="在 TradingView 開啟 '+esc(symbol)+'">'+label+'</a>'}
function taipeiDate(){return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
function dayInfo(){var d=String(DATA&&DATA.dataDate||DATA&&DATA.risk&&DATA.risk.date||'');var today=taipeiDate();var weekend=[0,6].includes(new Date().getDay());var label=d===today?'📅 '+d+'｜當日交易日資料':(weekend?'⏸ 週末休市｜':'⏸ 尚無今日交易日資料｜')+'最近交易日 '+(d||'未知')+'（非即時訊號）';return {d:d,today:today,weekend:weekend,isCurrent:d===today,label:label}}
function applyTableMode(){
var isG=(MODEL==="G"||MODEL==="G Pro"),gCols=new Set([0,1,3,4,6,7,9,10,13,14,15,17,18,19,20,21]),gHiddenCols=new Set([8,16]),normalCols=new Set([0,1,3,4,5,6,9,11,12,13,14,15,16,17]);
stockTable.classList.toggle("compact",TABLE_COMPACT);layoutToggle.textContent=TABLE_COMPACT?"▤ 完整欄位":"▥ 精簡欄位";layoutToggle.setAttribute("aria-pressed",TABLE_COMPACT?"true":"false");
var heads=Array.from(stockTable.querySelectorAll("thead th"));heads[13].textContent=isG?"外資買賣超":"外資買超";heads[14].textContent=isG?"投信買賣超":"投信買超";
heads.forEach(function(h,i){var isExtra=i>=5&&i<=8,eff=!isG&&i>8?i-4:i,hide=(isG&&gHiddenCols.has(i))||(!isG&&isExtra)||(TABLE_COMPACT&&!(isG?gCols:normalCols).has(eff));h.style.display=hide?"none":""});
tb.querySelectorAll("tr").forEach(function(tr){
 var cells=Array.from(tr.cells);
 if(cells.length===1&&cells[0].hasAttribute("colspan")){cells[0].colSpan=TABLE_COMPACT?(isG?gCols.size:normalCols.size):(isG?20:18);return}
 cells.forEach(function(cell,i){cell.style.display=(isG&&gHiddenCols.has(i))||(TABLE_COMPACT&&!(isG?gCols:normalCols).has(i))?"none":""})
});
tableHint.textContent=isG?(TABLE_COMPACT?"G 精簡模式：保留分數、持續度、SAR、現價、外資／投信買賣超、RS20、5D／20D、趨勢與訊號；按「完整欄位」查看其他資料。":"G 完整模式：3D／18D 和 RVOL 欄位仍不顯示（選股資料及判斷保留）；可向右捲動。"):(TABLE_COMPACT?"精簡模式：保留分數、SAR、現價、資金、RS20、RVOL、5D／20D、趨勢與訊號；按「完整欄位」查看全部。":"完整模式：已顯示所有欄位，表格可向右捲動；左側 Rank／股票名稱固定。");
}
function renderModelNote(){
var r=DATA&&DATA.risk||{},score=r.score==null?"—":r.score,fg=r.fGate||{},f2g=r.f2Gate||{},gs=DATA&&DATA.gSelection||null,notes={
A:"A 多因子：上市＋上櫃｜股本＜500億元、股價≥10元、成交額≥1億元｜5D/20D 動能＋RVOL 量能＋均線趨勢＋突破位置＋RS20＋法人＋ATR 波動度綜合評分｜SAR 輔助同分排序｜取前20檔。",
D:"D 技術強勢：上市＋上櫃｜股本＜500億元、股價≥10元｜正式條件：日成交量＞2,000萬股、RVOL10＞1.2、10日漲幅＞0%、單日波幅＞10%｜正式優先取前20檔；不足由成交額≥1億元的次級高分候補補足｜量能、動能、EMA 趨勢、RS20、突破位置、法人計分。",
F:"F 固定大盤濾網＝D 技術強勢＋Risk Score≥60 放行；唯一例外：Strong Bottom Reversal｜正式 D 優先、候補補足20檔｜目前大盤分數："+score+"｜濾網："+(fg.allowed?"放行":"阻擋")+"（"+(fg.reason||"尚未分析")+"）。",
F2:"F2 動態大盤濾網＝D 技術強勢＋Risk Score≥60 進場、≥55 維持已開啟狀態｜Strong Bottom Reversal 可例外放行｜Top Reversal Attempt / Strong Top Reversal 或 Extreme Overbought 阻擋｜目前大盤分數："+score+"｜濾網："+(f2g.allowed?"放行":"阻擋")+"（"+(f2g.reason||"尚未分析")+"）。"
};
gNote.textContent=MODEL==="G Pro"?"G Pro：只檢查原G Top3，要求20D動能前25%、均線斜率前20%、成交額前25%、過去10天至少2次進原G Top20、相對量≥1.3、EMA20＞EMA60、收盤在EMA20上方且距離≤15%。未過則不選；此為嚴格選股，非回測勝率保證。":(MODEL==="G"||MODEL==="G Pro")?(gs?"G：最新完整日K "+gs.dataDate+"｜3D＋18D 前高雙突破｜前10日原版 G Top20 持續度加分（最高7分）｜可用歷史 "+(gs.pocketSnapshotsFound||0)+"/10"+(gs.pocketWarmup?"｜持續度建檔中":"")+"｜盤中僅更新現價，不當成 BOTTOM／TOP 觸發":"⚠ 尚未產生每日 G 訊號，請按「GitHub 更新」執行 full 完整更新；不會把舊的 2026 回測清單冒充今日名單。"):(notes[MODEL]||"尚未設定模型說明");
}
function renderTable(){
var xs=DATA&&DATA.models&&DATA.models[MODEL]||[],isG=(MODEL==="G"||MODEL==="G Pro"),gs=DATA&&DATA.gSelection||null;
tabG.classList.toggle("on",MODEL==="G");tabGPro.classList.toggle("on",MODEL==="G Pro");tabD.classList.toggle("on",MODEL==="D");tabF.classList.toggle("on",MODEL==="F");tabF2.classList.toggle("on",MODEL==="F2");tabA.classList.toggle("on",MODEL==="A");

modelTitle.textContent=MODEL==="G Pro"?"G Pro 嚴格強勢突破排行":isG?"G 雙突破＋強勢持續度排行":MODEL==="D"?"D 主模型排行":MODEL==="F"?"F 固定濾網排行":MODEL==="F2"?"F2 動態濾網排行":"A 備用模型排行";
var strict=xs.filter(function(x){return x.strictPass===true}).length;
if(isG){
var candidates=MODEL==="G Pro"?3:gs&&gs.doubleBreakCandidates;
count.textContent=MODEL==="G Pro"?xs.length+" 檔｜原G Top3 嚴格確認":xs.length+" 檔｜雙突破候選 "+(candidates==null?"—":candidates)+" 檔";
renderModelNote();
}else{count.textContent=MODEL==="A"?xs.length+" 檔":xs.length+" 檔｜嚴格 "+strict+" 檔";renderModelNote()}
if(!xs.length){tb.innerHTML='<tr><td colspan="'+(isG?20:18)+'" style="text-align:center;padding:40px">'+(MODEL==="G Pro"?"原G Top3 今日無股票通過 G Pro 嚴格條件，正常空訊號。":isG?(gs?"此交易日沒有通過 G 雙突破的股票，屬正常空訊號；不會改用回測舊清單。":"⚠ G 每日資料尚未更新，請執行 GitHub 完整更新。"):"尚無資料")+'</td></tr>';applyTableMode();return}
tb.innerHTML=xs.map(function(x,i){
var cp=x.currentPrice!=null?N(x.currentPrice):N(x.close),chg=x.currentPct!=null?' <span class="'+C(x.currentPct)+'">('+(Number(x.currentPct)>=0?"+":"")+N(x.currentPct)+'%)</span>':"";
var extra=isG?'<td>'+N(x.gScore)+'</td><td title="加分 +'+N(x.gExtra)+'"><b>'+N((x.persistence||{}).strength,1)+'</b> <span class="sub">+'+N(x.gExtra)+'</span></td><td>'+(x.gPast10==null?"—":x.gPast10)+'/10 <span class="sub">連'+(x.gStreak||0)+'天</span></td><td><b>'+(x.gBreak3?"✓":"—")+' 3D / '+(x.gBreak18?"✓":"—")+' 18D</b></td>':"";
return '<tr><td><b>'+(i+1)+'</b></td><td class="stock">'+tvStockLink(x)+'</td><td>'+esc(x.market)+'</td><td class="theme" title="'+esc(x.theme||"")+'">'+esc(x.theme||"—")+'</td><td class="score">'+N(x.total,1)+'</td>'+extra+'<td class="sar">'+esc(x.sarText||"—")+'</td><td>'+cp+chg+'</td><td>'+N(x.capitalB)+'</td><td>'+N(x.turnoverB)+'</td><td class="'+C(x.foreignToday)+'">'+N(x.foreignToday,0)+'</td><td class="'+C(x.trustToday)+'">'+N(x.trustToday,0)+'</td><td class="'+C(x.rs20)+'">'+P(x.rs20)+'</td><td>'+N(x.rvol)+'</td><td class="'+C(x.ret5)+'">'+P(x.ret5)+'</td><td class="'+C(x.ret20)+'">'+P(x.ret20)+'</td><td class="'+C(x.breakoutPct)+'">'+P(x.breakoutPct)+'</td><td class="'+C(x.ma20Slope)+'">'+P(x.ma20Slope)+'</td><td>'+esc(x.signal||"")+'</td></tr>'
}).join("");applyTableMode()
}
function renderMeta(){if(!DATA)return;var s="資料日 "+(DATA.dataDate||"--")+" ｜ 完整更新 "+(DATA.generatedAt||"--");if(DATA.intradayUpdatedAt)s+=" ｜ 盤中快刷 "+DATA.intradayUpdatedAt+" ("+(DATA.intradayQuoteOk||0)+"/"+(DATA.intradayUniverse||0)+")";s+=" ｜ 股票池 "+(DATA.universeCount||0)+" ｜ K成功 "+(DATA.historyOk||0)+" ｜ 錯誤 "+(DATA.historyErrors||0);meta.textContent=s;var d=new Date(DATA.generatedAt),last=dayInfo(),days=Math.round((new Date(last.today+"T12:00:00+08:00")-new Date(last.d+"T12:00:00+08:00"))/86400000),isStale=Number.isFinite(d.getTime())&&(Date.now()-d.getTime()>20*3600*1000)&&(last.isCurrent||days>=5);staleWarning.style.display=isStale?"block":"none";if(isStale)staleWarning.textContent="⚠ 最近交易日資料為 "+(last.d||"未知")+"，已超過合理更新期間，請檢查 GitHub Actions。";}
async function load(){loading.classList.add("show");try{var r=await fetch("./data/latest.json?"+Date.now(),{cache:"no-store"});if(!r.ok)throw new Error("HTTP "+r.status);DATA=await r.json();renderTable();renderMeta()}catch(e){meta.textContent="載入失敗："+e.message;tb.innerHTML='<tr><td colspan="18" style="text-align:center;padding:40px;color:#dc2626">資料載入失敗，請稍後重新載入</td></tr>'}finally{loading.classList.remove("show")}}
layoutToggle.onclick=function(){TABLE_COMPACT=!TABLE_COMPACT;applyTableMode()};tabG.onclick=function(){MODEL="G";renderTable()};tabGPro.onclick=function(){MODEL="G Pro";renderTable()};tabD.onclick=function(){MODEL="D";renderTable()};tabF.onclick=function(){MODEL="F";renderTable()};tabF2.onclick=function(){MODEL="F2";renderTable()};tabA.onclick=function(){MODEL="A";renderTable()};reload.onclick=load;load();setInterval(load,90000);