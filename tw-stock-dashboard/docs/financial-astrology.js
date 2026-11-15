/* Financial Astrology Research Center V1.0: read-only, no trading signals. */
(function(){
  'use strict';
  const el=id=>document.getElementById(id);
  const state={ephemeris:null,calendar:null,report:null};
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
  function renderEphemeris(){
    const data=state.ephemeris;
    if(!data?.positions?.length){
      show('astroSummary','天文資料尚未發布或暫時無法讀取。');
      show('astroUpdated','星曆待更新');
      el('astroPlanets').replaceChildren();
      show('astroAspects','無法讀取星象相位');
      return;
    }
    const stale=(Date.now()-Date.parse(data.generatedAt))>48*3600000;
    show('astroUpdated',when(data.generatedAt)+(stale?'（逾48小時，非即時）':''));
    show('astroSummary','月相角 '+number(data.moon?.phaseAngleDeg)+'°（'+(data.moon?.phaseLabel||'—')+
      '）；當前符合 2° Orb 的主要相位 '+(data.aspects?.length||0)+' 組。'+
      '此處僅為可重現天文資料，不提供已驗證買賣建議。');
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
    for(const id of ['metricN','metricWin','metricMean','metricBase','metricExcess','metricDd'])show(id,'—');
    el('astroCohorts').replaceChildren();
    const report=state.report;
    if(!report?.reports){
      show('astroBacktestMeta','歷史研究 JSON 尚未產生。');
      show('astroEvidence','沒有真實行情與事件配對結果，因此不顯示任何勝率或報酬。');return;
    }
    const result=report.reports[market];
    show('astroBacktestMeta',(result?.marketName||market)+'｜資料日期：'+(result?.sampleStart||'—')+'～'+
      (result?.sampleEnd||'—')+'｜來源：'+(result?.source||'未取得')+'｜研究生成時間 '+when(report.generatedAt));
    if(!result || result.status!=='ok'){
      show('astroEvidence','資料尚不可用：'+(result?.message||'該指數尚無經確認的歷史行情。')+
        ' 不以占星解讀代替回測。');return;
    }
    const r=result.horizons?.find(x=>x.horizonSessions===h);
    if(!r || r.sampleSize<1){
      show('astroEvidence','此期間沒有已完成的有效樣本（資料不足或研究期限尚未結束）。');return;
    }
    show('metricN',String(r.sampleSize));
    show('metricWin',percent(r.winRate,1));
    show('metricMean',percent(r.meanReturn));
    show('metricBase',percent(r.baselineReturn));
    show('metricExcess',percent(r.excessReturn));
    show('metricDd',percent(r.meanMaxDrawdown));
    const warn=r.sampleSize<30?'事件數量少於30，統計可能非常不穩定。':'此為探索性統計，不能推定因果。';
    const ci=Array.isArray(r.confidence95)?'；bootstrap 95% 區間 '+percent(r.confidence95[0])+
      '～'+percent(r.confidence95[1]):'；信賴區間尚不足以估計';
    const p=r.pValue===null?'未估計':number(r.pValue,3);
    const q=r.fdrQValue===null?'未估計':number(r.fdrQValue,3);
    show('astroEvidence',warn+' '+r.censoredEvents+' 個樣本因未到期或無價格而排除。'+
      '置換檢驗 p='+p+'，FDR q='+q+ci+'。'+
      (r.holdout?' 已顯示依時間切割的觀察性留出樣本。':' 尚無充足樣本外驗證。')+
      ' 不代表行星影響股價，也不建議據此交易。');
    const wrap=el('astroCohorts'),table=document.createElement('table');
    const thead=document.createElement('thead');const heading=document.createElement('tr');
    ['精確合相 UTC','入場交易日','出場交易日','期間報酬','期間最大回撤'].forEach(x=>cell(heading,x,'th'));
    thead.appendChild(heading);table.appendChild(thead);
    const tbody=document.createElement('tbody');
    for(const s of (r.events||[])){
      row(tbody,[when(s.eventUtc),s.entryDate,s.exitDate,percent(s.return),percent(s.windowMaxDrawdown)]);
    }
    table.appendChild(tbody);wrap.appendChild(table);
  }
  async function start(){
    const results=await Promise.allSettled([load('latest.json'),load('calendar.json'),load('report.json')]);
    const vals=results.map(x=>x.status==='fulfilled'?x.value:null);
    [state.ephemeris,state.calendar,state.report]=vals;
    renderEphemeris();renderCalendar();renderBacktest();
    if(results.every(x=>x.status==='rejected'))show('astroEvidence','所有資料來源暫時不可用，請檢查 GitHub Actions。');
  }
  el('astroTimezone').addEventListener('change',()=>{renderEphemeris();renderCalendar();renderBacktest();});
  el('astroMarket').addEventListener('change',renderBacktest);
  el('astroHorizon').addEventListener('change',renderBacktest);
  start().catch(e=>show('astroEvidence','研究頁初始化失敗：'+e.message));
})();
