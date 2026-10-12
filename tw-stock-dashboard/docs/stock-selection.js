var DATA=null,MODEL="G",TABLE_COMPACT=false,G_INTRADAY=null,G_INTRADAY_STATUS=null;
function currentLiveG(){var g=G_INTRADAY;if(!g||g.quality!=="intraday-provisional-allmarket"||!Array.isArray(g.rows)||g.asOfDate!==taipeiDate())return null;if(String(DATA&&DATA.dataDate||"")>=g.asOfDate||!g.sourceCloseDate||g.sourceCloseDate!==DATA.dataDate)return null;var age=Date.now()-new Date(g.publishedAt).getTime();if(!Number.isFinite(age)||age<0||age>110*60*1000)return null;if(G_INTRADAY_STATUS&&G_INTRADAY_STATUS.status==="unavailable"&&Date.parse(G_INTRADAY_STATUS.checkedAt)>Date.parse(g.publishedAt))return null;return g;}
function N(x,n){if(x==null||x==="")return "--";var v=Number(x);return Number.isFinite(v)?v.toFixed(n==null?2:n):"--"}
function P(x,n){return Number.isFinite(Number(x))?N(x,n==null?2:n)+"%":"--"}
function C(x){return Number(x)>=0?"pos":"neg"}
function esc(x){return String(x==null?"":x).replace(/[&<>"']/g,function(c){return{"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function tvStockLink(x){var code=String(x.code||"").trim().toUpperCase(),market=String(x.market||"").trim(),ex=market==="上市"?"TWSE":market==="上櫃"?"TPEX":"",label=esc(code+" "+(x.name||""));if(!ex||!/^[0-9A-Z]{4,8}$/.test(code))return label;var symbol=ex+":"+code;return '<a class="tv-link" href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(symbol)+'" target="_blank" rel="noopener noreferrer" title="在 TradingView 開啟 '+esc(symbol)+'">'+label+'</a>'}
function taipeiDate(){return new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
function dayInfo(){var d=String(DATA&&DATA.dataDate||DATA&&DATA.risk&&DATA.risk.date||'');var today=taipeiDate();var weekend=[0,6].includes(new Date().getDay());var label=d===today?'📅 '+d+'｜當日交易日資料':(weekend?'⏸ 週末休市｜':'⏸ 尚無今日交易日資料｜')+'最近交易日 '+(d||'未知')+'（非即時訊號）';return {d:d,today:today,weekend:weekend,isCurrent:d===today,label:label}}
var VIEW_PREF="",THEME_FILTER="",EXPANDED_STOCK="";
try{VIEW_PREF=localStorage.getItem("tw_selection_view_v1")||""}catch(_){}
TABLE_COMPACT=VIEW_PREF==="simple"?true:VIEW_PREF==="detail"?false:window.matchMedia("(max-width:760px)").matches;
var STOCK_SIMPLE_HEAD='<tr><th>排名</th><th>股票／題材</th><th>強度</th><th>現價／漲跌</th></tr>';
var L_SIMPLE_HEAD='<tr><th>排名</th><th>股票／題材</th><th>週K／週D</th><th>訊號收盤</th></tr>';
var L_TABLE_HEAD='<tr><th>Rank</th><th>股票</th><th>市場</th><th>題材</th><th>週K</th><th>週D</th><th>交叉日期</th><th>收盤價</th><th>最新營收月份</th><th>營收 MoM</th><th>營收 YoY</th><th>營收可用日</th></tr>';
var N_SIMPLE_HEAD='<tr><th>排名</th><th>股票</th><th>成長分數</th><th>收盤價</th></tr>';
function themeButton(theme){var t=String(theme||"").trim();return t?'<button type="button" class="theme-pick" data-theme="'+esc(t)+'" aria-pressed="'+(THEME_FILTER===t?'true':'false')+'" title="篩選 '+esc(t)+' 題材">'+esc(t)+'</button>':'<span class="simple-secondary">題材未分類</span>'}
function filterBar(){var bar=document.getElementById("themeFilterBar");if(!bar)return;bar.hidden=!THEME_FILTER;document.getElementById("themeFilterLabel").textContent=THEME_FILTER?"🔎 題材："+THEME_FILTER+"（同時篩選排行及重複上榜）":""}
function applyTableMode(){
 var isN=MODEL==="N",isL=MODEL==="L",simple=TABLE_COMPACT;
 var official=document.getElementById("officialStockTable");official.classList.toggle("compact",simple);official.classList.toggle("simple-mode",simple);official.tHead.innerHTML=simple?STOCK_SIMPLE_HEAD:NORMAL_G_TABLE_HEAD.replace("現價 / 收盤","正式收盤價");
 stockTable.classList.toggle("compact",simple);stockTable.classList.toggle("simple-mode",simple);
 stockTable.tHead.innerHTML=simple?(isN?N_SIMPLE_HEAD:isL?L_SIMPLE_HEAD:STOCK_SIMPLE_HEAD):(isN?N_TABLE_HEAD:isL?L_TABLE_HEAD:(MODEL==="G"||MODEL==="G Pro"?NORMAL_G_TABLE_HEAD:NORMAL_NON_G_TABLE_HEAD));
 layoutToggle.textContent=simple?"▤ 詳細模式":"▥ 簡單模式";
 document.getElementById("modeBadge").textContent=simple?"簡單模式":"詳細模式";
 layoutToggle.setAttribute("aria-pressed",simple?"true":"false");
 layoutToggle.setAttribute("aria-label",simple?"切換詳細模式，顯示全部欄位":"切換簡單模式，無需左右滑動");
 document.getElementById("repeatPanel").classList.toggle("repeat-simple",simple);
 tableHint.textContent=simple?(isN?"N 簡單模式：基本面歷史訊號，不是即時選股。":"簡單模式：股票＋題材、10日入選／SAR、現價及漲跌幅；點選股票以外的空白位置可展開明細，點題材可篩選。"):"詳細模式：顯示所有原始欄位，可左右捲動；點題材可篩選。";
 filterBar();
}
function simpleMetric(name,value){return '<div><dt>'+esc(name)+'</dt><dd>'+value+'</dd></div>'}
function renderSimpleStock(x,i,isG,live,official){
 var theme=x.theme||"",key=(official?"official|":"")+String(x.market||"")+"|"+String(x.code||""),open=EXPANDED_STOCK===key;
 var px=official?N(x.close):(live&&/midpoint|one-sided/.test(x.intradayPriceSource||"")?"≈":"")+(x.currentPrice!=null?N(x.currentPrice):N(x.close));
 var pctSource=official?x.dayRet:x.currentPct;
 var pct=pctSource==null?'<span class="simple-secondary">漲跌未提供</span>':'<span class="simple-pct '+C(pctSource)+'">'+(Number(pctSource)>=0?"+":"")+N(pctSource)+'%</span>';
 var strength=isG?'<b>10日 '+(x.gPast10==null?"—":esc(x.gPast10))+'/10</b>':'<b>總分 '+N(x.total,1)+'</b>';
 var cells=[simpleMetric("市場",esc(x.market||"—")),simpleMetric("總分",N(x.total,1)),simpleMetric("SAR",esc(x.sarText||"—")),simpleMetric("題材",esc(theme||"—")),simpleMetric("外資買賣超",N(x.foreignToday,0)),simpleMetric("投信買賣超",N(x.trustToday,0)),simpleMetric("RS20",P(x.rs20)),simpleMetric("RVOL",N(x.rvol)),simpleMetric("5D",P(x.ret5)),simpleMetric("20D",P(x.ret20)),simpleMetric("股本",N(x.capitalB)),simpleMetric("成交額",N(x.turnoverB)),simpleMetric("距20日高",P(x.breakoutPct)),simpleMetric("MA20斜率",P(x.ma20Slope)),simpleMetric("訊號",esc(x.signal||"—"))];
 if(isG){cells.splice(2,0,simpleMetric("原G分",N(x.gScore)),simpleMetric("持續度",N((x.persistence||{}).strength,1)),simpleMetric("3D／18D",(x.gBreak3?"✓":"—")+"／"+(x.gBreak18?"✓":"—")))}
 return '<tr class="simple-stock-row" tabindex="0" aria-expanded="'+(open?"true":"false")+'" data-key="'+esc(key)+'"><td><b>'+(i+1)+'</b></td><td class="stock"><span class="simple-stock-name">'+tvStockLink(x)+'</span><span class="simple-stock-theme">'+themeButton(theme)+'</span></td><td>'+strength+'<span class="simple-secondary simple-sar">'+esc(x.sarText||"—")+'</span></td><td><span class="simple-price">'+esc(px)+'</span>'+pct+'</td></tr>'+(open?'<tr class="simple-detail-row"><td colspan="4"><dl class="simple-detail-grid">'+cells.join("")+'</dl></td></tr>':"");
}
function renderModelNote(){
var r=DATA&&DATA.risk||{},score=r.score==null?"—":r.score,fg=r.fGate||{},f2g=r.f2Gate||{},gs=DATA&&DATA.gSelection||null,notes={
A:"A 多因子：上市＋上櫃｜股本＜500億元、股價≥10元、成交額≥1億元｜5D/20D 動能＋RVOL 量能＋均線趨勢＋突破位置＋RS20＋法人＋ATR 波動度綜合評分｜SAR 輔助同分排序｜取前20檔。",
D:"D 技術強勢：上市＋上櫃｜股本＜500億元、股價≥10元｜正式條件：日成交量＞2,000萬股、RVOL10＞1.2、10日漲幅＞0%、單日波幅＞10%｜正式優先取前20檔；不足由成交額≥1億元的次級高分候補補足｜量能、動能、EMA 趨勢、RS20、突破位置、法人計分。",
F:"F 固定大盤濾網＝D 技術強勢＋Risk Score≥60 放行；唯一例外：Strong Bottom Reversal｜正式 D 優先、候補補足20檔｜目前大盤分數："+score+"｜濾網："+(fg.allowed?"放行":"阻擋")+"（"+(fg.reason||"尚未分析")+"）。",
F2:"F2 動態大盤濾網＝D 技術強勢＋Risk Score≥60 進場、≥55 維持已開啟狀態｜Strong Bottom Reversal 可例外放行｜Top Reversal Attempt / Strong Top Reversal 或 Extreme Overbought 阻擋｜目前大盤分數："+score+"｜濾網："+(f2g.allowed?"放行":"阻擋")+"（"+(f2g.reason||"尚未分析")+"）。"
};
var live=MODEL==="G"?currentLiveG():null;
if(live){var cov=live.coverage||{},ps=live.quotePriceSources||{},proxy=(ps["bid-ask-midpoint"]||0)+(ps["one-sided-high-bid"]||0)+(ps["one-sided-low-ask"]||0);gNote.textContent="🟠 G 盤中重新選股｜"+live.asOfDate+"｜更新 "+live.publishedAt+"｜全上市櫃即時有效報價 "+(cov.valid||0)+"/"+(cov.total||0)+"（其中 "+proxy+" 檔使用買賣委託價暫估）｜3D／18D 當日突破尚未收盤確認；現價標≈者不是實際成交價；法人、SAR 不提供假盤中數據，原版盤後G榜單未改動。";return;}
gNote.textContent=MODEL==="G Pro"?"G Pro：只檢查原G Top3，要求20D動能前25%、均線斜率前20%、成交額前25%、過去10天至少2次進原G Top20、相對量≥1.3、EMA20＞EMA60、收盤在EMA20上方且距離≤15%。未過則不選；此為嚴格選股，非回測勝率保證。":(MODEL==="G"||MODEL==="G Pro")?(gs?"G：最新完整日K "+gs.dataDate+"｜3D＋18D 前高雙突破｜前10日原版 G Top20 持續度加分（最高7分）｜可用歷史 "+(gs.pocketSnapshotsFound||0)+"/10"+(gs.pocketWarmup?"｜持續度建檔中":"")+"｜當日未取得有效盤中重選時僅更新原榜單現價；非 BOTTOM／TOP 觸發":"⚠ 尚未產生每日 G 訊號，請按「GitHub 更新」執行 full 完整更新；不會把舊的 2026 回測清單冒充今日名單。"):(notes[MODEL]||"尚未設定模型說明");
}
var N_ARCHIVE=null,N_SUMMARY=null,N_LOADING=false;
var NORMAL_TABLE_HEAD=document.getElementById("stockTable").tHead.innerHTML;
var NORMAL_G_TABLE_HEAD=NORMAL_TABLE_HEAD.replace("外資買超","外資買賣超").replace("投信買超","投信買賣超");
var NORMAL_NON_G_TABLE_HEAD=NORMAL_TABLE_HEAD.replace(/<th class="g-only">[\s\S]*?<\/th>/g,"");
var N_TABLE_HEAD='<tr><th>Rank</th><th>股票</th><th>市場</th><th>收盤價</th><th>EPS 累計年增</th><th>月營收 YoY</th><th>RS 全市場分位</th><th>距 52 週高點</th><th>成長動能分</th><th>EPS／營收最早可用日</th></tr>';
function toggleNView(show){
 stockTable.classList.toggle("stock-n-table",show);
 stockTable.tHead.innerHTML=show?N_TABLE_HEAD:NORMAL_TABLE_HEAD;
 stockTable.closest(".table-card").style.display="";
 nPanel.style.display=show?"block":"none";
 layoutToggle.style.display="";
 tableHint.style.display="";
}
async function loadNArchive(){
 if(N_LOADING)return;N_LOADING=true;
 try{
  var root="./data/research/n_canslim/";
  var results=await Promise.all(["picks","summary"].map(async function(kind){
   var r=await fetch(root+kind+".json?t="+Date.now(),{cache:"no-store"});
   if(!r.ok)throw new Error(kind+" 歷史研究尚未發布 ("+r.status+")");
   return await r.json();
  }));
  N_ARCHIVE=results[0];N_SUMMARY=results[1];
  if(N_ARCHIVE.version!==N_SUMMARY.version||N_SUMMARY.marketDays!==728||N_SUMMARY.modelCount!==16||!N_ARCHIVE.signalTop3)throw new Error("N 資料版本或回測日數不符");
  if(MODEL==="N")renderNTable();
 }catch(err){
  N_ARCHIVE=null;N_SUMMARY=null;
  if(MODEL==="N"){
   nStatus.textContent="⚠ N 尚無通過驗證的選股排行："+err.message;
   tb.innerHTML='<tr><td colspan="10" style="text-align:center;padding:28px">N 歷史選股資料無法載入；不顯示猜測的股票。</td></tr>';
   nLearned.textContent="請檢查 N 遞迴回測資料。";count.textContent="資料不可用";
  }
 }finally{N_LOADING=false}
}
function renderNTable(){
 if(MODEL!=="N")return;
 applyTableMode();
 if(!N_ARCHIVE||!N_SUMMARY){
  nStatus.textContent="⏳ 正在讀取 N 成長動能歷史排行…";
  tb.innerHTML='<tr><td colspan="'+(TABLE_COMPACT?4:10)+'" style="text-align:center;padding:28px">載入 N 歷史選股資料中…</td></tr>';
  count.textContent="讀取中";loadNArchive();return;
 }
 var raw=N_ARCHIVE.signalTop3||{},days=Object.keys(raw).sort(),last=days.length?days[days.length-1]:null;
 if(!last){nStatus.textContent="沒有任何可用的 N 歷史候選股";count.textContent="0 檔";tb.innerHTML='<tr><td colspan="10">N 歷史回測沒有合格候選。</td></tr>';return}
 var list=raw[last]||[],selected=N_SUMMARY.selected&&N_SUMMARY.selected.id||null;
 var leader=selected&&(N_ARCHIVE.modelDailyTop1||{})[selected]||{},selectedDays=Object.keys(leader).filter(function(d){return Array.isArray(leader[d])&&leader[d].length>0}).sort();
 var leaderDate=selectedDays.length?selectedDays[selectedDays.length-1]:null;
 var chosen=leaderDate?leader[leaderDate][0]:null;
 var mainDate=DATA&&DATA.dataDate||"",isOlder=mainDate&&last<mainDate;
 modelTitle.textContent="N｜基本面 × 成長動能排行";
 count.textContent=list.length+" 檔｜資料 "+last;
 tableHint.textContent="N 使用已發布的歷史因子 Top3，非盤中最新即時排行；與 G 等即時選股來源不同。點選股票可開啟 TradingView。";
 nStatus.textContent=(isOlder?"⚠ 資料晚於其他策略尚未更新｜":"📅 已驗證歷史選股｜")+"N 訊號日 "+last+"｜G等策略資料日 "+(mainDate||"—")+"｜全市場 "+N_SUMMARY.baseUniverse+" 檔｜"+(selected?"2025年驗證選定遞迴模型":"沒有通過2025驗證的模型");
 tb.innerHTML=list.map(function(z,i){
  var m=z.metrics||{},ex=z.market==="otc"?"TPEX":"TWSE",symbol=ex+":"+z.code,where=z.market==="otc"?"上櫃":"上市";
  var ratio=m.near52WeekHighPct==null?null:100-Number(m.near52WeekHighPct),isMl=(leaderDate===last&&chosen&&chosen.code===z.code);
  var name='<a class="tv-link" href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(symbol)+'" target="_blank" rel="noopener noreferrer">'+esc(z.code)+" "+esc(z.name)+'</a>'+(isMl?' <span class="badge" title="本日遞迴模型 Top1">Top1</span>':'');
  if(TABLE_COMPACT)return '<tr><td><b>'+(i+1)+'</b></td><td class="stock">'+name+'<span class="simple-secondary">歷史訊號 '+last+'</span></td><td class="score">'+N(z.factorScore,1)+'</td><td>'+N(z.close,2)+'</td></tr>';
  return '<tr><td><b>'+(i+1)+'</b></td><td class="stock">'+name+'</td><td>'+where+'</td><td>'+N(z.close,2)+'</td><td class="pos">'+P(m.epsYtdGrowthPct,1)+'</td><td>'+P(m.revenueYoYPct,1)+'</td><td>'+P(m.rsPercentile,1)+'</td><td>'+(ratio==null?"—":N(ratio,1)+"%")+'</td><td class="score">'+N(z.factorScore,1)+'</td><td>'+esc(m.epsAvailableFrom||"—")+'／'+esc(m.revAvailableFrom||"—")+'</td></tr>';
 }).join("")||'<tr><td colspan="10">最新歷史交易日沒有符合 N 條件的股票。</td></tr>';
 if(!selected)nLearned.textContent="2025年沒有通過驗證門檻的 N 遞迴 Top1 模型，因此不推薦事後最佳。";
 else if(!chosen)nLearned.textContent="已選擇模型 "+selected+"，但目前沒有已發布的 Top1 交易訊號。";
 else nLearned.textContent=leaderDate+"｜"+chosen.code+" "+chosen.name+"｜模型預估淨報酬 "+P(chosen.predictedNetPct,2)+"｜候選 "+chosen.candidatesRanked+" 檔｜EPS 年增 "+P(chosen.epsYtdGrowthPct,1)+"，營收年增 "+P(chosen.revenueYoYPct,1)+"｜這是歷史研究結果，不是今日買進建議。";
}
var L_ARCHIVE=null,L_SUMMARY=null,L_LOADING=false;
async function loadLArchive(){
 if(L_LOADING)return;L_LOADING=true;
 try{
  var root="./data/research/l_weekly_kd/";
  var response=await Promise.all(["latest","summary"].map(async function(kind){
   var r=await fetch(root+kind+".json?v="+Date.now(),{cache:"no-store"});
   if(!r.ok)throw new Error(kind+" 尚未完成 ("+r.status+")");
   return r.json();
  }));
  if(response[0]?.selection?.version!==response[1]?.version||response[0].selection.state!=="ready"||!response[1].statistics)throw new Error("L 訊號／回測版本或資料狀態不一致");
  L_ARCHIVE=response[0];L_SUMMARY=response[1];
 }catch(err){
  L_ARCHIVE=null;L_SUMMARY=null;
  if(MODEL==="L")lStatus.textContent="⚠ L 尚無經驗證的週KD＋營收選股資料："+err.message+"。不以 G／其他模型名單代替。";
 }finally{L_LOADING=false;if(MODEL==="L"&&L_ARCHIVE)renderLTable()}
}
function renderLStats(){
 var area=document.getElementById("lStats"),stats=L_SUMMARY?.statistics?.[document.getElementById("lScope").value];
 if(!stats){area.textContent="完整回測數據尚未發布";return}
 area.innerHTML=[1,2,3].map(function(h){
  var z=stats[String(h)]||{},p=z.avgNetPct;
  return '<div class="l-stats-card"><div class="l-h">'+h+'W｜'+(z.n||0)+' 筆</div><strong class="'+(p==null?"":C(p))+'">'+(p==null?"—":(p>=0?"+":"")+N(p,2)+"%")+'</strong><small>勝率 '+P(z.winRatePct,1)+'</small><small>中位數 '+P(z.medianNetPct,2)+'</small><small>賺錢平均 '+P(z.avgProfitPct,2)+'<br>賠錢平均 '+P(z.avgLossPct,2)+'</small></div>'
 }).join("");
}
function renderLTable(){
 if(MODEL!=="L")return;applyTableMode();
 modelTitle.textContent="L｜週KD<40黃金交叉＋已公告月營收增加";
 var area=document.getElementById("lPanel");area.style.display="block";
 if(!L_ARCHIVE||!L_SUMMARY){
  count.textContent="等待回測";tb.innerHTML='<tr><td colspan="'+(TABLE_COMPACT?4:12)+'" style="text-align:center;padding:24px">L 獨立全市場週KD與 MOPS 營收資料尚未發布，暫不顯示其他策略的股票。</td></tr>';
  document.getElementById("lStats").textContent="回測數據讀取中";if(!L_LOADING)void loadLArchive();return;
 }
 var z=L_ARCHIVE.selection,rows=Array.isArray(L_ARCHIVE.rows)?L_ARCHIVE.rows:[],mainDate=String(DATA?.dataDate||"");
 if(mainDate&&L_ARCHIVE.asOf>mainDate){lStatus.textContent="⚠ L 研究資料日晚於網站正式資料日，暫停展示。";count.textContent="資料日期不符";tb.innerHTML="";return}
 lStatus.textContent="L 週線訊號週 "+z.signalWeek+"｜全市場 "+z.marketUniverse+" 檔｜有效週K "+z.weeklyCovered+" 檔｜KD金叉<40 "+z.crossoverCount+" 檔｜營收正成長 "+z.strictCandidates+" 檔｜行情截至 "+L_ARCHIVE.asOf+"；不把未完成週線當金叉。";
 var selected=rows.filter(function(x){return !THEME_FILTER||String(x.theme||"").trim()===THEME_FILTER});
 count.textContent=selected.length+"／"+z.strictCandidates+" 檔（Top20）";
 gNote.textContent="L 規則：週KD(9,3,3)前週K≤D、本週K>D，且K<40與D<40；最新已公告月營收MoM>0%或YoY>0%其中一項成立。獨立選股，不加入G或大盤門檻。";
 renderLStats();
 tb.innerHTML=selected.map(function(x,i){
  var name=tvStockLink(x),th=themeButton(x.theme),kd=N(x.weekK,1)+"／"+N(x.weekD,1);
  if(TABLE_COMPACT)return '<tr><td><b>'+(i+1)+'</b></td><td class="stock">'+name+'<div>'+th+'</div><span class="simple-secondary">金叉 '+esc(x.signalDate)+'</span></td><td class="score">'+kd+'<span class="simple-secondary">MoM '+P(x.revenueMoMPct,1)+' / YoY '+P(x.revenueYoYPct,1)+'</span></td><td>'+N(x.close)+'</td></tr>';
  return '<tr><td><b>'+(i+1)+'</b></td><td class="stock">'+name+'</td><td>'+esc(x.market)+'</td><td>'+th+'</td><td class="score">'+N(x.weekK,2)+'</td><td class="score">'+N(x.weekD,2)+'</td><td>'+esc(x.signalDate)+'</td><td>'+N(x.close)+'</td><td>'+esc(x.revenueFiscal)+'</td><td class="'+C(x.revenueMoMPct)+'">'+P(x.revenueMoMPct,2)+'</td><td class="'+C(x.revenueYoYPct)+'">'+P(x.revenueYoYPct,2)+'</td><td>'+esc(x.revenueAvailableFrom)+'</td></tr>';
 }).join("")||'<tr><td colspan="'+(TABLE_COMPACT?4:12)+'" style="text-align:center;padding:26px">這個完成的交易週沒有同時符合 KD 金叉低於40及已公告營收正成長的股票。</td></tr>';
}
function renderOfficialDetailedRow(x,i){
var cp=N(x.close),chg=x.dayRet==null?"":' <span class="'+C(x.dayRet)+'">('+(Number(x.dayRet)>=0?"+":"")+N(x.dayRet)+'%)</span>';
var isG=true;
var extra=isG?'<td>'+N(x.gScore)+'</td><td title="加分 +'+N(x.gExtra)+'"><b>'+N((x.persistence||{}).strength,1)+'</b> <span class="sub">+'+N(x.gExtra)+'</span></td><td>'+(x.gPast10==null?"—":x.gPast10)+'/10 <span class="sub">連'+(x.gStreak||0)+'天</span></td><td><b>'+(x.gBreak3?"✓":"—")+' 3D / '+(x.gBreak18?"✓":"—")+' 18D</b></td>':"";
return '<tr><td><b>'+(i+1)+'</b></td><td class="stock">'+tvStockLink(x)+'</td><td>'+esc(x.market)+'</td><td class="theme" title="'+esc(x.theme||"")+'">'+themeButton(x.theme)+'</td><td class="score">'+N(x.total,1)+'</td>'+extra+'<td class="sar">'+esc(x.sarText||"—")+'</td><td>'+cp+chg+'</td><td>'+N(x.capitalB)+'</td><td>'+N(x.turnoverB)+'</td><td class="'+C(x.foreignToday)+'">'+N(x.foreignToday,0)+'</td><td class="'+C(x.trustToday)+'">'+N(x.trustToday,0)+'</td><td class="'+C(x.rs20)+'">'+P(x.rs20)+'</td><td>'+N(x.rvol)+'</td><td class="'+C(x.ret5)+'">'+P(x.ret5)+'</td><td class="'+C(x.ret20)+'">'+P(x.ret20)+'</td><td class="'+C(x.breakoutPct)+'">'+P(x.breakoutPct)+'</td><td class="'+C(x.ma20Slope)+'">'+P(x.ma20Slope)+'</td><td>'+esc(x.signal||"")+'</td></tr>'

}
function renderOfficialG(){
 if(MODEL!=="G")return;
 var status=document.getElementById("gOfficialStatus"),number=document.getElementById("gOfficialCount"),body=document.getElementById("officialTb");
 var source=DATA&&DATA.dataDate,selection=DATA&&DATA.gSelection,full=DATA&&DATA.models&&DATA.models.G;
 var verified=Array.isArray(full)&&!!source&&!!selection&&selection.dataDate===source;
 var lg=currentLiveG(),liveStatus=document.getElementById("gIntradayStatus"),liveCount=document.getElementById("gIntradayCount");
 if(lg){liveStatus.textContent="盤中資料日 "+lg.asOfDate+"｜更新 "+lg.publishedAt+"｜全市場有效報價 "+(lg.coverage&&lg.coverage.valid||0)+"/"+(lg.coverage&&lg.coverage.total||0)+"｜未完成日K，訊號僅供暫估";liveCount.textContent=lg.rows.length+" 檔"}
 else{var st=G_INTRADAY_STATUS,reason=st&&st.asOfDate===taipeiDate()&&st.status==="unavailable"?"｜"+(st.message||"來源未就緒"):"";liveStatus.textContent="目前沒有可用的當日盤中暫估榜單（休市、尚未更新或超過有效時間）"+reason+"；不使用前一日正式榜冒充盤中訊號";liveCount.textContent="尚無有效盤中榜"}
 if(!verified){status.textContent="⚠ 最近正式 G 選股尚未完成或日期不一致，不能將盤中價格當作盤後正式訊號";number.textContent="資料未就緒";body.innerHTML='<tr><td colspan="'+(TABLE_COMPACT?4:22)+'" style="padding:25px;text-align:center">正式 G 資料尚未同步，請等待盤後完整更新。</td></tr>';return}
 var selected=full.map(function(stock,i){return {stock:stock,rank:i+1}}).filter(function(pair){return !THEME_FILTER||String(pair.stock.theme||"").trim()===THEME_FILTER});
 status.textContent="正式訊號日 "+source+"｜依已完成日K計算，顯示該日真正收盤價與當日漲跌幅；當日盤中快刷不改變正式名單";
 number.textContent=selected.length+"/"+full.length+" 檔"+(THEME_FILTER?"｜"+THEME_FILTER:"");
 if(!selected.length){body.innerHTML='<tr><td colspan="'+(TABLE_COMPACT?4:22)+'" style="text-align:center;padding:25px">'+(THEME_FILTER?"此正式榜單沒有「"+esc(THEME_FILTER)+"」題材":"該交易日沒有正式 G 入選股票")+'</td></tr>';return}
 body.innerHTML=selected.map(function(pair){var x=pair.stock,i=pair.rank-1;return TABLE_COMPACT?renderSimpleStock(x,i,true,null,true):renderOfficialDetailedRow(x,i)}).join("");
}
function updateGReportOverview(){
 var nav=document.getElementById("gReportIntro");if(!nav||MODEL!=="G")return;
 var date=String(DATA&&DATA.dataDate||""),g=DATA&&DATA.gSelection||null,official=DATA&&DATA.models&&DATA.models.G;
 var verified=!!(date&&g&&g.dataDate===date&&Array.isArray(official));
 var live=currentLiveG(),r=typeof REPEAT_DATA!=="undefined"?REPEAT_DATA:null,rg=r&&r.models&&r.models.G;
 var repeatReady=!!(rg&&r.referenceDate===date);
 document.getElementById("gReportIntroDate").textContent="最近正式交易日 "+(date||"未提供")+"｜三份清單各有獨立資料日期；保留既有全部欄位與原始排序。盤中資料只在有效時顯示，不能代替盤後正式清單。";
 document.getElementById("gQuickRepeat").textContent=repeatReady?(rg.stocks||[]).length+" 檔重複上榜｜統計至 "+date:rg?"統計檔案待與正式日期同步":"正在讀取歷史快照";
 document.getElementById("gQuickLive").textContent=live?live.rows.length+" 檔暫估｜"+(live.asOfDate||"今日")+" 有效": "目前無有效盤中榜單";
 document.getElementById("gQuickOfficial").textContent=verified?official.length+" 檔正式｜"+date:"正式資料待同步";
}
function renderTable(){
var isDualG=MODEL==="G";document.body.classList.toggle("g-report-mode",isDualG);document.getElementById("gIntradayHeading").style.display=isDualG?"":"none";document.getElementById("gOfficialPanel").style.display=isDualG?"":"none";if(isDualG)updateGReportOverview();
var rp=document.getElementById("repeatPanel");if(rp)rp.style.display=MODEL==="L"?"none":"";if(MODEL!=="L"&&typeof renderRepeatPanel==="function")renderRepeatPanel(MODEL,DATA);
filterBar();
var live=MODEL==="G"?currentLiveG():null,xs=MODEL==="G"?(live?live.rows:[]):(DATA&&DATA.models&&DATA.models[MODEL]||[]),isG=(MODEL==="G"||MODEL==="G Pro"),gs=live?live.selection:(DATA&&DATA.gSelection||null);
if(MODEL==="L"){["tabG","tabGPro","tabD","tabF","tabF2","tabA","tabN"].forEach(function(id){document.getElementById(id).classList.remove("on")});tabL.classList.add("on");toggleNView(false);renderLTable();return;}
 document.getElementById("lPanel").style.display="none";tabL.classList.remove("on");
 if(MODEL==="N"){
 tabG.classList.remove("on");tabGPro.classList.remove("on");tabD.classList.remove("on");tabF.classList.remove("on");tabF2.classList.remove("on");tabA.classList.remove("on");tabN.classList.add("on");
 toggleNView(true);
 modelTitle.textContent="N｜基本面 × 成長動能排行";count.textContent="讀取中";
 gNote.textContent="N 基本面採 MOPS 歷史彙總與保守公告可用日期；僅顯示研究檔案已發布的最新歷史候選，不代表今日即時買進訊號。";
 renderNTable();return;
}
tabN.classList.remove("on");if(stockTable.classList.contains("stock-n-table"))toggleNView(false);
tabG.classList.toggle("on",MODEL==="G");tabGPro.classList.toggle("on",MODEL==="G Pro");tabD.classList.toggle("on",MODEL==="D");tabF.classList.toggle("on",MODEL==="F");tabF2.classList.toggle("on",MODEL==="F2");tabA.classList.toggle("on",MODEL==="A");

modelTitle.textContent=MODEL==="G"?"G 強勢股｜盤中＋盤後雙榜單":MODEL==="G Pro"?"G Pro 嚴格強勢突破排行":isG?"G 雙突破＋強勢持續度排行":MODEL==="D"?"D 主模型排行":MODEL==="F"?"F 固定濾網排行":MODEL==="F2"?"F2 動態濾網排行":"A 備用模型排行";
var strict=xs.filter(function(x){return x.strictPass===true}).length;
if(isG){
var candidates=MODEL==="G Pro"?3:gs&&gs.doubleBreakCandidates;
count.textContent=MODEL==="G"?"盤中 "+xs.length+" 檔｜盤後 "+(DATA&&DATA.models&&Array.isArray(DATA.models.G)?DATA.models.G.length:0)+" 檔":xs.length+" 檔｜原G Top3 嚴格確認";
renderModelNote();
}else{count.textContent=MODEL==="A"?xs.length+" 檔":xs.length+" 檔｜嚴格 "+strict+" 檔";renderModelNote()}
var selectedRows=xs.map(function(stock,i){return {stock:stock,rank:i+1}}).filter(function(pair){return !THEME_FILTER||String(pair.stock.theme||"").trim()===THEME_FILTER});
if(THEME_FILTER)count.textContent+="｜題材 "+THEME_FILTER+" "+selectedRows.length+" 檔";
if(!selectedRows.length&&THEME_FILTER){tb.innerHTML='<tr><td colspan="'+(TABLE_COMPACT?4:isG?22:18)+'" style="padding:24px;text-align:center">此盤中榜單沒有「'+esc(THEME_FILTER)+'」題材的上榜股票。可點上方清除篩選。</td></tr>';if(MODEL==="G")renderOfficialG();applyTableMode();return;}
if(!xs.length){tb.innerHTML='<tr><td colspan="'+(TABLE_COMPACT?4:isG?22:18)+'" style="text-align:center;padding:40px">'+(MODEL==="G Pro"?"原G Top3 今日無股票通過 G Pro 嚴格條件，正常空訊號。":isG?(MODEL==="G"?"目前沒有有效的當日盤中暫估榜單；下方正式榜單仍可查看。":(gs?"此交易日沒有通過 G 雙突破的股票，屬正常空訊號。":"⚠ G 正式資料尚未更新。")):"尚無資料")+'</td></tr>';if(MODEL==="G")renderOfficialG();applyTableMode();return}
tb.innerHTML=selectedRows.map(function(pair){var x=pair.stock,i=pair.rank-1;
if(TABLE_COMPACT)return renderSimpleStock(x,i,isG,live);
var cp=(live&&/midpoint|one-sided/.test(x.intradayPriceSource||"")?"≈":"")+(x.currentPrice!=null?N(x.currentPrice):N(x.close)),chg=x.currentPct!=null?' <span class="'+C(x.currentPct)+'">('+(Number(x.currentPct)>=0?"+":"")+N(x.currentPct)+'%)</span>':"";
var extra=isG?'<td>'+N(x.gScore)+'</td><td title="加分 +'+N(x.gExtra)+'"><b>'+N((x.persistence||{}).strength,1)+'</b> <span class="sub">+'+N(x.gExtra)+'</span></td><td>'+(x.gPast10==null?"—":x.gPast10)+'/10 <span class="sub">連'+(x.gStreak||0)+'天</span></td><td><b>'+(x.gBreak3?"✓":"—")+' 3D / '+(x.gBreak18?"✓":"—")+' 18D</b></td>':"";
return '<tr><td><b>'+(i+1)+'</b></td><td class="stock">'+tvStockLink(x)+'</td><td>'+esc(x.market)+'</td><td class="theme" title="'+esc(x.theme||"")+'">'+themeButton(x.theme)+'</td><td class="score">'+N(x.total,1)+'</td>'+extra+'<td class="sar">'+esc(x.sarText||"—")+'</td><td>'+cp+chg+'</td><td>'+N(x.capitalB)+'</td><td>'+N(x.turnoverB)+'</td><td class="'+C(x.foreignToday)+'">'+N(x.foreignToday,0)+'</td><td class="'+C(x.trustToday)+'">'+N(x.trustToday,0)+'</td><td class="'+C(x.rs20)+'">'+P(x.rs20)+'</td><td>'+N(x.rvol)+'</td><td class="'+C(x.ret5)+'">'+P(x.ret5)+'</td><td class="'+C(x.ret20)+'">'+P(x.ret20)+'</td><td class="'+C(x.breakoutPct)+'">'+P(x.breakoutPct)+'</td><td class="'+C(x.ma20Slope)+'">'+P(x.ma20Slope)+'</td><td>'+esc(x.signal||"")+'</td></tr>'
}).join("");if(MODEL==="G")renderOfficialG();applyTableMode()
}
function renderMeta(){if(!DATA)return;var s="資料日 "+(DATA.dataDate||"--")+" ｜ 完整更新 "+(DATA.generatedAt||"--");if(DATA.intradayUpdatedAt)s+=" ｜ 盤中快刷 "+DATA.intradayUpdatedAt+" ("+(DATA.intradayQuoteOk||0)+"/"+(DATA.intradayUniverse||0)+")";var lg=MODEL==="G"?currentLiveG():null;if(lg)s+=" ｜ 🟠 G當日盤中重新選股 "+lg.publishedAt+" (全市場 "+(lg.coverage&&lg.coverage.valid||0)+"/"+(lg.coverage&&lg.coverage.total||0)+")";else if(MODEL==="G"&&G_INTRADAY_STATUS&&G_INTRADAY_STATUS.asOfDate===taipeiDate()&&G_INTRADAY_STATUS.status==="unavailable")s+=" ｜ ⚠ G盤中重選未完成："+G_INTRADAY_STATUS.message;s+=" ｜ 股票池 "+(DATA.universeCount||0)+" ｜ K成功 "+(DATA.historyOk||0)+" ｜ 錯誤 "+(DATA.historyErrors||0);meta.textContent=s;var d=new Date(DATA.generatedAt),last=dayInfo(),days=Math.round((new Date(last.today+"T12:00:00+08:00")-new Date(last.d+"T12:00:00+08:00"))/86400000),isStale=Number.isFinite(d.getTime())&&(Date.now()-d.getTime()>20*3600*1000)&&(last.isCurrent||days>=5);staleWarning.style.display=isStale?"block":"none";if(isStale)staleWarning.textContent="⚠ 最近交易日資料為 "+(last.d||"未知")+"，已超過合理更新期間，請檢查 GitHub Actions。";}
async function load(){loading.classList.add("show");try{var r=await fetch("./data/latest.json?"+Date.now(),{cache:"no-store"});if(!r.ok)throw new Error("HTTP "+r.status);DATA=await r.json();var gs=await Promise.all(["./data/g_intraday/latest.json","./data/g_intraday/status.json"].map(async function(p){try{var q=await fetch(p+"?"+Date.now(),{cache:"no-store"});return q.ok?await q.json():null}catch(_){return null}}));G_INTRADAY=gs[0];G_INTRADAY_STATUS=gs[1];renderTable();renderMeta();if(typeof refreshRepeatArchive==="function")refreshRepeatArchive()}catch(e){meta.textContent="載入失敗："+e.message;tb.innerHTML='<tr><td colspan="18" style="text-align:center;padding:40px;color:#dc2626">資料載入失敗，請稍後重新載入</td></tr>'}finally{loading.classList.remove("show")}}
function switchRanking(name){MODEL=name;THEME_FILTER="";EXPANDED_STOCK="";history.replaceState(null,"",location.pathname+location.search+"#"+encodeURIComponent(name));renderTable()}
layoutToggle.onclick=function(){TABLE_COMPACT=!TABLE_COMPACT;VIEW_PREF=TABLE_COMPACT?"simple":"detail";try{localStorage.setItem("tw_selection_view_v1",VIEW_PREF)}catch(_){}renderTable()};
document.addEventListener("click",function(e){var b=e.target.closest(".theme-pick");if(b){var t=b.getAttribute("data-theme")||"";THEME_FILTER=THEME_FILTER===t?"":t;EXPANDED_STOCK="";renderTable();return}if(e.target.closest("#clearThemeFilter")){THEME_FILTER="";renderTable();return}var tr=e.target.closest("#tb tr.simple-stock-row,#officialTb tr.simple-stock-row");if(tr&&!e.target.closest("a,button")){var k=tr.getAttribute("data-key");EXPANDED_STOCK=EXPANDED_STOCK===k?"":k;renderTable()}});
document.addEventListener("keydown",function(e){if(e.key!=="Enter"&&e.key!==" ")return;var tr=e.target.closest("#tb tr.simple-stock-row,#officialTb tr.simple-stock-row");if(tr&&e.target===tr){e.preventDefault();var k=tr.getAttribute("data-key");EXPANDED_STOCK=EXPANDED_STOCK===k?"":k;renderTable();var match=Array.from(document.querySelectorAll("#tb tr.simple-stock-row,#officialTb tr.simple-stock-row")).find(function(x){return x.getAttribute("data-key")===k});if(match)match.focus()}});
window.addEventListener("resize",function(){if(VIEW_PREF)return;var want=window.matchMedia("(max-width:760px)").matches;if(want!==TABLE_COMPACT){TABLE_COMPACT=want;renderTable()}});
tabG.onclick=function(){switchRanking("G")};tabGPro.onclick=function(){switchRanking("G Pro")};
tabD.onclick=function(){switchRanking("D")};tabF.onclick=function(){switchRanking("F")};
tabF2.onclick=function(){switchRanking("F2")};tabA.onclick=function(){switchRanking("A")};
tabN.onclick=function(){switchRanking("N")};tabL.onclick=function(){switchRanking("L")};document.getElementById("lScope").onchange=function(){if(MODEL==="L")renderLStats()};
var incoming=decodeURIComponent(location.hash.slice(1));
if(["G","G Pro","D","F","F2","A","N","L"].includes(incoming))MODEL=incoming;
window.addEventListener("hashchange",function(){var value=decodeURIComponent(location.hash.slice(1));if(["G","G Pro","D","F","F2","A","N","L"].includes(value)){MODEL=value;THEME_FILTER="";EXPANDED_STOCK="";renderTable()}});
reload.onclick=load;load();setInterval(load,90000);