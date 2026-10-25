/* Dynamic, read-only visual summary. Real source fields only; no invented consensus or trades. */
(function(root,factory){"use strict";const api=factory();if(typeof module!=="undefined"&&module.exports)module.exports=api;else root.SixAgentVisual=api;})(typeof globalThis==="object"?globalThis:this,function(){"use strict";
const DEFS=[
 {id:"atlas",name:"ATLAS",role:"G 強勢股掃描",note:"價量與相對強弱",icon:"scan"},
 {id:"vega",name:"VEGA",role:"技術面結構",note:"均線、ATR、訊號",icon:"chart"},
 {id:"orion",name:"ORION",role:"新聞與事件",note:"核對關聯與來源",icon:"news"},
 {id:"luna",name:"LUNA",role:"社群情緒",note:"逐篇語意／樣本品質",icon:"moon"},
 {id:"titan",name:"TITAN",role:"硬性風險否決",note:"否決優先且不能解除",icon:"shield"},
 {id:"nova",name:"NOVA",role:"多代理總結",note:"整理證據，待人審查",icon:"layers"}
];
const SHAPES={
 scan:'<circle cx="11" cy="11" r="7"/><path d="m16 16 5 5M8 11h6m-3-3v6"/>',
 chart:'<path d="M3 20h18M5 16l4-5 4 3 6-8"/><circle cx="19" cy="6" r="1"/>',
 news:'<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 7h8M8 11h8M8 15h5"/>',
 moon:'<path d="M20.5 14a8.5 8.5 0 0 1-10.5-10.5A8.5 8.5 0 1 0 20.5 14Z"/><path d="m18 3 .5 1.5L20 5l-1.5.5L18 7l-.5-1.5L16 5l1.5-.5Z"/>',
 shield:'<path d="M12 2 20 6v6c0 5-3 8-8 10-5-2-8-5-8-10V6Z"/><path d="m9 12 2 2 4-4"/>',
 layers:'<path d="m12 3 9 5-9 5-9-5 9-5ZM3 12l9 5 9-5M3 16l9 5 9-5"/>'
};
const safeNumber=n=>typeof n==="number"&&Number.isFinite(n)?n:null;
const num=(n,d=0)=>safeNumber(n)===null?"缺值":n.toFixed(d);
function statusTone(status){
 if(/否決|拒絕|極度偏空|偏空|過高/.test(status))return "bad";
 if(/不足|待|未|歷史|觀察|無法|難判|缺值|未證實/.test(status))return "warn";
 if(/候選|偏多|偏強|核實|通過/.test(status))return "good";
 return "neutral";
}
function descriptor(data,mode){
 const d=data||{},x=mode||{};
 switch(x.id){
 case "atlas":return {label:d.status||"尚未取得",metric:"G 排名 "+(d.rank??"—")+"｜RS20 "+num(d.rs20,1),
  tone:d.status==="候選"?"good":"warn"};
 case "vega":return {label:d.status||"待確認",metric:"MA20 "+num(d.slope,1)+"%｜ATR "+num(d.atrPct,1)+"%",
  tone:statusTone(d.status||"")};
 case "orion":return {label:d.status||"缺值",metric:"核實 "+(d.verifiedCount??0)+" 則｜相關 "+(Array.isArray(d.sources)?d.sources.length:0)+" 則",
  tone:d.verifiedCount?"good":"warn"};
 case "luna":{
  const v=d.semanticSummary||{},ok=["verified","cached","partial"].includes(v.status)&&
   safeNumber(v.classified)!==null;
  return {label:d.socialSample?d.socialStatus:"無可核對的討論",metric:ok?
   "Gemini 判讀 "+v.classified+" 篇｜投資意見 "+(v.investment??0)+" 篇":
   "Gemini 未驗證｜規則樣本 "+(d.socialSample??0)+" 篇",
  tone:"warn"};}
 case "titan":return {label:d.hardVeto?"禁止通過":"已過研究閘門",
  metric:d.hardVeto?(d.veto?.[0]||"資料不完整"):"仍需人工檢查，不代表可下單",
  tone:d.hardVeto?"bad":"good"};
 case "nova":return {label:d.status||"待整理",metric:d.noTrade===true?
  "僅供研究｜不提供下單許可":"輸出尚未通過安全驗證",
  tone:d.noTrade===true?statusTone(d.status||""):"bad"};
 }
 return {label:"尚未取得",metric:"等待資料",tone:"warn"};
}
function summary(out,c){
 if(!out||!c)return {label:"尚無有效候選資料",tone:"warn",caption:"缺少可供核對的 G 候選，六代理不生成虛構研究結論。"};
 const a=c.agents||{};
 if(!out.liveVerified)return {label:"歷史研究・不可當成進場訊號",tone:"warn",
  caption:(c.code+" "+c.name)+"｜資料日 "+(c.asOfDate||"缺值")+"｜"+(a.titan?.hardVeto?"TITAN 已否決":"未驗證盤中資料")};
 if(a.titan?.hardVeto)return {label:"TITAN 硬性否決",tone:"bad",
  caption:c.code+" "+c.name+"｜"+(a.titan.veto?.[0]||"需查核風險資料")};
 return {label:a.nova?.status||"僅供研究",tone:"warn",
  caption:c.code+" "+c.name+"｜已通過部分研究閘門，仍須人工審核；不得自動下單"};
}
function el(tag,cls,value){const n=document.createElement(tag);if(cls)n.className=cls;if(value!==undefined)n.textContent=String(value);return n}
function setText(id,value){const e=document.getElementById(id);if(e)e.textContent=String(value)}
function render(out,c){
 if(typeof document==="undefined")return;
 const info=summary(out,c),hero=document.getElementById("vHero");
 if(hero)hero.dataset.tone=info.tone;
 setText("vHeadline",info.label);setText("vCaption",info.caption);
 setText("vSelected",c?c.code+" "+c.name+"｜六代理分析":"尚無候選");
 setText("vDataMode",out?.liveVerified?"已驗證盤中規則快照":"休市／非即時規則快照");
 setText("vCandidates",out?.counts?.candidates??"—");
 setText("vVeto",out?.counts?.veto??"—");
 setText("vResearch",out?.counts?.review??"—");
 const score=safeNumber(out?.source?.riskScore),risk=document.getElementById("vRiskGauge");
 setText("vRiskValue",score===null?"—":num(score,0));
 if(risk){const pct=score===null?0:Math.min(100,Math.max(0,score));
  risk.setAttribute("stroke-dasharray",pct+" 100");
  risk.setAttribute("stroke",score===null?"#9ca3af":score<60?"#fecaca":"#9ef0cd");
 }
 const grid=document.getElementById("vCards");if(!grid)return;grid.replaceChildren();
 for(const role of DEFS){
  const data=c?.agents?.[role.id]||null,x=data?descriptor(data,role):
    {label:"等待資料",metric:"尚未取得可核對結果",tone:"warn"};
  const card=el("article","v-agent");card.dataset.role=role.id;
  const top=el("div","v-agent-top"),icon=el("span","v-icon");
  icon.setAttribute("aria-hidden","true");
  // Static, in-repository SVG path literals only; untrusted model/source data uses textContent.
  icon.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true">'+SHAPES[role.icon]+'</svg>';
  top.append(icon);
  const name=el("div");name.append(el("div","v-agent-name",role.name),el("div","v-agent-role",role.role));
  top.append(name);card.append(top);
  const main=el("div","v-agent-main",x.label);main.dataset.tone=x.tone;card.append(main);
  card.append(el("div","v-agent-metric",x.metric));
  card.append(el("div","v-agent-note",role.note));
  grid.append(card);
 }
}
function modelReport(doc,hours){
 if(typeof document==="undefined")return;
 const ok=doc?.verifiedModelExecution===true&&doc?.inferenceCalls===9&&doc?.noTrade===true;
 const stale=ok&&(hours>26||!doc.inputIsLive);
 const host=document.getElementById("vModelStatus");if(!host)return;
 host.dataset.tone=ok&&stale?"warn":ok?"good":"bad";
 host.textContent=!ok?"Gemini 九輪：未驗證":
  "Gemini 九輪："+(stale?"歷史研究":"已驗證報告")+"｜"+
  new Date(doc.generatedAt).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false,
  month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"});
 setText("vModelEvidence",ok?"模型來源日："+(doc.evidenceDate||"缺值")+"｜與上方規則快照獨立":"未執行或報告驗證失敗，不顯示假結論");
}
return {render,modelReport,summary,descriptor,statusTone,DEFS};
});