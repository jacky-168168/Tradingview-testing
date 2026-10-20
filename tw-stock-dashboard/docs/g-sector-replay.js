/* Only archived real G rounds, never synthesizes absent sessions or returns. */
(function(){
"use strict";
const $=id=>document.getElementById(id),ROOT="./data/g_intraday/archive/";
let days=[],rounds=[],index=0,request=0;
function esc(v){return String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function num(v,d=1){return typeof v==="number"&&Number.isFinite(v)?v.toFixed(d):"—"}
function signed(v,d=2){return typeof v==="number"&&Number.isFinite(v)?(v>0?"+":"")+v.toFixed(d):"—"}
async function json(url){let u=url+(url.includes("?")?"&":"?")+"t="+Date.now();let resp=await fetch(u,{cache:"no-store"});if(!resp.ok)throw Error("HTTP "+resp.status);return resp.json()}
function valid(entry,day,snap){
 return !!(snap&&snap.quality==="intraday-provisional-allmarket"&&snap.asOfDate===day&&snap.publishedAt===entry.publishedAt&&Array.isArray(snap.rows));
}
function contextText(g){
 const m=g?.gSignalContext?.market,risk=g?.gSignalContext?.previousCloseRisk;
 if(!m)return "此輪尚未開始封存 G 訊號市場情境；不以盤後風險分數回填。";
 return "市場上漲家數占比 "+num(m.allMarketUpPct,1)+"%（"+esc(m.breadthBand||"未分類")+"）｜前一完整收盤風險分數 "+(risk?.score==null?"未取得":esc(risk.score)+" 分（"+esc(risk.date)+"）")+"。本輪不是獨立買進交易紀錄。";
}
function buildChange(cur,previous){
 if(!cur)return [];
 const old=new Map(((previous?.freeMarketOverlay?.industryMomentum?.ranking)||[]).map(x=>[x.industry,x]));
 return cur.map(x=>{const p=old.get(x.industry),score=typeof p?.scorePct==="number"&&typeof x.scorePct==="number"?Math.round((x.scorePct-p.scorePct)*100)/100:null;
 return {...x,priorScoreDiff:score,priorRankMove:Number.isInteger(p?.rank)&&Number.isInteger(x.rank)?p.rank-x.rank:null}})
}
function render(){
 let entry=rounds[index],g=entry?.snap;
 $("prev").disabled=index===0;$("next").disabled=index>=rounds.length-1;
 $("timeline").max=Math.max(0,rounds.length-1);$("timeline").value=index;
 if(!entry){$("round").textContent="無封存輪次";$("status").textContent="該日期沒有成功封存的有效盤中輪次";$("sectorRows").innerHTML='<tr><td colspan="9">無資料</td></tr>';$("summary").innerHTML="";$("context").textContent="";return}
 $("round").textContent=entry.publishedAt.slice(11,19)+"（第 "+(index+1)+"／"+rounds.length+" 輪）";
 if(!g){$("status").textContent="⚠ 這輪的封存檔讀取失敗或校驗未通過；不使用其他輪次資料補足。";$("sectorRows").innerHTML='<tr><td colspan="9">資料無法驗證</td></tr>';$("summary").innerHTML="";$("context").textContent="";return}
 const coverage=g.coverage||{},quality=g.freeMarketOverlay?.industryMomentum,items=quality?.ranking||[];
 const prev=rounds.slice(0,index).reverse().find(x=>Array.isArray(x.snap?.freeMarketOverlay?.industryMomentum?.ranking));
 const ref=prev?.snap;
 $("status").textContent=(items.length?"✅ 產業研究資料已封存。":"⚠ 此輪尚未封存免費產業強度資料，不能推算排名。")+
 (ref?" 前一筆可比較輪次："+ref.publishedAt.slice(11,19):" 尚無同日可比較的較早產業資料。");
 const breadth=g.marketBreadth?.total||{};
 $("summary").innerHTML=[
  ["本輪發布",esc(g.publishedAt.slice(11,19))],
  ["有效報價",esc(coverage.valid??"—")+"／"+esc(coverage.total??"—")],
  ["實際成交上漲家數比",num(breadth.upPct)+"%"]
 ].map(x=>'<div class="metric"><span>'+x[0]+'</span><strong>'+x[1]+'</strong></div>').join("");
 $("context").textContent=contextText(g);
 const rendered=buildChange(items,ref);
 $("sectorRows").innerHTML=rendered.length?rendered.map(x=>{
  const move=x.priorRankMove,change=x.priorScoreDiff;
  const delta=ref?'<span class="'+(change>=0?"pos":"neg")+'">'+signed(change,2)+'pp</span>':'—';
  return '<tr><td>'+esc(x.rank)+'</td><td><b>'+esc(x.industry)+'</b></td><td class="'+(x.scorePct>=0?"pos":"neg")+'">'+signed(x.scorePct)+'%</td><td>'+delta+'</td><td>'+(move===null?"—":move===0?"持平":move>0?"↑"+move:"↓"+(-move))+'</td><td>'+num(x.breadthPct)+'%</td><td>'+num(x.turnoverEstimatedB,2)+' 億</td><td>'+esc(x.quoted)+'／'+esc(x.total)+'</td><td>'+esc((x.leaders||[]).map(y=>y.name).join("、"))+'</td></tr>';
 }).join(""):'<tr><td colspan="9">尚無符合資料品質要求的產業強度快照。</td></tr>';
}
async function select(day){
 const id=++request;rounds=[];index=0;render();$("status").textContent="正在核對 "+day+" 已成功封存的每一輪…";
 try{
  if(!/^\d{4}-\d{2}-\d{2}$/.test(day)||!days.includes(day))throw Error("無效交易日");
  const cat=await json(ROOT+day+"/index.json");
  if(cat.date!==day||!Array.isArray(cat.snapshots))throw Error("封存索引格式錯誤");
  const list=cat.snapshots.filter(x=>/^\d{6}(?:-\d+)?\.json$/.test(x.file||"")&&!isNaN(Date.parse(x.publishedAt))).slice(-50);
  const fetched=await Promise.all(list.map(async e=>{
   try{const snap=await json(ROOT+day+"/"+e.file);return {...e,snap:valid(e,day,snap)?snap:null}}
   catch(_){return {...e,snap:null}}
  }));
  if(id!==request)return;
  rounds=fetched.sort((a,b)=>a.publishedAt.localeCompare(b.publishedAt));
  index=Math.max(0,rounds.length-1);render();
 }catch(e){if(id!==request)return;$("status").textContent="⚠ "+e.message;render()}
}
async function init(){
 try{
  let cat=await json(ROOT+"index.json");days=Array.isArray(cat.dates)?cat.dates.filter(x=>/^\d{4}-\d{2}-\d{2}$/.test(x)).sort().reverse():[];
  $("tradeDay").innerHTML=days.map(d=>'<option value="'+esc(d)+'">'+esc(d)+'</option>').join("");
  if(days.length)await select(days[0]);else{$("status").textContent="尚無任何可回放交易日";render()}
 }catch(e){$("status").textContent="⚠ 封存日期索引讀取失敗："+e.message}
}
$("tradeDay").addEventListener("change",()=>select($("tradeDay").value));
$("prev").addEventListener("click",()=>{index=Math.max(0,index-1);render()});
$("next").addEventListener("click",()=>{index=Math.min(rounds.length-1,index+1);render()});
$("timeline").addEventListener("input",()=>{index=Math.min(rounds.length-1,Math.max(0,Number($("timeline").value)||0));render()});
$("reload").addEventListener("click",init);
init();
})();
