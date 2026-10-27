const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const html=fs.readFileSync(path.join(__dirname,"../docs/index.html"),"utf8");
const begin=html.indexOf("function nextEntryPreview(){"),end=html.indexOf("async function loadFutures(){",begin);
assert(begin>0&&end>begin,"TX preview and live validation must exist");
const source=html.slice(begin,end);
const FakeDate=class extends Date {static now(){return new Date("2026-10-27T09:01:00+08:00").getTime()}};
const runner=new Function("Date","document","TX_LIVE","FUTURES","DATA","sameContractTX","futDisplay","taipeiDate",
 source+"\nnextEntryPreview();return document.getElementById('nextEntry');");
function render(last,reference=46234){
 const classes=[],el={className:"",textContent:"",classList:{add(v){if(!v)throw Error("Empty class token");classes.push(v)}}};
 const q={status:"ok",quality:"dated-third-party-snapshot",asOfDate:"2026-10-27",symbol:"WTX&",quoteTime:"2026-10-27T09:00:40+08:00",last,reference};
 const node=runner(FakeDate,{getElementById:()=>el},q,null,{risk:{date:"2026-10-22"}},()=>null,v=>Number(v).toLocaleString('en-US'),()=>"2026-10-27");
 return {node,classes};
}
const rising=render(46636);
assert.match(rising.node.textContent,/今日台指期/);
assert.match(rising.node.textContent,/46,636/);
assert(!rising.classes.includes(""),"positive quote must not add empty CSS class");
assert(rising.node.textContent.includes("+0.87%"));
const dropping=render(45500);
assert(dropping.classes.includes("stop"));
assert.match(dropping.node.textContent,/今日台指期/);
console.log("PASS fresh 08:45+ TX quote displays; positive and negative CSS states do not crash");
