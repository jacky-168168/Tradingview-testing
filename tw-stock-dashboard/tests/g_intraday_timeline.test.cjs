const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
function fixture(){
  const src=fs.readFileSync(path.join(__dirname,'../docs/g-intraday-timeline.js'),'utf8');
  const dates={dates:['2026-10-16']};
  const ts=['2026-10-16T09:05:11+08:00','2026-10-16T09:36:10+08:00','2026-10-16T10:08:31+08:00'];
  const snap=(time,price)=>({asOfDate:'2026-10-16',publishedAt:time,quality:'intraday-provisional-allmarket',rows:[{code:'3535',currentPrice:price}]});
  const scans=[snap(ts[0],91),snap(ts[1],95),snap(ts[2],103)];
  const manifest={date:'2026-10-16',snapshots:ts.map((t,i)=>({file:t.slice(11,19).replaceAll(':','')+'.json',publishedAt:t,count:1}))};
  const files={'./data/g_intraday/archive/index.json':dates,'./data/g_intraday/archive/2026-10-16/index.json':manifest};
  manifest.snapshots.forEach((entry,i)=>{files['./data/g_intraday/archive/2026-10-16/'+entry.file]=scans[i]});
  const ids=['gHistoryPrev','gHistoryNext','gHistoryLatest','gHistoryLabel','gHistoryNote','gHistoryDate'];
  const controls=Object.fromEntries(ids.map(id=>[id,{textContent:'',disabled:false,value:'',innerHTML:'',onclick:null,onchange:null}]));
  let rendered=0;
  const context={window:{},document:{getElementById:id=>controls[id]},taipeiDate:()=> '2026-10-16',
    fetch:async url=>{const val=files[url.split('?')[0]];if(!val)return {ok:false,status:404};return {ok:true,json:async()=>structuredClone(val)}},
    renderTable:()=>{rendered++},renderMeta:()=>{},Date};
  vm.runInNewContext(src,context);
  return {timeline:context.window.GIntradayTimeline,controls,files,manifest,scans,rendered:()=>rendered};
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
test('latest by default, arrows show actual historical rounds and keep pinned on refresh',async()=>{
  const {timeline,controls,manifest,files,scans}=fixture();
  timeline.init();
  await timeline.sync(scans[2]);
  assert.equal(timeline.current(null).rows[0].currentPrice,103);
  assert.match(controls.gHistoryLabel.textContent,/10:08:31/);
  controls.gHistoryPrev.onclick();await tick();await tick();
  assert.equal(timeline.current(null).rows[0].currentPrice,95);
  assert.match(controls.gHistoryLabel.textContent,/2\/3 輪/);
  manifest.snapshots.push({file:'104001.json',publishedAt:'2026-10-16T10:40:01+08:00',count:1});
  const newer={...scans[2],publishedAt:'2026-10-16T10:40:01+08:00',rows:[{code:'3535',currentPrice:111}]};
  files['./data/g_intraday/archive/2026-10-16/104001.json']=newer;
  await timeline.sync(newer);
  assert.equal(timeline.current(null).rows[0].currentPrice,95,'historical selection must stay pinned after polling');
  controls.gHistoryLatest.onclick();await tick();await tick();
  assert.equal(timeline.current(null).rows[0].currentPrice,111);
  assert.match(controls.gHistoryLabel.textContent,/4\/4 輪/);
  assert.equal(controls.gHistoryNext.disabled,true);
});
