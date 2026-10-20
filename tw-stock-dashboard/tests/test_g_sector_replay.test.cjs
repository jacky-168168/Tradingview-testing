const test=require("node:test"),assert=require("node:assert/strict");
const vm=require("node:vm"),fs=require("node:fs"),path=require("node:path");
const script=fs.readFileSync(path.join(__dirname,"../docs/g-sector-replay.js"),"utf8");
function data(time,score,previousRisk){
 return {asOfDate:"2026-10-21",publishedAt:time,quality:"intraday-provisional-allmarket",rows:[{code:"1234"}],
  coverage:{valid:1700,total:1983},marketBreadth:{total:{upPct:42}},
  gSignalContext:previousRisk?{market:{allMarketUpPct:42,breadthBand:"偏弱"},previousCloseRisk:{score:55,date:"2026-10-20"}}:undefined,
  freeMarketOverlay:score===null?undefined:{industryMomentum:{ranking:[{industry:"半導體",rank:1,scorePct:score,
   breadthPct:60,turnoverEstimatedB:18.2,quoted:50,total:60,leaders:[{name:"台積電"}]}]}}};
}
function harness(){
 const ids=["tradeDay","prev","next","round","reload","timeline","status","summary","context","sectorRows"],els={};
 for(const id of ids){els[id]={value:"",innerHTML:"",textContent:"",max:0,disabled:false,handlers:{},addEventListener(event,fn){this.handlers[event]=fn}}}
 const t1="2026-10-21T09:31:00+08:00",t2="2026-10-21T10:02:00+08:00";
 const map={
  "./data/g_intraday/archive/index.json":{dates:["2026-10-21","2026-10-20"]},
  "./data/g_intraday/archive/2026-10-21/index.json":{date:"2026-10-21",snapshots:[{file:"093100.json",publishedAt:t1},{file:"100200.json",publishedAt:t2}]},
  "./data/g_intraday/archive/2026-10-21/093100.json":data(t1,1,true),
  "./data/g_intraday/archive/2026-10-21/100200.json":data(t2,3,true),
  "./data/g_intraday/archive/2026-10-20/index.json":{date:"2026-10-20",snapshots:[{file:"130000.json",publishedAt:"2026-10-20T13:00:00+08:00"}]},
  "./data/g_intraday/archive/2026-10-20/130000.json":{asOfDate:"2026-10-20",publishedAt:"2026-10-20T13:00:00+08:00",quality:"intraday-provisional-allmarket",rows:[],coverage:{valid:1500,total:1983},marketBreadth:{total:{upPct:25}}}
 };
 const ctx={document:{getElementById(id){return els[id]}},Date,Number,Math,Array,Map,Set,String,Promise,
  fetch:async url=>{let key=url.split("?")[0];return {ok:key in map,status:key in map?200:404,json:async()=>map[key]}}};
 vm.runInNewContext(script,ctx);
 return {els};
}
test("real archived sector comparison calculates observed +2pp without synthetic missing slots",async()=>{
 const {els}=harness();await new Promise(r=>setTimeout(r,12));
 assert.match(els.round.textContent,/第 2／2 輪/);
 assert.match(els.sectorRows.innerHTML,/\+2\.00pp/);
 assert.match(els.context.textContent,/前一完整收盤風險分數 55/);
 els.prev.handlers.click();assert.match(els.sectorRows.innerHTML,/>—<\/td>/);
});
test("older snapshots without sector overlay must show missing data",async()=>{
 const {els}=harness();await new Promise(r=>setTimeout(r,12));
 els.tradeDay.value="2026-10-20";els.tradeDay.handlers.change();
 await new Promise(r=>setTimeout(r,12));
 assert.match(els.sectorRows.innerHTML,/尚無符合資料品質要求/);
 assert.match(els.context.textContent,/尚未開始封存/);
});
