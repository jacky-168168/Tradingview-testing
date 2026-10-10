/* Two-month frozen daily selection repeats. Independent of G model calculations.
   No historical list is synthesized from price candles or a later Top20. */
var REPEAT_DATA=null,REPEAT_LOAD_ERROR="",REPEAT_EXPANDED=false,REPEAT_FETCHING=null;
function repeatSafe(x){return String(x==null?"":x).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function repeatNum(x,digits){return x==null||x===""||!Number.isFinite(Number(x))?"—":Number(x).toFixed(digits==null?1:digits)}
function repeatPct(x){return x==null||x===""||!Number.isFinite(Number(x))?"—":repeatNum(x,1)+"%"}
function repeatSignedClass(x){return x==null||x===""||!Number.isFinite(Number(x))?"":Number(x)<0?"neg":"pos"}
function repeatTradingview(stock){
 var exchange=stock.market==="上櫃"?"TPEX":stock.market==="上市"?"TWSE":null,code=String(stock.code||"").trim();
 var label=repeatSafe(code+" "+(stock.name||""));
 return exchange&&/^[0-9A-Z]{4,8}$/.test(code)?
  '<a class="tv-link" href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(exchange+":"+code)+'" target="_blank" rel="noopener noreferrer">'+label+'</a>':label;
}
function renderRepeatPanel(model,data){
 var panel=document.getElementById("repeatPanel");
 if(!panel)return;
 panel.style.display=model==="N"?"none":"";
 if(model==="N")return;
 var coverage=document.getElementById("repeatCoverage"),state=document.getElementById("repeatStatus"),rows=document.getElementById("repeatRows"),
     size=document.getElementById("repeatCount"),toggle=document.getElementById("repeatExpand");
 document.getElementById("repeatModel").textContent=model==="G Pro"?"G Pro":model;
 var goHistory=panel.querySelector(".repeat-history");if(goHistory)goHistory.href="./history.html#"+(model==="G Pro"?"GPro":encodeURIComponent(model));
 if(!REPEAT_DATA){
  coverage.textContent=REPEAT_LOAD_ERROR?"資料讀取失敗":"等待歷史資料";
  state.textContent=REPEAT_LOAD_ERROR?"⚠ "+REPEAT_LOAD_ERROR:"正在讀取近兩個月已封存的歷史榜單…";
  rows.innerHTML='<tr><td colspan="16" class="repeat-empty">歷史重複上榜資料讀取中／尚未可用</td></tr>';
  size.textContent="—";toggle.style.display="none";return;
 }
 if(REPEAT_DATA.version!=="TWO_CALENDAR_MONTHS_FROZEN_TOP20_V1"){
  state.textContent="⚠ 重複上榜統計資料版本不符，請重新執行 GitHub 更新。";
  rows.innerHTML='<tr><td colspan="16" class="repeat-empty">歷史來源尚未通過驗證</td></tr>';
  coverage.textContent="版本不符";size.textContent="—";toggle.style.display="none";return;
 }
 var x=REPEAT_DATA.models&&REPEAT_DATA.models[model];
 if(!x){state.textContent="⚠ 無此選股模型的歷史統計。";size.textContent="—";rows.innerHTML="";toggle.style.display="none";return}
 var total=x.snapshotDays||0,repeated=x.stocks||[],uptodate=data&&data.dataDate===REPEAT_DATA.referenceDate;
 var earlier=x.firstSnapshot&&x.firstSnapshot>REPEAT_DATA.windowStart;
 coverage.textContent="統計區間 "+REPEAT_DATA.windowStart+" ～ "+REPEAT_DATA.referenceDate+
  "｜"+model+" 已保存 "+total+" 個交易日｜資料起點 "+(x.firstSnapshot||"尚未建立");
 size.textContent=repeated.length+" 檔重複上榜";
 state.className="repeat-status"+(total<2||earlier||!uptodate?" repeat-attention":"");
 if(total<2)state.textContent="⚠ "+model+" 目前只保存 "+total+" 個正式榜單日期，還不能判斷兩個月內哪些股票重複上榜；資料會從每日更新後持續累積。";
 else if(!repeated.length)state.textContent="目前在已保存的 "+total+" 個榜單日期內，尚無同一股票出現至少2次。"+
   (earlier?" 資料尚未覆蓋完整兩個月，不能視為完整回溯結果。":"");
 else state.textContent="依「同一選股模型＋相同股票代號／市場」統計不同日期的 Top 榜單，至少2次才列出；"+
  (earlier?"目前歷史不足整整兩個月，以下是已保存日期內的實際次數。":"近兩個月內每個已保存日期只計1次。");
 if(!uptodate&&data)state.textContent+=" ⚠ 最新選股日期與此統計檔案不同，請等待同步更新（未混算）。";
 if(!repeated.length){
  rows.innerHTML='<tr><td colspan="16" class="repeat-empty">'+(total<2?"歷史日期不足，暫無可驗證的重複上榜股票。":"沒有至少2次上榜的標的。")+'</td></tr>';
  toggle.style.display="none";return;
 }
 var all=REPEAT_EXPANDED?repeated:repeated.slice(0,15);
 rows.innerHTML=all.map(function(s,i){
  var score=s.total??s.gScore??null;
  return '<tr>'+
   '<td><b>'+(i+1)+'</b></td>'+
   '<td class="stock">'+repeatTradingview(s)+(s.onReferenceDate?' <span class="repeat-live">最新在榜</span>':'')+'</td>'+
   '<td>'+repeatSafe(s.market||"—")+'</td>'+
   '<td class="theme" title="'+repeatSafe(s.theme||s.subIndustry||"")+'">'+repeatSafe(s.theme||s.subIndustry||"—")+'</td>'+
   '<td class="repeat-frequency"><strong>'+repeatSafe(s.count)+'</strong> 次</td>'+
   '<td>'+repeatSafe(s.lastSeen||"—")+'</td>'+
   '<td>'+repeatSafe(s.previousSeen||"—")+'</td>'+
   '<td>'+repeatSafe(s.lastRank)+'</td>'+
   '<td class="score">'+repeatNum(score,1)+'</td>'+
   '<td class="sar">'+repeatSafe(s.sarText||"—")+'</td>'+
   '<td>'+repeatNum(s.close,2)+'</td>'+
   '<td class="'+repeatSignedClass(s.foreignToday)+'">'+repeatNum(s.foreignToday,0)+'</td>'+
   '<td class="'+repeatSignedClass(s.trustToday)+'">'+repeatNum(s.trustToday,0)+'</td>'+
   '<td class="'+repeatSignedClass(s.rs20)+'">'+repeatPct(s.rs20)+'</td>'+
   '<td class="'+repeatSignedClass(s.ret5)+'">'+repeatPct(s.ret5)+'</td>'+
   '<td class="'+repeatSignedClass(s.ret20)+'">'+repeatPct(s.ret20)+'</td></tr>';
 }).join("");
 toggle.style.display=repeated.length>15?"":"none";
 toggle.textContent=REPEAT_EXPANDED?"收合，僅顯示前15檔":"展開全部 "+repeated.length+" 檔";
}
function toggleRepeatList(){REPEAT_EXPANDED=!REPEAT_EXPANDED;if(typeof MODEL!=="undefined")renderRepeatPanel(MODEL,typeof DATA==="undefined"?null:DATA)}
async function refreshRepeatArchive(){
 if(REPEAT_FETCHING)return REPEAT_FETCHING;
 REPEAT_FETCHING=(async function(){
  try{
   var r=await fetch("./data/rolling-repeats.json?t="+Date.now(),{cache:"no-store"});
   if(!r.ok)throw Error("HTTP "+r.status+"，請等待 GitHub 更新生成近兩個月統計");
   var fresh=await r.json();
   if(!fresh||fresh.version!=="TWO_CALENDAR_MONTHS_FROZEN_TOP20_V1"||
       fresh.calendarWindowMonths!==2||!fresh.models||!fresh.savedDates||!fresh.referenceDate)
       throw Error("歷史統計檔案尚未通過完整性檢查");
   REPEAT_DATA=fresh;REPEAT_LOAD_ERROR="";
  }catch(err){REPEAT_DATA=null;REPEAT_LOAD_ERROR=err.message||String(err)}
  finally{REPEAT_FETCHING=null;if(typeof MODEL!=="undefined")renderRepeatPanel(MODEL,typeof DATA==="undefined"?null:DATA)}
 })();
 return REPEAT_FETCHING;
}
