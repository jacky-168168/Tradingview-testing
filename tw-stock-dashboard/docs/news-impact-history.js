(function(){
"use strict";
const $=id=>document.getElementById(id);
const esc=v=>String(v==null?"":v).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const ASSETS=["美股S&P500","NASDAQ","台股","黃金","白銀","WTI原油","美元","美債殖利率","銅"];
const URL="./data/news_impact/official_study.json";
let study=null,page=0;
const detailCache={},detailPending={},detailErrors={};
const PAGE_SIZE=12;
const fmt=(v,digits=2)=>typeof v==="number"&&Number.isFinite(v)?(v>0?"+":"")+v.toFixed(digits)+"%":"—";
function cellClass(v){return typeof v!=="number"?"neutral":v>0?"pos":v<0?"neg":"neutral"}
function currentStats(group,asset,horizon){
 return study&&Array.isArray(study.stats)?study.stats.find(s=>s.group===group&&s.asset===asset&&s.horizon===horizon):null
}
function controls(){
 return {group:$("group").value,asset:$("asset").value,horizon:$("horizon").value};
}
function casesFor(group,asset){
 const category=group.startsWith("FOMC:")?"FOMC":group;
 if(!study.detailFiles)return study.events||[];
 const key=category+"|"+asset;
 if(Object.prototype.hasOwnProperty.call(detailCache,key))return detailCache[key];
 if(detailPending[key])return null;
 const path=study.detailFiles?.[category]?.[asset];
 if(!path){detailErrors[key]="此事件／資產的明細資料尚未發布";return []}
 detailPending[key]=true;
 fetch(path+"?v="+encodeURIComponent(study.generatedAt||""),{cache:"no-store"})
 .then(r=>{if(!r.ok)throw Error("HTTP "+r.status);return r.json()})
 .then(d=>{
  if(d.schema!==1||d.category!==category||d.asset!==asset||!Array.isArray(d.events))throw Error("明細資料格式不符");
  detailCache[key]=d.events;
 })
 .catch(e=>{detailErrors[key]=String(e.message||e);detailCache[key]=[]})
 .finally(()=>{delete detailPending[key];render()});
 return null;
}
function render(){
 if(!study)return;
 const {group,asset,horizon}=controls(),s=currentStats(group,asset,horizon);
 const count=s?s.n:0;
 $("eventN").textContent=count;
 $("sampleNote").textContent=count>=study.minSample?"描述性統計（仍非因果）":"樣本不足（至少 "+study.minSample+" 筆才顯示描述性統計）";
 for(const [id,key] of [["avg","meanPct"],["relative","vsUnconditionalPct"]]){
  const v=count>=study.minSample&&s?s[key]:null;
  $(id).textContent=fmt(v);
  $(id).className=cellClass(v);
 }
 $("positive").textContent=count>=study.minSample&&s&&typeof s.positivePct==="number"?s.positivePct.toFixed(1)+"%":"—";
 const other=ASSETS.map(a=>{
  const x=currentStats(group,a,horizon)||{n:0},sufficient=x.n>=study.minSample;
  const cls=cellClass(x.meanPct),pct=sufficient?x.positivePct:null;
  return '<tr><td><strong>'+esc(a)+'</strong></td><td>'+x.n+(sufficient?'':' <span class="tag">小樣本</span>')+'</td>'+
   '<td class="'+cls+'">'+(sufficient?fmt(x.meanPct):'—')+'</td>'+
   '<td class="'+cellClass(x.medianPct)+'">'+(sufficient?fmt(x.medianPct):'—')+'</td>'+
   '<td>'+((sufficient&&typeof pct==="number")?pct.toFixed(1)+"%":"—")+
   ((sufficient&&typeof pct==="number")?'<div class="bar"><div class="fill '+(pct<50?'down':'')+'" style="width:'+Math.min(100,Math.max(0,pct))+'%"></div></div>':'')+
   '</td><td class="'+cellClass(x.vsUnconditionalPct)+'">'+(sufficient?fmt(x.vsUnconditionalPct):'—')+'</td></tr>';
 });
 $("summaryTable").innerHTML=other.join("");
 const isSub=group.startsWith("FOMC:"),sublabel=group.split(":")[1];
 const allCases=casesFor(group,asset);
 if(allCases===null){
  $("status").textContent="正在載入此事件／資產的歷史明細…";
  $("caseTable").innerHTML='<tr><td colspan="8">正在取得逐筆價格資料…</td></tr>';
  $("pageLabel").textContent="資料載入中";
  $("previous").disabled=true;$("next").disabled=true;
  return;
 }
 const cases=allCases.filter(e=>isSub?(e.category==="FOMC"&&e.subtype===sublabel):e.category===group)
  .sort((a,b)=>String(b.date).localeCompare(String(a.date)));
 const pmax=Math.max(1,Math.ceil(cases.length/PAGE_SIZE));page=Math.min(page,pmax-1);
 const k=(isSub?"FOMC":group)+"|"+asset;
 $("status").textContent=detailErrors[k]?"⚠ 明細讀取失敗："+detailErrors[k]:"此類別歷史日期 "+cases.length+" 筆；此資產／期間已完成 "+count+" 筆價格樣本。未成熟期間保留「—」。";
 const slice=cases.slice(page*PAGE_SIZE,(page+1)*PAGE_SIZE);
 $("caseTable").innerHTML=slice.length?slice.map(e=>{
  const r=e.outcomes&&e.outcomes[asset],a=r?r.results:{};
  const href=/^https:\/\//.test(e.sourceUrl||"")?e.sourceUrl:"#";
  const small=e.calendarKind==="alfred_historical_vintage"||e.primaryReleaseVerified===false?"ALFRED資料更新／修訂":e.timeAccuracy==="inferred_regular_meeting"?"推導公告日":e.timeAccuracy==="date_only"||e.timeAccuracy==="date_only_release_link"?"日期代理":"公布日期";
  return '<tr><td>'+esc(e.date)+'<div class="tag">'+esc(small)+'</div></td>'+
   '<td class="case-source"><strong>'+esc(e.title)+'</strong><div><a href="'+esc(href)+'" target="_blank" rel="noopener noreferrer">'+esc(e.source)+'｜資料來源</a></div></td>'+
   '<td>'+esc(asset)+'</td><td>'+esc(r&&r.baselineDate||"—")+'</td><td>'+esc(r&&r.firstEligibleDate||"—")+'</td>'+
   '<td class="'+cellClass(a["1D"])+'">'+fmt(a["1D"])+'</td>'+
   '<td class="'+cellClass(a["5D"])+'">'+fmt(a["5D"])+'</td>'+
   '<td class="'+cellClass(a["20D"])+'">'+fmt(a["20D"])+'</td></tr>';
 }).join(""):'<tr><td colspan="8">這個組別暫無可驗證事件。</td></tr>';
 $("pageLabel").textContent="第 "+(page+1)+"／"+pmax+" 頁";
 $("previous").disabled=page<=0;$("next").disabled=page>=pmax-1;
}
async function boot(){
 try{
  const r=await fetch(URL+"?v="+Date.now(),{cache:"no-store"});
  if(!r.ok)throw Error("HTTP "+r.status);
  const d=await r.json();
  if(d.schema!==1||!Array.isArray(d.stats)||!Array.isArray(d.groups)||(!Array.isArray(d.events)&&!d.detailFiles))throw Error("研究資料格式無效");
  study=d;
  const select=$("group");
  const old=select.value;
  select.innerHTML=d.groups.map(g=>'<option value="'+esc(g.key)+'">'+esc(g.label)+'</option>').join("");
  if(d.groups.some(g=>g.key===old))select.value=old;
  const sourceErrors=Object.keys(d.catalogSourceErrors||{}).length;
  $("meta").textContent="研究快照："+(d.generatedAt||"未知")+"｜行情狀態："+(d.status||"未知")+"｜官方事件日期 "+(d.catalogCount||0)+" 筆｜有行情可驗證 "+(d.eventsWithPriceData??"待確認")+" 筆｜涵蓋："+(d.catalogEarliest||"—")+" ～ "+(d.catalogLatest||"—")+"｜行情資產 "+(d.priceSymbolsOk||[]).length+"/9"+(sourceErrors?"｜⚠ "+sourceErrors+" 個官方資料來源擷取異常":"")+(Object.keys(d.priceErrors||{}).length?"｜⚠ 部分行情缺失":"");
  if(d.generatedAt&&Date.now()-Date.parse(d.generatedAt)>48*3600000)$("meta").textContent+="｜⚠ 研究快照超過 48 小時";
  render();
 }catch(e){
  $("meta").textContent="⚠ 歷史統計尚未發布或讀取失敗："+e.message+"。可到 GitHub Actions 檢查 Global Market News Impact 工作流程。";
  $("summaryTable").innerHTML='<tr><td colspan="6">暫時沒有可信的研究結果，不以估計值代替。</td></tr>';
  $("caseTable").innerHTML='<tr><td colspan="8">待第一次官方事件回測工作流程成功執行。</td></tr>';
  $("status").textContent="歷史研究尚未就緒";
 }
}
for(const name of ["group","asset","horizon"]){$(name).addEventListener("change",()=>{page=0;render()})}
$("previous").addEventListener("click",()=>{if(page>0){page--;render()}});
$("next").addEventListener("click",()=>{page++;render()});
boot();
})();