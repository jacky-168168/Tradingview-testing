/* Taiwan index capital-water backtest. Uses verified historical closes, NOT investable total-return ETF. 
 * Signal at day D close -> rebalance at D+1 CLOSE. No same-bar fill or unknown future data.
 * This file supports Node unit tests and static GitHub Pages. No dependencies. */
(function(root){
"use strict";
const finite=x=>x!==null&&x!==""&&Number.isFinite(Number(x))?Number(x):null;
const clamp=(x,a,b)=>Math.min(b,Math.max(a,x));
const DEFAULT_COST={buy:0.002425,sell:0.003425}; // 0.1425% commission each way + 0.10% slip each way + 0.10% sell ETF tax
const BASE_BREAKS=[2,5,10,15],BASE_LEVELS=[30,40,50,65,80];
function mergeSeries(base,extra=[]){
 if(!Array.isArray(base)||!Array.isArray(extra))throw Error("Market history must be arrays");
 const byDate=new Map();for(const a of [...base,...extra]){
  const date=String(a?.date??""),price=finite(a?.index);
  if(!/^\d{4}-\d\d-\d\d$/.test(date)||price===null||price<=0)continue;
  byDate.set(date,{date,index:price,score:finite(a.score),ma20:finite(a.ma20),topState:String(a.topState||"")});
 }
 const rows=[...byDate.values()].sort((a,b)=>a.date.localeCompare(b.date));
 if(rows.length<130)throw Error("Need at least 130 completed market days (120-day warmup)");
 for(let i=1;i<rows.length;i++)if(rows[i].date<=rows[i-1].date)throw Error("Duplicate or unordered date");
 return rows;
}
const SPECS={
 buy_hold:{label:"加權指數滿倉（100%）",type:"fixed",fixed:100},
 fixed_60:{label:"固定60%股票／40%現金",type:"fixed",fixed:60},
 fixed_40:{label:"固定40%股票／60%現金",type:"fixed",fixed:40},
 original_v2:{label:"目前V2：120日逆向水位",type:"step",window:120,breaks:BASE_BREAKS,levels:BASE_LEVELS,maCap:25,maGap:7},
 original_gate:{label:"目前V2＋Risk<60不加倉",type:"step",window:120,breaks:BASE_BREAKS,levels:BASE_LEVELS,maCap:25,maGap:7,riskGate:true},
 original_no_ma:{label:"目前V2（不加MA過熱限額）",type:"step",window:120,breaks:BASE_BREAKS,levels:BASE_LEVELS},
 conservative:{label:"逆向保守：20/30/45/60/75%",type:"step",window:120,breaks:BASE_BREAKS,levels:[20,30,45,60,75],maCap:20,maGap:7},
 aggressive:{label:"逆向積極：40/50/60/75/90%",type:"step",window:120,breaks:BASE_BREAKS,levels:[40,50,60,75,90],maCap:30,maGap:7},
 wider_breaks:{label:"逆向較寬門檻：3/7/12/20%",type:"step",window:120,breaks:[3,7,12,20],levels:BASE_LEVELS,maCap:25,maGap:7},
 short_60:{label:"逆向60日高點（較短週期）",type:"step",window:60,breaks:BASE_BREAKS,levels:BASE_LEVELS,maCap:25,maGap:7},
 long_250:{label:"逆向250日高點（較長週期）",type:"step",window:250,breaks:BASE_BREAKS,levels:BASE_LEVELS,maCap:25,maGap:7},
 };
function targetAt(rows,signalIndex,model){
 const spec=typeof model==="string"?SPECS[model]:model;
 if(!spec)throw Error("Unknown model "+String(model));
 if(spec.type==="fixed")return {target:spec.fixed,drawdown:null,maGap:null,raw:spec.fixed,cap:false,score:null};
 const w=Number(spec.window||120),end=signalIndex;
 if(!Number.isInteger(end)||end-w+1<0)return null;
 const date=rows[end],price=date.index;
 let high=-Infinity;
 for(let j=end-w+1;j<=end;j++)high=Math.max(high,rows[j].index);
 if(!(high>0))return null;
 const dd=clamp((high-price)/high*100,0,100),breaks=spec.breaks,levels=spec.levels;
 let n=0;while(n<breaks.length&&dd>=breaks[n])n++;
 const raw=levels[n],gap=date.ma20>0?(price/date.ma20-1)*100:null;
 const cap=Number.isFinite(spec.maGap)&&gap!==null&&gap>=spec.maGap;
 const target=cap?Math.min(raw,spec.maCap):raw;
 return {target,drawdown:dd,maGap:gap,raw,cap,score:date.score};
}
function simulate(rows,model,params={}){
 const spec=typeof model==="string"?SPECS[model]:model;
 if(!spec)throw Error("Unknown simulation");
 const start=String(params.start||"2024-04-15"),end=String(params.end||rows.at(-1).date),band=Number.isFinite(params.band)?params.band:0.05;
 const buyFee=Number.isFinite(params.buyFee)?params.buyFee:DEFAULT_COST.buy,sellFee=Number.isFinite(params.sellFee)?params.sellFee:DEFAULT_COST.sell;
 let cash=Number(params.initialCapital||1000000),stock=0,peak=cash,drawdown=0,count=0,turnover=0,cost=0,days=0,expo=0,returns=[],series=[],lastPrice=null;
 let prevEquity=cash,firstDate=null,signalMisses=0;
 for(let i=0;i<rows.length;i++){
  const day=rows[i];if(day.date<start||day.date>end)continue;
  const s=targetAt(rows,i-1,spec);
  if(!s){signalMisses++;continue}
  const price=day.index;
  // From yesterday's close to today's close: OLD position earns today's return.
  if(lastPrice!==null)stock*=price/lastPrice;
  const gross=cash+stock;
  let target=s.target/100;
  const oldExp=gross>0?stock/gross:0;
  const prev=rows[i-1],gate=spec.riskGate && (prev.score===null||prev.score<60||/Strong Top Reversal|Top Reversal Attempt/.test(prev.topState));
  if(gate)target=Math.min(target,oldExp);
  let action="hold",notional=0,dayCost=0;
  if(Math.abs(target-oldExp)>=band){
   let wanted=gross*target-stock;
   if(wanted>0){
    const amount=Math.min(wanted,cash/(1+buyFee));
    if(amount>0){stock+=amount;cash-=amount*(1+buyFee);dayCost=amount*buyFee;notional=amount;action="buy"}
   }else if(wanted<0){
    const amount=Math.min(-wanted,stock);if(amount>0){stock-=amount;cash+=amount*(1-sellFee);dayCost=amount*sellFee;notional=amount;action="sell"}
   }
   if(notional>0){count++;turnover+=notional;cost+=dayCost}
  }
  const equity=stock+cash;
  peak=Math.max(peak,equity);drawdown=Math.max(drawdown,(peak-equity)/peak);
  if(days>0)returns.push(equity/prevEquity-1);days++;expo+=equity?stock/equity:0;
  if(!firstDate)firstDate=day.date;
  series.push({date:day.date,index:price,equity:Math.round(equity),stock:Math.round(stock),cash:Math.round(cash),allocation:Math.round((stock/equity||0)*1000)/10,target:s.target,signalDrawdown:s.drawdown===null?null:Math.round(s.drawdown*100)/100,signalScore:s.score,gate:!!gate,action,fees:Math.round(dayCost)});
  lastPrice=price;prevEquity=equity;
 }
 const last=series.at(-1),initial=Number(params.initialCapital||1000000);
 const annual=days>=30?(Math.pow(last.equity/initial,252/Math.max(1,days-1))-1)*100:null,profit=(last.equity/initial-1)*100;
 const mean=returns.reduce((a,b)=>a+b,0)/Math.max(1,returns.length);
 const dev=Math.sqrt(returns.reduce((a,b)=>a+(b-mean)**2,0)/Math.max(1,returns.length));
 const sharpe=dev>0?mean/dev*Math.sqrt(252):null;
 return {id:typeof model==="string"?model:spec.id||"custom",label:spec.label,start:firstDate,end:last.date,tradingDays:days,missingWarmup:signalMisses,initial,final:last.equity,totalReturn:profit,cagr:annual,maxDrawdown:drawdown*100,sharpe,meanExposure:expo/days*100,tradeCount:count,turnover:turnover/initial,fees:cost,series};
}
function compare(rows,opts={}){
 const windows=opts.windows||[{name:"train2024_2025",start:"2024-04-15",end:"2025-12-31"},{name:"holdout2026",start:"2026-01-01",end:"2026-10-13"},{name:"full",start:"2024-04-15",end:"2026-10-13"}];
 const modelIds=opts.models||Object.keys(SPECS);const out={};
 for(const w of windows){
  out[w.name]=modelIds.map(id=>{
   const r=simulate(rows,id,{...w,band:opts.band??.05,buyFee:opts.buyFee,sellFee:opts.sellFee});
   return Object.fromEntries(Object.entries(r).filter(([k])=>k!=="series"));
  });
 }
 return out;
}
const api={mergeSeries,targetAt,simulate,compare,SPECS,DEFAULT_COST};
if(typeof module!=="undefined"&&module.exports)module.exports=api;
root.CapitalWaterBacktest=api;
})(typeof window!=="undefined"?window:typeof globalThis!=="undefined"?globalThis:{});
