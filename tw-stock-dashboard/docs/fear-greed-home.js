/* WantGoo Fear & Greed + S&P500 market-context chart: display only, never trades. */
(function(scope){
"use strict";
const URL="./data/research/us_fear_greed/history.json",NS="http://www.w3.org/2000/svg";
const $=id=>document.getElementById(id),finite=x=>Number.isFinite(Number(x))&&x!==""&&x!==null;
const fmt=n=>Number(n).toLocaleString("zh-TW",{maximumFractionDigits:2});
const pct=n=>(n>0?"+":"")+n.toFixed(2)+"%";
function zone(score){
 if(score<25)return {label:"極度恐懼",key:"extreme-fear",detail:"市場情緒極度悲觀"};
 if(score<45)return {label:"恐懼",key:"fear",detail:"投資人偏向防禦"};
 if(score<55)return {label:"中立",key:"neutral",detail:"市場情緒偏中性"};
 if(score<75)return {label:"貪婪",key:"greed",detail:"市場風險偏好增加"};
 return {label:"極度貪婪",key:"extreme-greed",detail:"市場樂觀情緒偏高"};
}
function validate(x){
 if(!x||!["US_WANTGOO_FEAR_GREED_SPX_V2","US_CNN_FEAR_GREED_SPX_V1"].includes(x.version)||JSON.stringify(x.columns)!=='["date","fearGreed","spx"]'||!Array.isArray(x.rows))throw Error("恐懼與貪婪歷史資料格式異常");
 let last="",rows=[];
 for(const row of x.rows){
  if(!Array.isArray(row)||row.length!==3||!/^20\d{2}-\d{2}-\d{2}$/.test(row[0])||row[0]<=last||!finite(row[1])||!finite(row[2]))throw Error("歷史日期或數值異常");
  const f=Number(row[1]),p=Number(row[2]);
  if(f<0||f>100||p<=0)throw Error("歷史資料超出合理範圍");
  rows.push([row[0],f,p]);last=row[0];
 }
 if(rows.length<150||x.asOf!==last)throw Error("歷史涵蓋率不足或最新日期不一致");
 return rows;
}
function recent(rows,range){
 if(range==="max")return rows;
 const d=new Date(rows.at(-1)[0]+"T12:00:00Z");
 d.setUTCMonth(d.getUTCMonth()-(range==="2y"?24:6));
 const cutoff=d.toISOString().slice(0,10),i=rows.findIndex(x=>x[0]>=cutoff);
 return i<0?rows:rows.slice(Math.max(0,i-1));
}
function explain(rows){
 if(!Array.isArray(rows)||rows.length<22)return null;
 const last=rows.at(-1),prev=rows.at(-2),five=rows.at(-6),twenty=rows.at(-21);
 const delta=last[1]-five[1],d1=last[1]-prev[1],r5=(last[2]/five[2]-1)*100,r20=(last[2]/twenty[2]-1)*100;
 const mood=zone(last[1]);let title,guide,risk;
 if(last[1]<25&&delta<=0){title="🔴 極度恐懼仍在惡化";guide="市場情緒十分悲觀且近5日持續走弱，價格可能繼續下跌。不要只因分數低就認定已到底部。";risk="觀察市場廣度是否回升、S&P 500是否重新站穩短期趨勢。";}
 else if(last[1]<25){title="🟠 極度恐懼開始改善";guide="情緒仍極度悲觀，但最近5日有回升；可能出現超跌反彈觀察機會，並不等於底部已確認。";risk="等價格與市場廣度同步改善，再考慮提高風險曝險。";}
 else if(last[1]>=75){title="🟡 樂觀偏高，留意追高風險";guide="市場貪婪情緒偏強，通常代表風險偏好較高，但不表示近期一定下跌。";risk="以S&P 500的價格結構、獲利了結與持倉風險為主，避免單憑情緒高點放空。";}
 else if(last[1]<45){title="🟠 偏向恐懼，觀察止跌條件";guide="市場風險偏好不足。即使分數小幅上升，仍要留意S&P 500趨勢是否繼續轉弱。";risk="價格止跌並配合台股本身的廣度與Risk Score，比單看情緒更可靠。";}
 else if(last[1]>=55){title="🟢 市場風險偏好較高";guide="市場情緒偏樂觀，但樂觀不代表無風險。";risk="觀察是否出現價格創高、情緒卻開始下滑的分歧。";}
 else{title="⚪ 市場情緒中立";guide="情緒尚未指向明顯恐懼或貪婪，不能單憑這項指標預判行情。";risk="優先確認市場價格趨勢與臺股自身訊號。";}
 return {date:last[0],value:last[1],zone:mood,delta5:delta,delta1:d1,spx5:r5,spx20:r20,
  title,guide,risk,summary:"近5交易日：情緒 "+(delta>=0?"+":"")+delta.toFixed(1)+" 分；S&P 500 "+pct(r5)+"。"};
}
const E=(tag,props={},text)=>{const e=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(props))e.setAttribute(k,String(v));if(text!==undefined)e.textContent=text;return e};
const WIDTH=1000,LEFT=52,RIGHT=20,BOTTOM=24,TOP=13;
function plot(svg,rows,column,isFear){
 const height=isFear?206:148,minX=LEFT,maxX=WIDTH-RIGHT,lo=isFear?0:Math.min(...rows.map(x=>x[column])),hi=isFear?100:Math.max(...rows.map(x=>x[column]));
 const span=hi-lo||1,pad=isFear?0:span*0.08,minY=lo-pad,maxY=hi+pad;
 const y=v=>height-BOTTOM-(v-minY)/(maxY-minY)*(height-TOP-BOTTOM);
 const x=i=>minX+(i/(rows.length-1))*(maxX-minX);
 svg.replaceChildren();svg.setAttribute("viewBox","0 0 "+WIDTH+" "+height);
 if(isFear){
  const bands=[[0,25,"#7f1d1d"],[25,45,"#b45309"],[45,55,"#475569"],[55,75,"#166534"],[75,100,"#065f46"]];
  for(const [a,b,color]of bands)svg.appendChild(E("rect",{x:minX,y:y(b),width:maxX-minX,height:y(a)-y(b),fill:color,opacity:".27"}));
 }
 for(let k=0;k<=4;k++){
  const v=minY+(maxY-minY)*k/4,Y=y(v);
  svg.appendChild(E("line",{x1:minX,x2:maxX,y1:Y,y2:Y,stroke:"#59718c","stroke-opacity":".35","stroke-dasharray":"5 6"}));
  svg.appendChild(E("text",{x:minX-7,y:Y+4,"text-anchor":"end",fill:"#cbd5e1","font-size":"12"},isFear?String(Math.round(v)):String(Math.round(v).toLocaleString("en-US"))));
 }
 const points=rows.map((r,i)=>x(i).toFixed(2)+","+y(r[column]).toFixed(2)).join(" ");
 svg.appendChild(E("polyline",{points,fill:"none",stroke:isFear?"#f8bd62":"#60cb98","stroke-width":isFear?3:2.6,"stroke-linejoin":"round","stroke-linecap":"round"}));
 for(let i=0;i<5;i++){
  const idx=Math.round((rows.length-1)*i/4);
  svg.appendChild(E("text",{x:x(idx),y:height-4,"text-anchor":i===0?"start":i===4?"end":"middle",fill:"#aebdd0","font-size":"12"},rows[idx][0].slice(2).replace(/-/g,"/")));
 }
 const line=E("line",{x1:x(rows.length-1),x2:x(rows.length-1),y1:TOP,y2:height-BOTTOM,stroke:"#f8fafc","stroke-dasharray":"4 5",opacity:".7"});
 const point=E("circle",{cx:x(rows.length-1),cy:y(rows.at(-1)[column]),r:"5",fill:isFear?"#f8bd62":"#60cb98",stroke:"#1e293b","stroke-width":"2"});
 svg.append(line,point);
 return {select(i){line.setAttribute("x1",x(i));line.setAttribute("x2",x(i));point.setAttribute("cx",x(i));point.setAttribute("cy",y(rows[i][column]));},nearest(px){return Math.max(0,Math.min(rows.length-1,Math.round((px-minX)/(maxX-minX)*(rows.length-1))))}};
}
function build(){
 const root=$("fearGreedPanel");if(!root)return;
 const output=$("fgMessage"),retry=$("fgRetry");
 let data=null,rows=null,ranges="6m",visible=[],cur=0,charts=[];
 function selection(i){
  if(!visible.length)return;
  cur=Math.max(0,Math.min(i,visible.length-1));
  for(const chart of charts)chart.select(cur);
  const r=visible[cur],z=zone(r[1]);
  $("fgSelectedDate").textContent=r[0].replace(/-/g,"/")+" · "+z.label;
  $("fgValue").textContent=r[1].toFixed(1);
  $("fgSpxValue").textContent=fmt(r[2]);
  $("fgMood").textContent=z.label;
  $("fgMood").dataset.zone=z.key;
 }
 function draw(){
  visible=recent(rows,ranges);
  const f=plot($("fgChart"),visible,1,true),s=plot($("fgSpxChart"),visible,2,false);
  charts=[f,s];selection(visible.length-1);
  for(const el of root.querySelectorAll("[data-fg-range]")){
   const selected=el.dataset.fgRange===ranges;
   el.classList.toggle("is-active",selected);el.setAttribute("aria-pressed",selected?"true":"false");
  }
 }
 function report(){
  const e=explain(rows);
  $("fgReportTitle").textContent=e.title;
  $("fgReportBody").textContent=e.guide;
  $("fgReportWatch").textContent=e.risk;
  $("fgReportContext").textContent=e.summary;
 }
 function bind(svg,index){
  function pointer(ev){
   const bounds=svg.getBoundingClientRect();if(!bounds.width)return;
   selection(charts[index].nearest((ev.clientX-bounds.left)/bounds.width*WIDTH));
  }
  svg.addEventListener("pointermove",pointer);
  svg.addEventListener("pointerdown",pointer);
  svg.addEventListener("keydown",ev=>{
   if(ev.key==="ArrowLeft"||ev.key==="ArrowRight"){ev.preventDefault();selection(cur+(ev.key==="ArrowRight"?1:-1));}
   else if(ev.key==="End"){ev.preventDefault();selection(visible.length-1);}
  });
 }
 bind($("fgChart"),0);bind($("fgSpxChart"),1);
 for(const btn of root.querySelectorAll("[data-fg-range]"))btn.addEventListener("click",()=>{ranges=btn.dataset.fgRange;draw()});
 let pending=false;
 async function load(){
  if(pending)return;pending=true;
  try{
   const response=await fetch(URL+"?t="+Date.now(),{cache:"no-store"});
   if(!response.ok)throw Error("HTTP "+response.status);
   data=await response.json();rows=validate(data);
   const freshness=scope.USMarketFreshness?.warning(data.asOf)||{stale:false,message:""};
   const fromWantgoo=data.version==="US_WANTGOO_FEAR_GREED_SPX_V2";
   $("fgSource").textContent=fromWantgoo?("WantGoo 恐懼與貪婪／S&P 500｜WantGoo資料日 "+String(data.wantgooLast||"未知")+"｜最後收盤日："+data.asOf+"｜歷史 "+rows.length+" 筆"+(data.legacyThrough?"｜"+data.legacyThrough+"（含）以前沿用舊CNN／S&P封存資料":"")):("舊版CNN封存資料（尚待WantGoo更新）｜最後共同收盤日："+data.asOf+"｜歷史 "+rows.length+" 筆");
   const alert=$("fgMarketFreshness");
   if(alert){alert.hidden=!freshness.stale;alert.textContent=freshness.message;}
   output.textContent="美股情緒是風險背景，不能直接視為台股買進或賣出訊號。低分不等於立即見底，高分也不代表必跌。";
   report();draw();retry.hidden=true;
  }catch(err){
   output.textContent="目前無法取得已驗證的恐懼與貪婪歷史資料："+err.message+"。不使用推估分數，也不把舊資料當成即時。";
   retry.hidden=false;
  }finally{pending=false}
 }
 retry.addEventListener("click",load);
 void load();
}
const api={validate,recent,zone,explain};
scope.USFearGreed=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
if(typeof document!=="undefined"){
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",build,{once:true});
 else build();
}
})(typeof window!=="undefined"?window:typeof globalThis!=="undefined"?globalThis:{});
