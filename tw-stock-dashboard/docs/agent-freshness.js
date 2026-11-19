/* 六代理來源時效看板：只呈現可核對的 JSON，不把來源更新誤稱為 Gemini 執行。 */
(function(root,factory){"use strict";const api=factory();if(typeof module!=="undefined"&&module.exports)module.exports=api;else{root.AgentSourceFreshness=api;if(typeof document!=="undefined"){const start=()=>api.loadAndRender();if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",start,{once:true});else start();document.getElementById("refresh")?.addEventListener("click",start);}}})(typeof globalThis==="object"?globalThis:this,function(){"use strict";
const TZ="Asia/Taipei",ROLES=["ATLAS","VEGA","ORION","LUNA","TITAN","NOVA"];
function dateTW(at){return new Intl.DateTimeFormat("en-CA",{timeZone:TZ,year:"numeric",month:"2-digit",day:"2-digit"}).format(at)}
function fullTW(s){const ms=Date.parse(s||"");return Number.isFinite(ms)?new Intl.DateTimeFormat("zh-TW",{timeZone:TZ,hour12:false,year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}).format(new Date(ms)):"無可驗證時間"}
function validDay(s){return typeof s==="string"&&/^20\d{2}-\d{2}-\d{2}$/.test(s)?s:null}
function recent(ts,now,hours){const d=Date.parse(ts||"");return Number.isFinite(d)&&d<=now.getTime()&&now.getTime()-d<=hours*3600000}
function makeRow(name,source,day,stamp,now,extra="",valid=true){
 const today=dateTW(now),known=validDay(day),isToday=known===today;
 const ok=valid&&isToday&&(stamp===null||recent(stamp,now,8));
 const state=!valid?"來源不完整":!known?"日期未確認":ok?"今日來源已更新":"歷史來源／未完成今日更新";
 return {name,source,state,tone:ok?"ok":"warn",detail:"資料日："+(known||"缺值")+"｜來源時間："+(stamp?fullTW(stamp):"未提供時間")+(extra?"｜"+extra:"")};
}
function build(d,nowInput){const now=nowInput instanceof Date?nowInput:new Date(),daily=d.daily||{},orion=d.orion||{},social=d.social||{},llm=d.llm||{};
 const sourceDay=validDay(daily.dataDate),riskDay=validDay(daily.risk?.date);
 const gExtra="正式日榜單；盤中價更新不代表重新計算日榜";
 const gA=makeRow("ATLAS","正式 G 候選",sourceDay,null,now,gExtra,Array.isArray(daily.models?.G)&&daily.models.G.length>0);
 const gV=makeRow("VEGA","G 技術指標",sourceDay,null,now,gExtra,Array.isArray(daily.models?.G)&&daily.models.G.length>0);
 const newsDay=recent(orion.generatedAt,now,8)?dateTW(new Date(orion.generatedAt)):null;
 const feeds=orion.coverage||{},orionOk=Array.isArray(orion.items)&&orion.items.length>0&&Number(feeds.healthyFeeds)>0;
 const newsExtra="來源 "+(feeds.healthyFeeds??"缺值")+"/"+(feeds.configuredFeeds??"缺值")+"；Gemini 標題判讀 "+(orion.semantic?.classified??0)+"/"+(orion.semantic?.eligible??"缺值")+" 篇";
 const o=makeRow("ORION","財經新聞來源",newsDay,orion.generatedAt,now,newsExtra,orionOk);
 const socialDay=recent(social.generatedAt,now,8)?dateTW(new Date(social.generatedAt)):null;
 const socialOk=Array.isArray(social.items)&&Object.values(social.sources||{}).some(x=>x&&["ok","partial"].includes(x.status));
 const socialExtra="G 個股熱度使用 "+(validDay(social.stockHeat?.sourceDate)||"缺值")+" 日候選；社群來源與個股熱度日期不同";
 const l=makeRow("LUNA","社群公開資料",socialDay,social.generatedAt,now,socialExtra,socialOk);
 const risk=makeRow("TITAN","正式大盤風險",riskDay,null,now,"不因社群或新聞更新而改變風險分數",typeof daily.risk?.score==="number"&&Number.isFinite(daily.risk.score));
 const nova=makeRow("NOVA","規則研究彙整",sourceDay,null,now,"與 Gemini 九輪報告分開；風控不得覆寫",gA.tone==="ok"&&risk.tone==="ok"&&riskDay===sourceDay);
 const ts=Date.parse(llm.generatedAt||"");
 const verified=llm.verifiedModelExecution===true&&llm.provider==="Google Gemini API"&&llm.inferenceCalls===9&&llm.noTrade===true&&Number.isFinite(ts)&&ts<=now.getTime();
 const modelToday=verified&&validDay(llm.evidenceDate)===dateTW(now)&&recent(llm.generatedAt,now,26);
 const model={name:"Gemini 九輪模型會議",source:"獨立模型報告",state:!verified?"未取得已驗證模型報告":modelToday?"今日有效來源的模型報告":"歷史模型報告／尚未完成今日推論",tone:modelToday?"ok":"warn",
  detail:"模型完成："+(verified?fullTW(llm.generatedAt):"缺值")+"｜使用市場資料日："+(validDay(llm.evidenceDate)||"缺值")+"｜成功執行九輪："+(verified?"是":"未驗證")};
 return {rows:[gA,gV,o,l,risk,nova],model,today:dateTW(now)};
}
async function json(path){const res=await fetch(path+"?v="+Date.now(),{cache:"no-store",signal:AbortSignal.timeout(12000)});if(!res.ok)throw Error("HTTP "+res.status);return res.json()}
function add(parent,tag,content,cls){const el=document.createElement(tag);if(cls)el.className=cls;el.textContent=content;parent.appendChild(el);return el}
function render(result,errors=[]){const host=document.getElementById("agentSourceStatus");if(!host)return;host.replaceChildren();
 add(host,"p","臺灣日期："+result.today+"｜下列六項是規則式代理使用的資料來源，不代表各自完成了新的 LLM 推論。","sf-intro");
 const grid=add(host,"div","","sf-grid");
 for(const item of result.rows.concat([result.model])){const box=add(grid,"article","","sf-item");
  add(box,"strong",item.name+"｜"+item.source,"sf-name");add(box,"span",item.state,"sf-state "+item.tone);
  add(box,"p",item.detail,"sf-detail");}
 if(errors.length)add(host,"p","無法讀取來源："+errors.join("、")+"。缺值不代表來源已更新。","sf-error");
}
async function loadAndRender(){const names=["daily","orion","social","llm"],paths=["./data/latest.json","./data/orion_news/latest.json","./data/social_sentiment/latest.json","./data/agent_llm/latest.json"];
 const results=await Promise.allSettled(paths.map(json)),source={},errors=[];
 results.forEach((x,i)=>{source[names[i]]=x.status==="fulfilled"?x.value:{};if(x.status!=="fulfilled")errors.push(names[i]);});
 render(build(source,new Date()),errors);
}
return {build,render,loadAndRender,dateTW,fullTW,recent,ROLES};
});
