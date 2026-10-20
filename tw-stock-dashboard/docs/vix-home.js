/* VIX family: Cboe daily closes via GitHub-generated JSON. No external chart embeds. */
(function(scope){
"use strict";
const SOURCE="./data/research/us_vix/history.json", NS="http://www.w3.org/2000/svg";
const SYMBOLS={VIX:"VIX · 30天",VIX9D:"VIX9D · 9天",VIX3M:"VIX3M · 3個月",VVIX:"VVIX · VIX波動"};
const $=id=>document.getElementById(id);
function valid(payload){
 if(!payload||payload.version!=="CBOE_VIX_DAILY_V1"||!payload.series||typeof payload.series!=="object")throw Error("VIX資料格式不符");
 const result={};
 for(const [name,obj] of Object.entries(payload.series)){
  if(!Object.hasOwn(SYMBOLS,name)||!obj||!Array.isArray(obj.rows))continue;
  let last="",clean=[];
  for(const r of obj.rows){
   if(!Array.isArray(r)||r.length!==2||!/^\d{4}-\d{2}-\d{2}$/.test(r[0])||r[0]<=last||!Number.isFinite(r[1])||r[1]<=0||r[1]>=1000)throw Error(name+" 歷史資料異常");
   clean.push([r[0],r[1]]);last=r[0];
  }
  if(clean.length<30||obj.lastDate!==last)throw Error(name+" 交易日不一致");
  result[name]=clean;
 }
 if(!result.VIX)throw Error("缺少主要VIX官方收盤紀錄");
 return result;
}
function choose(rows,range){
 if(range==="all")return rows;
 let d=new Date(rows.at(-1)[0]+"T12:00:00Z");
 if(range==="6m")d.setUTCMonth(d.getUTCMonth()-6);
 else if(range==="2y")d.setUTCFullYear(d.getUTCFullYear()-2);
 else d.setUTCFullYear(d.getUTCFullYear()-5);
 const cut=d.toISOString().slice(0,10),i=rows.findIndex(r=>r[0]>=cut);
 return i<0?rows:rows.slice(Math.max(0,i-1));
}
function sample(rows){
 const max=700;if(rows.length<=max)return rows;
 const result=[];for(let i=0;i<max;i++)result.push(rows[Math.floor(i*(rows.length-1)/(max-1))]);
 return result;
}
const node=(tag,props={},label)=>{const x=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(props))x.setAttribute(k,String(v));if(label!==undefined)x.textContent=label;return x;};
function chart(svg,rows){
 const W=1000,H=225,L=48,R=19,T=13,B=27,lo=Math.min(...rows.map(r=>r[1])),hi=Math.max(...rows.map(r=>r[1]));
 const pad=Math.max((hi-lo)*0.12,1.5),a=Math.max(0,lo-pad),b=hi+pad;
 const x=i=>L+i/(rows.length-1)*(W-L-R),y=v=>H-B-(v-a)/(b-a)*(H-T-B);
 svg.replaceChildren();svg.setAttribute("viewBox",`0 0 ${W} ${H}`);
 for(let i=0;i<5;i++){const v=a+(b-a)*i/4,Y=y(v);
  svg.append(node("line",{x1:L,x2:W-R,y1:Y,y2:Y,stroke:"#58708e","stroke-opacity":".35","stroke-dasharray":"5 5"}));
  svg.append(node("text",{x:L-8,y:Y+4,"text-anchor":"end",fill:"#c7d5e6","font-size":12},v.toFixed(1)));
 }
 const points=rows.map((r,i)=>x(i).toFixed(2)+","+y(r[1]).toFixed(2)).join(" ");
 svg.append(node("polyline",{points,fill:"none",stroke:"#c4a1ff","stroke-width":2.7,"stroke-linejoin":"round","stroke-linecap":"round"}));
 for(let i=0;i<=4;i++){const idx=Math.round((rows.length-1)*i/4);
  svg.append(node("text",{x:x(idx),y:H-5,"text-anchor":i===0?"start":i===4?"end":"middle",fill:"#b5c7dc","font-size":12},rows[idx][0].slice(2).replace(/-/g,"/")));
 }
 const ruler=node("line",{x1:0,x2:0,y1:T,y2:H-B,stroke:"#f0e5ff","stroke-dasharray":"4 5",opacity:".8"});
 const marker=node("circle",{cx:0,cy:0,r:5,fill:"#d0b3ff",stroke:"#152238","stroke-width":2});svg.append(ruler,marker);
 return {select(i){ruler.setAttribute("x1",x(i));ruler.setAttribute("x2",x(i));marker.setAttribute("cx",x(i));marker.setAttribute("cy",y(rows[i][1]));},
  nearest(px){return Math.max(0,Math.min(rows.length-1,Math.round((px-L)/(W-R-L)*(rows.length-1))))}};
}
function guidance(sym,v,d5){
 if(sym==="VVIX")return v>=130?"VIX本身的預期波動偏高，市場避險情緒可能不穩定；仍需搭配VIX、SPX判斷。":"VVIX衡量VIX的預期波動，不能直接視為股市方向訊號。";
 if(v>=35)return "預期波動非常高，注意槓桿曝險、隔夜跳空與流動性；VIX高不代表已見底。";
 if(v>=25)return "預期波動偏高，先確認SPX價格趨勢與台股市場廣度，勿只靠恐慌抄底。";
 if(v>=20)return "波動預期升高，搭配近5日VIX變化與S&P 500走勢觀察風險。";
 return d5>3?"目前水位較低但近5日快速升高，宜留意波動轉折。":"目前預期波動相對溫和，低VIX不等於沒有下跌風險。";
}
function boot(){
 const root=$("fgVixPanel");if(!root)return;
 const status=$("fgVixStatus"),svg=$("fgVixChart"),retry=$("fgVixRetry");
 let series=null,payload=null,symbol="VIX",range="6m",visible=[],idx=0,handle=null;
 const buttons=[...root.querySelectorAll("[data-vix-symbol]")],ranges=[...root.querySelectorAll("[data-vix-range]")];
 const present=()=>{
  if(!visible.length)return;
  idx=Math.min(Math.max(idx,0),visible.length-1);handle.select(idx);
  const cur=visible[idx],all=series[symbol],index=all.findIndex(r=>r[0]===cur[0]);
  const prev=index>0?all[index-1][1]:null,change=prev===null?null:((cur[1]/prev-1)*100);
  $("fgVixDate").textContent=cur[0].replace(/-/g,"/");
  $("fgVixValue").textContent=cur[1].toFixed(2);
  $("fgVixChange").textContent=change===null?"—":(change>0?"+":"")+change.toFixed(2)+"%";
  $("fgVixChange").style.color=change===null?"#d8e3f1":change>0?"#fca5a5":"#86efac";
  const win=all.slice(Math.max(0,index-251),index+1).map(x=>x[1]),rank=win.length>1?Math.round(100*win.filter(x=>x<=cur[1]).length/win.length):null;
  $("fgVixPercentile").textContent=rank===null?"—":rank+"%";
  const d5=index>=5?cur[1]-all[index-5][1]:0;
  $("fgVixGuide").textContent=guidance(symbol,cur[1],d5);
  $("fgVixGuideTitle").textContent=SYMBOLS[symbol]+"｜收盤風險解讀";
 };
 const draw=()=>{
  const source=series[symbol];if(!source||source.length<30){status.textContent=SYMBOLS[symbol]+" 官方日資料暫時未取得，請改選其他指標或使用下方Cboe連結。";const warn=$("fgVixFreshness");if(warn){warn.hidden=false;warn.textContent="⚠ 此指標目前沒有可驗證的新交易日數據。";}svg.replaceChildren();return;}
  status.textContent="資料來源：Cboe 官方每日收盤｜最新美股交易日："+source.at(-1)[0]+(payload.errors?.[symbol]?"｜⚠本次更新失敗，保留上次成功資料":"");
  const fresh=scope.USMarketFreshness?.warning(source.at(-1)[0])||{stale:false,message:""};
  const warning=$("fgVixFreshness");
  if(warning){warning.hidden=!fresh.stale;warning.textContent=fresh.message;}
  if(!warning&&fresh.stale)status.textContent+="｜"+fresh.message;
  visible=sample(choose(source,range));idx=visible.length-1;handle=chart(svg,visible);present();
  for(const b of buttons){const yes=b.dataset.vixSymbol===symbol;b.classList.toggle("is-active",yes);b.setAttribute("aria-pressed",yes?"true":"false");}
  for(const b of ranges){const yes=b.dataset.vixRange===range;b.classList.toggle("is-active",yes);b.setAttribute("aria-pressed",yes?"true":"false");}
 };
 const pick=event=>{
  if(!handle||!visible.length)return;
  const b=svg.getBoundingClientRect();if(!b.width)return;
  idx=handle.nearest((event.clientX-b.left)/b.width*1000);present();
 };
 svg.addEventListener("pointermove",pick);svg.addEventListener("pointerdown",pick);
 svg.addEventListener("keydown",event=>{if(!visible.length)return;
  if(event.key==="ArrowLeft"||event.key==="ArrowRight"){event.preventDefault();idx+=event.key==="ArrowLeft"?-1:1;present();}
  if(event.key==="End"){event.preventDefault();idx=visible.length-1;present();}
 });
 buttons.forEach(btn=>btn.addEventListener("click",()=>{symbol=btn.dataset.vixSymbol;if(series)draw()}));
 ranges.forEach(btn=>btn.addEventListener("click",()=>{range=btn.dataset.vixRange;if(series)draw()}));
 let pending=false;
 async function load(){
  if(pending)return;pending=true;retry.hidden=true;status.textContent="正在讀取Cboe已確認的每日收盤紀錄…";
  try{
   const r=await fetch(SOURCE+"?t="+Date.now(),{cache:"no-store"});
   if(!r.ok)throw Error("HTTP "+r.status);
   payload=await r.json();series=valid(payload);draw();
  }catch(err){
   status.textContent="暫時無法讀取VIX歷史資料（"+err.message+"）。此圖不會顯示假數據；請稍後重試或開啟Cboe官方連結。";
   retry.hidden=false;svg.replaceChildren();
  }finally{pending=false}
 }
 retry.addEventListener("click",load);
 void load();
}
const api={valid,choose,sample,guidance};scope.USVix=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
if(typeof document!=="undefined"){if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",boot,{once:true});else boot();}
})(typeof window!=="undefined"?window:typeof globalThis!=="undefined"?globalThis:{});
