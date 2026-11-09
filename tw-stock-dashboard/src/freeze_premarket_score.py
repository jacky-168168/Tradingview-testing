"""Publish one dated, immutable next-session premarket reference.
Primarily PREBUILD after preceding TWSE close; morning slots and late recovery are backups.
Only verified prior official Risk Score and rigorously dated *completed* TX night can count.
No current-day intraday/official numbers or F/F2/G gates are changed.
"""
from __future__ import annotations
import json,math,sys
from datetime import datetime,time,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"docs/data"
OUTPUT=DATA/"market_premarket"/"latest.json"
TZ=ZoneInfo("Asia/Taipei")
QUALITY="fixed-premarket-reference-v1"

def valid_score(r):
    return isinstance(r,dict) and type(r.get("score")) is int and 0<=r["score"]<=100

def next_weekday(d):
    d+=timedelta(days=1)
    while d.weekday()>=5:
        d+=timedelta(days=1)
    return d

def target_day(now):
    local=now.astimezone(TZ)
    # Pre-build immediately after today's verified official close and store tomorrow's
    # session; the 08:xx schedule is no longer a single point of failure.
    if local.weekday()<5 and local.time()>=time(17,30):
        return next_weekday(local.date()).isoformat()
    if local.weekday()>=5:
        d=local.date()
        while d.weekday()>=5:d+=timedelta(days=1)
        return d.isoformat()
    return local.date().isoformat()

def tx_delta(pct):
    if not math.isfinite(pct) or abs(pct)>12:
        raise ValueError("TX pct outside validated range")
    return -25 if pct<=-2 else -15 if pct<=-1 else -8 if pct<=-.5 else 10 if pct>=2 else 7 if pct>=1 else 4 if pct>=.5 else 0

def get_last_cash(target,read):
    candidates=[]
    for name in ("market_risk_close/latest.json","latest.json"):
        path=DATA/name
        if not path.exists():continue
        row=read(path)
        risk=row.get("risk") or {}
        day=str(row.get("asOfDate") or row.get("dataDate") or "")
        if name.startswith("market_risk_close/") and row.get("quality")!="official-twse-close-risk-v1":
            continue
        if not valid_score(risk) or risk.get("date")!=day or not day<target:
            continue
        try:gap=(datetime.fromisoformat(target)-datetime.fromisoformat(day)).days
        except ValueError:continue
        # Preserve holidays/weekends, but do not silently use a week-old score.
        if 1<=gap<=5:candidates.append((day,risk,name))
    if not candidates:
        raise RuntimeError("NO_RECENT_DATE_MATCHED_OFFICIAL_CASH_RISK")
    candidates.sort(key=lambda x:(x[0],x[2].startswith("market_risk_close/")),reverse=True)
    # Prevent an old trading session replacing a newer verified official snapshot.
    return candidates[0]

def matched_tx(target,base_day,read):
    path=DATA/"futures/latest.json"
    if not path.exists():return None
    q=read(path);day=q.get("day") or {};night=q.get("night") or {}
    compact=base_day.replace("-","")
    if q.get("quality")!="paired-day-night" or q.get("asOfDate")!=base_day or \
       day.get("date")!=compact or night.get("date")!=compact or \
       day.get("contract")!=q.get("contract") or night.get("contract")!=q.get("contract") or \
       night.get("reportQueryDate")!=target:return None
    try:a,b,reported=float(day.get("close")),float(night.get("close")),float(q.get("nightVsDayPct"))
    except (ValueError,TypeError):return None
    if min(a,b)<=10000 or max(a,b)>100000 or not all(map(math.isfinite,(a,b,reported))):
        return None
    pct=(b/a-1)*100
    if abs(pct-reported)>.08 or abs(pct)>12:return None
    return {"pct":round(pct,4),"source":"期交所已完成同月份台指期日夜盤"}

def dated_path(day):
    return OUTPUT.parent/(day+".json")

def build(now,read=None):
    read=read or (lambda path:json.loads(path.read_text(encoding="utf-8")))
    here=now.astimezone(TZ);target=target_day(now)
    dated=dated_path(target)
    for path in (dated,OUTPUT):
        if path.exists():
            existing=read(path)
            if existing.get("quality")==QUALITY and existing.get("targetDate")==target and \
               valid_score({"score":existing.get("score")}) and existing.get("lockedForTradingDate")==target:
                print("PREMARKET_ALREADY_FROZEN",target,existing["score"],flush=True)
                return existing
    base_day,risk,origin=get_last_cash(target,read)
    if here.weekday()<5 and here.time()>=time(17,30) and base_day!=here.date().isoformat():
        raise RuntimeError('OFFICIAL_TODAY_NOT_READY_FOR_TOMORROW_PREBUILD: '+base_day)
    base=risk["score"]
    tx=matched_tx(target,base_day,read)
    delta=tx_delta(tx["pct"]) if tx else 0
    score=max(0,min(100,base+delta))
    mode="after-close-prebuild" if here.date().isoformat()<target else \
         "before-open" if here.time()<time(9) else "late-recovery"
    return {
        "quality":QUALITY,"targetDate":target,"lockedForTradingDate":target,
        "publishedAt":here.isoformat(timespec="seconds"),"calculationMode":mode,
        "score":score,"baseScore":base,"baseDate":base_day,
        "adjustment":delta,"txPct":tx["pct"] if tx else None,
        "txSource":tx["source"] if tx else None,
        "source":"前一可核對交易日的正式 Risk Score"+("＋已完成 TX 夜盤調整" if tx else "；無已驗證 TX 夜盤，未調整"),
        "cashSource":origin,"method":"FIXED_REFERENCE_NOT_OFFICIAL_INTRADAY_RISK",
        "note":"盤前固定風險參考，不是盤中或當日收盤 Risk Score；計算時間見 publishedAt。延遲補建必須標明。"
    }

def write_json(path,obj):
    raw=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8")==raw:return False
    tmp=path.with_suffix(".json.tmp")
    tmp.write_text(raw,encoding="utf-8")
    tmp.replace(path)
    return True

def main():
    now=datetime.now(TZ)
    data=build(now)
    target=data["targetDate"]
    changed_archive=write_json(dated_path(target),data)
    # latest.json is an index convenience. Dated per-session files are source of
    # truth so an evening pre-build for tomorrow NEVER erases today's hero score.
    changed_latest=False
    if not OUTPUT.exists():
        changed_latest=write_json(OUTPUT,data)
    else:
        old=json.loads(OUTPUT.read_text(encoding="utf-8"))
        if str(old.get("targetDate") or "")<=target:
            changed_latest=write_json(OUTPUT,data)
    print("PREMARKET_READY",target,data["score"],"base",data["baseDate"],"mode",data["calculationMode"],
          "archiveChanged",changed_archive,"latestChanged",changed_latest,flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("PREMARKET_FREEZE_FAILED",type(exc).__name__,str(exc)[:600],file=sys.stderr,flush=True)
        sys.exit(1)
