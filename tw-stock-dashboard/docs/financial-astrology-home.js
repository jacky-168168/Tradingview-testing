(()=>{'use strict';
const el=document.getElementById('financialAstroHome'),summary=document.getElementById('financialAstroHomeSummary');
if(!el||!summary)return;
fetch('./data/financial_astrology/latest.json',{cache:'no-store'}).then(res=>{if(!res.ok)throw Error('missing');return res.json();})
.then(data=>{
 if(data.schema!==1||!data.snapshot||!Array.isArray(data.events))throw Error('invalid');
 const age=Date.now()-Date.parse(data.generatedAt);
 if(age<0||age>36*3600000){summary.textContent='星曆資料已逾時，僅提供歷史研究入口；不顯示即時市場訊號。';return;}
 const moon=data.snapshot.moonPhase?.name||'未知';
 const next=data.events.find(e=>Date.parse(e.utc)>=Date.now());
 const kind=next?(next.kind==='aspect'?next.first+' '+next.name+' '+next.second:next.kind==='station'?next.body+' 逆行／順行轉折':next.name):'近期無事件';
 summary.textContent='月相：'+moon+'｜下一事件：'+kind+'｜星曆更新：'+new Intl.DateTimeFormat('zh-TW',{timeZone:'Asia/Taipei',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(data.generatedAt));
}).catch(()=>{summary.textContent='星曆資料尚未發布；可進入研究頁檢視方法與資料狀態。';});
})();