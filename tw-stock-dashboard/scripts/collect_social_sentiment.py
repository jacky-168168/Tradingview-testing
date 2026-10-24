#!/usr/bin/env python3
"""Read-only public social sentiment collector. Fails closed; no invented discussion counts."""
from __future__ import annotations
import datetime as dt
import html
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
PTT_URL = "https://www.ptt.cc/atom/stock.xml"
PTT_FEEDS = (PTT_URL, "https://www.ptt.cc/atom/Stock.xml")
PTT_BOARD = "https://www.ptt.cc/bbs/Stock/index.html"
STOCK_PATH = ROOT / "data/latest.json"
NEWS_PATH = ROOT / "data/market_events/latest.json"
OUT_PATH = ROOT / "data/social_sentiment/latest.json"
UP = ("看多", "多頭", "轉強", "突破", "創高", "噴出", "漲停", "軋空", "強勢", "反攻", "上攻", "拉升", "飆漲")
DOWN = ("看空", "空頭", "轉弱", "破底", "崩盤", "暴跌", "跌停", "套牢", "利空", "出貨", "殺盤", "跳水", "重挫", "賣壓")
IGNORE = re.compile(r"^\s*(?:Re:|Fw:|\[公告\]|\[版務\])", re.I)
REPOST = re.compile(r"^\s*(?:\[新聞\]|【新聞】|\[轉錄\]|\[情報\])", re.I)
UNCERTAIN = re.compile(r"反指標|反串|諷刺|笑死|真的嗎|求救|已讀不回|韭菜|崩到起飛")
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
    if REPOST.search(text) or UNCERTAIN.search(text):
        return "中立／難判"
    up, down = any(s in text for s in UP), any(s in text for s in DOWN)
    return "偏多" if up and not down else "偏空" if down and not up else "中立／難判"

def request(url, token=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {"www.ptt.cc", "graph.threads.net", "graph.facebook.com"}:
        raise ValueError("拒絕非白名單 HTTPS 來源")
    h = {"User-Agent": "Tradingview-testing-SocialResearch/1.0", "Accept": "application/atom+xml, text/html;q=0.9, application/json;q=0.8"}
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
            "stance":score(title), "contentType":"新聞轉載" if REPOST.search(title) else "公開討論",
            "tone":"語意不明／疑似反諷" if UNCERTAIN.search(title) else "未驗證", "method":"標題規則（非留言全文）"}

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


def ptt_board(html_bytes, now):
    """HTML emergency fallback: extract public board links; post-ID time is an estimate, never official publishedAt."""
    body=html_bytes.decode("utf-8","replace") if isinstance(html_bytes,bytes) else str(html_bytes)
    out=[]
    for block in re.findall(r'<div\b[^>]*class=["\'][^"\']*\btitle\b[^"\']*["\'][^>]*>(.*?)</div>',body,re.I|re.S):
        a=re.search(r'<a\b[^>]*href=["\'](/bbs/Stock/M\.(\d{9,11})\.[^"\']+\.html)["\'][^>]*>(.*?)</a>',block,re.I|re.S)
        if not a:continue
        title=html.unescape(re.sub(r"<[^>]+>","",a.group(3))).strip()
        if IGNORE.search(title):continue
        try:published=dt.datetime.fromtimestamp(int(a.group(2)),tz=UTC).isoformat()
        except (ValueError,OverflowError,OSError):continue
        row=sanitize("PTT",title,"https://www.ptt.cc"+html.unescape(a.group(1)),published,now)
        if row:
            row["timestampBasis"]="文章網址 ID 推算，非官方發文時間"
            out.append(row)
    return out

def collect_ptt(now,fetch):
    failures=[]
    for url in PTT_FEEDS:
        try:
            rows=ptt(fetch(url),now)
            if rows:
                return rows,{"status":"ok","method":"官方 Atom","url":url,"freshCount":len(rows),"timestampBasis":"Atom 發布時間"}
            failures.append("Atom 無48小時有效貼文")
        except Exception as exc:
            failures.append(type(exc).__name__)
    try:
        rows=ptt_board(fetch(PTT_BOARD),now)
        if rows:
            return rows,{"status":"ok","method":"公開看板 HTML 備援","url":PTT_BOARD,
                         "freshCount":len(rows),"timestampBasis":"網址時間戳推算，僅供研究"}
        failures.append("HTML 無48小時有效貼文")
    except Exception as exc:
        failures.append(type(exc).__name__)
    return [],{"status":"error" if any(x not in {"Atom 無48小時有效貼文","HTML 無48小時有效貼文"} for x in failures) else "empty",
               "reason":"；".join(failures)[:160],"url":PTT_URL,"freshCount":0}

