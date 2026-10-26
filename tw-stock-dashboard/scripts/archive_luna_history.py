#!/usr/bin/env python3
"""Daily transparent research snapshots, using repository JSON files as a small append/update database.
No private accounts, authors, cookies, or full comments. Retains at most 30 days of files in working tree.
Git history may preserve older public snapshots: this is not a legal deletion guarantee.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
UTC=dt.timezone.utc
TPE=dt.timezone(dt.timedelta(hours=8))
ROOT=Path(__file__).resolve().parents[1]/"docs/data/social_sentiment"
LATEST=ROOT/"latest.json"
HISTORY=ROOT/"history"
INDEX=HISTORY/"index.json"
def read(path,default):
    try:return json.loads(path.read_text("utf-8"))
    except (OSError,ValueError,TypeError):return default
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n","utf-8")
    temporary.replace(path)
def archive(latest,older=None,now=None):
    now=now or dt.datetime.now(UTC)
    if not isinstance(latest,dict) or latest.get("schema")!=1:raise ValueError("invalid LUNA report")
    generated=dt.datetime.fromisoformat(latest["generatedAt"].replace("Z","+00:00"))
    if generated.tzinfo is None or abs((generated-now).total_seconds())>3600:raise ValueError("stale/future archive report")
    today=now.astimezone(TPE).date().isoformat()
    old=older if isinstance(older,dict) else {}
    if old.get("day")!=today:old={}
    entries={x["url"]:x for x in old.get("records",[]) if isinstance(x,dict) and isinstance(x.get("url"),str)}
    for p in latest.get("items",[]):
        if not isinstance(p,dict) or p.get("platform") not in ("PTT","Bluesky","Threads","Instagram"):continue
        url=p.get("url")
        if not isinstance(url,str) or not url.startswith("https://"):continue
        original=entries.get(url,{})
        record={k:p[k] for k in ("platform","title","url","publishedAt","contentType","investmentEligible","stance") if k in p}
        if isinstance(p.get("semantic"),dict):
            record["semantic"]={k:v for k,v in p["semantic"].items() if k in ("model","intent","stance","emotion","confidence","evidence")}
        elif "semantic" in original:record["semantic"]=original["semantic"]
        record["firstObservedAt"]=original.get("firstObservedAt",latest["generatedAt"])
        record["lastObservedAt"]=latest["generatedAt"]
        entries[url]=record
    records=sorted(entries.values(),key=lambda x:x.get("lastObservedAt",""),reverse=True)[:300]
    runs=(old.get("runs") or [])[-23:]+[{"generatedAt":latest["generatedAt"],
      "rawSample":latest.get("social",{}).get("rawSample",0),
      "investmentSample":latest.get("social",{}).get("sample",0),
      "semanticStatus":latest.get("semantic",{}).get("status","not_run"),
      "sourceStatus":{k:v.get("status","unavailable") for k,v in latest.get("sources",{}).items() if isinstance(v,dict)}}]
    return {"schema":1,"day":today,"updatedAt":latest["generatedAt"],
      "records":records,"runs":runs,
      "notes":"含同日可核對的公開原文摘要、見到時間、來源狀態；不儲存留言全文／帳戶個資，不代表市場共識"}
def daily_summary(snapshot):
    run=snapshot["runs"][-1]
    posts=snapshot["records"]
    sem=[p for p in posts if isinstance(p.get("semantic"),dict) and p["semantic"].get("intent")=="投資意見"]
    count=lambda label:sum(x["semantic"].get("stance")==label for x in sem)
    return {"day":snapshot["day"],"path":snapshot["day"]+".json",
      "uniquePostsObserved":len(posts),"latestRawSample":run["rawSample"],
      "latestInvestmentSample":run["investmentSample"],
      "modelInterpreted":len(sem),"bull":count("偏多"),"bear":count("偏空"),
      "neutral":count("中立／難判"),"semanticStatus":run["semanticStatus"],
      "updatedAt":snapshot["updatedAt"],"sourceStatus":run["sourceStatus"]}
def run(now=None):
    now=now or dt.datetime.now(UTC)
    today=now.astimezone(TPE).date()
    latest=read(LATEST,{})
    path=HISTORY/(today.isoformat()+".json")
    result=archive(latest,read(path,{}),now)
    atomic(path,result)
    index=read(INDEX,{})
    byday={v["day"]:v for v in index.get("days",[]) if isinstance(v,dict) and isinstance(v.get("day"),str)}
    byday[result["day"]]=daily_summary(result)
    keep=[v for v in byday.values() if 0<=(today-dt.date.fromisoformat(v["day"])).days<30]
    keep.sort(key=lambda x:x["day"],reverse=True)
    atomic(INDEX,{"schema":1,"updatedAt":latest["generatedAt"],"retentionDays":30,"days":keep,
      "notes":"日期為台灣時間；樣本為每日最後一輪公開資料更新，非每日總流量；獨立日檔列示當日所有去重可核對貼文。"})
    for f in HISTORY.glob("????-??-??.json"):
        try:day=dt.date.fromisoformat(f.stem)
        except ValueError:continue
        if (today-day).days>=30 or (today-day).days<0:f.unlink()
    print("LUNA_HISTORY_ARCHIVED",json.dumps({"day":result["day"],"uniquePosts":len(result["records"]),
     "dailyRuns":len(result["runs"]),"indexDays":len(keep)},ensure_ascii=False))
if __name__=="__main__":run()
