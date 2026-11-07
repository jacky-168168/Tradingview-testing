/* NOVA 個股進場研究報告畫面；只讀資料，價位試算僅留在本頁記憶體。 */
(function(){"use strict";
const $=id=>document.getElementById(id),drafts=new Map();
function add(host,tag,value,cls){const x=document.createElement(tag);if(value!==null&&value!==undefined)x.textContent=String(value);if(cls)x.className=cls;host.appendChild(x);return x}
function price(v){return typeof v==="number"&&Number.isFinite(v)?v.toFixed(2):"未提供"}
function render(candidate,report){
 const body=$("entryReport"),manual=$("entryManualPlan");if(!body||!manual||!window.SixAgentEntryDecision)return;
 body.replaceChildren();manual.replaceChildren();
 const result=window.SixAgentEntryDecision.evaluate(candidate,report);
 const title=add(body,"div",null,"entry-decision-top");
 add(title,"strong","NOVA｜個股進場決策報告");
 add(title,"span",result.status,"flag "+(candidate.agents.titan.hardVeto?"no":"warn"));
 add(body,"p","符合 "+result.passed+"／"+result.total+" 項可觀測條件｜資料日："+(result.reference.asOfDate||"未知")+
  "｜"+(result.reference.live?"盤中研究快照":"歷史資料；不能當即時買進訊號"),"description");
 add(body,"p",result.trigger,"entry-trigger");
 const refs=add(body,"div",null,"entry-levels");
 for(const [label,val] of [["行情參考價",result.reference.price],["G 前3日高點",result.reference.prior3High],["G 前18日高點",result.reference.prior18High]]){
  const cell=add(refs,"div",null,"entry-level");add(cell,"span",label,"small");add(cell,"strong",price(val));
 }
 const items=add(body,"div",null,"entry-checks");
 for(const check of result.checks){
  const item=add(items,"div",null,"entry-check");
  add(item,"span",check.state,"entry-check-tag "+(check.state==="符合"?"good":check.state==="缺資料"?"missing":"bad"));
  const desc=add(item,"div");add(desc,"strong",check.title);add(desc,"p",check.detail,"small");
 }
 const argumentsRow=add(body,"div",null,"entry-arguments");
 for(const [title,lines] of [["支持進場研究的依據",result.support],["反對或待確認的理由",result.caution]]){
  const section=add(argumentsRow,"section");add(section,"h4",title);
  const ul=add(section,"ul");for(const line of lines)add(ul,"li",line);
 }
 add(body,"p","系統未生成自動買進區間、停損或目標價，也不根據條件數推估勝率；TITAN 否決不可被模型或自填價位解除。","description");
 add(manual,"h3","自訂價位情境｜風報比試算");
 add(manual,"p","請根據自己核對過的 K 線與支撐阻力填入。這不是 NOVA 推薦價，也不會儲存、提交或送出訂單。","description");
 const key=candidate.code+"|"+(candidate.asOfDate||"")+"|"+(report?.liveVerified?"live":"historical");
 const state=drafts.get(key)||{buyLow:"",buyHigh:"",stop:"",target:""};
 const fields=add(manual,"div",null,"entry-inputs");
 const labels=[["buyLow","買進區間下緣"],["buyHigh","買進區間上緣"],["stop","停損失效價"],["target","目標價"]];
 const resultNode=add(manual,"p",null,"entry-result");
 const note=add(manual,"p",null,"description");
 function update(){
  const p=window.SixAgentEntryDecision.manualPlan(state);
  resultNode.textContent=p.status==="calculated"?"試算風報比 "+p.rr+" : 1｜每股風險 "+price(p.risk)+"｜每股潛在報酬 "+price(p.reward):"風報比：尚無有效試算";
  resultNode.className="entry-result "+(p.status==="invalid"?"invalid":"");
  note.textContent=p.message+"｜不含費用、滑價與跳空風險；不論結果如何均非交易許可。";
 }
 for(const [field,label] of labels){
  const wrap=add(fields,"label",null,"entry-input");
  add(wrap,"span",label,"small");
  const input=add(wrap,"input");input.type="number";input.min="0";input.step="any";input.inputMode="decimal";
  input.placeholder="自行輸入";input.value=state[field]||"";input.setAttribute("aria-label",label);
  input.addEventListener("input",()=>{state[field]=input.value;drafts.set(key,state);update()});
 }
 update();
}
window.SixAgentEntryUI={render};
})();
