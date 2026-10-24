#!/usr/bin/env python3
"""Read-only public social sentiment collector. Fails closed; no invented discussion counts."""
from __future__ import annotations
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

UTC = dt.timezone.utc
ROOT = Path(__file__).resolve().parents[1] / "docs"
PTT_URL = "https://www.ptt.cc/atom/Stock.xml"
NEWS_PATH = ROOT / "data/market_events/latest.json"
OUT_PATH = ROOT / "data/social_sentiment/latest.json"
UP = ("看多", "多頭", "轉強", "突破", "創高", "噴出", "漲停", "軋空", "強勢", "反攻", "上攻", "拉升", "飆漲")
DOWN = ("看空", "空頭", "轉弱", "破底", "崩盤", "暴跌", "跌停", "套牢", "利空", "出貨", "殺盤", "跳水", "重挫", "賣壓")
IGNORE = re.compile(r"^\s*(?:Re:|Fw:|\[公告\]|\[版務\])", re.I)
ATOM = "{http://www.w3.org/2005/Atom}"

def iso(value):
    if not value:
        return None
    try:
        obj = dt.datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        return obj.astimezone(UTC) if obj.tzinfo else None
    except (ValueError, TypeError):
        return None

def score(title):
    text = str(title)
    up, down = any(s in text for s in UP), any(s in text for s in DOWN)
    return "偏多" if up and not down else "偏空" if down and not up else "中立／難判"

