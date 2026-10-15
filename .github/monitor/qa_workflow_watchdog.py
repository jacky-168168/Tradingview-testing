"""Independent GitHub Actions QA watchdog. Posts deduplicated assigned issues."""
from __future__ import annotations
import json,os,sys,base64
from datetime import datetime,timezone,time,timedelta
from urllib.request import Request,urlopen
from zoneinfo import ZoneInfo
from g_intraday_health import CLOSED_2026
ROOT="https://api.github.com/repos/jacky-168168/Tradingview-testing"
WORKFLOWS={
 "TW Stock Python CI":"tw-stock-ci.yml",
 "Full Website Browser Audit":"full-site-browser-audit.yml",
 "TW Stock Pages":"tw-stock-pages.yml",
 "TW Stock Dashboard":"tw-stock-dashboard.yml",
 "G Intraday Health Monitor":"g-intraday-health.yml",
}
SCHEDULES={"TW Stock Python CI":25,"Full Website Browser Audit":192}
PREFIX="[AUTOMATED QUALITY] "
def hours_since(when,now):
    try:
        t=datetime.fromisoformat(str(when).replace("Z","+00:00"))
        return (now-t).total_seconds()/3600 if t.tzinfo else None
    except (ValueError,TypeError):return None
def due(name,last,now):
    if name not in SCHEDULES:return None
    if not last or (hours:=hours_since(last.get("created_at"),now)) is None:
        return "找不到最近的 "+name+" 執行紀錄"
    if hours>SCHEDULES[name]:
        return name+f" 已超過 {hours:.1f} 小時沒有執行；預期上限 {SCHEDULES[name]} 小時"
    return None
def req(path,method="GET",body=None):
    headers={"Authorization":"Bearer "+os.environ["GITHUB_TOKEN"],"Accept":"application/vnd.github+json","User-Agent":"tw-stock-quality-watchdog"}
    if body is not None:headers["Content-Type"]="application/json"
    raw=json.dumps(body,ensure_ascii=False).encode() if body is not None else None
    with urlopen(Request(ROOT+path,data=raw,headers=headers,method=method),timeout=25) as resp:
        data=resp.read().decode()
    return json.loads(data) if data else None
def issue_for(name):
    issues=req("/issues?state=all&sort=updated&direction=desc&per_page=100")
    title=PREFIX+name
    return next((x for x in issues if x.get("title")==title and not x.get("pull_request")),None)
def publish(name,reason,run_id=None,run_url=None):
    issue=issue_for(name)
    if not reason:
        if issue and issue["state"]=="open":
            req(f"/issues/{issue['number']}/comments","POST",{"body":"✅ 已觀測到最新一次正常執行；此項異常結案。"})
            req(f"/issues/{issue['number']}","PATCH",{"state":"closed","state_reason":"completed"})
            print("QA_RECOVERED",name)
        return
    message=("**自動 QA 異常：** "+reason+"\n\n"+
        ("**GitHub Actions：** "+run_url+"\n" if run_url else "**GitHub Actions：** https://github.com/jacky-168168/Tradingview-testing/actions\n")+
        ("**執行編號：** "+str(run_id)+"\n" if run_id else "")+
        "\nCI 僅檢查程式與研究資料一致性，不代表策略已達成可交易統計顯著性。"+
        "\n\n<!-- managed:tw-stock-quality-watchdog -->")
    if issue and issue["state"]=="open":
        if (run_id is None and reason in str(issue.get("body",""))) or (run_id is not None and str(run_id) in str(issue.get("body",""))):
            print("QA_ALREADY_REPORTED",name,run_id);return
        req(f"/issues/{issue['number']}","PATCH",{"body":message})
        req(f"/issues/{issue['number']}/comments","POST",{"body":"⚠ 新異常執行："+(run_url or reason)})
    elif issue:
        req(f"/issues/{issue['number']}","PATCH",{"state":"open","body":message,"assignees":["jacky-168168"]})
    else:
        issue=req("/issues","POST",{"title":PREFIX+name,"body":message,"assignees":["jacky-168168"]})
    print("QA_ALERT",name,issue.get("html_url"))
def run_event(event):
    entry=event.get("workflow_run") or {}
    name=str(entry.get("name") or "")
    if name not in WORKFLOWS:return
    state=entry.get("conclusion")
    if state=="failure":
        publish(name,"工作流程執行失敗，請核對失敗 Job 的完整日誌。",entry.get("id"),entry.get("html_url"))
    elif state=="success":publish(name,None)
    else:print("QA_IGNORED",name,state)
