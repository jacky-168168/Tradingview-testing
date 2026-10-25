#!/usr/bin/env python3
"""ORION Taiwan finance headline database. Licensed/public RSS metadata only.
No full articles or paywall access; partial-feed failure never invents coverage.
"""
from __future__ import annotations
import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UTC=dt.timezone.utc
TPE=dt.timezone(dt.timedelta(hours=8))
DATA=Path(__file__).resolve().parents[1]/"docs/data"
ROOT=DATA/"orion_news"
OUT=ROOT/"latest.json"
ARCHIVE=ROOT/"history"
FEEDS=(
 ("中央通訊社","產經證券","https://feeds.feedburner.com/rsscna/finance",("www.cna.com.tw","cna.com.tw")),
 ("中央通訊社","科技","https://feeds.feedburner.com/rsscna/technology",("www.cna.com.tw","cna.com.tw")),
 ("自由時報","財經","https://news.ltn.com.tw/rss/business.xml",("ec.ltn.com.tw","news.ltn.com.tw")),
 ("ETtoday","財經","https://feeds.feedburner.com/ettoday/finance",("finance.ettoday.net","www.ettoday.net")),
 ("Yahoo股市","台股","https://tw.stock.yahoo.com/rss?category=tw-market",("tw.stock.yahoo.com","tw.finance.yahoo.com","tw.news.yahoo.com")),
 ("Yahoo股市","國際財經","https://tw.stock.yahoo.com/rss?category=intl-markets",("tw.stock.yahoo.com","tw.finance.yahoo.com","tw.news.yahoo.com")),
)
AT="{http://www.w3.org/2005/Atom}"
FINANCE=re.compile(r"台股|臺股|台指|加權|上櫃|股市|股票|股價|股息|基金|股利|期貨|金融|央行|利率|匯率|美元|債券|科技|晶片|半導體|台積電|AI|ETF|景氣|GDP|就業|經濟|通膨|關稅|營收|獲利|財報|法說|銀行|投資|能源|油價|黃金|外資|投信|上市|全球市場|美股|美債",re.I)
THEMES=(
 ("AI／半導體",r"台積電|半導體|AI|晶片|CPO|輝達|英偉達|封裝|光通訊|IC設計|記憶體|PCB"),
 ("資金／法人",r"外資|投信|自營商|買超|賣超|融資|融券|三大法人|成交額|籌碼"),
 ("總體／利率",r"央行|Fed|聯準會|降息|升息|通膨|CPI|GDP|就業|景氣|匯率|美元|債券"),
 ("能源／原物料",r"原油|油價|天然氣|黃金|白銀|金價|能源|銅價"),
 ("政策／地緣",r"關稅|川普|貿易戰|選舉|制裁|戰爭|禁令|政策"),
 ("ETF／投資",r"ETF|正二|反一|0050|00631L|00675L|殖利率|配息"),
 ("台股／行情",r"台股|臺股|加權|股價|股市|台指|期貨|漲停|跌停|大盤"),
)
BULLISH=re.compile(r"利多|大漲|飆漲|創高|買超|上攻|反彈|獲利成長|成長強勁|訂單大增|上修|轉盈")
BEARISH=re.compile(r"利空|重挫|暴跌|跌停|創低|賣超|衰退|下修|萎縮|恐慌|砍單|獲利下滑|轉虧")
def parse_date(value):
    try:
        x=dt.datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if x.tzinfo:return x.astimezone(UTC)
    except (TypeError,ValueError):pass
    try:
        x=email.utils.parsedate_to_datetime(str(value))
        if x.tzinfo:return x.astimezone(UTC)
    except (TypeError,ValueError,IndexError):pass
    return None

def clean_title(value):
    t=html.unescape(re.sub(r"<[^>]+>","",str(value or "")))
    return re.sub(r"\s+"," ",t).strip()[:145]

