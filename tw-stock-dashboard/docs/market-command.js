/* Market Command Center: transparent on-screen guidance; NEVER overrides live A/D/F/F2/G selectors.
 * The previous official cash close + verified same-month TX night provides a DISPLAY-ONLY
 * reference score until the new official daily score is published. This does not change any strategy gate.
 */
(function(scope){
"use strict";
const $=id=>typeof document==="undefined"?null:document.getElementById(id);
const twDay=(now=new Date())=>new Intl.DateTimeFormat("sv-SE",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).format(now);
const twWeekday=(now=new Date())=>new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Taipei",weekday:"short"}).format(now);
function fallback(r){
 if(!r||r.score===null||r.score===undefined||!Number.isFinite(Number(r.score)))
   return {level:"UNKNOWN",headline:"⚪ 市場資料尚未核對",action:"等待有效的官方收盤分數，暫不提供進場評估。",flags:[]};
 const score=Number(r.score),top=String(r.topState||""),bottom=String(r.bottomState||"");
 if(top==="🔴 Strong Top Reversal"||top==="🟠 Top Reversal Attempt")
   return {level:"STOP",headline:"⛔ 暫緩新倉｜頂部警戒",action:"頂部反轉監測出現轉弱警示；避免以高分作為追價理由。",flags:[]};
 if(top==="🔴 Extreme Overbought")
   return {level:"CAUTION",headline:"🟠 過熱，避免追高",action:"等待短線波動收斂，再確認個股進場價及停損。",flags:[]};
 if(score<60&&bottom==="🟢 Strong Bottom Reversal")
   return {level:"REVERSAL",headline:"🟣 超跌反轉候選",action:"須搭配個股 Bottom 訊號，不能把低分反轉直接當成一般買點。",flags:[]};
 if(score<40&&Number(r.oversoldScore||0)>=3)
   return {level:"REVERSAL",headline:"🟣 超跌觀察，尚未確認",action:"低分可能繼續下跌；先等待反轉確認。",flags:[]};
 if(score<50)return {level:"STOP",headline:"🔴 暫不建議一般新倉",action:"大盤未達60分進場基準；等待趨勢改善。",flags:[]};
 if(score<60)return {level:"WAIT",headline:"🟡 尚未達進場門檻",action:"觀察市場廣度與個股訊號，暫緩一般趨勢買進。",flags:[]};
 const overheat=Number(r.distMA20||0)>=6&&Number(r.ret5||0)>=8;
 const near=r.distHigh120Pct!=null&&Number(r.distHigh120Pct)>=-2&&Number(r.distHigh120Pct)<=0&&r.mode==="TOP";
 if(overheat||near)return {level:"CAUTION",headline:"🟠 趨勢合格，避免追高",action:"短線過熱或接近前高，等待可控的個股買點。",flags:[]};
 return {level:"READY",headline:score>=80?"🟢 強勢，可評估新倉":"🟢 趨勢達標，可評估新倉",
         action:"仍需個股 G／D、Bottom 訊號及停損配置，分數達標並非必須買進。",flags:[]};
}
function evaluate(r,diag,now=new Date()){
 let decision=diag&&diag.asOf===r?.date&&diag.riskScore===r?.score?diag.decision:fallback(r);
 const marketDate=String(r?.date||""),t=taipeiParts(now),today=t.date,weekend=["Sat","Sun"].includes(twWeekday(now));
 const diff=marketDate?Math.round((Date.parse(today+"T12:00:00+08:00")-Date.parse(marketDate+"T12:00:00+08:00"))/86400000):999;
 // At/after 14:30 on a weekday, the previous session is NOT today's official close.
 // Conservative for exchange holidays: show historical score only, never invent a current one.
 const closePending=!weekend&&t.minute>=14*60+30&&marketDate!==today;
 const stale=diff>8||diff<0||!marketDate||closePending;
 if(stale)decision={level:"UNKNOWN",headline:"⚠ 今日大盤資料尚未更新",action:"目前只有 "+(marketDate||"未知")+" 的歷史分數；等待證交所官方資料核對後重算，暫不據此評估新倉。",flags:[]};
 return {decision,diag:!stale&&diag?.asOf===marketDate?diag:null,marketDate,today,stale,weekend,closePending};
}

function taipeiParts(now=new Date()){
 const p=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(now);
 const v=Object.fromEntries(p.map(x=>[x.type,x.value]));
 return {date:v.year+"-"+v.month+"-"+v.day,minute:Number(v.hour)*60+Number(v.minute)};
}
// A risk scenario from VERIFIED COMPLETED NIGHT session; not live 08:58 TX
// and never an overwrite of original TWSE Risk Score or official F/F2 gates.
function txScoreDelta(pct){
 if(!Number.isFinite(Number(pct)))return null;
 const n=Number(pct);
 return n<=-2?-25:n<=-1?-15:n<=-.5?-8:n>=2?10:n>=1?7:n>=.5?4:0;
}
// Derive an independent, verified preview from published same-contract TX day/night closes.
// This removes the homepage dependency on a secondary (possibly hidden) preview component.
function verifiedNightPreview(r,f,now=new Date()){
 const d=taipeiParts(now),day=f?.day||{},night=f?.night||{},cashDate=String(r?.date||""),
       compact=cashDate.replace(/-/g,""),target=String(night.reportQueryDate||"");
 if(!cashDate||r?.score==null||!Number.isFinite(Number(r.score))||Number(r.score)<0||Number(r.score)>100||!Number.isFinite(Number(day.close))||
    !Number.isFinite(Number(night.close))||Number(day.close)<=0||Number(night.close)<=0||
    f?.quality!=="paired-day-night"||f.asOfDate!==cashDate||day.date!==compact||night.date!==compact||
    day.contract!==f.contract||night.contract!==f.contract||!/^20\d{4}$/.test(String(f.contract||""))||
    !/^20\d{2}-\d{2}-\d{2}$/.test(target)||target<=cashDate||target<d.date)return null;
 const targetDay=new Date(target+"T12:00:00+08:00"),weekday=twWeekday(targetDay);
 const gap=(targetDay-Date.parse(cashDate+"T12:00:00+08:00"))/86400000;
 if(!Number.isFinite(gap)||gap>4||["Sat","Sun"].includes(weekday))return null; // 長休市不得將舊夜盤當作當前開市日
 const pct=100*(Number(night.close)/Number(day.close)-1),reported=Number(f.nightVsDayPct);
 if(!Number.isFinite(pct)||Math.abs(pct)>12||!Number.isFinite(reported)||Math.abs(pct-reported)>.08)return null;
 const adjustment=txScoreDelta(pct),base=Number(r.score),score=Math.max(0,Math.min(100,base+adjustment));
 return {valid:true,sourceDate:cashDate,nextDate:target,base,pct,adjustment,score};
}
function marketPremarket(r,x,now=new Date()){
 if(r?.score==null||x?.valid!==true)return null;
 const t=taipeiParts(now),base=Number(r.score),pct=Number(x.pct),
  adjust=Number(x.adjustment),score=Number(x.score);
 if(![base,pct,adjust,score].every(Number.isFinite))return null;
 // Completed Friday night belongs to the NEXT official session (usually Monday).
 // Display a conditional risk preview on Sat/Sun, never as Saturday cash trading.
 const weekendLead=["Sat","Sun"].includes(twWeekday(now))&&t.date>x.sourceDate&&t.date<x.nextDate;
 const targetMorning=x.nextDate===t.date&&t.minute>=510&&t.minute<540;
 if((!weekendLead&&!targetMorning)||x.sourceDate!==r.date||Number(x.base)!==base)return null;
 if(score!==Math.max(0,Math.min(100,base+adjust))||Math.abs(pct)>12)return null;
 let level="WAIT",headline="🟡 盤前觀察｜等09:00現貨確認",
     action="TX 完成夜盤僅作盤前風險參考；不代表即時 08:58 成交價，更不能取代開盤後上漲家數。";
 if(pct<=-1||score<50){
  level="STOP";headline="⛔ 盤前暫緩新倉｜台指期偏弱";
  action="TX 完成夜盤相對同月日盤 "+pct.toFixed(2)+"%；盤前風險上升，09:00 開盤後先確認實際現貨狀況。";
 }else if(pct<=-.5||score<60){
  headline="🟡 夜盤轉弱｜先觀察";
  action="雖然盤前分數已調整，但現貨尚未開盤，先確認個股是否同步轉弱。";
 }else if(pct>=.5){
  headline="🟡 夜盤偏多｜等09:00確認";
  action="TX 夜盤偏多，但即使暫估超過60分，也不自動升級成正式買進許可。";
 }
 if(weekendLead){
  if(level==="STOP")headline="⛔ 下個交易日風險升高｜已完成夜盤重挫";
  else headline="🟡 下個交易日盤前觀察｜夜盤已完成";
  action="期貨夜盤已完成，"+x.nextDate+" 才是下一現貨交易日；此為提前風險試算，週末沒有現貨交易。"+(pct<=-1?" 夜盤跌幅達 "+Math.abs(pct).toFixed(2)+"%，暫緩一般新倉並控管曝險。":" 下次開盤仍要確認現貨走勢。");
 }
 return {active:true,level,headline,action,score,base,pct,adjustment:adjust,
  deltaLabel:(adjust>0?"+":"")+adjust,referenceDate:r.date,targetDate:x.nextDate,weekendPreview:weekendLead,
  source:weekendLead?"已完成TX夜盤，週末顯示下個交易日預覽":"已完成TX夜盤，非08:58即時報價"};
}
// The published cash Risk Score belongs to its dated close, not the next cash session.
// Night risk and verified same-day trade breadth are advisory only: no fake live Risk Score.
function overnightRisk(f,r,now=new Date()){
 const t=taipeiParts(now),day=f?.day||{},night=f?.night||{},date=String(f?.asOfDate||""),compact=date.replace(/-/g,"");
 if(!r||r.date!==date||date>=t.date||f?.quality!=="paired-day-night"||night.reportQueryDate!==t.date||
    day.date!==compact||night.date!==compact||day.contract!==f.contract||night.contract!==f.contract)return null;
 const gap=(Date.parse(t.date+"T12:00:00+08:00")-Date.parse(date+"T12:00:00+08:00"))/86400000;
 if(!Number.isFinite(gap)||gap>4||gap<1)return null; // 10/22 夜盤不可延續到 10/27 充作昨夜
 const d=Number(day.close),n=Number(night.close),quoted=Number(f.nightVsDayPct);
 if(!Number.isFinite(d)||!Number.isFinite(n)||d<=0||n<=0||!Number.isFinite(quoted))return null;
 const pct=(n/d-1)*100;if(Math.abs(pct)>12||Math.abs(pct-quoted)>.08)return null;
 return {pct,date,target:t.date,source:"期交所已完成同月份夜盤，非目前即時期貨"};
}
function tradedBreadth(g,now=new Date()){
 const age=(now-Date.parse(g?.publishedAt||""))/60000;
 if(g?.asOfDate!==taipeiParts(now).date||g?.quality!=="intraday-provisional-allmarket"||
    g?.marketBreadth?.quality!=="verified-trade-only"||!Number.isFinite(age)||age< -5||age>75)return null;
 const coverage=g.coverage||{},b=g.marketBreadth||{},l=b.exchange?.["上市"]||{},o=b.exchange?.["上櫃"]||{},t=b.total||{};
 const ns=[coverage.valid,coverage.total,coverage.exchange?.["上市"]?.valid,coverage.exchange?.["上市"]?.total,
           coverage.exchange?.["上櫃"]?.valid,coverage.exchange?.["上櫃"]?.total,t.up,t.down,t.flat,t.sample,l.sample,o.sample].map(Number);
 if(ns.some(x=>!Number.isFinite(x)||x<0)||coverage.total<1800||coverage.valid/coverage.total<.65||
    coverage.exchange["上市"].valid/coverage.exchange["上市"].total<.60||
    coverage.exchange["上櫃"].valid/coverage.exchange["上櫃"].total<.60||
    t.sample<600||l.sample<300||o.sample<100||t.up+t.down+t.flat!==t.sample||l.sample+o.sample!==t.sample)return null;
 return {pct:t.up/t.sample*100,sample:t.sample,up:t.up,down:t.down,flat:t.flat,at:g.publishedAt};
}
function verifiedTXIntraday(q,now=new Date()){
 const t=taipeiParts(now),ms=Date.parse(q?.quoteTime||""),
       age=(now.getTime()-ms)/60000,minute=q?.quoteTime? taipeiParts(new Date(ms)).minute:-1,
       last=Number(q?.last),ref=Number(q?.reference);
 if(q?.status!=="ok"||q?.quality!=="dated-third-party-snapshot"||q?.asOfDate!==t.date||
    q?.symbol!=="WTX&"||!Number.isFinite(ms)||!Number.isFinite(age)||age<0||age>25||
    minute<525||minute>=825||!Number.isFinite(last)||!Number.isFinite(ref)||
    last<10000||last>100000||ref<10000||ref>100000)return null;
 const points=last-ref,pct=100*points/ref;
 if(!Number.isFinite(Number(q.changePct))||Math.abs(pct-Number(q.changePct))>0.06||
    !Number.isFinite(Number(q.changePoints))||Math.abs(points-Number(q.changePoints))>1)return null;
 return {date:t.date,time:q.quoteTime,last,reference:ref,points,pct,source:q.source||"第三方期貨報價"};
}
function postOpenState(r,now=new Date(),night=null,breadth=null,live=null){
 const t=taipeiParts(now),weekday=twWeekday(now);
 if(!r?.date||r.date>=t.date||t.minute<540||t.minute>=1050||["Sat","Sun"].includes(weekday)||
    (t.minute>=870&&!night))return null;
 const flags=[],weakNight=night&&night.pct<=-1;
 const base=Number(r.score),delta=night?txScoreDelta(night.pct):null;
 const baseline=night&&r.score!=null&&Number.isFinite(base)&&base>=0&&base<=100&&delta!=null?
  {score:Math.max(0,Math.min(100,base+delta)),base,delta,pct:night.pct,date:r.date,target:night.target}:null;
 let level="WAIT",headline="🟡 現貨已開盤｜等待今日盤勢確認",action="今日完整 Risk Score 尚未形成；前次收盤分數不能自動授權新倉。";
 if(night)flags.push({code:"LAST_NIGHT_TX",title:"昨夜台指 "+(night.pct>=0?"+":"")+night.pct.toFixed(2)+"%",severity:night.pct<=-.5?"caution":"info",detail:"已完成夜盤對同月日盤，非現貨即時報價。"});
 if(breadth){
  flags.push({code:"TODAY_TRADE_BREADTH",title:"今日上漲成交股 "+breadth.pct.toFixed(1)+"%",severity:breadth.pct<45?"caution":"info",detail:"上市櫃已成交 "+breadth.sample+" 檔（不含未成交與委託價）｜更新 "+breadth.at});
  if(breadth.pct<35){level="STOP";headline="⛔ 今日盤中跌多漲少｜暫緩新倉";action="今日實際成交股票僅 "+breadth.pct.toFixed(1)+"% 上漲，市場廣度弱；不是昨日 Risk Score 所能反映。";}
  else if(breadth.pct<45){headline="🟠 今日盤中廣度偏弱｜先觀察";action="今日實際成交股票上漲比率 "+breadth.pct.toFixed(1)+"%；暫緩積極新倉。";}
  else{headline=weakNight?"🟡 夜盤曾重挫｜盤中修復待確認":"🟡 今日廣度 "+breadth.pct.toFixed(1)+"%｜尚無正式分數";action="已取得今天的盤中成交廣度，但不能把它換算成未回測的正式 Risk Score，仍需後續驗證。";}
 }else if(weakNight){level="STOP";headline="⛔ 昨夜台指期重挫｜今日現貨未確認";action="台指期同月夜盤下跌 "+Math.abs(night.pct).toFixed(2)+"%。今天尚未取得合格的現貨廣度，不能用昨天的收盤分數直接放行新倉。";}
 else if(night?.pct<=-.5){headline="🟠 夜盤偏弱｜今日現貨尚待確認";action="夜盤偏弱，仍缺今天的可靠市場廣度，不宜以昨日分數追價。";}
 if(live){
  flags.unshift({code:"TODAY_TX_VERIFIED",title:"今日台指期 "+(live.pct>=0?"+":"")+live.pct.toFixed(2)+"%",severity:live.pct<=-.5?"caution":"info",
   detail:"當日近月 TX 已成交 "+live.last.toLocaleString("en-US")+" 點，參考價 "+live.reference.toLocaleString("en-US")+"，成交 "+live.time+"；不是昨夜報價，不能直接換算現貨 Risk Score。"});
  if(live.pct<=-1){
   level="STOP";headline="⛔ 今日 TX 跌 "+Math.abs(live.pct).toFixed(2)+"%｜風控待確認";
   action="台指期當日已成交且相對參考價下跌；先控管曝險，等待今日現貨市場廣度及風險模型更新。";
  }else if(!breadth){
   headline="🟡 今日 TX "+(live.pct>=0?"+":"")+live.pct.toFixed(2)+"%｜現貨待確認";
   action="已驗證今天 08:45 後的 TX 成交價，但還沒有合格的當日市場廣度；不得把舊日夜盤跌幅或舊 Risk Score 當作今日分數。";
  }
 }
 if(!breadth)flags.push({code:"PENDING_LIVE_BREADTH",title:"今日上漲家數待核對",severity:"caution",detail:"不得把昨日市場廣度當成今天。"});
 if(baseline){
  flags.unshift({code:"TX_BASELINE",title:"盤前基準 "+baseline.score+"/100",severity:baseline.score<60?"caution":"info",
   detail:"昨收正式 "+baseline.base+" 分 "+(baseline.delta>=0?"+":"")+baseline.delta+" 分（前夜 TX "+baseline.pct.toFixed(2)+"%）；規則尚未獨立回測。"});
  if(baseline.score<60&&level==="WAIT"){level="WAIT";headline="🟠 盤前基準 "+baseline.score+" 分｜暫緩積極新倉";
   action="昨日正式 "+baseline.base+" 分，台指期夜盤 "+baseline.pct.toFixed(2)+"% 調整 "+baseline.delta+" 分；今天以 "+baseline.score+" 分作盤前基準，須再核對現貨，不是正式盤中 Risk Score。";}
 }
 return {level,headline,action,flags,night,breadth,baseline,txLive:live};
}

function txt(id,value){const el=$(id);if(el)el.textContent=value}
function strength(score){
 if(!Number.isFinite(score))return "尚無風險分數";
 if(score>=80)return "強勢多頭";
 if(score>=60)return "趨勢達標";
 if(score>=50)return "中性觀察";
 return "弱勢警戒";
}
function scoreBand(score){
 const n=Number(score);
 if(score==null||!Number.isFinite(n)||n<0||n>100)return null;
 if(n>=75)return {band:"75～100",label:"強勢偏多",title:"擇優評估，仍不追高",body:"市場條件較有利；仍須確認 G／D 或 Bottom 買點、停損與部位，不能只看高分就滿倉。",tone:"ready"};
 if(n>=60)return {band:"60～74",label:"偏多觀察",title:"有條件評估小部位",body:"趨勢相對有利，但只在個股訊號成立、量價與風險可控時才考慮試單；不代表必須買進。",tone:"ready"};
 if(n>=45)return {band:"45～59",label:"中性觀望",title:"觀望為主，暫緩積極新倉",body:"尚未達一般趨勢進場參考門檻 60 分；優先等待大盤與個股止跌／轉強，不急於追價。",tone:"wait"};
 return n>=25?{band:"25～44",label:"偏空觀察",title:"避免一般新倉，先控管曝險",body:"市場偏弱，觀察能否持續止跌，不建議因反彈就積極加碼。",tone:"stop"}:{band:"0～24",label:"極度偏空",title:"先控管曝險，超跌不代表底部",body:"極度偏空是市場環境分類，不等於恐慌指標；若屬超跌觀察，仍須獨立確認 Bottom。",tone:"stop"};
}
function scoreGuidance(score,{reference=false,level="WAIT",historical=false}={}){
 const band=scoreBand(score);
 if(!band)return {title:"今日操作：等待有效資料",text:"尚未取得可以對應今天的完整分數與資料，暫不以昨日分數判定進場。",tone:"neutral",band:null};
 if(historical)return {title:"歷史 "+Number(score)+" 分｜非今日進場許可",text:band.label+"。這是已完成交易日的分數，只說明當時市場環境；今天須再確認台指期與現貨狀況。",tone:"neutral",band};
 if(level==="STOP")return {title:"今日操作：暫緩新倉（"+Number(score)+" 分）",text:"目前有獨立重大風險警示，即使分數落在偏多區也應先等風險解除。"+(reference?"此分數是昨收＋已完成夜盤的盤前基準，尚未經獨立績效回測；不能直接當買進訊號。":band.body),tone:"stop",band};
 if(level==="CAUTION")return {title:"今日操作：避免追高（"+Number(score)+" 分）",text:"有短線過熱或其他風險，優先等待價格與停損條件改善。"+(reference?"盤前基準未經獨立績效回測。":""),tone:"wait",band};
 if(level==="REVERSAL")return {title:"今日操作：僅觀察反轉訊號（"+Number(score)+" 分）",text:"低分反轉不等於可以直接進場，必須另外確認 Bottom 及個股風險。",tone:"wait",band};
 if(reference&&Number(score)>=60)return {title:"今日操作：先確認現貨（"+Number(score)+" 分）",text:"盤前基準位於「"+band.label+"」區，但 TX 夜盤加減分未經獨立回測；需等今天現貨與個股買點確認，不能直接放行新倉。",tone:"wait",band};
 return {title:"今日操作："+band.title+"（"+Number(score)+" 分）",text:band.body+(reference?" 本數字僅作昨收＋已完成 TX 夜盤參考基準，不是正式盤中 Risk Score。":""),tone:band.tone,band};
}
function drawScoreGuide({officialScore,officialDate,currentScore,reference,level,date}){
 const container=$("commandTradeGuide"),comparison=$("commandGuideCompare");
 if(!container)return;
 const valid=officialScore!=null&&Number.isFinite(Number(officialScore)),current=currentScore!=null&&Number.isFinite(Number(currentScore));
 const guide=scoreGuidance(current?Number(currentScore):null,{reference,level,historical:!reference&&date!==officialDate});
 container.dataset.tone=guide.tone;
 txt("commandGuideTitle",guide.title);txt("commandGuideText",guide.text);
 txt("commandGuideSource",reference?"下次交易日盤前基準｜非正式分數":current&&date===officialDate?"今日正式收盤 Risk Score":"歷史參考／今日未確認");
 if(comparison){
  comparison.replaceChildren();
  const add=(label,value,meaning)=>{
   const col=document.createElement("div"),cap=document.createElement("small"),strong=document.createElement("strong"),detail=document.createElement("span");
   cap.textContent=label;strong.textContent=value;detail.textContent=meaning;
   col.appendChild(cap);col.appendChild(strong);col.appendChild(detail);comparison.appendChild(col);
  };
  if(reference&&valid&&current){
   add("前次正式｜"+officialDate,Number(officialScore)+"/100",scoreBand(Number(officialScore))?.label||"歷史參考");
   add("下次交易日盤前基準｜"+date,Number(currentScore)+"/100",(guide.band?.label||"資料不足")+"｜"+(level==="STOP"?"暫緩新倉":"等待現貨確認"));
   comparison.hidden=false;
  }else comparison.hidden=true;
 }
}
function draw(data,diag){
 const panel=$("marketCommand");if(!panel)return;
 const r=data?.risk||{},now=new Date(),val=Number(r.score),x=evaluate(r,diag,now),verified=verifiedNightPreview(r,currentFutures,now),pre=marketPremarket(r,verified,now)||(currentFutures?null:marketPremarket(r,currentPremarket,now)),txToday=verifiedTXIntraday(currentTXLive,now),night=txToday?null:overnightRisk(currentFutures,r,now),breadthLive=tradedBreadth(currentIntraday,now),post=pre?null:postOpenState(r,now,night,breadthLive,txToday),d=pre?{...x.decision,...pre}:post?{...x.decision,...post}:x.decision,info=x.diag?.marketHealth||{};
 const weekendNeedsNight=!pre&&x.weekend&&r?.date&&x.today>r.date;
 panel.dataset.level=d.level;panel.dataset.premarket=pre?"true":"false";panel.className="market-command market-compact cmd-"+d.level.toLowerCase();
 txt("commandStatus",d.headline);
 txt("commandAction",d.action);
 txt("commandScore",pre?String(pre.score):post?.baseline?String(post.baseline.score):weekendNeedsNight||post||x.stale?"—":Number.isFinite(val)&&r.score!=null?String(val):"—");
 txt("commandScoreDescription",pre?"下次交易日盤前基準｜未回測":weekendNeedsNight?"週末盤前資料待核對，正式分數僅供歷史參考":post?.baseline?"昨收＋夜盤｜今日基準（未回測）":post?.txLive?"當日台指報價已驗證｜正式現貨分數待確認":post?"今日 Risk Score 尚未建立":x.stale?"正式分數待更新":strength(val)+"｜盤後正式分數");
 txt("commandCashReference",pre?"昨收正式 "+pre.base+"/100（"+pre.referenceDate+"）｜台指期調整 "+pre.deltaLabel+" 分":post?.baseline?"昨收正式 "+post.baseline.base+"/100（"+post.baseline.date+"） "+(post.baseline.delta>=0?"+":"")+post.baseline.delta+" 分（已完成 TX 夜盤 "+post.baseline.pct.toFixed(2)+"%）＝今日盤前基準 "+post.baseline.score+"/100":x.stale?"今日正式 Risk Score 尚未建立；"+(r.date||"未知")+" 的 "+val+" 分僅供歷史參考":post?.txLive?"今日 TX "+post.txLive.last.toLocaleString("en-US")+" 點（"+(post.txLive.pct>=0?"+":"")+post.txLive.pct.toFixed(2)+"%）｜歷史現貨 Risk Score "+val+" 分（"+r.date+"）不代表今日":post?"昨收歷史 Risk Score "+val+"/100（"+(r.date||"未知")+"）｜非今日盤中":weekendNeedsNight?"已核對的正式收盤 "+r.score+"/100；週末下個交易日盤前資料待確認，不以舊分數取代":"");
 const ref=$("commandCashReference");if(ref)ref.hidden=!pre&&!post&&!x.stale&&!weekendNeedsNight;
 const fill=$("commandScoreFill");if(fill)fill.style.width=(pre?pre.score:post?.baseline?post.baseline.score:weekendNeedsNight||post||x.stale?0:r.score==null||!Number.isFinite(val)?0:Math.max(0,Math.min(100,val)))+"%";
 const date=x.marketDate||"未知";
 txt("commandAsOf",pre?"下次交易日 "+pre.targetDate+"｜現貨最後收盤 "+pre.referenceDate:post?"今日 "+x.today+" 盤中｜昨收資料 "+date:x.stale?"⚠ 最新正式資料 "+date+"｜今日盤後資料待同步":"最新已收盤 "+date+(x.weekend?"｜今日休市":"｜非即時交易訊號"));
 let timeNote=pre?"僅TX已完成夜盤，非08:58即時期貨":post?.baseline?"昨日收盤＋昨夜 TX｜今日參考基準":post?.txLive?"今日台指期成交已核對｜現貨分數待確認":post?"今日盤中風險核對｜非正式分數":x.weekend?"休市日：下個交易日的盤前參考":x.today===date?"已完成的現貨市場評估":"最近資料日：非即時盤中訊號";
 if(x.stale&&!post)timeNote="資料延遲／官方資料待同步｜暫停進場判斷";
 txt("commandTiming",timeNote);
 const breadth=Number(r.breadth);
 txt("commandBreadth",post?(post.breadth?post.breadth.pct.toFixed(1)+"%":"—"):x.stale?"—":r.breadth==null||!Number.isFinite(breadth)?"—":breadth.toFixed(1)+"%");
 txt("commandBreadthSub",post?(post.breadth?"今日實際成交 "+post.breadth.sample+" 檔；盤中暫估":"昨收 "+date+" 為 "+(Number.isFinite(breadth)?breadth.toFixed(1)+"%":"—")+"，今天尚未取得"):x.stale?"今日尚未取得":info.breadth5Pct!=null?"近5日平均 "+Number(info.breadth5Pct).toFixed(1)+"%":"TWSE 上漲家數比例");
 txt("commandScoreChange",info.riskScore5SessionChange==null?"—":(Number(info.riskScore5SessionChange)>0?"+":"")+Number(info.riskScore5SessionChange).toFixed(0)+" 分");
 txt("commandScoreChangeSub",post?"截至 "+date+" 的歷史變化":info.riskScore3MA!=null?"3日平滑分數 "+Number(info.riskScore3MA).toFixed(1):"5交易日分數變化");
 txt("commandVol",info.realizedVol20AnnualPct==null?"—":Number(info.realizedVol20AnnualPct).toFixed(1)+"%");
 txt("commandVolSub",info.volatilityHistoryPercentile!=null?"波動歷史百分位 "+Number(info.volatilityHistoryPercentile).toFixed(0):"20日年化波動");
 const dist=info.distancePrior120HighPct;
 txt("commandHigh",dist==null?"—":(Number(dist)>0?"+":"")+Number(dist).toFixed(1)+"%");
 txt("commandHighSub",info.prior120HighType?"相對前120日"+info.prior120HighType:"距前120日高點");
 const reasons=$("commandReasons");if(reasons){reasons.replaceChildren();const flagPriority={NEAR_HIGH_TOP:1,NARROW_BREADTH:2,SCORE_DECELERATION:3,HIGH_VOLATILITY:4,STRETCHED_MA:5,FOREIGN_OUTFLOW:6,WEAK_BREADTH:7,DAY_BREADTH_WEAK:8};let flags=Array.isArray(d.flags)?[...d.flags].sort((a,b)=>(flagPriority[a.code]??50)-(flagPriority[b.code]??50)):[];if(pre)flags.unshift({code:"TX_NIGHT_PREVIEW",title:"TX夜盤 "+(pre.pct>=0?"+":"")+pre.pct.toFixed(2)+"%",severity:pre.pct<=-.5?"caution":"info",detail:"已完成夜盤收盤價，非08:58即時成交；調整分數未經獨立回測。"});
  if(x.stale&&!post)flags=[{code:"STALE_OFFICIAL",title:"今日正式資料未同步",severity:"caution",detail:"上方數字是 "+date+" 歷史分數，不能用於今日進場決策。"}];
  if(!flags.length&&r.score<60){flags=[{code:"BELOW_GATE",title:"分數未達60",severity:"caution"}];if(breadth<45)flags.push({code:"LOW_BREADTH",title:"當日廣度偏弱",severity:"caution"});}
  if(!flags.length)flags=[{code:"NO_EXTRA_VETO",title:"暫無主要附加警訊",severity:"info"}];
  for(const f of flags.slice(0,3)){const chip=document.createElement("span");chip.className="command-chip "+(f.severity||"info");chip.textContent=f.title||String(f.code||"");reasons.appendChild(chip)}
  if(flags.length>3){const more=document.createElement("span");more.className="command-chip more";more.textContent="＋"+(flags.length-3)+" 項風險";reasons.appendChild(more)}
  const full=$("commandFullFlags");if(full){full.replaceChildren();for(const f of flags){const row=document.createElement("div");row.className="full-flag";
   const bold=document.createElement("strong");bold.textContent=f.title||String(f.code||"");row.appendChild(bold);
   if(f.detail){const detail=document.createElement("span");detail.textContent=f.detail;row.appendChild(detail)}full.appendChild(row)}}
 }
 txt("commandLogic",post?.baseline?"今日參考基準＝昨日正式 "+post.baseline.base+" 分 "+(post.baseline.delta>=0?"+":"")+post.baseline.delta+" 分，根據對應今日的同月台指期夜盤調整，故為 "+post.baseline.score+"/100；基準不會因日內價格波動變動，今日現貨廣度另以警示表示，不修改正式 F／F2／G，調整門檻尚未獨立回測。":x.stale?"交易日已進入收盤後，但官方收盤資料尚未完整同步；僅顯示上次已核對分數，不改動 F／F2／G 原始策略或補入推測法人數值。":pre?"盤前情境 "+pre.base+" "+pre.deltaLabel+" = "+pre.score+"/100。"+pre.source+"，調整規則尚未通過獨立回測；正式 F／F2／G 仍用現貨分數。":post?"今日現貨資料尚未齊全，前一交易日現貨分數不自動放行新倉。":post?"只將今天的 MIS 實際成交廣度及前一晚官方台指期作風險警示；昨日 Risk Score 不具今日即時效力。":x.diag?"已核對市場廣度、波動、前高和反轉監測；僅原始 Risk Score 曾參與既有進場回測。":"目前顯示經核對的原始收盤 Risk Score；延伸市場診斷尚未同步，暫不推測其他指標。");
 const reference=!!(pre||post?.baseline);
 const currentScore=pre?Number(pre.score):post?.baseline?Number(post.baseline.score):weekendNeedsNight||x.stale||post?null:r.score==null?null:Number(r.score);
 if(scope.MarketCompact)scope.MarketCompact.render({score:currentScore,officialScore:r.score,officialDate:r.date,level:d.level,reference,date:pre?.targetDate||post?.baseline?.target||x.today,delta:pre?.adjustment??post?.baseline?.delta??null,stale:x.stale,post:!!post,weekend:x.weekend,nightPending:!!weekendNeedsNight});
 drawScoreGuide({officialScore:r.score,officialDate:r.date,currentScore,reference,level:d.level,date:pre?.targetDate||x.today});
 if(scope.MarketSentiment)scope.MarketSentiment.render({officialScore:r.score,officialDate:r.date,currentScore,reference,stale:x.stale,post:!!post,updated:data?.generatedAt,risk:r});
 const btn=$("commandPrimaryLink");
 if(btn){btn.href="./selections.html";btn.textContent=d.level==="READY"?"查看 G／D 強勢股候選 →":d.level==="REVERSAL"?"查看個股 Bottom 反轉候選 →":"查看選股名單（僅觀察） →";}
}
let strategyEvidencePending=null,strategyEvidenceLoaded=false;
async function loadStrategyEvidence(){
 const el=$("commandStrategyEvidence");if(!el||strategyEvidenceLoaded||strategyEvidencePending)return strategyEvidencePending;
 strategyEvidencePending=(async()=>{
  try{
   const res=await fetch("./data/research/market_entry_playbook/summary.json?v="+Date.now(),{cache:"no-store"});
   if(!res.ok)throw Error("研究資料不存在");
   const j=await res.json();
   if(j?.version!=="MARKET_ENTRY_PLAYBOOK_2026_V1"||j?.research?.marketDays!==728||j?.source2025ValidationOnly!==true)throw Error("驗證版本不符");
   const g=j?.comparisons?.G20_RISK60,d=j?.comparisons?.D10_RISK60;
   if(!g?.validation?.n||!g?.holdout?.n||!d?.validation?.n||!d?.holdout?.n)throw Error("驗證樣本不足");
   const f=(x)=>Number(x.meanNetPct).toFixed(2);
   if([g.validation,g.holdout,d.validation,d.holdout].some(x=>!Number.isFinite(Number(x.meanNetPct))))throw Error("無效報酬數值");
   el.textContent="G 波段20日｜2025 "+f(g.validation)+"%、2026 "+f(g.holdout)+"%；D 波段10日｜2025 "+f(d.validation)+"%、2026 "+f(d.holdout)+"%（訊號平均淨報酬）。";
   strategyEvidenceLoaded=true;
  }catch(_){el.textContent="歷史研究暫時無法核對，請查看回測報告；不因此給出額外買進許可。"}
  finally{strategyEvidencePending=null}
 })();
 return strategyEvidencePending;
}
let currentData=null,currentDiag=null,currentPremarket=null,currentFutures=null,currentIntraday=null,currentTXLive=null,fetchToken=0;
function applyFutures(f){currentFutures=f;if(currentData)draw(currentData,currentDiag)}
function applyIntraday(g){currentIntraday=g;if(currentData)draw(currentData,currentDiag)}
function applyTXLive(q){currentTXLive=q;if(currentData)draw(currentData,currentDiag)}
function applyPremarket(snapshot){currentPremarket=snapshot;if(currentData)draw(currentData,currentDiag)}
async function refresh(data){
 currentData=data;currentPremarket=null;currentIntraday=null;currentDiag=data?.marketIntelligence?.asOf===data?.dataDate?data.marketIntelligence:null;
 draw(data,currentDiag);if(!strategyEvidenceLoaded)void loadStrategyEvidence();const token=++fetchToken;
 try{
 const url="./data/research/market_intelligence/latest.json?v="+Date.now();
 const response=await fetch(url,{cache:"no-store"});if(!response.ok)throw Error("diagnostic http "+response.status);
 const j=await response.json();if(token!==fetchToken)return;
 if(j?.asOf===data?.dataDate&&Number(j.riskScore)===Number(data?.risk?.score)){currentDiag=j;draw(data,j)}
 }catch(_err){/* Fallback is the original validated daily Risk Score, never an invented ML estimate. */}
}
async function checkMl(){
 try{const r=await fetch("./data/research/market_ml_audit/summary.json?v="+Date.now(),{cache:"no-store"});
  if(!r.ok)return;const x=await r.json();if(!x?.horizonModels)return;
  txt("commandAi",x.advisoryEligible?"AI 候選僅通過方向研究；不參與買進判斷":"AI 回測未證明穩定增益，正式買進判斷維持規則式");
 }catch(_err){txt("commandAi","AI 尚未通過可供正式使用的驗證");}
}
scope.MarketCommand={evaluate,fallback,refresh,checkMl,verifiedNightPreview,applyPremarket,applyFutures,applyIntraday,applyTXLive,verifiedTXIntraday,marketPremarket,postOpenState,overnightRisk,tradedBreadth,txScoreDelta,scoreBand,scoreGuidance};
if(typeof module!=="undefined"&&module.exports)module.exports={fallback,evaluate,verifiedNightPreview,marketPremarket,postOpenState,verifiedTXIntraday,taipeiParts,overnightRisk,tradedBreadth,txScoreDelta,scoreBand,scoreGuidance};
})(typeof window!=="undefined"?window:globalThis);
