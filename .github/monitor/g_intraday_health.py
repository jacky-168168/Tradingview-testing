"""G intraday independent watchdog. Standard library only; no trading signals are changed."""
from __future__ import annotations
import base64,json,os,sys
from datetime import datetime,timezone,time,timedelta
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
TZ=ZoneInfo("Asia/Taipei")
API="https://api.github.com/repos/jacky-168168/Tradingview-testing"
BASE="https://github.com/jacky-168168/Tradingview-testing"
PAGES="https://jacky-168168.github.io/Tradingview-testing/data/g_intraday/latest.json"
ISSUE="[G-INTRADAY-HEALTH] 盤中選股健康監控異常"
# Known TWSE 2026 exchange closures; update against official calendar for future years.
CLOSED_2026=set("01-01 02-12 02-13 02-16 02-17 02-18 02-19 02-20 02-27 04-03 04-06 05-01 06-19 09-25 09-28 10-09 10-26 12-25".split())
def parse(s):
    try:
        d=datetime.fromisoformat(str(s).replace("Z","+00:00"))
        return d if d.tzinfo else None
    except (TypeError,ValueError):return None
def session(now):
    n=now.astimezone(TZ)
    return n.weekday()<5 and not(n.year==2026 and n.strftime("%m-%d") in CLOSED_2026) and time(9,50)<=n.time()<time(13,45)
def assess(now,latest,status,runs,pages=None):
    latest=latest if isinstance(latest,dict) else {}
    status=status if isinstance(status,dict) else {}
    errors=[];today=now.astimezone(TZ).strftime("%Y-%m-%d")
    published=parse(latest.get("publishedAt"))
    age=(now-published).total_seconds()/60 if published else None
    if latest.get("asOfDate")!=today or latest.get("quality")!="intraday-provisional-allmarket":errors.append("今日盤中 G 快照缺失或品質標籤錯誤")
    if age is None or age<0 or age>65:errors.append("盤中榜單超過 65 分鐘未更新（目前距今 "+(str(round(age)) if age is not None else "未知")+" 分鐘）")
    rows=latest.get("rows")
    if not isinstance(rows,list) or not 1<=len(rows)<=20 or any(not isinstance(r,dict) or not str(r.get("code","")).strip() for r in rows):errors.append("盤中榜單空白或格式不合法")
    try:
        c=latest["coverage"];valid,total=int(c["valid"]),int(c["total"])
        if total<1800 or valid<1000 or valid/total<.65:errors.append(f"上市櫃全市場覆蓋率不足 {valid}/{total}")
        for market in ("上市","上櫃"):
            m=c["exchange"][market];a,b=int(m["valid"]),int(m["total"])
            if b<500 or a/b<.60:errors.append(f"{market}報價覆蓋率不足 {a}/{b}")
    except (KeyError,TypeError,ValueError,ZeroDivisionError):errors.append("有效報價覆蓋率缺失或格式錯誤")
    failure=parse(status.get("checkedAt"))
    if status.get("asOfDate")==today and status.get("status")=="unavailable" and failure and (not published or failure>published):
        errors.append("最新重選失敗："+str(status.get("message") or "不明原因")[:140])
    recent=[r for r in (runs or []) if r.get("name")=="TW Stock Dashboard" and (t:=parse(r.get("created_at"))) and 0<=(now-t).total_seconds()<95*60]
    if not recent:errors.append("最近95分鐘無 TW Stock Dashboard 工作紀錄，排程可能未觸發")
    active=any(r.get("status") in ("queued","waiting","in_progress","pending","requested") for r in recent)
    if pages is not None and published:
        page_at=parse(pages.get("publishedAt")) if isinstance(pages,dict) else None
        if not page_at or published-page_at>timedelta(minutes=25):errors.append("GitHub Pages 榜單比原始檔落後超過25分鐘")
    return {"ok":not errors,"errors":errors,"date":today,"publishedAt":latest.get("publishedAt"),
            "ageMinutes":round(age) if age is not None else None,"rows":len(rows) if isinstance(rows,list) else 0,"activeRun":active}
def request(path,method="GET",payload=None,external=False):
    url=path if external else API+path
    head={"Accept":"application/vnd.github+json","User-Agent":"tw-g-intraday-watchdog","X-GitHub-Api-Version":"2022-11-28"}
    if not external:head["Authorization"]="Bearer "+os.environ["GITHUB_TOKEN"]
    if payload is not None:head["Content-Type"]="application/json"
    data=json.dumps(payload,ensure_ascii=False).encode("utf-8") if payload is not None else None
    req=Request(url,headers=head,data=data,method=method)
    with urlopen(req,timeout=25) as resp:
        raw=resp.read().decode("utf-8")
    return json.loads(raw) if raw else None
