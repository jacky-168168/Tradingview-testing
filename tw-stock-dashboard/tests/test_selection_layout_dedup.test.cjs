const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const docs=path.join(__dirname,"../docs");
const html=fs.readFileSync(path.join(docs,"selections.html"),"utf8");
const js=fs.readFileSync(path.join(docs,"stock-selection.js"),"utf8");
const repeat=fs.readFileSync(path.join(docs,"repeat-rankings.js"),"utf8");
const overlay=fs.readFileSync(path.join(docs,"g-free-market-overlay.js"),"utf8");
test("G historical repeats, intraday Top20 and official Top20 remain three distinct sources",()=>{
 for(const id of ["repeatPanel","repeatTable","gIntradayHeading","stockTable","gOfficialPanel","officialStockTable"]){
  assert.equal((html.match(new RegExp('id="'+id+'"',"g"))||[]).length,1,"missing/duplicated "+id);
 }
 assert.ok(html.indexOf('id="repeatPanel"')<html.indexOf('id="gIntradayHeading"'));
 assert.ok(html.indexOf('id="gIntradayHeading"')<html.indexOf('id="stockTable"'));
 assert.ok(html.indexOf('id="stockTable"')<html.indexOf('id="gOfficialPanel"'));
 assert.ok(html.indexOf('id="gOfficialPanel"')<html.indexOf('id="officialStockTable"'));
 assert.ok(js.includes('live?live.rows:[]'),"intraday G source must remain provisional");
 assert.ok(js.includes('DATA&&DATA.models&&DATA.models.G'),"official G source must remain independent");
});
test("live G Top20 table appears immediately after its session heading",()=>{
 const x=html.indexOf('id="gIntradayHeading"'),y=html.indexOf('id="stockTable"');
 const between=html.slice(x,y);
 assert.ok(between.includes('id="gHistoryControls"'),"must preserve history controls");
 assert.ok(!between.includes('id="gFreeMarketPanel"'),"supplemental research cannot interrupt live top20");
 assert.ok(!between.includes('id="lPanel"'),"L model controls cannot interrupt G panel");
});
test("supplemental research remains reachable but collapsed by default",()=>{
 const x=html.indexOf('id="stockTable"'),y=html.indexOf('id="gExtraResearch"'),z=html.indexOf('id="gOfficialPanel"');
 assert.ok(x<y&&y<z,"research toggle belongs after live Top20, before official panel");
 assert.match(html,/<details id="gExtraResearch"[^>]*hidden>/);
 assert.ok(js.includes('extraResearch.hidden=!isDualG'),"non-G models must not show G supplemental research");
 assert.ok(html.includes('id="gFreeMarketPanel"'),"retain verified market research details");
});
test("remove genuinely repeated presentation while retaining single sector replay link",()=>{
 assert.equal((html.match(/href="\.\/g-sector-replay\.html"/g)||[]).length,1,"one replay link in G intraday header");
 assert.ok(!overlay.includes('href="./g-sector-replay.html"'),"no duplicate replay inside research");
 assert.ok(repeat.includes('inlineTheme'),"inline theme must be conditional on compact mode");
 assert.ok(repeat.includes("TABLE_COMPACT"),"desktop theme column replaces inline theme chip");
 assert.ok(html.includes('id="repeatTable"'),"historical repeats must not be deleted");
});
