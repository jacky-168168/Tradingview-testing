/* 個股進場研究決策（唯讀）。只使用既有六代理與 G 的可驗證欄位；不推導虛構進出場價。 */
(function(root,factory){"use strict";const api=factory();if(typeof module!=="undefined"&&module.exports)module.exports=api;else root.SixAgentEntryDecision=api;})(typeof globalThis==="object"?globalThis:this,function(){"use strict";
function num(x){return typeof x==="number"&&Number.isFinite(x)?x:null;}
function evaluate(candidate,report){
 const c=candidate||{},a=c.agents||{},at=a.atlas||{},ve=a.vega||{},or=a.orion||{},lu=a.luna||{},ti=a.titan||{},nv=a.nova||{};
 const checks=[];
 function check(title,passed,missing,detail){checks.push({title,state:missing?"缺資料":passed?"符合":"未符合",detail});}
 const risk=num(report?.source?.riskScore),live=report?.liveVerified===true&&report?.source?.gQuality?.ok===true;
 check("盤中資料可驗證",live,false,live?"正式品質閘門通過（盤中暫估，非收盤確認）":"非有效即時盤中快照；僅能回顧");
 check("TITAN 風控通過",ti.hardVeto===false,typeof ti.hardVeto!=="boolean","大盤風險 "+(risk===null?"缺值":risk)+"／100"+(ti.veto?.length?"；"+ti.veto.join("；"):""));
 check("RS20 相對強勢",num(at.rs20)!==null&&at.rs20>0,num(at.rs20)===null,"RS20："+(num(at.rs20)===null?"缺值":at.rs20));
 const rvol=num(at.rvol),turnover=num(at.turnoverB);
 check("量能與流動性",rvol!==null&&rvol>=1.5&&turnover!==null&&turnover>=.5,rvol===null||turnover===null,"RVOL "+(rvol??"缺值")+"；成交額 "+(turnover??"缺值")+" 億");
 const slope=num(ve.slope),atr=num(ve.atrPct);
 check("技術方向與波動",slope!==null&&slope>0&&atr!==null&&atr<=12,slope===null||atr===null,"MA20 斜率 "+(slope??"缺值")+"%；ATR "+(atr??"缺值")+"%");
 const price=num(c.price),prior3=num(c.referenceLevels?.prior3High),prior18=num(c.referenceLevels?.prior18High);
 const break3=c.referenceLevels?.break3,observed=price!==null&&prior3!==null&&price>prior3&&break3===true;
 check("G 前3日高點突破觀察",observed,price===null||prior3===null||typeof break3!=="boolean","觀察價 "+(price??"缺值")+"；前3日高點 "+(prior3??"缺值")+"；G 旗標 "+(typeof break3==="boolean"?(break3?"成立":"未成立"):"缺值")+"（盤中不等於收盤確認）");
 const passed=checks.filter(x=>x.state==="符合").length,hardVeto=ti.hardVeto!==false;
 const status=hardVeto?"風險否決":checks.every(x=>x.state==="符合")?"研究條件符合，仍需人工確認":"等待進場條件確認";
 const support=[],caution=[];
 if(num(at.rs20)!==null&&at.rs20>0)support.push("ATLAS：RS20 正值，具相對強度證據。");
 if(rvol!==null&&rvol>=1.5)support.push("ATLAS：量比達 1.5，量能較近期基準放大。");
 if(slope!==null&&slope>0)support.push("VEGA：MA20 斜率為正。");
 if(observed)support.push("VEGA／G：觀察價格超過前3日高點，尚待收盤確認。");
 if(!support.length)support.push("目前沒有足夠量價與技術支持證據。");
 if(ti.veto?.length)caution.push("TITAN："+ti.veto.join("；"));
 if(!live)caution.push("資料不是已驗證的即時盤中報價，不能當作今日進場訊號。");
 if(!observed)caution.push("VEGA：尚無可核實的前3日高點突破確認。");
 if(or.verifiedCount===0)caution.push("ORION：沒有可確認的個股第一手消息；媒體關聯不代表利多。");
 if(lu.overheatWatch===true)caution.push("LUNA：社群討論過熱，須留意追高風險。");
 if(nv.status==="等待確認")caution.push("NOVA：整體研究仍有缺口。");
 caution.push("尚無經確認的支撐失效點與獨立目標價；不得由 ATR 或百分比任意推算。");
 return {status,passed,total:checks.length,checks,reference:{price,prior3High:prior3,prior18High:prior18,asOfDate:c.asOfDate||null,live},
  trigger:prior3===null?"G 前3日突破參考價缺失，請先確認原始 K 線。":
   "觀察條件：價格高於 G 前3日高點 "+prior3+"，且以選定週期收盤確認；目前"+(observed?"已有盤中突破觀察，但未有收盤確認證據。":"尚未具備可驗證突破證據。"),
  support,caution,noTrade:true,pricePlan:{buyLow:null,buyHigh:null,stop:null,target:null,rr:null,source:"無足夠來源自動生成合理買進區、失效價或目標價。"}};
}
function manualPlan(input){
 const fields=["buyLow","buyHigh","stop","target"],out={noTrade:true,origin:"使用者自行填入的試算情境；非 AI 估價或交易訊號"};
 const prices={};
 for(const k of fields){const raw=input?.[k];if(raw===null||raw===undefined||String(raw).trim()==="")return {...out,status:"incomplete",message:"填寫買進區間上下緣、停損失效價與目標價，才能計算試算風報比。",rr:null};
  const v=Number(raw);if(!Number.isFinite(v)||v<=0)return {...out,status:"invalid",message:"價位必須是大於零的有效數字。",rr:null};
  prices[k]=v;
 }
 if(prices.buyLow>prices.buyHigh)return {...out,status:"invalid",message:"買進區間下緣不可高於上緣。",rr:null};
 if(prices.stop>=prices.buyLow)return {...out,status:"invalid",message:"只做多的試算：停損價必須低於買進區間下緣。",rr:null};
 if(prices.target<=prices.buyHigh)return {...out,status:"invalid",message:"只做多的試算：目標價必須高於買進區間上緣。",rr:null};
 const risk=prices.buyHigh-prices.stop,reward=prices.target-prices.buyHigh,rr=reward/risk;
 return {...out,status:"calculated",message:"以買進區間上緣作保守成本計算；未扣手續費、稅、滑價，亦未證明目標或停損有效。",prices,risk,reward,rr:Number(rr.toFixed(2))};
}
return {evaluate,manualPlan};
});
