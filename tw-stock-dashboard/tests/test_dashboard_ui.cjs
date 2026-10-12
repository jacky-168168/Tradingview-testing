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
const noteJs=part("function renderModelNote(){","var N_ARCHIVE=null");
const describe=new Function("MODEL","DATA","gNote","currentLiveG",noteJs+"renderModelNote()");
const data={gSelection:{dataDate:"2026-10-08",pocketSnapshotsFound:4,pocketWarmup:true},risk:{score:71,fGate:{allowed:true,reason:"RISK_ON"},f2Gate:{allowed:true,reason:"HYSTERESIS_HOLD"}}};
const expected={A:["股本＜500億元","成交額≥1億元","SAR"],D:["日成交量＞2,000萬股","RVOL10＞1.2","候補"],F:["Risk Score≥60","濾網：放行","RISK_ON"],F2:["≥55 維持","Strong Bottom Reversal","HYSTERESIS_HOLD"],G:["3D＋18D 前高雙突破","可用歷史 4/10","當日未取得有效盤中重選時僅更新原榜單現價"]};
for(const [model,words] of Object.entries(expected)){const node={textContent:""};describe(model,data,node,()=>null);for(const w of words)assert(node.textContent.includes(w),model+" caption missing "+w)}
const blocked={gSelection:data.gSelection,risk:{score:40,fGate:{allowed:false,reason:"MARKET_BLOCK"},f2Gate:{allowed:false,reason:"TOP_REVERSAL_VETO"}}};
for(const model of ["F","F2"]){const node={textContent:""};describe(model,blocked,node,()=>null);assert(node.textContent.includes("濾網：阻擋"),model+" must show blocked gate")}
const modeJs=part("function applyTableMode(){","function simpleMetric(");
function table(model,simple){
 const stockTable={classList:{toggle(){}},tHead:{innerHTML:""}},layoutToggle={textContent:"",setAttribute(){}},tableHint={textContent:""},badge={textContent:""},panel={classList:{toggle(){}}};
 const document={getElementById:id=>id==="repeatPanel"?panel:id==="modeBadge"?badge:null};
 const original='<tr>'+Array.from({length:22},(_,i)=>'<th>原始'+i+'</th>').join("")+'</tr>';
 const nOriginal='<tr>'+Array.from({length:10},(_,i)=>'<th>N'+i+'</th>').join("")+'</tr>';
 const simpleHead='<tr><th>排名</th><th>股票／題材</th><th>強度</th><th>現價／漲跌</th></tr>';
 const nSimple='<tr><th>排名</th><th>股票</th><th>成長分數</th><th>收盤價</th></tr>';
 new Function("MODEL","TABLE_COMPACT","stockTable","layoutToggle","tableHint","document","N_SIMPLE_HEAD","STOCK_SIMPLE_HEAD","N_TABLE_HEAD","NORMAL_TABLE_HEAD","filterBar",modeJs+"applyTableMode()")(model,simple,stockTable,layoutToggle,tableHint,document,nSimple,simpleHead,nOriginal,original,()=>{});
 return {html:stockTable.tHead.innerHTML,label:layoutToggle.textContent,badge:badge.textContent,hint:tableHint.textContent};
}
const sg=table("G",true);assert.equal((sg.html.match(/<th>/g)||[]).length,4,"Simple mobile G should show exactly four columns");
assert(sg.html.includes("股票／題材")&&sg.html.includes("現價／漲跌"));assert.equal(sg.badge,"簡單模式");
assert.equal(sg.label,"▤ 詳細模式");
const dg=table("G",false);assert.equal((dg.html.match(/<th>/g)||[]).length,22,"Detailed G must retain all 22 columns, including 3D/18D and RVOL");
assert.equal(dg.badge,"詳細模式");assert.equal(dg.label,"▥ 簡單模式");
assert.equal((table("D",false).html.match(/<th>/g)||[]).length,22,"All original table headers remain in detailed D");
assert.equal((table("N",true).html.match(/<th>/g)||[]).length,4,"N simple view has four columns");
assert.equal((table("N",false).html.match(/<th>/g)||[]).length,10,"N detailed view retains ten columns");
const simpleJs=part("function simpleMetric(","function renderModelNote(){");
const esc=s=>String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;");
const N=x=>x==null?"--":Number(x).toFixed(2),P=x=>N(x)+"%",C=x=>Number(x)>=0?"pos":"neg";
const simple=new Function("x","EXPANDED_STOCK","themeButton","tvStockLink","esc","N","P","C",simpleJs+"return renderSimpleStock(x,0,true,null)");
const sample={code:"3624",name:"光頡",market:"上市",theme:"CPO",gPast10:10,sarText:"多27根K",currentPrice:173,currentPct:-1.14};
const render=(expanded)=>simple(sample,expanded?"上市|3624":"",x=>'<button class="theme-pick" data-theme="'+x+'">'+x+'</button>',x=>x.code+" "+x.name,esc,N,P,C);
assert(render(false).includes("3624 光頡")&&render(false).includes("10日 10/10")&&render(false).includes('data-theme="CPO"'));
assert.equal((render(false).match(/<td/g)||[]).length,4,"Simple view should render only four initial table cells");
assert(render(true).includes("simple-detail-grid")&&render(true).includes("外資買賣超"),"Tap to expand details");
assert(script.includes('localStorage.setItem("tw_selection_view_v1"'),"Manual mode choice must persist");
assert(script.includes('THEME_FILTER')&&script.includes("selectedRows"),"G theme ranking filter missing");
assert(html.includes('id="clearThemeFilter"')&&html.includes('id="modeBadge"'),"Theme filter bar and mode label required");
const repeatJs=fs.readFileSync(path.resolve(__dirname,"../docs/repeat-rankings.js"),"utf8");new Function(repeatJs);
assert(repeatJs.includes("allRepeated.filter")&&repeatJs.includes("themeButton(s.theme"),"Repeat table must also support exact theme filters");
for(const key of ["tabG","tabA","tabD","tabF","tabF2"]){assert(html.includes('id="'+key+'"'),key+" toggle missing")}
assert(script.includes("'+tvStockLink(x)+'</td>"),"All models must render clickable stock name through shared row");
console.log("PASS: TradingView links, strategy notes, mobile 4-column mode, all detailed columns, G theme filters and repeats");
