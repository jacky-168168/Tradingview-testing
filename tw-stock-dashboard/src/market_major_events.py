"""Major Taiwan-market catalyst radar.
Headline discovery only. Never convert an unverified headline into a confirmed fact.
No API key; only official event seeds and attributable Google News RSS articles.
"""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Taipei")
OUTPUT=Path(__file__).resolve().parents[1]/"docs/data/market_events/latest.json"
FRESH_NEWS_HOURS=48  # Display and publish only genuinely recent headlines, including weekends.
QUERIES=[
 ("財報","(輝達 OR NVIDIA OR 微軟 OR 蘋果 OR Meta OR Google OR 亞馬遜) (財報 OR 財測 OR 法說) when:2d",r"財報|財測|法說|earnings|財季|業績|營收",["美國科技","AI","台積電供應鏈"]),
 ("展覽","(PCB OR 電路板 OR AI OR 半導體) (展覽 OR 展會 OR 研討會) when:2d",r"展覽|展會|展期|研討會|登場|論壇|expo|show",["PCB","載板","半導體"]),
 ("報價","(矽晶圓 OR wafer) (漲價 OR 報價 OR 價格) when:2d",r"矽晶圓|wafer|晶圓報價",["矽晶圓","半導體材料"]),
 ("報價","(被動元件 OR MLCC OR 電容) (漲價 OR 報價 OR 調漲) when:2d",r"被動元件|MLCC|電容|電阻",["被動元件"]),
 ("報價","(DRAM OR NAND OR HBM OR 記憶體) (價格 OR 報價 OR 漲價) when:2d",r"DRAM|NAND|HBM|記憶體",["記憶體","HBM"]),
 ("AI需求","(AI伺服器 OR AI晶片 OR GPU) (需求 OR 訂單 OR 擴產) when:2d",r"AI|GPU|晶片|伺服器|算力",["AI伺服器","半導體"]),
 ("AI需求","(CoWoS OR CPO OR 光通訊 OR 先進封裝) (訂單 OR 擴產 OR 需求) when:2d",r"CoWoS|CPO|光通訊|先進封裝",["先進封裝","CPO"]),
 ("財報","台積電 (財報 OR 法說 OR 資本支出 OR 擴產) when:2d",r"台積電|TSMC|晶圓代工",["晶圓代工","半導體"]),
 ("總經","(聯準會 OR FOMC OR Fed) (升息 OR 降息 OR 利率) when:2d",r"聯準會|FOMC|Fed|央行|利率|降息|升息",["金融","科技股"]),
 # 三大商品類別各使用獨立的新聞檢索，避免只有油價、金價而漏掉供需報告。
 ("原油／能源","(WTI OR 布蘭特 OR Brent OR 原油 OR OPEC) (油價 OR 產量 OR 庫存 OR 減產 OR 增產 OR 供應) when:2d",r"原油|WTI|布蘭特|Brent|OPEC|油價",["原油","OPEC+","塑化","航運"]),
 ("原油／能源","(EIA OR 美國能源資訊署) (原油庫存 OR 石油庫存 OR WTI) when:2d",r"EIA|美國能源資訊署|原油|石油|WTI",["EIA","原油","能源"]),
 ("原油／能源","(天然氣 OR LNG OR Henry Hub) (庫存 OR 供給 OR 價格 OR 出口) when:2d",r"天然氣|LNG|Henry Hub",["天然氣","能源"]),
 ("貴金屬","(黃金 OR 金價 OR gold) (美元 OR 殖利率 OR 升息 OR 降息 OR 漲 OR 跌) when:2d",r"黃金|金價|gold|XAU",["黃金","美元","利率"]),
 ("貴金屬","(白銀 OR 銀價 OR silver) (漲 OR 跌 OR 需求 OR 供給 OR 報價) when:2d",r"白銀|銀價|silver|XAG",["白銀","工業需求","貴金屬"]),
 ("貴金屬","(鉑金 OR 鈀金 OR platinum OR palladium) (價格 OR 供給 OR 需求 OR 漲 OR 跌) when:2d",r"鉑金|鈀金|platinum|palladium",["鉑金","鈀金","工業需求"]),
 ("農產品","(黃豆 OR 大豆 OR 玉米 OR 小麥 OR soybean OR corn OR wheat) (價格 OR 收成 OR 乾旱 OR 出口 OR USDA) when:2d",r"黃豆|大豆|玉米|小麥|soybeans?|corn|wheat|USDA",["黃豆","玉米","小麥"]),
 ("農產品","(咖啡 OR 糖價 OR 原糖 OR coffee OR sugar) (漲 OR 跌 OR 乾旱 OR 產量 OR 出口) when:2d",r"咖啡|coffee|糖價|原糖|sugar",["咖啡","原糖","食品"]),
 ("農產品","(USDA OR 美國農業部 OR WASDE) (農產品 OR 黃豆 OR 玉米 OR 小麥 OR 穀物) when:2d",r"USDA|美國農業部|WASDE|黃豆|玉米|小麥|穀物",["USDA","農產品","供需報告"]),
 ("總經","(CPI OR PCE OR 非農) (通膨 OR 就業 OR 利率) when:2d",r"CPI|PCE|非農|通膨|就業",["總經","利率"]),
]
OFFICIAL=[
 {"id":"event-tpca-show-2026","type":"event","category":"展覽","title":"TPCA Show 2026｜台灣電路板產業國際展",
  "date":"2026-10-20","endDate":"2026-10-22","source":"TPCA Show 官方","url":"https://www.tpcashow.com/",
  "themes":["PCB","CCL","載板","先進封裝","AI伺服器"],"confirmed":True},
 {"id":"event-impact-2026","type":"event","category":"展覽","title":"IMPACT 2026｜國際構裝暨電路板研討會",
  "date":"2026-10-19","endDate":"2026-10-22","source":"TPCA 台灣電路板協會","url":"https://www.tpca.org.tw/web/news_detail.php?menu_no=161&mod_no=1&news_no=500394",
  "themes":["先進封裝","PCB","載板"],"confirmed":True},
 {"id":"event-taitronics-2026","type":"event","category":"展覽","title":"TAITRONICS & AIoT Taiwan 2026",
  "date":"2026-10-20","endDate":"2026-10-22","source":"台北世貿展覽行事曆","url":"https://www.twtc.org.tw/en/exhibition?p=menu1",
  "themes":["AIoT","電子零組件"],"confirmed":True},
 {"id":"event-netflix-q3-2026","type":"event","category":"財報","title":"Netflix Q3 財報｜美西 10/20 公布",
  "date":"2026-10-21","endDate":"2026-10-21","source":"Netflix 投資人關係","url":"https://ir.netflix.net/investor-news-and-events/financial-releases/press-release-details/2026/Netflix-to-Announce-Third-Quarter-2026-Financial-Results/default.aspx",
  "themes":["美國科技","串流媒體"],"confirmed":True},
 {"id":"event-tesla-q3-2026","type":"event","category":"財報","title":"Tesla Q3 財報｜美東 10/21 盤後",
  "date":"2026-10-22","endDate":"2026-10-22","source":"Tesla 投資人關係","url":"https://ir.tesla.com/press-release/tesla-third-quarter-2026-production-deliveries-and-deployments",
  "themes":["電動車","儲能","車用電子"],"confirmed":True},
 {"id":"event-fomc-oct2026","type":"event","category":"總經","title":"美國聯準會 FOMC 利率決策｜美國 10/27–28",
  "date":"2026-10-28","endDate":"2026-10-29","source":"Federal Reserve 官方","url":"https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
  "themes":["升降息","美元","黃金","科技股"],"confirmed":True},
]
UA="Mozilla/5.0 (compatible; MarketCatalystRadar/1.0; +https://github.com/jacky-168168/Tradingview-testing)"
PTT_ATOM="https://www.ptt.cc/atom/stock.xml"
PTT_NEWS=re.compile(r"台股|臺股|台指|加權|台積電|股價|股市|美股|期貨|金融|ETF|股票|關稅|利率|油價|晶片|AI|半導體|暴跌|補跌",re.I)
PRIORITY=re.compile(r"漲價|調漲|上調|上漲|下跌|走高|走低|漲幅|跌幅|創高|創低|大漲|大跌|暴跌|暴增|飆升|缺貨|產能|擴產|突破|訂單|需求|財報|財測|FOMC|降息|升息|開幕|展覽|停產|限產|出口管制|guidance|earnings|surge|cuts|庫存|減產|增產|出口|收成|乾旱|歉收|供需|供應|禁運|播種|產量|進口|oil inventory|harvest|drought|USDA|EIA",re.I)

