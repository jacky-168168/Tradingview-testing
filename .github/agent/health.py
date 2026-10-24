"""Deterministic read-only diagnosis of G and market-news publishing.

No trading, no repository writes, no LLM. Dependency-free on purpose.
Issue deduplication lives in issue_reporter.py.
"""
from __future__ import annotations
import base64,json,os,re,sys
from datetime import datetime,time,timedelta,timezone
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo

TZ=ZoneInfo("Asia/Taipei")
API="https://api.github.com/repos/jacky-168168/Tradingview-testing"
PAGES="https://jacky-168168.github.io/Tradingview-testing"
CLOSED_2026=set("01-01 02-12 02-13 02-16 02-17 02-18 02-19 02-20 02-27 04-03 04-06 05-01 06-19 09-25 09-28 10-09 10-26 12-25".split())
WORKFLOWS={
 "dashboard":"tw-stock-dashboard.yml",
 "monitor":"g-intraday-health.yml",
 "recovery":"g-intraday-recovery-clock.yml",
 "news":"market-major-events.yml",
}
G_PATH="tw-stock-dashboard/docs/data/g_intraday"
NEWS_PATH="tw-stock-dashboard/docs/data/market_events/latest.json"

def parse(value):
    try:
        x=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        return x if x.tzinfo else None
    except (TypeError,ValueError):return None

def g_session(now):
    tw=now.astimezone(TZ)
    return (tw.weekday()<5 and
            not(tw.year==2026 and tw.strftime("%m-%d") in CLOSED_2026) and
            time(9,50)<=tw.time()<time(13,45))

def incident(kind, detail, **metrics):
    return {"kind":kind,"detail":detail,**metrics}

def age_min(now,stamp):
    t=parse(stamp)
    return (now-t).total_seconds()/60 if t else None

def recent_run(now,runs,minutes):
    return [r for r in (runs or []) if (t:=parse(r.get("created_at"))) and
            0<=(now-t).total_seconds()<=minutes*60]

def valid_code(row):
    return isinstance(row,dict) and bool(re.fullmatch(r"[0-9]{4}",str(row.get("code",""))))

def evaluate_g(now,latest,status,dashboard,monitor,recovery,pages=None):
    """Return anomalies only inside an actual TW trading session."""
    if not g_session(now):return []
    latest=latest if isinstance(latest,dict) else {}
    status=status if isinstance(status,dict) else {}
    errors=[];today=now.astimezone(TZ).date().isoformat()
    published=parse(latest.get("publishedAt"))
    age=age_min(now,latest.get("publishedAt"))
    rows=latest.get("rows")
    if latest.get("asOfDate")!=today or latest.get("quality")!="intraday-provisional-allmarket" or not(isinstance(rows,list) and 1<=len(rows)<=20 and all(map(valid_code,rows))):
        errors.append(incident("stale-g","今日榜單日期、品質標籤或股票格式不正確",publishedAt=latest.get("publishedAt"),rows=len(rows) if isinstance(rows,list) else 0))
    if age is None or age<0 or age>65:
        errors.append(incident("stale-g","盤中榜單超過65分鐘未更新或具有未來時間戳",ageMinutes=round(age,1) if age is not None else None))
    try:
        c=latest["coverage"];valid=int(c["valid"]);total=int(c["total"])
        if total<1000 or valid<1000 or valid/total<.65:
            errors.append(incident("data-quality","全市場有效報價不足",valid=valid,total=total))
        for market in ("上市","上櫃"):
            v=c["exchange"][market];a=int(v["valid"]);b=int(v["total"])
            if b<1 or a/b<.60:errors.append(incident("data-quality",market+"有效報價涵蓋率不足",valid=a,total=b))
    except (KeyError,ValueError,TypeError,ZeroDivisionError):
        errors.append(incident("data-quality","coverage 結構缺失或無法解讀"))
    last=recent_run(now,dashboard,95)
    if not last:
        errors.append(incident("missing-schedule","最近95分鐘無 TW Stock Dashboard 執行紀錄"))
    elif all(r.get("conclusion")=="failure" for r in last):
        errors.append(incident("missing-schedule","最近95分鐘主更新均失敗",runs=len(last)))
    tw=now.astimezone(TZ)
    # Give monitor startup some slack at 09:50. A completed workflow_run is valid.
    if tw.time()>=time(10,25):
        mr=recent_run(now,monitor,40)
        if not mr or all(r.get("conclusion") in ("failure","cancelled") for r in mr):
            errors.append(incident("monitor-failed","G 健康監控器超過40分鐘未正常執行"))
        rr=recent_run(now,recovery,65)
        if not rr or all(r.get("conclusion") in ("failure","cancelled") for r in rr):
            errors.append(incident("monitor-failed","G 獨立備援時鐘超過65分鐘未正常執行"))
    checked=parse(status.get("checkedAt"))
    if status.get("asOfDate")==today and status.get("status")=="unavailable" and checked and (not published or checked>published):
        errors.append(incident("new-unavailable","最後失敗狀態比成功榜單更新",checkedAt=status.get("checkedAt"),message=str(status.get("message") or "")[:160]))
    if pages is not None and published and (now-published)>timedelta(minutes=25):
        page_date=parse(pages.get("publishedAt")) if isinstance(pages,dict) else None
        if not page_date or page_date<published:
            errors.append(incident("pages-lag","發布超過25分鐘，但 Pages 仍落後 main JSON",pagesPublishedAt=pages.get("publishedAt") if isinstance(pages,dict) else None))
    return errors

