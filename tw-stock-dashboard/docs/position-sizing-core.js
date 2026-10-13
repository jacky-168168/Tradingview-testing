/* Stock & ETF risk-budget dashboard. Educational, uncalibrated, no broker orders or proprietary ARK formula. */
(function(scope){
"use strict";
const num=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))?Number(v):null;
const clamp=(x,a,b)=>Math.max(a,Math.min(x,b)),cash=v=>Number.isFinite(v)?Math.round(v):0;
const TYPES={
 "stock":{name:"一般股票",cap:.08,risk:.005,stress:.12,atrMult:2.5},
 "broad-etf":{name:"廣泛分散 ETF",cap:.15,risk:.006,stress:.08,atrMult:2.2},
 "sector-etf":{name:"產業／高集中 ETF",cap:.10,risk:.0045,stress:.12,atrMult:2.5},
 "leveraged-etf":{name:"正 2／槓桿 ETF",cap:.04,risk:.003,stress:.20,atrMult:3}
};
const GROUPS={"technology":"科技／半導體","dividend":"高股息","finance":"金融","market":"廣泛市場","other":"其他／未知"};
const ETF={
 "0052":{name:"富邦科技",type:"sector-etf",group:"technology"},
 "0056":{name:"元大高股息",type:"sector-etf",group:"dividend"},
 "00675L":{name:"富邦臺灣加權正2",type:"leveraged-etf",group:"market"},
 "00631L":{name:"元大台灣50正2",type:"leveraged-etf",group:"market"},
 "00670L":{name:"富邦NASDAQ正2",type:"leveraged-etf",group:"technology"},
 "00909":{name:"國泰數位支付服務",type:"sector-etf",group:"technology"},
 "0050":{name:"元大台灣50",type:"broad-etf",group:"market"},
 "006208":{name:"富邦台50",type:"broad-etf",group:"market"},
 "00646":{name:"元大S&P500",type:"broad-etf",group:"market"},
 "VT":{name:"Vanguard Total World",type:"broad-etf",group:"market"},
 "QQQ":{name:"Invesco QQQ",type:"sector-etf",group:"technology"}
};
function normalizeSymbol(v){return String(v||"").trim().toUpperCase().replace(/^(TWSE|TPEX|TWO):/,"")}
function guessGroup(x){
 if(!x||typeof x!=="object")return "other";
 const raw=[x.theme,x.industry,x.subIndustry].filter(Boolean).join(" ").toLowerCase();
 if(/半導體|cpo|光通訊|科技|ic|伺服器|記憶體|電子|pcb|被動|電機電子|光電|ai|通信|網通/.test(raw))return "technology";
 if(/金融|保險|銀行|證券/.test(raw))return "finance";
 return "other";
}
function parseSeries(raw,price){
 const lines=String(raw||"").trim().split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
 const vals=[];let dated=false,prev="";
 for(const line of lines){
  const cells=line.split(/[,;\t]/).map(x=>x.trim());
  let val=null;
  if(/^\d{4}[-/]\d{2}[-/]\d{2}$/.test(cells[0]||"")){
   const day=cells[0].replace(/\//g,"-");
   if(prev && day<=prev)throw Error("歷史收盤日期需由舊到新、不可重複");
   prev=day;dated=true;val=num(cells[1]);
  }else if(cells.length===1)val=num(cells[0]);
  else throw Error("請使用一行一個收盤價，或 YYYY-MM-DD,收盤價");
  if(val===null||val<=0||val>1e7)throw Error("歷史收盤價格需要正數");
  vals.push(val);
 }
 if(vals.length<60)return {ready:false,count:vals.length,reason:"至少需要 60 筆依時間排列的每日收盤價，才能計算技術位階。"};
 if(dated&&!/^\d{4}-\d\d-\d\d$/.test(prev))throw Error("日期格式錯誤");
 const ref=num(price),close=ref!==null&&ref>0?ref:vals.at(-1),sample=vals.slice(-60);
 // Reference prices use preceding 60 closes only; current price is evaluated against that distribution.
 const mean=sample.reduce((a,b)=>a+b,0)/sample.length;
 const sd=Math.sqrt(sample.reduce((a,b)=>a+(b-mean)**2,0)/sample.length);
 if(sd<1e-9)return {ready:false,count:vals.length,reason:"60日收盤價沒有波動，無法建立 Z-score。"};
 const z=(close-mean)/sd;
 let zone=z<=-1?"value":z<.7?"normal":z<1.5?"warm":"hot";
 return {ready:true,count:vals.length,dated,lastDay:dated?prev:null,mean,sd,z,close,zone,label:{value:"相對低位",normal:"一般位階",warm:"升溫區",hot:"高位階"}[zone],note:"以60日收盤均值與標準差計算價格 Z-score；非基本面合理價值或方舟原始訊號。"};
}
function size(input,market){
 const f=input||{},capital=num(f.capital),price=num(f.price),positions=Array.isArray(f.positions)?f.positions:[],unknownHeld=num(f.otherHeld)||0;
 const fail=why=>({valid:false,reason:why});
 if(capital===null||capital<=0||capital>1e11)return fail("總資金需填入大於 0 的有效金額");
 if(price===null||price<=0||price>1e7)return fail("目前股價需填入大於 0 的有效價格");
 const code=normalizeSymbol(f.code),base=ETF[code]||{},kind=TYPES[f.type]?f.type:base.type||"stock",group=GROUPS[f.group]?f.group:base.group||"other";
 const spec=TYPES[kind],holdings=positions.map(p=>({code:normalizeSymbol(p.code),type:TYPES[p.type]?p.type:ETF[normalizeSymbol(p.code)]?.type||"stock",group:GROUPS[p.group]?p.group:ETF[normalizeSymbol(p.code)]?.group||"other",value:Math.max(0,num(p.value)||0)}));
 const invested=holdings.reduce((a,b)=>a+b.value,0)+Math.max(0,unknownHeld),present=holdings.filter(x=>x.code===code).reduce((a,b)=>a+b.value,0);
 const sectorHeld=holdings.filter(x=>x.group===group).reduce((a,b)=>a+b.value,0),leverHeld=holdings.filter(x=>x.type==="leveraged-etf").reduce((a,b)=>a+b.value,0);
 const targetPct=market?.valid?num(market.target):null;
 const targetCap=targetPct===null?null:capital*clamp(targetPct,0,100)/100;
 const marketLeft=targetCap===null?0:Math.max(0,targetCap-invested);
 const classCap=capital*spec.cap;
 // Overlap is a conservative grouping proxy, NOT constituent-level ETF correlation.
 const sectorCap=capital*(group==="technology"?.25:group==="market"?.65:group==="other"?.25:.22);
 const sectorLeft=Math.max(0,sectorCap-sectorHeld);
 const leverLeft=kind==="leveraged-etf"?Math.max(0,capital*.07-leverHeld):Infinity;
 const atr=num(f.atrPct);
 const stressPct=Math.min(1,Math.max(spec.stress,atr!==null&&atr>0?atr/100*spec.atrMult:spec.stress));
 const riskMoney=capital*spec.risk;
 const riskCap=Math.max(0,riskMoney/stressPct-present);
 const caps={market:marketLeft,class:Math.max(0,classCap-present),sector:sectorLeft,leverage:leverLeft,risk:riskCap};
 const limit=cash(Math.max(0,Math.min(...Object.values(caps))));
 const zone=f.zone||"unknown",zonePct={value:.35,normal:.2,warm:.1,hot:0,unknown:.15}[zone]??.15;
 const signal=String(f.signal||"none"),signalPct=signal==="ss"?.35:signal==="bottom"?.25:signal==="manual"?.2:0;
 const pct=Math.min(zonePct,signalPct,kind==="leveraged-etf"?.2:1);
 const firstPotential=cash(limit*pct);
 const dataStale=market?.valid!==true||market.stale===true;
 const riskOff=num(market?.risk)!==null&&Number(market.risk)<60;
 const confirmed=f.entryConfirmed===true;
 const reasons=[];
 if(targetPct===null)reasons.push("大盤水位尚未建立");
 if(dataStale)reasons.push("正式大盤資料過期或不足");
 if(riskOff)reasons.push("原始 Risk Score 低於 60；一般新倉不開放");
 if(!/^[A-Z0-9]{2,12}$/.test(code))reasons.push("股票／ETF 代碼未填或格式不正確");
 if(signal==="none")reasons.push("尚未確認 Bottom／SS Bottom 或其他入場條件");
 if(!confirmed)reasons.push("未完成個股進場檢核");
 if(kind==="leveraged-etf")reasons.push("正2部位風險可能超過投入本金比例，需另評估槓桿與隔夜缺口");
 if(!Number.isFinite(limit)||limit<=0)reasons.push("沒有可配置額度（總水位、單檔、族群、槓桿或風險上限）");
 // Simulated entry orders require ALL gates. Show potential for study, never as executable order.
 const canBuy=market?.valid===true&&!dataStale&&!riskOff&&confirmed&&signal!=="none"&&/^[A-Z0-9]{2,12}$/.test(code)&&limit>0&&firstPotential>=price;
 const first=canBuy?Math.floor(firstPotential/price)*price:0;
 const firstShares=canBuy?Math.floor(firstPotential/price):0;
 const remaining=Math.max(0,limit-first),maxShares=Math.floor(limit/price);
 const riskAtMax=limit*stressPct;
 const rest=1-pct,ladderWeights=pct>0?[pct,rest*.4,rest*.35,rest*.25]:[.25,.25,.25,.25],ladder=ladderWeights.map((fraction,i)=>{
  const budget=cash(limit*fraction),drop=atr!==null&&atr>0?Math.max(2,Math.min(8,atr*1.1)):kind==="leveraged-etf"?7:4;
  return {step:i+1,referencePrice:Math.max(.01,price*Math.pow(1-drop/100,i)),budget,purpose:i===0?"首次進場":i===1?"二批候補":i===2?"三批候補":"末批備援",trigger:i===0?"必須先有交易訊號":"必須有新 Bottom 訊號且跌幅達門檻",dropPct:drop};
 });
 const grossEffective=holdings.reduce((t,h)=>t+h.value*(h.type==="leveraged-etf"?2:1),0)+unknownHeld;
 const warnings=[];
 if(sectorHeld>capital*.2&&group!=="market")warnings.push("同族群部位已高，需留意 ETF 與個股重複持股。");
 if(leverHeld>0)warnings.push("現有正2 ETF 以名目約 2 倍估計曝險，非精確追蹤或實際 VaR。");
 if(unknownHeld>0)warnings.push("另計的未分類持股不分配至各族群，可能低估集中度。");
 if(!f.historyValidated)warnings.push("未提供足夠歷史收盤資料，無法核實 ETF 價值／升溫位階。");
 if(!f.priceDate)warnings.push("參考股價日期未填，請先核實是否為最新完整交易日。");
 if(price && f.priceDate && market?.date && f.priceDate!==market.date)warnings.push("參考股價日期和大盤資料日不同，股數僅供情境試算。");
 return {valid:true,code,kind,group,capital,price,invested,present,sectorHeld,leverHeld,grossEffective,marketPct:targetPct,marketMax:targetCap,marketLeft,caps,limit,stressPct,riskMoney,riskAtMax,maxShares,zone,zonePct,signalPct,pct,firstPotential,first,firstShares,remaining,canBuy,blocked:reasons,ladder,warnings,concentration:invested/capital,groupPct:sectorHeld/capital,unknownHeld};
}
const api={TYPES,GROUPS,ETF,normalizeSymbol,guessGroup,parseSeries,size};
scope.PositionSizingCore=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof window!=="undefined"?window:typeof globalThis!=="undefined"?globalThis:{});
