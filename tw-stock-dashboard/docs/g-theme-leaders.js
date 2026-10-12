/* G Top20 sector concentration alert; read-only overlay, never changes ranking or strategy signals. */
var G_LEADER_CATALOG=null,G_LEADER_CATALOG_LOADING=null;
function gLeaderEscape(value){return String(value==null?"":value).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function gLeaderSplit(raw){
 var src=String(raw||""),parts=[],buf="",depth=0;
 for(var i=0;i<src.length;i++){var c=src[i];if(c==="("||c==="（")depth++;if(c===")"||c==="）")depth=Math.max(0,depth-1);
  if(depth===0&&/[、,，;；|｜]/.test(c)){if(buf.trim())parts.push(buf.trim());buf="";}else buf+=c;
 }
 if(buf.trim())parts.push(buf.trim());
 return parts.filter(function(x){return x!=="—"&&x!=="--"&&!/^(其他|未分類|未知|無|N\/A|原材料|其他.*|主\/被動元件)$/i.test(x)&&x.length<=36});
}
function gLeaderCpoCodes(catalog){
 var codes=new Set();
 if(!catalog||!Array.isArray(catalog.industries))return codes;
 catalog.industries.filter(function(g){return g.code==="CPO"||/^CPO/.test(g.name||"")}).forEach(function(industry){
  (industry.subgroups||[]).forEach(function(group){(group.stocks||[]).forEach(function(stock){var code=String(stock.code||"").trim();if(code)codes.add(code)})});
 });
 return codes;
}
function gLeaderStats(rows,catalog){
 var top=(Array.isArray(rows)?rows:[]).slice(0,20),cpo=gLeaderCpoCodes(catalog),seen=new Set(),groups=new Map();
 top.forEach(function(stock){
  if(!stock)return;var code=String(stock.code||"").trim(),key=String(stock.market||"")+"|"+code;if(!code||seen.has(key))return;seen.add(key);
  var tags=new Map();
  gLeaderSplit(stock.subIndustry).forEach(function(s){tags.set(s,1)});
  gLeaderSplit(stock.theme).forEach(function(s){if(!tags.has(s))tags.set(s,2)});
  if(cpo.has(code)||/(^|[、,，\s\/])CPO([／\/、,，\s]|$)/i.test(String(stock.theme||"")))tags.set("CPO",0);
  tags.forEach(function(priority,name){
   if(!groups.has(name))groups.set(name,{name:name,kind:priority,count:0,stocks:[]});
   var g=groups.get(name);g.kind=Math.min(g.kind,priority);g.count++;g.stocks.push({code:code,name:String(stock.name||""),market:String(stock.market||"")});
  });
 });
 var sorted=Array.from(groups.values()).filter(function(g){return g.count>6}).sort(function(a,b){return b.count-a.count||a.kind-b.kind||a.name.localeCompare(b.name,"zh-Hant")});
 return {leaders:sorted,listed:seen.size,slots:20,threshold:"超過30%（至少7/20）"};
}
function gLeaderStockLink(stock){
 var code=String(stock.code||""),exchange=stock.market==="上市"?"TWSE":stock.market==="上櫃"?"TPEX":"";
 var label=gLeaderEscape(code+" "+stock.name);
 return exchange&&/^[0-9A-Z]{4,8}$/.test(code)?'<a href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(exchange+":"+code)+'" target="_blank" rel="noopener noreferrer">'+label+'</a>':label;
}
function gLeaderCard(entry,catalog){
 var stats=gLeaderStats(entry.rows,catalog);if(!stats.leaders.length)return "";
 var top=stats.leaders[0],others=stats.leaders.slice(1);
 var other=others.length?'<div class="g-sector-other"><strong>其他集中題材：</strong>'+others.map(function(x){return '<span>'+gLeaderEscape(x.name)+' '+x.count+'/20（'+(x.count*5)+'%）</span>'}).join("")+'</div>':"";
 var cpoNote=stats.leaders.some(function(x){return x.name==="CPO"})?'<div class="g-sector-source">CPO 按現有「上游類股」的 CPO／矽光子研究名單辨識；不代表已取得 CPO 訂單或營收。</div>':"";
 return '<article class="g-sector-leader-card '+(entry.live?"is-live":"is-official")+'"><div class="g-sector-leader-head"><span class="g-sector-context">'+(entry.live?"🟠 盤中暫估":"🔵 盤後正式")+'｜'+gLeaderEscape(entry.date)+'</span><span class="g-sector-ratio">前20名 '+top.count+'/20 · '+(top.count*5)+'%</span></div>'+
 '<div class="g-sector-main"><span aria-hidden="true">🏆</span><strong>'+gLeaderEscape(top.name)+'｜'+(entry.live?"盤中":"盤後")+'最強入榜類股</strong></div>'+
 '<p class="g-sector-desc">G Top20 中有 '+top.count+' 檔屬於「'+gLeaderEscape(top.name)+'」，占比 '+(top.count*5)+'%，超過 30% 提醒門檻。'+(entry.live?"此為未收盤暫估，仍可能變動。":"此為已完成日K正式排名。")+'</p>'+
 '<details class="g-sector-members"><summary>查看 '+top.count+' 檔入榜股票</summary><div class="g-sector-stock-list">'+top.stocks.map(function(x){return '<span>'+gLeaderStockLink(x)+'</span>'}).join("")+'</div></details>'+
 other+cpoNote+'</article>';
}
function hideGThemeLeaders(){var panel=document.getElementById("gSectorLeaderPanel");if(panel){panel.hidden=true;panel.innerHTML=""}}
function renderGThemeLeaders(){
 var panel=document.getElementById("gSectorLeaderPanel");if(!panel)return;
 if(typeof MODEL==="undefined"||MODEL!=="G"||!DATA){hideGThemeLeaders();return}
 var live=typeof currentLiveG==="function"?currentLiveG():null;
 var source=String(DATA.dataDate||""),selection=DATA.gSelection,official=DATA.models&&DATA.models.G;
 var verified=!!(source&&selection&&selection.dataDate===source&&Array.isArray(official));
 var items=[];if(live)items.push({live:true,date:live.asOfDate,rows:live.rows});
 if(verified)items.push({live:false,date:source,rows:official});
 var cards=items.map(function(item){return gLeaderCard(item,G_LEADER_CATALOG)}).filter(Boolean);
 if(!cards.length){hideGThemeLeaders();return}
 panel.hidden=false;
 panel.innerHTML='<div class="g-sector-title">🔥 G Top20｜強勢類股集中提醒 <span>相同類股占前20名超過30%才顯示</span></div>'+
 '<div class="g-sector-cards">'+cards.join("")+'</div>'+
 '<div class="g-sector-foot">依原始 G 排名（不受下方題材篩選影響）；每檔股票在同一類股僅計一次。入榜集中度 ≠ 全市場漲幅排名、買進訊號或資金流入證據。'+(G_LEADER_CATALOG?'分類資料：'+gLeaderEscape(G_LEADER_CATALOG.dataDate||"最近更新"):'產業類股資料載入中；先依選股欄位判斷。')+'</div>';
}
function ensureGThemeCatalog(){
 if(G_LEADER_CATALOG||G_LEADER_CATALOG_LOADING||typeof fetch!=="function")return;
 G_LEADER_CATALOG_LOADING=fetch("./data/industry_upstream/latest.json",{cache:"no-store"}).then(function(resp){if(!resp.ok)throw new Error("sector HTTP "+resp.status);return resp.json()}).then(function(payload){
  if(!payload||!Array.isArray(payload.industries))throw new Error("invalid CPO sector source");
  G_LEADER_CATALOG=payload;renderGThemeLeaders();
 }).catch(function(){/* Keep normal industry-chain categories; never fake CPO membership. */}).finally(function(){G_LEADER_CATALOG_LOADING=null});
}
