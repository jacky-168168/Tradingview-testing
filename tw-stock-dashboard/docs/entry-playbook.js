/* Buy-timing playbook: dated cash research + conservative market-open verification.
 * This is NOT real-time quote data, and NEVER alters F/F2/G production selectors.
 * Published 2025/2026 evidence is read only; GRU never auto-approves a buy.
 */
(function(scope){"use strict";
const $=id=>typeof document==="undefined"?null:document.getElementById(id);
const TOP_VETO=new Set(["🔴 Strong Top Reversal","🟠 Top Reversal Attempt","🔴 Extreme Overbought"]);
function parts(now=new Date()){
 const p=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",weekday:"short",hour:"2-digit",minute:"2-digit",hourCycle:"h23"}).formatToParts(now);
 const q=Object.fromEntries(p.map(x=>[x.type,x.value]));
 return {date:q.year+"-"+q.month+"-"+q.day,minute:Number(q.hour)*60+Number(q.minute),weekday:q.weekday};
}
function checkedReport(q){
 return q?.version==="MARKET_ENTRY_PLAYBOOK_2026_V1"&&q?.source2025ValidationOnly===true&&
  q?.research?.marketDays===728&&q?.policy?.risk60&&q?.comparisons?.G20_RISK60?.validation?.n>=90;
}
function assess(data,preview=null,report=null,now=new Date()){
 const p=parts(now),r=data?.risk||{},date=String(data?.dataDate||r.date||"");
 const score=Number(r.score),ok=r.score!==null&&r.score!==undefined&&Number.isFinite(score)&&score>=0&&score<=100&&date&&date===r.date;
 const validR=checkedReport(report),weekend=p.weekday==="Sat"||p.weekday==="Sun";
 const diff=date?Math.round((Date.parse(p.date+"T12:00:00+08:00")-Date.parse(date+"T12:00:00+08:00"))/86400000):999;
 const stale=diff>8||diff<0||!ok;
 const inCash=!weekend&&p.minute>=540&&p.minute<810;
 const inPre=!weekend&&p.minute>=510&&p.minute<540;
 const verifiedNight=inPre&&preview?.valid===true&&preview.sourceDate===date&&preview.nextDate===p.date&&
    Number(preview.base)===score&&Number.isFinite(Number(preview.pct))&&Math.abs(Number(preview.pct))<=12;
 const nightDrop=verifiedNight&&Number(preview.pct)<=-1;
 const top=String(r.topState||"");const veto=TOP_VETO.has(top)||TOP_VETO.has(String(r.activeState||""));
 const breadth=r.breadth!=null&&Number.isFinite(Number(r.breadth))?Number(r.breadth):null;
 const diagonal=data?.marketIntelligence?.asOf===date&&Number(data.marketIntelligence.riskScore)===score?data.marketIntelligence:null;
 const narrow=diagonal?.marketHealth?.indexBreadthDivergence===true;
 const weakBreadth=breadth!==null&&breadth<45;
 const facts=[];
 if(ok)facts.push({ok:score>=60,text:"現貨趨勢 "+score+"/100"+(score>=60?"（≥60）":"（未達60）")});
 else facts.push({ok:false,text:"正式現貨分數尚未核對"});
 facts.push({ok:!weakBreadth&&breadth!==null,text:breadth===null?"最近收盤市場廣度缺值":"上漲家數 "+breadth.toFixed(1)+"%（"+date+" 收盤）"});
 facts.push({ok:false,text:"盤中 VWAP／G 同步率：沒有已驗證即時資料"});
 if(verifiedNight)facts.push({ok:!nightDrop,text:"TX 已完成夜盤 "+(Number(preview.pct)>=0?"+":"")+Number(preview.pct).toFixed(2)+"%（非即時）"});
 const ctx={clock:p,referenceDate:date||null,score:ok?score:null,immediateBuyConfirmed:false,inCash,inPre,validStudy:validR,
  facts,nightDrop,trendEligible:false,tone:"unknown",status:"⚪ 無法確認買進條件",headline:"先等待有效市場資料",
  action:"現貨 Risk Score 與歷史研究尚未核對；不提供買進許可。",basis:"沒有完成即時盤中確認，不能聲稱現在可買。",
  warning:"",horizon:"無",timing:"",history:null};
 const finish=(tone,status,headline,action,basis,horizon)=>{
   Object.assign(ctx,{tone,status,headline,action,basis,horizon});return ctx;
 };
 ctx.timing=weekend?"週末休市｜下個交易日重新核對":inPre?"08:30–08:59｜只作盤前風險預估":inCash?"09:00–13:30｜盤中需即時確認":"非現貨交易時段｜可規劃下次進場";
 if(!ok||stale)return finish("unknown","⚪ 暫無買進結論","官方市場資料無效或過期","檢查最新盤後 Risk Score、資料日期與研究來源。","超過合理日期間隔時禁止使用舊分數。","無");
 if(veto)return finish("stop","⛔ 不建議新倉","出現已確認的頂部或極端過熱","先暫停一般強勢股追價，等待頂部警戒解除並重新核對行情。","確認 TOP／過熱是風險卡控，不代表一定會跌。","無");
 if(score<60){
   const reversal=String(r.bottomState||"")==="🟢 Strong Bottom Reversal";
   return finish(reversal?"watch":"stop",reversal?"🟣 只觀察反轉":"⛔ 暫不買進強勢股",
      reversal?"低分反轉例外，非一般追價訊號":"收盤 Risk Score 低於 60",
      reversal?"僅另行評估個股 Bottom 反轉與停損；不當作 G／D 趨勢進場許可。":"大盤未達回測中的基本趨勢條件，等待收盤風險改善。",
      "G 20 日／D 10 日研究使用 Risk≥60；低分不代表一定下跌。","無");
 }
 ctx.trendEligible=true;
 if(nightDrop)return finish("stop","⛔ 盤前暫緩進場","台指期夜盤偏弱，等待現貨開盤","已完成夜盤相對同月日盤跌至少 1%；不要因前次收盤分數≥60就在08:58預先下多單。",
     "這是保守盤前風險提示，夜盤門檻本身尚未通過股票買點回測。","G 約20日／D 約10日");
 if(inCash)return finish("watch","🟡 盤中尚未確認可買","趨勢條件達標，但沒有即時驗證",
   "09:00後不能拿前次收盤分數取代今日廣度；先看上市櫃是否普漲、個股是否站穩開盤區間與風險停損，再決定是否交易。",
   "未接入可核對時間戳的即時盤中廣度、VWAP 與 G 候選同步率，不能發布自動『現在可買』訊號。","G 約20日／D 約10日");
 if(weakBreadth||narrow)return finish("watch","🟠 波段可觀察，避免追高","最近收盤市場廣度偏弱",
   "即使 Risk≥60，少數權值股可能使指數看起來強；等待下一交易日廣度與個股量價同步。",
   "當日廣度<45%或10日指數／廣度背離屬未單獨證明能提高實際獲利的警訊。","G 約20日／D 約10日");
 const strong=score>=80;
 const a=strong?"Risk≥80 的 G 20 日持有研究在2025、2026均有正平均淨報酬，但與Risk≥60的差額信賴區間跨零。":"Risk≥60 的 G 20 日／D 10 日研究在2025、2026均有正平均淨報酬。";
 return finish(strong?"ready":"prepare",strong?"🟢 波段條件偏強｜非即時買點":"🟡 可準備波段候選｜待確認",
    strong?"風險分數較高，優先規劃波段":"趨勢門檻已達，規劃下一交易日",
    "先檢查 G／D 名單、買點與停損；開盤後核對實際現貨與 G 候選走勢。早盤第一根紅 K 不構成買進理由。",
    a,"G 約20日／D 約10日");
}
let current=null,preview=null,study=null,loading=null;
function draw(now=new Date()){
 const box=$("entryPlaybook");if(!box)return;
 const x=assess(current,preview,study,now);
 box.dataset.tone=x.tone;box.dataset.study=x.validStudy?"verified":"missing";
 const t=(id,s)=>{const el=$(id);if(el)el.textContent=s};
 t("entryPlaybookStatus",x.status);t("entryPlaybookHeadline",x.headline);t("entryPlaybookAction",x.action);
 t("entryPlaybookTiming",x.timing);t("entryPlaybookHorizon",x.horizon);
 t("entryPlaybookBasis",x.basis);t("entryPlaybookSource","正式現貨資料日 "+(x.referenceDate||"未知")+"；"+(x.validStudy?"2025驗證＋2026時序測試已發布":"研究證據尚未驗證"));
 t("entryPlaybookInstant","盤中即時買進許可：未確認");
 const steps=$("entryPlaybookFacts");
 if(steps){steps.replaceChildren();for(const f of x.facts){const span=document.createElement("span");span.className="entry-fact "+(f.ok?"yes":"no");span.textContent=(f.ok?"✓ ":"• ")+f.text;steps.appendChild(span)}}
 const research=$("entryPlaybookResearch");
 if(research){
  if(x.validStudy){const g=study.comparisons.G20_RISK60,d=study.comparisons.D10_RISK60;
   research.textContent="歷史研究｜G 20D Risk≥60：2025 "+g.validation.meanNetPct.toFixed(2)+"%、2026 "+g.holdout.meanNetPct.toFixed(2)+
     "%；D 10D Risk≥60：2025 "+d.validation.meanNetPct.toFixed(2)+"%、2026 "+d.holdout.meanNetPct.toFixed(2)+"%（訊號平均淨報酬，非即時或複利）。";
  }else research.textContent="歷史研究尚未核對；不採用 AI 分數作為買進許可。";
 }
}
async function refresh(data){
 current=data;preview=null;draw();
 if(loading)return loading;
 loading=(async()=>{
  try{const response=await fetch("./data/research/market_entry_playbook/summary.json?v="+Date.now(),{cache:"no-store"});
   if(!response.ok)throw Error("No verified study");
   const z=await response.json();study=checkedReport(z)?z:null;
  }catch(_){study=null}finally{draw();loading=null}
 })();
 return loading;
}
function applyPremarket(p){preview=p;draw()}
function tick(){if(current)draw()}
scope.EntryPlaybook={assess,refresh,applyPremarket,tick,parts,checkedReport};
if(typeof module!=="undefined"&&module.exports)module.exports={assess,parts,checkedReport};
})(typeof window!=="undefined"?window:globalThis);