def request_feed(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme!="https" or u.hostname not in {"feeds.feedburner.com","news.ltn.com.tw","tw.stock.yahoo.com"}:
        raise ValueError("RSS 來源未在白名單")
    r=urllib.request.Request(url,headers={"User-Agent":"LUNA-ORION-Research-RSS/1.0",
        "Accept":"application/rss+xml,application/atom+xml,application/xml;q=0.9"})
    with urllib.request.urlopen(r,timeout=18) as stream:return stream.read(1_500_000)

def parse_feed(contents,name,section,hosts,now):
    root=ET.fromstring(contents);kind=root.tag.rsplit("}",1)[-1].lower()
    rows=[]
    entries=root.findall("./channel/item") if kind=="rss" else root.findall(AT+"entry")
    if not entries:raise ValueError("RSS／Atom 沒有可解析的項目")
    for x in entries[:100]:
        title=clean_title(x.findtext("title") or x.findtext(AT+"title"))
        link=x.findtext("link") or ""
        if not link:
            link=next((z.get("href") for z in x.findall(AT+"link") if z.get("href")),"")
        u=urllib.parse.urlsplit(str(link).strip())
        if u.scheme!="https" or u.hostname not in hosts or not 5<=len(title)<=145:continue
        when=parse_date(x.findtext("pubDate") or x.findtext("published") or x.findtext(AT+"published")
            or x.findtext(AT+"updated") or x.findtext("{http://purl.org/dc/elements/1.1/}date"))
        if when is None or not -60<=(now-when).total_seconds()<=48*3600:continue
        if not FINANCE.search(title):continue
        themes=[label for label,pattern in THEMES if re.search(pattern,title,re.I)]
        tone="偏多" if BULLISH.search(title) and not BEARISH.search(title) else \
            "偏空" if BEARISH.search(title) and not BULLISH.search(title) else "中立／待判"
        rows.append({"title":title,"url":str(link)[:400],
            "publishedAt":when.isoformat().replace("+00:00","Z"),
            "source":name,"channel":section,"themes":themes[:4],
            "headlineRuleTone":tone,
            "method":"來源網站的公開 RSS 標題；關鍵詞初判，不代表股價方向"})
    return rows

def old_market_events(now):
    path=DATA/"market_events/latest.json"
    try:
        data=json.loads(path.read_text("utf-8"))
        created=parse_date(data.get("generatedAt"))
        if not created or not 0<=(now-created).total_seconds()<=36*3600:return []
        rows=[]
        for x in data.get("items",[]):
            if not isinstance(x,dict) or x.get("type")!="news":continue
            when=parse_date(x.get("publishedAt"))
            title=clean_title(x.get("title"))
            u=urllib.parse.urlsplit(str(x.get("url") or ""))
            if not when or not 0<=(now-when).total_seconds()<=48*3600:continue
            if u.scheme!="https" or not u.netloc or not FINANCE.search(title):continue
            rows.append({"title":title,"url":str(x["url"])[:400],
             "publishedAt":when.isoformat().replace("+00:00","Z"),
             "source":str(x.get("source") or "既有財經新聞")[:55],
             "channel":"既有系統新聞","themes":[str(t)[:35] for t in x.get("themes",[]) if isinstance(t,str)][:4],
             "headlineRuleTone":"中立／待判",
             "method":"既有市場事件 JSON 標題，僅作第二來源，無即時全文"})
        return rows
    except (OSError,ValueError,TypeError):return []

def article_key(p):return hashlib.sha256((p["source"]+"\0"+p["url"]).encode()).hexdigest()[:20]
def headline_fingerprint(title):
    """Conservative event grouping for identical or near-identical headlines."""
    return re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+","",str(title)).lower()

def similar_headlines(a,b):
    a=headline_fingerprint(a);b=headline_fingerprint(b)
    if a==b:return True
    if len(a)<12 or len(b)<12 or min(len(a),len(b))/max(len(a),len(b))<0.72:return False
    # Do not merge different percentages, prices, dates or corporate figures.
    if sorted(re.findall(r"\d+",a))!=sorted(re.findall(r"\d+",b)):return False
    aa={a[i:i+2] for i in range(len(a)-1)}
    bb={b[i:i+2] for i in range(len(b)-1)}
    return len(aa&bb)/max(1,len(aa|bb))>=0.82

def mark_events(items):
    """Assign comparable-event groups without dropping articles or pretending semantic equivalence."""
    leaders=[];counts={}
    for item in items:
        date=parse_date(item.get("publishedAt"))
        group=None
        for first in leaders:
            earlier=parse_date(first.get("publishedAt"))
            if date and earlier and abs((date-earlier).total_seconds())<=24*3600 and similar_headlines(item["title"],first["title"]):
                group=first["eventGroup"];break
        if not group:
            group=item["id"]
            leaders.append(item)
        item["eventGroup"]=group
        counts[group]=counts.get(group,0)+1
    return {"articleCount":len(items),"eventCount":len(counts),
        "repostedOrSimilar":len(items)-len(counts),
        "method":"僅用高相似度標題與24小時內日期保守合併同一事件；不同敘事可能仍屬同一事件，不做未證實的語意合併"}

def unique_articles(rows,limit=180):
    seen=set();items=[]
    for x in sorted(rows,key=lambda y:y["publishedAt"],reverse=True):
        k=x["url"].split("#",1)[0].split("?",1)[0]
        if k in seen:continue
        seen.add(k);x["id"]=article_key(x)
        x["headlineGroup"]=hashlib.sha256(re.sub(r"[\W_]+","",x["title"]).encode()).hexdigest()[:14]
        items.append(x)
        if len(items)>=limit:break
    return items

def collect(now=None,fetch=request_feed,previous=None):
    now=now or dt.datetime.now(UTC)
    inputs=[];state={}
    for name,section,url,hosts in FEEDS:
        key=name+"／"+section
        try:
            rows=parse_feed(fetch(url),name,section,hosts,now)
            state[key]={"status":"ok" if rows else "empty","freshCount":len(rows),"feed":url}
            inputs.extend(rows)
        except Exception as exc:
            state[key]={"status":"error","freshCount":0,"error":type(exc).__name__,"feed":url}
    fallback=old_market_events(now)
    state["既有市場新聞"]={"status":"ok" if fallback else "empty","freshCount":len(fallback)}
    inputs+=fallback
    items=unique_articles(inputs)
    events=mark_events(items)
    if not items and isinstance(previous,dict):
        # Failure remains explicitly visible; old data is never called fresh and never used for today's tone.
        state["history"]={"status":"no_fresh_articles","note":"可在歷史日檔查詢舊報導；不可當今天的新消息"}
    counts={k:sum(x["headlineRuleTone"]==k for x in items) for k in ("偏多","偏空","中立／待判")}
    themes={}
    for x in items:
        for t in x["themes"]:themes[t]=themes.get(t,0)+1
    return {"schema":1,"generatedAt":now.isoformat().replace("+00:00","Z"),
      "coverage":{"configuredFeeds":len(FEEDS),
        "healthyFeeds":sum(v["status"] in ("ok","empty") for k,v in state.items() if k!="既有市場新聞" and k!="history"),
        "sources":state,"allTaiwanMediaCovered":False},
      "items":items,"eventSummary":events,"ruleTone":counts,
      "themes":[{"name":k,"count":v} for k,v in sorted(themes.items(),key=lambda v:-v[1])[:9]],
      "method":"跨媒體公開 RSS 標題＋既有市場新聞；只儲存標題、來源、發稿時間與原文連結。分類是報導語氣，不等於讀者情緒或股票績效；不宣稱涵蓋台灣所有媒體。"}

def archive(report,now=None,old=None):
    now=now or dt.datetime.now(UTC)
    day=now.astimezone(TPE).date().isoformat()
    old=old if isinstance(old,dict) and old.get("day")==day else {}
    entries={x["id"]:x for x in old.get("items",[]) if isinstance(x,dict) and x.get("id")}
    for p in report.get("items",[]):
        q=dict(p);q["firstSeenAt"]=entries.get(q["id"],{}).get("firstSeenAt",report["generatedAt"])
        q["lastSeenAt"]=report["generatedAt"]
        entries[q["id"]]=q
    items=sorted(entries.values(),key=lambda x:x["publishedAt"],reverse=True)[:350]
    return {"schema":1,"day":day,"updatedAt":report["generatedAt"],
      "items":items,"runs":(old.get("runs") or [])[-11:]+[
       {"generatedAt":report["generatedAt"],"articles":len(report.get("items",[])),
        "healthyFeeds":report["coverage"]["healthyFeeds"]}]}

def save_index(report,snapshot,now=None):
    now=now or dt.datetime.now(UTC)
    index_path=ARCHIVE/"index.json"
    index=read(index_path,{})
    days={x["day"]:x for x in index.get("days",[]) if isinstance(x,dict) and x.get("day")}
    summaries=report.get("semantic",{})
    days[snapshot["day"]]={"day":snapshot["day"],"path":snapshot["day"]+".json",
      "observedHeadlines":len(snapshot["items"]),"latestArticles":len(report["items"]),
      "healthyFeeds":report["coverage"]["healthyFeeds"],
      "semanticStatus":summaries.get("status","not_run"),"classified":summaries.get("classified",0),
      "distinctEventsClassified":summaries.get("distinctEventsClassified",0),
      "eventCount":report.get("eventSummary",{}).get("eventCount",0),
      "coveragePct":summaries.get("coveragePct",0),
      "positive":summaries.get("positive",0),"negative":summaries.get("negative",0),
      "neutral":summaries.get("neutral",0)}
    today=now.astimezone(TPE).date()
    retained=sorted([x for x in days.values() if 0<=(today-dt.date.fromisoformat(x["day"])).days<30],
                    key=lambda x:x["day"],reverse=True)
    write(index_path,{"schema":1,"updatedAt":report["generatedAt"],
      "retentionDays":30,"days":retained,
      "note":"每天的公開標題與歷史發現紀錄；工作樹 30 日保留，不代表 Git 歷史永久刪除。"})
    for p in ARCHIVE.glob("????-??-??.json"):
        try:
            if (today-dt.date.fromisoformat(p.stem)).days>=30:p.unlink()
        except ValueError:continue

def read(p,default):
    try:return json.loads(p.read_text("utf-8"))
    except (OSError,ValueError,TypeError):return default
def write(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_suffix(p.suffix+".tmp");tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n","utf-8")
    tmp.replace(p)

def main():
    now=dt.datetime.now(UTC);old=read(OUT,{})
    report=collect(now,previous=old)
    write(OUT,report)
    print("ORION_NEWS_COLLECTED",json.dumps({"count":len(report["items"]),
      "feeds":{k:v["status"] for k,v in report["coverage"]["sources"].items()}},ensure_ascii=False))
if __name__=="__main__":main()
