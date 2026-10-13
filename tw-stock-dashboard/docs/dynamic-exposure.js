/* Dynamic Capital Exposure V1 | Transparent original research model, NOT ARK source code.
   Published cash-market facts only; never alters Risk Score, G rankings or F/F2 gates.
   Exports pure calculations for regression tests (CommonJS) and browser UI renderer. */
(function(scope){
"use strict";
const clamp=(v,a,b)=>Math.max(a,Math.min(b,v)),finite=v=>v!==null&&v!==undefined&&v!==""&&Number.isFinite(Number(v))?Number(v):null;
const fmt=v=>Math.round(v).toLocaleString("zh-TW"),pc=v=>Number(v).toFixed(0)+"%";
function localParts(now=new Date()){
 const parts=new Intl.DateTimeFormat("en-GB",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",weekday:"short",hourCycle:"h23"}).formatToParts(now);
 const p=Object.fromEntries(parts.map(x=>[x.type,x.value]));
 return {day:p.year+"-"+p.month+"-"+p.day,week:p.weekday,hour:Number(p.hour),minute:Number(p.minute)};
}
function elapsedTradingDays(start,end){
 if(!/^\d{4}-\d\d-\d\d$/.test(String(start))||start>end)return 999;
 let d=new Date(start+"T00:00:00Z"),stop=new Date(end+"T00:00:00Z"),n=0,loop=0;
 if(!Number.isFinite(d.getTime())||!Number.isFinite(stop.getTime()))return 999;
 while(d<stop&&loop++<22){d=new Date(d.getTime()+86400000);const wd=d.getUTCDay();if(wd!==0&&wd!==6)n++}return d<stop?999:n;
}
function ageStatus(date,now=new Date()){
 const p=localParts(now),gap=elapsedTradingDays(date,p.day),isWeekend=p.week==="Sat"||p.week==="Sun";
 const stale=gap===999||gap>=2||(gap===1&&!isWeekend&&(p.hour*60+p.minute)>=870);
 return {stale,day:p.day,gap,label:stale?"資料待更新，僅供歷史試算":date===p.day?"本交易日盤後資料":isWeekend?"最近完整收盤日":gap===1?"前一交易日正式收盤資料":"最近完整收盤日"};
}
function calculate(data,now=new Date()){
 const r=data&&data.risk,diag=data&&data.marketIntelligence,health=diag&&diag.asOf===r?.date&&diag.riskScore===r?.score?diag.marketHealth:null;
 const risk=finite(r?.score),date=String(r?.date||"");
 const empty={valid:false,stale:true,date,score:null,target:null,reason:"缺少具日期及數值的大盤正式 Risk Score；暫停資金水位推估。",factors:[],flags:[]};
 if(risk===null||risk<0||risk>100||!/^\d{4}-\d\d-\d\d$/.test(date))return empty;
 const factors=[{key:"risk",name:"正式 Risk Score",weight:40,input:risk,value:risk,note:"沿用原始收盤分數，不更改選股與大盤條件。"}];
 const breadth=finite(r.breadth);
 if(breadth!==null&&breadth>=0&&breadth<=100)factors.push({key:"breadth",name:"上漲家數廣度",weight:20,input:breadth,value:clamp(50+(breadth-50)*2.5,0,100),note:"以 50% 廣度為中點，每差 1 個百分點調整 2.5 分。"});
 const index=finite(r.index),ma20=finite(r.ma20);
 if(index!==null&&ma20!==null&&index>0&&ma20>0){const dist=(index/ma20-1)*100;factors.push({key:"trend",name:"大盤相對 MA20",weight:15,input:dist,value:clamp(50+dist*4,0,100),note:"大盤距 MA20 每 1% 約調整 4 分；不以短期乖離當作股票估值。"});}
 const vPct=finite(health?.volatilityHistoryPercentile);
 if(vPct!==null&&vPct>=0&&vPct<=100)factors.push({key:"volatility",name:"20日波動歷史分位",weight:15,input:vPct,value:100-vPct,note:"歷史波動分位越高，風險分數越低；僅限同日市場診斷。"});
 const foreign=finite(r.foreign);
 if(foreign!==null)factors.push({key:"foreign",name:"外資買賣超",weight:10,input:foreign,value:clamp(50+foreign/20,0,100),note:"官方風控欄位單位為億元，以 ±1,000 億對應 0–100；僅作小權重輔助。"});
 const weight=factors.reduce((t,f)=>t+f.weight,0);
 if(weight<85||factors.length<4)return {...empty,date,reason:"可用指標未滿 85% 權重或少於 4 項，避免以缺值硬算配置。",factors};
 const composite=factors.reduce((t,f)=>t+f.value*f.weight,0)/weight;
 // Exposure is a decision-support RESEARCH mapping, not calibrated or backtested.
 const raw=clamp(Math.round((15+composite*.75)/5)*5,10,85),flags=[];
 let cap=85;
 if(risk<45){cap=Math.min(cap,25);flags.push("原始 Risk Score <45：一般新倉總水位上限 25%。")}
 else if(risk<60){cap=Math.min(cap,40);flags.push("原始 Risk Score 45–59：一般持股試算上限 40%，不等於允許進場。")}
 if(breadth!==null&&breadth<40){cap=Math.min(cap,30);flags.push("上漲家數低於 40%，降低持股上限。")}
 if(vPct!==null&&vPct>=85){cap=Math.min(cap,45);flags.push("歷史波動分位 ≥85%，限制總曝險。")}
 const top=String(r.topState||"");
 if(top.includes("Strong Top Reversal")){cap=Math.min(cap,20);flags.push("大盤強烈 Top 反轉：試算上限 20%。")}
 else if(top.includes("Top Reversal Attempt")){cap=Math.min(cap,30);flags.push("大盤 Top 嘗試反轉：試算上限 30%。")}
 else if(top.includes("Extreme Overbought")){cap=Math.min(cap,35);flags.push("大盤極端過熱：試算上限 35%。")}
 else if(top.includes("Top Watch"))flags.push("Top Watch 只是觀察，未確認真正頂部。");
 if(health?.indexBreadthDivergence===true){cap=Math.min(cap,55);flags.push("指數與市場廣度背離，限制擴張部位。")}
 const strongBottom=String(r.bottomState||"").includes("Strong Bottom Reversal");
 if(strongBottom&&risk<60)flags.push("大盤強底部反轉僅屬研究例外；仍須個股 Bottom/SS 訊號確認，不自動解禁。");
 const target=Math.min(raw,cap),fresh=ageStatus(date,now);
 return {valid:true,stale:fresh.stale,age:fresh.label,date,score:Math.round(composite*10)/10,target,raw,cap,weight,coverage:weight,flags,factors,risk,source:"已確認同日收盤資料",reason:fresh.stale?"本交易日風控資料尚未更新，只顯示歷史水位，不給今日新增部位許可。":""};
}

/** Countercyclical drawdown budget, independent of directional Risk Score.
 * NOT ARK proprietary formula: preceding 120-session high drawdown is a price proxy, not intrinsic value.
 * Defines a preparation allocation only, NOT permission to buy.
 */
function calculateContrarian(data,now=new Date()){
 const r=data?.risk||{},health=data?.marketIntelligence?.asOf===r.date?data?.marketIntelligence?.marketHealth:null;
 const date=String(r.date||""),risk=finite(r.score),index=finite(r.index),high=finite(r.priorHigh120);
 const closeHighDist=index!==null&&index>0&&high!==null&&high>0?(index/high-1)*100:finite(health?.distancePrior120HighPct);
 if(risk===null||risk<0||risk>100||!/^\d{4}-\d\d-\d\d$/.test(date)||closeHighDist===null||closeHighDist>1||closeHighDist< -100)
   return {valid:false,stale:true,target:null,date,risk,reason:"缺少可核實的大盤價格或前120日高點，不以 Risk Score 倒數假造低估位階。"};
 const drawdown=clamp(-closeHighDist,0,100),ma20=finite(r.ma20),aboveMA=ma20!==null&&ma20>0&&index!==null?(index/ma20-1)*100:null;
 const tiers=[{limit:2,pct:30},{limit:5,pct:40},{limit:10,pct:50},{limit:15,pct:65},{limit:Infinity,pct:80}];
 const tier=tiers.find(t=>drawdown<t.limit),raw=tier.pct;
 const overheating=aboveMA!==null&&aboveMA>=7;
 const target=overheating?Math.min(raw,25):raw;
 const freshness=ageStatus(date,now),riskOff=risk<60,top=String(r.topState||"");
 const topVeto=top.includes("Strong Top Reversal")||top.includes("Top Reversal Attempt");
 const allowedNew=!freshness.stale&&!riskOff&&!topVeto;
 const reasons=[];
 if(overheating)reasons.push("大盤高於 MA20 ≥7%，額外降低預備持股比例。");
 if(riskOff)reasons.push("Risk Score <60，僅預留逢低布局資金，不開放一般新倉。");
 if(topVeto)reasons.push("大盤已確認頂部反轉警訊，停止一般新倉。");
 if(freshness.stale)reasons.push("大盤資料過期，只能查看歷史情境。");
 return {valid:true,date,stale:freshness.stale,age:freshness.label,risk,target,cash:100-target,drawdown:Math.round(drawdown*100)/100,aboveMA:aboveMA===null?null:Math.round(aboveMA*100)/100,source:high!==null?"現貨指數與資料庫前120日高點":"一致日期的大盤診斷前高距離",raw,allowedNew,reasons,reason:reasons.join(" "),method:"跌幅 <2%→30%；2–5%→40%；5–10%→50%；10–15%→65%；≥15%→80%。若較MA20高≥7%，水位上限25%。"};
}
function sizePlan(result,opts={}){
 const capital=clamp(finite(opts.capital)??1000000,0,1e10),held=clamp(finite(opts.held)??0,0,1e10),stocks=clamp(Math.round(finite(opts.stocks)??5),1,30);
 const percent=result?.valid?result.target:0,limit=capital*percent/100,headroom=Math.max(0,limit-held),excess=Math.max(0,held-limit),reserve=Math.max(0,capital-limit);
 const stock=opts.stock&&typeof opts.stock==="object"?opts.stock:null;
 const price=finite(stock?.currentPrice??stock?.close),atr=finite(stock?.atrPct),ret20=finite(stock?.ret20);
 let perStock=limit/stocks;
 // Inverse volatility inspired risk sizing, not a valuation or ARK proprietary formula.
 const volFactor=atr!==null&&atr>0?clamp(4/atr,.5,1.25):.75;
 perStock*=volFactor;
 const firstPct=ret20!==null&&ret20>=25?10:ret20!==null&&ret20>=15?15:atr!==null&&atr>=8?10:atr!==null&&atr>=5?15:25;
 const firstBudget=Math.min(headroom,perStock*firstPct/100);
 const shares=price!==null&&price>0?Math.floor(firstBudget/price):null;
 const canBuy=result?.valid===true&&!result.stale&&headroom>0&&Boolean(stock)&&shares!==null&&shares>0;
 return {capital,held,stocks,limit,headroom,excess,reserve,perStock,volFactor,firstPct,firstBudget,shares,lots:shares===null?null:Math.floor(shares/1000),price,atr,ret20,canBuy};
}
function byId(id){return document.getElementById(id)}
function put(id,value){const e=byId(id);if(e)e.textContent=String(value)}
let current=null,selected=null;
function candidateList(data){
 const g=data?.models?.G||[];
 const unique=new Map();
 for(const s of g){if(!/^\d{4,6}$/.test(String(s.code||"")))continue;if(!unique.has(s.code))unique.set(s.code,s);if(unique.size>=20)break}
 return [...unique.values()];
}
function selectOptions(data){
 const node=byId("expStock");if(!node)return;
 const keep=node.value;
 node.replaceChildren(new Option("選擇 G 強勢股（非推薦買進）",""));
 for(const s of candidateList(data)){node.add(new Option(String(s.code)+" "+String(s.name||"")+"｜"+Number(s.currentPrice??s.close).toFixed(2),String(s.code)))}
 node.value=[...node.options].some(o=>o.value===keep)?keep:"";
}
function render(){
 if(!current)return;
 const calc=calculate(current),selection=byId("expStock")?.value;
 selected=candidateList(current).find(s=>String(s.code)===selection)||null;
 const plan=sizePlan(calc,{capital:byId("expCapital")?.value,held:byId("expHeld")?.value,stocks:byId("expSlots")?.value,stock:selected});
 const card=byId("dynamicExposure");if(card){card.dataset.status=!calc.valid||calc.stale?"paused":calc.target<40?"defensive":calc.target>=65?"risk-on":"neutral";}
 put("expAsOf",calc.valid?"資料日 "+calc.date+"｜"+calc.age:"資料不完整");
 put("expHeadline",!calc.valid?"資料不足，暫停計算":calc.stale?"資料待更新｜不作今日新倉建議":calc.target<=30?"防守水位｜控制新增風險":calc.target<60?"審慎水位｜保留加碼現金":"趨勢水位｜仍需等個股訊號");
 put("expTarget",calc.valid?pc(calc.target):"—");
 const fill=byId("expStockFill");if(fill)fill.style.width=(calc.valid?calc.target:0)+"%";
 put("expCash",calc.valid?pc(100-calc.target):"—");
 put("expComposite",calc.valid?calc.score.toFixed(1)+"/100":"—");
 put("expAllowed",calc.valid?fmt(plan.limit)+" 元":"—");
 put("expFree",calc.valid?fmt(plan.headroom)+" 元":"—");
 put("expReserve",calc.valid?fmt(plan.reserve)+" 元":"—");
 put("expFirst",!selected?"先選 G 榜標的":!calc.valid?"暫停":!plan.canBuy?"不可作今日新倉":fmt(plan.firstBudget)+" 元");
 put("expShares",!selected||plan.shares===null?"—":fmt(plan.shares)+" 股｜整張 "+fmt(plan.lots));
 put("expSub",!selected?"單檔以 G 榜最近資料計算，沒有足夠資料不推測價值區。":String(selected.code)+" "+String(selected.name||"")+"｜參考價 "+(plan.price===null?"缺值":plan.price.toFixed(2))+"｜20日漲幅 "+(plan.ret20===null?"未知":plan.ret20.toFixed(1)+"%")+"｜ATR "+(plan.atr===null?"未知":plan.atr.toFixed(1)+"%")+"｜本批比例 "+plan.firstPct+"%");
 const status=byId("expStatus");
 if(status)status.textContent=!calc.valid?calc.reason:calc.stale?"⚠ "+calc.reason:plan.excess>0?"⚠ 目前投入已超過此模型水位 "+fmt(plan.excess)+" 元。僅提醒重新評估，不自動賣出。":calc.risk<60?"⚠ 正式 Risk Score 低於 60。水位只做資產壓力情境，仍須遵守既有大盤進場閘門。":"獨立資金管理試算，不代表即時行情、進場保證或已回測績效。";
 const root=byId("expFactors");
 if(root){
  root.replaceChildren();
  if(calc.valid){
   for(const f of calc.factors){
    const row=document.createElement("div");row.className="exp-factor";
    const lab=document.createElement("span");lab.textContent=f.name+"（"+f.weight+"%）";
    const bar=document.createElement("div");bar.className="exp-bar";
    const fill=document.createElement("i");fill.style.width=f.value.toFixed(1)+"%";bar.appendChild(fill);
    const value=document.createElement("strong");value.textContent=f.value.toFixed(0)+"/100";
    row.append(lab,bar,value);root.appendChild(row);
   }
  }else root.textContent="缺少可核對資料；不以缺值補假分數。";
 }
 const explain=byId("expExplain");
 if(explain)explain.textContent=calc.valid?"五因子加權 "+calc.score.toFixed(1)+" 分 → 原始水位 "+calc.raw+"% → 套用風險上限 "+calc.cap+"% → 參考持股 "+calc.target+"%。資料涵蓋 "+calc.coverage+"% 權重。"+(calc.flags.length?" 風險提醒："+calc.flags.join(" "):"")+" 未經獨立回測，不修改 G／F2 邏輯。":calc.reason;
}
function refresh(data){current=data||null;selectOptions(current);render()}
function init(){
 if(typeof document==="undefined"||!byId("dynamicExposure"))return;
 for(const id of ["expCapital","expHeld","expSlots","expStock"]){const el=byId(id);if(el)el.addEventListener("input",render)}
}
const api={calculate,calculateContrarian,sizePlan,ageStatus,elapsedTradingDays,candidateList,refresh,init};
scope.DynamicExposure=api;
if(typeof module!=="undefined"&&module.exports)module.exports=api;
})(typeof window!=="undefined"?window:typeof globalThis!=="undefined"?globalThis:{});
