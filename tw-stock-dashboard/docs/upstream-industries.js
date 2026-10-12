(function(){
"use strict";
const $=id=>document.getElementById(id);
const state={data:null,sector:null,query:""};
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const n=(v,dec=2)=>v==null||v===""||!Number.isFinite(Number(v))?"—":Number(v).toLocaleString("zh-TW",{minimumFractionDigits:dec,maximumFractionDigits:dec});
const pct=v=>v==null||!Number.isFinite(Number(v))?"—":(Number(v)>0?"+":"")+n(v,2)+"%";
const signed=v=>v==null?"":Number(v)>0?"positive":Number(v)<0?"negative":"";
const marketStock=s=>((s.market==="上櫃"?"TPEX":"TWSE")+":"+s.code);
const tv=s=>"https://www.tradingview.com/chart/?symbol="+encodeURIComponent(marketStock(s));
const codeOK=s=>/^[0-9]{4}$/.test(String(s.code||""))&&["上市","上櫃"].includes(s.market);
const fmtDate=s=>String(s||"—").slice(0,10);
function categories(){return state.data?.industries||[]}
function contains(stock,sectorName,groupName,q){
 if(!q)return true;
 const text=[stock.name,stock.code,stock.market,stock.industry,sectorName,groupName,...(stock.models||[])].join(" ").toLocaleLowerCase("zh-TW");
 return text.includes(q);
}
function matchedGroups(industry){
 return (industry.subgroups||[]).map(g=>{
  const rows=(g.stocks||[]).filter(s=>contains(s,industry.name,g.name,state.query));
  return {...g,rows};
 }).filter(g=>g.rows.length>0);
}
function nav(){
 const sectors=categories();
 $("industryNav").innerHTML=sectors.map(s=>'<button type="button" class="industry-button" data-sector="'+esc(s.code)+'" aria-current="'+(state.sector===s.code?'true':'false')+'"><span>'+esc(s.name)+'</span><em>'+n(s.stockCount,0)+' 檔</em></button>').join("");
}
function row(s){
 const tags=(s.models||[]).filter(x=>["G","G Pro","D","F","F2","A"].includes(x)).slice(0,3).map(m=>'<span class="tag">'+esc(m)+'</span>').join("");
 return '<tr><td class="stock-cell"><a href="'+esc(tv(s))+'" target="_blank" rel="noopener noreferrer">'+esc(s.code)+' '+esc(s.name)+'</a><small>'+esc(s.market)+' · '+esc(marketStock(s))+'</small></td>'+
 '<td class="numeric">'+n(s.close)+'</td><td class="numeric '+signed(s.ret5)+'">'+pct(s.ret5)+'</td><td class="numeric '+signed(s.ret20)+'">'+pct(s.ret20)+'</td>'+
 '<td class="optional numeric">'+n(s.momentumScore,1)+'</td><td class="optional">'+(tags||'<span class="sub">—</span>')+'</td></tr>';
}
function show(){
 nav();
 const current=categories().find(s=>s.code===state.sector);
 if(!current){$("results").innerHTML='<div class="empty">尚無經官方上游核對的產業。請檢查 GitHub 資料產製狀態。</div>';return}
 const groups=matchedGroups(current),found=new Set(groups.flatMap(g=>g.rows.map(s=>s.market+"_"+s.code)));
 const summary='<div class="industry-top"><div class="industry-title"><h2>'+esc(current.name)+'｜上游類股</h2><span class="stat">'+found.size+' 檔股票</span></div>'+
 '<p>官方產業鏈已核對上游細分類；分別列出各細項的上市櫃股票。'+(state.query?'｜搜尋：'+esc(state.query):'｜點擊分類可展開或收合對應股票。')+'</p>'+
 '<a class="industry-source" href="'+esc(current.source)+'" target="_blank" rel="noopener noreferrer">查看櫃買中心原始產業鏈分類 ↗</a></div>';
 let html=groups.map((g,i)=>{
  const inner=g.rows.map(row).join("");
  return '<details class="group" '+(i<3?'open':'')+'><summary><span class="group-name">'+esc(g.name)+'</span><span class="group-count">'+g.rows.length+' 檔</span></summary>'+
  '<div style="overflow-x:auto"><table class="stock-table"><thead><tr><th>股票／名稱</th><th class="numeric">收盤</th><th class="numeric">5D</th><th class="numeric">20D</th><th class="optional numeric">動能分位</th><th class="optional">入選模型</th></tr></thead><tbody>'+inner+'</tbody></table></div></details>';
 }).join("");
 $("results").innerHTML=summary+'<div class="groups">'+(html||'<div class="empty">目前此產業沒有符合搜尋條件且經核對的上游股票。可清除搜尋，或點官方來源核對其他細項。</div>')+'</div>';
}
function select(code,updateHistory=true){
 const s=categories().find(x=>x.code===code);if(!s)return;
 state.sector=s.code;show();
 if(updateHistory){const u=new URL(location.href);u.searchParams.set("industry",s.code);history.replaceState(null,"",u.pathname+u.search)}
}
function load(){
 $("status").textContent="正在讀取已核對之官方產業上游資料…";
 fetch("./data/industry_upstream/latest.json?v="+Date.now(),{cache:"no-store"}).then(async r=>{
  if(!r.ok)throw new Error("產業上游資料尚未發布（HTTP "+r.status+"）");
  return r.json();
 }).then(d=>{
  if(d.schema!=="tw-upstream-industries-v1"||!d.coverage||!Array.isArray(d.industries)||d.industries.length<5||d.coverage.verifiedCompanyPages<500)
   throw new Error("資料版本或官方核對涵蓋率不符");
  const markets=d.industries.some(s=>(s.subgroups||[]).some(g=>(g.stocks||[]).some(codeOK)));
  if(!markets)throw new Error("沒有有效上市櫃上游股票，拒絕顯示不完整資料");
  state.data=d;
  $("sectorCount").textContent=n(d.coverage.industries,0);
  $("stocksCount").textContent=n(d.coverage.distinctUpstreamStocks,0);
  $("membershipCount").textContent=n(d.coverage.upstreamMemberships,0);
  $("coverageCount").textContent=n(d.coverage.verifiedRatioPct,1)+"%";
  const dated=fmtDate(d.dataDate),today=new Intl.DateTimeFormat("sv-SE",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
  const age=Math.floor((Date.parse(today+"T12:00:00+08:00")-Date.parse(dated+"T12:00:00+08:00"))/86400000);
  const warn=d.coverage.verifiedRatioPct<90||age>7;
  $("status").classList.toggle("warn",warn);
  $("status").textContent="資料日 "+dated+"｜已核對公司 "+n(d.coverage.verifiedCompanyPages,0)+"/"+n(d.coverage.marketStocks,0)+"｜上游分類採櫃買中心官方產業價值鏈，非自行由股價推論。"+(warn?" ⚠ 部分公司分類未取得或資料日期較舊；未確認的股票不計入，不能視為全市場完整覆蓋。":"");
  const requested=new URLSearchParams(location.search).get("industry");
  const current=categories().find(x=>x.code===requested)||categories().find(x=>x.stockCount>0)||categories()[0];
  select(current.code,false);
 }).catch(e=>{
  $("status").classList.add("warn");$("status").textContent="⚠ 上游產業資料尚未就緒："+e.message+"。不拿一般產業別或 G 選股名單冒充已核對上游股票。";
  $("industryNav").innerHTML="";
  $("results").innerHTML='<div class="empty">資料尚未完成核對。請稍後重新載入，或查看 <a href="https://github.com/jacky-168168/Tradingview-testing/actions" target="_blank" rel="noopener noreferrer">GitHub 更新流程</a>。</div>';
 });
}
$("industryNav").addEventListener("click",e=>{const b=e.target.closest("[data-sector]");if(b)select(b.dataset.sector)});
$("search").addEventListener("input",e=>{state.query=e.target.value.trim().toLocaleLowerCase("zh-TW");if(state.data)show()});
$("clear").onclick=()=>{$("search").value="";state.query="";if(state.data)show()};
$("reload").onclick=load;load();
})();