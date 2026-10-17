/* Full-width daily DIX / S&P 500 / GEX interactive market chart.
 * Three independent y-axis ranges: never imply common units or causality.
 * No mutation of Taiwan market score, G ranks, or execution signals.
 */
(function(scope){
"use strict";
const NS="http://www.w3.org/2000/svg",URL="./data/research/us_options/";
const SERIES=[
 {id:"dix",index:2,color:"#56baff",label:"DIX",format:v=>v.toFixed(2)+"%"},
 {id:"spx",index:1,color:"#3cdb79",label:"S&P 500",format:v=>v.toLocaleString("en-US",{maximumFractionDigits:2})},
 {id:"gex",index:3,color:"#f5c651",label:"GEX",format:v=>Math.round(v).toLocaleString("en-US")}
];
const $=id=>document.getElementById(id);
const make=(tag,attrs={},text)=>{const el=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));if(text!==undefined)el.textContent=text;return el};
const fmtDate=d=>d.replace(/-/g,"/");
const validate=d=>{
 if(!d||!Array.isArray(d.columns)||d.columns.join(",")!=="date,spx,dixPct,gex"||!Array.isArray(d.rows))throw Error("歷史資料格式異常");
 let last="",rows=[];
 for(const r of d.rows){
  if(!Array.isArray(r)||r.length!==4||!/^20\d{2}-\d{2}-\d{2}$/.test(r[0])||r[0]<=last)throw Error("日期順序異常");
  const nums=r.slice(1).map(Number);
  if(!nums.every(Number.isFinite)||nums[0]<=0||nums[1]<=0||nums[1]>=100)throw Error("不合理的來源數值");
  rows.push([r[0],...nums]);last=r[0];
 }
 if(rows.length<100||d.asOf!==last)throw Error("資料涵蓋不足或日期未核對");
 return rows;
};
const recent=(rows,range)=>{
 if(range==="max")return rows;
 const t=new Date(rows[rows.length-1][0]+"T12:00:00Z");
 t.setUTCMonth(t.getUTCMonth()-(range==="2y"?24:6));
 const cutoff=t.toISOString().slice(0,10),from=rows.findIndex(r=>r[0]>=cutoff);
 return from<0?rows:rows.slice(Math.max(0,from-1));
};
/* Uses only confirmed daily observations, never next-day data or Taiwan scores.
 * GEX comparison uses the previous 20 days' absolute-value median so a
 * positive-but-near-zero reading is not misleadingly described as stable.
 */
