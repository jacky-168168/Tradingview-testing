/* Financial Astrology UI: independent research display, never changes market risk. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const names={Sun:'太陽',Moon:'月亮',Mercury:'水星',Venus:'金星',Mars:'火星',Jupiter:'木星',Saturn:'土星',Uranus:'天王星',Neptune:'海王星',Pluto:'冥王星'};
const signs=['牡羊','金牛','雙子','巨蟹','獅子','處女','天秤','天蠍','射手','摩羯','水瓶','雙魚'];
const phases=['新月','盈眉月','上弦月','盈凸月','滿月','虧凸月','下弦月','殘月'];
const angles=[['合相',0],['六分相',60],['四分相',90],['三分相',120],['對分相',180]];
let dataset=null,localAstro=null,stats=null;
const fmt=(iso,tz)=>{try{return new Intl.DateTimeFormat('zh-TW',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(iso));}catch{return iso;}};
const signed=x=>(x+540)%360-180;
const escapeUnused=0; // All dynamic content is inserted using textContent only.
function cell(tr,text){const el=document.createElement('td');el.textContent=String(text);tr.appendChild(el);}
function row(table,values){const tr=document.createElement('tr');for(const value of values)cell(tr,value);table.appendChild(tr);}
function empty(table,msg,colspan){table.replaceChildren();const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=colspan;td.textContent=msg;tr.appendChild(td);table.appendChild(tr);}
const position=(A,b,date)=>{const v=A.GeoVector(b,date,true),e=A.Ecliptic(v);return {longitude:(e.elon+360)%360,latitude:e.elat};};
function localSnapshot(date){
  const A=localAstro,bodyNames=Object.keys(names),d=date.getTime(),H=3*3600000;
  const positions=bodyNames.map(body=>{
    const p=position(A,body,date),p1=position(A,body,new Date(d-H)),p2=position(A,body,new Date(d+H));
    const velocity=signed(p2.longitude-p1.longitude)/(6/24);
    return {body,longitude:p.longitude,latitude:p.latitude,sign:signs[Math.floor(p.longitude/30)],signDegree:p.longitude%30,
      velocityDegPerDay:velocity,motion:Math.abs(velocity)<.00005?'stationary':velocity<0?'retrograde':'direct'};
  });
  const phase=(A.MoonPhase(date)+360)%360,aspects=[];
  const diff=(x,y)=>Math.abs(signed(x-y));
  for(let i=0;i<positions.length;i++)for(let j=i+1;j<positions.length;j++){
    for(const [type,angle] of angles){
      const orb=Math.abs(diff(positions[i].longitude,positions[j].longitude)-angle);
      if(orb<=2)aspects.push({first:positions[i].body,second:positions[j].body,type,angle,orb});
    }
  }
  return {at:date.toISOString(),positions,moonPhase:{name:phases[Math.floor((phase+22.5)/45)%8],angle:phase},aspects:aspects.sort((x,y)=>x.orb-y.orb)};
}
function interpret(aspects){
  const out=[];
  for(const a of aspects.slice(0,5)){
    const one=names[a.first]||a.first,two=names[a.second]||a.second;
    const traditional=({
      '合相':'傳統象徵能量集中或主題放大',
      '六分相':'傳統上解讀為可協調的機會',
      '四分相':'傳統上解讀為壓力與摩擦',
      '三分相':'傳統上解讀為順暢或協同',
      '對分相':'傳統上解讀為對立與拉鋸'})[a.type];
    out.push(one+'與'+two+' '+a.type+'：'+traditional+'。');
  }
  return out.length?out.join(' '):'目前沒有 Orb ≤2° 的主要行星相位。';
}
function showSnapshot(s){
  $('atLabel').textContent=fmt(s.at,$('timezone').value);
  $('moonPhase').textContent='月相：'+s.moonPhase.name+'（角度 '+Number(s.moonPhase.angle).toFixed(1)+'°）';
  const body=$('positions');body.replaceChildren();
  for(const p of s.positions)row(body,[names[p.body]||p.body,(p.sign||signs[Math.floor(p.longitude/30)])+'座',Number(p.longitude).toFixed(2)+'°',Number(p.signDegree).toFixed(2)+'°',p.motion==='retrograde'?'逆行':p.motion==='stationary'?'駐留':'順行']);
  $('aspects').replaceChildren();
  if(!s.aspects.length)$('aspects').textContent='Orb ≤2° 的主要相位：無';
  for(const a of s.aspects){const el=document.createElement('span');el.className='pill';el.textContent=(names[a.first]||a.first)+' '+a.type+' '+(names[a.second]||a.second)+'｜'+Number(a.orb).toFixed(2)+'°';$('aspects').append(el);}
  $('interpretations').textContent=interpret(s.aspects);
}
function showEvents(){
  const list=$('events');list.replaceChildren();
  if(!dataset?.events?.length){empty(list,'尚無可用的天象事件',3);return;}
  const days=Number($('eventWindow').value)||90,now=Date.now();
  const events=dataset.events.filter(e=>Date.parse(e.utc)>=now&&Date.parse(e.utc)<=now+days*86400000).slice(0,150);
  for(const e of events)row(list,[fmt(e.utc,$('timezone').value),e.kind==='aspect'?(names[e.first]||e.first)+' '+e.name+' '+(names[e.second]||e.second):e.kind==='station'?(names[e.body]||e.body)+(e.motionAfter==='retrograde'?'開始逆行':'恢復順行'):e.name,e.kind==='aspect'?'行星相位':e.kind==='station'?'逆行轉折':'月相']);
  $('eventCount').textContent='已列出 '+events.length+'／'+dataset.events.length+' 件';
}
function showStats(){
  const market=$('market').value,horizon=$('horizon').value, r=stats?.results?.[market]?.[horizon];
  if(!r||r.status!=='verified'||r.oosVerified!==true||!Number.isFinite(r.sampleCount)){
    $('research').textContent='目前 '+market+'、事件後 '+horizon+' 交易日尚無合格且通過樣本外驗證的研究結果。顯示 N/A，絕不以傳統解讀推估勝率。';
    return;
  }
  $('research').textContent='樣本 '+r.sampleCount+' 筆｜平均報酬 '+r.meanReturnPct.toFixed(2)+'%｜上漲率 '+r.winRatePct.toFixed(1)+'%｜超額報酬 '+r.excessReturnPct.toFixed(2)+'%；請查核信賴區間、FDR 與樣本外研究報告。';
}
function taipeiInput(){const parts=new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Taipei',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date());return parts.replace(' ','T');}
function loadBrowserEngine(){
 return new Promise(resolve=>{
   if(window.Astronomy){resolve(window.Astronomy);return;}
   const tag=document.createElement('script');
   tag.src='https://cdn.jsdelivr.net/npm/astronomy-engine@2.1.19/astronomy.browser.min.js';
   tag.referrerPolicy='no-referrer';
   tag.onload=()=>resolve(window.Astronomy||null);
   tag.onerror=()=>resolve(null);
   document.head.append(tag);
 });
}
async function load(){
  $('at').value=taipeiInput();
  const [data,backtest,A]=await Promise.all([
    fetch('./data/financial_astrology/latest.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('snapshot unavailable');return r.json();}).catch(()=>null),
    fetch('./data/financial_astrology/stats.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).catch(()=>null),
    loadBrowserEngine()]);
  dataset=data;stats=backtest;localAstro=A;
  $('freshness').textContent=data?.snapshot?.at&&data.generatedAt?'星曆產生 '+fmt(data.generatedAt,'Asia/Taipei')+(Date.now()>Date.parse(data.validUntil)?'｜資料已逾時':''):'星曆資料尚未發布；本機可計算指定時間';
  if(A){showSnapshot(localSnapshot(new Date()));$('alert').textContent='';}
  else if(data?.snapshot){showSnapshot(data.snapshot);$('alert').textContent='本機星曆程式無法載入，目前僅顯示上次發布的固定時間星盤，無法計算任意時間。';}
  else{$('alert').textContent='星曆來源無法取得；不展示推算星盤。';empty($('positions'),'星曆暫不可用',5);}
  showEvents();showStats();
}
$('calculate').addEventListener('click',()=>{
  if(!localAstro){$('alert').textContent='星曆程式無法使用，無法計算指定日期。';return;}
  const v=$('at').value;const d=new Date(v+':00+08:00');
  if(!Number.isFinite(d.getTime())){$('alert').textContent='請輸入有效的台灣時間。';return;}
  try{showSnapshot(localSnapshot(d));$('alert').textContent='';}catch{$('alert').textContent='天文計算失敗，請改用其他有效時間。';}
});
$('timezone').addEventListener('change',()=>{if(window.__astroDisplayed?.at)showSnapshot(window.__astroDisplayed);showEvents();});
const oldShow=showSnapshot;showSnapshot=function(s){window.__astroDisplayed=s;oldShow(s);};
$('eventWindow').addEventListener('change',showEvents);
$('market').addEventListener('change',showStats);$('horizon').addEventListener('change',showStats);
load().catch(()=>{$('alert').textContent='資料初始化失敗，請檢查星曆檔案與發布狀態。';});
})();