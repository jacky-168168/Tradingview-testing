(function(){
"use strict";
const el=id=>document.getElementById(id);
const state={stocks:[],filtered:[],selected:null,watches:new Set(),watchOnly:false,visible:100,mode:"",date:""};
const esc=s=>String(s==null?"":s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const n=(v,d=1)=>v===null||v===undefined||v===""||!Number.isFinite(Number(v))?"—":Number(v).toLocaleString("zh-TW",{minimumFractionDigits:d,maximumFractionDigits:d});
const pct=v=>v==null||!Number.isFinite(Number(v))?"—":(Number(v)>0?"+":"")+n(v,1)+"%";
const tone=v=>v==null?"":Number(v)>=0?"positive":"negative";
const tv=s=>"https://www.tradingview.com/chart/?symbol="+encodeURIComponent((s.market==="上市"?"TWSE":"TPEX")+":"+s.code);
const safeCode=s=>/^[0-9]{4}$/.test(String(s||""));
function loadWatches(){try{const w=JSON.parse(localStorage.getItem("tw-stock-watch-v1")||"[]");state.watches=new Set(Array.isArray(w)?w.filter(safeCode):[])}catch(_){state.watches=new Set()}}
function saveWatches(){try{localStorage.setItem("tw-stock-watch-v1",JSON.stringify([...state.watches]))}catch(_){}}
function uniqueModels(data){const all=new Map();for(const [m,stocks] of Object.entries(data.models||{})){for(const s of (Array.isArray(stocks)?stocks:[])){if(!safeCode(s.code))continue;const old=all.get(s.code)||{...s,models:[],signals:[],momentumScore:null,lowVolP:null,industry:s.industry||"未分類"};if(!old.models.includes(m))old.models.push(m);all.set(s.code,old)}}return [...all.values()]}
function updateIndustries(){const options=[...new Set(state.stocks.map(x=>x.industry||"未分類"))].sort((a,b)=>a.localeCompare(b,"zh-Hant"));el("industry").innerHTML='<option value="">全部產業</option>'+options.map(x=>'<option value="'+esc(x)+'">'+esc(x)+'</option>').join("")}
function init(payload,mode){state.mode=mode;state.stocks=mode==="complete"?(payload.stocks||[]):uniqueModels(payload);
state.date=payload.dataDate||"—";updateIndustries();
el("dataDate").textContent=state.date;el("totalCount").textContent=n(state.stocks.length,0);el("positiveCount").textContent=n(state.stocks.filter(x=>Number(x.ret20)>0).length,0);
el("selectedCount").textContent=n(state.stocks.filter(x=>Array.isArray(x.models)&&x.models.length).length,0);
el("status").innerHTML=mode==="complete"?'✅ 自建全市場資料｜交易日 '+esc(state.date)+' ｜有效日K '+esc(String(state.stocks.length))+' / '+esc(String(payload.coverage&&payload.coverage.universe||"?"))+' 檔｜收盤後快照（非即時）':'⚠ 全市場診斷資料尚未發布，暫以最新選股模型入選股票示範；目前不能搜尋未入選股票，也不計算動能／低波動分位。完整資料需等待下一次成功的 full 更新。';
if(mode==="fallback")el("status").classList.add("warn");else el("status").classList.remove("warn");
const params=new URLSearchParams(location.search),code=params.get("code");const first=state.stocks.find(x=>x.code===code)||state.stocks[0]||null;state.selected=first&&first.code;filterAndRender();showDetail(first)}
function scoreSort(x){const key=el("sort").value;return key==="signals"?(x.signals||[]).length:Number(x[key])}
function filterAndRender(){const q=el("search").value.trim().toLowerCase(),model=el("model").value,ind=el("industry").value;
state.filtered=state.stocks.filter(x=>(!q||(x.code||"").includes(q)||(x.name||"").toLowerCase().includes(q))&&(!ind||x.industry===ind)&&(model==="all"||(model==="selected"?(x.models||[]).length:(x.models||[]).includes(model)))&&(!state.watchOnly||state.watches.has(x.code)));
state.filtered.sort((a,b)=>{const v=scoreSort(b),w=scoreSort(a);if(Number.isFinite(v)&&Number.isFinite(w)&&v!==w)return v-w;if(Number.isFinite(v))return -1;if(Number.isFinite(w))return 1;return String(a.code).localeCompare(String(b.code))});
renderRows()}
function renderRows(){const arr=state.filtered.slice(0,state.visible);
el("matchCount").textContent="符合 "+state.filtered.length+" 檔｜已顯示 "+arr.length+" 檔";
el("rows").innerHTML=arr.length?arr.map(x=>'<tr data-code="'+esc(x.code)+'" class="'+(state.selected===x.code?"selected":"")+'"><td><button class="btn watch" data-watch="'+esc(x.code)+'" aria-label="切換 '+esc(x.code)+' 觀察" aria-pressed="'+state.watches.has(x.code)+'">'+(state.watches.has(x.code)?"★":"☆")+'</button></td><td><b>'+esc(x.code)+'</b> '+esc(x.name)+'</td><td>'+esc(x.industry||"—")+'</td><td class="num">'+n(x.close,2)+'</td><td class="num '+tone(x.ret20)+'">'+pct(x.ret20)+'</td><td class="num '+tone(x.rs20)+'">'+pct(x.rs20)+'</td><td><b>'+n(x.momentumScore)+'</b></td><td>'+n(x.lowVolP)+'</td><td>'+esc(String((x.signals||[]).length))+'</td><td>'+esc((x.models||[]).join(" / ")||"—")+'</td></tr>').join(""):'<tr><td colspan="10" style="padding:40px;text-align:center">沒有符合條件的股票；可更改搜尋、產業或模型篩選。</td></tr>';
el("more").hidden=state.filtered.length<=state.visible}
function metric(label,value){return '<div class="metric"><label>'+esc(label)+'</label><strong>'+esc(String(value))+'</strong></div>'}
function showDetail(x){if(!x){el("detail").innerHTML='<h2>個股體檢</h2><div class="placeholder">沒有可顯示的股票資料。</div>';return}
state.selected=x.code;
const modelLabels=(x.models||[]).map(m=>'<span class="tag">'+esc(m)+'</span>').join("")||'<span class="tag muted">未入選現有模型</span>';
const signals=(x.signals||[]).map(v=>'<span class="tag">'+esc(v)+'</span>').join("")||'<span class="tag muted">目前未觸發設定的技術觀察條件</span>';
const date=esc(state.date), code=esc(x.code);
el("detail").innerHTML='<div class="sub">'+date+' 收盤資料｜'+esc(x.market||"")+' · '+esc(x.industry||"")+'</div>'+
'<div class="stock-name">'+code+' '+esc(x.name)+'</div><div class="tags">'+modelLabels+'</div>'+
'<div class="metrics">'+metric("收盤價",n(x.close,2)) +metric("20日漲幅",pct(x.ret20))+metric("60日漲幅",pct(x.ret60))+metric("RS20（對加權指數）",pct(x.rs20))+
metric("動能分位（0～100）",n(x.momentumScore))+metric("低波動分位",n(x.lowVolP))+metric("近20日年化波動率",pct(x.volatility20))+metric("相對量（20日基準）",n(x.rvol20,2))+
metric("距120日高點",pct(x.distanceHigh120))+metric("52週高點（完整252日才算）",n(x.high252,2))+metric("成交額（億元）",n(x.turnoverB,2))+metric("股本（億元）",n(x.capitalB,2))+
metric("外資當日買賣超（張）",n(x.foreignToday,1))+metric("投信當日買賣超（張）",n(x.trustToday,1))+'</div>'+
'<h2>技術觀察條件</h2><div class="tags">'+signals+'</div><div class="note">條件觸發數量不是歷史勝率，也不是買入或賣出指示。上櫃或來源缺失的法人數字顯示「—」，不作零買賣超處理。</div>'+
'<h2 style="margin-top:18px">財報與估值</h2><div class="placeholder">EPS、ROE、本益比歷史分位、股利與經驗勝率：尚未接入可追溯的完整財報／回測來源。此版不填假數值，後續可用公開資訊觀測站資料擴充。</div>'+
'<div class="actions" style="margin-top:16px"><a class="btn primary" target="_blank" rel="noopener noreferrer" href="'+esc(tv(x))+'">📈 TradingView</a><a class="btn" target="_blank" rel="noopener noreferrer" href="https://finlab.finance/stocks/'+encodeURIComponent(x.code)+'">🔗 FinLab 原站（外部）</a><button class="btn" id="detailWatch" type="button">'+(state.watches.has(x.code)?"★ 已加入觀察":"☆ 加入觀察")+'</button></div>';
el("detailWatch").onclick=()=>toggleWatch(x.code)}
function toggleWatch(code){if(state.watches.has(code))state.watches.delete(code);else state.watches.add(code);saveWatches();renderRows();const item=state.stocks.find(x=>x.code===code);if(item&&state.selected===code)showDetail(item)}
async function load(){el("status").textContent="載入自建市場資料中…";let payload=null;try{const r=await fetch("./data/stocks/latest.json?v="+Date.now(),{cache:"no-store"});if(!r.ok)throw new Error("diagnostics "+r.status);payload=await r.json();if(payload.schema!=="stock-diagnostics-v1"||!Array.isArray(payload.stocks))throw new Error("診斷資料格式異常");init(payload,"complete");return}catch(e){console.info("stock diagnostic fallback:",e.message)}
try{const r=await fetch("./data/latest.json?v="+Date.now(),{cache:"no-store"});if(!r.ok)throw new Error("latest "+r.status);init(await r.json(),"fallback")}catch(e){el("status").textContent="❌ 個股資料載入失敗："+e.message;el("status").classList.add("warn")}}
for(const id of ["search","sort","model","industry"])el(id).addEventListener(id==="search"?"input":"change",()=>{state.visible=100;filterAndRender()});
el("watchFilter").onclick=()=>{state.watchOnly=!state.watchOnly;el("watchFilter").classList.toggle("active",state.watchOnly);el("watchFilter").setAttribute("aria-pressed",String(state.watchOnly));state.visible=100;filterAndRender()};
el("rows").onclick=e=>{const watch=e.target.closest("button[data-watch]");if(watch){toggleWatch(watch.dataset.watch);return}const tr=e.target.closest("tr[data-code]");if(!tr)return;const x=state.stocks.find(x=>x.code===tr.dataset.code);if(x){showDetail(x);renderRows()}};
el("more").onclick=()=>{state.visible+=100;renderRows()};
el("reload").onclick=load;loadWatches();load();
})();