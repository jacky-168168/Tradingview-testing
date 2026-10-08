/* Browser-only entry screen for the public GitHub Pages stock dashboard.
   IMPORTANT: A client-side password never secures publicly downloadable HTML,
   JS, JSON, or source code. For real access control migrate behind a server /
   identity-aware proxy, and move confidential data off public GitHub Pages. */
(function(){
"use strict";
const SITE_SALT="tw-stock-access-v1-2026-10";
const SITE_PASS_SHA256="fc1f46718a688c862a5be8fd7ad2427997141cea22e0f15bddefb92f2f6f3e88";
const ACCESS_KEY="tw-stock-access-valid-until-v1";
const ACCESS_TTL_MS=48*60*60*1000;
let attempts=0,lockUntil=0;
function readAccess(){try{const n=Number(localStorage.getItem(ACCESS_KEY));return Number.isFinite(n)&&n>Date.now()&&n<=Date.now()+ACCESS_TTL_MS}catch(_){return false}}
function saveAccess(){try{localStorage.setItem(ACCESS_KEY,String(Date.now()+ACCESS_TTL_MS))}catch(_){}}
function clearAccess(){try{localStorage.removeItem(ACCESS_KEY)}catch(_){}}
function hex(array){return [...new Uint8Array(array)].map(x=>x.toString(16).padStart(2,"0")).join("")}
async function verify(password){
 if(!window.crypto||!crypto.subtle)throw new Error("瀏覽器不支援安全雜湊，請使用 HTTPS 開啟網站。");
 const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(SITE_SALT+":"+password));
 return hex(digest)===SITE_PASS_SHA256;
}
const css=`
html[data-tw-access="locked"] body{overflow:hidden!important}
html[data-tw-access="locked"] body>*:not(#tw-access-gate){visibility:hidden!important}
#tw-access-gate{visibility:visible!important;position:fixed;inset:0;z-index:2147483647;display:grid;place-items:center;overflow:auto;padding:20px;background:radial-gradient(circle at 13% 17%,#e0ebfd 0,transparent 45%),linear-gradient(130deg,#f8fafc,#e7edf7);color:#15243d;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",Arial,sans-serif}
#tw-access-gate *{box-sizing:border-box}#tw-access-gate .tw-access-card{width:min(100%,420px);padding:32px;border:1px solid #dfe7f3;background:#fff;border-radius:20px;box-shadow:0 18px 60px rgba(30,58,97,.13)}
#tw-access-gate .tw-access-icon{width:52px;height:52px;display:grid;place-items:center;font-size:26px;background:#eaf1ff;color:#1d4ed8;border-radius:15px;margin-bottom:18px}
#tw-access-gate h2{margin:0 0 8px;font-size:24px;font-weight:850;letter-spacing:.2px;color:#15243d}
#tw-access-gate p{font-size:13px;color:#64748b;line-height:1.8;margin:0 0 24px}
#tw-access-gate label{display:block;font-size:12px;font-weight:750;margin:0 0 8px;color:#34415b}
#tw-access-gate .tw-access-input-wrap{display:flex;align-items:center;border:1px solid #cdd7e5;border-radius:11px;overflow:hidden;background:#fff}
#tw-access-gate input{min-width:0;width:100%;border:0;outline:none;background:transparent;padding:13px 14px;font-size:16px;color:#142238;font-family:inherit}
#tw-access-gate .tw-access-show{height:43px;flex:0 0 auto;border:0;background:transparent;color:#47617e;padding:0 12px;cursor:pointer;font-size:12px;font-weight:700}
#tw-access-gate .tw-access-input-wrap:focus-within{border-color:#2563eb;box-shadow:0 0 0 3px #2563eb20}
#tw-access-gate .tw-access-enter{display:block;width:100%;margin-top:15px;padding:13px;background:#2563eb;color:#fff;border:0;border-radius:11px;font-size:14px;font-family:inherit;font-weight:800;cursor:pointer}
#tw-access-gate .tw-access-enter:disabled{opacity:.6;cursor:wait}
#tw-access-gate .tw-access-message{font-size:12px;color:#be123c;min-height:21px;padding-top:7px}
#tw-access-gate .tw-access-bottom{border-top:1px solid #edf1f7;padding-top:15px;margin-top:9px;line-height:1.7;font-size:11px;color:#7c889a}
#tw-site-lock{position:fixed;right:14px;bottom:13px;z-index:2147483600;border:1px solid #d8e0eb;border-radius:999px;background:#fff;color:#43536a;padding:6px 12px;cursor:pointer;font-family:inherit;font-size:11px;box-shadow:0 1px 9px #0000001c}
#tw-site-lock:hover{background:#f0f5ff;color:#234d9c}
@media(max-width:540px){#tw-access-gate{padding:12px}#tw-access-gate .tw-access-card{padding:25px 20px}#tw-access-gate h2{font-size:22px}}
`;
const style=document.createElement("style");style.id="tw-access-style";style.textContent=css;document.head.appendChild(style);
const unlockedAtLoad=readAccess();
document.documentElement.setAttribute("data-tw-access",unlockedAtLoad?"unlocked":"locked");
function addLockButton(){
 if(document.getElementById("tw-site-lock"))return;
 const lock=document.createElement("button");lock.id="tw-site-lock";lock.type="button";lock.textContent="🔒 鎖定網站";lock.title="立即鎖定網站並清除這個瀏覽器的 48 小時進入記錄";
 lock.addEventListener("click",()=>{clearAccess();location.reload()});document.body.appendChild(lock);
}
function unlock(){
 saveAccess();document.documentElement.setAttribute("data-tw-access","unlocked");
 const el=document.getElementById("tw-access-gate");if(el)el.remove();addLockButton();
}
function buildGate(){
 if(unlockedAtLoad){addLockButton();return}
 const root=document.createElement("div");root.id="tw-access-gate";root.setAttribute("role","dialog");root.setAttribute("aria-modal","true");root.setAttribute("aria-labelledby","tw-access-title");
 root.innerHTML=`<section class="tw-access-card">
 <div class="tw-access-icon" aria-hidden="true">🔐</div>
 <h2 id="tw-access-title">台股量化選股系統</h2>
 <p>此網站已設定進入密碼。請輸入通行碼後繼續瀏覽選股、回測與強勢股研究頁面。</p>
 <form id="tw-access-form" autocomplete="off">
  <label for="tw-access-password">網站通行碼</label>
  <div class="tw-access-input-wrap"><input id="tw-access-password" type="password" placeholder="請輸入密碼" autocomplete="current-password" required autofocus><button class="tw-access-show" id="tw-access-show" type="button" aria-label="顯示密碼">顯示</button></div>
  <div id="tw-access-message" class="tw-access-message" aria-live="polite"></div>
  <button class="tw-access-enter" id="tw-access-enter" type="submit">進入網站</button>
 </form>
 <div class="tw-access-bottom">同一瀏覽器驗證後保留 48 小時，可使用右下角「鎖定網站」提前登出。<br>此為前端入口限制，公開的 GitHub Pages 檔案仍可經由網址直接取得。</div>
 </section>`;
 document.body.appendChild(root);
 const form=root.querySelector("#tw-access-form"),input=root.querySelector("#tw-access-password"),message=root.querySelector("#tw-access-message"),button=root.querySelector("#tw-access-enter"),show=root.querySelector("#tw-access-show");
 show.addEventListener("click",()=>{const visible=input.type==="password";input.type=visible?"text":"password";show.textContent=visible?"隱藏":"顯示";show.setAttribute("aria-label",visible?"隱藏密碼":"顯示密碼");input.focus()});
 form.addEventListener("submit",async(e)=>{
  e.preventDefault();
  if(Date.now()<lockUntil){message.textContent="嘗試次數過多，請稍後重試。";return}
  const value=input.value;
  button.disabled=true;button.textContent="正在驗證…";message.textContent="";
  try{
   if(await verify(value)){attempts=0;input.value="";unlock();return}
   attempts++;input.value="";
   if(attempts>=5){lockUntil=Date.now()+30*1000;attempts=0;message.textContent="密碼不正確，請 30 秒後重試。"}
   else message.textContent="密碼不正確，請重新輸入。";
  }catch(err){message.textContent=err?.message||"驗證暫時無法使用。"}
  finally{button.disabled=false;button.textContent="進入網站";if(document.documentElement.getAttribute("data-tw-access")==="locked")input.focus()}
 });
 input.focus();
}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",buildGate,{once:true});else buildGate();
})();