def stock_catalog():
    try:
        data=json.loads(STOCK_PATH.read_text("utf-8"))
        rows=data.get("models",{}).get("G",[])
        found=[]
        for r in rows[:20]:
            code=str(r.get("code",""))
            name=str(r.get("name","")).strip()
            if not re.fullmatch(r"\d{4}",code) or not 2<=len(name)<=15:continue
            found.append({"code":code,"name":name,"theme":str(r.get("theme",""))[:160],
                          "ret20":r.get("ret20"),"rvol":r.get("rvol"),"ma20Slope":r.get("ma20Slope")})
        return str(data.get("dataDate","")),found
    except (OSError,ValueError,TypeError,AttributeError):
        return "",[]

def mentions_stock(title,row):
    code=row["code"];name=row["name"]
    return bool(re.search(r"(?<!\d)"+re.escape(code)+r"(?!\d)",title) or name in title)

def topic_heat(items,now,catalog):
    date,stocks=catalog
    result=[]
    for r in stocks:
        hit=[x for x in items if mentions_stock(x["title"],r)]
        if not hit:continue
        current=sum(0 <= (now-iso(x["publishedAt"])).total_seconds()<=86400 for x in hit)
        previous=sum(86400 < (now-iso(x["publishedAt"])).total_seconds()<=172800 for x in hit)
        organic=sum(x.get("contentType")!="新聞轉載" for x in hit)
        extended=(isinstance(r["ret20"],(int,float)) and r["ret20"]>=25 and
                 ((isinstance(r["rvol"],(int,float)) and r["rvol"]>=2) or
                  (isinstance(r["ma20Slope"],(int,float)) and r["ma20Slope"]>=5)))
        result.append({"code":r["code"],"name":r["name"],"theme":r["theme"],"sample":len(hit),
                       "recent24h":current,"prior24h":previous,"originalDiscussion":organic,
                       "overheatWatch":bool(current>=3 and organic>=3 and extended),
                       "links":[{"title":x["title"],"url":x["url"],"platform":x["platform"]} for x in hit[:3]]})
    result.sort(key=lambda x:(-x["recent24h"],-x["sample"],x["code"]))
    return {"sourceDate":date,"stocks":result[:10],
            "method":"僅 G 前20名、文章標題完全對上股票代號或公司名稱；無命中不列榜。至少3篇非新聞轉載且價量延伸才顯示過熱觀察，不代表買賣訊號"}

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
    cached=[]
    for x in prior:
        if not isinstance(x,dict) or x.get("platform") not in ("PTT","Threads","Instagram"):continue
        row=sanitize(x.get("platform"),x.get("title"),x.get("url"),x.get("publishedAt"),now)
        if row:
            if x.get("timestampBasis")=="文章網址 ID 推算，非官方發文時間":
                row["timestampBasis"]=x["timestampBasis"]
            cached.append(row)
    prior=cached
    inputs=[]
    state={}
    new,state["PTT"]=collect_ptt(now,fetch)
    inputs+=new
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
    social_stats["originalDiscussion"]=sum(x.get("contentType")!="新聞轉載" for x in social)
    social_stats["repostedNews"]=len(social)-social_stats["originalDiscussion"]
    news_stats=statistics(news)
    heat=topic_heat(social[:80],now,stock_catalog())
    return {"schema":1,"generatedAt":now.isoformat().replace("+00:00","Z"),
        "sources":state,"social":social_stats,"news":news_stats,"stockHeat":heat,
        "items":social[:80],"newsItems":news[:30],
        "notes":["僅使用公開、實際取得且不超過48小時的資料；缺乏授權的平台顯示未授權。",
                 "標題關鍵詞易受反諷、轉載、選擇偏差與機器人影響；不能視為代表性民調。",
                 "新聞與社群分開計數；標題反諷／轉載不直接判定多空，無讀取留言全文。",
                 "個股熱度只是對 G Top20 的實際可驗證標題對照，不更改 G 排名或 TITAN 風控。"]}

def main():
    old={}
    if OUT_PATH.exists():
        try:
            old=json.loads(OUT_PATH.read_text("utf-8"))
        except (ValueError,OSError):
            pass
    report=collect(old=old)
    # Missing public feeds are published as explicit unavailable status, never fabricated neutral evidence.
    OUT_PATH.parent.mkdir(parents=True,exist_ok=True)
    OUT_PATH.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n","utf-8")
    print("SOCIAL_SENTIMENT",json.dumps({"social":report["social"],"sources":report["sources"]},ensure_ascii=False))

if __name__=="__main__":
    main()