def published_json(filename):
    b=request("/contents/tw-stock-dashboard/docs/data/g_intraday/"+filename+"?ref=main")
    return json.loads(base64.b64decode(b["content"]).decode("utf-8"))
def find_issue():
    found=request("/issues?state=all&sort=updated&direction=desc&per_page=100")
    return next((item for item in found if item["title"]==ISSUE and "pull_request" not in item),None)
def issue_message(now,s):
    return ("**監控時間：** "+now.astimezone(TZ).isoformat(timespec="seconds")+"\n\n**最後成功榜單：** "+str(s["publishedAt"])+
            f"（{s['ageMinutes']} 分鐘前，{s['rows']} 檔）\n\n**異常項目：**\n"+ "\n".join("- "+e for e in s["errors"])+
            f"\n\n[盤中網頁](https://jacky-168168.github.io/Tradingview-testing/selections.html) · [Actions]({BASE}/actions/workflows/tw-stock-dashboard.yml) · [JSON]({BASE}/blob/main/tw-stock-dashboard/docs/data/g_intraday/latest.json)\n\n此問題會自動補跑並在驗證恢復後關閉。<!-- monitor:g-intraday-health -->")
def last_retry(number):
    comments=request(f"/issues/{number}/comments?per_page=100")
    stamps=[parse(c.get("created_at")) for c in comments if "AUTO_RECOVERY" in c.get("body","")]
    return max((x for x in stamps if x),default=None)
def issue_update(now,s):
    issue=find_issue()
    if s["ok"]:
        if issue and issue["state"]=="open":
            request(f"/issues/{issue['number']}/comments","POST",{"body":f"✅ 盤中 G 已恢復：{s['publishedAt']}，{s['rows']} 檔。"})
            request(f"/issues/{issue['number']}","PATCH",{"state":"closed","state_reason":"completed"})
            print("HEALTH_RECOVERED",issue["html_url"])
        else:print("HEALTH_OK",s["publishedAt"],s["rows"])
        return
    fresh=not issue or issue["state"]!="open"
    if not issue:issue=request("/issues","POST",{"title":ISSUE,"body":issue_message(now,s),"assignees":["jacky-168168"]})
    elif issue["state"]=="closed":
        issue=request(f"/issues/{issue['number']}","PATCH",{"state":"open","body":issue_message(now,s),"assignees":["jacky-168168"]})
    print("HEALTH_ALERT" if fresh else "HEALTH_PERSISTENT",issue["html_url"]," | ".join(s["errors"]))
    t=now.astimezone(TZ).time()
    retry=None if fresh else last_retry(issue["number"])
    if not s["activeRun"] and t<time(13,28) and (not retry or now-retry>timedelta(minutes=45)):
        try:
            request("/actions/workflows/tw-stock-dashboard.yml/dispatches","POST",{"ref":"main","inputs":{"mode":"intraday"}})
            request(f"/issues/{issue['number']}/comments","POST",{"body":"🔄 AUTO_RECOVERY：已請求重新執行盤中 G 更新；尚待新榜單驗證。"})
            print("AUTO_RECOVERY_TRIGGERED")
        except Exception as exc:
            request(f"/issues/{issue['number']}/comments","POST",{"body":"⚠ AUTO_RECOVERY 補跑失敗："+str(exc)[:240]})
            print("AUTO_RECOVERY_FAILED",str(exc),file=sys.stderr)
def main():
    now=datetime.now(timezone.utc)
    if not session(now):
        print("OUTSIDE_SESSION_SKIP",now.astimezone(TZ).isoformat());return
    latest=published_json("latest.json");status=published_json("status.json")
    runs=request("/actions/workflows/tw-stock-dashboard.yml/runs?per_page=40").get("workflow_runs",[])
    pages=None
    try:pages=request(PAGES+"?nocache="+str(int(now.timestamp())),external=True)
    except Exception as exc:print("PAGES_FETCH_WARN",repr(exc))
    s=assess(now,latest,status,runs,pages)
    if pages is None and s["ageMinutes"] is not None and s["ageMinutes"]>25:
        s["ok"]=False;s["errors"].append("GitHub Pages 暫時無法讀取，無法確認前端資料")
    print("HEALTH_RESULT",json.dumps(s,ensure_ascii=False));issue_update(now,s)
if __name__=="__main__":main()
