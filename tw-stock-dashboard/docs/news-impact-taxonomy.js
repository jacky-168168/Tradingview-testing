/* Deterministic V1.2 topic recognition. Observed moves != forecasts. */
(function(root,factory){const api=factory();if(typeof module==="object"&&module.exports)module.exports=api;if(root)root.NewsImpactTaxonomy=api})(typeof window!=="undefined"?window:(typeof globalThis!=="undefined"?globalThis:null),function(){
"use strict";
const VERSION="2026-11-09-v1.2";
const TOPICS=[
["AI算力／資料中心",/\b(?:AI|GPU|CoreWeave|Nvidia|Oracle|Microsoft)\b|算力|資料中心|雲端|輝達|甲骨文|微軟/i],
["半導體／封裝",/封裝|台積電|半導體|晶圓|光通訊|散熱|伺服器|semiconductor|packaging|chipmaker/i],
["記憶體產業",/\b(?:DRAM|DDR[345]|HBM|NAND)\b|記憶體|華邦電|南亞科|旺宏/i],
["企業財報／營收",/財報|財測|營收|獲利|毛利率|法說|\b(?:earnings|EPS|guidance|revenue|profit)\b/i],
["央行／利率",/聯準會|美聯儲|升息|降息|殖利率|利率|\b(?:Fed|FOMC|rate hikes?|rate cuts?|Treasury yields?)\b/i],
["經濟指標",/非農|就業|通膨|CPI|PPI|GDP|PCE|失業率|景氣|經濟|\b(?:payrolls?|inflation|jobs report|recession)\b/i],
["原油／天然氣",/原油|油價|油井|石油|能源|天然氣|\b(?:WTI|OPEC|oil|crude|gas field|NYMEX)\b/i],
["貴金屬／銅",/黃金|白銀|金價|銀價|銅價|貴金屬|\b(?:gold|silver|copper|COMEX)\b/i],
["農產品",/大豆|豆油|小麥|玉米|農產品|咖啡|腰果|\b(?:CBOT|soybean|wheat|corn|grain)\b/i],
["匯率",/匯率|美元|港幣|紐元|紐幣|美元指數|\b(?:NZD|forex|dollar|currency|yen|yuan|euro)\b/i],
["選舉／政治",/選舉|期中選舉|組閣|執政|白宮|國會|川普|特朗普|\b(?:election|midterms?|coalition|ruling party|Congress|Trump|White House)\b/i],
["地緣政治",/以色列|伊朗|中東|戰爭|和談|停火|烏克蘭|荷姆茲|\b(?:Israel|Iran|Ukraine|Russia|missile|drone attack|peace talks?|Kremlin)\b/i],
["關稅／貿易",/關稅|貿易戰|出口管制|制裁|\b(?:tariffs?|sanctions?|trade war|export controls?)\b/i],
["氣候／補貼",/氣候|新能源|電動車補貼|\b(?:COP3[0-9]|climate|subsidies|electrification)\b/i],
["市場行情／評論",/股價|股市|反彈|暴跌|賣壓|期貨|ETF|散戶|\b(?:stocks?|shares?|Wall Street|cryptocurrenc)\b/i]
];
const ASSET_TERMS=[
["WTI原油",/(?:WTI|NYMEX原油|國際油價|原油|油價|crude oil|oil prices?|\boil\b)/i],
["黃金",/(?:黃金|金價|COMEX黃金|\bgold\b)/i],
["白銀",/(?:白銀|銀價|\bsilver\b)/i],
["美元",/(?:美元指數|美元|US dollar|U\.S\. dollar|dollar index|\bDXY\b)/i],
["紐元NZD",/(?:紐元|紐幣|New Zealand Dollar|NZ dollar|kiwi dollar|\bNZD\b)/i],
["銅",/(?:銅價|\bcopper\b)/i],
["農產品期貨",/(?:大豆|豆油|小麥|玉米|CBOT|soybean|wheat|corn)/i],
["加密資產",/(?:加密貨幣|比特幣|\bbitcoin\b|cryptocurrenc)/i]
];
const UP=/(?:上漲|大漲|走高|走強|升值|漲幅|創高|飆升|反彈|\b(?:rises?|rose|gains?|higher|advances?|advanced|surges?|climbs?|rebounds?)\b)/i;
const DOWN=/(?:下跌|大跌|暴跌|走低|走弱|重挫|腰斬|跌幅|貶值|\b(?:falls?|fell|drops?|declines?|slides?|weakens?|plunges?)\b)/i;
const FUTURE=/(?:將|可能|預計|預估|預測|恐|或將|看漲|看跌|預期|下週|明年|\b(?:could|may|might|expect|forecast|likely|predict)\b)/i;
function examine(item){
 const title=String(item?.title||"").trim(),category=String(item?.category||""),source=String(item?.source||"");
 const topics=TOPICS.filter(t=>t[1].test(title)).map(t=>t[0]),rules=[],observations=[],flags=[];
 // "60.167美元" and "砸280億美元" are monetary units, NOT USD FX news.
 const fxReal=/匯率|美元指數|美元走|美元升|美元跌|美金匯價|港幣|港元|紐元|紐幣|\b(?:USD|US dollar|U\.S\. dollar|NZD|New Zealand Dollar|NZ dollar|currency|forex|yen|yuan|euro)\b/i.test(title);
 if(!fxReal&&topics.includes("匯率"))topics.splice(topics.indexOf("匯率"),1);
 function add(id,name,impact,why,caveat,scope){
  if(!rules.some(x=>x.id===id))rules.push({id,name,impact,why,caveat,scope:scope||"研究情境",model:VERSION})
 }
 function topic(t){if(!topics.includes(t))topics.push(t)}
 const rumored=/傳聞|據傳|傳出|可能|恐|預計|或將|\b(?:could|may|might|reportedly|rumou?r|expects?|forecast|plans?)\b/i.test(title);
 if(rumored)flags.push("傳聞／預期未確認");
 if(/？|\?|評論|前瞻|社論|看漲|看跌|analyst|opinion/i.test(title))flags.push("評論／預測");
 if(/PTT|論壇|討論牆|股市爆料|鉅亨號/i.test(category+" "+source))flags.push("轉載／論壇");
 // Reactions described in a headline are observations, never predictions.
 // Split at the *next* mentioned asset to avoid oil-down/gold-up cross-tagging.
 const found=[];
 for(const [asset,re] of ASSET_TERMS){const m=re.exec(title);if(!m)continue;
  // Prices quoted in "60.167美元" denote USD units, not a USD-index move.
  if(asset==="美元"&&/\d(?:\.\d+)?$/.test(title.slice(0,m.index)))continue;
  found.push({asset,start:m.index,end:m.index+m[0].length});}
 found.sort((a,b)=>a.start-b.start);
 for(let i=0;i<found.length;i++){
  const x=found[i],next=found[i+1];
  const phrase=title.slice(x.end,Math.min(x.end+38,next?next.start:title.length));
  if(FUTURE.test(phrase.slice(0,25)))continue;
  const up=UP.test(phrase),down=DOWN.test(phrase);
  if(up!==down)observations.push({asset:x.asset,label:up?"新聞稱已上漲":"新聞稱已下跌"});
 }
 const goodHike=/(?:升息|加息)(?:押注|預期|機率).{0,10}(?:降溫|減弱|降低|下降|回落)|(?:hike bets?|hike expectations?).{0,15}(?:cool|ease|fall|fade)/i.test(title);
 if(goodHike){
  topic("央行／利率");add("hike-bets-cool","升息預期降溫（非實際降息）",{"美元":-15,"美債殖利率":-15},"升息押注減弱可能壓抑美元與利率；不是央行宣布降息。","需觀察利差、匯率和官方決議；單一分析師看法尚未驗證。","市場預期");
 }
 const strongJobs=/(?:非農|就業|payrolls?|jobs report).{0,35}(?:激增|大增|強勁|報喜|太強|surge|strong|beat)/i.test(title);
 if(strongJobs)add("strong-jobs-context","強勁就業／利率預期",{},"就業強可能推升升息押注，也可能顯示景氣韌性，方向依市場預期而定。","缺少原始數據與當時共識，不以就業標題直接判美股利空。","總經");
 if(/先進封裝|CoWoS|advanced packaging/i.test(title)&&/擴產|資本支出|砸近|需求爆發|營收齊飆|spending boom|demand surge/i.test(title)){
  add("advanced-packaging-demand","先進封裝／設備需求擴張",{"AI／半導體設備":25},"擴產增加設備與材料商接單機會，但不代表股價立即上漲。","須確認資本支出已執行、受益公司與當時估值。","產業");
 }
 if(/(?:甲骨文|微軟|Oracle|Microsoft|CoreWeave|GPU)/i.test(title)&&/租用|租賃|算力|cloud contracts?|GPU demand/i.test(title)&&/終止|取消|縮減|減少|停租|reduc|cancel|end contracts?/i.test(title)){
  add("cloud-contract-risk","雲端算力合約不確定",{"雲端算力租賃":-20},"取消租約可能降低出租方收入能見度。","須確認是否只是傳聞、僅涉及舊 GPU，不能代表整體 AI 需求轉弱。","產業");
 }
 if(/天然氣|gas field|gas production/i.test(title)&&/停產|中斷|暫停|遭攻擊|suspend|shutdown|attack/i.test(title)){
  add("gas-field-outage","天然氣供給中斷",{"天然氣供應":35},"設施停產可能使地區天然氣供給吃緊。","天然氣與 WTI 不同，無原油供應證據不應推算 WTI 利多。","天然氣");
 }
 if(/原油|石油|crude oil|oil output|oil production/i.test(title)&&/產量創新高|產量增加|原油增產|record production|record output/i.test(title)){
  add("crude-supply-growth","原油供給增加",{"WTI原油":-25},"新增產量可能降低油價支撐。","觀察 OPEC、EIA、庫存及需求；一口鑽井變動影響有限。","原油");
 }
 if(/美伊|伊朗|Iran/i.test(title)&&/和談|談判|peace talks?|negotiations?/i.test(title)&&/希望|進展|恢復|再起|progress|hope|resume/i.test(title)&&!/破局|失敗|collapse|fail/i.test(title)){
  add("iran-talks","伊朗和談／油價風險溢價",{"WTI原油":-20},"和談進展可能降低地緣油價風險溢價。","和談不等於達成停火，且原油可能已提前反應。","地緣情境");
 }
 // Separate supplier tailwinds from broad tech-index direction. Reported
 // profit growth is an observation; an actual future share move is not known.
 if(/記憶體|DRAM|DDR[345]|NAND/i.test(title)&&/缺貨|供給吃緊|漲價|記憶體成本|供應不足/i.test(title)&&!/暴跌|價格下跌|跌價/i.test(title)){
  add("memory-tight-supply","記憶體供給偏緊／漲價",{"台股記憶體供應端":20},"供給偏緊及產品漲價通常支撐製造商報價，但會增加下游採購成本。","預期明年漲價、單一公司言論或庫存估計都尚未等於實際合約價格。","產業");
 }
 if(/AI|伺服器|台積電設備|光通訊|散熱/i.test(title)&&/需求熱|需求強勁|營收創高|獲利狂飆|訂單成長|擴大布局/i.test(title)&&!rules.some(r=>r.id==="advanced-packaging-demand")){
  add("ai-supply-growth","AI硬體供應鏈需求改善",{"AI／半導體設備":15},"需求或營收改善對供應鏈基本面可能有利，不代表股價必漲。","個別公司產品組合與股價已反映程度未知。","產業");
 }
 const corp=/財報|財測|營收|獲利|毛利率|\b(?:EPS|guidance|revenue|earnings)\b/i.test(title);
 if(corp){
  const good=/上修|成長|創高|飆升|超標|大增|獲利暴增|raise(?:d|s)? guidance|record revenue/i.test(title);
  const bad=/下修|衰退|不如預期|減少|虧損|縮水|cut guidance|miss(?:es|ed)? estimates/i.test(title);
  if(good!==bad)add(good?"earnings-up":"earnings-down",good?"企業財報／需求改善":"企業財報／財測轉弱",{},
   good?"公司營收獲利改善，但未必高於市場共識。":"公司獲利或財測轉弱可能構成企業基本面壓力。",
   "需核對公司、官方財報、預期差與股價反應；不直接外推大盤。","公司基本面");
 }
 if(/選舉|期中選舉|election|midterm/i.test(title))
  add("election-context","選舉／政策背景",{},"選情需連結具體關稅、稅務、科技、能源或國防政策才能判斷資產方向。","不能按政黨勝敗直接推導美股或黃金固定漲跌。","政治");
 if(/COP3[0-9]|氣候峰會|climate summit|EV, battery subsidies/i.test(title))
  add("climate-context","氣候／補貼政策討論",{},"補貼與能源政策可能改變個別產業需求。","僅開會或討論，不代表政策生效。","政策");
 const aliases={"財報":"企業財報／營收","報價":"市場行情／評論","AI需求":"AI算力／資料中心","國際總經":"經濟指標","總經":"經濟指標","原油／能源":"原油／天然氣","農產品":"農產品","貴金屬":"貴金屬／銅","地緣政治":"地緣政治","國際政策":"選舉／政治","美國選舉":"選舉／政治"};
 if(topics.length===0&&aliases[category])topic(aliases[category]);
 return {topics:[...new Set(topics)],rules,observations,flags,version:VERSION};
}
return {VERSION,examine};
});