"""Independent silent backup clock for live G scans (no trades, no alerts).

Runs at offset minutes on TW trading days. If the primary cron has not
published a current, validated G snapshot, use workflow_dispatch to recover.
The health monitor separately owns GitHub Issue notifications.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone, time, timedelta
from g_intraday_health import TZ, CLOSED_2026, parse, request, published_json

ACTIVE={"queued","waiting","in_progress","pending","requested"}

def trade_window(now):
    tw=now.astimezone(TZ)
    return (tw.weekday()<5
            and not(tw.year==2026 and tw.strftime("%m-%d") in CLOSED_2026)
            and time(9,10)<=tw.time()<time(13,42))

def is_good_snapshot(latest, now):
    if not isinstance(latest,dict):return False
    tw=now.astimezone(TZ)
    if latest.get("asOfDate")!=tw.date().isoformat() or latest.get("quality")!="intraday-provisional-allmarket":return False
    rows=latest.get("rows")
    if not isinstance(rows,list) or not 1<=len(rows)<=20 or not all(isinstance(r,dict) and str(r.get("code","")).isdigit() and len(str(r.get("code","")))==4 for r in rows):return False
    try:
        c=latest["coverage"];total=int(c["total"]);valid=int(c["valid"])
        if total<1800 or valid<1000 or valid/total<.65:return False
        for market in ("上市","上櫃"):
            a=c["exchange"][market]
            if int(a["total"])<500 or int(a["valid"])/int(a["total"])<.60:return False
    except (KeyError,TypeError,ValueError,ZeroDivisionError):return False
    stamp=parse(latest.get("publishedAt"))
    return stamp is not None and 0<=(now-stamp).total_seconds()<22*60

def recovery_decision(now, latest, status, runs):
    if not trade_window(now):return False,"not-trading-session"
    recent_ok=is_good_snapshot(latest,now)
    pub=parse(latest.get("publishedAt")) if isinstance(latest,dict) else None
    failure=parse(status.get("checkedAt")) if isinstance(status,dict) else None
    failed_newer=(isinstance(status,dict) and status.get("asOfDate")==now.astimezone(TZ).date().isoformat()
                  and status.get("status")=="unavailable" and failure is not None
                  and (pub is None or failure>pub+timedelta(seconds=10)))
    if recent_ok and not failed_newer:return False,"fresh-validated-today"
    for run in runs or []:
        if run.get("name")!="TW Stock Dashboard":continue
        started=parse(run.get("created_at"))
        if not started:continue
        age=(now-started).total_seconds()
        if 0<=age<15*60:return False,"dashboard-run-just-started"
        if 0<=age<90*60 and run.get("status") in ACTIVE:return False,"dashboard-already-running"
    return True,"stale-or-invalid-live-G"

def main():
    now=datetime.now(timezone.utc)
    if not trade_window(now):
        print("G_BACKUP_OUTSIDE_SESSION",now.astimezone(TZ).isoformat());return
    try:latest=published_json("latest.json")
    except Exception as e:
        print("G_BACKUP_LATEST_UNREADABLE",type(e).__name__,str(e)[:160]);latest={}
    try:status=published_json("status.json")
    except Exception as e:
        print("G_BACKUP_STATUS_UNREADABLE",type(e).__name__,str(e)[:160]);status={}
    runs=request("/actions/workflows/tw-stock-dashboard.yml/runs?per_page=40").get("workflow_runs",[])
    trigger,reason=recovery_decision(now,latest,status,runs)
    print("G_BACKUP_DECISION",json.dumps({"time":now.astimezone(TZ).isoformat(timespec="seconds"),
          "reason":reason,"trigger":trigger,"latest":latest.get("publishedAt"),"status":status.get("status")},ensure_ascii=False))
    if not trigger:return
    request("/actions/workflows/tw-stock-dashboard.yml/dispatches","POST",{"ref":"main","inputs":{"mode":"intraday"}})
    print("G_BACKUP_DISPATCH_ACCEPTED_PENDING_RESULT")
if __name__=="__main__":main()
