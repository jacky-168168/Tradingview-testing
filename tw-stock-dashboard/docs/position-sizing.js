/* Position sizing V1: browser-only worksheet, manual portfolio, authenticated site gate shared from site-access.js. */
(function(){
"use strict";
const C=window.PositionSizingCore,D=window.DynamicExposure,$=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const money=v=>v==null||!Number.isFinite(v)?"—":Math.round(v).toLocaleString("zh-TW")+" 元";
const number=(v,n=0)=>v==null||!Number.isFinite(v)?"—":Number(v).toLocaleString("zh-TW",{minimumFractionDigits:n,maximumFractionDigits:n});
let DATA=null,market=null,selectedStock=null,current=null;
const typeOptions=Object.entries(C.TYPES).map(([v,s])=>'<option value="'+v+'">'+esc(s.name)+'</option>').join("");
const groupOptions=Object.entries(C.GROUPS).map(([v,s])=>'<option value="'+v+'">'+esc(s)+'</option>').join("");
const gMap=new Map();
function message(text,bad=false){$("feedback").textContent=text;$("feedback").dataset.error=bad?"1":"0"}
function row(p={}) {
 const root=document.createElement("div");root.className="holding-row";
 root.innerHTML='<label>標的代碼<input data-key="code" placeholder="例如 0052、2330" value="'+esc(p.code||"")+'" maxlength="20"></label><label>類別<select data-key="type">'+typeOptions+'</select></label><label>風險族群<select data-key="group">'+groupOptions+'</select></label><label>目前投入市值（元）<input data-key="value" inputmode="decimal" type="number" min="0" step="1000" value="'+esc(p.value??0)+'"></label><button class="remove" type="button" title="刪除此筆持股">移除</button>';
 root.querySelector('[data-key=type]').value=p.type||"stock";
 root.querySelector('[data-key=group]').value=p.group||"other";
 root.querySelector(".remove").addEventListener("click",()=>{root.remove();recalc()});
 root.querySelector('[data-key=code]').addEventListener("change",()=>{
  const code=C.normalizeSymbol(root.querySelector('[data-key=code]').value),etf=C.ETF[code],g=gMap.get(code);
  if(etf||g){root.querySelector('[data-key=type]').value=etf?.type||"stock";root.querySelector('[data-key=group]').value=etf?.group||C.guessGroup(g)}
  recalc();
 });
 root.addEventListener("input",recalc);root.addEventListener("change",recalc);
 $("holdings").appendChild(root);
}
function selectedPositions(){
 return [...$("holdings").querySelectorAll(".holding-row")].map(row=>Object.fromEntries([...row.querySelectorAll("[data-key]")].map(el=>[el.dataset.key,el.value]))).filter(x=>x.code||Number(x.value)>0);
}
function codes(){
 const s=$("presets");s.replaceChildren(new Option("自訂股票／ETF 代碼",""));
 const seen=new Set();
 for(const [code,x] of Object.entries(C.ETF)){s.add(new Option(code+" "+x.name,code));seen.add(code)}
 const group=document.createElement("optgroup");group.label="本次 G 強勢股（資料日期："+(DATA?.dataDate||"—")+"）";
 for(const g of DATA?.models?.G||[]){
  const code=C.normalizeSymbol(g.code);
  if(!code||seen.has(code))continue;
  seen.add(code);gMap.set(code,g);
  group.appendChild(new Option(code+" "+String(g.name||""),code));
  if(gMap.size>=30)break;
 }
 s.appendChild(group);
}
function applySymbol(code){
 code=C.normalizeSymbol(code);
 if(!code)return;
 $("symbol").value=code;
 const etf=C.ETF[code],g=gMap.get(code);
 if(etf){$("name").textContent=etf.name;$("kind").value=etf.type;$("sector").value=etf.group; $("price").value=""; $("priceDate").value="";$("atr").value="";$("ret20").value="";message(code+" 是 ETF：目前沒有可驗證的 ETF 專屬歷史價格資料，請自行提供參考價與60日收盤價；不會用其他股票價格代替。");}
 else if(g){$("name").textContent=g.name||"G 候選股";$("kind").value="stock";$("sector").value=C.guessGroup(g);$("price").value=(g.currentPrice??g.close)??"";$("priceDate").value=DATA?.dataDate||"";$("atr").value=g.atrPct??"";$("ret20").value=g.ret20??"";message("已載入 G 榜 "+code+"，參考的是完整更新的市場資料日；G 強勢不等於已出現 SS Bottom。")}
 else{$("name").textContent="自訂標的";$("kind").value="stock";$("sector").value="other";$("price").value="";$("priceDate").value="";$("atr").value="";$("ret20").value="";message("手動股票代碼：請自行填寫價格、波動度及所屬族群。")}
 $("history").value="";recalc();
}
function input(){
 let zone={ready:false,count:0};
 try{zone=C.parseSeries($("history").value,$("price").value)}catch(e){zone={ready:false,reason:e.message,count:0,error:true}}
 const histHas=String($("history").value).trim().length>0;
 const zoneName=zone.ready?zone.label:histHas?(zone.reason||"資料不足"):"未核實（可貼60日收盤價）";
 $("zone").textContent=zoneName;
 $("zoneDetail").textContent=zone.ready?"Z-score "+number(zone.z,2)+"｜60日均值 "+number(zone.mean,2)+"｜收盤筆數 "+zone.count+"。這是相對位階，不是基本面價值。":zone.reason||"ETF/個股未提供歷史收盤序列時，系統不會假稱它處於價值區。";
 const f={
  code:$("symbol").value,type:$("kind").value,group:$("sector").value,price:$("price").value,priceDate:$("priceDate").value,atrPct:$("atr").value,ret20:$("ret20").value,
  capital:$("capital").value,otherHeld:$("otherHeld").value,positions:selectedPositions(),zone:zone.ready?zone.zone:"unknown",historyValidated:zone.ready,
  signal:$("signal").value,entryConfirmed:$("entryConfirmed").checked
 };
 return {f,zone};
}
function recalc(){
 if(!market){return}
 const {f,zone}=input();
 current=C.size(f,market);
 const x=current;
 if(!x.valid){$("decision").textContent="資料未備齊";$("decisionText").textContent=x.reason;return}
 const fill=$("allocationFill");fill.style.width=(market.valid?market.target:0)+"%";
 $("marketDate").textContent=market.valid?"大盤資料 "+market.date+(market.stale?"｜已過期":"｜有日期")+"｜正式 Risk "+market.risk+"/100":"大盤資料不足";
 $("marketTarget").textContent=market.valid?market.target+"%":"—";
 $("marketReserve").textContent=market.valid?100-market.target+"%":"—";
 $("invested").textContent=money(x.invested);
 $("remainingMarket").textContent=money(x.marketLeft);
 $("maxPosition").textContent=money(x.limit);
 $("maxShares").textContent=number(x.maxShares)+" 股";
 $("budgetRisk").textContent=money(x.riskMoney);
 $("stress").textContent=number(x.stressPct*100,1)+"%";
 $("riskLoss").textContent=money(x.riskAtMax);
 $("firstBudget").textContent=money(x.first);
 $("firstShares").textContent=number(x.firstShares)+" 股";
 $("firstPct").textContent="預定分配 "+number(x.pct*100)+"%｜潛在首批 "+money(x.firstPotential)+"，僅條件全通過才列入實際可買";
 $("holdingTotal").textContent="現持股 "+money(x.invested)+"，含其他未分類部位 "+money(x.unknownHeld)+"；正2名目曝險初估 "+money(x.grossEffective)+"（非精確投資組合風險）。";
 $("groupRisk").textContent="目前此風險族群 "+C.GROUPS[x.group]+" 已投入 "+money(x.sectorHeld)+"，族群上限剩餘 "+money(x.caps.sector)+"。";
 const labels=[["大盤可用額度",x.caps.market],["同檔可用上限",x.caps.class],["產業／風險族群剩餘",x.caps.sector],["正 2 集中額度",x.caps.leverage],["風險預算換算上限",x.caps.risk]];
 const caps=$("limitRows");caps.replaceChildren();
 for(const [key,v] of labels){if(v===Infinity)continue;const item=document.createElement("div");item.className="limit-row";const l=document.createElement("span");l.textContent=key;const w=document.createElement("strong");w.textContent=money(v);item.append(l,w);caps.append(item)}
 $("decision").textContent=x.canBuy?"風控通過｜可建立首批試算":"暫不建立新倉";
 const riskText=x.blocked.filter(z=>!(x.canBuy&&z.includes("正2部位"))).join("；");
 $("decisionText").textContent=x.canBuy?"已通過頁面設定的研究條件，仍須確認即時行情、成交量與實際風控；非券商委託。":riskText;
 const notes=[...x.warnings];
 if(zone.ready&&zone.zone==="hot")notes.unshift("高位階：本模型首批預算為 0，暫不追價。");
 if(f.group==="technology")notes.push("科技股票、0052、QQQ、科技正2 以同族群代理計入曝險，不代表已精算實際成分股重疊。");
 if(market.stale)notes.unshift("大盤資料過期；無論價格位階如何，買入動作都會被鎖定。");
 $("warnings").replaceChildren(...notes.map(n=>{const div=document.createElement("div");div.className="warn-item";div.textContent="• "+n;return div}));
 const ladder=$("ladderRows");ladder.replaceChildren();
 for(const t of x.ladder){
  const tr=document.createElement("tr");
  for(const val of [t.step===1?"首批":"第"+t.step+"批",number(t.referencePrice,2),money(t.budget),number(Math.floor(t.budget/t.referencePrice))+" 股",t.trigger]){
   const td=document.createElement("td");td.textContent=val;tr.append(td)
  }ladder.appendChild(tr)
 }
 $("ladderNote").textContent="此表為固定預算階梯情境，使用參考價每下降 "+number(x.ladder[0]?.dropPct,1)+"% 估算下批觸價；追加必須再出現 Bottom，不能只因價格跌到就買進。四批合計僅為配置上限；尚未扣除實際手續費和股數取整。";
}
function copyPlan(){
 if(!current?.valid){message("請先完成有效試算",true);return}
 const x=current,txt=["台股量化｜資金配置研究表","日期："+(market.date||"未知"),"股票："+x.code+"／"+(C.TYPES[x.kind]?.name||""),"參考價："+x.price,"正式 Risk："+market.risk,"大盤參考股票水位："+(market.target??"缺值")+"%","現有投入："+money(x.invested),"單檔可規劃上限："+money(x.limit),"建議首批（條件全通過才非零）："+money(x.first),"預估首批股數："+x.firstShares,"假設不利波動："+number(x.stressPct*100,1)+"%","下跌壓力損失："+money(x.riskAtMax),"當下條件："+(x.canBuy?"研究條件通過":"尚不允許新倉"),...x.blocked,"此為研究配置，不是券商委託或投資建議。"].join("\n");
 if(!navigator.clipboard?.writeText){message("瀏覽器不支援剪貼簿 API，請改用 Chrome 開啟",true);return}
 navigator.clipboard.writeText(txt).then(()=>message("已複製資金試算結果"),()=>message("複製失敗，請檢查瀏覽器權限",true));
}
async function load(){
 try{
  const response=await fetch("./data/latest.json?v="+Date.now(),{cache:"no-store"});
  if(!response.ok)throw Error("資料下載 HTTP "+response.status);
  DATA=await response.json();market=D.calculate(DATA);
  codes();$("dataStatus").textContent="已讀取 "+DATA.dataDate+" 大盤與 G 選股資料；本工具不取即時報價。";
  recalc();
 }catch(e){$("dataStatus").textContent="資料讀取失敗："+e.message;message("無法載入正式市場資料，暫停資金水位與買入試算",true)}
}
for(const id of ["capital","otherHeld","kind","sector","price","priceDate","atr","ret20","signal","entryConfirmed","history","symbol"])$(id).addEventListener("input",recalc);
$("symbol").addEventListener("change",()=>applySymbol($("symbol").value));
$("presets").addEventListener("change",()=>applySymbol($("presets").value));
$("addHolding").addEventListener("click",()=>{row();recalc()});
$("copyPlan").addEventListener("click",copyPlan);
$("clearHoldings").addEventListener("click",()=>{if(!window.confirm("清空目前頁面的所有持股輸入？"))return;$("holdings").replaceChildren();$("otherHeld").value="0";recalc()});
$("refreshData").addEventListener("click",load);
row();load();
})();
