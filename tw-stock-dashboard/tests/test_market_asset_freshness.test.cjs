const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),crypto=require("node:crypto"),path=require("node:path");
const root=path.join(__dirname,"../docs"),html=fs.readFileSync(path.join(root,"index.html"),"utf8");
const marketAssets=["market-sentiment.js","market-sentiment.css","market-command.js","market-command.css"];
test("homepage market assets use their exact Git blob hash as the cache-busting version",()=>{
 for(const filename of marketAssets){
  const re=new RegExp('(?:src|href)="\\./'+filename.replaceAll(".","\\.")+'\\?v=([0-9a-f]{12})"',"g");
  const versions=[...html.matchAll(re)].map(x=>x[1]);
  assert.equal(versions.length,1,filename+" must be linked exactly once with a content-addressed version");
  const content=fs.readFileSync(path.join(root,filename));
  const full=crypto.createHash("sha1").update("blob "+content.length+"\0").update(content).digest("hex");
  assert.equal(versions[0],full.slice(0,12),filename+" changed without updating index.html asset query: mobile browsers would reuse a stale file");
 }
});
test("both official-risk band labels and secondary guide use the new wording",()=>{
 const gauge=fs.readFileSync(path.join(root,"market-sentiment.js"),"utf8"),guide=fs.readFileSync(path.join(root,"market-command.js"),"utf8");
 for(const name of ["極度偏空","偏空觀察"]){
  assert.ok(gauge.includes('label:"'+name+'"'),"gauge label "+name);
  assert.ok(guide.includes('label:"'+name+'"'),"guide label "+name);
  assert.ok(html.includes("｜"+name+"</strong>"),"homepage printed band "+name);
 }
 for(const old of ["極高風險","風險偏高"]){
  assert.ok(!gauge.includes('label:"'+old+'"'),"gauge should not retain "+old);
 }
});
