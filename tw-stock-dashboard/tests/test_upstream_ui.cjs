"use strict";
const fs=require("node:fs"),path=require("node:path"),assert=require("node:assert/strict"),vm=require("node:vm");
const dir=path.resolve(__dirname,"../docs");
const html=fs.readFileSync(path.join(dir,"upstream.html"),"utf8");
const src=fs.readFileSync(path.join(dir,"upstream-industries.js"),"utf8");
new Function(src);
assert(!html.includes('class="kpis"'),"Unneeded top 4 statistics cards must be removed");
assert(html.includes('id="industryNav"')&&html.includes('id="results"'));
const sectors=[
 {code:"D000",name:"半導體",source:"https://ic.tpex.org.tw/introduce.php?ic=D000",stockCount:1,subgroups:[
  {name:"半導體用矽晶圓／磊晶材料（延伸上游）",count:1,source:"https://www.itis.org.tw/NetReport_Detail.aspx?rpno=613160445",
   note:"晶圓材料而不是代工",stocks:[{code:"6488",name:"環球晶",market:"上櫃",close:120,ret5:2,ret20:9,momentumScore:50,models:[],
      basis:"independent_industry_material",classification:"半導體材料供應鏈（延伸）",source:"https://www.itis.org.tw/NetReport_Detail.aspx?rpno=613160445"}]}]},
 {code:"A100",name:"太陽能",source:"https://ic.tpex.org.tw/introduce.php?ic=A100",stockCount:1,subgroups:[
  {name:"太陽能材料（跨產業應用）",count:1,source:"https://ic.tpex.org.tw/introduce.php?ic=A100",note:"官方材料分類不等於主要營收",
  stocks:[{code:"4760",name:"勤凱科技",market:"上櫃",close:80,ret5:1,ret20:3,momentumScore:40,models:[],
    basis:"tpex_official",classification:"櫃買中心上游階段",source:"https://ic.tpex.org.tw/company_chain.php?stk_code=4760",
    roleNote:"太陽能背銀但非純太陽能股"}]}]},
 {code:"I000",name:"通信網路",source:"https://ic.tpex.org.tw/introduce.php?ic=I000",stockCount:2,subgroups:[
  {name:"主動元件（光主動／晶片）",count:1,source:"https://ic.tpex.org.tw/introduce.php?ic=I000",note:"官方混合分類延伸公司產品",
   stocks:[{code:"3081",name:"聯亞",market:"上櫃",close:150,ret5:4,ret20:11,momentumScore:78,models:[],classification:"通信設備上游：光主動零組件",source:"https://www.lmoc.com.tw/index.php?i=1&id=282&lang=cht&option=module&task=dfile"}]},
  {name:"被動元件（電阻電容／濾波等）",count:1,source:"https://ic.tpex.org.tw/introduce.php?ic=I000",note:"國巨在被動元件產業中游",
   stocks:[{code:"2327",name:"國巨*",market:"上市",close:130,ret5:-1,ret20:6,momentumScore:77,models:[],classification:"通信設備上游（跨產業補列）；被動元件產業中游",basis:"tpex_cross_industry",source:"https://ic.tpex.org.tw/company_chain.php?stk_code=2327",roleNote:"國巨為通信設備上游供應商，但在被動元件產業本身屬中游製造商。"}]}
 ]},
 {code:"CPO",name:"CPO／矽光子",source:"https://www.trendforce.com.tw/presscenter/news/20260727-13150.html",sourceLabel:"CPO 產業供應鏈研究（非櫃買官方產業碼）",stockCount:1,subgroups:[
  {name:"FAU／光纖陣列與精密耦合（核心上游）",count:1,source:"https://www.trendforce.com.tw/presscenter/news/20260727-13150.html",note:"非官方產業碼；與CPO訂單不同",
   stocks:[{code:"3363",name:"上詮",market:"上櫃",close:222,ret5:5,ret20:10,momentumScore:81,models:[],basis:"cpo_industry_research",classification:"CPO 上游光學零件研究名單（非官方類股）",source:"https://finmoconf.diveinvest.net/presentation/691c7285bab52fb5c8f0575f",roleNote:"CPO FAU 光纖陣列，不等於已取得客戶訂單"}]}
 ]},
 ...["L000","F000","K000","3000","A300"].map(code=>({code,name:code,stockCount:0,subgroups:[],source:"https://ic.tpex.org.tw/introduce.php?ic="+code}))
];
sectors.push(...[{code:"IC_SUB",name:"IC 載板／ABF・BT（研究）",stockCount:0,source:"https://ic.tpex.org.tw/introduce.php?ic=L000",subgroups:[]},{code:"LEO",name:"低軌衛星／太空通訊（研究）",stockCount:0,source:"https://ic.tpex.org.tw/introduce.php?ic=4100",subgroups:[]}]);
const payload={schema:"tw-upstream-industries-v2",dataDate:"2026-10-12",coverage:{industries:11,marketStocks:1952,verifiedCompanyPages:1952,verifiedRatioPct:100,distinctUpstreamStocks:5,upstreamMemberships:5},industries:sectors};
const events={},els={};
function el(id){if(!els[id])els[id]={innerHTML:"",textContent:"",value:"",classList:{toggle(){} ,add(){}},addEventListener(type,fn){events[id+"|"+type]=fn}};return els[id]}
const ctx={document:{getElementById:el},fetch:()=>Promise.resolve({ok:true,json:()=>Promise.resolve(payload)}),Date,Intl,URL,URLSearchParams,Number,Set,String,Array,console,
location:{href:"https://example.com/upstream.html",search:""},history:{replaceState(){}},
};
vm.runInNewContext(src,ctx,{timeout:1000});
setImmediate(()=>{
 try{
  assert(els.industryNav.innerHTML.startsWith('<button type="button" class="industry-button" data-sector="all"'),"All must be first");
  assert(els.industryNav.innerHTML.includes('🌐 所有'),"All selector label");
  assert(els.results.innerHTML.includes('所有產業｜上游類股總覽'),"All is default");
  assert(els.results.innerHTML.includes('半導體｜上游類股')&&els.results.innerHTML.includes('太陽能｜上游類股'),"All must show multiple distinct sectors");
  assert(els.results.innerHTML.includes('6488 環球晶')&&els.results.innerHTML.includes('4760 勤凱科技'),"All must contain every upstream stock");
  assert(els.results.innerHTML.includes('5 檔股票'),"All stocks must be deduplicated");
  assert(els.results.innerHTML.includes('核對依據'),"Individual company source must be visible");
  assert(els.results.innerHTML.includes('非純太陽能股'),"Cross-industry evidence should be visible");
  assert(els.results.innerHTML.includes('主動元件（光主動／晶片）')&&els.results.innerHTML.includes('被動元件（電阻電容／濾波等）'),"Independent active/passive headings required");
  assert(els.results.innerHTML.includes('2327 國巨*')&&els.results.innerHTML.includes('3081 聯亞'),"Both verified active and passive companies should be listed");
  assert(els.results.innerHTML.includes('被動元件產業本身屬中游'),"Yageo midstream caveat must be clearly visible");
  assert(els.industryNav.innerHTML.includes('CPO／矽光子'),"CPO must be selectable");
  assert(els.results.innerHTML.includes('CPO／矽光子｜上游類股')&&els.results.innerHTML.includes('3363 上詮'),"All must show CPO FAU supplier");
  assert(els.results.innerHTML.includes('CPO 產業供應鏈研究（非櫃買官方產業碼）'),"Clearly independent from official TPEx industry chains");
  const click=events["industryNav|click"];assert.equal(typeof click,"function");
  click({target:{closest:()=>({dataset:{sector:"D000"}})}});
  assert(els.results.innerHTML.includes('6488 環球晶')&&!els.results.innerHTML.includes('4760 勤凱科技'),"Single sector remains isolated");
  click({target:{closest:()=>({dataset:{sector:"I000"}})}});
  assert(els.results.innerHTML.includes('2327 國巨*')&&els.results.innerHTML.includes('3081 聯亞')&&!els.results.innerHTML.includes('4760 勤凱科技'),"Communication sector must not mix unrelated solar");
  click({target:{closest:()=>({dataset:{sector:"CPO"}})}});
  assert(els.results.innerHTML.includes('3363 上詮')&&!els.results.innerHTML.includes('2327 國巨*'),"CPO optical supply should exclude unrelated passive capacitor maker");
  click({target:{closest:()=>({dataset:{sector:"all"}})}});
  assert(els.results.innerHTML.includes('4760 勤凱科技'),"All can be restored");
  console.log("PASS: All first/default, 8 TPEx and 1 CPO research categories, sector switch, GlobalWafers/sun-paste evidence, no KPI boxes");
 }catch(e){console.error(e);process.exitCode=1}
});
