/* Static integration + basic lifecycle smoke tests, no password value in test source. */
"use strict";
const assert=require("node:assert/strict"),fs=require("node:fs"),path=require("node:path"),vm=require("node:vm");
const base=path.resolve(__dirname,"../docs");
const js=fs.readFileSync(path.join(base,"site-access.js"),"utf8");
assert.match(js,/SITE_PASS_SHA256="[0-9a-f]{64}"/);
assert.match(js,/ACCESS_TTL_MS=48\*60\*60\*1000/);
assert.match(js,/crypto\.subtle\.digest\("SHA-256"/);
assert.match(js,/document\.documentElement\.setAttribute\("data-tw-access"/);
assert.match(js,/Same-origin/i.test(js) ? /Same-origin/i : /GitHub Pages 檔案仍可經由網址直接取得/);
assert.match(js,/body>\*:not\(#tw-access-gate\)/);
const pages=fs.readdirSync(base).filter(x=>x.endsWith(".html"));
assert.equal(pages.length,8,"Expected all eight public dashboard routes");
for(const p of pages){const html=fs.readFileSync(path.join(base,p),"utf8");const head=html.split(/<\/head>/i)[0];assert.match(head,/<script src="\.\/site-access\.js"><\/script>/,p+": early password gate is missing");assert.equal((html.match(/site-access\.js/g)||[]).length,1,p+": gate included more than once")}
function init(expiry){
 const state={attrs:{},events:{},style:null};
 const doc={
  head:{appendChild(node){state.style=node}},
  createElement(tag){return {tag,id:"",textContent:""}},
  documentElement:{setAttribute(k,v){state.attrs[k]=v}},
  addEventListener(k,callback){state.events[k]=callback},
  readyState:"loading"
 };
 const storage={getItem(){return expiry===null?null:String(expiry)},setItem(){},removeItem(){}};
 vm.runInNewContext(js,{document:doc,localStorage:storage,window:{crypto:{}},Date,Uint8Array,TextEncoder,location:{}},{timeout:500});
 return state;
}
assert.equal(init(null).attrs["data-tw-access"],"locked");
assert.equal(init(Date.now()-10).attrs["data-tw-access"],"locked");
assert.equal(init(Date.now()+48*60*60*1000+10000).attrs["data-tw-access"],"locked");
assert.equal(init(Date.now()+60*60*1000).attrs["data-tw-access"],"unlocked");
assert.match(init(null).style.textContent,/tw-access-gate/);
console.log("PASS: password gate syntax, eight routes, default lock and 48-hour expiration");
