/* Six-agent research browser renderer. Untrusted source content is rendered via textContent only. */
(function(){"use strict";
const core=window.SixAgentResearch,$=id=>document.getElementById(id);
let current=null,selected=null;
function el(tag,text,css){const e=document.createElement(tag);if(text!==undefined&&text!==null)e.textContent=String(text);if(css)e.className=css;return e;}
function fmt(n,d=1){return typeof n==="number"&&Number.isFinite(n)?n.toFixed(d):"缺值";}
function append(parent,tag,text,css){const node=el(tag,text,css);parent.appendChild(node);return node;}
function explainCard(host,name,heading,status,details,style){const card=append(host,"section",null,"agent"+(style?" "+style:""));
 const title=append(card,"h3");append(title,"span",name);append(title,"span",heading,"small");
 append(card,"p",status,"flag"+(style==="deny"?" no":style==="final"?" warn":""));
 for(const line of details){if(typeof line==="string")append(card,"p",line,"hint");else if(line?.url){
  const a=append(card,"a",line.title||line.url);a.href=line.url;a.target="_blank";a.rel="noopener noreferrer nofollow";
  append(card,"p",(line.source||"未註明媒體")+" · "+(line.publishedAt||"時間不明")+(line.confirmed?" · 已核實":" · 未獨立核實"),"hint");
 }}
 return card;
}
function detail(c){
 selected=c.code;const a=c.agents;
 $("detailTitle").textContent=c.code+" "+c.name;
 $("decision").textContent=a.nova.status;
 $("decision").className="flag"+(a.titan.hardVeto?" no":a.nova.status.includes("等待")?" warn":" ok");
 $("detailIntro").textContent="第 "+c.sourceRank+" 名 · "+(c.market||"市場未標註")+" · 參考價 "+fmt(c.price,2)+
  " · 資料日 "+(c.asOfDate||"未知")+"。這裡只顯示研究證據，無下單功能。";
 const host=$("agents");host.replaceChildren();
 explainCard(host,"ATLAS","全市場掃描",a.atlas.status,[
  "原始 G 排名第 "+a.atlas.rank+" 名；RS20 "+fmt(a.atlas.rs20,2)+"、RVOL "+fmt(a.atlas.rvol,2),
  ...a.atlas.facts,a.atlas.note]);
 explainCard(host,"VEGA","技術結構",a.vega.status,[...a.vega.facts,
  "目前技術訊號："+(a.vega.signal||"缺值"),a.vega.invalidation]);
 const sourceList=a.orion.sources.map(x=>({...x}));const links=sourceList.map(x=>({title:x.title,url:x.url,source:x.source,publishedAt:x.publishedAt,confirmed:x.confirmed})).filter(x=>x.url);
 explainCard(host,"ORION","新聞與事件",a.orion.status,[a.orion.reason,
  "來源資料同步年齡："+(a.orion.datasetAgeMinutes===null?"不明":Math.round(a.orion.datasetAgeMinutes)+" 分鐘"),...links]);
 explainCard(host,"LUNA","市場與公開社群討論",a.luna.status,[
  "大盤風險分數："+fmt(a.luna.score,0)+"／100；上漲家數比率："+fmt(a.luna.breadth,1)+"%",
  "社群標題觀察："+a.luna.socialStatus+"（有效 "+(a.luna.socialSample??0)+" 篇；偏多 "+(a.luna.socialBull??0)+"／偏空 "+(a.luna.socialBear??0)+"）",
  "來源篇數：PTT "+(a.luna.socialPlatforms?.PTT??0)+"／Threads "+(a.luna.socialPlatforms?.Threads??0)+"／Instagram "+(a.luna.socialPlatforms?.Instagram??0)+"／Bluesky "+(a.luna.socialPlatforms?.Bluesky??0),
  "與此股票名稱／代碼直接相關的投資討論標題："+(a.luna.socialMentions??"無有效樣本")+" 篇",
  "Gemini 逐篇判讀："+a.luna.semanticSummary.status+"；已判讀 "+(a.luna.semanticSummary.classified??0)+" 篇（與規則結果分開）",
  "個股討論熱度："+a.luna.heatStatus,
  "新聞標題觀察："+a.luna.newsStatus+"（獨立計數，不代表社群討論）",
  "來源：PTT "+a.luna.sourceStatus.PTT+"；Threads "+a.luna.sourceStatus.Threads+"；Instagram "+a.luna.sourceStatus.Instagram+"；Bluesky "+a.luna.sourceStatus.Bluesky,
  a.luna.method,...(a.luna.sources||[])]);
 explainCard(host,"TITAN","硬性風險否決",a.titan.status,
  a.titan.veto.length?a.titan.veto.concat(a.titan.notes):[...a.titan.notes,a.titan.warning],a.titan.hardVeto?"deny":"");
 explainCard(host,"NOVA","最後證據整理",a.nova.status,[
  ...a.nova.reasons,a.nova.summary,"研究結果不構成交易允許，所有買賣決定由使用者自行判斷。"],"final");
 for(const item of host.querySelectorAll("a")){if(!/^https:\/\//.test(item.href))item.removeAttribute("href");}
 for(const n of $("candidates").querySelectorAll("button"))n.setAttribute("aria-pressed",String(n.dataset.code===selected));
}
function renderList(){
 const host=$("candidates");host.replaceChildren();if(!current)return;
 const filter=$("filter").value;
 const chosen=current.candidates.filter(c=>filter==="all"||
  filter==="veto"&&c.agents.titan.hardVeto||filter==="wait"&&c.agents.nova.status==="等待確認"||
  filter==="review"&&c.agents.nova.status.startsWith("研究候選"));
 if(!chosen.length){append(host,"div","此條件下沒有候選標的。","empty");return;}
 for(const c of chosen){
  const b=append(host,"button",null,"candidate");b.type="button";b.dataset.code=c.code;
  b.setAttribute("aria-pressed",String(c.code===selected));
  const top=append(b,"div",null,"candidate-top");
  append(top,"span",c.sourceRank+". "+c.code+" "+c.name,"stock");
  append(top,"span",c.agents.titan.hardVeto?"TITAN 否決":c.agents.nova.status,"flag "+(c.agents.titan.hardVeto?"no":"warn"));
  append(b,"div","RS20 "+fmt(c.agents.atlas.rs20,2)+" ｜ ATR "+fmt(c.agents.vega.atrPct,2)+"%","candidate-bottom");
  b.addEventListener("click",()=>detail(c));
 }
 if(!chosen.some(x=>x.code===selected))detail(chosen[0]);
}
function renderSemantic(social){
 const host=$("lunaSemantic");if(!host)return;host.replaceChildren();
 const report=social?.semantic||{},status=report.status||"not_run";
 const labels={verified:"本輪 Gemini API 執行成功",cached:"已核實的模型歷史判讀（本輪沒有重複呼叫）",
  partial:"部分貼文已核實，其他未完成",error:"Gemini 判讀失敗",unavailable:"Gemini 未授權／未能執行",
  empty:"目前沒有符合資格的投資討論",not_run:"資料來源尚未產生語意判讀"};
 append(host,"p","狀態："+(labels[status]||"未驗證")+"｜模型："+(report.model||"缺值")+
  "｜實際呼叫："+(report.inferenceCalls??0)+" 次｜已判讀 "+(report.classifiedCount??0)+
  " 篇／待判讀 "+(report.unclassified??0)+" 篇。","description");
 if(["verified","cached","partial"].includes(status)&&report.noTrade===true)
  append(host,"p","經模型確認的投資立場：偏多 "+(report.bullish??0)+"／偏空 "+(report.bearish??0)+
   "／不明 "+(report.neutral??0)+"（不等於市場共識；非交易訊號）。","small");
 else append(host,"p","目前未確認可用的 Gemini 情緒統計，不以規則結果冒充 AI。","small");
 const allowed=/^https:\/\/(?:www\.ptt\.cc|bsky\.app|(?:www\.)?threads\.(?:net|com)|(?:www\.)?instagram\.com)\//;
 for(const item of (social?.items||[]).filter(x=>x?.semantic?.evidence).slice(0,8)){
  const s=item.semantic;
  const box=append(host,"div",null,"entry");
  append(box,"p",(item.platform||"未知")+"｜"+s.intent+"｜"+s.stance+"｜"+
   s.emotion+"｜信心："+s.confidence,"small");
  append(box,"p","原文依據：「"+s.evidence+"」","description");
  if(typeof item.url==="string"&&allowed.test(item.url)){
   const a=append(box,"a","核對公開原文");a.href=item.url;a.target="_blank";a.rel="noopener noreferrer nofollow";
  }
 }
}
function renderHistory(index){
 const host=$("lunaHistory");if(!host)return;host.replaceChildren();
 if(index?.schema!==1||!Array.isArray(index.days)||!index.days.length){
  append(host,"p","尚無可核對的歷史日檔。","small");return
 }
 append(host,"p","臺灣時間，每日最後一次更新的樣本統計。歷史原文日檔最多保留 30 天，不代表每日貼文總流量。","description");
 for(const day of index.days.slice(0,14)){
  if(!/^20\d{2}-\d{2}-\d{2}$/.test(day.day))continue;
  const box=append(host,"div",null,"entry");
  append(box,"span",day.day+"｜原始 "+day.latestRawSample+"／投資討論 "+
   day.latestInvestmentSample+"｜Gemini "+day.semanticStatus,"small");
  const link=append(box,"a"," 開啟日檔（JSON）");
  link.href="./data/social_sentiment/history/"+day.day+".json";
  link.target="_blank";link.rel="noopener noreferrer";
 }
}
function renderSocialHeat(social){
 const host=$("lunaHeat");if(!host)return;
 host.replaceChildren();
 const stamp=social?.generatedAt?Date.parse(social.generatedAt):NaN;
 const healthy=Array.isArray(social?.items)&&social.items.some(x=>x.investmentEligible!==false&&["ok","partial"].includes(social?.sources?.[x.platform]?.status));
 const fresh=healthy&&Number.isFinite(stamp)&&Date.now()>=stamp&&Date.now()-stamp<=8*3600000;
 const entries=Array.isArray(social?.stockHeat?.stocks)?social.stockHeat.stocks:[];
 const p=append(host,"p",(fresh?"最新可核對來源":"歷史快照／來源可能過期")+
  "｜PTT "+(social?.sources?.PTT?.status||"缺值")+"／Bluesky "+(social?.sources?.Bluesky?.status||"缺值")+"｜資料日 "+(social?.stockHeat?.sourceDate||"缺值")+"｜公開討論 "+
  (social?.social?.investmentDiscussion??social?.social?.originalDiscussion??"缺值")+" 篇、新聞轉載 "+
  (social?.social?.repostedNews??"缺值")+" 篇、非投資話題 "+
  (social?.social?.unrelated??"缺值")+" 篇（原始可查 "+(social?.social?.rawSample??"缺值")+" 篇）。僅追蹤 G 前20名；無樣本不代表沒有討論。","description");
 p.setAttribute("role","status");
 if(!entries.length){append(host,"p","目前沒有可核對的個股提及，未建立熱度排行榜。","small");return}
 for(const x of entries.slice(0,10)){
  if(!/^\d{4}$/.test(String(x.code||""))||!Number.isInteger(x.sample)||x.sample<1)continue;
  const card=append(host,"div",null,"entry");
  append(card,"div",x.code+" "+x.name+"｜近24小時 "+x.recent24h+" 篇／前24小時 "+x.prior24h+" 篇（累計 "+x.sample+"）","small");
  if(fresh&&x.overheatWatch===true&&x.originalDiscussion>=3&&x.recent24h>=3)
   append(card,"p","熱度過熱觀察：價量延伸且有多篇獨立討論；不代表交易訊號。","hint");
  for(const link of (x.links||[]).slice(0,2)){
   if(typeof link.url!=="string"||!/^https:\/\/(?:www\.ptt\.cc|(?:www\.)?threads\.(?:net|com)|(?:www\.)?instagram\.com|bsky\.app)\//.test(link.url))continue;
   const a=append(card,"a",link.platform+"｜"+link.title);
   a.href=link.url;a.target="_blank";a.rel="noopener noreferrer nofollow";
   append(card,"span","　","small");
  }
 }
}
async function loadJson(path){
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),12000);
 try{const r=await fetch(path+(path.includes("?")?"&":"?")+"v="+Date.now(),{cache:"no-store",signal:controller.signal});
  if(!r.ok)throw Error("HTTP "+r.status);return await r.json();
 }finally{clearTimeout(timer)}
}
async function load(){
 $("refresh").disabled=true;$("warning").textContent="正在核對行情、新聞與資料時間；沒有真實資料不會產生假候選。";
 const base="./data/";
 const files=await Promise.allSettled([
  loadJson(base+"latest.json"),loadJson(base+"g_intraday/latest.json"),
  loadJson(base+"g_intraday/status.json"),loadJson(base+"market_events/latest.json"),loadJson(base+"social_sentiment/latest.json")
 ]);
 const errors=files.map((x,i)=>x.status==="rejected"?["正式日榜單","盤中 G","盤中狀態","重大新聞","社群情緒"][i]+"無法讀取":null).filter(Boolean);
 const [daily,intraday,status,news,social]=files.map(x=>x.status==="fulfilled"?x.value:{});
 renderSocialHeat(social);
 renderSemantic(social);
 void loadJson(base+"social_sentiment/history/index.json").then(renderHistory).catch(()=>renderHistory(null));
 const result=core.analyze({daily,intraday,status,news,social},new Date());current=result;
 $("mode").textContent=result.mode;$("asOf").textContent="來源日："+(result.asOfDate||"缺值")+"｜風險日："+(result.source.riskDate||"缺值");
 $("nCandidates").textContent=String(result.counts.candidates);
 $("nVeto").textContent=String(result.counts.veto);
 $("nReview").textContent=String(result.counts.review);
 const reasons=[];
 if(!result.liveVerified)reasons.push("目前不是已驗證的即時盤中研究；歷史數據不得當成當日買進訊號。");
 if(result.marketSession&&!result.liveVerified)reasons.push("盤中 G 不可用："+result.source.gQuality.errors.join("、"));
 if(result.source.riskDate!==result.asOfDate&&result.asOfDate)reasons.push("正式大盤風險日期與候選來源日不同，TITAN 可能否決。");
 if(errors.length)reasons.push("部分來源讀取失敗："+errors.join("、"));
 reasons.push("NOVA 不會推翻 TITAN；新聞關鍵字比對屬探索性，非已證實事件影響。");
 $("warning").textContent=reasons.join(" ");
 selected=null;renderList();
 $("refresh").disabled=false;
}
$("filter").addEventListener("change",renderList);
$("refresh").addEventListener("click",()=>load());
load().catch(e=>{$("warning").textContent="無法完成資料分析："+String(e)+"。所有研究結論暫停。";$("refresh").disabled=false;});
})();