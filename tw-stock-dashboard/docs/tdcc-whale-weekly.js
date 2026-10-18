/* 400+ lot TDCC whale weekly quadrant renderer; public EOD research, not a trade signal. */
(function(root){
"use strict";
const URL="./data/research/tdcc_whales/latest.json";
const ORDER=["續買","回頭車","下車","續賣"];
const IDEAS={
 "續買":"連續兩期大戶持股比率增加",
 "回頭車":"前期下降，本期重新增加",
 "下車":"前期增加，本期轉為下降",
 "續賣":"連續兩期大戶持股比率下降"
};
const $=id=>document.getElementById(id);
const esc=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=(v,s=2)=>Number(v).toLocaleString("zh-TW",{minimumFractionDigits:s,maximumFractionDigits:s});
const signed=(v,unit="")=>(v>0?"+":"")+fmt(v)+unit;
function validate(doc){
 if(!doc||doc.version!=="TDCC_WHALE_400_QUADRANTS_V1"||!doc.quadrants||doc.thresholdPP!==1.0)throw Error("四象限週報格式異常");
 if(!/^\d{4}-\d{2}-\d{2}$/.test(doc.date)||!(doc.twoWeeksBefore<doc.priorDate&&doc.priorDate<doc.date))throw Error("歷史基準日順序錯誤");
 const seen=new Set;
 for(const key of ORDER){
  const group=doc.quadrants[key];
  if(!group||!Array.isArray(group.rows)||group.count!==group.rows.length)throw Error(key+" 資料數量不符");
  for(const x of group.rows){
   if(!/^\d{4}$/.test(String(x.code))||!Number.isFinite(x.previousPP)||!Number.isFinite(x.currentPP)||!Number.isFinite(x.bigHolderRatio))throw Error(key+" 個股欄位錯誤");
   if(Math.abs(x.previousPP)<.995||Math.abs(x.currentPP)<.995)throw Error("未通過1百分點門檻");
   if(x.bigHolderRatio<0||x.bigHolderRatio>100)throw Error("大戶占比異常");
   if(x.priceReturnPct!==null&&!Number.isFinite(x.priceReturnPct))throw Error("股價反應格式異常");
   if((x.previousPP>0)!==(key==="續買"||key==="下車")||(x.currentPP>0)!==(key==="續買"||key==="回頭車"))throw Error("四象限方向錯誤");
   if(seen.has(x.code))throw Error("重複入榜 "+x.code);
   seen.add(x.code);
  }
 }
 return doc;
}
const priceCls=n=>n>0?"is-red":n<0?"is-green":"is-neutral";
const toDate=s=>s.replace(/-/g,"/");
function build(){
 const panel=$("tdccWhalePanel");
 if(!panel)return;
 const status=$("tdccWhaleStatus"),cards=$("tdccWhaleCards"),retry=$("tdccWhaleRetry");
 let loading=false;
 function card(k,g,showAll){
  const rows=showAll?g.rows:g.rows.slice(0,12),n=g.count;
  const body=rows.map(x=>'<div class="whale-stock">'+
    '<span class="whale-name">'+esc(x.name)+' <small>'+esc(x.code)+'</small></span>'+
    '<span class="whale-flow">'+signed(x.previousPP)+' → '+signed(x.currentPP)+' <small>pp</small></span>'+
    '<span class="whale-return '+(x.priceReturnPct===null?"is-neutral":priceCls(x.priceReturnPct))+'">'+(x.priceReturnPct===null?"未取得":signed(x.priceReturnPct,"%"))+'</span>'+
    '</div>').join("");
  const mark=k==="續買"?"↗":k==="回頭車"?"↻":k==="下車"?"↘":"↙";
  return '<article class="whale-quadrant" data-whale-category="'+esc(k)+'">'+
    '<header class="whale-quadrant-head"><div class="whale-quadrant-title"><strong>'+mark+' '+esc(k)+'</strong><span>'+n+' 檔</span><small>'+esc(IDEAS[k])+'</small></div>'+
    '<div class="whale-week-returns">'+(g.avgPriceReturnPct===null?"本週股價未取得":'本週股價：平均 <b class="'+priceCls(g.avgPriceReturnPct)+'">'+signed(g.avgPriceReturnPct,"%")+'</b>｜上漲 '+g.upCount+'/'+g.priceCount+' 檔')+'</div></header>'+
    '<div class="whale-row-head"><span>股票</span><span>前週 → 本週（pp）</span><span>股價漲跌</span></div>'+
    '<div class="whale-grid">'+(body||'<p class="whale-none">本週無符合條件的股票</p>')+'</div>'+
    (n>12?'<button type="button" class="whale-expand" data-whale-expand="'+esc(k)+'" aria-expanded="'+(showAll?'true':'false')+'">'+(showAll?'收合':'顯示其餘 '+(n-12)+' 檔')+'</button>':'')+
    '</article>';
 }
 async function load(){
  if(loading)return;loading=true;retry.hidden=true;
  status.textContent="正在核對本週集保股權分散資料與價格…";
  try{
   const response=await fetch(URL+"?t="+Date.now(),{cache:"no-store"});
   if(!response.ok)throw Error("HTTP "+response.status);
   const data=validate(await response.json());
   const age=Math.floor((Date.now()-new Date(data.date+"T12:00:00+08:00").getTime())/86400000);
   $("tdccWhaleDates").textContent="集保週資料："+toDate(data.date)+" vs "+toDate(data.priorDate)+" vs "+toDate(data.twoWeeksBefore);
   $("tdccWhaleCoverage").textContent="官方集保1-5級距｜400張以上比率｜上市＋上櫃｜股價本週反應｜"+(age>12?"⚠ 最近一期較舊":"每週更新");
   const expanded=new Set;
   function draw(){
    cards.innerHTML=ORDER.map(k=>card(k,data.quadrants[k],expanded.has(k))).join("");
    for(const btn of cards.querySelectorAll("[data-whale-expand]")){
     btn.addEventListener("click",()=>{
      const key=btn.dataset.whaleExpand;
      if(expanded.has(key))expanded.delete(key);else expanded.add(key);
      draw();
     });
    }
   }
   draw();
   const total=ORDER.reduce((n,k)=>n+data.quadrants[k].count,0);
   status.textContent="本期 "+total+" 檔符合公開條件，前兩期變動均至少1個百分點。原圖還有未公開的入榜條件，檔數不一定相同。"+(age>12?"（資料逾12日，請確認是否有新一期）":"");
   $("tdccWhaleFoot").textContent="比率＝持有400,001股以上之集保股數／集保總股數；變化單位為百分點（pp），不是實際買賣張數。排除集保合計股數單週變動逾5%的個股。股價是兩個公布基準日間的調整後收盤漲跌；無資料顯示未取得。資料：臺灣集中保管結算所，歷史原始檔備份。";
  }catch(e){
   status.textContent="本週資料尚未取得完整驗證結果："+e.message+"。不以舊報告冒充新資料，也不使用假數字。";
   cards.replaceChildren();retry.hidden=false;
  }finally{loading=false}
 }
 retry.addEventListener("click",load);
 load();
}
const api={validate,priceCls,ORDER,IDEAS};
root.TDCCWhaleWeekly=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
if(typeof document!=="undefined"){
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",build,{once:true});
 else build();
}
})(typeof window!=="undefined"?window:typeof globalThis!=="undefined"?globalThis:{});
