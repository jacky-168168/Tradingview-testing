/* 六代理研究引擎 v0.1｜純資料規則，沒有下單、模型呼叫或策略修改。
 * 來源：既有 G Top20、正式日資料、重大新聞；任何資料缺漏都不會被補成看似真實的事實。
 * Node tests: module.exports; Pages: window.SixAgentResearch.
 */
(function(root,factory){"use strict";const api=factory();if(typeof module!=="undefined"&&module.exports)module.exports=api;else root.SixAgentResearch=api;})(typeof globalThis==="object"?globalThis:this,function(){"use strict";
const HOLIDAYS_2026=new Set("01-01 02-12 02-13 02-16 02-17 02-18 02-19 02-20 02-27 04-03 04-06 05-01 06-19 09-25 09-28 10-09 10-26 12-25".split(" "));
const LIMIT={gMinutes:65,newsHours:48,newsDatasetHours:36,minTotal:1000,minValid:1000,minCoverage:.65,minExchange:.60,riskScore:60,minTurnoverB:.5,maxAtrPct:12};
function numeric(x){return typeof x==="number"&&Number.isFinite(x)?x:null;}
function parseDate(x){if(typeof x!=="string"||!/(?:Z|[+-]\d\d:\d\d)$/.test(x))return null;const t=Date.parse(x);return Number.isFinite(t)?t:null;}
function ageMinutes(s,now){const t=parseDate(s);return t===null?null:(now.getTime()-t)/60000;}
function taipei(now){const p=Object.fromEntries(new Intl.DateTimeFormat("en-US",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",weekday:"short",hourCycle:"h23"}).formatToParts(now).filter(x=>x.type!=="literal").map(x=>[x.type,x.value]));return {date:p.year+"-"+p.month+"-"+p.day,year:Number(p.year),md:p.month+"-"+p.day,weekday:p.weekday,minute:Number(p.hour)*60+Number(p.minute)};}
function session(now){const p=taipei(now);return p.year===2026&&!["Sat","Sun"].includes(p.weekday)&&!HOLIDAYS_2026.has(p.md)&&p.minute>=590&&p.minute<825;}
function legalStocks(rows){return Array.isArray(rows)&&rows.length>=1&&rows.length<=20&&rows.every(x=>x&&/^\d{4}$/.test(String(x.code||"")));}
function qualityCheck(g,status,now){
 const errors=[],p=taipei(now);g=g||{};
 if(g.asOfDate!==p.date)errors.push("不是今日盤中榜單");
 if(g.quality!=="intraday-provisional-allmarket")errors.push("盤中資料品質標籤不符");
 if(!legalStocks(g.rows))errors.push("榜單數量／股票代碼不合法");
 const age=ageMinutes(g.publishedAt,now);
 if(age===null||age<0||age>LIMIT.gMinutes)errors.push("發布時間無效、來自未來或超過65分鐘");
 const c=g.coverage;
 if(!c||numeric(c.total)===null||numeric(c.valid)===null||c.total<LIMIT.minTotal||c.valid<LIMIT.minValid||c.valid/c.total<LIMIT.minCoverage)errors.push("全市場有效報價或涵蓋率不足");
 for(const market of ["上市","上櫃"]){
  const a=c?.exchange?.[market];
  if(!a||numeric(a.total)===null||numeric(a.valid)===null||a.total<500||a.valid/a.total<LIMIT.minExchange)errors.push(market+"報價覆蓋率不足");
 }
 const sTime=parseDate(status?.checkedAt),gTime=parseDate(g.publishedAt);
 if(status?.asOfDate===p.date&&status?.status==="unavailable"&&sTime!==null&&(gTime===null||sTime>gTime))errors.push("較新盤中檢查回報 unavailable");
 return {ok:errors.length===0,errors,ageMinutes:age,coverage:c||null};
}
function textTags(x){return String(x||"").split(/[、,，／/|;；\s]+/).map(t=>t.trim()).filter(t=>t.length>=2&&t.length<=18);}
function eventLinks(row,news,now){
 const matched=[],tags=textTags(row.theme).concat(textTags(row.subIndustry));const hay=[String(row.name||""),...tags];
 const datasetAge=ageMinutes(news?.generatedAt,now);
 const datasetFresh=datasetAge!==null&&datasetAge>=0&&datasetAge<=LIMIT.newsDatasetHours*60;
 if(!datasetFresh)return {status:"資料不足",reason:"新聞資料集未在36小時內同步或時間不明",sources:[],verifiedCount:0,datasetAgeMinutes:datasetAge};
 for(const x of (Array.isArray(news.items)?news.items:[])){
  if(x?.type!=="news")continue;
  const a=ageMinutes(x.publishedAt,now);
  if(a===null||a<0||a>LIMIT.newsHours*60)continue;
  const xtags=(Array.isArray(x.themes)?x.themes:[]).map(String);
  const common=xtags.some(t=>t.length>=2&&hay.some(h=>h.includes(t)||t.includes(h)&&h.length>=3));
  const nameMatch=String(row.name||"").length>=2&&String(x.title||"").includes(String(row.name));
  if(!common&&!nameMatch)continue;
  matched.push({title:String(x.title||""),source:String(x.source||""),url:typeof x.url==="string"&&/^https:\/\//.test(x.url)?x.url:null,publishedAt:x.publishedAt,confirmed:x.confirmed===true});
  if(matched.length===3)break;
 }
 const confirmed=matched.filter(x=>x.confirmed).length;
 return {status:confirmed?"有已核實消息":matched.length?"有相關媒體報導（未證實）":"未找到直接相關新消息",
  reason:matched.length?"相符關鍵字不代表消息造成漲跌；消息與個股關聯仍需人工查核":"未找到近期直接關聯資訊，不推定沒有事件",
  sources:matched,verifiedCount:confirmed,datasetAgeMinutes:datasetAge};
}
function atlas(row,rank){const rs=numeric(row.rs20),rvol=numeric(row.rvol),turnover=numeric(row.turnoverB);
 const signs=[];if(rs!==null&&rs>0)signs.push("RS20 相對市場偏強");
 if(rvol!==null&&rvol>=1.5)signs.push("量比 ≥1.5");
 if(turnover!==null&&turnover>=LIMIT.minTurnoverB)signs.push("成交額達研究門檻");
 return {status:signs.length>=2?"候選":"證據不足",facts:signs,rank,rs20:rs,rvol,turnoverB:turnover,
  note:"沿用原 G 排名，六代理不重新排序正式 Top20。"};
}
function vega(row){const slope=numeric(row.ma20Slope),rs=numeric(row.rs20),atr=numeric(row.atrPct),close=numeric(row.close);
 const positive=slope!==null&&slope>0&&rs!==null&&rs>0,highVol=atr!==null&&atr>LIMIT.maxAtrPct;
 return {status:positive?(highVol?"技術偏多但波動過高":"技術條件偏多"):"技術待確認",
  slope,rs20:rs,atrPct:atr,close,signal:typeof row.signal==="string"?row.signal:null,
  invalidation:"缺少可驗證支撐／壓力與失效價位，不生成虛構的進出場價格。",
  facts:["MA20 斜率："+(slope===null?"缺值":slope.toFixed(2)+"%"),"RS20："+(rs===null?"缺值":rs.toFixed(2)),
  "ATR%："+(atr===null?"缺值":atr.toFixed(2)+"%")]};
}
function luna(risk,social,now,row){const score=numeric(risk?.score),breadth=numeric(risk?.breadth),ret20=numeric(risk?.ret20);
 const status=score===null?"資料不足":score<26?"極度偏空":score<60?"偏空觀察":score<80?"中性偏強":"偏強";
 const age=ageMinutes(social?.generatedAt,now),fresh=age!==null&&age>=0&&age<=8*60;
 const feeds=social?.sources||{};
 const domains={PTT:/^https:\/\/www\.ptt\.cc\//,Threads:/^https:\/\/(?:www\.)?threads\.(?:net|com)\//,
  Instagram:/^https:\/\/(?:www\.)?instagram\.com\//,Bluesky:/^https:\/\/bsky\.app\/profile\/[^/]+\/post\/[a-zA-Z0-9]+$/};
 const posts=(Array.isArray(social?.items)?social.items:[]).filter(x=>{
  const a=ageMinutes(x?.publishedAt,now);
  return x&&typeof x.title==="string"&&x.title.length>=4&&typeof x.url==="string"&&
    domains[x.platform]?.test(x.url)&&x.investmentEligible!==false&&a!==null&&a>=0&&a<=48*60;});
 // Real publicly traceable posts count from the first post. No minimum sample threshold.
 const sample=posts.length,bull=posts.filter(x=>x.stance==="偏多").length,bear=posts.filter(x=>x.stance==="偏空").length;
 const signal=sample===0?"尚無可核對的社群討論":
  bull>bear?"已有樣本｜偏多內容較多":bear>bull?"已有樣本｜偏空內容較多":
  bull+bear===0?"已有樣本｜尚無明確多空方向":"已有樣本｜多空內容接近";
 const currentEvidence=posts.some(x=>["ok","partial"].includes(feeds[x.platform]?.status));
 const socialStatus=sample&&fresh&&currentEvidence?signal:sample?"已有歷史樣本｜來源未在8小時內更新或已失聯":signal;
 const semanticRaw=social?.semantic||{};
 const semanticVerified=["verified","cached","partial"].includes(semanticRaw.status)&&semanticRaw.noTrade===true;
 const semanticSummary=semanticVerified?{status:semanticRaw.status,model:semanticRaw.model,
  classified:semanticRaw.classifiedCount??0,investment:semanticRaw.investmentCount??0,
  bullish:semanticRaw.bullish??0,bearish:semanticRaw.bearish??0,neutral:semanticRaw.neutral??0,
  inferenceCalls:semanticRaw.inferenceCalls??0}:{status:semanticRaw.status||"not_run",classified:0};
 const examples=posts.slice(0,3).map(x=>({title:x.title,url:x.url,
  source:x.platform+"（公開貼文標題）",publishedAt:x.publishedAt}));
 const name=String(row?.name||""),code=String(row?.code||"");
 const mentions=posts.filter(x=>(/^\d{4}$/.test(code)&&new RegExp("(^|\\D)"+code+"(?!\\d)").test(x.title))||
  (name.length>=2&&x.title.includes(name))).length;
 const creatorMedia=Array.isArray(social?.creatorMedia)?social.creatorMedia:[];
 const creatorCounts={YouTube:creatorMedia.filter(x=>x.platform==="YouTube").length,
  Facebook:creatorMedia.filter(x=>x.platform==="Facebook").length};
  const heat=(Array.isArray(social?.stockHeat?.stocks)?social.stockHeat.stocks:[]).find(x=>x.code===code&&x.name===name);
 const heatCount=heat&&Number.isInteger(heat.recent24h)&&heat.recent24h>=0?heat.recent24h:null;
 const corroborated=heat&&heat.sample<=posts.length&&heatCount!==null&&mentions>=heatCount;
 const sourceHealthy=["PTT","Threads","Instagram","Bluesky"].some(k=>["ok","partial"].includes(feeds[k]?.status));
 const overheatWatch=Boolean(fresh&&sourceHealthy&&corroborated&&heat.overheatWatch===true&&
   heat.originalDiscussion>=3&&heatCount>=3);
 const heatStatus=overheatWatch?"社群過熱觀察：討論升溫且價量延伸，警惕追高（非買賣訊號）":
  corroborated&&fresh&&sourceHealthy?"可核對近24小時提及 "+heatCount+" 篇（僅 G 候選標題）":
  corroborated?"已有歷史樣本，來源未確認":"熱度不足／尚未驗證";
 return {status,score,breadth,ret20,method:"只要有1篇可核對公開貼文就視為已有樣本；資料量少僅代表少量觀察，不可推論市場共識。社群不修改 Risk Score 或 TITAN 風控。",
  socialStatus,socialSample:sample?sample:null,socialBull:sample?bull:null,socialBear:sample?bear:null,
  socialMentions:sample?mentions:null,semanticSummary,creatorCounts,heatStatus,overheatWatch,socialPlatforms:sample?{
   PTT:posts.filter(x=>x.platform==="PTT").length,
   Threads:posts.filter(x=>x.platform==="Threads").length,
   Instagram:posts.filter(x=>x.platform==="Instagram").length,
   Bluesky:posts.filter(x=>x.platform==="Bluesky").length}:null,newsStatus:fresh?String(social?.news?.status||"未取得"):"新聞情緒資料未確認",
  sources:examples,sourceStatus:{PTT:feeds.PTT?.status||"not_available",Threads:feeds.Threads?.status||"not_authorized",
   Instagram:feeds.Instagram?.status||"not_authorized",Bluesky:feeds.Bluesky?.status||"not_available",
   YouTube:feeds.YouTube?.status||"not_configured",Facebook:feeds.Facebook?.status||"not_authorized"},socialAgeMinutes:age};
}
function titan(row,context){const veto=[],info=[];
 const risk=context.risk;
 if(!risk||numeric(risk.score)===null)veto.push("缺少有效大盤風險分數");
 else if(risk.score<LIMIT.riskScore)veto.push("大盤風險分數低於60");
 if(!context.marketReady)veto.push("盤中資料品質不符或不是可確認的即時盤中快照");
 if(!context.sameRiskDate)veto.push("市場風險與候選資料日期未對齊");
 if(numeric(row.atrPct)===null)veto.push("缺少 ATR 波動率資料");
 else if(row.atrPct>LIMIT.maxAtrPct)veto.push("ATR% 超過研究上限12%");
 if(numeric(row.turnoverB)===null)veto.push("缺少成交額");
 else if(row.turnoverB<LIMIT.minTurnoverB)veto.push("成交額不足");
 info.push("缺少帳戶持倉與槓桿資料，不能推估可交易部位或實際最大虧損");
 info.push("失效價位未經確認，不能計算真實 R 值");
 return {status:veto.length?"否決":"通過資料前置閘門",veto,notes:info,hardVeto:veto.length>0,
  warning:"通過研究前置閘門不代表可以下單，須另經人工風險審核。"};
}
function nova(parts){const reasons=[];
 if(parts.titan.hardVeto)reasons.push("TITAN 硬性否決："+parts.titan.veto.join("；"));
 if(parts.atlas.status!=="候選")reasons.push("ATLAS 候選證據不足");
 if(parts.vega.status!=="技術條件偏多")reasons.push("VEGA 尚有技術或波動限制");
 if(parts.orion.verifiedCount===0)reasons.push("ORION 未取得可驗證的個股第一手消息");
 if(parts.luna.status==="資料不足")reasons.push("LUNA 市場情緒代理資料不足");
 const state=parts.titan.hardVeto?"拒絕／僅回顧":reasons.length?"等待確認":"研究候選（待人工審核）";
 return {status:state,reasons,summary:reasons.length?reasons.slice(0,3).join("；"):"研究閘門通過，仍須確認失效點、曝險與資料時效",noTrade:true};
}
function analyze(input,nowInput){
 const now=nowInput instanceof Date?nowInput:new Date(),daily=input?.daily||{},intraday=input?.intraday||{},news=input?.news||{},social=input?.social||{},status=input?.status||{},orion=input?.orion||{};
 const trading=session(now),p=taipei(now),q=qualityCheck(intraday,status,now);
 const dailyDate=typeof daily.dataDate==="string"?daily.dataDate:null;
 const useLive=trading&&q.ok;
 const rows=useLive?intraday.rows:Array.isArray(daily?.models?.G)?daily.models.G:[];
 const asOfDate=useLive?intraday.asOfDate:dailyDate;
 const mode=useLive?"盤中暫估":trading?"盤中資料未通過，僅歷史回顧":"休市／非盤中時段，歷史研究快照";
 const candidateRows=rows.filter(x=>x&&/^\d{4}$/.test(String(x.code||""))).slice(0,10);
 const marketReady=useLive;
 const risk=daily.risk||null;
 const newsAge=ageMinutes(orion.generatedAt,now),isFreshNews=newsAge!==null&&newsAge>=0&&newsAge<=8*60;
 const verifiedNews=isFreshNews&&orion.semantic?.noTrade===true&&["verified","cached","partial"].includes(orion.semantic?.status);
 const newsroom=verifiedNews?{
  positive:orion.semantic.positive||0,negative:orion.semantic.negative||0,
  neutral:orion.semantic.neutral||0,classified:orion.semantic.classified||0,
  sourceCount:orion.semantic.sourceCount||0,
  status:orion.semantic.status,
  caution:"Gemini 僅分析報導標題，不能推論股價或散戶情緒"}:null;
 const sameRiskDate=!!(risk&&risk.date===(useLive?intraday.sourceCloseDate:asOfDate));
 const candidates=candidateRows.map((row,i)=>{
  const parts={atlas:atlas(row,i+1),vega:vega(row),orion:{...eventLinks(row,news,now),newsroom},luna:luna(risk,social,now,row)};
  parts.titan=titan(row,{risk,marketReady,sameRiskDate});
  parts.nova=nova(parts);
  return {code:String(row.code),name:String(row.name||row.code),market:String(row.market||""),price:numeric(row.close),theme:String(row.theme||""),
   sourceRank:i+1,asOfDate,agents:parts};
 });
 return {version:"six-agent-rule-v0.1",checkedAt:now.toISOString(),taipeiDate:p.date,asOfDate,mode,marketSession:trading,
   liveVerified:useLive,source:{gPublishedAt:intraday.publishedAt||null,gQuality:q,officialDataDate:dailyDate,riskDate:risk?.date||null,
   riskScore:numeric(risk?.score),newsGeneratedAt:news.generatedAt||null,socialGeneratedAt:social.generatedAt||null},
   candidates,counts:{candidates:candidates.length,veto:candidates.filter(x=>x.agents.titan.hardVeto).length,
   review:candidates.filter(x=>x.agents.nova.status==="研究候選（待人工審核）").length},
   policy:"僅供研究；不下單、不重排原 G 榜單。無當日有效報價、風險日期不一致或缺少失效點時不可輸出交易許可。"};
}
return {analyze,session,taipei,qualityCheck,eventLinks,atlas,vega,luna,titan,nova,LIMIT};
});