def rss_url(q):
    return "https://news.google.com/rss/search?"+urllib.parse.urlencode({"q":q,"hl":"zh-TW","gl":"TW","ceid":"TW:zh-Hant"})

def fetch_feed(feed):
    category,query,matcher,themes=feed
    req=urllib.request.Request(rss_url(query),headers={"User-Agent":UA,"Accept":"application/rss+xml, application/xml, text/xml"})
    with urllib.request.urlopen(req,timeout=14) as response:
        raw=response.read(1_200_000)
    return parse_feed(raw,feed)

def parse_feed(xml,feed,now=None):
    category,query,matcher,themes=feed
    now=now or datetime.now(TZ)
    root=ET.fromstring(xml)
    result=[]
    for el in root.findall(".//channel/item")[:28]:
        title=" ".join((el.findtext("title") or "").split())
        source=(el.findtext("source") or "").strip()
        url=(el.findtext("link") or "").strip()
        if not source and " - " in title:
            title,source=title.rsplit(" - ",1)
        elif source and title.endswith(" - "+source):
            title=title[:-(len(source)+3)]
        published=el.findtext("pubDate")
        try:
            t=parsedate_to_datetime(published).astimezone(TZ)
        except (ValueError,TypeError,OverflowError):
            continue
        if t>now+timedelta(minutes=5) or t<now-timedelta(hours=FRESH_NEWS_HOURS):continue
        if not re.search(matcher,title,re.I) or not PRIORITY.search(title):continue
        if len(title)<12 or len(title)>180:continue
        if not url.startswith("https://") or not source:continue
        if re.search(r"股價目標|目標價|買進評等|推薦股|明牌|飆股|哪檔|這\s*[0-9一二三四五六七八九十]+\s*檔|台股大跌後該買|買什麼|翻身密碼|獲利密碼|解密飆股|名單出列|搶進哪|概念股出列",title):continue
        if re.search(r"投資網誌|股市同學會|股市爆料|聚財網",source,re.I):continue
        key=re.sub(r"[^\w\u4e00-\u9fff]","",title.casefold())
        result.append({"id":"news-"+hashlib.sha256(key.encode()).hexdigest()[:16],
         "type":"news","category":category,"title":title,"date":t.strftime("%Y-%m-%d"),
         "publishedAt":t.isoformat(timespec="seconds"),"source":source[:50],"url":url,
         "themes":themes,"confirmed":False})
    return result

