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
 const progress=items(host,"div","orion-coverage");
 const full=Number(meta.eligible??doc.items.length),classified=Number(meta.classified??0);
 const pct=full?Math.min(100,Math.max(0,classified/full*100)):0;
 items(progress,"span","", "Gemini 完成率："+classified+"／"+full+"（"+pct.toFixed(1)+"%）"+
  (full===classified?"｜全部完成":"｜剩餘 "+Math.max(0,full-classified)+" 篇下一輪續判"));
 const track=items(progress,"div","orion-bar-track"),fill=items(track,"div","orion-bar-fill orion-positive");
 fill.style.width=pct.toFixed(1)+"%";
 if(Number.isFinite(meta.repeatedHeadlineCount)&&meta.repeatedHeadlineCount>0)
  items(progress,"span","", "重複標題 "+meta.repeatedHeadlineCount+" 則（只做文字完全相同的保守比對）");
 const synopsis=items(host,"p","description",(fresh?"近期新聞標題來源":"歷史快照／非即時")+
 "｜"+(ai?"Gemini 標題語氣研判":"僅關鍵詞初判（非 Gemini 判讀）")+
 "｜"+(meta.classified??0)+" 篇完成模型判讀"+
 (meta.status==="partial"?"，以下僅為已判讀樣本，不能推論全部新聞風向":"")+
 "；不能代表股票實際漲跌或媒體受眾共識。");
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
 if(ai&&Array.isArray(meta.contrastingThemes)&&meta.contrastingThemes.length){
  const sides=items(host,"details","orion-fold");
  items(sides,"summary","","同題材出現正反報導（點開核對，不代表同一事件）");
  for(const pair of meta.contrastingThemes.slice(0,5)){
   const block=items(sides,"div","orion-article");
   items(block,"strong","",pair.theme||"未標示題材");
   items(block,"p","small","同題材存在正反標題，不代表兩篇討論相同事件。請先核對原文。");
   for(const [prefix,x] of [["偏利多",pair.bull],["偏利空",pair.bear]]){
    if(!x||!sourceOK(x.url))continue;
    const link=items(block,"a","",prefix+"｜"+x.title);
    link.href=x.url;link.target="_blank";link.rel="noopener noreferrer nofollow";
   }
   if(pair.bull&&pair.bear&&sourceOK(pair.bull.url)&&sourceOK(pair.bear.url)){
    const button=items(block,"button","orion-copy","複製 ChatGPT 深度查證提示");
    button.type="button";
    button.addEventListener("click",async()=>{
     const research="請依據下列台灣財經報導原文進行來源查證與多空敘事分析。"+
      "必須先檢查原文內容、報導日期、作者與轉載關係，分別列出客觀事實、報導者立場、推測、可能的缺漏與利益衝突。"+
      "請特別確認兩篇是否其實討論不同事件，不可因為同一題材正反標題就宣稱事實互相矛盾。"+
      "請標明每項結論的證據來源，不能把新聞風向當成股價預測。"+
      "\n新聞題材："+(pair.theme||"未分類")+
      "\n偏利多："+pair.bull.source+"｜"+pair.bull.title+"\n"+pair.bull.url+
      "\n偏利空："+pair.bear.source+"｜"+pair.bear.title+"\n"+pair.bear.url;
     try{
      await navigator.clipboard.writeText(research);
      button.textContent="已複製，貼到 ChatGPT 即可深入查證";
     }catch{
      button.textContent="複製失敗，請手動複製兩篇原文連結";
     }
    });
   }
  }
 }
  const statuses=source.sources||{},sources=items(host,"details","orion-fold");
 items(sources,"summary","", "檢視媒體來源覆蓋率與失聯狀態");
 for(const [name,state] of Object.entries(statuses)){
  items(sources,"p","small",name+"｜"+(state.status||"unknown")+"｜"+
   (state.freshCount??0)+" 篇");
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
