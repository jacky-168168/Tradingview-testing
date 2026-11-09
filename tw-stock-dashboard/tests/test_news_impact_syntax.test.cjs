// Regression for 2026-11-09 duplicate HISTORY declaration in news-impact.js.
// Ensures all-time history URL remains separate from mutable history response.
const {test}=require("node:test");
const assert=require("node:assert/strict");
const {readFileSync}=require("node:fs");
const {spawnSync}=require("node:child_process");
const path=require("node:path");
const script=path.resolve(__dirname,"../docs/news-impact.js");
test("news-impact script parses without duplicate HISTORY bindings",()=>{
    const js=readFileSync(script,"utf8");
    assert.match(js,/const NEWS=.*HISTORY_URL=/);
    assert.match(js,/let DATA=\[\],HISTORY=null/);
    assert.match(js,/fetch\(HISTORY_URL\+"\?t="/);
    const result=spawnSync(process.execPath,["--check",script],{encoding:"utf8"});
    assert.equal(result.status,0,result.stderr);
});
