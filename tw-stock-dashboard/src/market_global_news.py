"""Foreign-source international market catalyst headlines and conditional transmission notes.

Only attributable original foreign publishers / official institutions. News titles
are not independently fact-checked, and impact notes are scenarios, not price data.
"""
from __future__ import annotations
import hashlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Taipei")
FRESH_HOURS=48
UA="Mozilla/5.0 (compatible; MarketCatalystRadar/2.0)"
def google_rss(query):
    return "https://news.google.com/rss/search?"+urllib.parse.urlencode({
        "q":query+" when:2d","hl":"en-US","gl":"US","ceid":"US:en"
    })

# Google News is only the feed transport: <source url> must match the
# foreign original publisher. This prevents domestic rewrites entering the tab.
GLOBAL_FEEDS=[
 {"name":"Reuters 政治","source":"Reuters","site":"reuters.com","url":google_rss(
  "site:reuters.com (Trump OR tariffs OR election OR sanctions OR White House OR Congress)")},
 {"name":"Reuters 戰爭","source":"Reuters","site":"reuters.com","url":google_rss(
  "site:reuters.com (war OR military OR attack OR Iran OR Ukraine OR Taiwan Strait OR ceasefire)")},
 {"name":"Reuters 總經","source":"Reuters","site":"reuters.com","url":google_rss(
  "site:reuters.com (Federal Reserve OR inflation OR Treasury yields OR interest rates OR OPEC)")},
 {"name":"AP 國際政治","source":"Associated Press","site":"apnews.com","url":google_rss(
  "site:apnews.com (Trump OR election OR tariffs OR war OR sanctions OR Congress)")},
 {"name":"POLITICO 美國政策","source":"POLITICO","site":"politico.com","url":google_rss(
  "site:politico.com (White House OR Trump OR election OR tariff OR trade policy)")},
 {"name":"Financial Times","source":"Financial Times","site":"ft.com","url":google_rss(
  "site:ft.com (tariffs OR Federal Reserve OR inflation OR war OR oil OR sanctions)")},
 {"name":"BBC World","source":"BBC News","site":"bbc.com","url":"https://feeds.bbci.co.uk/news/world/rss.xml","direct":True},
 {"name":"Bloomberg Politics","source":"Bloomberg","site":"bloomberg.com","url":"https://feeds.bloomberg.com/politics/news.rss","direct":True},
 {"name":"WSJ World","source":"The Wall Street Journal","site":"wsj.com","url":"https://feeds.content.dowjones.io/public/rss/RSSWorldNews","direct":True},
 {"name":"Federal Reserve","source":"Federal Reserve","site":"federalreserve.gov","url":"https://www.federalreserve.gov/feeds/press_all.xml","direct":True}
]
WAR=re.compile(r"\b(war|warfare|airstrike|airstrikes|missile|missiles|invasion|invades?|bombing|military|attack|attacks|ceasefire|strikes?|conflict|iran|israel|ukraine|russia|nato|taiwan strait|strait of hormuz|red sea|hostilities)\b",re.I)
ELECTION=re.compile(r"\b(election|elections|midterm|midterms|vote|voting|ballot|polls|republicans?|democrats?|senate|congress|presidential race)\b",re.I)
US_CONTEXT=re.compile(r"\b(u\.?s\.?|america|american|trump|white house|congress|senate|republican|democrat|midterm|washington|president)\b",re.I)
POLICY=re.compile(r"\b(tariffs?|trade deal|trade war|sanctions?|export controls?|semiconductor ban|chip ban|executive order|trade policy|tax bill|tax cuts?|budget bill|debt ceiling|government shutdown|white house|industrial policy|regulation|regulatory|subsidy|subsidies)\b",re.I)
MACRO=re.compile(r"\b(fed|fomc|federal reserve|interest rates?|rate hikes?|rate cuts?|inflation|cpi|pce|jobs report|payrolls|unemployment|treasury yields?|bond yields?|central bank|recession|opec|oil prices?|crude prices?|dollar|ecb)\b",re.I)
STRONG=re.compile(r"\b(attack|attacks|airstrike|missile|invasion|bombing|sanctions|tariff|shutdown|emergency|strikes)\b",re.I)
NOT_STOCK_TIP=re.compile(r"\b(best stocks? to buy|stock picks?|price target|top [0-9]+ stocks?|buy now|investing tips?)\b",re.I)
LINKS={
 "地緣政治":("WTI 原油、黃金、S&P 500、台指期","若衝突影響能源運輸或風險偏好，可能牽動油價、避險資產與股指；方向須看衝突是否升級及市場反應。"),
 "美國選舉":("美股、美元、美債殖利率、台股科技","選舉結果可能改變稅收、財政與科技政策預期；需觀察實際政策及期貨反應。"),
 "國際政策":("美股、美元、半導體、台灣出口類股","關稅、制裁與出口管制可能影響供應鏈成本、需求及估值；要區分提案、通過與生效。"),
 "國際總經":("NASDAQ、美債殖利率、美元、黃金","利率、通膨及經濟數據可能透過折現率與資金流向影響市場；結果需與預期值比較。")
}
def classify(title):
    if WAR.search(title):return "地緣政治"
    if ELECTION.search(title) and US_CONTEXT.search(title):return "美國選舉"
    if POLICY.search(title):return "國際政策"
    if MACRO.search(title):return "國際總經"
    return None

