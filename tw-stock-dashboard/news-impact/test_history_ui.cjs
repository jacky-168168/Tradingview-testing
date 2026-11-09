"use strict";
/* Browser-render regression for full 1/5/20/180/360 day historical data.
 * The live published JSON from main is required; does not request external
 * prices, backfill false results or bypass maturity checks.
 */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const docRoot = path.resolve(__dirname, "../docs");
const source = fs.readFileSync(path.join(docRoot, "news-impact-history.js"), "utf8");
const html = fs.readFileSync(path.join(docRoot, "news-impact-history.html"), "utf8");
const summary = JSON.parse(fs.readFileSync(path.join(docRoot, "data/news_impact/official_study.json"), "utf8"));
const horizons = ["1D", "5D", "20D", "180D", "360D"];
const assets = ["美股S&P500", "NASDAQ", "台股", "黃金", "白銀", "WTI原油", "美元", "美債殖利率", "銅"];

assert.ok(horizons.every(h => html.includes('value="' + h + '"')), "missing historical horizon selector");
assert.ok(html.includes('id="reloadData"'), "reload button must exist");
assert.ok(html.includes("<th>180D</th><th>360D</th>"), "missing long-horizon columns");
assert.ok(horizons.every(h => summary.stats.some(s => s.horizon === h)), "published summary missing long horizons");

for (const group of summary.groups) {
  for (const asset of assets) {
    for (const horizon of ["180D", "360D"]) {
      const statistic = summary.stats.find(s => s.group === group.key && s.asset === asset && s.horizon === horizon);
      assert.ok(statistic, "missing " + group.key + " / " + asset + " / " + horizon);
      assert.ok(Number.isInteger(statistic.n) && statistic.n >= 0, "invalid sample count");
    }
  }
}

function page(initialData, group, asset, horizon) {
  const nodes = {}, handlers = {}, fetched = [];
  for (const id of ["group", "asset", "horizon", "eventN", "sampleNote", "avg", "relative", "positive",
    "summaryTable", "status", "caseTable", "pageLabel", "previous", "next", "meta", "reloadData"]) {
    nodes[id] = {
      value: id === "group" ? group : id === "asset" ? asset : id === "horizon" ? horizon : "",
      textContent: "", innerHTML: "", className: "", disabled: false,
      addEventListener(event, fn) { handlers[id + ":" + event] = fn; }
    };
  }
  const document = {
    getElementById(id) {
      assert.ok(nodes[id], "missing fake DOM element " + id);
      return nodes[id];
    }
  };
  async function fetch(url) {
    fetched.push(url);
    let payload;
    if (url.includes("/official_details/")) {
      const rel = url.split("?")[0].replace(/^\.\//, "");
      payload = JSON.parse(fs.readFileSync(path.join(docRoot, rel), "utf8"));
    } else payload = initialData;
    return {ok: true, json: async () => payload};
  }
  vm.runInNewContext(source, {document, fetch, Date, console}, {timeout: 1500});
  return {nodes, handlers, fetched};
}

async function settle() {
  for (let i = 0; i < 35; i++) await Promise.resolve();
}

async function main() {
  const a = page(summary, "OPEC", "美股S&P500", "360D");
  await settle();
  const recorded = summary.stats.find(s => s.group === "OPEC" && s.asset === "美股S&P500" && s.horizon === "360D");
  assert.equal(String(a.nodes.eventN.textContent), String(recorded.n));
  assert.ok(recorded.n > 0 && recorded.n < summary.minSample, "test needs current true OPEC small-sample study");
  assert.equal(a.nodes.avg.textContent, (recorded.meanPct > 0 ? "+" : "") + recorded.meanPct.toFixed(2) + "%");
  assert.ok(a.nodes.sampleNote.textContent.includes("小樣本"), "small N needs explicit caution");
  assert.ok(a.nodes.summaryTable.innerHTML.includes("小樣本／僅供參考"));
  assert.ok(a.nodes.caseTable.innerHTML.includes("未滿期間／缺資料"), "unmatured 360D must be labeled");
  assert.ok(a.nodes.caseTable.innerHTML.includes("%"), "some mature returns should display");
  assert.equal(a.nodes.reloadData.disabled, false);
  a.handlers["reloadData:click"]();
  await settle();
  assert.ok(a.fetched.length >= 3, "reload needs a fresh summary and details request");

  a.nodes.group.value = "美國選舉";
  a.handlers["group:change"]();
  await settle();
  const v = summary.stats.find(s => s.group === "美國選舉" && s.asset === "美股S&P500" && s.horizon === "360D");
  assert.equal(String(a.nodes.eventN.textContent), String(v.n));

  // Old 1/5/20 summary with a freshly deployed selector must say "stale",
  // never invent a false result of 0 samples or a 0.00% average.
  const old = {...summary, stats: summary.stats.filter(s => !["180D", "360D"].includes(s.horizon)),
    horizonsTradingDays: [1, 5, 20], longHorizonCoverage: undefined};
  const b = page(old, "美國選舉", "美股S&P500", "180D");
  await settle();
  assert.equal(b.nodes.eventN.textContent, "統計待更新");
  assert.equal(b.nodes.avg.textContent, "統計待更新");
  assert.ok(b.nodes.meta.textContent.includes("舊版摘要"));
  console.log("Historical study UI regression passed: long windows, all category/asset stat keys, small N, refresh and stale-summary handling");
}
main().catch(e => {console.error(e); process.exitCode = 1});
