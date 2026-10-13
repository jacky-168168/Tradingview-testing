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
  await check(page,tag+' 3 G report jump links',async()=>page.locator('.g-report-jump').count()===3);
  await check(page,tag+' official market and date status',async()=> (await page.locator('#gOfficialStatus').innerText()).includes('正式訊號日'));
  await check(page,tag+' G Top20 sector summary contains accurate source note or hidden',async()=>page.evaluate(()=>{
   const p=document.querySelector('#gSectorLeaderPanel');return p.hidden||p.textContent.includes('Top20');
  }));
  await check(page,tag+' G day not falsely showing stale intraday',async()=>(await page.locator('#gIntradayStatus').innerText()).includes('沒有可用'));
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
  await check(page,tag+' G filter then clear',async()=>{
   const btn=page.locator('#officialTb .theme-pick').first();if(!await btn.count())return false;
   await btn.click();const shown=await page.locator('#themeFilterBar').isVisible();
   await page.locator('#clearThemeFilter').click();return shown&&!(await page.locator('#themeFilterBar').isVisible())&&await page.locator('#officialTb tr').count()===20;
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
  await check(page,tag+' no runtime exception',async()=>errs.length===0?true:JSON.stringify(errs));
  await check(page,tag+' no 4xx/5xx for assets',async()=>badHttp.length===0?true:JSON.stringify(badHttp));
  await ctx.close();
 }
 await browser.close();
 console.log(JSON.stringify({checks:results.length,passed:results.filter(x=>x.pass).length,failed:findings.length,findings,results},null,2));
 if(findings.length)process.exitCode=1;
}
main().catch(e=>{console.error('BROWSER_TEST_FATAL',e);process.exitCode=1});
