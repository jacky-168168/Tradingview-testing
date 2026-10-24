const assert=require("node:assert/strict"),test=require("node:test");
const fs=require("node:fs"),path=require("node:path");
const core=require("../docs/agent-research-core.js");
const docs=path.resolve(__dirname,"../docs");
const when=s=>new Date(s);
const LIVE=when("2026-10-22T03:00:00Z"); // 11:00 Taipei trading day
const row=(code="2330")=>({code,name:"台積電",market:"上市",close:1500,rs20:22.5,
 ma20Slope:2.2,turnoverB:30,rvol:2,atrPct:3,signal:"G 突破",theme:"半導體、晶圓代工",subIndustry:"半導體"});
function fixtures(now=LIVE){
 const nowStr=new Date(now.getTime()-20*60000).toISOString();
 return {
  daily:{dataDate:"2026-10-21",risk:{date:"2026-10-21",score:75,breadth:60,ret20:3},models:{G:[row()]}},
  intraday:{asOfDate:"2026-10-22",quality:"intraday-provisional-allmarket",
   publishedAt:nowStr,sourceCloseDate:"2026-10-21",rows:[row()],
   coverage:{valid:1690,total:1984,exchange:{"上市":{valid:980,total:1091},"上櫃":{valid:710,total:893}}}},
  status:{asOfDate:"2026-10-22",status:"ok",checkedAt:nowStr},
  news:{generatedAt:nowStr,status:"ok",items:[
   {type:"news",title:"台積電發表新製程",publishedAt:nowStr,confirmed:false,source:"媒體",url:"https://example.com/article",themes:["半導體"]},
   {type:"event",title:"舊展覽",date:"2026-10-20",confirmed:true,themes:["半導體"]}]}
 };
}
test("session respects holidays, weekend, 09:50 and 13:45 boundaries",()=>{
 assert.equal(core.session(LIVE),true);
 assert.equal(core.session(when("2026-10-22T01:49:00Z")),false);
 assert.equal(core.session(when("2026-10-22T05:45:00Z")),false);
 assert.equal(core.session(when("2026-10-24T03:00:00Z")),false);
 assert.equal(core.session(when("2026-10-26T03:00:00Z")),false);
 assert.equal(core.session(when("2027-02-02T03:00:00Z")),false);
});
test("healthy intraday data yields six named agents, no auto trading",()=>{
 const out=core.analyze(fixtures(),LIVE);
 assert.equal(out.liveVerified,true);
 assert.equal(out.mode,"盤中暫估");
 assert.equal(out.candidates.length,1);
 const c=out.candidates[0];
 assert.deepEqual(Object.keys(c.agents),["atlas","vega","orion","luna","titan","nova"]);
 assert.equal(c.agents.titan.hardVeto,false);
 assert.equal(c.agents.orion.verifiedCount,0);
 assert.equal(c.agents.nova.status,"等待確認");
 assert.equal(c.agents.nova.noTrade,true);
});
test("risk veto cannot be overruled by positive charts or news",()=>{
 const data=fixtures();data.daily.risk.score=11;
 const c=core.analyze(data,LIVE).candidates[0];
 assert.equal(c.agents.atlas.status,"候選");
 assert.equal(c.agents.titan.hardVeto,true);
 assert.equal(c.agents.nova.status,"拒絕／僅回顧");
 assert.match(c.agents.nova.summary,/TITAN/);
});
test("intraday unavailable newer than success is blocked",()=>{
 const x=fixtures();x.status={asOfDate:"2026-10-22",status:"unavailable",checkedAt:LIVE.toISOString()};
 const out=core.analyze(x,LIVE);
 assert.equal(out.liveVerified,false);
 assert.ok(out.source.gQuality.errors.some(s=>s.includes("unavailable")));
 assert.ok(out.candidates.every(c=>c.agents.titan.hardVeto));
});
test("coverage and invalid stock code cause fail-closed fallback",()=>{
 const x=fixtures();x.intraday.coverage.valid=990;
 assert.equal(core.analyze(x,LIVE).liveVerified,false);
 const z=fixtures();z.intraday.rows=[{...row(),code:"ZZZZ"}];
 assert.equal(core.analyze(z,LIVE).liveVerified,false);
 const y=fixtures();y.intraday.coverage.exchange["上櫃"].valid=200;
 assert.equal(core.analyze(y,LIVE).liveVerified,false);
});
test("future or old timestamp must not be considered fresh",()=>{
 for(const min of [-2,70]){
  const x=fixtures();x.intraday.publishedAt=new Date(LIVE.getTime()-min*60000).toISOString();
  assert.equal(core.analyze(x,LIVE).liveVerified,false);
 }
});
test("off-session displays clearly labeled historical snapshot, not live",()=>{
 const x=fixtures();x.daily.dataDate="2026-10-22";x.daily.risk.date="2026-10-22";
 const a=core.analyze(x,when("2026-10-24T13:00:00Z"));
 assert.equal(a.liveVerified,false);
 assert.match(a.mode,/歷史/);
 assert.equal(a.asOfDate,"2026-10-22");
 assert.equal(a.candidates[0].agents.nova.status,"拒絕／僅回顧");
});
test("news uses traceable recent sources, labels keyword matches unverified",()=>{
 const x=fixtures(),out=core.analyze(x,LIVE);
 const news=out.candidates[0].agents.orion;
 assert.match(news.status,/未證實/);
 assert.equal(news.sources.length,1);
 assert.equal(news.sources[0].source,"媒體");
 assert.equal(news.verifiedCount,0);
});
test("stale news, future news or malformed dates never authorize facts",()=>{
 const x=fixtures();x.news.generatedAt="2026-10-18T00:00:00+08:00";
 let o=core.analyze(x,LIVE).candidates[0].agents.orion;
 assert.equal(o.status,"資料不足");assert.equal(o.sources.length,0);
 x.news.generatedAt=LIVE.toISOString();x.news.items[0].publishedAt="2026-10-25T12:00:00+08:00";
 o=core.analyze(x,LIVE).candidates[0].agents.orion;
 assert.equal(o.sources.length,0);
});
test("missing risk/ATR/quotes remain veto, not invented support levels",()=>{
 const x=fixtures();delete x.daily.risk;x.intraday.rows[0].atrPct=null;
 const c=core.analyze(x,LIVE).candidates[0];
 assert.equal(c.agents.titan.hardVeto,true);
 assert.match(c.agents.vega.invalidation,/不生成虛構/);
});
test("source code never sends a brokerage order or invokes language model",()=>{
 const source=fs.readFileSync(path.join(docs,"agent-research-core.js"),"utf8");
 assert.ok(!/\bfetch\s*\(|api\.openai\.com|placeOrder|broker\.buy|order_submit/i.test(source));
 assert.match(source,/noTrade:true/);
});
test("HTML navigation, mobile viewport, aria feedback, script wiring",()=>{
 const html=fs.readFileSync(path.join(docs,"agent-research.html"),"utf8");
 const home=fs.readFileSync(path.join(docs,"index.html"),"utf8");
 const ui=fs.readFileSync(path.join(docs,"agent-research-ui.js"),"utf8");
 assert.match(html,/lang="zh-Hant"/);
 assert.match(html,/name="viewport"/);
 for(const id of ["mode","warning","candidates","agents","nVeto","nReview","filter","refresh"])
  assert.ok(html.includes('id="'+id+'"'),id);
 assert.ok(html.includes('src="./agent-research-core.js"')&&html.includes('src="./agent-research-ui.js"'));
 assert.ok(home.includes('href="./agent-research.html"'),"homepage link required");
 assert.match(ui,/textContent/);new Function(ui);
});

test("LUNA keeps real social sample distinct from risk and absent Meta sources",()=>{
 const x=fixtures(),time=new Date(LIVE.getTime()-10*60000).toISOString();
 x.social={generatedAt:time,sources:{PTT:{status:"ok"},Threads:{status:"not_authorized"},Instagram:{status:"not_authorized"}},
  social:{status:"偏多討論較多",sample:12,bull:8,bear:3,neutral:1,directional:11},
  news:{status:"樣本不足"},items:[
   {platform:"PTT",title:"台積電今日看多突破",url:"https://www.ptt.cc/bbs/Stock/M.100.html",publishedAt:time,stance:"偏多"},
   ...Array.from({length:11},(_,i)=>({platform:"PTT",title:"台股第"+i+"篇",url:"https://www.ptt.cc/bbs/Stock/M."+i+".html",publishedAt:time,stance:i<7?"偏多":i<10?"偏空":"中立／難判"}))]};
 const out=core.analyze(x,LIVE);
 const c=out.candidates[0].agents;
 assert.equal(c.luna.socialStatus,"已有樣本｜偏多內容較多");
 assert.equal(c.luna.socialSample,12);
 assert.equal(c.luna.socialMentions,1);
 assert.equal(c.luna.sourceStatus.Threads,"not_authorized");
 assert.equal(c.luna.sourceStatus.Instagram,"not_authorized");
 assert.equal(c.titan.hardVeto,false);
 assert.equal(c.nova.noTrade,true);
});
test("LUNA never turns missing posts into social samples",()=>{
 const x=fixtures();
 x.social={generatedAt:"2026-10-21T00:00:00+08:00",sources:{PTT:{status:"ok"}},
  social:{status:"偏多討論較多",sample:100,directional:99,bull:90,bear:9},items:[]};
 assert.equal(core.analyze(x,LIVE).candidates[0].agents.luna.socialSample,null);
 x.social.generatedAt=LIVE.toISOString();x.social.sources.PTT.status="error";
 assert.equal(core.analyze(x,LIVE).candidates[0].agents.luna.socialSample,null);
});
test("LLM role pipeline has explicit self-test and no-trade guard",async()=>{
 const llm=require("../scripts/run_six_agent_llm.cjs");
 await llm.selfTest();
});

test("LUNA counts a single verifiable neutral PTT post as an actual sample",()=>{
 const x=fixtures(),time=new Date(LIVE.getTime()-15*60000).toISOString();
 x.social={generatedAt:time,sources:{PTT:{status:"ok"},Threads:{status:"not_authorized"},Instagram:{status:"not_authorized"}},
  social:{status:"已有樣本｜尚無明確多空方向",sample:1,bull:0,bear:0,neutral:1,directional:0},
  items:[{platform:"PTT",title:"台股接下來怎麼看",url:"https://www.ptt.cc/bbs/Stock/M.1.html",publishedAt:time,stance:"中立／難判"}]};
 const l=core.analyze(x,LIVE).candidates[0].agents.luna;
 assert.equal(l.socialSample,1);
 assert.equal(l.socialBull,0);
 assert.equal(l.socialBear,0);
 assert.match(l.socialStatus,/已有樣本/);
 assert.doesNotMatch(l.socialStatus,/樣本不足/);
});
test("LUNA counts an authorized Threads post with no PTT feed",()=>{
 const x=fixtures(),time=new Date(LIVE.getTime()-15*60000).toISOString();
 x.social={generatedAt:time,sources:{PTT:{status:"empty"},Threads:{status:"ok"},Instagram:{status:"not_authorized"}},
  items:[{platform:"Threads",title:"台股今天真的很強勢突破",url:"https://www.threads.net/@user/post/xyz",publishedAt:time,stance:"偏多"}]};
 const l=core.analyze(x,LIVE).candidates[0].agents.luna;
 assert.equal(l.socialSample,1);
 assert.equal(l.socialBull,1);
 assert.match(l.socialStatus,/已有樣本/);
});
test("LUNA confirms stock overheat only with fresh corroborated posts and never changes TITAN",()=>{
 const x=fixtures(),time=LIVE.toISOString();
 const posts=Array.from({length:3},(_,i)=>({platform:"PTT",title:"[討論] 2330 突破 第"+i+"篇",
  url:"https://www.ptt.cc/bbs/Stock/M."+i+".html",publishedAt:time,stance:"偏多"}));
 x.social={generatedAt:time,items:posts,sources:{PTT:{status:"ok"},Threads:{status:"not_authorized"},Instagram:{status:"not_authorized"}},
  stockHeat:{sourceDate:"2026-10-21",stocks:[{code:"2330",name:"台積電",sample:3,recent24h:3,prior24h:0,
   originalDiscussion:3,overheatWatch:true}]}};
 const a=core.analyze(x,LIVE).candidates[0].agents;
 assert.equal(a.luna.overheatWatch,true);
 assert.match(a.luna.heatStatus,/社群過熱/);
 assert.equal(a.titan.hardVeto,false);
 x.social.stockHeat.stocks[0].sample=200;
 assert.equal(core.analyze(x,LIVE).candidates[0].agents.luna.overheatWatch,false);
 x.social.stockHeat.stocks[0].sample=3;
 x.social.generatedAt="2026-10-21T00:00:00Z";
 assert.equal(core.analyze(x,LIVE).candidates[0].agents.luna.overheatWatch,false);
});
test("LUNA labels valid cached posts as historical instead of erasing them",()=>{
 const x=fixtures(),time=new Date(LIVE.getTime()-12*3600000).toISOString();
 x.social={generatedAt:time,sources:{PTT:{status:"error"}},
  items:[{platform:"PTT",title:"台股今天怎麼看",url:"https://www.ptt.cc/bbs/Stock/M.3.html",publishedAt:time,stance:"中立／難判"}]};
 const l=core.analyze(x,LIVE).candidates[0].agents.luna;
 assert.equal(l.socialSample,1);
 assert.match(l.socialStatus,/已有歷史樣本/);
});