function dailyAnalysis(rows){
 if(!Array.isArray(rows)||rows.length<22)return null;
 const now=rows[rows.length-1],prev=rows[rows.length-2],old5=rows[rows.length-6];
 const pct=(a,b)=>b>0?100*(a/b-1):null,one=pct(now[1],prev[1]),five=pct(now[1],old5[1]);
 const dixOne=now[2]-prev[2],dixFive=now[2]-old5[2];
 const vals=rows.slice(-21,-1).map(r=>Math.abs(r[3])).filter(Number.isFinite).sort((a,b)=>a-b);
 if(![now[1],now[2],now[3],prev[1],old5[1]].every(Number.isFinite)||one===null||five===null||vals.length!==20)return null;
 const typical=(vals[9]+vals[10])/2,gexRelative=typical>0?Math.abs(now[3])/typical:null;
 const weak=five<=-1||(one<=-0.7&&five<0),strong=five>=1&&one>=0;
 const thin=gexRelative!==null&&gexRelative<0.25,negative=now[3]<0;
 const headline=weak&&(thin||negative)?"短線偏弱｜留意波動風險":weak?"價格偏弱｜反轉尚待確認":strong&&!thin&&!negative?"短線偏強｜觀察延續性":thin||negative?"方向待確認｜波動風險偏高":"市場訊號分歧｜持續觀察";
 const signed=(v,places=2)=>(v>0?"+":"")+v.toFixed(places),relative=gexRelative===null?"未取得":"約為前20日典型絕對水準的 "+(gexRelative*100).toFixed(1)+"%";
 const price="S&P 500｜單日 "+signed(one)+"%、近5日 "+signed(five)+"%，"+(weak?"短線價格偏弱。":strong?"短線價格偏強。":"方向尚待確認。");
 const dixState=dixOne>=0.8&&dixFive<0?"單日回升，但近5日仍偏弱。":dixOne<=-0.8&&dixFive>0?"單日回落，近5日仍為回升。":dixFive<=-1?"近期比率走弱。":dixFive>=1?"近5日比率回升，仍須觀察持續性。":"變化尚未形成明確方向。";
 const dix="DIX｜"+now[2].toFixed(2)+"%，單日 "+signed(dixOne)+"、近5日 "+signed(dixFive)+" 個百分點；"+dixState;
 const abs=Math.abs(now[3]),units=abs>=1e8?(abs/1e8).toFixed(2)+"億":(abs/1e4).toFixed(0)+"萬";
 const gexState=negative?"負值下，選擇權避險交易可能放大波動。":thin?"雖為正值，但緩和波動的效果可能減弱。":"正值不代表股市必漲，仍須留意波動。";
 const gex="GEX｜"+(now[3]<0?"−":"+")+units+"，"+relative+"；"+gexState;
 return {date:now[0],headline,lines:[price,dix,gex],metrics:{spx1:one,spx5:five,dix1:dixOne,dix5:dixFive,gexRelative,thin,negative},disclaimer:"依已公布美股每日收盤資料；DIX 不代表機構淨買超，GEX 非漲跌方向預測。"};
}
function renderDailyAnalysis(rows,stale){
 const area=$("usopDailyAnalysis"),title=$("usopDailyTitle"),list=$("usopDailyList"),meta=$("usopDailyMeta");
 if(!area||!title||!list||!meta)return;
 const report=dailyAnalysis(rows);
 list.replaceChildren();
 if(!report){title.textContent="資料不足，無法分析";meta.textContent="需具備至少 22 個美股交易日的完整數列。";area.dataset.state="unavailable";return}
 title.textContent=report.headline;
 for(const line of report.lines){const li=document.createElement("li");li.textContent=line;list.appendChild(li)}
 meta.textContent="資料日："+fmtDate(report.date)+(stale?"｜⚠ 歷史資料過期":"")+"｜"+report.disclaimer;
 area.dataset.state=stale?"stale":"ready";
}
function build(){
 const svg=$("usopChart"),wrap=$("usopChartWrap"),date=$("usopDate"),msg=$("usopMessage");
 if(!svg||!wrap||!date||!msg)return;
 const toggles=Array.from(document.querySelectorAll("[data-usop-series]"));
 const ranges=Array.from(document.querySelectorAll("[data-usop-range]"));
 const vals=Object.fromEntries(SERIES.map(s=>[s.id,$("usopValue"+s.id)]));
 const state={data:[],view:[],range:"6m",visible:{dix:true,spx:true,gex:true},geom:null,selected:-1};
 const bounds={},marks={},labels={},dateText=$("usopDate"),valueStatus=$("usopStatus");
 function showPoint(i){
  if(!state.view.length||!state.geom)return;
  i=Math.max(0,Math.min(state.view.length-1,i));state.selected=i;
  const row=state.view[i],geo=state.geom,x=geo.left+i/Math.max(1,state.view.length-1)*geo.plotW;
  dateText.textContent=fmtDate(row[0])+"｜美股收盤";
  marks.cross.setAttribute("x1",x);marks.cross.setAttribute("x2",x);marks.cross.style.display="";
  SERIES.forEach(s=>{
   const val=row[s.index],circle=marks[s.id];
   vals[s.id].textContent=s.format(val);
   const b=bounds[s.id],y=geo.top+(b.hi-val)/(b.hi-b.lo)*geo.plotH;
   circle.setAttribute("cx",x);circle.setAttribute("cy",y);
   circle.style.display=state.visible[s.id]?"":"none";
  });
 }
 function render(){
  if(!state.data.length)return;
  state.view=recent(state.data,state.range);state.selected=-1;
  const w=Math.max(280,Math.round(wrap.clientWidth||900)),h=w<480?275:w<720?310:376;
  svg.setAttribute("viewBox","0 0 "+w+" "+h);
  svg.setAttribute("height",h);
  svg.replaceChildren();
  const geo={left:w<450?13:22,right:w-13,top:21,bottom:h-39};
  geo.plotW=geo.right-geo.left;geo.plotH=geo.bottom-geo.top;state.geom=geo;
  const grid=make("g",{"aria-hidden":"true"});
  for(let j=0;j<=4;j++){
   const y=geo.top+geo.plotH*j/4;
   grid.appendChild(make("line",{x1:geo.left,y1:y,x2:geo.right,y2:y,stroke:"#2c3851","stroke-width":1,"stroke-dasharray":"3 5"}));
  }
  const ticks=w<500?3:5;
  for(let j=0;j<ticks;j++){
   const i=Math.round((state.view.length-1)*j/(ticks-1)),x=geo.left+geo.plotW*i/(state.view.length-1);
   grid.appendChild(make("line",{x1:x,y1:geo.top,x2:x,y2:geo.bottom,stroke:"#263349","stroke-width":1}));
   const label=state.view[i][0].slice(0,7).replace("-","/");
   grid.appendChild(make("text",{x,y:h-13,fill:"#91a0b8","font-size":w<500?10:12,"text-anchor":j===0?"start":j===ticks-1?"end":"middle"},label));
  }
  svg.appendChild(grid);
  SERIES.forEach(s=>{
   const arr=state.view.map(r=>r[s.index]);
   const rawMin=Math.min(...arr),rawMax=Math.max(...arr),span=Math.max((rawMax-rawMin),Math.abs(rawMax)*0.005,0.00001);
   bounds[s.id]={lo:rawMin-span*0.08,hi:rawMax+span*0.08};
   const b=bounds[s.id],pts=state.view.map((r,i)=>{
    const x=geo.left+(geo.plotW*i/(state.view.length-1));
    const y=geo.top+(b.hi-r[s.index])/(b.hi-b.lo)*geo.plotH;
    return(i===0?"M":"L")+x.toFixed(2)+" "+y.toFixed(2);
   }).join(" ");
   svg.appendChild(make("path",{d:pts,stroke:s.color,"stroke-width":w<480?1.8:2.25,fill:"none","stroke-linecap":"round","stroke-linejoin":"round",opacity:state.visible[s.id]?1:0,"data-path-series":s.id}));
  });
  marks.cross=make("line",{x1:0,y1:geo.top,x2:0,y2:geo.bottom,stroke:"#c6d2e1","stroke-width":1,"stroke-dasharray":"4 4",opacity:.75,"pointer-events":"none"});
  svg.appendChild(marks.cross);
  for(const s of SERIES){
   marks[s.id]=make("circle",{r:w<480?4:4.8,stroke:"#172034","stroke-width":2,fill:s.color,"pointer-events":"none"});
   svg.appendChild(marks[s.id]);
  }
  toggles.forEach(btn=>{
   const on=state.visible[btn.dataset.usopSeries];btn.setAttribute("aria-pressed",String(on));
   btn.classList.toggle("is-off",!on);
  });
  ranges.forEach(btn=>{btn.classList.toggle("is-active",btn.dataset.usopRange===state.range);btn.setAttribute("aria-pressed",String(btn.dataset.usopRange===state.range));});
  showPoint(state.view.length-1);
 }
 function move(e){
  if(!state.view.length||!state.geom)return;
  const rect=svg.getBoundingClientRect();
  // rect width corresponds to viewBox full width, not plot width.
  const full=((e.clientX-rect.left)/Math.max(1,rect.width))*svg.viewBox.baseVal.width;
  const p=(full-state.geom.left)/state.geom.plotW;
  showPoint(Math.round(p*(state.view.length-1)));
 }
 svg.addEventListener("pointermove",move);
 svg.addEventListener("pointerdown",move);
 svg.addEventListener("pointerleave",()=>showPoint(state.view.length-1));
 svg.addEventListener("keydown",e=>{
  if(!["ArrowLeft","ArrowRight","Home","End"].includes(e.key)||!state.view.length)return;
  e.preventDefault();
  const i=e.key==="Home"?0:e.key==="End"?state.view.length-1:e.key==="ArrowLeft"?state.selected-1:state.selected+1;
  showPoint(i);
 });
 for(const btn of ranges)btn.addEventListener("click",()=>{state.range=btn.dataset.usopRange;render()});
 for(const btn of toggles)btn.addEventListener("click",()=>{
  const key=btn.dataset.usopSeries;
  // Keep at least one series visible.
  if(state.visible[key]&&Object.values(state.visible).filter(Boolean).length===1)return;
  state.visible[key]=!state.visible[key];render();
 });
 if(typeof ResizeObserver!=="undefined"){const ro=new ResizeObserver(()=>{if(state.data.length)render()});ro.observe(wrap);}
 else scope.addEventListener("resize",()=>{if(state.data.length)render()});
 const retryButton=$("usopRetry");
 let pending=false;
 async function readJson(name,attempts=3){
  let lastError;
  for(let k=0;k<attempts;k++){
   const controller=typeof AbortController!=="undefined"?new AbortController():null;
   const timer=controller?setTimeout(()=>controller.abort(),12000):null;
   try{
    // A new cache key on each retry avoids a stale 404 from a Pages CDN edge.
    const url=URL+name+"?retry="+Date.now()+"-"+k;
    const res=await fetch(url,{cache:"no-store",...(controller?{signal:controller.signal}:{})});
    if(!res.ok)throw Error("HTTP "+res.status);
    return await res.json();
   }catch(e){lastError=e;
   }finally{if(timer!==null)clearTimeout(timer)}
   if(k+1<attempts)await new Promise(resolve=>setTimeout(resolve,500*(k+1)));
  }
  throw Error(name+"："+(lastError?.message||"下載失敗"));
 }
 async function loadChart(){
  if(pending)return;
  pending=true;
  if(retryButton)retryButton.hidden=true;
  date.textContent="正在載入歷史曲線…";
  msg.textContent="正在核對美股官方歷史資料…";
  try{
   // Full history is independently self-validating; latest.json is optional.
   // An out-of-order update of latest.json MUST NOT blank all existing curves.
   const hist=await readJson("history.json"),rows=validate(hist);
   state.data=rows;
   const age=(Date.now()-Date.parse(hist.asOf+"T23:59:59Z"))/86400000;
   const stale=!Number.isFinite(age)||age>8;
   valueStatus.textContent="SqueezeMetrics 官方日資料｜"+rows.length.toLocaleString("en-US")+" 個交易日"+(stale?"｜⚠ 資料過期":"");
   msg.textContent=stale?"⚠ 官方歷史資料超過八天未更新，僅供歷史觀察。":"三條線採獨立尺度比較各自變化趨勢，不能直接比較絕對高低；不是台股買賣訊號。";
   wrap.classList.remove("usop-error");
   render();
   renderDailyAnalysis(rows,stale);
   // Cross-check separately: metadata staleness is a warning, never a graph outage.
   readJson("latest.json",1).then(latest=>{
    if(latest?.date!==hist.asOf||Math.abs(Number(latest?.spx)-rows[rows.length-1][1])>1){
     valueStatus.textContent+="｜⚠ 最新摘要同步中（曲線可正常使用）";
    }
   }).catch(()=>{valueStatus.textContent+="｜⚠ 最新摘要暫不可用（曲線可正常使用）"});
  }catch(e){
   state.data=[];
   renderDailyAnalysis([],true);
   date.textContent="圖表暫時無法載入";
   valueStatus.textContent="歷史資料尚未取得";
   msg.textContent="載入失敗："+String(e?.message||e).slice(0,170)+"。可按「重試圖表」，不會影響台股風控分數。";
   wrap.classList.add("usop-error");
   // Retain <svg> and listener bindings so retry is actually functional.
   svg.replaceChildren();
   if(retryButton)retryButton.hidden=false;
   if(typeof console!=="undefined")console.warn("DIX/GEX history load",e);
  }finally{pending=false}
 }
 if(retryButton)retryButton.addEventListener("click",loadChart);
 void loadChart();
}
if(typeof document!=="undefined"){
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",build,{once:true});else build();
}
if(typeof module!=="undefined")module.exports={validate,recent,dailyAnalysis};
})(typeof window!=="undefined"?window:globalThis);
