"use strict";
/* Audits real published map, not just synthetic UI fixtures. A cited theme is not an official upstream row. */
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,"../docs");
const d=JSON.parse(fs.readFileSync(path.join(root,"data/industry_upstream/latest.json"),"utf8"));
const catalog=JSON.parse(fs.readFileSync(path.join(root,"data/industry_upstream/theme_catalog.json"),"utf8"));
const html=fs.readFileSync(path.join(root,"upstream.html"),"utf8");
const js=fs.readFileSync(path.join(root,"upstream-industries.js"),"utf8");
assert.equal(d.schema,"tw-upstream-industries-v2");
assert.equal(d.industries.length,11);
assert.equal(d.coverage.industries,11);
assert.ok(d.coverage.verifiedCompanyPages>=500);
assert.equal(catalog.schema,"tw-industry-chain-research-overlay-v1");
const by=Object.fromEntries(d.industries.map(x=>[x.code,x]));
for(const code of ["D000","L000","CPO","A100","IC_SUB","LEO"])assert.ok(by[code],code);
const group=(sector,name)=>{const x=by[sector].subgroups.find(g=>g.name===name);assert.ok(x,sector+"/"+name);return x};
const codes=g=>new Set(g.stocks.map(x=>x.code));
const has=(g,list)=>list.every(x=>codes(g).has(x));
assert.ok(has(group("L000","玻璃纖維／玻纖布"),["1303","1802","1815","5340","5475"]));
assert.ok(by.CPO.subgroups.every(g=>g.stage.startsWith("研究延伸")),"CPO is independent industry research, not official TPEx upstream");
assert.ok(group("D000","半導體用矽晶圓／磊晶材料（延伸上游）").stage.startsWith("研究延伸"),"Wafer material category must be independent ITIS research");
assert.equal(group("LEO","衛星射頻／毫米波／天線零組件（上游）").stocks.find(x=>x.code==="3138").market,"上市","耀登 3138 is TWSE listed, not OTC");
assert.ok(has(group("L000","銅箔基板 CCL／高速基材（中游延伸）"),["2383","6213","6274","1303"]));
assert.ok(has(group("L000","PCB 精密鑽針／鑽孔耗材（製程上游供應）"),["8021"]));
assert.ok(!codes(group("L000","玻璃纖維／玻纖布")).has("8021"));
assert.ok(has(group("IC_SUB","ABF／BT IC 載板製造（中游）"),["3037","8046","3189","4958"]));
assert.ok(!codes(group("IC_SUB","載板用樹脂／材料（上游跨應用）")).has("3037"));
const union=s=>new Set(by[s].subgroups.flatMap(g=>g.stocks.map(x=>x.code)));
assert.ok(["2313","2367","2383","3491","3138","6285","3105"].every(x=>union("LEO").has(x)));
assert.ok(!union("LEO").has("2330"));
for(const sector of d.industries){
 const count=new Set(sector.subgroups.flatMap(g=>g.stocks.map(r=>r.market+"_"+r.code))).size;
 assert.equal(sector.stockCount,count,sector.code+" count");
 for(const g of sector.subgroups){
  assert.equal(g.count,g.stocks.length,sector.code+"/"+g.name+" row count");
  for(const row of g.stocks){
   assert.match(row.code,/^\d{4}$/);assert.ok(["上市","上櫃"].includes(row.market));
   assert.ok(/^https:\/\//.test(row.source));
   if(row.basis==="industry_theme_research"){
    assert.ok(g.stage&&!g.stage.includes("官方上游"),"Theme stage must not be labeled official upstream");
    assert.ok(row.classification.includes("研究延伸"),"Theme stock classification missing");
    assert.ok(row.roleNote.includes("不等於"),"Avoid falsely declaring customer orders");
   }
  }
 }
}
const all=d.industries.flatMap(sec=>sec.subgroups.flatMap(g=>g.stocks));
assert.equal(new Set(all.map(x=>x.market+"_"+x.code)).size,d.coverage.distinctUpstreamStocks);
assert.equal(all.length,d.coverage.upstreamMemberships);
assert.ok(html.includes("上游＋研究延伸")&&html.includes("鑽針"));
assert.ok(js.includes('industry.code==="LEO"')&&js.includes('industry.code==="IC_SUB"')&&js.includes("industry_theme_research"));
console.log("PASS 11 verified sectors, PCB CCL/drills, substrates, LEO stage boundaries, sources, counts, no fabricated order claims");
