/* Independent, display-only US options overlay. No G/D score or trading gate mutation. */
(function(){
"use strict";
const $=id=>document.getElementById(id);
const ui=()=>({head:$("usOptionsHeadline"),body:$("usOptionsBody")});
const pct=x=>Number.isFinite(Number(x))?Number(x).toFixed(2)+"%":"未驗證";
const text=(parent,value)=>{const d=document.createElement("div");d.textContent=value;parent.appendChild(d);return d};
async function get(path){const r=await fetch(path+"?t="+Date.now(),{cache:"no-store"});if(!r.ok)throw Error("HTTP "+r.status);return r.json()}
async function start(){
 const {head,body}=ui();if(!head||!body)return;
 const url="./data/research/us_options/";
 try{
  const [latest,report]=await Promise.all([get(url+"latest.json"),get(url+"backtest.json")]);
  if(latest.date!==report.usSourceEnd||!Number.isFinite(Number(latest.gex))||!Number.isFinite(Number(latest.dix)))throw Error("資料日期或數值校驗失敗");
  const now=new Date(),date=new Date(latest.date+"T00:00:00Z"),age=(now.getTime()-date.getTime())/86400000,stale=!Number.isFinite(age)||age>8||age<0;
  const state=Number(latest.gex)>=0?"Gamma 正值（潛在波動較低）":"Gamma 負值（留意波動擴大）";
  head.textContent=stale?"⚪ 資料過期｜不提供當日判斷":(Number(latest.gex)>=0?"🟢 ":"🟠 ")+state;
  body.replaceChildren();
  text(body,"美股資料日："+latest.date+"｜DIX："+Number(latest.dix).toFixed(2)+"%｜GEX："+Math.round(Number(latest.gex)).toLocaleString("en-US")+"｜S&P 500："+Number(latest.spx).toLocaleString("en-US"));
  if(stale)text(body,"⚠ 來源資料超過八天未更新，舊訊號不可用於今日台股風險判斷。");
  const groups=report.groups||{},old=groups.oos_2022_2023,newer=groups.recent_2024_2026;
  if(old?.sufficientGexGroups)text(body,"歷史樣本外 2022～2023（保守延後一天）：GEX 正值次日台股上漲率 "+pct(old.gexPositive?.upRatePct)+"（"+old.gexPositive?.n+"日）；負值 "+pct(old.gexNegative?.upRatePct)+"（"+old.gexNegative?.n+"日）。");
  const training=groups.training_2015_2021;
  if(training?.sufficientGexGroups)text(body,"2015～2021 訓練段：GEX 正值上漲率 "+pct(training.gexPositive?.upRatePct)+"；負值 "+pct(training.gexNegative?.upRatePct)+"。與 2022～2023 方向相反，關聯不具跨時期穩定性。");
  if(newer?.sufficientGexGroups)text(body,"近期 2024～2026 獨立分段：GEX 正值台股上漲率 "+pct(newer.gexPositive?.upRatePct)+"（"+newer.gexPositive?.n+"日）；負值 "+pct(newer.gexNegative?.upRatePct)+"（"+newer.gexNegative?.n+"日）。");
  if(newer&&!newer.sufficientGexGroups)text(body,"2024～2026 驗證：正負 GEX 子樣本不足，暫不推論。");
  const note=text(body,"僅為美股選擇權市場風險參考。DIX ≥45% 未通過穩定預測驗證；GEX 關聯性跨期間不一致，不能作為買賣訊號。未加入 Risk Score／G 選股權重。");note.style.color="#64748b";note.style.fontSize="12px";
  const links=document.createElement("div");links.style.marginTop="7px";for(const [label,href] of [["官方來源 ↗","https://squeezemetrics.com/monitor/dix"],["回測結果 JSON ↗",url+"backtest.json"]]){const a=document.createElement("a");a.href=href;a.textContent=label;a.target="_blank";a.rel="noopener noreferrer";a.style.marginRight="17px";a.style.color="#2563eb";links.appendChild(a)}body.appendChild(links);
 }catch(e){head.textContent="⚪ 研究資料尚未完成同步";body.textContent="DIX／GEX 尚未取得可核對的正式來源，暫不顯示交易風險訊號；原本台股大盤分數與選股均不受影響。";}
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start,{once:true});else start();
})();