def parse_ptt_stock_news(xml,now=None):
    """Only original timestamped PTT Stock [新聞] links; NOT verified journalism or social votes."""
    now=now or datetime.now(TZ)
    root=ET.fromstring(xml)
    entries=root.findall("{http://www.w3.org/2005/Atom}entry")
    if not entries:raise ValueError("PTT Atom 無項目")
    output=[]
    for post in entries[:90]:
        title=" ".join((post.findtext("{http://www.w3.org/2005/Atom}title") or "").split())[:180]
        if not re.match(r"^\[新聞\]",title) or not PTT_NEWS.search(title):continue
        url=next((x.get("href") for x in post.findall("{http://www.w3.org/2005/Atom}link") if x.get("href")),"")
        uri=urllib.parse.urlsplit(url)
        if uri.scheme!="https" or uri.hostname!="www.ptt.cc" or not re.fullmatch(r"/bbs/Stock/M\.[^/]+\.html",uri.path):continue
        published=post.findtext("{http://www.w3.org/2005/Atom}published") or post.findtext("{http://www.w3.org/2005/Atom}updated")
        try:stamp=datetime.fromisoformat(str(published).replace("Z","+00:00")).astimezone(TZ)
        except (TypeError,ValueError):continue
        if stamp>now+timedelta(minutes=5) or stamp<now-timedelta(hours=FRESH_NEWS_HOURS):continue
        output.append({"id":"news-ptt-"+hashlib.sha256(url.encode()).hexdigest()[:16],
          "type":"news","category":"PTT轉載","title":title,"date":stamp.strftime("%Y-%m-%d"),
          "publishedAt":stamp.isoformat(timespec="seconds"),
          "source":"PTT 股票板（新聞轉載）","url":url,"themes":["PTT","台股"],
          "confirmed":False,"originType":"forum_repost"})
    return output