def _host_ok(host,domain):
    host=(host or "").lower().rstrip(".")
    return host==domain or host.endswith("."+domain)

def parse_global_feed(raw,spec,now=None):
    """Validate Google publisher source URL, freshness, and market relevance."""
    now=now or datetime.now(TZ)
    root=ET.fromstring(raw)
    entries=root.findall(".//channel/item")
    if not entries:
        entries=root.findall("{http://www.w3.org/2005/Atom}entry")
    result=[]
    for el in entries[:60]:
        atom=el.tag.endswith("}entry")
        ns="{http://www.w3.org/2005/Atom}"
        title=" ".join((el.findtext(ns+"title" if atom else "title") or "").split())
        if title.endswith(" - "+spec["source"]):title=title[:-(len(spec["source"])+3)]
        category=classify(title)
        if not category or len(title)<15 or len(title)>240 or NOT_STOCK_TIP.search(title):continue
        link=el.findtext("link") or ""
        if atom:
            link=next((x.get("href","") for x in el.findall(ns+"link") if x.get("href")),"")
        if not link.startswith("https://"):continue
        if not spec.get("direct"):
            source_el=el.find("source")
            if source_el is None or not _host_ok(
                urllib.parse.urlsplit(source_el.get("url","")).hostname,spec["site"]):
                continue
        stamp=el.findtext(ns+"updated" if atom else "pubDate") or el.findtext(ns+"published" if atom else "dc:date",default="")
        try:
            t=(datetime.fromisoformat(stamp.replace("Z","+00:00")) if atom
               else parsedate_to_datetime(stamp)).astimezone(TZ)
        except (ValueError,TypeError,OverflowError):continue
        if t>now+timedelta(minutes=5) or t<now-timedelta(hours=FRESH_HOURS):continue
        assets,reason=LINKS[category]
        key=re.sub(r"[^\w]","",title.casefold())
        result.append({
            "id":"global-"+hashlib.sha256((spec["source"]+key).encode()).hexdigest()[:16],
            "type":"news","category":category,"title":title,"source":spec["source"],
            "date":t.strftime("%Y-%m-%d"),"publishedAt":t.isoformat(timespec="seconds"),
            "url":link,"themes":[category,"國際新聞"],"confirmed":False,
            "originType":"foreign_original","impactAssets":assets,"impactNote":reason,
            "impactLevel":"高關注" if STRONG.search(title) else "持續觀察",
            "impactStatus":"可能連動・未驗證實際行情"
        })
    return result

def fetch_global_feed(spec):
    req=urllib.request.Request(spec["url"],headers={"User-Agent":UA,"Accept":"application/rss+xml, application/atom+xml, application/xml"})
    with urllib.request.urlopen(req,timeout=14) as response:
        raw=response.read(1_200_000)
    return parse_global_feed(raw,spec)
