/* Verified GitHub Models research snapshot viewer; never presents text as live stock advice. */
(function(){"use strict";
const $=id=>document.getElementById(id),ROLE=["ATLAS","VEGA","ORION","LUNA","TITAN","NOVA"];
function node(tag,text,css){const n=document.createElement(tag);if(text!=null)n.textContent=String(text);if(css)n.className=css;return n}
function card(where,role,data,heading){
 const box=node("article",null,"agent"+(role==="TITAN"?" deny":role==="NOVA"?" final":""));
 box.append(node("h3",role+"｜"+heading));
 box.append(node("p",data.assessment));
 box.append(node("p","信心水準："+data.confidence+"；資料依據："+data.evidenceRefs.join("、"),"hint"));
 for(const u of data.uncertainties)box.append(node("p","待確認："+u,"hint"));
 where.append(box);
}
function assertReport(j){
 if(!j||j.schema!==1||j.provider!=="GitHub Models"||j.verifiedModelExecution!==true||j.inferenceCalls!==9||j.noTrade!==true)throw Error("未完成真實 LLM 驗證");
 if(!j.rounds||!j.rounds.initial||!j.rounds.critiques||!j.rounds.final)throw Error("交叉質疑報告不完整");
 for(const role of ROLE.slice(0,5)){if(j.rounds.initial[role]?.role!==role)throw Error("獨立角色缺失 "+role)}
 if(j.rounds.draft?.role!=="NOVA"||j.rounds.final?.role!=="NOVA"||j.rounds.critiques.TITAN?.role!=="TITAN"||
  j.rounds.critiques.VEGA?.role!=="VEGA")throw Error("風控質疑或最終角色缺失");
 const ts=Date.parse(j.generatedAt),now=Date.now();
 if(!Number.isFinite(ts)||ts>now+60000)throw Error("模型報告時間無效");
 return (now-ts)/3600000;
}
async function load(){
 const host=$("llmDebate"),flag=$("llmState"),info=$("llmMeta");
 if(!host)return;
 host.replaceChildren();flag.textContent="核對中…";info.textContent="正在讀取 GitHub Models 研究快照…";
 try{
  const response=await fetch("./data/agent_llm/latest.json?v="+Date.now(),{cache:"no-store",signal:AbortSignal.timeout(12000)});
  if(!response.ok)throw Error("報告尚未發布（HTTP "+response.status+"）");
  const doc=await response.json(),hours=assertReport(doc);
  const historical=hours>26||!doc.inputIsLive;
  flag.textContent=hours>26?"歷史報告（已過期）":historical?"歷史研究":"模型討論快照";
  info.textContent="模型："+doc.model+"｜推論呼叫："+doc.inferenceCalls+" 次｜產出："+doc.generatedAt+
   "｜來源日："+(doc.evidenceDate||"缺值")+"｜"+doc.marketMode+"｜"+doc.outcome+
   "。此為 AI 研究觀點，逐條事實尚未經人工覆核；不是買賣建議。";
  for(const role of ROLE.slice(0,5))card(host,role,doc.rounds.initial[role],"第一輪獨立觀點");
  card(host,"NOVA",doc.rounds.draft,"第一輪彙整");
  card(host,"VEGA",doc.rounds.critiques.VEGA,"交叉質疑");
  card(host,"TITAN",doc.rounds.critiques.TITAN,"風控反駁");
  card(host,"NOVA",doc.rounds.final,"最終研究結論（不可下單）");
 }catch(e){
  flag.textContent="LLM 未驗證／暫不可用";
  info.textContent="目前沒有可確認的九次模型討論紀錄；"+String(e.message)+
    "。六角色規則式研究仍可使用，不會將它偽裝成 LLM 分析。";
 }
}
$("refresh")?.addEventListener("click",()=>{void load()});
void load();
})();
