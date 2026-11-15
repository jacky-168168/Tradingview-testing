/* Financial Astrology V1.1 — book-informed, original-language chart explanations.
 * Interpretive source: 占星其實很簡單！1 入門篇, chapters 2-3, 2-4, 2-6, 2-7, 2-8.
 * No quoted book text and no prediction claims. Event sky chart != natal horoscope.
 */
(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports)module.exports=api;
  if(root)root.FinancialAstrologyInterpret=api;
})(typeof window!=='undefined'?window:null,function(){
'use strict';
const PLANETS={
  Sun:{title:'太陽',symbol:'☉',role:'主題、意志、權威與可見性',description:'傳統占星將太陽視為核心方向、目標與呈現於外的力量。',market:'研究上可對照市場主題、領導者與政策焦點，但太陽星座不能單獨預測股價。'},
  Moon:{title:'月亮',symbol:'☽',role:'情緒、反應、習慣與短期節奏',description:'傳統占星常把月亮連結到情緒感受、需要與快速改變的反應。',market:'金融占星常研究新月、滿月週期；這是值得回測的假說，並非滿月必跌。'},
  Mercury:{title:'水星',symbol:'☿',role:'資訊、分析、溝通與交易',description:'象徵資訊傳遞、細節理解、談判與商業交流。',market:'水星逆行常被賦予資訊反覆檢討的象徵；不是電腦故障或股市下跌的原因證據。'},
  Venus:{title:'金星',symbol:'♀',role:'價值、偏好、協調與關係',description:'象徵價值判斷、協調、偏好與吸引力。',market:'可把它當成研究估值、消費偏好等主題的聯想，不應直接映射某個產業漲跌。'},
  Mars:{title:'火星',symbol:'♂',role:'行動、競爭、衝突與執行力',description:'傳統上與主動出擊、競爭、速度與衝突連結。',market:'金融研究可檢驗成交量、真實波動率是否隨特定火星相位變化，而非預設暴漲或暴跌。'},
  Jupiter:{title:'木星',symbol:'♃',role:'擴張、期待、信念與成長',description:'常被視為成長、機會、信心與擴大規模的象徵；也可能包含過度擴張。',market:'這是研究風險偏好與成長敘事的占星假說，不能取代經濟數據。'},
  Saturn:{title:'土星',symbol:'♄',role:'結構、責任、限制與耐心',description:'常與規則、邊界、責任、長期建立和延遲連結。',market:'可聯想到監管、融資成本與風險限制，但須以市場資料驗證。'},
  Uranus:{title:'天王星',symbol:'♅',role:'改革、突發變化、創新與獨立',description:'象徵突破常規、創新、獨立與意外轉折。',market:'與科技或行情突變的連結是象徵性詮釋，不是科技股買進訊號。'},
  Neptune:{title:'海王星',symbol:'♆',role:'想像、願景、模糊與理想',description:'常代表理想化、想像空間、界線模糊與難以確認的資訊。',market:'可提醒研究市場敘事與真實財報的落差，但不表示市場一定受騙。'},
  Pluto:{title:'冥王星',symbol:'♇',role:'轉型、控制、權力與深層重構',description:'象徵較長時間尺度的重組、轉型與力量關係。',market:'只能作為觀察制度或產業結構變化的假說，無法直接設定價格目標。'}
};
const SIGNS={
  '牡羊':{element:'火',modality:'開創',qualities:'主動、競爭、迅速啟動',tension:'也可能過於急切'},
  '金牛':{element:'土',modality:'固定',qualities:'穩定、資源、累積價值',tension:'也可能不願改變'},
  '雙子':{element:'風',modality:'變動',qualities:'資訊交換、好奇、彈性變通',tension:'也可能過度分散'},
  '巨蟹':{element:'水',modality:'開創',qualities:'安全感、保護、情緒歸屬',tension:'也可能過度防禦'},
  '獅子':{element:'火',modality:'固定',qualities:'自信、展現、主導與創造',tension:'也可能太過自我中心'},
  '處女':{element:'土',modality:'變動',qualities:'分析、細節、修正與服務',tension:'也可能過分挑剔'},
  '天秤':{element:'風',modality:'開創',qualities:'協商、平衡、比較選項',tension:'也可能遲疑'},
  '天蠍':{element:'水',modality:'固定',qualities:'深入、保密、洞察與轉化',tension:'也可能過度控制'},
  '射手':{element:'火',modality:'變動',qualities:'探索、信念、遠景與拓展',tension:'也可能盲目樂觀'},
  '摩羯':{element:'土',modality:'開創',qualities:'紀律、責任、架構與目標',tension:'也可能過於僵硬'},
  '水瓶':{element:'風',modality:'固定',qualities:'創新、群體、系統性改革',tension:'也可能反對一切常規'},
  '雙魚':{element:'水',modality:'變動',qualities:'想像、同理、直覺與連結',tension:'也可能界線模糊'}
};
const ASPECTS={
  conjunction:{title:'合相',symbol:'☌',angle:0,meaning:'兩股主題集中、結合與放大',subtlety:'是否順利取決於兩顆行星的性質與整張星盤；不等於吉利。'},
  sextile:{title:'六分相',symbol:'⚹',angle:60,meaning:'協調、配合與可運用的機會',subtlety:'有機會不代表必然發生，仍要看其他條件。'},
  square:{title:'四分相',symbol:'□',angle:90,meaning:'摩擦、張力、障礙與推動調整',subtlety:'不只代表壞事，也可象徵因壓力而產生行動。'},
  trine:{title:'三分相',symbol:'△',angle:120,meaning:'自然流動、支持與順勢運作',subtlety:'順暢也可能維持既有慣性，未必帶來市場獲利。'},
  opposition:{title:'對分相',symbol:'☍',angle:180,meaning:'兩端對立、拉扯、平衡需求',subtlety:'強調兩種力量的關係，而非必然價格反轉。'}
};
const ELEMENTS={火:'熱情、行動與發起',土:'實務、累積與穩定',風:'概念、資訊與交流',水:'情緒、關係與感受'};
const MODALITIES={開創:'提出開始、發起新局',固定:'維繫、深化、持續',變動:'調整、適應、轉化'};
const MOTION={direct:'順行',retrograde:'逆行',stationary:'留／轉向附近'};
function safeNumber(x){return Number.isFinite(x)?x:null;}
function fmt(x,precision=2){return Number.isFinite(x)?Number(x).toFixed(precision):'—';}
function describe(data){
  if(!data||!Array.isArray(data.positions)||!data.positions.length)
    return {status:'unavailable',summary:'尚無可供解讀的星曆資料。',planets:[],aspects:[],elements:{},modalities:{}};
  const planets=[],elements={火:0,土:0,風:0,水:0},modalities={開創:0,固定:0,變動:0};
  for(const p of data.positions){
    const body=PLANETS[p.name],sign=SIGNS[p.sign];
    if(!body||!sign)continue;
    elements[sign.element]++;modalities[sign.modality]++;
    const speed=safeNumber(p.speedDegPerDay);
    const motion=MOTION[p.motion]||'未判定';
    const motionText=p.motion==='retrograde'
      ?'視運動逆行：從地球觀察黃經暫時後退。傳統常將它理解為反覆檢查、向內反思或重新評估；不是天體真的倒退。'
      :p.motion==='stationary'
      ?'接近視運動轉向（留）：傳統會特別留意這段轉折；不是可預期的股市轉折。'
      :'視運動順行：黃經一般向前變化；不能據此推論股價向上。';
    planets.push({name:p.name,title:body.title,symbol:body.symbol,sign:p.sign,
      longitudeDeg:safeNumber(p.longitudeDeg),signDegree:safeNumber(p.signDegree),
      motion,element:sign.element,modality:sign.modality,role:body.role,
      meaning:body.description,
      combined:'「'+body.title+'」象徵'+body.role+'；落在'+p.sign+'座時，傳統上會以'+sign.qualities+'的方式來表達這類主題（'+sign.tension+'）。',
      motionText,market:body.market,speedDegPerDay:speed});
  }
  const aspects=(data.aspects||[]).filter(a=>a&&PLANETS[a.bodyA]&&PLANETS[a.bodyB]&&ASPECTS[a.aspect])
    .map(a=>{
      const definition=ASPECTS[a.aspect],left=PLANETS[a.bodyA],right=PLANETS[a.bodyB];
      return {bodyA:a.bodyA,bodyB:a.bodyB,title:left.title+' '+definition.symbol+' '+right.title,
        kind:definition.title,angle:definition.angle,
        actualAngleDeg:safeNumber(a.actualAngleDeg),
        orbErrorDeg:safeNumber(a.orbErrorDeg),
        applying:a.applying===true,meaning:definition.meaning,subtlety:definition.subtlety,
        interpretation:'這個相位把「'+left.role+'」與「'+right.role+'」連結在一起。傳統上解讀為'+definition.meaning+'。'+definition.subtlety,
        status:a.applying===true?'接近精確相位（Applying）':'離開精確相位（Separating）'};
    }).sort((a,b)=>(a.orbErrorDeg??999)-(b.orbErrorDeg??999));
  const sun=planets.find(p=>p.name==='Sun');
  const moon=planets.find(p=>p.name==='Moon');
  const retro=planets.filter(p=>p.motion==='逆行');
  const active=aspects.slice(0,3).map(a=>a.title+'（'+a.kind+'）').join('、');
  const summary='這是某個時間點天空中的「行運星盤」，不是個人出生圖。'+
    (sun?'太陽位於'+sun.sign+'座，代表傳統詮釋的當期主題；':'')+
    (moon?'月亮位於'+moon.sign+'座，描述較短期的情緒象徵；':'')+
    (active?'目前較接近精確角度的相位有'+active+'。':'目前沒有符合本頁 ±2° 容許度的主要相位。')+
    ' 星象描述不包含經驗證的股市多空方向。';
  const dominant=(scores)=>Object.entries(scores).sort((a,b)=>b[1]-a[1]).slice(0,2)
    .map(([key,n])=>key+' '+n+'顆').join('、');
  const categories='四元素分布：'+dominant(elements)+'；行動模式分布：'+dominant(modalities)+
    '。這是十天體等權重的描述性計數，並非傳統命盤加權評分，也不是股市因子分數。';
  const moonPhase=data.moon?.phaseLabel||'尚未取得月相資料';
  const moonText='月相：'+moonPhase+'。月相是太陽與月亮之間的相對角度；滿月、新月在金融占星中常被拿來檢驗市場週期，但統計結論並不一致。';
  return {status:'ok',summary,planets,aspects,elements,modalities,retrogradeNames:retro.map(p=>p.title),
    categories,moonText,bookScope:'本書主要教授個人出生圖判讀；目前顯示的行運天象沒有出生時間、地點，因此不計上升、天頂及十二宮。'};
}

/** Primary human-readable synthesis for the selected historical/current sky.
 * This is a traditional symbolic reading, NOT a prediction of equity returns.
 */
function plainLanguageConclusion(data){
  const r=describe(data);
  if(r.status!=='ok')return {
    status:'unavailable',headline:'目前沒有可解讀的星盤。',
    reason:'尚未取得有效的行星位置資料。',
    market:'無法判定股市多空方向。',watch:'請先查詢有效日期。',
    limitation:'未提供已驗證的金融統計證據。'
  };
  const sun=r.planets.find(p=>p.name==='Sun');
  const moon=r.planets.find(p=>p.name==='Moon');
  const key=(r.aspects||[]).slice().sort((a,b)=>{
    function weight(x){
      const names=[x.bodyA,x.bodyB];
      const inner=names.filter(n=>['Sun','Moon','Mercury','Venus','Mars','Jupiter'].includes(n)).length;
      const sunMoon=names.some(n=>['Sun','Moon'].includes(n))?8:0;
      const marsJupiter=names.includes('Mars')&&names.includes('Jupiter')?12:0;
      const tension=['square','opposition'].includes(x.kind)||x.kind==='四分相'||x.kind==='對分相'?2:0;
      return inner*5+sunMoon+marsJupiter+tension-(x.orbErrorDeg||0)*2;
    }
    return weight(b)-weight(a);
  })[0];
  let headline='',reason='',watch='';
  if(key){
    const names=[key.bodyA,key.bodyB];
    const marsJupiter=names.includes('Mars')&&names.includes('Jupiter');
    const marsSaturn=names.includes('Mars')&&names.includes('Saturn');
    const saturnUranus=names.includes('Saturn')&&names.includes('Uranus');
    const mercuryNeptune=names.includes('Mercury')&&names.includes('Neptune');
    if(marsJupiter&&key.kind==='合相'){
      headline='傳統占星象徵：行動與擴張同時突出，容易積極，也要留意過度自信。';
      reason='核心依據是火星與木星合相：火星代表競爭、行動，木星代表樂觀、成長；兩者主題集中，但不代表股市必漲。';
      watch='可觀察 Nasdaq、S&P 500 的成交量、ATR、VIX 是否真的擴張，並核對技術趨勢。';
    }else if(marsSaturn&&['四分相','對分相'].includes(key.kind)){
      headline='傳統占星象徵：推進與限制相互拉扯，主題偏向壓力下的調整。';
      reason='火星象徵行動、土星象徵規範與限制；'+key.kind+'通常被視為需要克服的張力。';
      watch='可檢查股市實際波動率、信用利差、重大政策事件與支撐壓力位。';
    }else if(saturnUranus&&['四分相','對分相'].includes(key.kind)){
      headline='傳統占星象徵：舊制度與新變革間出現明顯拉扯。';
      reason='土星偏向結構與紀律，天王星偏向改革與突破；'+key.kind+'象徵兩者存在張力。';
      watch='可觀察科技股相對強弱、產業輪動與市場對政策的實際反應。';
    }else if(mercuryNeptune&&['四分相','對分相'].includes(key.kind)){
      headline='傳統占星象徵：資訊判讀與想像之間容易產生落差。';
      reason='水星象徵消息和分析，海王星象徵想像與模糊；'+key.kind+'在傳統解讀中偏向需要仔細查證。';
      watch='可觀察市場傳聞與正式財報之間的落差；所有消息應比對可靠來源。';
    }else{
      headline='傳統占星象徵：'+key.meaning+'，但沒有預設的吉凶或股票方向。';
      reason='主要相位為'+key.title+'（'+key.kind+'，與精確角度相差 '+fmt(key.orbErrorDeg)+'°）。'+key.interpretation;
      watch='可把該相位時間記錄下來，與股票成交量、VIX、ATR 及歷史同類事件的實際價格變化比較。';
    }
  }else{
    headline='傳統占星象徵：目前沒有特別接近的五大行星相位，以行星所在星座的主題為主。';
    reason='選定時間內沒有落入 ±2° 容許度的五大相位，不能把這解讀成股市將平靜或必然盤整。';
    watch='可觀察月相、重大宏觀經濟日程與股市實際價格結構；等待可回測的事件條件。';
  }
  const context=(sun?'太陽在'+sun.sign+'座，'+SIGNS[sun.sign].qualities+'；':'')+
    (moon?'月亮在'+moon.sign+'座，'+SIGNS[moon.sign].qualities+'。':'');
  return {status:'ok',headline,reason:reason+(context?' 配合星座背景：'+context:''),
    market:'股市方向：無法根據星盤判斷偏多或偏空；這不是買賣訊號。',
    watch,limitation:'統計證據：這個日期的星象解讀尚未建立能證明股市預測優勢的樣本外績效；應以下方真實行情回測為準。'};
}
function renderPlainLanguageConclusion(data){
  if(typeof document==='undefined')return plainLanguageConclusion(data);
  const x=plainLanguageConclusion(data);
  const targets={
    astroConclusionHeadline:x.headline,
    astroConclusionWhy:x.reason,
    astroConclusionMarket:x.market,
    astroConclusionWatch:x.watch,
    astroConclusionEvidence:x.limitation
  };
  for(const [id,value] of Object.entries(targets)){
    const node=document.getElementById(id);
    if(node)node.textContent=value;
  }
  const time=document.getElementById('astroConclusionAt');
  if(time){
    const instant=new Date(data?.generatedAt||'');
    if(Number.isFinite(instant.getTime())){
      const zone=document.getElementById('astroTimezone')?.value||'Asia/Taipei';
      try{
        time.textContent='星盤時間：'+new Intl.DateTimeFormat('zh-TW',
          {timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(instant)+'（'+zone+'）';
      }catch(_){time.textContent='星盤時間：'+instant.toISOString();}
    }else time.textContent='星盤時間尚不可用';
  }
  return x;
}

function el(tag,cls,textValue){
  const e=document.createElement(tag);
  if(cls)e.className=cls;
  if(textValue!==undefined)e.textContent=textValue;
  return e;
}
function render(data){
  if(typeof document==='undefined')return describe(data);
  const reading=describe(data);
  const overview=document.getElementById('astroReadingOverview');
  const highlights=document.getElementById('astroReadingHighlights');
  const planetBox=document.getElementById('astroReadingPlanets');
  const aspectBox=document.getElementById('astroReadingAspects');
  const categoryBox=document.getElementById('astroReadingCategories');
  if(!overview||!highlights||!planetBox||!aspectBox||!categoryBox)return reading;
  renderPlainLanguageConclusion(data);
  overview.textContent=reading.summary;
  [highlights,planetBox,aspectBox,categoryBox].forEach(node=>node.replaceChildren());
  if(reading.status!=='ok')return reading;
  const lead=[
    ['☀️ 太陽的主題',reading.planets.find(p=>p.name==='Sun')],
    ['🌙 月亮的反應',reading.planets.find(p=>p.name==='Moon')],
    ['🔭 最接近的相位',reading.aspects[0]]
  ];
  for(const [label,item] of lead){
    const card=el('div','astro-reading-highlight');
    card.appendChild(el('small','',label));
    if(item&&'combined' in item)card.appendChild(el('p','',item.combined));
    else if(item&&'interpretation' in item)card.appendChild(el('p','',item.title+'：'+item.interpretation));
    else card.appendChild(el('p','','目前沒有此類可判讀項目。'));
    highlights.appendChild(card);
  }
  for(const p of reading.planets){
    const details=el('details','astro-reading-item');
    const summary=el('summary','',p.symbol+' '+p.title+'｜'+p.sign+' '+fmt(p.signDegree)+'°｜'+p.motion);
    details.appendChild(summary);
    const content=el('div','astro-reading-detail');
    content.appendChild(el('p','',p.combined));
    content.appendChild(el('p','',p.motionText));
    content.appendChild(el('p','astro-reading-market','金融研究提醒：'+p.market));
    details.appendChild(content);
    planetBox.appendChild(details);
  }
  if(!reading.aspects.length){
    aspectBox.appendChild(el('p','astro-reading-empty','目前沒有落入 ±2° 的五大相位，並不是缺少市場行情。'));
  }
  for(const [i,a] of reading.aspects.entries()){
    const details=el('details','astro-reading-item');
    if(i<3)details.open=true;
    details.appendChild(el('summary','',a.title+'｜'+a.kind+' '+a.angle+'°｜誤差 '+fmt(a.orbErrorDeg)+'°'));
    const body=el('div','astro-reading-detail');
    body.appendChild(el('p','',a.interpretation));
    body.appendChild(el('p','',a.status+'；越接近 0°，越貼近幾何精確相位。'));
    body.appendChild(el('p','astro-reading-market','金融研究提醒：這只是天文相位與傳統象徵，不是股價上漲、下跌或變盤的可靠訊號。'));
    details.appendChild(body);aspectBox.appendChild(details);
  }
  categoryBox.appendChild(el('p','',reading.categories));
  categoryBox.appendChild(el('p','',reading.moonText));
  categoryBox.appendChild(el('p','',reading.bookScope));
  const list=el('div','astro-element-grid');
  for(const [name,meaning] of Object.entries(ELEMENTS)){
    list.appendChild(el('div','astro-element-tile',name+'元素 '+(reading.elements[name]||0)+' 顆｜'+meaning));
  }
  for(const [name,meaning] of Object.entries(MODALITIES)){
    list.appendChild(el('div','astro-element-tile',name+'特質 '+(reading.modalities[name]||0)+' 顆｜'+meaning));
  }
  categoryBox.appendChild(list);
  return reading;
}
return {PLANETS,SIGNS,ASPECTS,ELEMENTS,MODALITIES,describe,plainLanguageConclusion,renderPlainLanguageConclusion,render};
});
