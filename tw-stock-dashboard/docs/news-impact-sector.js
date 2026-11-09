/*
 * Deterministic sector + observed-market-reaction layer.
 * A reported asset price move is NOT a forecast. Broad index effects must not
 * be inferred from one component/industry price quote.
 * These are hypotheses, not fitted empirical probabilities.
 */
(function(root,factory){
"use strict";
const api=factory();
if(typeof module==="object"&&module.exports)module.exports=api;
if(root)root.NewsImpactSector=api;
})(typeof window!=="undefined"?window:(typeof globalThis!=="undefined"?globalThis:null),function(){
"use strict";
function examine(item){
 const title=String(item&&item.title||"");
 const rules=[],observations=[];
 const memory=/\b(?:DRAM|DDR[345]|HBM|NAND(?:\s+FLASH)?)\b|記憶體/i.test(title);
 const priced=/(?:報價|均價|現貨價|合約價|市場價格|晶片價格)|\b(?:spot price|contract price|chip prices?)\b/i.test(title);
 const falling=/(?:報價|均價|現貨價|合約價|價格).{0,45}(?:下跌|跌幅|走低|下降|回落|下滑|重挫)|(?:下跌|走低|下降|回落|下滑).{0,20}(?:報價|均價|現貨價|合約價|價格)|\b(?:prices?|quotes?).{0,22}\b(?:fall|falls|fell|drop|decline|slide|lower)\b/i.test(title);
 const rising=/(?:報價|均價|現貨價|合約價|價格).{0,45}(?:上漲|漲幅|走高|上升|回升|攀升)|(?:上漲|走高|上升|回升).{0,20}(?:報價|均價|現貨價|合約價|價格)|\b(?:prices?|quotes?).{0,22}\b(?:rise|rises|rose|jump|increase|higher)\b/i.test(title);
 const uncertain=/傳聞|據傳|可能|恐|預計|或將|\b(?:rumor|may|might|could|expected|forecast)\b/i.test(title);
 if(memory&&priced&&!uncertain&&falling!==rising){
  const down=falling;
  rules.push({
   id:down?"memory-price-down":"memory-price-up",
   name:down?"記憶體報價下跌":"記憶體報價上漲",
   impact:{"台股記憶體供應端":down?-35:35},
   why:down
    ?"DRAM／記憶體報價下跌，對記憶體供應商的平均售價與毛利屬條件式逆風；採購端則可能受惠。"
    :"DRAM／記憶體報價上漲，對記憶體供應商的平均售價可能有利，但採購端成本可能增加。",
   caveat:"單次報價不代表季度合約價或股價；須查核現貨／合約、庫存、公司產品組合與價格趨勢。此訊號不外推至台股大盤。",
   scope:"產業"
  });
 }else if(memory&&priced&&falling&&rising){
  rules.push({id:"memory-price-mixed",name:"記憶體報價方向衝突",impact:{},why:"標題同時包含上漲及下跌資訊，無法直接判定供應端方向。",caveat:"須拆分品項、日期與價格資料。",scope:"產業"});
 }
 const isNZD=/\b(?:new zealand dollar|NZD(?:\/USD)?|kiwi dollar)\b|紐元|紐幣/i.test(title);
 const nzdUp=/\b(?:advances?|rises?|gains?|strengthens?|climbs?|rebounds?)\b|走強|上漲|回升/i.test(title);
 const nzdDown=/\b(?:falls?|declines?|drops?|weakens?|slides?)\b|走弱|下跌|回落/i.test(title);
 const isElection=/\b(?:election|ruling party|coalition|vote count)\b|選舉|執政|選情|組閣/i.test(title);
 if(isNZD&&isElection){
  rules.push({
   id:"nzd-election",name:"紐西蘭選舉與紐元反應",
   impact:{},
   why:"標題描述紐西蘭選情與匯價變動；這是新聞已報導的匯市反應，而非預測其後價格。",
   caveat:"正式開票、聯合執政、紐西蘭央行利率和美元走勢都可能改變後續方向。",
   scope:"匯市／政治"
  });
  if(nzdUp!==nzdDown)observations.push({asset:"紐元NZD",label:nzdUp?"新聞稱已走強":"新聞稱已走弱"});
 }
 const israel=/\b(?:israel(?:'s|’s)? president|israeli president|eisenkot)\b/i.test(title);
 const form=/\b(?:form (?:the )?(?:next )?government|forming (?:the )?(?:next )?government|form a government|coalition talks?|tasked with forming)\b/i.test(title);
 if(israel&&form){
  rules.push({
   id:"israel-coalition",name:"以色列組閣／政治過渡",
   impact:{},
   why:"組閣授權屬政治進程，不能直接等同停火、戰爭升級、油氣供應中斷或油價風險溢價改變。",
   caveat:"須查核聯合政府是否成立、實際國防／外交政策及波斯灣供應與航運變化。",
   scope:"地緣政治"
  });
 }
 return {rules,observations};
}
return {examine};
});