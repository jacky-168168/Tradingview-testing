(function(){
"use strict";
const $=id=>document.getElementById(id);
const esc=x=>String(x==null?"":x).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const NEWS="./data/market_events/latest.json", HISTORY_URL="./data/news_impact/history.json", SCORECARD_URL="./data/news_impact/scorecard.json";
const VERSION="2026-11-09-v1.3";
const assets=["美股S&P500","NASDAQ","台股","台股記憶體供應端","AI／半導體設備","雲端算力租賃","天然氣價格","黃金","白銀","WTI原油","美元","美債殖利率","銅","紐元NZD","港幣HKD","農產品期貨","加密資產"];
const rules=[
{id:"war-up",name:"地緣衝突升溫",re:/\b(escalat(?:e|es|ion)|airstrikes?|missile (?:attack|strike)|invad(?:e|es|ed)|military strikes?|attacks? on oil|strait of hormuz (?:clos|block))\b|戰爭升級|軍事攻擊|空襲|飛彈襲擊|荷姆茲海峽封鎖|衝突升溫/i,impact:{"美股S&P500":-50,"NASDAQ":-55,"台股":-55,"黃金":65,"白銀":30,"WTI原油":40,"美元":25,"美債殖利率":-10},why:"避險需求可能增加；若實際波及產油、航運，油價上行風險提高。",caveat:"政治聲明不等於實際供應中斷"},
{id:"war-down",name:"停火與緊張緩和",re:/\b(ceasefire (?:deal|agreed|agreement|takes effect)|peace deal|de[- ]escalat(?:ion|es|ed))\b|停火協議|達成停火|和平協議|緊張緩和/i,impact:{"美股S&P500":45,"NASDAQ":45,"台股":40,"黃金":-40,"白銀":-20,"WTI原油":-35,"美元":-15},why:"風險溢價可能下降，避險資產與地緣油價溢價可能回落。",caveat:"若停火未落實，方向可能立即反轉"},
{id:"rate-hawk",name:"利率偏鷹／升息",re:/\b(rate hikes?|hike rates|higher for longer|hawkish|fed (?:raises|raised) rates|bond yields? (?:surge|jump))\b|升息|偏鷹|利率維持高檔|公債殖利率飆升/i,impact:{"美股S&P500":-45,"NASDAQ":-65,"台股":-50,"黃金":-45,"白銀":-40,"WTI原油":-25,"美元":55,"美債殖利率":55},why:"折現率提高通常壓抑成長股與無息資產；美元可能受支撐。",caveat:"若早已充分預期，當日行情可能相反"},
{id:"rate-dove",name:"降息／偏鴿",re:/\b(rate cuts?|cut rates|dovish|easing cycle|fed (?:cuts|cut) rates|bond yields? (?:fall|drop))\b|降息|偏鴿|寬鬆政策|殖利率下滑/i,impact:{"美股S&P500":40,"NASDAQ":60,"台股":45,"黃金":45,"白銀":40,"WTI原油":10,"美元":-45,"美債殖利率":-55},why:"利率下降可能支撐風險資產與黃金，但若因衰退而降息則不一定利多股票。",caveat:"必須區分預防式降息與衰退式降息"},
{id:"cpi-hot",name:"通膨高於預期",re:/\b(inflation (?:accelerat|surge|jump|hotter|higher than expected)|cpi (?:hotter|above expectations|surprises? to the upside))\b|通膨升溫|通膨高於預期|CPI高於預期/i,impact:{"美股S&P500":-45,"NASDAQ":-60,"台股":-45,"黃金":-20,"白銀":-20,"WTI原油":5,"美元":40,"美債殖利率":55},why:"更高的通膨意外可能推升升息預期、殖利率及美元。",caveat:"黃金的抗通膨敘事可能與實質利率影響相抵"},
{id:"cpi-cool",name:"通膨低於預期",re:/\b(inflation (?:cools?|slows?|eases?|lower than expected)|cpi (?:cooler|below expectations))\b|通膨降溫|通膨低於預期|CPI低於預期/i,impact:{"美股S&P500":40,"NASDAQ":55,"台股":40,"黃金":40,"白銀":30,"WTI原油":0,"美元":-35,"美債殖利率":-50},why:"通膨壓力減輕可能降低緊縮預期，支持股債與黃金。",caveat:"需同時看景氣是否急速下滑"},
{id:"oil-cut",name:"產油供給收縮",re:/\b(opec\+?.{0,35}(?:cut|reduce)|oil output cuts?|production cuts?|supply disruption|oil supply (?:falls?|tightens?))\b|OPEC.{0,15}減產|原油減產|原油供應中斷|油田停產/i,impact:{"美股S&P500":-20,"NASDAQ":-20,"台股":-25,"黃金":15,"WTI原油":80},why:"供應收縮推升油價的機率較高，卻可能增加企業能源成本。",caveat:"實際漲跌受庫存及需求左右"},
{id:"oil-up",name:"石油增產／供應恢復",re:/\b(opec\+?.{0,35}(?:increase|boost|raise)|oil output (?:rises?|increases?)|production (?:increase|hike)|oil supply resumes)\b|OPEC.{0,15}增產|原油增產|原油恢復供應/i,impact:{"美股S&P500":15,"NASDAQ":15,"台股":20,"WTI原油":-70},why:"供應增多通常對原油價格造成下行壓力。",caveat:"旺季需求仍可能蓋過供給影響"},
{id:"trade-tight",name:"關稅與出口限制升級",re:/\b(tariffs? (?:raised|increased|hiked|imposed)|new tariffs?|export ban|chip export restrictions?|trade war escalat)\b|加徵關稅|提高關稅|晶片出口管制|出口禁令|貿易戰升級/i,impact:{"美股S&P500":-35,"NASDAQ":-55,"台股":-60,"黃金":35,"美元":15,"銅":-35},why:"供應鏈不確定性與企業成本增加可能影響台股科技、美國成長股。",caveat:"個別受保護企業可能受惠"},
{id:"trade-ease",name:"關稅撤銷／貿易緩和",re:/\b(tariffs? (?:removed|reduced|lifted)|trade deal reached|export restrictions? (?:eased|lifted))\b|取消關稅|降低關稅|貿易協議達成|放寬出口管制/i,impact:{"美股S&P500":35,"NASDAQ":50,"台股":55,"黃金":-15,"銅":30},why:"全球供應鏈成本與地緣交易摩擦可能下降。",caveat:"應查核協議是否實際生效"},
{id:"demand-fall",name:"景氣／需求下滑",re:/\b(recession fears?|economy contracts?|manufacturing slump|demand collapses?|weak demand|unemployment (?:surges?|jumps?))\b|經濟衰退|需求萎縮|製造業萎縮|失業率飆升|需求疲弱/i,impact:{"美股S&P500":-55,"NASDAQ":-50,"台股":-55,"黃金":25,"WTI原油":-55,"銅":-60,"美債殖利率":-40},why:"總需求下降常壓抑股市、油價與工業金屬。",caveat:"黃金反應取決於美元與實質利率"},
{id:"demand-rise",name:"景氣／需求轉強",re:/\b(industrial production (?:surges?|rebounds?)|manufacturing rebounds?|demand recovery|economic growth accelerates?)\b|景氣回升|需求復甦|製造業回升|經濟成長加速/i,impact:{"美股S&P500":35,"NASDAQ":30,"台股":40,"WTI原油":35,"銅":55,"美債殖利率":20},why:"需求改善有利風險資產、能源與工業金屬。",caveat:"若引發利率上升，成長股可能反而受壓"}
];
let DATA=[],HISTORY=null,PROVENANCE={},ASSET="全部",REGION="全部",STATUS="全部",HOURS=48,SEARCH="";
function sourceTypeOf(n){
 const source=String(n.source||"");
 if(n.originType==="forum_repost"||/PTT|論壇|reddit/i.test(source))return "論壇／轉載（不代表原始消息）";
 if(/Yahoo新聞|Google News|新聞聚合/i.test(source))return "聚合平台（需核對原始媒體）";
 if(/Federal Reserve|Federal Reserve Board|U\.S\. Energy Information Administration|\bEIA\b|Bureau of Labor Statistics|\bBLS\b|中央銀行|經濟部|證交所/i.test(source))return "官方發布來源（仍需核對原文）";
 if(n.originType==="foreign_original")return "國際媒體原始報導（未獨立查核）";
 return "媒體報導（未獨立查核）";
}
function classify(n){
 const title=String(n.title||"");
 // Headlines such as "Fed will not hike" or "attack unlikely" must not
 // produce the opposite of their literal meaning via simple keyword hits.
 const negated=/\b(?:not|no|unlikely|denies|deny|rules out|won't|without)\b|不會|未將|否認|沒有|並未|排除|不再/i.test(title);
 const root=typeof window==="object"?window:globalThis;
 const extra=root.NewsImpactSector?root.NewsImpactSector.examine(n):{rules:[],observations:[]};
 const taxonomy=root.NewsImpactTaxonomy?root.NewsImpactTaxonomy.examine(n):{topics:[],rules:[],observations:[],flags:[]};
 // "升息預期降溫" does not mean an actual Fed rate hike.
 // Similarly forecasts/concerns/press speculation must not be upgraded to actual policy actions.
 const hikeNotConfirmed=/(?:升息|加息).{0,16}(?:預期|疑慮|押注|機率|料將|可能|恐|炸彈|降溫|兩難|討論|猜測)|(?:預期|押注|疑慮|恐|兩難).{0,14}(?:升息|加息)|hike bets|hike expectations|not confirmed/i.test(title);
 const oldHits=negated?[]:rules.filter(r=>r.re.test(title)&&!(r.id==="rate-hawk"&&hikeNotConfirmed)&&!(r.id==="rate-dove"&&/降息.{0,12}(?:押注|預期|疑慮|傳出|可能|恐)/.test(title)));
 const hits=[...oldHits,...extra.rules,...taxonomy.rules];
 const observations=[...(extra.observations||[])];
 for(const o of taxonomy.observations||[])if(!observations.some(x=>x.asset===o.asset))observations.push(o);
 const topics=taxonomy.topics||[];
 const flags=taxonomy.flags||[];
 const topicEvidence=taxonomy.topicEvidence||"none";
 const scores={};for(const a of assets)scores[a]=[];
 for(const r of hits)for(const [a,v] of Object.entries(r.impact||{}))if(v&&scores[a])scores[a].push(v);
 const impacts=Object.entries(scores).filter(([a,values])=>values.length).map(([asset,values])=>{
 const pos=values.some(v=>v>0),neg=values.some(v=>v<0),mixed=pos&&neg;
 const score=mixed?0:Math.max(-100,Math.min(100,Math.round(values.reduce((a,b)=>a+b,0)/values.length)));
 return {asset,score,mixed,label:mixed?"方向衝突":score>0?"偏多":"偏空"};
 }).sort((a,b)=>Math.abs(b.score)-Math.abs(a.score));
 const speculative=/\b(could|may|might|if|plan|proposal|consider|warn|rumor|rumour|opinion|predict|expects?|likely|unlikely)\b|可能|傳聞|疑慮|恐|擬|計畫|研議|或將|傳出|預測|？|\?/i.test(title);
 const opinion=/\bopinion\b|評論|社論/i.test(title);
 return {...n,hits,impacts,observations,topics,flags,topicEvidence,speculative,opinion,negated,sourceType:sourceTypeOf(n),classifierVersion:VERSION};
}
function elapsed(n){const t=Date.parse(n.publishedAt||"");return Number.isFinite(t)?(Date.now()-t)/3600000:Infinity}
function visible(n){
 if(elapsed(n)<-1||elapsed(n)>HOURS)return false;
 if(REGION==="國際"&&n.originType!=="foreign_original")return false;
 if(REGION==="國內"&&n.originType==="foreign_original")return false;
 if(ASSET!=="全部"&&!n.impacts.some(x=>x.asset===ASSET)&&!n.observations.some(x=>x.asset===ASSET))return false;
 if(STATUS==="可推估方向"&&!n.impacts.length)return false;
 if(STATUS==="已報導行情"&&!n.observations.length)return false;
 if(STATUS==="事件有分類、方向未知"&&(n.impacts.length||!(n.topics.length||n.hits.length)))return false;
 if(STATUS==="未識別"&&(n.topics.length||n.hits.length||n.observations.length))return false;
 const q=SEARCH.trim().toLowerCase();return !q||[n.title,n.source,n.category,...n.topics,...n.hits.map(h=>h.name)].join(" ").toLowerCase().includes(q)
}
function badge(a){const cls=a.mixed?"mixed":a.score>0?"bull":"bear";return '<span class="signal '+cls+'">'+esc(a.asset)+' '+(a.mixed?"多空衝突":a.score>0?"+":"")+a.score+'</span>'}
function observedBadge(o){return '<span class="signal mixed">'+esc(o.asset)+"｜"+esc(o.label)+"（非預測）"+'</span>'}
function historyOf(n){
 if(!HISTORY||!Array.isArray(HISTORY.events))return "";
 const x=HISTORY.events.find(e=>e.id===n.id);if(!x)return "";
 let verified=Object.entries(x.realized||{}).flatMap(([asset,frames])=>Object.entries(frames||{}).filter(([k,v])=>v!=null&&Number.isFinite(v)).map(([k,v])=>asset+" "+k+": "+(v>0?"+":"")+v.toFixed(2)+"%"));
 return verified.length?'<div class="reality">已實現價格後續報酬（非因果證明）｜'+esc(verified.slice(0,6).join("　"))+'</div>':"";
}
function eventCard(n){
 const type=n.hits.length?n.hits.map(r=>r.name).join("／"):n.topics.length?"事件主題可識別／方向待確認":"尚無足夠事件規則";
 const certainty=n.impacts.length?(n.speculative||n.opinion||n.flags.length?"低｜含傳聞／評論／預期":"有限｜條件式標題規則，非歷史勝率"):n.hits.length?"已辨識事件，但未有足夠證據判方向":n.topicEvidence==="source_category_only"?"僅沿用來源分類，標題證據不足":n.topics.length?"可辨識主題，但不足以推估市場方向":"目前不足以判讀";
 const explain=n.hits.length?[...new Set(n.hits.map(r=>r.why))].join(" "):n.observations.length?"標題描述已發生的商品／匯率變動，只能作行情觀察，尚不能推論之後會延續或反轉。":n.topics.length?"目前能辨識主題，但尚缺政策實施、供需衝擊、財報預期差或可比價格資訊，不能直接判利多空。":n.negated?"標題具有否定語境，暫不自動判多空。":"目前標題無明確市場傳導依據，不能可靠判斷方向。";
 const caveats=n.hits.length?[...new Set(n.hits.map(r=>r.caveat))].join("；"):"需核對原文、預期差與實際行情";
 const time=String(n.publishedAt||n.date||"").replace("T"," ").slice(0,16);
 const url=/^https:\/\//.test(n.url||"")?n.url:"#";
 const topicLine=n.topics.length?'<div class="topicline">主題：'+esc(n.topics.join("／"))+(n.topicEvidence==="source_category_only"?"（僅來源分類）":"")+'</div>':"";
 return '<article class="article"><div class="item-top"><span>'+esc(n.originType==="foreign_original"?"🌍 國際":"🇹🇼 國內／其他")+'</span><span>'+esc(time)+'（台灣）</span></div>'+
 '<h3><a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(n.title)+'</a></h3>'+
 '<div class="source">'+esc(n.source||"來源不明")+' · '+esc(n.sourceType)+' · '+esc(n.category||"")+" · "+esc(type)+'</div>'+topicLine+
 '<div class="signals">'+(n.impacts.length?n.impacts.slice(0,9).map(badge).join(""):n.hits.length?'<span class="signal mixed">事件已辨識｜方向尚未確定</span>':n.observations.length?'<span class="signal mixed">已報導行情（非預測）</span>':n.topics.length?'<span class="signal mixed">主題已分類｜方向待確認</span>':'<span class="signal mixed">未判定利多利空</span>')+(n.observations||[]).map(observedBadge).join("")+'</div>'+
 '<div class="reason"><b>推估傳導：</b>'+esc(explain)+'</div><div class="caveat">可信程度：'+esc(certainty)+'｜反向條件：'+esc(caveats)+'</div>'+
 historyOf(n)+'</article>'
}
function render(){
 const filtered=DATA.filter(visible).sort((a,b)=>String(b.publishedAt||"").localeCompare(String(a.publishedAt||"")));
 const matched=filtered.filter(n=>n.hits.length||n.topics.length||n.observations.length);
 const directional=filtered.filter(n=>n.impacts.length);
 const observedCount=filtered.filter(n=>n.observations.length).length;
 $("count").textContent="近 "+HOURS+" 小時 "+filtered.length+" 則｜"+matched.length+" 則主題／事件可辨識｜"+directional.length+" 則有條件式方向｜"+observedCount+" 則有新聞已報導行情（非預測）";
 $("articles").innerHTML=filtered.length?filtered.slice(0,100).map(eventCard).join(""):'<div class="empty">所選期間或條件沒有符合的新聞。可放寬篩選條件。</div>';
 const rows=assets.map(asset=>{
 const events=matched.flatMap(n=>n.impacts.filter(x=>x.asset===asset).map(x=>({n,...x})));
 const observed=filtered.reduce((k,n)=>k+n.observations.filter(o=>o.asset===asset).length,0);
 if(!events.length)return {asset,score:null,count:0,observed,conflicts:0};
 const net=events.reduce((s,e)=>s+e.score,0)/events.length;
 return {asset,score:Math.round(net),count:events.length,observed,conflicts:events.filter(e=>e.mixed).length};
 });
 $("assetSummary").innerHTML=rows.map(r=>{
 const label=r.score==null?(r.observed?"僅有已報導行情，無未來預測":"無判斷依據"):r.score>0?"偏多":r.score<0?"偏空":"方向相抵";
 const klass=r.score==null?"":r.score>0?"up":r.score<0?"down":"";
 return '<button class="asset '+klass+(ASSET===r.asset?" selected":"")+'" data-asset="'+esc(r.asset)+'"><span>'+esc(r.asset)+'</span><strong>'+(r.score==null?"—":(r.score>0?"+":"")+r.score)+'</strong><small>'+esc(label)+' · '+r.count+' 則有方向'+(r.observed?' · '+r.observed+' 則已報導行情':'')+'</small></button>';
 }).join("");
 $("assetSummary").querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{ASSET=ASSET===b.dataset.asset?"全部":b.dataset.asset;$("asset").value=ASSET;render()}));
 let text="新聞來源更新："+(PROVENANCE.generatedAt||"未知")+" ｜新聞資料狀態："+(PROVENANCE.status||"未知");
 if(Date.now()-Date.parse(PROVENANCE.generatedAt||"")>12*3600000)text+="｜⚠ 新聞可能過期";
 if(HISTORY&&HISTORY.generatedAt)text+=" ｜歷史驗證更新："+HISTORY.generatedAt;
 $("meta").textContent=text;
 const verified=HISTORY&&Array.isArray(HISTORY.events)?HISTORY.events.reduce((n,e)=>n+Object.values(e.realized||{}).filter(f=>Object.values(f).some(v=>v!=null)).length,0):0;
 $("research").textContent=verified?"已累積 "+verified+" 筆資產／事件價格驗證（不等於獨立事件筆數；僅描述後續報酬）。":"歷史價格樣本尚未建立或尚未成熟；目前不提供虛構勝率。";
}
async function boot(){
 try{
 const r=await fetch(NEWS+"?t="+Date.now(),{cache:"no-store"});
 if(!r.ok)throw Error("HTTP "+r.status);
 const j=await r.json();if(!Array.isArray(j.items))throw Error("Invalid news schema");
 PROVENANCE=j;
 const seen=new Set();
 DATA=j.items.filter(n=>n.type==="news"&&n.title&&n.url).filter(n=>{const k=(n.title||"").toLowerCase().replace(/\s+/g," ").trim();if(seen.has(k))return false;seen.add(k);return true}).map(classify);
 try{const h=await fetch(HISTORY_URL+"?t="+Date.now(),{cache:"no-store"});if(h.ok)HISTORY=await h.json()}catch(_){}
 render();
 try{
  const response=await fetch(SCORECARD_URL+"?t="+Date.now(),{cache:"no-store"});
  if(!response.ok)throw Error("HTTP "+response.status);
  const sc=await response.json();if(!sc.audit||!Array.isArray(sc.byAsset))throw Error("無有效驗證資料");
  $("scorecardSummary").textContent="已凍結方向紀錄 "+(sc.predictionRecords||0)+" 則｜已成熟資產／期間觀測 "+sc.audit.maturedObservationCount+" 筆｜待成熟 "+sc.audit.pendingHorizonCount+" 筆。"+(sc.status==="insufficient_matured_signals"?"目前尚無足量可公布的預測勝率；不使用歷史日期冒充訓練結果。":"查看逐資產信賴區間與已成熟結果。");
 }catch(e){$("scorecardSummary").textContent="前瞻預測驗證紀錄尚不可用；可至獨立驗證頁查看。"}
 }catch(e){$("meta").textContent="新聞資料載入失敗："+e.message;$("articles").innerHTML='<div class="empty">資料暫時無法取得，請確認原新聞工作流程。</div>';}
}
if(typeof module==="object"&&module.exports){module.exports={classify,VERSION,assets};return;}
$("asset").addEventListener("change",e=>{ASSET=e.target.value;render()});
$("region").addEventListener("change",e=>{REGION=e.target.value;render()});
$("hours").addEventListener("change",e=>{HOURS=Number(e.target.value);render()});
$("query").addEventListener("input",e=>{SEARCH=e.target.value;render()});
$("recognition").addEventListener("change",e=>{STATUS=e.target.value;render()});
$("refresh").addEventListener("click",boot);
boot();
})();