def request(url, token=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.ptt.cc", "graph.threads.net", "graph.facebook.com"}:
        raise ValueError("拒絕非白名單 HTTPS 來源")
    h = {"User-Agent": "Tradingview-testing-SocialResearch/1.0", "Accept": "application/atom+xml, application/json;q=0.9"}
    if token:
        h["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=20) as r:
        return r.read(1_500_000)

def sanitize(source, title, url, date, now, max_hours=48):
    t = iso(date)
    if t is None or (now-t).total_seconds() < -60 or (now-t).total_seconds() > max_hours*3600:
        return None
    link = urllib.parse.urlsplit(str(url))
    allowed = {"PTT": {"www.ptt.cc"}, "Threads": {"www.threads.net", "threads.net", "www.threads.com", "threads.com"},
               "Instagram": {"www.instagram.com", "instagram.com"}, "新聞": None}
    if link.scheme != "https" or (allowed[source] is not None and link.hostname not in allowed[source]):
        return None
    if not link.netloc or len(str(title).strip()) < 4:
        return None
    title = re.sub(r"[\x00-\x1f]+", " ", str(title).strip())[:160]
    return {"platform":source, "title":title, "url":str(url)[:350], "publishedAt":t.isoformat().replace("+00:00", "Z"),
            "stance":score(title)}

def ptt(xml, now):
    root = ET.fromstring(xml)
    rows = []
    for entry in root.findall(ATOM+"entry"):
        title = (entry.findtext(ATOM+"title") or "").strip()
        if IGNORE.search(title):
            continue
        link = next((x.get("href") for x in entry.findall(ATOM+"link") if x.get("href")), "")
        item = sanitize("PTT", title, link, entry.findtext(ATOM+"published") or entry.findtext(ATOM+"updated"), now)
        if item:
            rows.append(item)
    return rows

def threads(token, now):
    queries = ["台股", "股票"]
    entries = []
    for q in queries:
        url = "https://graph.threads.net/v1.0/keyword_search?" + urllib.parse.urlencode({
            "q":q,"search_type":"RECENT","fields":"id,text,permalink,timestamp","limit":25})
        data = json.loads(request(url, token))
        if not isinstance(data.get("data"), list):
            raise ValueError("Threads 搜尋沒有有效 data")
        for row in data["data"]:
            entry = sanitize("Threads", row.get("text",""), row.get("permalink",""), row.get("timestamp"), now)
            if entry:
                entries.append(entry)
    return entries

def instagram(token, user_id, now):
    if not re.fullmatch(r"\d+",user_id):
        raise ValueError("Instagram user id 格式錯誤")
    entries=[]
    for tag in ["台股", "股票"]:
        base="https://graph.facebook.com/v24.0/"
        lookup=base+"ig_hashtag_search?"+urllib.parse.urlencode({"user_id":user_id,"q":tag})
        ids=json.loads(request(lookup,token)).get("data",[])
        for d in ids[:1]:
            hid=str(d.get("id",""))
            if not hid.isdigit():
                continue
            url=base+hid+"/recent_media?"+urllib.parse.urlencode({
                "user_id":user_id,"fields":"id,caption,permalink,timestamp","limit":25})
            result=json.loads(request(url,token))
            for row in result.get("data",[]):
                x=sanitize("Instagram",row.get("caption",""),row.get("permalink",""),row.get("timestamp"),now)
                if x:
                    entries.append(x)
    return entries

def news_items(now):
    if not NEWS_PATH.exists():
        return [], "新聞 JSON 缺失"
    try:
        data=json.loads(NEWS_PATH.read_text("utf-8"))
        generated=iso(data.get("generatedAt"))
        if not generated or not 0 <= (now-generated).total_seconds() <= 36*3600:
            return [], "新聞資料集過期或生成時間無效"
        out=[]
        for item in data.get("items",[]):
            if item.get("type") != "news":
                continue
            x=sanitize("新聞",item.get("title",""),item.get("url",""),item.get("publishedAt"),now)
            if x:
                out.append(x)
        return out, None
    except (OSError,ValueError,TypeError,KeyError):
        return [], "新聞 JSON 解析失敗"

def unique(rows, limit=120):
    seen=set()
    out=[]
    for x in sorted(rows,key=lambda e:e["publishedAt"],reverse=True):
        link=x["url"].split("?",1)[0]
        if link in seen:
            continue
        seen.add(link)
        out.append(x)
        if len(out)>=limit:
            break
    return out

def statistics(items):
    bull=sum(x["stance"]=="偏多" for x in items)
    bear=sum(x["stance"]=="偏空" for x in items)
    neutral=len(items)-bull-bear
    directional=bull+bear
    state=("尚無有效討論" if not items else
        "已有樣本｜偏多討論較多" if bull>bear else
        "已有樣本｜偏空討論較多" if bear>bull else
        "已有樣本｜尚無明確多空方向" if directional==0 else
        "已有樣本｜多空討論接近")
    return {"sample":len(items),"bull":bull,"bear":bear,"neutral":neutral,"directional":directional,
            "status":state,"method":"只要有一篇有效公開貼文就視為已有樣本；關鍵詞僅供觀察，篇數少不代表市場共識，也不是留言全文分析"}

def collect(now=None, fetch=request, old=None, environmental=None):
    now=now or dt.datetime.now(UTC)
    environmental=os.environ if environmental is None else environmental
    old=old or {}
    prior=old.get("items") if isinstance(old.get("items"),list) else []
    prior=[sanitize(x.get("platform"),x.get("title"),x.get("url"),x.get("publishedAt"),now)
           for x in prior if isinstance(x,dict) and x.get("platform") in ("PTT","Threads","Instagram")]
    prior=[x for x in prior if x is not None]
    inputs=[]
    state={}
    try:
        new=ptt(fetch(PTT_URL),now)
        state["PTT"]={"status":"ok" if new else "empty","freshCount":len(new),"url":PTT_URL}
        inputs+=new
    except (Exception,) as ex:
        state["PTT"]={"status":"error","reason":type(ex).__name__,"url":PTT_URL}
    for name, func, args in [
        ("Threads",threads,(environmental.get("THREADS_ACCESS_TOKEN"),now)),
        ("Instagram",instagram,(environmental.get("IG_ACCESS_TOKEN"),environmental.get("IG_USER_ID",""),now))]:
        configured=all(args[:-1])
        if not configured:
            state[name]={"status":"not_authorized","freshCount":0}
            continue
        try:
            new=func(*args)
            state[name]={"status":"ok" if new else "empty","freshCount":len(new)}
            inputs+=new
        except Exception as ex:
            state[name]={"status":"error","reason":type(ex).__name__,"freshCount":0}
    news,reason=news_items(now)
    state["新聞"]={"status":"ok" if news else "unavailable","freshCount":len(news)}
    if reason:
        state["新聞"]["reason"]=reason
    social=unique(inputs+prior)
    news=unique(news,80)
    social_stats=statistics(social)
    news_stats=statistics(news)
    return {"schema":1,"generatedAt":now.isoformat().replace("+00:00","Z"),
        "sources":state,"social":social_stats,"news":news_stats,
        "items":social[:80],"newsItems":news[:30],
        "notes":["僅使用公開、實際取得且不超過48小時的資料；缺乏授權的平台顯示未授權。",
                 "標題關鍵詞易受反諷、轉載、選擇偏差與機器人影響；不能視為代表性民調。",
                 "新聞與社群分開計數；絕不修改 G 排名或 TITAN 風控。"]}

def main():
    old={}
    if OUT_PATH.exists():
        try:
            old=json.loads(OUT_PATH.read_text("utf-8"))
        except (ValueError,OSError):
            pass
    report=collect(old=old)
    if report["sources"]["PTT"]["status"]=="error" and not report["items"]:
        raise SystemExit("PTT 抓取失敗且無有效歷史樣本，拒絕發布假情緒")
    OUT_PATH.parent.mkdir(parents=True,exist_ok=True)
    OUT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n","utf-8")
    print("SOCIAL_SENTIMENT",json.dumps({"social":report["social"],"sources":report["sources"]},ensure_ascii=False))

if __name__=="__main__":
    main()
