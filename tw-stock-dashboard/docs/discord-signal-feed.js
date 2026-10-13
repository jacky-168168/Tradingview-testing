/* Discord Signal Feed: read-only browser client. Token is never written to localStorage or GitHub. */
(function(){
"use strict";
const $=id=>document.getElementById(id),esc=s=>String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[m]));
let latest=[],timer=null,connected=false,credentials=null;
function message(s){$("discordStatus").textContent=s}
function endpoint(raw){
 const u=new URL(String(raw||"").trim());
 if(u.protocol!=="https:"||u.username||u.password||u.search||u.hash||u.pathname!=="/")throw Error("請輸入 Cloudflare Worker 的 HTTPS 根網址，不含其他路徑或參數");
 return u.origin;
}
async function request(path){
 const r=await fetch(credentials.base+path,{method:"GET",headers:{Authorization:"Bearer "+credentials.token,Accept:"application/json"},cache:"no-store"});
 if(!r.ok)throw Error(r.status===401?"金鑰錯誤（401）":r.status===403?"Worker 未允許此網站 Origin（403）":"Worker HTTP "+r.status);
 return r.json();
}
function render(){
 const unique=new Map();
 for(const e of latest){
  const k=[e.channelId,e.symbol,e.signal,e.price,Math.floor(e.time/60000)].join("|");
  if(!unique.has(k))unique.set(k,{...e,variants:new Set([e.variant])});
  else unique.get(k).variants.add(e.variant);
 }
 const groups=[...unique.values()].sort((a,b)=>b.time-a.time),ready=groups.filter(e=>e.timeframe==="2");
 $("discordCount").textContent=groups.length+" 組／已核實 2 分鐘 "+ready.length+" 組";
 $("discordImport").disabled=!ready.length;
 $("discordRows").innerHTML=groups.length?groups.slice(0,100).map(e=>{
  const signal=e.variants.has("SS")&&e.variants.has("NORMAL")?"SS＋一般 "+e.signal:e.variants.has("SS")?"SS "+e.signal:e.signal;
  const d=new Date(e.time).toLocaleString("zh-TW",{timeZone:"Asia/Taipei",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false});
  const tf=e.timeframe==="2"?"2 分（已確認）":e.timeframe==="5"?"5 分":"週期未核實";
  return '<tr><td>'+esc(d)+'</td><td>'+esc(e.channel)+'</td><td><b>'+esc(e.symbol)+'</b></td><td class="'+(e.signal==="BOTTOM"?"green":"red")+'">'+esc(signal)+'</td><td class="num">'+esc(e.price)+'</td><td>'+esc(tf)+'</td><td class="orange">Trend 未提供</td></tr>';
 }).join(""):'<tr><td colspan="7">未收到任何可解析的訊號。可以先核對 Discord Bot 權限、頻道是否有新訊息，以及後端同步狀態。</td></tr>';
}
async function refresh(){
 if(!credentials)return;
 try{
  const [data,status]=await Promise.all([request("/api/events?limit=300"),request("/api/status")]);
  latest=Array.isArray(data.events)?data.events:[];
  const channels=(status.channels||[]).map(c=>c.name+"："+(c.lastError?"錯誤 "+c.lastError:c.lastChecked?"上次檢查 "+new Date(c.lastChecked).toLocaleTimeString("zh-TW",{timeZone:"Asia/Taipei",hour12:false}):"尚未執行同步"));
  message("已連接："+channels.join("｜")+"。此處每 60 秒更新畫面，並非秒級行情。");
  render();
 }catch(err){message("讀取失敗："+err.message)}
}
$("discordConnect").addEventListener("click",async()=>{
 try{
  const base=endpoint($("discordWorker").value),token=$("discordReadToken").value.trim();
  if(token.length<16)throw Error("請輸入 Worker 的 DASHBOARD_READ_TOKEN，至少 16 個字元");
  credentials={base,token};connected=true;
  try{localStorage.setItem("tw-discord-worker-base-v1",base)}catch(e){}
  $("discordReadToken").value="";
  if(timer)clearInterval(timer);
  await refresh();timer=setInterval(refresh,60000);
 }catch(err){message("連線設定錯誤："+err.message)}
});
$("discordRefresh").addEventListener("click",refresh);
$("discordDisconnect").addEventListener("click",()=>{
 credentials=null;latest=[];connected=false;if(timer)clearInterval(timer);timer=null;
 $("discordCount").textContent="尚未連線";render();message("已斷開本頁連線；讀取金鑰已從頁面執行記憶體清除。");
});
$("discordImport").addEventListener("click",()=>{
 const records=latest.filter(e=>e.timeframe==="2"&&["BOTTOM","TOP"].includes(e.signal));
 if(!records.length){message("沒有可核實為 2 分鐘的訊號；請先確認頻道警示週期並修改 Worker CHANNELS_CONFIG。");return}
 const unique=new Map();
 for(const e of records){
  const key=[e.time,e.symbol,e.signal,e.price].join("|");
  if(!unique.has(key))unique.set(key,{time:e.time,symbol:e.symbol,signal:e.signal,price:e.price,trend:e.trend??null,g:null,timeframe:"2"});
 }
 if(typeof CustomEvent==="undefined"){message("此瀏覽器不支援匯入事件");return}
 document.dispatchEvent(new CustomEvent("tw:discord-import",{detail:[...unique.values()]}));
 message("已提交 "+unique.size+" 筆 2 分鐘事件至紙上模擬。Discord 未提供 Trend，B/C 策略不會擅自放行。");
});
try{const stored=localStorage.getItem("tw-discord-worker-base-v1");if(stored)$("discordWorker").value=stored}catch(e){}
render();
})();
