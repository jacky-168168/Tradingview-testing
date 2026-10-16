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
QUERIES=[
 ("財報","美國 科技巨頭 財報 財測 輝達 微軟 蘋果 Meta Google 亞馬遜 when:7d",r"財報|財測|法說|earnings|財季|業績|營收",["美國科技","AI","台積電供應鏈"]),
 ("展覽","PCB 電路板 半導體 AI 展覽 研討會 開幕 when:7d",r"展覽|展會|展期|研討會|登場|論壇|expo|show",["PCB","載板","半導體"]),
 ("報價","矽晶圓 漲價 報價 價格 調漲 when:7d",r"矽晶圓|wafer|晶圓報價",["矽晶圓","半導體材料"]),
 ("報價","被動元件 MLCC 電容 電阻 漲價 調漲 報價 when:7d",r"被動元件|MLCC|電容|電阻",["被動元件"]),
 ("報價","DRAM NAND HBM 記憶體 報價 漲價 when:7d",r"DRAM|NAND|HBM|記憶體",["記憶體","HBM"]),
 ("AI需求","AI 晶片 GPU 伺服器 需求 訂單 擴產 when:7d",r"AI|GPU|晶片|伺服器|算力",["AI伺服器","半導體"]),
 ("AI需求","CoWoS CPO 先進封裝 光通訊 訂單 需求 when:7d",r"CoWoS|CPO|光通訊|先進封裝",["先進封裝","CPO"]),
 ("財報","台積電 財報 法說 資本支出 產能 when:7d",r"台積電|TSMC|晶圓代工",["晶圓代工","半導體"]),
 ("總經","聯準會 FOMC 升息 降息 利率 決策 when:7d",r"聯準會|FOMC|Fed|央行|利率|降息|升息",["金融","科技股"]),
 ("原物料","國際 油價 OPEC 原油 供給 大漲 大跌 when:7d",r"油價|原油|OPEC|布蘭特|WTI",["塑化","航運","能源"]),
 ("原物料","黃金 金價 美元 殖利率 大跌 上漲 when:7d",r"黃金|金價|gold",["黃金","美元","利率"]),
 ("總經","美國 CPI PCE 非農 就業 通膨 數據 when:7d",r"CPI|PCE|非農|通膨|就業",["總經","利率"]),
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
PRIORITY=re.compile(r"漲價|調漲|上調|大漲|大跌|暴跌|暴增|飆升|缺貨|產能|擴產|突破|訂單|需求|財報|財測|FOMC|降息|升息|開幕|展覽|停產|限產|出口管制|guidance|earnings|surge|cuts",re.I)

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
        if t>now+timedelta(hours=2) or t<now-timedelta(days=7):continue
        if not re.search(matcher,title,re.I) or not PRIORITY.search(title):continue
        if len(title)<12 or len(title)>180:continue
        if not url.startswith("https://") or not source:continue
        if re.search(r"股價目標|目標價|買進評等|推薦股|明牌|飆股|哪檔|這[0-9一二三四五六七八九十]檔",title):continue
        key=re.sub(r"[^\w\u4e00-\u9fff]","",title.casefold())
        result.append({"id":"news-"+hashlib.sha256(key.encode()).hexdigest()[:16],
         "type":"news","category":category,"title":title,"date":t.strftime("%Y-%m-%d"),
         "publishedAt":t.isoformat(timespec="seconds"),"source":source[:50],"url":url,
         "themes":themes,"confirmed":False})
    return result

def build(now=None,feeds=None,prior=None):
    now=now or datetime.now(TZ)
    stats={"success":0,"total":len(QUERIES)}
    found=[]
    if feeds is None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            futures=[pool.submit(fetch_feed,q) for q in QUERIES]
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
            if now-t<timedelta(days=5) and t<=now:dedup[item["id"]]=item
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
    return {"schema":1,"generatedAt":now.isoformat(timespec="seconds"),
      "status":"ok" if stats["success"]==stats["total"] else "partial" if stats["success"] else "degraded",
      "feedsOk":stats["success"],"feedsTotal":stats["total"],
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
