/* 臺股 VIXTWN 公開觀測值：獨立資訊卡，絕不寫入 Risk Score。 */
(function(scope){
"use strict";
const URL="./data/research/tw_vix/latest.json";
const $=id=>typeof document==="undefined"?null:document.getElementById(id);
const money=v=>Number(v).toFixed(2);
function taiwanDate(now=new Date()){
 const parts=new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).formatToParts(now);
 const map=Object.fromEntries(parts.map(x=>[x.type,x.value]));
 return [map.year,map.month,map.day].join("-");
}
function check(payload){
 if(!payload||payload.version!=="TW_VIX_TAIFEX_DAILY_V1"||!Array.isArray(payload.rows)||!payload.rows.length||payload.rows.length>260)
  throw Error("台股 VIX 資料格式無效");
 if(payload.sourceUrl!=="https://www.taifex.com.tw/cht/7/vixDaily3MNew")throw Error("台股 VIX 來源驗證失敗");
 let prior="",clean=[];
 for(let i=0;i<payload.rows.length;i++){
  const r=payload.rows[i];
  if(!r||typeof r.date!=="string"||!/^20\d{2}-\d{2}-\d{2}$/.test(r.date)||r.date<=prior||
    !/^(?:0\d|1\d|2[0-3]):[0-5]\d$/.test(r.time||"")||
    !["value","closeMinuteAverage"].every(k=>typeof r[k]==="number"&&Number.isFinite(r[k])&&r[k]>=5&&r[k]<=150)||
    Math.abs(r.value-r.closeMinuteAverage)>10)throw Error("期交所 VIX 官方日收盤資料不正確");
  if(i>0){
   const prev=clean.at(-1).value;
   if(typeof r.change!=="number"||typeof r.changePct!=="number"||
     !Number.isFinite(r.change)||!Number.isFinite(r.changePct)||
     Math.abs(r.change-(r.value-prev))>.011||
     Math.abs(r.changePct-(r.value/prev-1)*100)>.015)throw Error("期交所 VIX 收盤漲跌驗算失敗");
  }else if(r.change!==null||r.changePct!==null)throw Error("無前日資料卻宣稱漲跌");
  clean.push(r);prior=r.date;
 }
 if(payload.quality!=="official-taifex-daily-close"||payload.asOfDate!==prior||
   payload.sourceObservationAt!==prior+"T"+clean.at(-1).time+":00+08:00")
  throw Error("台股 VIX 官方來源時間與資料不符");
 return clean;
}
function percentile(rows,days){
 if(rows.length<days)return null;
 const values=rows.slice(-days).map(r=>r.value);
 return Math.round(values.filter(v=>v<=values.at(-1)).length/values.length*100);
}
function mood(row){
 if(row.change===null)return {label:"前日無資料",tone:"flat",text:"樣本首日無前一交易日官方收盤，不能憑空計算漲跌。"};
 if(row.change>=.25)return {label:"波動升溫",tone:"up",text:"期交所 VIX 官方日收盤較前一交易日上升，避險壓力可能增加；高 VIX 不代表底部已確認。"};
 if(row.change<=-.25)return {label:"波動降溫觀察",tone:"down",text:"期交所 VIX 官方日收盤下降，可配合加權指數與 Nasdaq 觀察，但不能單獨當作進場信號。"};
 return {label:"波動變化有限",tone:"flat",text:"臺股預期波動變化有限；需同時看 Nasdaq、VXN 與大盤 Risk Score，不能直接推斷指數方向。"};
}
function timeStatus(payload,now=new Date()){
 const last=payload.rows.at(-1),minute=(now.getTime()-Date.parse(payload.sourceObservationAt))/60000;
 if(!Number.isFinite(minute)||minute< -5)return {text:"期交所 VIX 收盤日期無法驗證",stale:true};
 const today=taiwanDate(now);
 if(minute>8*24*60)return {text:"期交所官方收盤資料超過 8 個日曆日，可能停止更新",stale:true};
 return {text:"期交所官方日收盤 "+last.date+" "+last.time+"（非盤中即時 VIX）"+
   (last.date===today?"":"；今天收盤尚未取得或非交易日"),stale:false};
}
function plot(svg,rows){
 svg.replaceChildren();
 const NS="http://www.w3.org/2000/svg", make=(name,attrs,text)=>{
  const e=document.createElementNS(NS,name);
  for(const [k,v] of Object.entries(attrs||{}))e.setAttribute(k,String(v));
  if(text!==undefined)e.textContent=text;
  svg.appendChild(e);return e;
 };
 svg.setAttribute("viewBox","0 0 760 115");
 if(rows.length<2){
  make("text",{x:380,y:55,"text-anchor":"middle",fill:"#a8bfd5","font-size":15},"歷史觀測正在累積，暫不繪製推測走勢");
  return;
 }
 const rowsToShow=rows.slice(-60),vals=rowsToShow.map(r=>r.value),lo=Math.min(...vals),hi=Math.max(...vals);
 const pad=Math.max(1.3,(hi-lo)*.18),left=52,right=740,top=12,bottom=91;
 const x=i=>left+(right-left)*i/(rowsToShow.length-1),y=v=>bottom-(v-(lo-pad))/(hi-lo+2*pad)*(bottom-top);
 for(let i=0;i<=2;i++){const v=lo-pad+(hi-lo+2*pad)*i/2,yy=y(v);
  make("line",{x1:left,x2:right,y1:yy,y2:yy,stroke:"#566981","stroke-dasharray":"3 6",opacity:".7"});
  make("text",{x:40,y:yy+4,"text-anchor":"end",fill:"#afc1d8","font-size":11},v.toFixed(1));
 }
 make("polyline",{points:rowsToShow.map((r,i)=>x(i).toFixed(1)+","+y(r.value).toFixed(1)).join(" "),fill:"none",stroke:"#a9a0fa","stroke-width":3,"stroke-linecap":"round","stroke-linejoin":"round"});
 make("circle",{cx:x(rowsToShow.length-1),cy:y(vals.at(-1)),r:5,fill:"#e0dcff"});
 make("text",{x:left,y:109,fill:"#b4c6da","font-size":11},rowsToShow[0].date.slice(5).replace("-","/"));
 make("text",{x:right,y:109,"text-anchor":"end",fill:"#b4c6da","font-size":11},rowsToShow.at(-1).date.slice(5).replace("-","/"));
}
function render(payload,now=new Date()){
 const rows=check(payload),current=rows.at(-1),signal=mood(current),fresh=timeStatus(payload,now);
 const val=$("twVixValue"),change=$("twVixChange"),chart=$("twVixChart");
 if(!val||!change||!chart)return;
 val.textContent=money(current.value);
 change.textContent=current.change===null?"—":(current.change>0?"+":"")+money(current.change)+"（"+(current.changePct>0?"+":"")+money(current.changePct)+"%）";
 change.dataset.tone=signal.tone;
 $("twVixMood").textContent=signal.label;
 $("twVixMood").dataset.tone=signal.tone;
 $("twVixP20").textContent=percentile(rows,20)===null?"待累積":percentile(rows,20)+"%";
 $("twVixP60").textContent=percentile(rows,60)===null?"待累積":percentile(rows,60)+"%";
 $("twVixAt").textContent=current.date+" "+current.time+"（臺灣時間）";
 $("twVixGuide").textContent=signal.text;
 $("twVixStatus").textContent=fresh.text+"｜資料：臺灣期貨交易所官方日收盤";
 $("twVixStatus").dataset.stale=String(fresh.stale);
 plot(chart,rows);
}
async function load(){
 const status=$("twVixStatus");if(!status)return;
 try{
  const resp=await fetch(URL+"?t="+Date.now(),{cache:"no-store"});
  if(!resp.ok)throw Error("HTTP "+resp.status);
  render(await resp.json());
 }catch(err){
  status.textContent="台股 VIX 來源檔讀取或驗證失敗："+err.message+"。請查看來源連結，不顯示猜測數值。";
  status.dataset.stale="true";
  const value=$("twVixValue");if(value)value.textContent="—";
  const change=$("twVixChange");if(change)change.textContent="—";
 }
}
if(typeof module!=="undefined"&&module.exports)module.exports={check,percentile,mood,timeStatus,taiwanDate};
if(typeof document!=="undefined"){
 const boot=()=>{if(!$("twVixPanel"))return;$("twVixRetry")?.addEventListener("click",load);void load();};
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();
}
})(typeof window!=="undefined"?window:globalThis);
