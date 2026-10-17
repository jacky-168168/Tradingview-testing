/* Whole-site smoke + interaction + source audit. Executed against the checked-out
   static Pages tree, with real Chromium at desktop and Android-like viewports. */
const {chromium}=require('playwright'),fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
const ROOT=path.resolve(__dirname,'../docs'),BASE='http://127.0.0.1:8765/';
const CORE=['index.html','selections.html','bubbles.html','stocks.html','upstream.html','history.html','backtest.html'];
const EXT=['market-methodology.html','market-ml-stocks.html','market-cash-3y.html','n-canslim.html','txf-backtest.html','etf-allocation.html','g-backtest.html','g-persistence.html','g-pro-3y.html','g-regime-3y.html','g-regime-contrarian-3y.html','g-target.html','g-candles.html','g-compound-3y.html','g-compound-v2-3y.html','g-compound-v3-walkforward.html'];
const ALL=[...CORE,...EXT],checks=[],problems=[],warnings=[];
const log=(name,ok,details)=>{const rec={name,pass:!!ok,...(details?{details}:{} )};checks.push(rec);if(!ok)problems.push(rec)};
async function test(name,fn){try{let ret=await fn();log(name,ret===true||ret?.ok===true,typeof ret==='object'?JSON.stringify(ret).slice(0,900):String(ret))}catch(e){log(name,false,e.message.slice(0,600))}}
function assetsAudit(){
 for(const file of ALL){
  const s=fs.readFileSync(path.join(ROOT,file),'utf8');
  test('static '+file+' local links exist',()=>{let invalid=[];for(const m of s.matchAll(/(?:src|href)="((?:\.\/|data\/)[^"]+)"/g)){
   const rel=m[1].split(/[?#]/)[0];if(!rel||rel==='./')continue;
   const p=path.resolve(ROOT,rel);if(!p.startsWith(ROOT)||!fs.existsSync(p))invalid.push(rel);
  }return invalid.length?{ok:false,invalid}:true});
 }
}
async function context(browser,w,h){const ctx=await browser.newContext({viewport:{width:w,height:h},timezoneId:'Asia/Taipei',locale:'zh-TW',serviceWorkers:'block'});await ctx.addInitScript(()=>{try{localStorage.setItem('tw-stock-access-valid-until-v1',String(Date.now()+3600000))}catch(_){}});return ctx}
async function visit(ctx,file,variant,delay=600){
 const page=await ctx.newPage(),jsErrors=[],httpErrors=[];
 page.on('pageerror',e=>jsErrors.push(e.message));
 page.on('response',r=>{if(r.status()>=400&&r.url().startsWith(BASE))httpErrors.push({url:r.url().split('?')[0].slice(BASE.length),code:r.status()})});
 await page.goto(BASE+file,{waitUntil:'domcontentloaded',timeout:28000});await page.waitForTimeout(delay);
 await test(variant+' '+file+' HTTP success',async()=>(await page.locator('body').count())===1&&!(await page.locator('body').innerText()).includes('404 File not found'));
 await test(variant+' '+file+' no JS exception',async()=>jsErrors.length?{ok:false,jsErrors}:true);
 await test(variant+' '+file+' no local asset 4xx',async()=>httpErrors.length?{ok:false,httpErrors}:true);
 if(variant==='mobile')await test('mobile '+file+' no body overflow',async()=>page.evaluate(()=>{
 const width=window.innerWidth,scroll=document.documentElement.scrollWidth;
 const offenders=[...document.querySelectorAll('body *')].filter(el=>{const r=el.getBoundingClientRect();return r.right>width+12&&r.width>0}).sort((a,b)=>b.getBoundingClientRect().right-a.getBoundingClientRect().right).slice(0,12).map(el=>({tag:el.tagName,id:el.id,cls:String(el.className?.baseVal||el.className||'').slice(0,85),x:Math.round(el.getBoundingClientRect().x),r:Math.round(el.getBoundingClientRect().right),width:Math.round(el.getBoundingClientRect().width)}));
 return {ok:scroll<=width+12,scroll,width,offenders};
}));
 return {page,jsErrors,httpErrors};
}
async function main(){
 assetsAudit();
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 for(const [variant,w,h] of [['desktop',1366,768],['mobile',390,844]]){
  const ctx=await context(browser,w,h);
  for(const file of ALL){const {page,jsErrors}=await visit(ctx,file,variant,file==='stocks.html'?1800:file==='bubbles.html'?1100:600);
   if(file==='index.html'){
    await test(variant+' home data loaded',()=>page.evaluate(()=>!!window.DATA?.dataDate&&Number.isFinite(Number(DATA.risk?.score))&&document.getElementById('marketMeta').textContent.includes(DATA.dataDate)));
    await test(variant+' home risk & timing',()=>page.evaluate(()=>Number(document.getElementById('riskScore').textContent)===Number(DATA.risk.score)&&!!document.getElementById('commandStatus').textContent));
    await test(variant+' DIX GEX chart renders real 3-series historical lines',async()=>{
      await page.waitForFunction(()=>{
        const wrap=document.getElementById('usopChartWrap'),svg=document.getElementById('usopChart');
        return wrap?.classList.contains('usop-error')||svg?.querySelectorAll('path[data-path-series]').length===3;
      },{timeout:18000}).catch(()=>{});
      const status=await page.evaluate(()=>{
        const w=document.getElementById('usopChartWrap'),svg=document.getElementById('usopChart');
        return {bad:w?.classList.contains('usop-error'),paths:svg?.querySelectorAll('path[data-path-series]').length||0,
          date:document.getElementById('usopDate')?.textContent,message:document.getElementById('usopMessage')?.textContent,
          main:document.getElementById('usopValuegex')?.textContent};
      });
      return status.paths===3&&!status.bad&&status.date.includes('2026/')&&status.main!=='—'?true:{ok:false,status};
    });

    await test(variant+' DIX six-month 7-step daily report renders with full evidence',()=>page.evaluate(()=>{
      const card=document.getElementById('usopDailyAnalysis'),title=document.getElementById('usopDailyTitle'),
        table=document.querySelector('#usopDailyBody table'),
        rows=table?[...table.querySelectorAll('tbody tr')]:[],
        headers=[...document.querySelectorAll('#usopDailyBody h4')].map(x=>x.textContent),
        lists=[...document.querySelectorAll('#usopDailyBody ul')],
        status=document.querySelector('#usopDailyBody .usop-report-status'),
        resonance=document.querySelector('#usopDailyBody .usop-report-resonance'),
        meta=document.getElementById('usopDailyMeta');
      return !!card&&card.dataset.state==="ready"&&title.textContent.includes("美股資金結構日報")&&
        !!status&&/🟢|🟡|🟠|🔴|⚪/.test(status.textContent)&&
        rows.length===3&&rows[0].textContent.includes("DIX")&&rows[1].textContent.includes("S&P 500")&&rows[2].textContent.includes("GEX")&&
        headers.includes("數據")&&headers.includes("重點解讀")&&headers.includes("明日觀察重點")&&
        lists.length===2&&lists[0].querySelectorAll('li').length>=3&&lists[1].querySelectorAll('li').length>=2&&
        !!resonance&&resonance.textContent.includes("程度")&&
        meta.textContent.includes("資料日")&&meta.textContent.includes("尚未獨立驗證預測力");
    }));
    await test(variant+' homepage shows score interpretation and action',()=>page.evaluate(()=>{
      const guide=document.getElementById('commandTradeGuide'),title=document.getElementById('commandGuideTitle'),
        detail=document.getElementById('commandGuideText'),scale=document.getElementById('commandGuideScale');
      return !!(guide&&title&&detail&&scale&&guide.getBoundingClientRect().height>50&&
        (title.textContent.startsWith('今日操作')||title.textContent.startsWith('歷史'))&&
        detail.textContent.length>20&&scale.querySelectorAll('.cmd-trade-guide-band').length===5&&
        guide.textContent.includes('分數解讀與操作方向'));
    }));
    await test(variant+' institution/source render',()=>page.evaluate(()=>document.getElementById('instSource').textContent.length>0&&document.getElementById('buyRows').textContent.length>0&&document.getElementById('sellRows').textContent.length>0));
    await test(variant+' DIX chart remains functional when latest.json is unavailable',async()=>{
      const x=await ctx.newPage();
      try{
        await x.route('**/data/research/us_options/latest.json*',route=>route.fulfill({status:503,body:'maintenance'}));
        await x.goto(BASE+'index.html',{waitUntil:'domcontentloaded',timeout:28000});
        await x.waitForFunction(()=>{
          const svg=document.getElementById('usopChart');
          return svg?.querySelectorAll('path[data-path-series]').length===3;
        },null,{timeout:18000});
        return await x.evaluate(()=>document.getElementById('usopValuegex').textContent!=='—'&&!document.getElementById('usopChartWrap').classList.contains('usop-error')&&document.querySelectorAll('#usopDailyBody tbody tr').length===3);
      }finally{await x.close()}
    });

    await test(variant+' home to linked core routes',()=>page.evaluate(()=>['./selections.html','./stocks.html','./bubbles.html','./upstream.html','./backtest.html'].every(x=>document.querySelector('a[href="'+x+'"]'))));
    if(variant==='mobile')await test('mobile market detail toggle',async()=>{const e=page.locator('#marketAdvanced');await e.evaluate(n=>n.open=true);return await e.evaluate(n=>n.open)});
   }
   if(file==='selections.html'){
    await test(variant+' G official 20 with dated source',()=>page.evaluate(()=>MODEL==='G'&&DATA.gSelection?.dataDate===DATA.dataDate&&document.querySelectorAll('#officialTb tr').length===DATA.models.G.length));
    await test(variant+' G 3 distinct panels',async()=>await page.locator('.g-report-jump').count()===3);
    await test(variant+' G warning only for valid 30% groups',()=>page.evaluate(()=>{
     const p=document.querySelector('#gSectorLeaderPanel');if(p.hidden)return true;
     return [...p.querySelectorAll('.g-sector-leader-card')].every(c=>(Number(c.querySelector('.g-sector-ratio')?.textContent.match(/(\d+)\/20/)?.[1]||0)>=6));
    }));
   }
   if(file==='bubbles.html'){
    await test(variant+' bubble frames/date',()=>page.evaluate(()=>document.getElementById('dateText').textContent.match(/^\d{4}-\d{2}-\d{2}$/)&&Number(document.getElementById('timeline').value)===Number(document.getElementById('timeline').max)));
    await test(variant+' bubble drawn visible and labeled',()=>page.evaluate(()=>document.querySelectorAll('svg#chart .point').length>10&&document.querySelectorAll('svg#chart .point text').length>10));
    await test(variant+' bubble has accessible complete sector directory',()=>page.evaluate(()=>document.querySelectorAll('#sectorDirectoryList button').length===document.querySelectorAll('svg#chart .point').length));
    await test(variant+' bubble click detail',async()=>{const before=await page.locator('#detailTitle').innerText();await page.locator('#sectorDirectory').evaluate(n=>n.open=true);await page.locator('#sectorDirectoryList button').first().click();const after=await page.locator('#detailTitle').innerText();return after&&after!==before&&after!=='點一顆泡泡看明細'});
    await test(variant+' bubble timeline back and forward',async()=>{await page.locator('#prev').click();const n=await page.locator('#dateText').innerText();await page.locator('#next').click();return n!==(await page.locator('#dateText').innerText())});
    await test(variant+' bubble search',async()=>{const before=await page.locator('svg#chart .point').count();await page.locator('#search').fill('半導體');const after=await page.locator('svg#chart .point').count();await page.locator('#search').fill('');return before>after&&after>=1});
    await test(variant+' bubble hot only toggle',async()=>{const b=page.locator('#hotOnly');await b.click();const ok=await b.evaluate(el=>el.classList.contains('on'));await b.click();return ok&&!(await b.evaluate(el=>el.classList.contains('on')))});
   }
   if(file==='stocks.html'){
    await test(variant+' diagnostics complete universe not fallback',()=>page.evaluate(()=>document.getElementById('status').textContent.includes('自建全市場資料')&&Number(document.getElementById('totalCount').textContent.replace(/,/g,''))>1000));
    await test(variant+' diagnostics searched stock',async()=>{await page.locator('#search').fill('2330');await page.waitForTimeout(200);const txt=await page.locator('#rows').innerText();await page.locator('#search').fill('');return txt.includes('2330')});
    await test(variant+' diagnostics watch toggle',async()=>{await page.locator('#watchFilter').click();const zero=await page.locator('#matchCount').innerText();await page.locator('#watchFilter').click();const has=await page.locator('#rows button[data-watch]').count();if(!has)return false;await page.locator('#rows button[data-watch]').first().click();await page.locator('#watchFilter').click();const one=await page.locator('#matchCount').innerText();return zero.includes('0 檔')&&one.includes('1 檔')});
    await test(variant+' diagnostics financial filter',async()=>{await page.locator('#watchFilter').click();await page.locator('#fundFilter').selectOption('growth');const stats=await page.locator('#matchCount').innerText();await page.locator('#fundFilter').selectOption('all');return /^符合 \d+ 檔/.test(stats)});
   }
   if(file==='upstream.html'){
    await test(variant+' 9 upstream categories populated',()=>page.evaluate(()=>document.getElementById('industryNav').querySelectorAll('[data-sector]').length>=10&&document.getElementById('results').textContent.includes('CPO')));
    await test(variant+' upstream CPO category focus',async()=>{const c=page.locator('#industryNav [data-sector="CPO"]');await c.click();return (await page.locator('#results').innerText()).includes('CPO')});
    await test(variant+' upstream search',async()=>{await page.locator('#industryNav [data-sector="all"]').click();await page.locator('#search').fill('環球晶');const txt=await page.locator('#results').innerText();await page.locator('#clear').click();return txt.includes('環球晶')});
    await test(variant+' upstream back to all',async()=>{await page.locator('#industryNav [data-sector="all"]').click();return (await page.locator('#results').innerText()).includes('所有產業')});
   }
   if(file==='history.html'){
    await test(variant+' history date select populated',async()=>await page.locator('#day option').count()>4);
    await test(variant+' history G primary render',async()=>await page.locator('#tb tr').count()>0&&await page.locator('#tableTitle').innerText()!=='' );
   }
   if(file==='backtest.html'){
    await test(variant+' backtest model controls',async()=>await page.locator('#modelTabs button').count()>=3);
    await test(variant+' backtest published data',async()=>!(await page.locator('#meta').innerText()).includes('載入失敗'));
   }
   await page.close();
  }
  await ctx.close();
 }
 await browser.close();
 const report={checks:checks.length,passed:checks.filter(x=>x.pass).length,failed:problems.length,failures:problems,warnings};
 fs.writeFileSync('/tmp/full_site_browser_audit.json',JSON.stringify({...report,checks},null,2));
 console.log('FULL_SITE_AUDIT '+JSON.stringify(report,null,2));
 if(problems.length)process.exitCode=1;
}
main().catch(e=>{console.error('AUDIT_FATAL',e.stack||e);process.exitCode=1});
