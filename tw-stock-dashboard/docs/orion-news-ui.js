/* ORION financial headline framing viewer. All publisher text uses textContent. */
(function(){"use strict";
const $=id=>document.getElementById(id);
const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=String(text);return n;};
const items=(host,tag,cls,text)=>{const n=el(tag,cls,text);host.appendChild(n);return n;};
const sourceOK=url=>{
 try{const u=new URL(url);return u.protocol==="https:"&&
 ["www.cna.com.tw","cna.com.tw","news.ltn.com.tw","ec.ltn.com.tw",
  "finance.ettoday.net","www.ettoday.net","tw.stock.yahoo.com",
  "tw.finance.yahoo.com","tw.news.yahoo.com"].includes(u.hostname);}catch{return false}
};
function draw(doc){
 const host=$("orionNewsBoard");if(!host)return;host.replaceChildren();
 if(doc?.schema!==1||!Array.isArray(doc.items)){
  items(host,"p","description","尚未取得可核對的 ORION 新聞資料。");return;
 }
 const source=doc.coverage||{},meta=doc.semantic||{},stat=meta.status||"not_run";
 const ts=Date.parse(doc.generatedAt||"");
 const fresh=Number.isFinite(ts)&&Date.now()>=ts&&Date.now()-ts<=8*3600000;
 const ai=["verified","cached","partial"].includes(stat)&&meta.noTrade===true;
 const counts=ai?[
  {t:"偏利多標題",n:meta.positive||0,k:"positive"},
  {t:"偏利空標題",n:meta.negative||0,k:"negative"},
  {t:"中性／難判",n:meta.neutral||0,k:"neutral"}
 ]:[
  {t:"偏多關鍵詞",n:doc.ruleTone?.["偏多"]||0,k:"positive"},
  {t:"偏空關鍵詞",n:doc.ruleTone?.["偏空"]||0,k:"negative"},
  {t:"中性／難判",n:doc.ruleTone?.["中立／待判"]||0,k:"neutral"}];
 const top=items(host,"div","orion-summary");
 for(const [label,value] of [["標題數",doc.items.length],["已連線 RSS",String(source.healthyFeeds??0)+"／"+String(source.configuredFeeds??0)],["Gemini 已判讀",ai?meta.classified??0:"尚未完成"]]){
  const b=items(top,"div","orion-stat");items(b,"strong","",value);items(b,"span","",label);
 }
 const completeness=doc.items.length?Math.round((meta.classified||0)/doc.items.length*1000)/10:0;
 const eventCount=doc.eventSummary?.eventCount;
 const synopsis=items(host,"p","description",(fresh?"近期新聞標題來源":"歷史快照／非即時")+
 "｜"+(ai?"Gemini 標題語氣研判":"僅關鍵詞初判（非 Gemini 判讀）")+
 "｜已判讀 "+(meta.classified??0)+"／"+doc.items.length+" 篇（"+
 completeness+"%）｜待分析 "+(meta.unclassified??Math.max(0,doc.items.length-(meta.classified??0)))+
 " 篇｜保守事件去重 "+(eventCount??"缺值")+" 組。");
 const progress=items(host,"div","orion-progress");
 progress.setAttribute("role","progressbar");progress.setAttribute("aria-label","ORION Gemini 新聞標題判讀完成率");
 progress.setAttribute("aria-valuemin","0");progress.setAttribute("aria-valuemax","100");
 progress.setAttribute("aria-valuenow",String(completeness));
 const progressFill=items(progress,"span","orion-progress-fill");
 progressFill.style.width=String(completeness)+"%";
 if(ai&&doc.eventSummary?.eventCount){
  const n=meta.eventTotals||{};
  items(host,"p","orion-summary-note","同事件保守去重後、已判讀事件 "+
   (meta.distinctEventsClassified??0)+" 組：偏利多 "+(n.positive??0)+
   "／偏利空 "+(n.negative??0)+"／混合或中性 "+(n.neutral??0)+
   "。上方柱狀圖仍為逐篇標題，不可當作媒體民調。");
 }
 synopsis.setAttribute("role","status");
 const total=counts.reduce((a,x)=>a+x.n,0),bar=items(host,"div","orion-bars");
 for(const r of counts){
  const row=items(bar,"div","orion-bar-row");
  items(row,"span","",r.t);const track=items(row,"span","orion-bar-track");
  const fill=items(track,"span","orion-bar-fill orion-"+r.k);
  fill.style.width=total?Math.round(r.n/total*100)+"%":"0%";
  items(row,"strong","",String(r.n));
 }
 const themes=ai&&meta.themeCounts&&Object.keys(meta.themeCounts).length?
  Object.entries(meta.themeCounts).sort((a,b)=>b[1]-a[1]).slice(0,7).map(([name,count])=>({name,count})):(doc.themes||[]).slice(0,7);
 if(themes.length){
  const b=items(host,"div","orion-themes");
  for(const t of themes)items(b,"span","orion-theme",(t.name||"其他")+" "+(t.count||0));
 }
 const statuses=source.sources||{},sources=items(host,"details","orion-fold");
 items(sources,"summary","", "檢視媒體來源覆蓋率與失聯狀態");
 for(const [name,state] of Object.entries(statuses)){
  items(sources,"p","small",name+"｜"+(state.status||"unknown")+"｜"+
   (state.freshCount??0)+" 篇");
 }
 const conflicts=Array.isArray(meta.topicConflicts)?meta.topicConflicts:[];
 const divergent=items(host,"section","orion-conflicts");
 items(divergent,"h3","orion-mini-title","跨媒體題材觀點分歧（已驗證標題）");
 if(!ai||!conflicts.length){
  items(divergent,"p","small","目前沒有足夠的跨媒體正反標題作為對照；不代表市場沒有分歧。");
 }else for(const conflict of conflicts.slice(0,5)){
  const sec=items(divergent,"div","orion-divergence");
  items(sec,"strong","",conflict.theme+"｜偏利多 "+conflict.positive+"、偏利空 "+conflict.negative);
  items(sec,"p","small","這是同題材不同敘事，不代表新聞事實互相矛盾。");
  const prompts=[];
  for(const row of (conflict.examples||[]).slice(0,2)){
   if(!sourceOK(row.url))continue;
   const p=items(sec,"p","small");
   const link=items(p,"a","",row.tone+"｜"+row.source+"｜"+row.title);
   link.href=row.url;link.target="_blank";link.rel="noopener noreferrer nofollow";
   prompts.push(row);
  }
  if(prompts.length===2){
   const btn=items(sec,"button","orion-copy","複製 ChatGPT 深入查證提示");
   btn.type="button";
   btn.addEventListener("click",async()=>{
    const body="請根據以下公開新聞標題和原文網址，深入查證同一題材的多空敘事。" +
     "請先開啟並核對原始報導，再區分客觀事實、媒體／專家觀點、推測與未驗證處；" +
     "比較消息日期、事件是否相同、是否轉載、資料缺漏與可能利益衝突。" +
     "不可把標題傾向當成股價預測，不要編造內文。\n題材："+conflict.theme+"\n"+
     prompts.map((p,i)=>(i+1)+". "+p.source+"｜"+p.tone+"｜"+p.title+"\n"+p.url).join("\n");
    try{await navigator.clipboard.writeText(body);btn.textContent="已複製，貼到 ChatGPT 即可研究";}
    catch{btn.textContent="複製未成功，請使用原文連結";}
   });
  }
 }
  const articles=items(host,"div","orion-articles");
 items(articles,"h3","orion-mini-title","最新可核對財經新聞");
 const newest=doc.items.filter(x=>sourceOK(x.url)).slice(0,10);
 for(const a of newest){
  const box=items(articles,"div","orion-article");
  const link=items(box,"a","",a.title||"無標題");
  link.href=a.url;link.target="_blank";link.rel="noopener noreferrer nofollow";
  items(box,"p","small",(a.source||"來源不明")+"｜"+
   (a.publishedAt?new Date(a.publishedAt).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",hour12:false,
    month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}):"日期缺值")+"｜"+
   (a.semantic?.tone||"Gemini 尚未判讀"));
 }
 items(host,"p","orion-foot","涵蓋已設定且成功取得的 RSS 與既有新聞來源，並非全台所有媒體。標題偏利多或偏利空是報導語氣，不是股價預測，且不改變 TITAN 硬性風控。");
}
function history(index){
 const host=$("orionHistory");if(!host)return;host.replaceChildren();
 if(index?.schema!==1||!Array.isArray(index.days)||!index.days.length){
  items(host,"p","small","目前還沒有正式可查的每日新聞日檔。");return;
 }
 for(const d of index.days.slice(0,14)){
  if(!/^20\d{2}-\d{2}-\d{2}$/.test(d.day||""))continue;
  const a=items(host,"a","orion-day",d.day+"｜"+d.observedHeadlines+" 篇標題"+
   "｜Gemini "+d.semanticStatus);
  a.href="./data/orion_news/history/"+d.day+".json";
  a.target="_blank";a.rel="noopener noreferrer";
 }
}
window.OrionNewsViewer={draw,history};
})();
