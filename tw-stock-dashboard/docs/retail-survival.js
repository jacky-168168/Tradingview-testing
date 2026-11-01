/* 散戶存活率／第三方估算融資維持率。資料不足時不虛構 K 棒。 */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const el=$('retailSurvival');if(!el)return;
const canvas=$('retailChart'),ctx=canvas.getContext('2d'),tip=$('retailTooltip');
const scope=$('retailScope'),days=$('retailDays'),fmt=new Intl.NumberFormat('zh-TW',{maximumFractionDigits:2});
const state={rows:[],view:[],type:'listed',count:60,selected:-1,plot:null};
const n=v=>Number(v),ok=v=>Number.isFinite(n(v)),num=v=>ok(v)?fmt.format(n(v)):'—';
const signed=v=>ok(v)?(v>0?'+':'')+Number(v).toFixed(2):'—';
const nowDay=()=>{const parts=new Intl.DateTimeFormat('en-US',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(new Date());const obj={};parts.forEach(p=>obj[p.type]=p.value);return obj.year+'-'+obj.month+'-'+obj.day};
function valid(r){return r&&/^20\d{2}-\d{2}-\d{2}$/.test(r.date)&&['listed','otc','overall','indexClose'].every(k=>ok(r[k]))&&n(r.overall)>75&&n(r.overall)<400&&n(r.indexClose)>3000}
function delta(i){return i>0?state.view[i][state.type]-state.view[i-1][state.type]:null}
function metric(row){return row?n(row[state.type]):null}
function updateStats(){const rows=state.rows.filter(r=>ok(r[state.type])&&n(r[state.type])>75);if(!rows.length)return;const i=rows.length-1,r=rows[i],before=rows[i-1],d=before?n(r[state.type])-n(before[state.type]):null;
 $('retailCurrent').textContent=num(r[state.type])+'%';
 $('retailChange').textContent=d===null?'—':signed(d)+' 個百分點';
 $('retailChange').className=d!==null?(d>=0?'retail-positive':'retail-negative'):'';
 $('retailIndex').textContent=num(r.indexClose);
 $('retailDate').textContent=r.date;
 $('retailAsOf').textContent='資料日 '+r.date+'（盤後）';
 const oldDays=(Date.parse(nowDay()+'T00:00:00Z')-Date.parse(r.date+'T00:00:00Z'))/86400000;
 const stale=oldDays>5;
 $('retailStatus').className='retail-status'+(stale?'':' ok');
 $('retailStatus').textContent=stale?'資料已超過 5 個日曆日，請勿視為最新盤後指標。':'最新已收錄交易日 '+r.date+'；未公布的新交易日不會提前填值。';
}
function table(){const all=state.rows.filter(r=>ok(r[state.type])&&n(r[state.type])>75),a=all.slice(-7).reverse();let html='';
 for(const r of a){const i=all.indexOf(r),prior=all[i-1],d=prior?n(r[state.type])-n(prior[state.type]):null;const cls=d===null?'':d>=0?'retail-positive':'retail-negative';
 html+='<tr><td>'+r.date.slice(5)+'</td><td>'+num(r.indexClose)+'</td><td>'+num(r[state.type])+'%</td><td class="'+cls+'">'+(d===null?'—':signed(d))+'</td></tr>';}
 $('retailTbody').innerHTML=html;
}
function draw(){const rect=canvas.getBoundingClientRect(),w=Math.max(280,rect.width),h=Math.max(260,rect.height),dpr=Math.min(window.devicePixelRatio||1,2);
 canvas.width=Math.floor(w*dpr);canvas.height=Math.floor(h*dpr);ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
 const view=state.view;if(!view.length)return;
 const mobile=w<600,left=mobile?36:53,right=mobile?38:65,top=16,bottom=27,mid=h*.47,split=14,plotW=w-left-right;
 const rates=view.map(x=>metric(x)),closes=view.map(x=>n(x.indexClose)),highs=view.map(x=>ok(x.indexHigh)?n(x.indexHigh):n(x.indexClose)),lows=view.map(x=>ok(x.indexLow)?n(x.indexLow):n(x.indexClose));
 const ixMin=Math.min(...lows),ixMax=Math.max(...highs),ixPad=Math.max(100,(ixMax-ixMin)*.12),loI=ixMin-ixPad,hiI=ixMax+ixPad;
 const loR=Math.min(110,Math.floor((Math.min(...rates)-12)/10)*10),hiR=Math.max(220,Math.ceil((Math.max(...rates)+12)/10)*10);
 const upperTop=top,upperBottom=mid,lowerTop=mid+split,lowerBottom=h-bottom;
 const x=i=>left+plotW*(i+.5)/view.length;
 const iy=v=>upperBottom-(v-loI)/(hiI-loI)*(upperBottom-upperTop);
 const ry=v=>lowerBottom-(v-loR)/(hiR-loR)*(lowerBottom-lowerTop);
 const cw=Math.max(1,Math.min(9,plotW/view.length*.55));
 state.plot={left,plotW,x};
 ctx.font=(mobile?'9px':'10px')+' -apple-system,BlinkMacSystemFont,"Noto Sans TC",sans-serif';ctx.textAlign='right';ctx.lineWidth=1;
 function grid(min,max,y,labels,suffix){for(let i=0;i<=4;i++){const val=min+(max-min)*i/4,yy=y(val);ctx.strokeStyle='#e7edf3';ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(w-right,yy);ctx.stroke();ctx.fillStyle='#64748b';ctx.textAlign='right';ctx.fillText(labels(val)+suffix,left-5,yy+3)}}
 grid(loI,hiI,iy,v=>Math.round(v).toLocaleString('en-US'),'');
 grid(loR,hiR,ry,v=>Math.round(v),'%');
 ctx.fillStyle='#475569';ctx.textAlign='left';ctx.fillText('加權指數 日 K／收盤',left+3,upperTop+10);ctx.fillText('融資維持率（%）',left+3,lowerTop+10);
 // 上方只對有 OHLC 的交易日畫 K，否則畫真實收盤連線，不產生假 K 棒。
 ctx.beginPath();ctx.strokeStyle='#64748b';ctx.lineWidth=1.2;closes.forEach((c,i)=>i===0?ctx.moveTo(x(i),iy(c)):ctx.lineTo(x(i),iy(c)));ctx.stroke();
 view.forEach((r,i)=>{const o=n(r.indexOpen),c=n(r.indexOhlcClose),hi=n(r.indexHigh),lo=n(r.indexLow);
 if(![o,c,hi,lo].every(Number.isFinite)||hi<Math.max(o,c)||lo>Math.min(o,c))return;
 const color=c>=o?'#d93641':'#15803d';ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=1;
 ctx.beginPath();ctx.moveTo(x(i),iy(hi));ctx.lineTo(x(i),iy(lo));ctx.stroke();
 const y1=iy(Math.max(o,c)),y2=iy(Math.min(o,c));ctx.fillRect(x(i)-cw/2,y1,cw,Math.max(1,y2-y1));
 });
 // 固定 160% 參考線
 const refY=ry(160);ctx.beginPath();ctx.setLineDash([6,4]);ctx.strokeStyle='#1780c1';ctx.lineWidth=2;ctx.moveTo(left,refY);ctx.lineTo(w-right,refY);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#1780c1';ctx.textAlign='left';ctx.fillText('160%',w-right+4,refY+3);
 // 風險色帶只做視覺參考，不代表個人維持率
 const grad=ctx.createLinearGradient(0,lowerTop,0,lowerBottom);grad.addColorStop(0,'rgba(222,47,56,.86)');grad.addColorStop(.35,'rgba(249,183,42,.8)');grad.addColorStop(.64,'rgba(224,223,65,.78)');grad.addColorStop(1,'rgba(30,129,138,.84)');
 ctx.beginPath();rates.forEach((v,i)=>i===0?ctx.moveTo(x(i),ry(v)):ctx.lineTo(x(i),ry(v)));ctx.lineTo(x(view.length-1),lowerBottom);ctx.lineTo(x(0),lowerBottom);ctx.closePath();ctx.fillStyle=grad;ctx.fill();
 ctx.beginPath();rates.forEach((v,i)=>i===0?ctx.moveTo(x(i),ry(v)):ctx.lineTo(x(i),ry(v)));ctx.strokeStyle='#132a60';ctx.lineWidth=2.2;ctx.stroke();
 if(state.selected>=0&&state.selected<view.length){const i=state.selected;ctx.beginPath();ctx.setLineDash([3,4]);ctx.strokeStyle='#475569';ctx.moveTo(x(i),top);ctx.lineTo(x(i),lowerBottom);ctx.stroke();ctx.setLineDash([]);ctx.beginPath();ctx.arc(x(i),ry(rates[i]),4,0,Math.PI*2);ctx.fillStyle='#132a60';ctx.fill();}
 ctx.fillStyle='#64748b';ctx.textAlign='center';
 const step=Math.max(1,Math.ceil(view.length/(mobile?4:8)));
 for(let i=0;i<view.length;i+=step)ctx.fillText(view[i].date.slice(5),x(i),h-9);
 ctx.fillText(view[view.length-1].date.slice(5),x(view.length-1),h-9);
}
function showTip(i){if(i<0||i>=state.view.length)return;state.selected=i;const r=state.view[i],d=delta(i),k=ok(r.indexOpen)?'開 '+num(r.indexOpen)+'｜高 '+num(r.indexHigh)+'｜低 '+num(r.indexLow)+'｜收 '+num(r.indexOhlcClose):'僅有指數收盤，OHLC 待補';
 tip.textContent=r.date+'｜'+scope.options[scope.selectedIndex].text+' '+num(r[state.type])+'%（'+(d===null?'—':signed(d))+'）｜指數 '+num(r.indexClose)+'｜'+k;tip.hidden=false;draw();}
async function load(){try{
 const response=await fetch('./data/retail_survival/latest.json?nocache='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('HTTP '+response.status);
 const data=await response.json();if(data.schema!=='retail-survival-v1'||!Array.isArray(data.rows))throw Error('格式不相容');
 state.rows=data.rows.filter(valid).sort((a,b)=>a.date.localeCompare(b.date));if(!state.rows.length)throw Error('無合法交易日數據');
 $('retailSourceLink').href=data.source&&/^https:\/\//.test(data.source.url)?data.source.url:'https://www.istock.tw/post/twmarginrequirement_more';
 render();
 }catch(e){$('retailStatus').textContent='融資維持率無法載入：'+e.message+'。不顯示推測數字。';$('retailStatus').className='retail-status';}}
function render(){state.view=state.rows.filter(r=>ok(r[state.type])&&n(r[state.type])>75).slice(-state.count);state.selected=-1;tip.hidden=true;if(!state.view.length){$('retailStatus').textContent='所選市場別目前沒有可核對資料。';return;}updateStats();table();draw();}
scope.addEventListener('change',()=>{state.type=scope.value;render();});
days.addEventListener('change',()=>{state.count=Number(days.value);render();});
canvas.addEventListener('pointermove',ev=>{if(!state.plot||!state.view.length)return;const rect=canvas.getBoundingClientRect(),p=(ev.clientX-rect.left-state.plot.left)/state.plot.plotW;showTip(Math.min(state.view.length-1,Math.max(0,Math.floor(p*state.view.length))));});
canvas.addEventListener('pointerleave',()=>{state.selected=-1;tip.hidden=true;draw();});
canvas.addEventListener('click',ev=>{if(!state.plot)return;const rect=canvas.getBoundingClientRect(),p=(ev.clientX-rect.left-state.plot.left)/state.plot.plotW;showTip(Math.min(state.view.length-1,Math.max(0,Math.floor(p*state.view.length))));});
if(typeof ResizeObserver!=='undefined')new ResizeObserver(()=>draw()).observe(canvas);else window.addEventListener('resize',draw);
load();})();
