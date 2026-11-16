/* Live homepage financial astrology, geocentric tropical longitude, research-only. */
(function(){
  'use strict';
  const root=document.getElementById('financialAstrologyHome');
  if(!root)return;
  const state=root.querySelector('[data-astro-state]');
  const event=root.querySelector('[data-astro-event]');
  const evidence=root.querySelector('[data-astro-evidence]');
  const fmt=instant=>new Intl.DateTimeFormat('zh-TW',{timeZone:'Asia/Taipei',
    year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',
    hourCycle:'h23'}).format(instant);
  const zodiac=['牡羊','金牛','雙子','巨蟹','獅子','處女','天秤','天蠍','射手','摩羯','水瓶','雙魚'];
  const wrap=x=>((x%360)+360)%360;
  const separation=(a,b)=>Math.abs(wrap(a-b+180)-180);
  function currentPlanet(name,when){
    const A=window.Astronomy;
    if(!A)throw new Error('Astronomy Engine unavailable');
    // GeoVector + Ecliptic is geocentric; EclipticLongitude() would be heliocentric.
    const ect=A.Ecliptic(A.GeoVector(A.Body[name],when,true));
    if(!Number.isFinite(ect.elon))throw new Error('Invalid planet position: '+name);
    return {name,lon:wrap(ect.elon),sign:zodiac[Math.floor(wrap(ect.elon)/30)]};
  }
  function refresh(){
    if(!window.Astronomy){
      state.textContent='最新星盤暫不可用（天文運算未載入）';
      event.textContent='無法核實當前行星位置，不顯示舊日期星盤';
      return;
    }
    try{
      const now=new Date();
      const mars=currentPlanet('Mars',now),jupiter=currentPlanet('Jupiter',now);
      const distance=separation(mars.lon,jupiter.lon);
      state.textContent='最新星盤 '+fmt(now)+'（台灣時間）｜火星 '+mars.sign+'座、木星 '+jupiter.sign+'座';
      event.textContent=distance<=2
        ?'火星與木星目前接近合相（相距 '+distance.toFixed(2)+'°）'
        :'火星與木星目前不在合相範圍內';
    }catch(err){
      state.textContent='當前星盤計算失敗，請稍後重新整理';
      event.textContent='未使用過期資料代替當前星盤';
    }
  }
  // Historical market research is separate from today's astronomical sky.
  async function researchStatus(){
    try{
      const response=await fetch('./data/financial_astrology/report.json?cache='+Date.now(),{cache:'no-store'});
      if(!response.ok)throw new Error('research report unavailable');
      const report=await response.json();
      const result=report?.reports?.NASDAQ;
      const horizon=result?.horizons?.find(h=>h.horizonSessions===20);
      if(result?.status==='ok'&&horizon?.sampleSize>0&&Number.isFinite(horizon.winRate)){
        const label=horizon.evidence?.label||'尚未評級';
        evidence.textContent='歷史研究：Nasdaq 合相後20交易日｜有效樣本 '+horizon.sampleSize+
          ' 次、上漲率 '+(100*horizon.winRate).toFixed(1)+'%、可信度：'+label+
          '｜不能據此判斷今天股票多空';
      }else evidence.textContent='歷史報酬尚無有效樣本；不顯示推測勝率';
    }catch(_){evidence.textContent='歷史報酬尚未發布；可點選進入研究中心';}
  }
  refresh();
  setInterval(refresh,60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});
  window.addEventListener('focus',refresh);
  researchStatus();
  setInterval(researchStatus,15*60000);
})();
