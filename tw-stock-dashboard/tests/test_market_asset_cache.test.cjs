const test=require("node:test"),assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const docs=path.join(__dirname,"../docs"),html=fs.readFileSync(path.join(docs,"index.html"),"utf8");
function gitBlobSha(buf){return crypto.createHash("sha1").update(Buffer.from("blob "+buf.length+"\\0".replace("\\\\0","\\0"))).update(buf).digest("hex")}
test("all four market CSS/JS asset URLs use immutable source content SHA, never stale manually tagged URLs",()=>{
 for(const name of ["market-command.js","market-sentiment.js","market-command.css","market-sentiment.css"]){
  const content=fs.readFileSync(path.join(docs,name)),expected=gitBlobSha(content);
  const matches=html.match(new RegExp("./"+name.replace(".","\\.")+"\\?v=([a-f0-9]{40})","g"))||[];
  assert.equal(matches.length,1,name+" must have exactly one content-hash version in homepage");
  assert.ok(html.includes("./"+name+"?v="+expected),name+" URL must update automatically in code review whenever the source file changes");
 }
});
test("new bearish labels are present in both market scoring and gauge, without the stale text",()=>{
 for(const name of ["market-command.js","market-sentiment.js"]){
  const source=fs.readFileSync(path.join(docs,name),"utf8");
  assert.ok(source.includes("極度偏空"),name);
  assert.ok(source.includes("偏空觀察"),name);
  assert.ok(!source.includes("極高風險"),name+" still exposes old label");
  assert.ok(!source.includes("風險偏高"),name+" still exposes old label");
 }
});