def evaluate_news(now,data,runs):
    data=data if isinstance(data,dict) else {}
    errors=[]
    age=age_min(now,data.get("generatedAt"))
    if age is None or age<0 or age>36*60:
        errors.append(incident("news-stale","新聞資料超過36小時未同步",ageMinutes=round(age) if age is not None else None))
    news=[x for x in data.get("items",[]) if isinstance(x,dict) and x.get("type")=="news"] if isinstance(data.get("items"),list) else []
    # An honestly empty recent window is not proof that news is stale.
    if news and not any((a:=age_min(now,x.get("publishedAt"))) is not None and 0<=a<=48*60 for x in news):
        errors.append(incident("news-stale","新聞列表沒有最近48小時內的文章"))
    if data.get("status") in ("degraded","initializing"):
        errors.append(incident("news-source","新聞來源全部不可用",status=data.get("status")))
    r=recent_run(now,runs,24*60)
    if not r:
        errors.append(incident("news-schedule","最近24小時無新聞更新工作流程紀錄"))
    elif len(r)>=2 and all(x.get("conclusion")=="failure" for x in r):
        errors.append(incident("news-schedule","最近新聞工作流程持續失敗"))
    return errors

def http_json(url,token=None):
    headers={"User-Agent":"tw-loop-harness/1.0","Accept":"application/vnd.github+json","Cache-Control":"no-cache"}
    if token:headers["Authorization"]="Bearer "+token
    with urlopen(Request(url,headers=headers),timeout=18) as response:
        return json.loads(response.read(3500000).decode("utf-8"))

def github_file(path,token=None):
    obj=http_json(API+"/contents/"+path+"?ref=main",token)
    return json.loads(base64.b64decode(obj["content"]).decode("utf-8"))

def workflow_runs(name,token=None):
    return http_json(API+"/actions/workflows/"+WORKFLOWS[name]+"/runs?per_page=30",token).get("workflow_runs",[])

def inspect(now=None,fetcher=None):
    now=now or datetime.now(timezone.utc)
    token=os.environ.get("GITHUB_TOKEN")
    fetcher=fetcher or {"json":lambda url:http_json(url,token), "file":lambda path:github_file(path,token),"runs":lambda name:workflow_runs(name,token)}
    results={"checkedAt":now.astimezone(TZ).isoformat(timespec="seconds"),"gSession":g_session(now),"incidents":[],"scopes":["news"]}
    # Do not make off-hours decisions or notifications about intraday G.
    if results["gSession"]:
        results["scopes"].append("g")
        try:
            latest=fetcher["file"](G_PATH+"/latest.json");status=fetcher["file"](G_PATH+"/status.json")
            all_runs={name:fetcher["runs"](name) for name in ("dashboard","monitor","recovery")}
            try:pages=fetcher["json"](PAGES+"/data/g_intraday/latest.json?nocache="+str(int(now.timestamp())))
            except Exception:pages=None
            results["incidents"]+=evaluate_g(now,latest,status,all_runs["dashboard"],all_runs["monitor"],all_runs["recovery"],pages)
            results["gLastPublishedAt"]=latest.get("publishedAt")
            results["gCoverage"]=latest.get("coverage")
        except Exception as exc:
            results["incidents"].append(incident("g-observation-error","G 巡檢資料或 Actions 無法讀取",error=type(exc).__name__))
    try:
        news=fetcher["file"](NEWS_PATH)
        results["incidents"]+=evaluate_news(now,news,fetcher["runs"]("news"))
        results["newsGeneratedAt"]=news.get("generatedAt")
        results["newsNewestAt"]=news.get("newestNewsAt")
    except Exception as exc:
        results["incidents"].append(incident("news-observation-error","新聞巡檢資料或 Actions 無法讀取",error=type(exc).__name__))
    return results

def main():
    result=inspect()
    destination=sys.argv[1] if len(sys.argv)>1 else "agent-health.json"
    with open(destination,"w",encoding="utf-8") as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print("LOOP_HEALTH",json.dumps({"checkedAt":result["checkedAt"],"session":result["gSession"],"incidents":[x["kind"] for x in result["incidents"]]},ensure_ascii=False))
if __name__=="__main__":main()
