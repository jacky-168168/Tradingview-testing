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
   svg.appendChild(make("path",{d:pts,stroke:s.color,"stroke-width":w<480?1.8:2.25,fill:"none","stroke-linecap":"round","stroke-linejoin":"round",opacity:state.visible[s.id]?1:0.04,"data-path-series":s.id}));
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
  const rect=svg.getBoundingClientRect(),x=((e.clientX-rect.left)/Math.max(1,rect.width))*state.geom.right;
  // rect width corresponds to viewBox full width, not plot width.
  const vb=svg.viewBox.baseVal,w=vb.width||rect.width,full=((e.clientX-rect.left)/rect.width)*w;
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
 (async()=>{
  try{
   const [histRes,latestRes]=await Promise.all([
    fetch(URL+"history.json?cache="+Date.now(),{cache:"no-store"}),
    fetch(URL+"latest.json?cache="+Date.now(),{cache:"no-store"})
   ]);
   if(!histRes.ok||!latestRes.ok)throw Error("資料尚未同步");
   const [hist,latest]=await Promise.all([histRes.json(),latestRes.json()]);
   const rows=validate(hist);
   if(latest.date!==hist.asOf||Math.abs(latest.spx-rows[rows.length-1][1])>1)throw Error("最新數據與圖表日期不一致");
   state.data=rows;
   const age=(Date.now()-Date.parse(hist.asOf+"T23:59:59Z"))/86400000;
   const stale=!Number.isFinite(age)||age>8;
   valueStatus.textContent="SqueezeMetrics 官方日資料｜"+rows.length.toLocaleString("en-US")+" 個交易日"+(stale?"｜⚠ 資料過期":"");
   msg.textContent=stale?"⚠ 官方資料超過八天未更新，僅供歷史觀察。":"三條線採獨立尺度比較各自的變化趨勢，不能比較線條的絕對高低；不是台股買賣訊號。";
   render();
  }catch(e){
   date.textContent="無法載入歷史曲線";
   valueStatus.textContent="尚無可核對的走勢資料";
   msg.textContent="圖表來源尚未同步或日期核對失敗；不顯示虛構曲線。";
   wrap.textContent="圖表資料暫時不可用，請稍後重試。";
   wrap.classList.add("usop-error");
  }
 })();
}
if(typeof document!=="undefined"){
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",build,{once:true});else build();
}
if(typeof module!=="undefined")module.exports={validate,recent};
})(typeof window!=="undefined"?window:globalThis);
