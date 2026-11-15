/* Homepage-only, read-only research summary. Does not touch Risk Score. */
(function(){
  'use strict';
  const root=document.getElementById('financialAstrologyHome');
  if(!root)return;
  const state=root.querySelector('[data-astro-state]');
  const event=root.querySelector('[data-astro-event]');
  const evidence=root.querySelector('[data-astro-evidence]');
  const fmt=iso=>new Intl.DateTimeFormat('zh-TW',{timeZone:'Asia/Taipei',month:'2-digit',day:'2-digit',
    hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(new Date(iso));
  async function json(url){
    const response=await fetch(url+'?t='+Date.now(),{cache:'no-store'});
    if(!response.ok)throw new Error('HTTP '+response.status);
    return response.json();
  }
  Promise.allSettled([
    json('./data/financial_astrology/latest.json'),
    json('./data/financial_astrology/report.json')
  ]).then(([astro,stats])=>{
    if(astro.status==='fulfilled'&&Array.isArray(astro.value.positions)){
      const obj=astro.value;
      const mars=obj.positions.find(p=>p.name==='Mars');
      const jupiter=obj.positions.find(p=>p.name==='Jupiter');
      state.textContent='星曆：'+fmt(obj.generatedAt)+'｜火星 '+(mars?.sign||'—')+'、木星 '+(jupiter?.sign||'—');
      const active=obj.aspects?.find(x=>((x.bodyA==='Mars'&&x.bodyB==='Jupiter')||(x.bodyA==='Jupiter'&&x.bodyB==='Mars'))&&x.aspect==='conjunction');
      event.textContent=active?'火星－木星合相｜角距 '+active.actualAngleDeg.toFixed(2)+'°':'目前未落入火星－木星 2° 合相窗口';
    }else{
      state.textContent='星曆尚未發布，請查看研究工作流';
      event.textContent='天文事件資料待更新';
    }
    const result=stats.status==='fulfilled'?stats.value?.reports?.NASDAQ:null;
    const horizon=result?.horizons?.find(h=>h.horizonSessions===20);
    if(result?.status==='ok' && horizon?.sampleSize>0){
      evidence.textContent='Nasdaq 合相後20日：'+horizon.sampleSize+'次有效樣本｜上漲率 '+(100*horizon.winRate).toFixed(1)+'%（探索性統計，非訊號）';
    }else evidence.textContent='Nasdaq 20日績效尚未取得有效歷史樣本；不顯示推測勝率';
  }).catch(()=>{state.textContent='星曆資料暫不可用';event.textContent='待更新';});
})();
