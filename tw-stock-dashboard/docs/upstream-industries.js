(function(){
"use strict";
const $=id=>document.getElementById(id);
const state={data:null,sector:"all",query:""};
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
 $("industryNav").innerHTML='<button type="button" class="industry-button" data-sector="all" aria-current="'+(state.sector==="all"?"true":"false")+'"><span>🌐 所有</span><em>'+n(state.data?.coverage?.distinctUpstreamStocks,0)+' 檔</em></button>'+sectors.map(s=>'<button type="button" class="industry-button" data-sector="'+esc(s.code)+'" aria-current="'+(state.sector===s.code?'true':'false')+'"><span>'+esc(s.name)+'</span><em>'+n(s.stockCount,0)+' 檔</em></button>').join("");
}
function row(s){
 const tags=(s.models||[]).filter(x=>["G","G Pro","D","F","F2","A"].includes(x)).slice(0,3).map(m=>'<span class="tag">'+esc(m)+'</span>').join("");
 const url=String(s.source||""),trusted=/^https:\/\/(ic\.tpex\.org\.tw|www\.itis\.org\.tw)\//.test(url);
 const evidence=trusted?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">分類來源 ↗</a>':"";
 const note=s.roleNote||"";
 const role='<small>'+esc(s.classification||"")+"｜"+evidence+'</small>'+(s.basis==="independent_industry_material"?'<small class="stock-note">晶圓材料供應商，非晶圓代工廠</small>':"")+(s.code==="4760"?'<small class="stock-note">'+esc(note)+' <a href="https://ampletec.com.tw/about.asp" target="_blank" rel="noopener noreferrer">公司說明 ↗</a></small>':"");
 return '<tr><td class="stock-cell"><a href="'+esc(tv(s))+'" target="_blank" rel="noopener noreferrer">'+esc(s.code)+' '+esc(s.name)+'</a><small>'+esc(s.market)+' · '+esc(marketStock(s))+'</small>'+role+'</td>'+
 '<td class="numeric">'+n(s.close)+'</td><td class="numeric '+signed(s.ret5)+'">'+pct(s.ret5)+'</td><td class="numeric '+signed(s.ret20)+'">'+pct(s.ret20)+'</td>'+
 '<td class="optional numeric">'+n(s.momentumScore,1)+'</td><td class="optional">'+(tags||'<span class="sub">—</span>')+'</td></tr>';
}
function groupMarkup(g,i){
 const inner=g.rows.map(row).join("");
 const extra=g.source&&g.source!==""?'<a class="industry-source" href="'+esc(g.source)+'" target="_blank" rel="noopener noreferrer">細項分類來源 ↗</a>':"";
 const note=g.note?'<div class="group-note">'+esc(g.note)+'</div>':"";
 return '<details class="group" '+(state.sector!=="all"&&i<3?"open":"")+'><summary><span class="group-name">'+esc(g.name)+'</span><span class="group-count">'+g.rows.length+' 檔</span></summary>'+
 note+extra+'<div style="overflow-x:auto"><table class="stock-table"><thead><tr><th>股票／名稱</th><th class="numeric">收盤</th><th class="numeric">5D</th><th class="numeric">20D</th><th class="optional numeric">動能分位</th><th class="optional">入選模型</th></tr></thead><tbody>'+inner+'</tbody></table></div></details>';
}
function industryMarkup(industry,allMode){
 const groups=matchedGroups(industry);
 const unique=new Set(groups.flatMap(g=>g.rows.map(s=>s.market+"_"+s.code)));
 if(state.query&&!groups.length)return "";
 const external='<a class="industry-source" href="'+esc(industry.source)+'" target="_blank" rel="noopener noreferrer">櫃買中心原始產業鏈 ↗</a>';
 const subtitle=allMode?'此產業經核對的上游細項；點選細項可展開股票。':'上游細項對應上市櫃股票，點選類別可展開。';
 return '<section class="industry-block" aria-label="'+esc(industry.name)+' 上游股票">'+
 '<div class="industry-top"><div class="industry-title"><h2>'+esc(industry.name)+'｜上游類股</h2><span class="stat">'+unique.size+' 檔股票</span></div>'+
 '<p>'+subtitle+(state.query?'｜搜尋：'+esc(state.query):'')+'</p>'+external+'</div>'+
 '<div class="groups">'+(groups.length?groups.map(groupMarkup).join(""):'<div class="empty">此產業尚無符合搜尋條件的上游股票。</div>')+'</div></section>';
}
function show(){
 nav();
 if(!state.data){$("results").innerHTML='<div class="empty">尚無經核對的產業資料。</div>';return}
 if(state.sector==="all"){
  const inds=categories();
  const visible=inds.filter(ind=>matchedGroups(ind).length>0);
  const keys=new Set(visible.flatMap(ind=>matchedGroups(ind).flatMap(g=>g.rows.map(x=>x.market+"_"+x.code))));
  $("results").innerHTML='<div class="all-summary"><div><h2>🌐 所有產業｜上游類股總覽</h2><p>依產業分區、依上游細項展開股票；不同產業同一家公司可能重複出現，總數以股票去重計算。</p></div><strong>'+visible.length+' 個產業｜'+keys.size+' 檔股票</strong></div>'+
   (visible.map(ind=>industryMarkup(ind,true)).join("")||'<div class="empty">所有產業都沒有符合搜尋的股票。</div>');
  return;
 }
 const current=categories().find(ind=>ind.code===state.sector);
 $("results").innerHTML=current?industryMarkup(current,false):'<div class="empty">查無此產業，請從左側重新選擇。</div>';
}
function select(code,updateHistory=true){
 if(code!=="all"&&!categories().some(s=>s.code===code))return;
 state.sector=code;show();
 if(updateHistory){const u=new URL(location.href);if(code==="all")u.searchParams.delete("industry");else u.searchParams.set("industry",code);history.replaceState(null,"",u.pathname+u.search)}
}
function load(){
 $("status").textContent="正在讀取已核對之官方產業上游資料…";
 fetch("./data/industry_upstream/latest.json?v="+Date.now(),{cache:"no-store"}).then(async r=>{
  if(!r.ok)throw new Error("產業上游資料尚未發布（HTTP "+r.status+"）");
  return r.json();
 }).then(d=>{
  if(d.schema!=="tw-upstream-industries-v2"||!d.coverage||!Array.isArray(d.industries)||d.industries.length<5||d.coverage.verifiedCompanyPages<500)
   throw new Error("資料版本或官方核對涵蓋率不符");
  const markets=d.industries.some(s=>(s.subgroups||[]).some(g=>(g.stocks||[]).some(codeOK)));
  if(!markets)throw new Error("沒有有效上市櫃上游股票，拒絕顯示不完整資料");
  state.data=d;

  const dated=fmtDate(d.dataDate),today=new Intl.DateTimeFormat("sv-SE",{timeZone:"Asia/Taipei",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
  const age=Math.floor((Date.parse(today+"T12:00:00+08:00")-Date.parse(dated+"T12:00:00+08:00"))/86400000);
  const wafer=d.industries.find(s=>s.code==="D000")?.subgroups?.find(g=>g.name.includes("半導體用矽晶圓"));
  if(!wafer||!wafer.stocks.some(x=>x.code==="6488"&&x.basis==="independent_industry_material"))throw new Error("環球晶與矽晶圓材料分類尚未完成核對");
  const warn=d.coverage.verifiedRatioPct<90||age>7;
  $("status").classList.toggle("warn",warn);
  $("status").textContent="資料日 "+dated+"｜已核對公司 "+n(d.coverage.verifiedCompanyPages,0)+"/"+n(d.coverage.marketStocks,0)+"｜上游採櫃買中心各產業階段；半導體用矽晶圓供應商另據工研院 ITIS 延伸分類，均可點股票查看來源。"+(warn?" ⚠ 部分公司分類未取得或資料日期較舊；未確認的股票不計入，不能視為全市場完整覆蓋。":"");
  const requested=new URLSearchParams(location.search).get("industry");
  const current=categories().find(x=>x.code===requested);
  select(current?current.code:"all",false);
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