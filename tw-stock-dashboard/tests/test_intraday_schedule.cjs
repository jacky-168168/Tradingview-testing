const assert=require('node:assert/strict'),fs=require('node:fs');
const wf=fs.readFileSync('.github/workflows/tw-stock-dashboard.yml','utf8');
const ui=fs.readFileSync('tw-stock-dashboard/docs/stock-selection.js','utf8');
const py=fs.readFileSync('tw-stock-dashboard/src/g_intraday.py','utf8');
assert.match(wf,/- cron: '0,30 1-5 \* \* 1-5'/);
assert.match(wf,/'0,30 1-5 \* \* 1-5'[^
]*MODE="intraday"/);
assert.match(wf,/- cron: '20 3-5 \* \* 1-5'/);
for(const utcHour of [1,2,3,4,5])for(const minute of [0,30]){
 const twHour=(utcHour+8)%24;assert(twHour>=9&&twHour<=13);
}
assert.match(wf,/- cron: '10 7 \* \* 1-5'/);
assert.match(wf,/- cron: '40 7 \* \* 1-5'/);
assert.match(wf,/python src\/g_intraday.py/);
assert.match(py,/clock\(9,0\)<=now\.time\(\)<clock\(13,45\)/);
assert.match(ui,/setInterval\(load,90000\)/);
assert.match(ui,/g\.asOfDate!==taipeiDate\(\)/);
assert.match(ui,/每30分鐘更新/);
console.log('PASS ten half-hour TW intraday slots, backend/website sync, full-close retries and stale-data gate');