def eod_health(now,data):
    local=now.astimezone(ZoneInfo("Asia/Taipei"))
    if local.weekday()>=5 or (local.year==2026 and local.strftime("%m-%d") in CLOSED_2026):return None
    day=local.date().isoformat()
    if not isinstance(data,dict):return "最新盤後 JSON 無法讀取"
    if data.get("dataDate")!=day:return "盤後正式資料尚未發布當日 "+day+"（目前資料日 "+str(data.get("dataDate"))+"）"
    if (data.get("risk") or {}).get("date")!=day:return "Risk Score 正式資料日期與盤後日期不一致"
    if (data.get("gSelection") or {}).get("dataDate")!=day:return "G 正式模型資料日期與盤後日期不一致"
    models=data.get("models") or {}
    if not isinstance(models.get("G"),list) or any(m not in models for m in ("A","D","F","F2")):return "正式 A/D/F/F2/G 模型資料缺失"
    quality=data.get("institutionQuality") or {}
    if quality.get("status")!="complete" or quality.get("date")!=day:
        return "正式榜單缺少當日上市／上櫃官方法人完整性驗證"
    if quality.get("missingRanked",1)!=0:return "正式榜單仍有 "+str(quality.get("missingRanked"))+" 檔法人資料缺漏"
    coverage=quality.get("marketCoverage") or {}
    if any(float(coverage.get(market) or 0)<.80 for market in ("上市","上櫃")):
        return "上市／上櫃法人資料覆蓋率不足 80%"
    return None
def load_official_snapshot():
    source=req("/contents/tw-stock-dashboard/docs/data/latest.json?ref=main")
    return json.loads(base64.b64decode(source["content"]).decode("utf-8"))
def eod_watch(now):
    """Independent recovery if GitHub scheduled FULL jobs never start.
    Called also by workflow_run events, so does not depend on GitHub cron.
    """
    local=now.astimezone(ZoneInfo("Asia/Taipei"))
    if local.weekday()>=5 or (local.year==2026 and local.strftime("%m-%d") in CLOSED_2026) or not time(18,0)<=local.time()<time(23,50):
        return
    try:
        reason=eod_health(now,load_official_snapshot())
    except Exception as exc:
        reason="盤後資料讀取異常："+repr(exc)[:220]
    title="TW Stock Dashboard EOD Freshness"
    if not reason:
        publish(title,None)
        print("EOD_LATEST_OK",local.isoformat())
        return
    publish(title,reason)
    runs=req("/actions/workflows/tw-stock-dashboard.yml/runs?per_page=45").get("workflow_runs",[])
    recent=lambda run,mins: (n:=hours_since(run.get("created_at"),now)) is not None and -0.04<=n<mins/60
    if any(recent(r,85) and r.get("status") in ("in_progress","queued","pending","waiting","requested") for r in runs):
        print("EOD_RECOVERY_WAIT_ACTIVE_RUN");return
    if any(recent(r,70) and r.get("event")=="workflow_dispatch" for r in runs):
        print("EOD_RECOVERY_COOLDOWN_RECENT_DISPATCH");return
    issue=issue_for(title)
    if issue:
        comments=req(f"/issues/{issue['number']}/comments?per_page=100")
        if any("AUTO_EOD_RETRY" in c.get("body","") and recent(c,65) for c in comments):
            print("EOD_RECOVERY_COOLDOWN_ISSUE");return
    print("EOD_RECOVERY_DISPATCH",reason)
    req("/actions/workflows/tw-stock-dashboard.yml/dispatches","POST",{"ref":"main","inputs":{"mode":"full"}})
    if issue:
        req(f"/issues/{issue['number']}/comments","POST",{"body":"🔄 AUTO_EOD_RETRY：正式盤後 JSON 過期，已請求 full 更新（尚待資料日期驗證）。"})
def daily(now):
    for name,wid in SCHEDULES.items():
        latest=req("/actions/workflows/"+WORKFLOWS[name]+"/runs?per_page=5").get("workflow_runs",[])
        newest=latest[0] if latest else None
        overdue=due(name,newest,now)
        if overdue:publish(name,overdue,newest.get("id") if newest else None,newest.get("html_url") if newest else None)
        elif newest and newest.get("conclusion")=="failure":publish(name,"最近一次測試失敗且尚未有新的成功紀錄。",newest.get("id"),newest.get("html_url"))
        elif newest and newest.get("conclusion")=="success":publish(name,None)
    eod_watch(now)
def main():
    event_name=os.getenv("GITHUB_EVENT_NAME","")
    event_path=os.getenv("GITHUB_EVENT_PATH")
    event=json.loads(open(event_path,encoding="utf-8").read()) if event_path and os.path.isfile(event_path) else {}
    if event_name=="workflow_run":
        run_event(event)
        if (event.get("workflow_run") or {}).get("name") in WORKFLOWS:eod_watch(datetime.now(timezone.utc))
    elif event_name in ("schedule","workflow_dispatch"):daily(datetime.now(timezone.utc))
    elif event_name=="push":eod_watch(datetime.now(timezone.utc))
    else:print("QA_BOOTSTRAP_RUN",event_name,"no incident raised")
if __name__=="__main__":main()
