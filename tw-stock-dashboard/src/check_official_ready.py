"""Fail-closed, nonfatal TWSE official-close readiness gate for scheduled builds.
Absence of BFI82U before publication means DEFER, not a valid daily Risk Score."""
from __future__ import annotations
import os,sys,json
from datetime import datetime,time
from zoneinfo import ZoneInfo
from risk import _report
TZ=ZoneInfo("Asia/Taipei")
def ready_for_close(day,check=_report):
    try:
        r=check(day,"fund/BFI82U",{"dayDate":day.replace("-",""),"type":"day"})
        data=r.get("data") or []
        return any(row and "外資及陸資" in str(row[0]) and len(row)>1 for row in data)
    except Exception as ex:
        print("CLOSE_DATA_DEFERRED",str(ex)[:320],flush=True)
        return False
def main():
    now=datetime.now(TZ);today=now.date().isoformat();event=os.getenv("GITHUB_EVENT_NAME","")
    # A push during the closing auction should only test/deploy frontend.
    # Scheduled retries at 15:40 onwards probe official date-pinned BFI82U.
    if now.weekday()>=5:
        ok=True;why="weekend: pipeline will freeze last completed trading day"
    elif now.time()<time(15,30):
        ok=False;why="official daily flow not expected before 15:30 Taipei"
    else:
        ok=ready_for_close(today);why="dated BFI82U ready" if ok else "dated BFI82U not published"
    with open(os.environ["GITHUB_OUTPUT"],"a",encoding="utf-8") as file:
        file.write("ready="+str(ok).lower()+"\n")
    print(json.dumps({"date":today,"event":event,"fullUpdateReady":ok,"reason":why},ensure_ascii=False),flush=True)
    if not ok:
        with open(os.environ.get("GITHUB_STEP_SUMMARY","/dev/null"),"a",encoding="utf-8") as file:
            file.write("### Official daily publication pending\nNo daily Risk Score or EOD G signal was published. "+why+". The next scheduled full retry will check again.\n")
if __name__=="__main__":main()
