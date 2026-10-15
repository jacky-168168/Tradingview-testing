/* Homepage market sentiment presentation only. Never modifies Risk Score, strategy gates or official data. */
(function(scope){
"use strict";
const BANDS=[{min:0,max:25,label:"極高風險",color:"#fce5e5",ink:"#9f252c"},{min:25,max:45,label:"風險偏高",color:"#fed8c9",ink:"#ba3b31"},{min:45,max:60,label:"中性觀望",color:"#e8ebf0",ink:"#475569"},{min:60,max:75,label:"偏多觀察",color:"#e4f2ed",ink:"#216d60"},{min:75,max:100,label:"強勢偏多",color:"#d4ebe3",ink:"#166354"}];
const $=id=>typeof document!=="undefined"?document.getElementById(id):null;
function band(score){if(score==null||score===""||!Number.isFinite(Number(score))||Number(score)<0||Number(score)>100)return null;return BANDS.find((b,i)=>Number(score)<b.max||i===BANDS.length-1)||null}
function dateOffset(date,days){if(!/^\d{4}-\d{2}-\d{2}$/.test(String(date)))return "";const d=new Date(date+"T12:00:00Z");if(!Number.isFinite(d.getTime()))return "";d.setUTCDate(d.getUTCDate()-days);return d.toISOString().slice(0,10)}
function normalizeHistory(rows){if(!Array.isArray(rows))return [];const seen=new Set();return rows.filter(x=>x&&/^\d{4}-\d{2}-\d{2}$/.test(String(x.date))&&band(x.riskScore)).sort((a,b)=>String(b.date).localeCompare(String(a.date))).filter(x=>{if(seen.has(x.date))return false;seen.add(x.date);return true}).map(x=>({date:x.date,score:Number(x.riskScore)}))}
function snapshotAtOrBefore(history,deadline,exclusive=false){return (history||[]).find(x=>exclusive?x.date<deadline:x.date<=deadline)||null}
function comparisons(history,officialDate){if(!/^\d{4}-\d{2}-\d{2}$/.test(String(officialDate)))return [];return [{title:"前一交易日",target:officialDate,exclusive:true},{title:"一週前",target:dateOffset(officialDate,7)},{title:"3天前",target:dateOffset(officialDate,3)},{title:"5天前",target:dateOffset(officialDate,5)}].map(spec=>({...spec,record:snapshotAtOrBefore(history,spec.target,!!spec.exclusive)}))}
function polar(score,r=206,cx=300,cy=286){let t=Math.PI*(1-score/100);return {x:cx+r*Math.cos(t),y:cy-r*Math.sin(t)}}
function numberText(score){return score==null||!Number.isFinite(Number(score))?"—":String(Math.round(Number(score)))}
function gaugeSVG(score){
const valid=band(score),n=valid?Math.max(0,Math.min(100,Number(score))):null;
const seg=BANDS.map((b,i)=>{const from=b.min+(i?0.55:0),to=b.max-(i<4?0.55:0),a=polar(from),z=polar(to);return '<path d="M '+a.x.toFixed(2)+' '+a.y.toFixed(2)+' A 206 206 0 0 1 '+z.x.toFixed(2)+' '+z.y.toFixed(2)+'" fill="none" stroke="'+b.color+'" stroke-width="79"/>'}).join("");
const ticks=Array.from({length:21},(_,i)=>{const k=i*5,a=polar(k,146),b=polar(k,k%25===0?135:140);return '<line x1="'+a.x.toFixed(2)+'" y1="'+a.y.toFixed(2)+'" x2="'+b.x.toFixed(2)+'" y2="'+b.y.toFixed(2)+'" stroke="#96a3b8" stroke-width="'+(k%25===0?2.6:1.9)+'"/>'}).join("");
const majors=[0,25,45,60,75,100].map(k=>{const a=polar(k,117);return '<text x="'+a.x.toFixed(2)+'" y="'+(a.y+5).toFixed(2)+'" text-anchor="middle" font-size="16" fill="#64748b">'+k+'</text>'}).join("");
const titles=BANDS.map((b,i)=>{const a=polar((b.min+b.max)/2,210);let chunks=b.label.length>2?[b.label.slice(0,2),b.label.slice(2)]:[b.label];return '<text x="'+a.x.toFixed(2)+'" y="'+(a.y-((chunks.length-1)*8)).toFixed(2)+'" font-size="'+(i===0||i===4?14:15)+'" text-anchor="middle" fill="'+b.ink+'" font-weight="800">'+chunks.map((w,j)=>'<tspan x="'+a.x.toFixed(2)+'" dy="'+(j?19:0)+'">'+w+'</tspan>').join("")+'</text>'}).join("");
let needle="";
if(valid){const tip=polar(n,161),left=polar(n-1.1,0),right=polar(n+1.1,0);needle='<line x1="300" y1="286" x2="'+tip.x.toFixed(2)+'" y2="'+tip.y.toFixed(2)+'" stroke="#202936" stroke-width="8" stroke-linecap="round"/><circle cx="300" cy="286" r="8" fill="#202936"/>'}
return '<svg class="sentiment-dial" viewBox="0 0 600 332" role="img" aria-label="'+(valid?"大盤風險分數 "+numberText(n)+"，"+valid.label:"大盤分數尚未取得")+'">'+seg+ticks+majors+titles+needle+'<circle cx="300" cy="286" r="57" fill="white" stroke="#edf1f5"/><text x="300" y="290" text-anchor="middle" font-size="47" font-weight="900" fill="#172033">'+numberText(n)+'</text><text x="300" y="316" text-anchor="middle" font-size="12" font-weight="700" fill="#64748b">大盤風險分數</text></svg>';
}
/* Research-only drawdown guard. Ex-ante conditions, no future candles/portfolio results. */
function reboundReview(risk,previous){
 const raw=risk?.score,score=raw==null?NaN:Number(raw);
 if(!Number.isFinite(score)||score<0||score>100)return {valid:false,status:"unavailable",adjusted:null,penalty:0,message:"原始 Risk Score 尚未取得"};
 if(!previous||!previous.date||!risk?.date||String(previous.date)>=String(risk.date))return {valid:false,status:"pending",adjusted:null,penalty:0,message:"前一交易日資料待確認，暫不推論反彈風險"};
 if([previous.dayRet,risk.dayRet,risk.ret5,risk.foreign].some(x=>x===null||x===undefined||x===""))return {valid:false,status:"pending",adjusted:null,penalty:0,message:"前日或當日風控欄位不完整，無法驗證反彈"};
 const previousDrop=Number(previous.dayRet),today=Number(risk.dayRet),five=Number(risk.ret5),foreign=Number(risk.foreign);
 if(![previousDrop,today,five,foreign].every(Number.isFinite))return {valid:false,status:"pending",adjusted:null,penalty:0,message:"前一交易日跌幅或當日資料不完整"};
 const shock=previousDrop<=-1.5,tentative=shock&&today>0&&today<Math.abs(previousDrop)&&five<0;
 if(!tentative)return {valid:true,status:"clear",adjusted:score,penalty:0,message:"未觸發大跌後弱勢反彈條件"};
 const penalty=foreign<0?15:10,adjusted=Math.max(0,score-penalty);
 return {valid:true,status:"rebound",adjusted,penalty,message:"前日跌 "+Math.abs(previousDrop).toFixed(2)+"%，今日僅反彈 "+today.toFixed(2)+"%；近5日仍跌 "+Math.abs(five).toFixed(2)+"%"+(foreign<0?"、外資持續賣超":"")+"。目前屬反彈待確認；校正值僅供研究參考，非正式交易門檻。"};
}
function specialPattern(risk){
 if(!risk||!risk.date)return {name:"型態待確認",detail:"尚無已完成交易日型態資料",tone:"neutral"};
 const top=String(risk.topState||""),bottom=String(risk.bottomState||""),mode=String(risk.mode||"");
 if(top.includes("Strong Top Reversal"))return {name:"頂部反轉確認",detail:"出現強頂部警訊，應優先管控曝險",tone:"stop"};
 if(top.includes("Top Reversal Attempt"))return {name:"頂部反轉嘗試",detail:"頂部警訊尚需後續確認",tone:"caution"};
 if(bottom.includes("Strong Bottom Reversal"))return {name:"底部反轉確認",detail:"僅代表強底部型態成立，仍須遵守個股停損與倉位控管",tone:"reversal"};
 if(bottom.includes("Bottom Reversal Attempt"))return {name:"底部反轉嘗試",detail:"出現初步止跌跡象，並非已確認大盤轉多",tone:"caution"};
 if(mode==="BOTTOM"||/Oversold|Extreme Oversold|Bottom Watch/.test(bottom))return {name:"超跌觀察｜反轉未確認",detail:"超跌強度 "+String(risk.oversoldScore??"—")+" 分／底部確認 "+String(risk.bottomConfirmScore??"—")+" 分，超跌不等於買進",tone:"stop"};
 if(mode==="TOP"||/Overbought|Top Watch/.test(top))return {name:"高檔轉折觀察",detail:"留意追高與頂部訊號，尚未確認反轉",tone:"caution"};
 return {name:"一般趨勢觀察",detail:"目前沒有已確認的極端 Bottom／Top 反轉訊號",tone:"neutral"};
}
const previousCache=new Map();
let history=[],last=null,mode="overview",historyLoaded=false,pending=null,previousRequest=null;
function currentPrevious(date){return history.find(x=>x.date<date)||null}
function updateReview(){
 if(!last)return;
 const risk=last.risk||{},date=String(last.officialDate||""),prev=currentPrevious(date),prior=prev?previousCache.get(prev.date)||null:null;
 const result=reboundReview(risk,prior),pattern=specialPattern(risk);
 const comparison=$("sentimentRiskReview"),summary=$("sentimentAdjusted"),reason=$("sentimentAdjustedReason"),patternName=$("sentimentPattern"),patternReason=$("sentimentPatternReason");
 if(comparison){comparison.dataset.status=result.status;comparison.dataset.verified=String(result.valid)}
 if(summary)summary.textContent=result.adjusted==null?"待確認":String(Math.round(result.adjusted))+" /100";
 if(reason)reason.textContent=result.message;
 if(patternName)patternName.textContent=pattern.name;
 if(patternReason)patternReason.textContent=pattern.detail;
 const label=$("sentimentReviewStatus");if(label)label.textContent=result.status==="rebound"?"⚠ 反彈待確認":result.status==="clear"?"已核對：無反彈警示":"風險校正待確認";
 const note=$("sentimentReviewNote");if(note)note.textContent=result.status==="rebound"?"原始 "+risk.score+" 分，僅示範下修 "+result.penalty+" 分作風險提示；G／F／F2 正式交易規則不變。":"與原始分數分開呈現；本研究規則尚缺少足夠樣本，不代表預測勝率。";
 const guide=$("commandReboundWarning");
 if(guide){guide.hidden=result.status!=="rebound";if(!guide.hidden)guide.textContent="⚠ 大跌後反彈尚未確認：原始 Risk Score "+risk.score+" 分、校正參考 "+result.adjusted+" 分。請勿只因原始高分就積極追價；"+result.message}
}
async function loadPrevious(){
 if(!last||!historyLoaded)return;
 const date=String(last.officialDate||""),prev=currentPrevious(date);
 if(!prev){updateReview();return}
 if(previousCache.has(prev.date)){updateReview();return}
 if(previousRequest===prev.date)return;
 previousRequest=prev.date;
 try{
   const res=await fetch("./data/daily/"+encodeURIComponent(prev.date)+".json?v="+Date.now(),{cache:"no-store"});
   if(!res.ok)throw Error("previous day "+res.status);
   const data=await res.json(),r=data?.risk;
   if(data?.dataDate===prev.date&&r?.date===prev.date&&Number(r?.score)===prev.score)previousCache.set(prev.date,r);
 }catch(_){/* Missing historical risk must stay unknown, never quietly pass the guard. */}
 finally{previousRequest=null;if(last?.officialDate===date){updateReview()} }
}

function renderRows(){
const box=$("sentimentHistory");if(!box)return;
const records=last?comparisons(history,last.officialDate):[];
const list=mode==="overview"?records:(last?history.filter(x=>x.date<=last.officialDate).slice(0,10).map(x=>({title:x.date,record:x})):[]);
box.replaceChildren();
if(!list.length){const msg=document.createElement("p");msg.className="sentiment-empty";msg.textContent=historyLoaded?"尚無相符的歷史交易日資料":"歷史分數載入中…";box.appendChild(msg);return}
for(const item of list){const row=document.createElement("div");row.className="sentiment-history-row";const info=document.createElement("div"),label=document.createElement("span"),state=document.createElement("strong"),date=document.createElement("small"),score=document.createElement("b"),value=item.record;
label.textContent=item.title;label.className="sentiment-history-title";state.textContent=value?(band(value.score)?.label||"未知"):"資料不足";date.textContent=value?value.date:"無相符歷史交易日";score.textContent=value?numberText(value.score):"—";score.className="sentiment-history-score "+(value?("zone-"+BANDS.indexOf(band(value.score))):"zone-missing");
info.append(label,state,date);row.append(info,score);box.appendChild(row);
}
}
function setMode(next){mode=next==="timeline"?"timeline":"overview";for(const b of document.querySelectorAll("[data-sentiment-tab]")){let active=b.dataset.sentimentTab===mode;b.classList.toggle("active",active);b.setAttribute("aria-selected",active?"true":"false")}renderRows()}
function render(snapshot){last=snapshot;const panel=$("sentimentPanel");if(!panel)return;
const officialValid=band(snapshot?.officialScore),reference=!!snapshot?.reference,chosen=band(snapshot?.currentScore)?Number(snapshot.currentScore):officialValid?Number(snapshot.officialScore):null,selectedBand=band(chosen),sourceDate=String(snapshot?.officialDate||"");
panel.dataset.zone=selectedBand?String(BANDS.indexOf(selectedBand)):"unknown";
const dial=$("sentimentGauge");if(dial)dial.innerHTML=gaugeSVG(chosen);
const name=$("sentimentCurrentState");if(name)name.textContent=selectedBand?selectedBand.label:"資料待更新";
const source=$("sentimentScoreSource");if(source)source.textContent=reference?"盤前／夜盤參考基準（非正式，未獨立回測）":snapshot?.stale||snapshot?.post?"最近正式收盤分數（非今日即時）":"最近正式收盤風險分數";
updateReview();void loadPrevious();
const dat=$("sentimentAsOf");if(dat)dat.textContent=sourceDate?"正式資料日："+sourceDate:"正式資料日期未確認";
const note=$("sentimentExplanation");if(note)note.textContent="這是網站原有 Risk Score 的風險情緒視覺化，並非獨立的恐懼與貪婪指數；新倉判斷請以『操作解讀』及風控警訊為準。";
const updated=$("sentimentUpdated");if(updated)updated.textContent=snapshot?.updated?"最新資料產生："+String(snapshot.updated).replace("T"," "):"等待最近有效交易日資料";
renderRows();
}
async function loadHistory(){if(pending)return pending;pending=(async()=>{try{const res=await fetch("./data/daily/index.json?v="+Date.now(),{cache:"no-store"});if(!res.ok)throw Error("history "+res.status);history=normalizeHistory(await res.json())}catch(_){history=[]}finally{historyLoaded=true;pending=null;renderRows();updateReview();void loadPrevious()}})();return pending}
function mount(){if(!$("sentimentPanel"))return;for(const b of document.querySelectorAll("[data-sentiment-tab]"))b.addEventListener("click",()=>setMode(b.dataset.sentimentTab));setMode("overview");void loadHistory()}
scope.MarketSentiment={band,normalizeHistory,comparisons,snapshotAtOrBefore,render,loadHistory,mount,gaugeSVG,reboundReview,specialPattern};
if(typeof module!=="undefined"&&module.exports)module.exports={band,normalizeHistory,comparisons,snapshotAtOrBefore,gaugeSVG,dateOffset,reboundReview,specialPattern};
})(typeof window!=="undefined"?window:globalThis);
