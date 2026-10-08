// 主頁研究入口隱藏、整合 G 回測：輕量前端回歸測試（Node 18+，無第三方依賴）。
const fs=require("node:fs"),path=require("node:path"),assert=require("node:assert/strict");
const docs=path.resolve(__dirname,"../docs"),read=x=>fs.readFileSync(path.join(docs,x),"utf8");
const index=read("index.html"),backtest=read("backtest.html"),source=read("backtest-g-panel.js");
for(const name of ["g-backtest.html","g-target.html","g-candles.html","g-persistence.html"]){
assert(fs.existsSync(path.join(docs,name)),name+" must be preserved");
assert(!index.includes('href="./'+name+'"'),name+" must not be linked from index");
}
assert(index.includes('href="./backtest.html"'),"Backtest entry must remain on homepage");
assert(backtest.includes('id="G" class="primary on"'),"G must be default in unified backtest");
assert(backtest.includes('src="./backtest-g-panel.js"'),"G JS must load in Backtest");
for(const id of ["D","F2","F","A","legacyView","modelTabs","gPerformance","gTrades","gAudits"]){
assert(backtest.includes('id="'+id+'"'),"Missing UI id "+id);
}
assert(backtest.includes("賺錢平均")&&backtest.includes("賠錢平均"),"Positive/negative averages must be separately shown");
function makeModel(){
return {candidateStats:{avg:3,days:2,days3:2},summary:[1,3,5,10,20].map(h=>({horizon:h,top3Daily:{n:2,avg:2.1,median:1,win:50},phasePortfolio:{meanTotalReturn:4.2}})),signals:[
{signalDate:"2026-10-07",rank:1,code:"1001",name:"測試甲",score:88,ret1:80,ret3:80,ret5:80,ret10:80,ret20:80},
{signalDate:"2026-10-07",rank:2,code:"1002",name:"測試乙",score:80,ret1:15,ret3:15,ret5:15,ret10:15,ret20:15},
{signalDate:"2026-10-07",rank:3,code:"1003",name:"測試丙",score:77,ret1:-20,ret3:-20,ret5:-20,ret10:-20,ret20:-20}
],sampleAudit:{n:3,top20:2,top3:1,checks:[{code:"1001",name:"測試甲",postDate:"2026-10-07",rank:1}]},latestPocket:{date:"2026-10-07",rows:[{rank:1,code:"1001",name:"測試甲",score:88,persistence:{strength:6,past10Top20:4,priorStreak:2},flags:{break3:true,break18:true}}]},repeatAudit:{noDoubleBuy:{"5":{},"10":{},"20":{}}}};
}
const p={period:{start:"2026-01-01",end:"2026-10-07"},signalDays:180,models:{G_DOUBLE_PERSIST:makeModel(),G_PERSIST:makeModel()},notes:[]};
const o={period:{start:"2026-01-01",end:"2026-10-07"},signalDays:180,models:{G_BASE:makeModel(),G_RELAXED:makeModel(),G_STRICT:makeModel()},sampleAudit:{G_BASE:{total:3,top20:2,top3:1,checks:[]}},notes:[]};
const els=new Map(),gids=["G_DOUBLE_PERSIST","G_PERSIST","G_BASE","G_RELAXED","G_STRICT"];
function el(id){if(!els.has(id))els.set(id,{id,innerHTML:"",textContent:"",value:"",style:{display:""},classList:{toggle(){}},dataset:{}});return els.get(id)}
const buttons=gids.map(id=>Object.assign(el("button_"+id),{dataset:{gmodel:id}}));
const nav=["G","D","F2","F","A"].map(el);
const document={getElementById:el,querySelectorAll:q=>q==="[data-gmodel]"?buttons:q==="#modelTabs button"?nav:[]};
const fetch=async url=>({ok:true,json:async()=>url.includes("g_persistence_2026")?p:o});
async function main(){
new Function("document","fetch",source)(document,fetch);
await el("gReload").onclick();
assert(el("gCurrent").textContent.includes("雙突破"),"G main should be selected by default");
assert.equal((el("gPerformance").innerHTML.match(/<tr/g)||[]).length,25,"five models x five horizons");
assert(el("gPerformance").innerHTML.includes("47.50%"),"profit avg (80+15)/2 should be 47.50%");
assert(el("gPerformance").innerHTML.includes("-20.00%"),"loss avg -20 should be separate");
assert(el("gPockets").innerHTML.includes("測試甲"),"persistence pocket list should display");
buttons[2].onclick();assert(el("gCurrent").textContent.includes("G_BASE"),"G base tab should switch");
assert.equal(el("gPocketSection").style.display,"none","no persistence pockets for G_BASE");
buttons[0].onclick();el("gSearch").value="1002";el("gSearch").oninput();
assert(el("gTrades").innerHTML.includes("測試乙")&&!el("gTrades").innerHTML.includes("測試甲"),"trade search must filter");
el("legacyView").style.display="block";el("gView").style.display="none";el("G").onclick();
assert.equal(el("legacyView").style.display,"none","returning to G should hide legacy");
assert.equal(el("gView").style.display,"block","returning to G should show G");
console.log("PASS: 4 hidden routes preserved, G + D/F/A tabs, 5 G models, P/L averages, search and view switching");
}
main().catch(e=>{console.error(e);process.exitCode=1});