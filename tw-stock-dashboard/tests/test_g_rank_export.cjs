'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const root='tw-stock-dashboard/docs/',html=fs.readFileSync(root+'selections.html','utf8'),code=fs.readFileSync(root+'g-rank-export.js','utf8');
for(const id of ['gExportIntraday','gExportOfficial'])assert(html.includes('id="'+id+'"'),'missing download button '+id);
assert(html.includes('src="./g-rank-export.js"'),'export JS not loaded');
assert(html.includes('src="./stock-selection.js"'),'selection JS missing');
assert(html.indexOf('src="./stock-selection.js"')<html.indexOf('src="./g-rank-export.js"'),'export loaded before ranking data');
const day='2026-10-14',live={asOfDate:day,publishedAt:day+'T13:30:00+08:00',rows:[{code:'6834'}]};
function makeTable(simple){
 const headers=simple?['排名','股票／題材','強度','現價／漲跌']:['Rank','股票','市場','題材','總分','正式收盤價'];
 const cells=simple?['1','6834 天二科技 光通訊','99.7','68.3 +4.2%']:['1','6834 天二科技','上市','光通訊','99.7','68.3'];
 return {classList:{contains:x=>simple&&x==='simple-mode'},tHead:{rows:[{cells:headers.map(innerText=>({innerText}))}]},tBodies:[{rows:[{cells:cells.map(innerText=>({innerText,colSpan:1})),classList:{contains:()=>false}},{cells:[{innerText:'expand',colSpan:4}],classList:{contains:()=>true}}]}]};
}
function run(simple){
 const stock=makeTable(simple),official=makeTable(simple),drawText=[];
 const fakeContext=()=>({measureText:t=>({width:Array.from(String(t)).length*10}),scale(){},fillRect(){},fillText(t){drawText.push(String(t))},beginPath(){},moveTo(){},lineTo(){},stroke(){},set font(v){},set fillStyle(v){},set textBaseline(v){},set strokeStyle(v){}});
 const doc={getElementById:id=>id==='stockTable'?stock:id==='officialStockTable'?official:id==='gIntradayStatus'?{textContent:'盤中資料日 2026-10-14'}:id==='gOfficialStatus'?{textContent:'正式訊號日 2026-10-13'}:null,createElement:t=>{assert.equal(t,'canvas');return{width:0,height:0,getContext:fakeContext}}};
 const window={};const env={document:doc,window,MODEL:'G',DATA:{dataDate:'2026-10-13',generatedAt:'2026-10-13T17:00:00+08:00',gSelection:{dataDate:'2026-10-13'},models:{G:[{code:'6834'}]}},currentLiveG:()=>live,gSnapshotNotice:()=>'',THEME_FILTER:'',Date,Intl,alert(){}};
 vm.runInNewContext(code,env);
 const api=window.GRankImageExport,now=api.collect('intraday'),close=api.collect('official');
 assert.equal(now.date,day);assert.equal(close.date,'2026-10-13');assert.equal(now.rows.length,1);assert.equal(close.rows.length,1);
 assert.equal(now.columns.length,simple?4:6);assert.equal(close.columns.length,simple?4:6);
 const a=api.renderPNG(now),b=api.renderPNG(close);
 assert(a.width>600&&a.height>500);assert(b.width>600&&b.height>500);
 assert(drawText.some(x=>x.includes('盤中選股')));assert(drawText.some(x=>x.includes('盤後選股')));
 env.currentLiveG=()=>null;assert.throws(()=>api.collect('intraday'),/沒有可用/);
 env.DATA.gSelection.dataDate='2026-10-12';assert.throws(()=>api.collect('official'),/尚未完成/);
}
run(true);run(false);console.log('PASS G export: both titles, script order, compact/detail rows, canvas, source date and fail-closed');
