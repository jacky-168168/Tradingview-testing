const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");
const js=fs.readFileSync(path.join(__dirname,"../docs/bottom-top-trader.js"),"utf8");
const BASE=Date.parse("2026-01-06T09:00:00+08:00");
function event(signal,price,trend,step=0,other={}){return {time:BASE+step*120000,symbol:"TWSE:1802",signal,price,trend,timeframe:"2",...other}}
function execute(strategy,data,opts={}){
 const els=new Map();
 const byId=id=>{if(!els.has(id))els.set(id,{id,value:"",checked:false,innerHTML:"",textContent:"",type:["useStop","requireG"].includes(id)?"checkbox":"text",handlers:{},addEventListener(ev,fn){this.handlers[ev]=fn},files:[]});return els.get(id)};
 const doc={getElementById:byId,querySelectorAll:()=>[]};
 const settings={strategy,capital:"1000000",riskCap:"20",trendMin:"70",batches:"5",dip:"3",unit:"1",discount:"6",tax:"0.3",stopPct:"12",useStop:false,requireG:false,...opts};
 let saved=JSON.stringify({settings,events:data});
 const sandbox={document:doc,localStorage:{getItem:()=>saved,setItem:(key,text)=>{saved=text}},location:{search:""},navigator:{},URLSearchParams,Date,Intl,Math,Number,String,JSON,Array,Object,RegExp,Set,Map,Error,console};
 vm.runInNewContext(js,sandbox,{timeout:3000,filename:"bottom-top-trader.js"});
 return {events:byId("banner").textContent,rows:byId("signalRows").innerHTML,positions:byId("stockRows").innerHTML,metrics:byId("metrics").innerHTML};
}
test("A: raw Bottom enters regardless of Trend and Top exits",()=>{
 const x=execute("A",[event("BOTTOM",60,null),event("TOP",65,0,1)]);
 assert.match(x.rows,/模擬買進/);assert.match(x.rows,/模擬出場/);assert.match(x.positions,/觀察中/);
});
test("B: Trend must strictly exceed 70; Top remains independent",()=>{
 const x=execute("B",[event("BOTTOM",60,70),event("BOTTOM",60,71,1),event("TOP",65,0,2)]);
 assert.match(x.rows,/未嚴格大於 70/);assert.match(x.rows,/模擬買進/);assert.match(x.rows,/模擬出場/);
});
test("C: adds one layer per later observed price event",()=>{
 const x=execute("C",[event("BOTTOM",60,82),event("PRICE",57.5,null,1),event("TOP",62,null,2)]);
 assert.match(x.rows,/分批加碼/);assert.match(x.rows,/模擬出場/);
 assert.match(x.metrics,/已模擬平倉<\/span><b>1 筆/);
});
test("G prerequisite blocks events not marked as selected",()=>{
 const x=execute("B",[event("BOTTOM",60,85,0,{g:null})],{requireG:true});
 assert.match(x.rows,/未確認在 G 股票池/);assert.doesNotMatch(x.rows,/模擬買進/);
});
test("Non 2-minute event is rejected",()=>{
 const x=execute("A",[event("BOTTOM",60,null,0,{timeframe:"5"})]);
 assert.match(x.events,/尚未匯入交易事件/);
});
test("Without new PRICE observation C does not invent a ladder fill",()=>{
 const x=execute("C",[event("BOTTOM",60,82),event("TOP",62,0,2)]);
 assert.doesNotMatch(x.rows,/分批加碼/);
});
test("Bridge Pine retains original independent signal equations",()=>{
 const s=fs.readFileSync(path.join(__dirname,"../docs/pine/Extreme_Reversal_Hunter_Dashboard_JSON_Bridge.pine"),"utf8");
 assert.match(s,/bottomEv=barstate\.isconfirmed and extCooled and fearRecent/);
 assert.match(s,/topEv=barstate\.isconfirmed and alsoTops and extCooled and greedHot/);
 assert.match(s,/strongBottom=bottomEv and strongTrendScore>strongTrendTh/);
 assert.match(s,/str\.tostring\(time_close\)/);assert.match(s,/alert\(bridgeMsg,alert\.freq_once_per_bar_close\)/);
});