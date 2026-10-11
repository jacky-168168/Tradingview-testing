/* Market Command Center: transparent on-screen guidance; NEVER overrides live A/D/F/F2/G selectors.
 * Published official Risk Score is the ONLY primary score. No AI predictions are treated as buy permission.
 */
(function(scope){
"use strict";
const $=id=>typeof document==="undefined"?null:document.getElementById(id);
const twDay=()=>new Intl.DateTimeFormat("sv-SE",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
const twWeekday=()=>new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Taipei",weekday:"short"}).format(new Date());
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
 const marketDate=String(r?.date||"");const today=twDay();
 const diff=marketDate?Math.round((Date.parse(today+"T12:00:00+08:00")-Date.parse(marketDate+"T12:00:00+08:00"))/86400000):999;
 let stale=diff>8||diff<0||!marketDate;
 if(stale)decision={level:"UNKNOWN",headline:"⚪ 資料過期，暫不提供進場判斷",action:"最近交易日與目前日期差距過大；請核對 GitHub Actions 及臺灣證交所資料。",flags:[]};
 return {decision,diag:!stale&&diag?.asOf===marketDate?diag:null,marketDate,today,stale,weekend:["Sat","Sun"].includes(twWeekday())};
}
function txt(id,value){const el=$(id);if(el)el.textContent=value}
function strength(score){
 if(!Number.isFinite(score))return "尚無風險分數";
 if(score>=80)return "強勢多頭";
 if(score>=60)return "趨勢達標";
 if(score>=50)return "中性觀察";
 return "弱勢警戒";
}
function draw(data,diag){
 const panel=$("marketCommand");if(!panel)return;
 const r=data?.risk||{},val=Number(r.score),x=evaluate(r,diag),d=x.decision,info=x.diag?.marketHealth||{};
 panel.dataset.level=d.level;panel.className="market-command cmd-"+d.level.toLowerCase();
 txt("commandStatus",d.headline);
 txt("commandAction",d.action);
 txt("commandScore",Number.isFinite(val)&&r.score!=null?String(val):"--");
 txt("commandScoreDescription",strength(val)+"｜原始現貨分數");
 const signalDate=x.marketDate||"未知";
 txt("commandAsOf","最新已收盤 "+signalDate+(x.weekend?"｜今日休市":"｜非即時交易訊號"));
 let dayLabel=x.weekend?"休市日：下個交易日的盤前參考":x.today===signalDate?"最近資料日：已完成的現貨市場評估":"最近資料日：非即時盤中訊號";
 if(x.stale)dayLabel="資料需要更新：暫停進場建議";
 txt("commandTiming",dayLabel);
 const breadth=Number(r.breadth);
 txt("commandBreadth",r.breadth==null||!Number.isFinite(breadth)?"—":breadth.toFixed(1)+"%");
 txt("commandBreadthSub",info.breadth5Pct!=null?"近5日平均 "+Number(info.breadth5Pct).toFixed(1)+"%":"TWSE 上漲家數比例");
 txt("commandScoreChange",info.riskScore5SessionChange==null?"—":(Number(info.riskScore5SessionChange)>0?"+":"")+Number(info.riskScore5SessionChange).toFixed(0)+" 分");
 txt("commandScoreChangeSub",info.riskScore3MA!=null?"3日平滑分數 "+Number(info.riskScore3MA).toFixed(1):"5交易日分數變化");
 txt("commandVol",info.realizedVol20AnnualPct==null?"—":Number(info.realizedVol20AnnualPct).toFixed(1)+"%");
 txt("commandVolSub",info.volatilityHistoryPercentile!=null?"波動歷史百分位 "+Number(info.volatilityHistoryPercentile).toFixed(0):"20日年化波動");
 const dist=info.distancePrior120HighPct;
 txt("commandHigh",dist==null?"—":(Number(dist)>0?"+":"")+Number(dist).toFixed(1)+"%");
 txt("commandHighSub",info.prior120HighType?"相對前120日"+info.prior120HighType:"距前120日高點");
 const reasons=$("commandReasons");if(reasons){reasons.replaceChildren();let flags=Array.isArray(d.flags)?d.flags:[];
  if(!flags.length&&r.score<60){flags=[{code:"BELOW_GATE",title:"分數未達60",severity:"caution"}];if(breadth<45)flags.push({code:"LOW_BREADTH",title:"當日廣度偏弱",severity:"caution"});}
  if(!flags.length)flags=[{code:"NO_EXTRA_VETO",title:"暫無主要附加警訊",severity:"info"}];
  for(const f of flags.slice(0,5)){const chip=document.createElement("span");chip.className="command-chip "+(f.severity||"info");chip.textContent=f.title||String(f.code||"");reasons.appendChild(chip)}
 }
 txt("commandLogic",x.diag?"已核對市場廣度、波動、前高和反轉監測；僅原始 Risk Score 曾參與既有進場回測。":"目前顯示經核對的原始收盤 Risk Score；延伸市場診斷尚未同步，暫不推測其他指標。");
 const btn=$("commandPrimaryLink");
 if(btn){btn.href="./selections.html";btn.textContent=d.level==="READY"?"查看 G／D 強勢股候選 →":d.level==="REVERSAL"?"查看個股 Bottom 反轉候選 →":"查看選股名單（僅觀察） →";}
}
let currentData=null,currentDiag=null,fetchToken=0;
async function refresh(data){
 currentData=data;currentDiag=data?.marketIntelligence?.asOf===data?.dataDate?data.marketIntelligence:null;
 draw(data,currentDiag);const token=++fetchToken;
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
scope.MarketCommand={evaluate,fallback,refresh,checkMl};
if(typeof module!=="undefined"&&module.exports)module.exports={fallback,evaluate};
})(typeof window!=="undefined"?window:globalThis);
