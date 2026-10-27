/* Compact homepage decision layer: presentation only. Never changes Risk Score, TX rules or G/D/F/F2 gates. */
(function(root){
"use strict";
const $=id=>typeof document==="undefined"?null:document.getElementById(id);
const put=(id,value)=>{const e=$(id);if(e)e.textContent=String(value==null?"—":value)};
const validScore=n=>n!==null&&n!==undefined&&n!==""&&Number.isFinite(Number(n))&&Number(n)>=0&&Number(n)<=100;
const safeScore=n=>validScore(n)?String(Math.round(Number(n))):"—";
const ACTION={STOP:"暫緩新倉",WAIT:"先觀望",CAUTION:"避免追高",REVERSAL:"等待反轉確認",READY:"擇優評估",UNKNOWN:"等待有效資料"};
function render(s){
 const box=$("compactMarketSummary");if(!box)return;
 const level=String(s?.level||"UNKNOWN").toUpperCase(),reference=!!s?.reference,provisional=!!s?.provisional,score=validScore(s?.score)?Number(s.score):null;
 box.dataset.tone=(level==="STOP"?"stop":level==="READY"?"ready":level==="CAUTION"?"caution":"wait");
 box.dataset.reference=reference?"true":"false";
 put("compactAction",level==="STOP"?"暫緩新倉":score===null&&validScore(s?.officialScore)?(s?.post?"今日盤中待確認":s?.stale?"今日資料待同步":"等待今日風險確認"):score===null?"等待有效資料":ACTION[level]||"先觀望");
 put("compactScore",safeScore(score));
 put("compactBand",score!==null&&root.MarketCommand?.scoreBand?root.MarketCommand.scoreBand(score)?.label||"待確認":"資料待確認");
 put("compactScoreType",provisional?"今日 TX 盤中參考試算｜非正式、未回測":reference?"下個交易日盤前參考分數｜未獨立回測":s?.stale?"歷史風險分數｜最新資料待同步":s?.post?"今日現貨正式分數待更新":s?.nightPending?"下個交易日盤前風險｜夜盤資料待核對":"最近正式收盤 Risk Score");
 put("compactSession",provisional?"今日盤中 "+(s?.date||"待確認")+"｜前次正式 "+(s?.officialDate||"待確認"):reference?"參考交易日 "+(s?.date||"待確認"):score===null&&validScore(s?.officialScore)?"今日盤中資料待核對｜前次正式資料日 "+(s?.officialDate||"待確認"):"正式資料日 "+(s?.officialDate||"待確認"));
 const off=validScore(s?.officialScore)?Number(s.officialScore):null,delta=reference&&s?.delta!=null&&Number.isFinite(Number(s.delta))?Math.round(Number(s.delta)):null;
 put("compactOfficial",safeScore(off));
 put("compactNight",delta===null?"—":(delta>=0?"+":"")+delta);
 const n=$("compactNightCell");if(n)n.hidden=!reference;
 const info=$("compactEquation");
 if(info)info.textContent=provisional?"今日 TX 盤中參考＝"+safeScore(off)+" 分（"+(s?.officialDate||"未知")+" 正式收盤）"+(delta===null?"":(delta>=0?"＋":"－")+Math.abs(delta)+" 分（今日 TX 漲跌分級）")+"；未經樣本外回測，不當成今日正式分數或新倉許可。":reference?"盤前參考＝正式收盤分數＋夜盤調整；風險校正為獨立研究，不參與此運算。":s?.nightPending?"夜盤尚未完成驗證，前次現貨收盤分數 "+safeScore(off)+" 分不代表下一交易日的盤前風險。":score===null&&off!==null?"今天尚無經驗證的盤中正式分數；前次收盤 "+safeScore(off)+" 分僅供歷史參考，不代表今天可進場。":"原始正式分數與校正研究分開呈現；盤後資料不代表下次開盤的交易許可。";
 const guard=$("compactResearch");
 if(guard)guard.hidden=off===null;
 put("compactScoreFootnote",provisional?"今日 TX 參考試算，不是正式 Risk Score；不授權交易。":reference?"僅供盤前情境判讀，非正式盤中交易許可。":"市場分類不是進出場保證，仍須確認個股條件。");
}
function review(result,pattern){
 const el=$("compactAdjusted"),box=$("compactResearch");if(!el)return;
 const verified=!!result?.valid&&validScore(result?.adjusted);
 el.textContent=verified?safeScore(result.adjusted):"—";
 if(box)box.dataset.verified=verified?"true":"false";
 const badge=$("compactPattern");
 if(badge){
  const name=String(pattern?.name||"");
  badge.hidden=!name||name==="一般趨勢觀察"||name==="型態待確認";
  if(!badge.hidden)badge.textContent=name;
 }
}
if(typeof module!=="undefined"&&module.exports)module.exports={validScore,safeScore,ACTION};
root.MarketCompact={render,review};
})(typeof window!=="undefined"?window:globalThis);
