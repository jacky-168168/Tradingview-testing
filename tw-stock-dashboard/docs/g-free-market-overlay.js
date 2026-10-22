/* Free TWSE/TPEx market-research overlay. Historical snapshots stay historical. */
(function(){
"use strict";
function h(s){return String(s==null?"":s).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]})}
function n(v,d){if(v==null||v==="")return "—";var x=Number(v);return Number.isFinite(x)?x.toFixed(d):"—"}
function render(g){
 var root=document.getElementById("gFreeMarketPanel");if(!root)return;
 var ov=g&&g.freeMarketOverlay;
 if(!ov||ov.asOfDate!==g.asOfDate||ov.status==="unavailable"){root.hidden=true;return}
 root.hidden=false;
 var ranked=ov.industryMomentum&&Array.isArray(ov.industryMomentum.ranking)?ov.industryMomentum.ranking:[];
 var old=window.GIntradayTimeline&&GIntradayTimeline.historical(g);
 var label=(old?"歷史快照｜":"盤中研究｜")+h(g.asOfDate)+" "+h(String(g.publishedAt||"").slice(11,19));
 var head='<header class="g-free-head"><h3>📊 免費官方資料｜產業強度與交易限制</h3><span>'+label+'</span></header>';
 var rows=ranked.slice(0,8).map(function(r){
  var score=Number(r.scorePct),cls=score>0?"pos":score<0?"neg":"";
  var move=r.rankMove==null?"":("｜名次"+(r.rankMove>0?"↑"+r.rankMove:r.rankMove<0?"↓"+Math.abs(r.rankMove):"—"));
  return '<tr><td>'+h(r.rank)+'</td><td><strong>'+h(r.industry)+'</strong></td><td class="'+cls+'">'+(score>0?"+":"")+n(score,2)+'%</td><td>'+n(r.breadthPct,1)+'%</td><td>'+n(r.turnoverEstimatedB,2)+' 億</td><td>'+h(r.quoted)+' / '+h(r.total)+'</td><td>'+h((r.leaders||[]).map(function(x){return x.name}).join("、"))+h(move)+'</td></tr>';
 }).join("");
 var rank='<div class="g-free-section"><h4>全市場產業強度（Top 8）</h4>'+(rows?'<div class="g-free-scroll"><table><thead><tr><th>名次</th><th>產業</th><th>強度</th><th>上漲占比</th><th>估計成交額</th><th>有效／母體</th><th>主要成交個股</th></tr></thead><tbody>'+rows+'</tbody></table></div>':'<p>此輪有效成交或產業涵蓋率不足，暫不顯示產業排名。</p>')+'<p class="g-free-note">強度＝實際成交價漲跌幅的 √估計成交額加權；估計成交額＝現價 × 累計成交股數，非交易所精確成交金額，也不是主力淨流入。排除未成交與買賣盤推算價；族群最低有效涵蓋率 60%。</p></div>';
 var restrictions=ov.tradeRestrictions||{},markets=restrictions.markets||{},flags=ov.topGRestrictions||[];
 var active=flags.filter(function(x){return x.status==="處置公告期間"}),unverified=[ "上市","上櫃" ].filter(function(x){return !markets[x]||markets[x].status!=="verified"});
 var stockMap={};(g.rows||[]).forEach(function(x){stockMap[x.market+"_"+x.code]=x.name||x.code});
 var risk=active.map(function(x){return '<span class="g-free-flag">'+h(x.market)+" "+h(x.code)+" "+h(stockMap[x.market+"_"+x.code]||"")+'｜處置公告期間</span>'}).join("");
 var status=unverified.length?'<p class="g-free-warn">⚠ '+h(unverified.join("、"))+'處置公告目前無法查證，不能視為沒有交易限制。</p>':'<p class="g-free-note">本輪 G Top20 未列入已取得的官方處置公告不等於保證可當沖；交易前仍需核對券商與交易所公告。</p>';
 var controls='<div class="g-free-section"><h4>G 榜單處置公告檢查</h4>'+(risk||'<p>本輪未發現已核實的處置公告期間標的。</p>')+status+
 '<p class="g-free-note">來源：<a href="https://www.twse.com.tw/rwd/zh/announcement/punish?response=json" target="_blank" rel="noopener noreferrer">證交所</a>／<a href="https://www.tpex.org.tw/openapi/v1/tpex_disposal_information" target="_blank" rel="noopener noreferrer">櫃買中心</a>。只作警示，不改變 G 排名與交易決策。</p></div>';
 var ctx=g&&g.gSignalContext,context='';
 if(ctx&&ctx.status!=="unavailable"&&ctx.asOfDate===g.asOfDate){
  var prev=ctx.previousCloseRisk||{},m=ctx.market||{},breadth=m.breadth||{},listed=breadth["上市"]||{},otc=breadth["上櫃"]||{};
  var risk=prev.score==null?"未取得":h(prev.score)+" 分（"+h(prev.date||"")+" 收盤）";
  var strength=(ctx.top20||[]).filter(function(x){return Number.isFinite(x.relativeToEqualWeightPeersPct)}).sort(function(a,b){return b.relativeToEqualWeightPeersPct-a.relativeToEqualWeightPeersPct}).slice(0,5);
  var leaders=strength.map(function(x){return '<span class="g-free-flag g-free-neutral">'+h(x.code)+" "+h(x.name)+" 相對同市場均漲 "+(x.relativeToEqualWeightPeersPct>0?"+":"")+n(x.relativeToEqualWeightPeersPct,2)+'pp</span>'}).join("")||"尚無足夠實際成交樣本";
  context='<div class="g-free-section g-free-wide"><h4>📍 本輪 G 訊號 × 大盤情境（只記錄，不改選股）</h4>'+
   '<p><strong>前一日正式風險分數：</strong>'+risk+'｜<strong>盤中實際成交價市場廣度：</strong>'+n(m.allMarketUpPct,1)+'% 上漲（'+h(m.breadthBand||"資料不足")+'）</p>'+
   '<p>上市上漲 '+n(listed.upPct,1)+'%（'+h(listed.tradedSample??0)+' 檔）｜上櫃上漲 '+n(otc.upPct,1)+'%（'+h(otc.tradedSample??0)+' 檔）</p>'+
   '<p><strong>本輪相對同市場平均漲幅較強：</strong>'+leaders+'</p>'+
   '<p class="g-free-note">風險分數是前一交易日收盤資料，不能視為當輪即時風險分數；相對強弱比較實際成交價股票的等權均漲，非加權或櫃買指數。歷史輪次不能當成獨立買進次數，尚無對應績效回測。</p></div>';
 }
 root.innerHTML=head+'<div class="g-free-grid">'+context+rank+controls+'</div>';
}
window.renderFreeGMarketOverlay=render;
})();
