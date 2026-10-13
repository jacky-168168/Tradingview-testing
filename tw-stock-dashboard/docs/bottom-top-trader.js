/* Bottom/Top trader V1: deterministic event-price paper simulation.
   Does not recreate or modify the Pine Bottom/Top formulas, and does not claim realtime market data. */
(function(){
"use strict";
const $=id=>document.getElementById(id),key="tw-bottom-top-trader-v1";
let events=[],log=[],portfolio={},closed=[],cash=0;
const fields=["strategy","capital","riskCap","trendMin","batches","dip","unit","discount","tax","stopPct","useStop","requireG"];
const clamp=(v,min,max)=>Math.min(max,Math.max(min,v));
const val=(id,min,max)=>clamp(Number($(id).value)||0,min,max);
const money=v=>Number.isFinite(v)?Math.round(v).toLocaleString("zh-TW"):"—";
const px=v=>Number.isFinite(v)?Number(v).toLocaleString("zh-TW",{maximumFractionDigits:3}):"—";
const esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
const dt=t=>new Intl.DateTimeFormat("zh-TW",{timeZone:"Asia/Taipei",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}).format(new Date(t));
function eventTime(v){
 if(typeof v==="number" || (typeof v==="string"&&/^\d{10,13}$/.test(v.trim()))){let n=Number(v);if(n<1e11)n*=1000;return Number.isFinite(n)?n:NaN}
 if(typeof v!=="string"||!/(?:Z|[+-]\d{2}:?\d{2})$/i.test(v.trim()))return NaN;
 return Date.parse(v);
}
function norm(raw){
 if(!raw||typeof raw!=="object")throw Error("列不是物件");
 const t=eventTime(raw.time??raw.timestamp??raw.datetime??raw.date);
 const s=String(raw.symbol??raw.ticker??raw.stock??"").trim().toUpperCase();
 const ty=String(raw.signal??raw.type??raw.action??raw.side??"").trim().toUpperCase();
 const p=Number(raw.price??raw.close??raw.value);
 const tf=String(raw.timeframe??raw.tf??raw.interval??"").trim().toLowerCase();
 const tv=raw.trend??raw.trendScore??raw.trend_score;
 const trend=tv==null||String(tv).trim()===""?null:Number(tv);
 const trendGt70=raw.trendGt70===true||raw.trend_gt_70===true||raw.trend_gt_70===1;
 const gv=raw.g??raw.in_g??raw.gSelected??null;
 const g=gv==null||String(gv).trim()===""?null:([true,1,"1","TRUE","YES","Y","是","G"].includes(typeof gv==="string"?gv.trim().toUpperCase():gv)?true:false);
 if(!Number.isFinite(t)||t<946684800000||t>Date.now()+86400000)throw Error("時間格式須為 Unix 毫秒或 ISO 時區時間");
 if(!/^[A-Z0-9:_./-]{3,50}$/.test(s))throw Error("股票代碼無效");
 if(!["BOTTOM","TOP","PRICE"].includes(ty))throw Error("訊號須為 BOTTOM、TOP、PRICE");
 if(!Number.isFinite(p)||p<=0||p>10000000)throw Error("價格無效");
 if(tf!=="2"&&tf!=="2m"&&tf!=="120s")throw Error("時間週期必須為 2 分鐘");
 if(trend!==null&&(!Number.isFinite(trend)||trend<0||trend>100))throw Error("Trend 需為 0～100");
 return {time:t,symbol:s,signal:ty,price:p,trend,trendGt70:ty==="BOTTOM"&&trendGt70,g,timeframe:"2"};
}
function csvRows(s){
 let out=[],row=[],cell="",quoted=false;
 for(let i=0;i<s.length;i++){let c=s[i];
  if(c==='"'){if(quoted&&s[i+1]==='"'){cell+='"';i++}else quoted=!quoted}
  else if(c===","&&!quoted){row.push(cell);cell=""}
  else if((c==="\n"||c==="\r")&&!quoted){if(c==="\r"&&s[i+1]==="\n")i++;row.push(cell);if(row.some(x=>x.trim()))out.push(row);row=[];cell=""}
  else cell+=c;
 }
 if(quoted)throw Error("CSV 有未閉合的引號");
 row.push(cell);if(row.some(x=>x.trim()))out.push(row);return out;
}
function extract(raw){
 const s=raw.replace(/^\uFEFF/,"").trim();
 if(!s)throw Error("請輸入事件");
 if(s[0]==="["||s[0]==="{"){
  if(s[0]==="["){let obj=JSON.parse(s);if(!Array.isArray(obj))throw Error("JSON 必須是陣列");return obj}
  return s.split(/\r?\n/).filter(Boolean).map(line=>JSON.parse(line));
 }
 let rows=csvRows(s);if(rows.length<2)throw Error("CSV 至少需要標題和一筆資料");
 let keys=rows.shift().map(x=>x.replace(/^\uFEFF/,"").trim());return rows.map(row=>Object.fromEntries(keys.map((k,i)=>[k,row[i]??""])));
}
function addEvents(raw){
 let values=extract(raw);if(values.length>10000)throw Error("每次至多匯入一萬列");
 let rejected=[],added=0,dups=0;
 let unique=new Map(events.map((e,i)=>[[e.time,e.symbol,e.signal,e.price].join("|"),i]));
 values.forEach((row,i)=>{try{let e=norm(row),k=[e.time,e.symbol,e.signal,e.price].join("|");if(unique.has(k)){let old=events[unique.get(k)];old.trendGt70=old.trendGt70||e.trendGt70;if(old.trend===null&&e.trend!==null)old.trend=e.trend;if(old.g!==true&&e.g===true)old.g=true;dups++;return}unique.set(k,events.length);events.push(e);added++}catch(err){if(rejected.length<5)rejected.push("第 "+(i+1)+" 筆："+err.message)}});
 events.sort((a,b)=>a.time-b.time||({"TOP":0,"PRICE":1,"BOTTOM":2}[a.signal]-{"TOP":0,"PRICE":1,"BOTTOM":2}[b.signal]));
 if(events.length>20000){events=events.slice(-20000);rejected.push("訊號已超上限，只保留最近 20,000 筆")}
 return {added,dups,rejected};
}
function conf(){
 return {strategy:$("strategy").value,initial:val("capital",1000,1e11),risk:val("riskCap",1,100)/100,minTrend:val("trendMin",0,100),maxLayers:Math.round(val("batches",2,15)),dip:val("dip",.1,30)/100,unit:Number($("unit").value),fee:.001425*val("discount",.1,10)/10,tax:val("tax",.01,1)/100,stop:val("stopPct",1,80)/100,useStop:$("useStop").checked,requireG:$("requireG").checked};
}
function trade(e,p,action,why,qty=0,pnl=null){
 log.push({time:e.time,symbol:e.symbol,signal:e.signal,price:e.price,trend:e.trend,trendGt70:e.trendGt70===true,action,why,qty,pnl});
}
function calc(){
 const c=conf();cash=c.initial;log=[];portfolio={};closed=[];
 const states={},positions={};
 const eList=events.filter(x=>Number.isFinite(x.time)).slice().sort((a,b)=>a.time-b.time||({"TOP":0,"PRICE":1,"BOTTOM":2}[a.signal]-{"TOP":0,"PRICE":1,"BOTTOM":2}[b.signal]));
 let buyCount=0,blocked=0;
 function enter(e,pos,layer){
  const limit=c.initial*c.risk,perLayer=c.strategy==="C"?limit/c.maxLayers:limit;
  const already=pos?pos.invested:0;
  const remaining=Math.max(0,limit-already),budget=Math.min(cash,remaining,perLayer);
  const qty=Math.floor(budget/(e.price*(1+c.fee))/c.unit)*c.unit;
  if(qty<=0){trade(e,pos,"略過","預算不足或股數單位不符");blocked++;return null}
  const spend=qty*e.price*(1+c.fee);cash-=spend;
  const next=pos||{qty:0,invested:0,layers:0,first:e.price,lastBuyTime:null,firstTime:e.time};
  next.qty+=qty;next.invested+=spend;next.layers++;next.lastBuy=e.price;next.lastBuyTime=e.time;
  positions[e.symbol]=next;buyCount++;
  trade(e,next,layer>1?"分批加碼":"模擬買進",layer>1?"到達第 "+layer+" 批價格階梯":"Bottom 觸發，事件收盤價僅為示意",qty);
  return next;
 }
 function exit(e,p,reason){
  const received=p.qty*e.price*(1-c.fee-c.tax);
  const pnl=received-p.invested;cash+=received;
  closed.push({time:e.time,symbol:e.symbol,pnl,entry:p.firstTime,exit:e.time});
  trade(e,p,"模擬出場",reason,p.qty,pnl);
  positions[e.symbol]=null;
  states[e.symbol].closedAt=e.time;
 }
 for(const e of eList){
  const state=states[e.symbol]||(states[e.symbol]={last:null,time:null,closedAt:NaN});
  state.last=e.price;state.time=e.time;state.signal=e.signal;state.trend=e.trend;
  let pos=positions[e.symbol];
  // TOP always closes, independent of Trend, G, market, and session.
  if(e.signal==="TOP"){
   if(pos&&pos.qty>0)exit(e,pos,"原始 TOP 出場，不使用 Trend");
   else trade(e,null,"觀察","TOP 已確認；沒有多單可以平倉");
   continue;
  }
  // Price/Bottom price is a discrete observation, not a continuously executable quote.
  if(pos&&c.useStop&&e.price<=pos.invested/pos.qty*(1-c.stop)){
   exit(e,pos,"獨立緊急停損（觀測價觸發）");continue;
  }
  if(pos){
   if(c.strategy==="C"&&pos.layers<c.maxLayers&&e.time>pos.lastBuyTime){
    const next=pos.lastBuy*(1-c.dip);
    if(e.price<=next)enter(e,pos,pos.layers+1);
    else trade(e,pos,"持有","未到下一批階梯 "+px(next));
   }else trade(e,pos,"持有",c.strategy==="C"&&pos.layers>=c.maxLayers?"加碼已達上限":"等待 TOP");
   continue;
  }
  if(e.signal!=="BOTTOM"){trade(e,null,"觀察","無部位，PRICE 只作為價格觀測");continue}
  if(state.closedAt===e.time){trade(e,null,"略過","本根已 TOP 出場，不在同根反手");blocked++;continue}
  if(c.strategy!=="A"&&!((e.trend!==null&&e.trend>c.minTrend)||(e.trendGt70===true&&c.minTrend<=70))){trade(e,null,"略過",e.trend===null?(e.trendGt70?"SS 只證明 Trend > 70，不足以確認大於目前設定 "+c.minTrend:"缺少 Trend 或 SS 確認，無法通過門檻"):"Trend "+e.trend+" 未嚴格大於 "+c.minTrend);blocked++;continue}
  if(c.requireG&&e.g!==true){trade(e,null,"略過","未確認在 G 股票池");blocked++;continue}
  enter(e,null,1);
 }
 const opened=Object.entries(positions).filter(([s,p])=>p&&p.qty>0);
 let floating=0,atRisk=0;
 opened.forEach(([s,p])=>{let mark=states[s]?.last??p.lastBuy;floating+=p.qty*mark*(1-c.fee-c.tax)-p.invested;atRisk+=p.invested});
 const realized=closed.reduce((s,x)=>s+x.pnl,0),wins=closed.filter(x=>x.pnl>0).length;
 const equity=cash+opened.reduce((s,[sym,p])=>s+p.qty*(states[s]?.last??p.lastBuy)*(1-c.fee-c.tax),0);
 return {conf:c,states,positions,opened,floating,realized,atRisk,equity,wins,buyCount,blocked,closed:closed.length};
}
function render(){
 const s=calc(),c=s.conf;
 $("metrics").innerHTML=[
  ["有效事件",events.length+" 筆"],["假設入場／加碼",s.buyCount+" 次"],
  ["已模擬平倉",s.closed+" 筆"],["已實現示意損益",money(s.realized)+" 元"],
  ["未平倉浮動損益",money(s.floating)+" 元"],["示意帳戶權益",money(s.equity)+" 元"],
  ["剩餘示意現金",money(cash)+" 元"],["被過濾／無法成交",s.blocked+" 次"]
 ].map(x=>'<div class="metric"><span>'+x[0]+'</span><b>'+esc(x[1])+'</b></div>').join("");
 let candidates=Object.keys(s.states);
 $("stockRows").innerHTML=candidates.length?candidates.map(sym=>{
  let info=s.states[sym],p=s.positions[sym],mark=info.last;
  let floating=p?p.qty*mark*(1-c.fee-c.tax)-p.invested:null;
  let next=p?(c.strategy==="C"&&p.layers<c.maxLayers?"下批 ≤ "+px(p.lastBuy*(1-c.dip))+"；TOP 出場":"等待 TOP 訊號"):"等待新 Bottom";
  return '<tr><td><b>'+esc(sym)+'</b></td><td>'+(p?'持倉 '+p.layers+' 批':'觀察中')+'</td><td class="num">'+(p?money(p.qty):"—")+'</td><td class="num">'+(p?px(p.invested/p.qty):"—")+'</td><td class="num">'+px(mark)+'</td><td class="num '+(floating!=null?(floating>=0?"green":"red"):"")+'">'+(floating==null?"—":money(floating))+'</td><td>'+esc(next)+'</td></tr>';
 }).join(""):'<tr><td colspan="7">目前沒有確認訊號，請先匯入事件。</td></tr>';
 $("signalRows").innerHTML=log.length?log.slice(-500).reverse().map(t=>
  '<tr><td>'+dt(t.time)+'</td><td>'+esc(t.symbol)+'</td><td>'+esc(t.signal)+'</td><td class="num">'+px(t.price)+'</td><td class="num">'+(t.trend===null?(t.trendGt70?"SS >70":"—"):px(t.trend))+'</td><td><b>'+esc(t.action)+'</b><div class="sub">'+esc(t.why)+'</div></td><td class="num '+(t.pnl===null?"":t.pnl>=0?"green":"red")+'">'+(t.pnl===null?"—":money(t.pnl))+'</td></tr>'
 ).join(""):'<tr><td colspan="7">尚無已確認的 Bottom / Top / PRICE 事件。</td></tr>';
 $("banner").textContent=events.length?'已匯入 '+events.length+' 筆 2 分鐘事件；目前為 '+({A:"A Bottom 直接進場",B:"B Bottom + Trend > "+c.minTrend,C:"C Bottom + Trend > "+c.minTrend+"＋分批加碼"}[c.strategy])+'。模擬使用事件價格，不是可成交的歷史回測。':'尚未匯入交易事件，沒有可驗證的 Bottom/Top 買點；不會自動產生假訊號。';
 $("banner").className="note "+(events.length?"good":"warn");
 try{const settings={};fields.forEach(id=>{let el=$(id);settings[id]=el.type==="checkbox"?el.checked:el.value});localStorage.setItem(key,JSON.stringify({settings,events:events.slice(-5000)}))}catch(err){$("importStatus").textContent="瀏覽器儲存失敗："+err.message}
}
function showMessage(s){$("importStatus").textContent=s}
function doImport(text){
 try{const r=addEvents(text);render();showMessage("已新增 "+r.added+" 筆、跳過重複 "+r.dups+" 筆。"+(r.rejected.length?" 有無效資料："+r.rejected.join("；"):""))}
 catch(e){showMessage("匯入失敗："+e.message)}
}
function csvEscape(s){return '"'+String(s??"").replace(/"/g,'""')+'"'}
function download(name,content,mime){
 const blob=new Blob([content],{type:mime||"text/plain;charset=utf-8"}),url=URL.createObjectURL(blob),a=document.createElement("a");
 a.href=url;a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function localNow(){
 const d=new Date(),z=new Date(d.getTime()-d.getTimezoneOffset()*60000);return z.toISOString().slice(0,16);
}
if(typeof document.addEventListener==="function")document.addEventListener("tw:discord-import",function(ev){
 const batch=ev?.detail;
 if(!Array.isArray(batch)||batch.length===0)return;
 doImport(JSON.stringify(batch.slice(0,500)));
});
$("manualTime").value=localNow();
$("importText").addEventListener("click",()=>doImport($("inputEvents").value));
$("fileEvents").addEventListener("change",async ev=>{
 const f=ev.target.files?.[0];if(!f)return;if(f.size>5e6){showMessage("檔案超過 5 MB；請先分批處理");return}
 try{doImport(await f.text())}catch(err){showMessage("讀檔失敗："+err.message)}finally{ev.target.value=""}
});
document.querySelectorAll("button[data-signal]").forEach(b=>b.addEventListener("click",()=>{
 const t=$("manualTime").value,p=Number($("manualPrice").value),trend=$("manualTrend").value.trim()===""?null:Number($("manualTrend").value),symbol=$("manualSymbol").value.trim(),sig=b.dataset.signal;
 if(!t){showMessage("請選擇事件時間。");return}
 let iso;try{iso=new Date(t).toISOString()}catch(err){showMessage("無效事件時間。");return}
 const obj={time:iso,symbol,signal:sig,price:p,trend:sig==="BOTTOM"?trend:null,timeframe:"2",g:$("manualG").value==="unknown"?null:$("manualG").value==="yes"};
 try{let result=addEvents(JSON.stringify([obj]));render();showMessage("已人工加入 "+result.added+" 筆 "+sig+"，請確認訊號原本確實在 TradingView 收盤成立。")}
 catch(err){showMessage("人工事件無效："+err.message)}
}));
fields.forEach(id=>$(id).addEventListener("input",render));
$("clearEvents").addEventListener("click",()=>{if(!confirm("確定清除本裝置這份訊號紀錄？此動作無法復原。"))return;events=[];render();showMessage("已清空本機訊號，不影響 GitHub。")});
$("exportEvents").addEventListener("click",()=>download("bottom_top_events.json",JSON.stringify(events,null,2),"application/json;charset=utf-8"));
$("exportTrades").addEventListener("click",()=>{
 const hdr=["time","symbol","signal","price","trend","trend_gt_70","action","note","qty","estimated_pnl"];
 const lines=[hdr.join(",")].concat(log.map(x=>[new Date(x.time).toISOString(),x.symbol,x.signal,x.price,x.trend??"",x.trendGt70===true?1:0,x.action,x.why,x.qty,x.pnl??""].map(csvEscape).join(",")));
 download("bottom_top_paper_trades.csv","\ufeff"+lines.join("\r\n"),"text/csv;charset=utf-8");
});
$("copyPine").addEventListener("click",()=>{
 const instr="使用 GitHub 專用原版 Extreme Reversal Hunter JSON Bridge Pine；切換至 2 分鐘圖，啟用「Dashboard JSON Alert」，建立『Any alert() function call』快訊。複製 Alerts Log 的 JSON 後貼入本頁。TOP 只管出場，Trend 僅過濾 Bottom 進場。";
 navigator.clipboard?.writeText(instr).then(()=>showMessage("已複製設定說明。")).catch(()=>showMessage(instr));
});
try{
 const saved=JSON.parse(localStorage.getItem(key)||"null");
 if(saved?.settings&&typeof saved.settings==="object")fields.forEach(id=>{const v=saved.settings[id];if(v===undefined)return;let node=$(id);if(node.type==="checkbox")node.checked=Boolean(v);else node.value=String(v)});
 if(Array.isArray(saved?.events))saved.events.slice(-5000).forEach(x=>{try{events.push(norm(x))}catch(e){}});
}catch(e){showMessage("舊紀錄無法讀取，請重新匯入。")}
const params=new URLSearchParams(location.search);
if(params.has("stock"))$("manualSymbol").value=String(params.get("stock")).slice(0,36);
render();
})();