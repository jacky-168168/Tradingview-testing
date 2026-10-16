/* End-to-end audit of stock selections against actual GitHub Pages build. */
const {chromium}=require('playwright'),assert=require('node:assert/strict');
const BASE='http://127.0.0.1:8765/selections.html';
const findings=[],results=[];
const record=(name,good,details)=>{results.push({name,pass:!!good,details:details||''});if(!good)findings.push({name,details:details||''})};
async function check(page,name,fn){try{const d=await fn();record(name,!!d,(d&&typeof d==='object')?JSON.stringify(d):String(d))}catch(e){record(name,false,e.stack?.slice(0,500)||String(e))}}
async function main(){
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 for(const viewport of [{width:1280,height:820},{width:390,height:844}]){
  const ctx=await browser.newContext({viewport,locale:'zh-TW',timezoneId:'Asia/Taipei'});
  await ctx.addInitScript(()=>localStorage.setItem('tw-stock-access-valid-until-v1',String(Date.now()+3600000)));
  const page=await ctx.newPage(),errs=[],badHttp=[];
  page.on('pageerror',e=>errs.push(e.message));
  page.on('response',r=>{if(r.status()>=400&&r.url().includes(':8765'))badHttp.push({url:r.url().split(':8765')[1],status:r.status()})});
  await page.goto(BASE,{waitUntil:'domcontentloaded',timeout:30000});
  await page.waitForFunction(()=>window.DATA&&window.DATA.models&&window.DATA.models.G,{timeout:25000});
  await page.waitForTimeout(500);
  const tag=viewport.width===390?'mobile':'desktop';
  await check(page,tag+' G default + source date',async()=>page.evaluate(()=>{
   const x=document.getElementById('officialTb').querySelectorAll('tr').length;
   return MODEL==='G'&&DATA.gSelection.dataDate===DATA.dataDate&&x===DATA.models.G.length&&x<=20;
  }));
  await check(page,tag+' 3 G report jump links',async()=>(await page.locator('.g-report-jump').count())===3);
  await check(page,tag+' compact G selection has no persistent instructional paragraphs',async()=>page.evaluate(()=>{
    const text=document.body.innerText,hidden=id=>getComputedStyle(document.getElementById(id)).display==='none';
    return hidden('tableHint')&&hidden('gNote')&&hidden('meta')&&
      !text.includes('箭頭只顯示實際成功存檔的輪次')&&
      !text.includes('G 簡單模式：近10日入榜')&&
      !text.includes('頁面每90秒同步；查看歷史');
  }));
  await check(page,tag+' compact G report jump buttons remain accessible',async()=>page.evaluate(()=>{
    const links=[...document.querySelectorAll('.g-report-jump')];
    if(links.length!==3||links.some(l=>l.getBoundingClientRect().width<65))return false;
    return innerWidth>650||links.every(l=>Math.abs(l.getBoundingClientRect().top-links[0].getBoundingClientRect().top)<3);
  }));
  await check(page,tag+' official market and date status',async()=> (await page.locator('#gOfficialStatus').innerText()).includes('正式訊號日'));
  await check(page,tag+' G Top20 sector summary contains accurate source note or hidden',async()=>page.evaluate(()=>{
   const p=document.querySelector('#gSectorLeaderPanel');return p.hidden||p.textContent.includes('Top20');
  }));
  await check(page,tag+' G intraday always labels old snapshots as historical or stale',async()=>page.evaluate(()=>{
   const t=document.getElementById('gIntradayStatus').textContent;
   return t.includes('沒有可用')||t.includes('歷史盤中快照')||t.includes('超過110分鐘')||t.includes('今日盤中已結束')||t.includes('盤中資料日 '+taipeiDate());
  }));
  await check(page,tag+' G timeline loaded with a real published timestamp',async()=>page.evaluate(()=>{
   return !!window.GIntradayTimeline&&document.getElementById('gHistoryLabel').textContent.includes('輪')&&document.getElementById('gHistoryDate').options.length>0;
  }));
  await check(page,tag+' TradingView link valid',async()=>page.evaluate(()=>Array.from(document.querySelectorAll('#officialTb a.tv-link')).some(a=>a.href.startsWith('https://www.tradingview.com/chart/?symbol=T'))));
  await check(page,tag+' repeat summary date and reconstruction warning',async()=>{
   await page.waitForFunction(()=>window.REPEAT_DATA!==null,{timeout:15000});
   return (await page.locator('#repeatStatus').innerText()).includes('回推')&&(await page.locator('#repeatCoverage').innerText()).includes('2026');
  });
  await check(page,tag+' repeat expand toggle',async()=>{
   const before=await page.locator('#repeatRows tr').count(),btn=page.locator('#repeatExpand');
   if(!await btn.isVisible())return before<=15;
   await btn.click();const after=await page.locator('#repeatRows tr').count();await btn.click();return after>=before&&await page.locator('#repeatRows tr').count()===before;
  });
  await check(page,tag+' multi-value theme tokens are separated for filtering',async()=>page.evaluate(()=>{
    const t={theme:'電阻器、電感器',subIndustry:'被動元件'};
    const html=themeButton(t.theme);
    return stockHasTheme(t,'電感器')&&stockHasTheme(t,'被動元件')&&!stockHasTheme(t,'太陽能')&&html.includes('data-theme="電感器"')&&html.includes('data-theme="電阻器"');
  }));
  await check(page,tag+' no false stale signal wording for N',async()=>page.evaluate(()=>{
    const old=MODEL;MODEL='N';N_ARCHIVE={version:'v',signalTop3:{'2026-10-08':[]}};N_SUMMARY={version:'v',baseUniverse:1800,selected:null};
    renderNTable();const msg=document.getElementById('nStatus').textContent;
    MODEL=old;N_ARCHIVE=null;N_SUMMARY=null;renderTable();
    return msg.includes('N 歷史訊號日期落後')&&!msg.includes('資料晚於其他策略');
  }));
  await check(page,tag+' G filter then clear',async()=>{
   const btn=page.locator('#officialTb .theme-pick').first();if(!await btn.count())return false;
   await btn.click();const shown=await page.locator('#themeFilterBar').isVisible();
   await page.locator('#clearThemeFilter').click();return shown&&!(await page.locator('#themeFilterBar').isVisible())&&(await page.locator('#officialTb tr').count())===await page.evaluate(()=>DATA.models.G.length);
  });
  await check(page,tag+' layout simple/detail toggles',async()=>{
   const old=await page.locator('#modeBadge').innerText();
   await page.locator('#layoutToggle').click();
   const now=await page.locator('#modeBadge').innerText();
   await page.locator('#layoutToggle').click();
   return old!==now&&old===await page.locator('#modeBadge').innerText();
  });
  if(tag==='mobile'){
   await check(page,'mobile simple rows expanding without JS error',async()=>{
    const row=page.locator('#officialTb tr.simple-stock-row').first(),before=await row.getAttribute('aria-expanded');
    await row.click({position:{x:8,y:10}});return before==='false'&&await page.locator('#officialTb tr.simple-detail-row').count()===1;
   });
   await check(page,'mobile simple G table no horizontal scroll',async()=>page.evaluate(()=>({
    good:document.getElementById('stockTable').getBoundingClientRect().width<=innerWidth,
    w:document.getElementById('stockTable').getBoundingClientRect().width,screen:innerWidth
   })).then(x=>x.good));
   await check(page,'mobile entire page no unexpected overflow',async()=>page.evaluate(()=>({good:document.documentElement.scrollWidth<=innerWidth+8,width:document.documentElement.scrollWidth,screen:innerWidth})).then(x=>x.good));
  }
  for(const m of ['G Pro','A','D','F','F2','N','L','G']){
   await check(page,tag+' switch '+m,async()=>{
    await page.evaluate(m=>switchRanking(m),m);await page.waitForTimeout(m==='N'?1500:m==='L'?450:100);
    return page.evaluate(m=>MODEL===m&&document.getElementById('count').textContent.length>0,m);
   });
  }
  await check(page,tag+' CPO leadership banner 6/20 and source trace',async()=>page.evaluate(()=>{
    const real=DATA.models.G,codes=Array.from(gLeaderCpoCodes(G_LEADER_CATALOG||{}));
    if(codes.length<6)return false;
    DATA.models.G=real.map((x,i)=>i<6?{...x,code:codes[i],name:'CPO稽核'+i}:x);
    renderGThemeLeaders();const alert=document.getElementById('gSectorLeaderPanel').textContent;
    DATA.models.G=real;renderGThemeLeaders();
    return alert.includes('CPO｜盤後最強入榜類股')&&alert.includes('6/20')&&alert.includes('30%');
  }));
  await check(page,tag+' forged stale latest cannot pass intraday validity check',async()=>page.evaluate(()=>{
    const old=G_INTRADAY,oldCurrent=GIntradayTimeline.current,oldHist=GIntradayTimeline.historical;
    try{
      GIntradayTimeline.current=function(fallback){return fallback};
      GIntradayTimeline.historical=function(){return false};
      G_INTRADAY={quality:'intraday-provisional-allmarket',asOfDate:taipeiDate(),sourceCloseDate:DATA.dataDate,publishedAt:'2026-01-01T09:00:00+08:00',rows:[DATA.models.G[0]]};
      return currentLiveG()===null;
    }finally{G_INTRADAY=old;GIntradayTimeline.current=oldCurrent;GIntradayTimeline.historical=oldHist}
  }));
  await check(page,tag+' no runtime exception',async()=>errs.length===0?true:JSON.stringify(errs));
  await check(page,tag+' no 4xx/5xx for assets',async()=>badHttp.length===0?true:JSON.stringify(badHttp));
  await ctx.close();
 }
 await browser.close();
 console.log(JSON.stringify({checks:results.length,passed:results.filter(x=>x.pass).length,failed:findings.length,findings,results},null,2));
 if(findings.length)process.exitCode=1;
}
main().catch(e=>{console.error('BROWSER_TEST_FATAL',e);process.exitCode=1});
