// Standalone rankings regression: G visual columns, links, model descriptions and no homepage selection table.
const fs=require("node:fs"),path=require("node:path"),assert=require("node:assert/strict");
const html=fs.readFileSync(path.resolve(__dirname,"../docs/selections.html"),"utf8");
const home=fs.readFileSync(path.resolve(__dirname,"../docs/index.html"),"utf8");
const script=fs.readFileSync(path.resolve(__dirname,"../docs/stock-selection.js"),"utf8");
assert.match(html,/<script src="\.\/stock-selection\.js"><\/script>/,"Rankings page must load its own script");new Function(script);
assert(!home.includes('id="stockTable"')&&!home.includes('id="tabG"'),"Home must not show the stock selection table");
assert(home.includes('href="./selections.html"'),"Home needs an obvious rankings entry");
assert(home.includes('id="riskScore"')&&home.includes('id="buyRows"')&&home.includes('id="txfNight"'),"Market and institutional panels must stay on homepage");
const homeScript=(home.match(/<script>\s*([\s\S]*?)<\/script>/)||[])[1];assert(homeScript,"Homepage market script missing");new Function(homeScript);
function part(from,to){const a=script.indexOf(from),b=script.indexOf(to,a+from.length);assert(a!==-1&&b>a,from+" missing");return script.slice(a,b)}
const link=new Function("x",part("function esc(","function dayInfo(")+"return tvStockLink(x)");
assert.equal(link({code:"1714",name:"和桐",market:"上市"}).includes("symbol=TWSE%3A1714"),true);
assert.equal(link({code:"3624",name:"光頡",market:"上櫃"}).includes("symbol=TPEX%3A3624"),true);
assert(link({code:"3624",name:"光頡",market:"上櫃"}).includes('target="_blank" rel="noopener noreferrer"'));
assert(!link({code:"1714",name:"測試",market:"未知"}).includes("<a"),"Unknown market should not open a wrong chart");
assert(!link({code:"<tag>",name:"測試",market:"上市"}).includes("<a"),"Invalid symbol should not open a chart");
const noteJs=part("function renderModelNote(){","function renderTable(){");
const describe=new Function("MODEL","DATA","gNote",noteJs+"renderModelNote()");
const data={gSelection:{dataDate:"2026-10-08",pocketSnapshotsFound:4,pocketWarmup:true},risk:{score:71,fGate:{allowed:true,reason:"RISK_ON"},f2Gate:{allowed:true,reason:"HYSTERESIS_HOLD"}}};
const expected={A:["股本＜500億元","成交額≥1億元","SAR"],D:["日成交量＞2,000萬股","RVOL10＞1.2","候補"],F:["Risk Score≥60","濾網：放行","RISK_ON"],F2:["≥55 維持","Strong Bottom Reversal","HYSTERESIS_HOLD"],G:["3D＋18D 前高雙突破","可用歷史 4/10","盤中僅更新現價"]};
for(const [model,words] of Object.entries(expected)){const node={textContent:""};describe(model,data,node);for(const w of words)assert(node.textContent.includes(w),model+" caption missing "+w)}
const blocked={gSelection:data.gSelection,risk:{score:40,fGate:{allowed:false,reason:"MARKET_BLOCK"},f2Gate:{allowed:false,reason:"TOP_REVERSAL_VETO"}}};
for(const model of ["F","F2"]){const node={textContent:""};describe(model,blocked,node);assert(node.textContent.includes("濾網：阻擋"),model+" must show blocked gate")}
const tableJs=part("function applyTableMode(){","function renderModelNote(){");
function table(model,compact){
const headers=Array.from({length:22},()=>({style:{},textContent:""})),cells=Array.from({length:model==="G"?22:18},()=>({style:{}}));
const tr={cells},stockTable={classList:{toggle(){}},setAttribute(){},querySelectorAll:()=>headers},tb={querySelectorAll:()=>[tr]};
const layoutToggle={setAttribute(){},textContent:""},tableHint={textContent:""};
new Function("MODEL","TABLE_COMPACT","stockTable","layoutToggle","tb","tableHint",tableJs+"applyTableMode()")(model,compact,stockTable,layoutToggle,tb,tableHint);
return {headers,cells,tableHint};
}
for(const compact of [true,false]){
const g=table("G",compact);
assert.equal(g.headers[8].style.display,"none","G 3D/18D header should always be hidden");
assert.equal(g.headers[16].style.display,"none","G RVOL header should always be hidden");
assert.equal(g.cells[8].style.display,"none","G 3D/18D data should always be hidden");
assert.equal(g.cells[16].style.display,"none","G RVOL data should always be hidden");
assert.equal(g.headers[13].textContent,"外資買賣超");
assert.equal(g.headers[14].textContent,"投信買賣超");
assert.notEqual(g.cells[13].style.display,"none");assert.notEqual(g.cells[14].style.display,"none");
}
const d=table("D",false);assert.equal(d.headers[8].style.display,"none","No phantom G extra headers for D");assert.notEqual(d.headers[16].style.display,"none","D must retain RVOL in full view");
for(const key of ["tabG","tabA","tabD","tabF","tabF2"]){assert(html.includes('id="'+key+'"'),key+" toggle missing")}
assert(html.includes("'+tvStockLink(x)+'</td>"),"All models must render clickable stock name through shared row");
console.log("PASS: TradingView TWSE/TPEX links, rule descriptions A/D/F/F2/G, market gate states and G-specific columns");