def fetch_ptt_stock_news():
    req=urllib.request.Request(PTT_ATOM,headers={"User-Agent":UA,"Accept":"application/atom+xml,application/xml"})
    with urllib.request.urlopen(req,timeout=14) as response:raw=response.read(900_000)
    return parse_ptt_stock_news(raw)

def build(now=None,feeds=None,prior=None):
    now=now or datetime.now(TZ)
    stats={"success":0,"total":len(QUERIES)+(1 if feeds is None else 0)}
    found=[]
    if feeds is None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futures=[pool.submit(fetch_feed,q) for q in QUERIES]
            futures.append(pool.submit(fetch_ptt_stock_news))
            for future in concurrent.futures.as_completed(futures):
                try:found.extend(future.result());stats["success"]+=1
                except Exception as exc:print("FEED_UNAVAILABLE",str(exc)[:180],file=sys.stderr)
    else:
        for batch in feeds:
            if batch is not None:found.extend(batch);stats["success"]+=1
    dedup={}
    for item in found:
        if item["id"] not in dedup or dedup[item["id"]]["publishedAt"]<item["publishedAt"]:
            dedup[item["id"]]=item
    if not stats["success"] and isinstance(prior,dict):
        # Explicit degraded status. Keep attribution and publication times; no fake new news.
        for item in prior.get("items",[]):
            if item.get("type")!="news":continue
            try:t=datetime.fromisoformat(item["publishedAt"])
            except (KeyError,ValueError,TypeError):continue
            if timedelta(0)<=now-t<=timedelta(hours=FRESH_NEWS_HOURS):
                dedup[item["id"]]=item
    ranked=sorted(dedup.values(),key=lambda x:x["publishedAt"],reverse=True)
    counts={};news=[]
    for item in ranked:
        category=item["category"]
        if counts.get(category,0)>=6:continue
        news.append(item);counts[category]=counts.get(category,0)+1
        if len(news)>=48:break
    events=[dict(e) for e in OFFICIAL if
      now.date()-timedelta(days=2)<=datetime.fromisoformat(e["endDate"]).date() and
      datetime.fromisoformat(e["date"]).date()<=now.date()+timedelta(days=60)]
    state="ok" if stats["success"]==stats["total"] else "partial" if stats["success"] else "degraded"
    # A green job with zero fresh articles must never masquerade as live news.
    if not news and stats["success"]:state="empty" if stats["success"]==stats["total"] else "partial"
    return {"schema":1,"generatedAt":now.isoformat(timespec="seconds"),
      "status":state,"feedsOk":stats["success"],"feedsTotal":stats["total"],
      "freshnessHours":FRESH_NEWS_HOURS,"newsCount":len(news),
      "newestNewsAt":news[0]["publishedAt"] if news else None,
      "items":sorted(events,key=lambda x:x["date"])+news}

def main():
    prior=None
    try:prior=json.loads(OUTPUT.read_text(encoding="utf-8"))
    except (OSError,ValueError):pass
    result=build(prior=prior)
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("MARKET_EVENTS",result["status"],result["feedsOk"],"/",result["feedsTotal"],"items",len(result["items"]))
if __name__=="__main__":main()
