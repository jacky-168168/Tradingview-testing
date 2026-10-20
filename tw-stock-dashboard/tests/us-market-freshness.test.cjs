"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const {expectedSession,warning}=require("../docs/us-market-freshness.js");
test("US completed-session date respects New York clock and weekend",()=>{
 assert.equal(expectedSession(new Date("2026-10-20T02:40:00Z")),"2026-10-19");
 assert.equal(expectedSession(new Date("2026-10-19T23:00:00Z")),"2026-10-16");
 assert.equal(expectedSession(new Date("2026-10-19T00:20:00Z")),"2026-10-16");
 assert.equal(expectedSession(new Date("2026-07-07T01:00:00Z")),"2026-07-06");
});
test("stale dates must be clearly labeled without guessed quotes",()=>{
 const now=new Date("2026-10-20T02:40:00Z");
 assert.equal(warning("2026-10-16",now).stale,true);
 assert.match(warning("2026-10-16",now).message,/10-16.*10-19/);
 assert.equal(warning("2026-10-19",now).stale,false);
 assert.equal(warning("2026-10-19",now).message,"");
 assert.equal(warning("",now).stale,true);
});
