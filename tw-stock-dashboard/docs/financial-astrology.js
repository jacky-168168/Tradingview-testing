/* Financial Astrology Research Center V1.0: read-only, no trading signals. */
(function(){
  'use strict';
  const el=id=>document.getElementById(id);
  const state={ephemeris:null,calendar:null,report:null,liveMode:true};
  const zones=new Set(['Asia/Taipei','America/New_York','Europe/London','Europe/Berlin','Europe/Paris']);
  const bodyNames={Sun:'太陽',Moon:'月亮',Mercury:'水星',Venus:'金星',Mars:'火星',
    Jupiter:'木星',Saturn:'土星',Uranus:'天王星',Neptune:'海王星',Pluto:'冥王星'};
  const aspects={conjunction:'合相',sextile:'六分相',square:'四分相',trine:'三分相',opposition:'對分'};
  const motion={direct:'順行',retrograde:'逆行',stationary:'留'};
  const show=(id,value)=>{const target=el(id);if(target)target.textContent=value;};
  const percent=(x,dp=2)=>typeof x==='number'&&Number.isFinite(x)?(x*100).toFixed(dp)+'%':'—';
  const number=(x,dp=2)=>typeof x==='number'&&Number.isFinite(x)?x.toFixed(dp):'—';
  const when=(x)=>{
    if(!x)return '—';
    const tz=zones.has(el('astroTimezone').value)?el('astroTimezone').value:'Asia/Taipei';
    const t=new Date(x);if(!Number.isFinite(t.getTime()))return '時間格式錯誤';
    return new Intl.DateTimeFormat('zh-TW',{timeZone:tz,year:'numeric',month:'2-digit',day:'2-digit',
      hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(t);
  };
  async function load(file){
    const response=await fetch('./data/financial_astrology/'+file+'?cache='+Date.now(),{cache:'no-store'});
    if(!response.ok)throw new Error(file+' HTTP '+response.status);
    return response.json();
  }
  function cell(tr,value,tag='td'){
    const n=document.createElement(tag);n.textContent=String(value??'—');tr.appendChild(n);
  }
  function row(parent,values){
    const tr=document.createElement('tr');
    for(const item of values)cell(tr,item);
    parent.appendChild(tr);
  }

  const PLANETS=['Sun','Moon','Mercury','Venus','Mars','Jupiter','Saturn','Uranus','Neptune','Pluto'];
  const ZODIAC=['牡羊','金牛','雙子','巨蟹','獅子','處女','天秤','天蠍','射手','摩羯','水瓶','雙魚'];
  const SYMBOLS={Sun:'☉',Moon:'☽',Mercury:'☿',Venus:'♀',Mars:'♂',Jupiter:'♃',Saturn:'♄',Uranus:'♅',Neptune:'♆',Pluto:'♇'};
  const ZODIAC_SYMBOLS=['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓'];
  const ASPECT_ANGLES=[['conjunction',0],['sextile',60],['square',90],['trine',120],['opposition',180]];
  const wrap=x=>((x%360)+360)%360;
  const delta=x=>wrap(x+180)-180;
  function positionClient(name,whenDate){
    if(!window.Astronomy)throw new Error('Astronomy Engine 尚未載入');
    const A=window.Astronomy;
    const point=t=>name==='Moon'?A.EclipticGeoMoon(t):A.Ecliptic(A.GeoVector(A.Body[name],t,true));
    const current=point(whenDate);
    const longitude=wrap(name==='Moon'?current.lon:current.elon);
    const latitude=name==='Moon'?current.lat:current.elat;
    const before=point(new Date(whenDate.getTime()-6*3600000));
    const after=point(new Date(whenDate.getTime()+6*3600000));
    const left=wrap(name==='Moon'?before.lon:before.elon);
    const right=wrap(name==='Moon'?after.lon:after.elon);
    const speed=delta(right-left)*2;
    return {name, longitudeDeg:longitude,latitudeDeg:latitude,
      sign:ZODIAC[Math.floor(longitude/30)],signDegree:longitude%30,
      speedDegPerDay:speed,motion:Math.abs(speed)<0.015?'stationary':speed<0?'retrograde':'direct'};
  }
  function snapshotClient(time){
    const now=new Date(time);
    if(!Number.isFinite(now.getTime())||now.getUTCFullYear()<1900||now.getUTCFullYear()>2100)
      throw new Error('僅支援西元1900～2100年的有效UTC時間');
    const positions=PLANETS.map(name=>positionClient(name,now));
    const aspectsFound=[];
    for(let i=0;i<positions.length;i++) for(let j=i+1;j<positions.length;j++){
      const a=positions[i],b=positions[j];
      const angle=Math.abs(delta(a.longitudeDeg-b.longitudeDeg));
      const future=Math.abs(delta((a.longitudeDeg+a.speedDegPerDay/24)-(b.longitudeDeg+b.speedDegPerDay/24)));
      for(const [aspect,targetAngleDeg] of ASPECT_ANGLES){
        const orbErrorDeg=Math.abs(angle-targetAngleDeg);
        if(orbErrorDeg>2)continue;
        aspectsFound.push({bodyA:a.name,bodyB:b.name,aspect,targetAngleDeg,
          actualAngleDeg:angle,orbErrorDeg,applying:Math.abs(future-targetAngleDeg)<orbErrorDeg});
      }
    }
    aspectsFound.sort((a,b)=>a.orbErrorDeg-b.orbErrorDeg);
    const phase=window.Astronomy.MoonPhase(now);
    const phaseLabel=phase<22.5||phase>=337.5?'新月附近':
      phase<157.5?'盈月':phase<202.5?'滿月附近':'虧月';
    return {generatedAt:now.toISOString(),positions,aspects:aspectsFound,
      moon:{phaseAngleDeg:phase,phaseLabel},liveComputed:true,orbDeg:2};
  }
  function drawWheel(data){
    const svg=el('astroWheel');
    if(!svg||!data?.positions)return;
    const ns='http://www.w3.org/2000/svg';
    svg.replaceChildren();
    const node=(tag,attrs,txt)=>{
      const element=document.createElementNS(ns,tag);
      Object.keys(attrs||{}).forEach(k=>element.setAttribute(k,attrs[k]));
      if(txt!==undefined)element.textContent=txt;
      svg.appendChild(element);
      return element;
    };
    const xy=(angle,r)=>{const a=(angle-90)*Math.PI/180;return [200+r*Math.cos(a),200+r*Math.sin(a)];};
    node('circle',{cx:200,cy:200,r:190,fill:'#fcfbff',stroke:'#b3aed2','stroke-width':2});
    node('circle',{cx:200,cy:200,r:148,fill:'#f7f8fc',stroke:'#cec8e6','stroke-width':1.5});
    node('circle',{cx:200,cy:200,r:101,fill:'#fff',stroke:'#cec8e6','stroke-width':1.5});
    for(let i=0;i<12;i++){
      const [x1,y1]=xy(i*30,148),[x2,y2]=xy(i*30,190);
      node('line',{x1,y1,x2,y2,stroke:'#d6d2e6','stroke-width':1});
      const [lx,ly]=xy(i*30+15,168);
      node('text',{x:lx,y:ly,'text-anchor':'middle','dominant-baseline':'middle',
        fill:'#61518d','font-size':19},ZODIAC_SYMBOLS[i]);
    }
    // Colour lines are decorative aspect geometry, never trading direction.
    for(const a of data.aspects||[]){
      const pa=data.positions.find(p=>p.name===a.bodyA);
      const pb=data.positions.find(p=>p.name===a.bodyB);
      if(!pa||!pb)continue;
      const [x1,y1]=xy(pa.longitudeDeg,98),[x2,y2]=xy(pb.longitudeDeg,98);
      node('line',{x1,y1,x2,y2,stroke:a.aspect==='square'||a.aspect==='opposition'?'#cb8d91':'#8a9dcc',
        'stroke-opacity':'.55','stroke-width':1.2});
    }
    // Alternating radial lanes reduce overlap near conjunctions.
    const sorted=[...data.positions].sort((a,b)=>a.longitudeDeg-b.longitudeDeg);
    for(let i=0;i<sorted.length;i++){
      const p=sorted[i],angle=p.longitudeDeg;
      const [px,py]=xy(angle,105);
      node('circle',{cx:px,cy:py,r:3.3,fill:'#6553aa'});
      const [tx,ty]=xy(angle,i%2?121:138);
      const text=node('text',{x:tx,y:ty,'text-anchor':'middle','dominant-baseline':'middle',
        'font-size':15,'font-weight':'bold',fill:'#352d6c'},SYMBOLS[p.name]||p.name[0]);
      const title=document.createElementNS(ns,'title');
      title.textContent=(bodyNames[p.name]||p.name)+'｜'+p.sign+' '+number(p.signDegree,2)+'°';
      text.appendChild(title);
    }
    node('text',{x:200,y:196,'text-anchor':'middle','font-size':12,fill:'#62637c'},'地心熱帶黃道');
    node('text',{x:200,y:212,'text-anchor':'middle','font-size':12,fill:'#62637c'},'行星與五大相位');
  }
  function calculateSelected(){
    const input=el('astroQueryTime')?.value;
    if(!input){show('astroSummary','請先選擇 UTC 日期與時間');return;}
    try{
      const timestamp=new Date(input+':00+08:00');
      state.liveMode=false;
      state.ephemeris=snapshotClient(timestamp);
      renderEphemeris();
      if(state.report)renderBacktest();
      show('astroWheelCaption','所選時間：'+input.replace('T',' ')+'（台灣時間）；星盤以天文演算法計算。');
    }catch(e){show('astroSummary','無法計算指定星盤：'+e.message);}
  }
  function setTimeInput(date){
    el('astroQueryTime').value=new Date(new Date(date).getTime()+8*3600000).toISOString().slice(0,16);
  }

  function refreshLiveChart(){
    if(!state.liveMode)return;
    if(!window.Astronomy){
      show('astroUpdated','即時星盤暫時無法計算');
      return;
    }
    try{
      const now=new Date();
      state.ephemeris=snapshotClient(now);
      setTimeInput(now);
      renderEphemeris();
      if(state.report)renderBacktest();
      show('astroWheelCaption','目前星盤：'+when(now.toISOString())+'｜每分鐘自動更新');
    }catch(error){
      show('astroUpdated','即時星盤暫時無法計算');
      show('astroSummary','無法計算目前星盤：'+error.message);
    }
  }
  function renderEphemeris(){
    const data=state.ephemeris;
    if(!data?.positions?.length){
      show('astroSummary','天文資料尚未發布或暫時無法讀取。');
      show('astroUpdated','星曆待更新');
      el('astroPlanets').replaceChildren();
      show('astroAspects','無法讀取星象相位');
      if(window.FinancialAstrologyInterpret)window.FinancialAstrologyInterpret.render(null);
      return;
    }
    const stale=!data.liveComputed && (Date.now()-Date.parse(data.generatedAt))>48*3600000;
    show('astroUpdated',when(data.generatedAt)+(data.liveComputed?'（星曆即時計算）':stale?'（逾48小時，非即時）':'（快照）'));
    show('astroSummary','月相角 '+number(data.moon?.phaseAngleDeg)+'°（'+(data.moon?.phaseLabel||'—')+
      '）；當前符合 2° Orb 的主要相位 '+(data.aspects?.length||0)+' 組。'+
      '此處僅為可重現天文資料，不提供已驗證買賣建議。');
    drawWheel(data);
    if(window.FinancialAstrologyInterpret)window.FinancialAstrologyInterpret.render(data);
    else show('astroReadingOverview','星盤可用，但詳細解讀模組尚未載入，請重新整理頁面。');
    const tbody=el('astroPlanets');tbody.replaceChildren();
    for(const p of data.positions){
      row(tbody,[bodyNames[p.name]||p.name,p.sign+' '+number(p.signDegree,2)+'°',
        number(p.longitudeDeg,4)+'°',number(p.latitudeDeg,4)+'°',
        number(p.speedDegPerDay,4),motion[p.motion]||p.motion]);
    }
    const box=el('astroAspects');box.replaceChildren();
    if(!data.aspects?.length){
      const p=document.createElement('p');p.textContent='目前無主要相位落入 ±2°；不代表市場會平靜。';box.appendChild(p);
    }else for(const a of data.aspects.slice(0,20)){
      const p=document.createElement('p');
      p.textContent=(bodyNames[a.bodyA]||a.bodyA)+' × '+(bodyNames[a.bodyB]||a.bodyB)+'｜'+
        (aspects[a.aspect]||a.aspect)+' '+number(a.actualAngleDeg,2)+'°，Orb誤差 '+
        number(a.orbErrorDeg,2)+'°｜'+(a.applying?'接近':'遠離');
      box.appendChild(p);
    }
  }
  function renderCalendar(){
    const box=el('astroCalendar');box.replaceChildren();
    if(!Array.isArray(state.calendar?.events)){
      box.textContent='日曆資料不可用，不以固定日期填充。';return;
    }
    const now=Date.now();
    const upcoming=state.calendar.events.filter(e=>Date.parse(e.exactUtc)>=now).slice(0,15);
    if(!upcoming.length){box.textContent='未找到未來90天的已計算相位事件。';return;}
    for(const a of upcoming){
      const p=document.createElement('p');
      p.textContent=when(a.exactUtc)+'｜'+(bodyNames[a.bodyA]||a.bodyA)+' × '+
        (bodyNames[a.bodyB]||a.bodyB)+'｜'+(aspects[a.aspect]||a.aspect)+' '+a.angleDeg+'°';
      box.appendChild(p);
    }
  }
  function renderBacktest(){
    const market=el('astroMarket').value;
    const h=Number(el('astroHorizon').value);
    const report=state.report;
    const marketName={NASDAQ:'Nasdaq Composite',SP500:'S&P 500',
      DAX:'DAX',FTSE100:'FTSE 100',CAC40:'CAC 40',TAIEX:'台灣加權指數'}[market]||market;
    const hasRelevantChart=state.ephemeris?.aspects?.some(a=>
      a.aspect==='conjunction' &&
      ((a.bodyA==='Mars'&&a.bodyB==='Jupiter')||(a.bodyA==='Jupiter'&&a.bodyB==='Mars')));
    show('astroEventMatch',hasRelevantChart
      ? '所選時間有火星與木星合相；下方統計仍不能直接預測這一天的股價。'
      : '所選時間沒有火星與木星合相。下方是獨立的歷史事件研究，不能當成這張星盤的市場判斷。');
    const clearNumbers=()=>{
      for(const id of ['metricN','metricWin','metricMean','metricBase','metricExcess','metricDd'])show(id,'—');
      for(const id of ['astroObservedN','astroObservedWin','astroObservedExcess'])show(id,'—');
      el('astroCohorts').replaceChildren();
    };
    const empty=(message)=>{
      show('astroMarketDirection','無法判定');
      show('astroCredibility','尚無證據');
      show('astroResearchVerdict',message);
      show('astroConclusionEvidence',message);
      show('astroEvidence',message);
    };
    clearNumbers();
    if(!report?.reports){
      show('astroBacktestMeta','歷史研究尚未取得真實行情資料，沒有可核實績效。');
      empty('尚未取得真實歷史行情與事件研究結果，不能給出勝率或推論市場方向。');
      return;
    }
    const result=report.reports[market];
    const asof=report.asOf||'—';
    const dates=result?.sampleStart&&result?.sampleEnd
      ? result.sampleStart+'～'+result.sampleEnd:'行情尚未取得';
    show('astroBacktestMeta',marketName+'｜行情期間：'+dates+
      '｜資料來源：'+(result?.source||'未取得')+
      '｜研究日期：'+asof);
    if(!result||result.status!=='ok'){
      empty(marketName+'：沒有可核實的價格研究結果（'+
        (result?.message||'資料來源目前無法取得')+'）。不能以占星解讀取代真實績效。');
      return;
    }
    const metric=result.horizons?.find(x=>x.horizonSessions===h);
    if(!metric || !Number.isInteger(metric.sampleSize) || metric.sampleSize<=0){
      empty(marketName+'：這個時間範圍沒有已完成、可驗證的事件樣本。');
      return;
    }
    const n=metric.sampleSize;
    const summary=metric.evidence||{label:'尚無正式評級',direction:'無法判定',
      reason:'舊版研究資料未附可信程度評級；需重新執行研究。'};
    const num=x=>typeof x==='number'&&Number.isFinite(x);
    const pfx=x=>num(x)?(x>0?'+':'')+(x*100).toFixed(2)+'%':'—';
    const ratio=x=>num(x)?(x*100).toFixed(1)+'%':'—';
    const age=Date.now()-Date.parse(report.generatedAt);
    const stale=!Number.isFinite(age)||age>14*86400000||age< -3600000;
    const label=stale?'資料過期':summary.label;
    const conclusion=stale?'無法判定':summary.direction||'無法判定';
    show('astroCredibility',label);
    show('astroMarketDirection',conclusion);
    show('astroObservedN',String(n)+' 次');
    show('astroObservedWin',ratio(metric.winRate));
    show('astroObservedExcess',pfx(metric.excessReturn));
    show('metricN',String(n));
    show('metricWin',ratio(metric.winRate));
    show('metricMean',pfx(metric.meanReturn));
    show('metricBase',pfx(metric.baselineReturn));
    show('metricExcess',pfx(metric.excessReturn));
    show('metricDd',pfx(metric.meanMaxDrawdown));
    const tendency=summary.historicalTendency||'未確認';
    const summaryText=marketName+'｜火星木星合相後 '+h+' 個交易日：'+n+
      ' 次有效樣本，上漲比例 '+ratio(metric.winRate)+
      '，平均報酬 '+pfx(metric.meanReturn)+
      '，同年份一般交易日平均 '+pfx(metric.baselineReturn)+
      '，差距 '+pfx(metric.excessReturn)+'。'+
      ' 這是「'+tendency+'」的歷史描述，不代表下次會重演。'+
      (stale?' 報告已超過14天未更新，暫不使用其結論。':' '+summary.reason);
    show('astroResearchVerdict',summaryText);
    show('astroConclusionEvidence',hasRelevantChart
      ? '這張星盤包含火星木星合相。'+summaryText
      : '目前所選星盤並非火星木星合相；下方 '+marketName+' 回測只供比較，不可當作本日預測。'+summaryText);
    const q=num(metric.fdrQValue)?metric.fdrQValue.toFixed(3):'尚無';
    const ci=Array.isArray(metric.excessConfidence95)?
      pfx(metric.excessConfidence95[0])+'～'+pfx(metric.excessConfidence95[1]):'尚無';
    const hold=metric.holdout;
    const holdInfo=hold?.holdoutCount?
      '；時間留出觀察：'+hold.holdoutCount+' 次（非預註冊樣本外驗證）':
      '；時間留出觀察：不足';
    show('astroEvidence','可信度：'+label+'；歷史事件 '+n+' 次、未完成／無行情事件 '+
      (metric.censoredEvents??0)+' 次；多重比較調整後 q='+q+
      '；超額報酬95%信賴區間 '+ci+holdInfo+
      '。無法直接證明因果與可交易優勢。');
    const wrap=el('astroCohorts'),table=document.createElement('table');
    const thead=document.createElement('thead'),heading=document.createElement('tr');
    ['事件時間','進場日期','出場日期','歷史報酬','期間最大跌幅'].forEach(x=>cell(heading,x,'th'));
    thead.appendChild(heading);table.appendChild(thead);
    const tbody=document.createElement('tbody');
    for(const e of metric.events||[]){
      row(tbody,[when(e.eventUtc),e.entryDate,e.exitDate,pfx(e.return),pfx(e.windowMaxDrawdown)]);
    }
    table.appendChild(tbody);wrap.appendChild(table);
  }
  async function start(){
    // The selected sky is computed live; stale daily JSON must never replace it.
    refreshLiveChart();
    const results=await Promise.allSettled([load('calendar.json'),load('report.json')]);
    state.calendar=results[0].status==='fulfilled'?results[0].value:null;
    state.report=results[1].status==='fulfilled'?results[1].value:null;
    renderCalendar();renderBacktest();
  }
  el('astroTimezone').addEventListener('change',()=>{if(state.liveMode)refreshLiveChart();else renderEphemeris();renderCalendar();renderBacktest();});
  el('astroMarket').addEventListener('change',renderBacktest);
  el('astroHorizon').addEventListener('change',renderBacktest);
  el('astroQueryDate').addEventListener('click',calculateSelected);
  el('astroQueryTime').addEventListener('change',calculateSelected);
  el('astroQueryNow').addEventListener('click',()=>{state.liveMode=true;refreshLiveChart();});
  setInterval(()=>{if(state.liveMode)refreshLiveChart();},60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&state.liveMode)refreshLiveChart();});
  window.addEventListener('focus',()=>{if(state.liveMode)refreshLiveChart();});
  start().catch(e=>show('astroEvidence','研究頁初始化失敗：'+e.message));
})();
