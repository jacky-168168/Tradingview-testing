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
  "來源篇數：PTT "+(a.luna.socialPlatforms?.PTT??0)+"／Threads "+(a.luna.socialPlatforms?.Threads??0)+"／Instagram "+(a.luna.socialPlatforms?.Instagram??0),
  "與此股票名稱／代碼直接相關的 PTT 標題："+(a.luna.socialMentions??"無有效樣本")+" 篇",
  "新聞標題觀察："+a.luna.newsStatus+"（獨立計數，不代表社群討論）",
  "來源：PTT "+a.luna.sourceStatus.PTT+"；Threads "+a.luna.sourceStatus.Threads+"；Instagram "+a.luna.sourceStatus.Instagram,
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