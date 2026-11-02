"""Freeze ONE daily premarket reference before cash open, never recompute intraday/evening.

This is a display-only reference derived from last verified official cash Risk Score
and, only if date-matched, a completed TX day/night pair. No F/F2/G trading gates
or published official daily snapshots are modified.
"""
from __future__ import annotations
import json, math, os, sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"docs/data"
OUTPUT=DATA/"market_premarket"/"latest.json"
TZ=ZoneInfo("Asia/Taipei")
QUALITY="fixed-premarket-reference-v1"

def valid_score(r):
    return isinstance(r,dict) and type(r.get("score")) is int and 0<=r["score"]<=100

def target_day(now):
    here=now.astimezone(TZ)
    if here.weekday()>=5 or not time(7,30)<=here.time()<time(9,0):
        return None
    return here.date().isoformat()

def tx_delta(pct):
    if not math.isfinite(pct) or abs(pct)>12:raise ValueError("TX percentage outside trusted range")
    return -25 if pct<=-2 else -15 if pct<=-1 else -8 if pct<=-.5 else 10 if pct>=2 else 7 if pct>=1 else 4 if pct>=.5 else 0

def get_last_cash(target,read):
    candidates=[]
    # Independent verified TWSE snapshot can exist before full A/D/F/G refresh.
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
        try:
            gap=(datetime.fromisoformat(target)-datetime.fromisoformat(day)).days
        except ValueError:
            continue
        if 1<=gap<=7:candidates.append((day,risk,name))
    # Never silently freeze a stale close from two sessions ago. Holiday gaps
    # need an independently verified calendar path, otherwise fail closed.
    target_date=datetime.fromisoformat(target).date()
    prior_weekday=target_date-timedelta(days=3 if target_date.weekday()==0 else 1)
    candidates=[row for row in candidates if row[0]==prior_weekday.isoformat()]
    if not candidates:raise RuntimeError("NO_RECENT_DATE_MATCHED_OFFICIAL_CASH_RISK")
    candidates.sort(key=lambda x:(x[0], x[2].startswith("market_risk_close/")),reverse=True)
    return candidates[0]

def matched_tx(target,base_day,read):
    path=DATA/"futures/latest.json"
    if not path.exists():return None
    q=read(path)
    day=q.get("day") or {};night=q.get("night") or {}
    compact=base_day.replace("-","")
    if q.get("quality")!="paired-day-night" or q.get("asOfDate")!=base_day or \
       day.get("date")!=compact or night.get("date")!=compact or \
       day.get("contract")!=q.get("contract") or night.get("contract")!=q.get("contract") or \
       night.get("reportQueryDate")!=target:
        return None
    try:
        a,b,reported=float(day.get("close")),float(night.get("close")),float(q.get("nightVsDayPct"))
    except (ValueError,TypeError):return None
    if min(a,b)<=10000 or max(a,b)>100000 or not all(map(math.isfinite,(a,b,reported))):
        return None
    pct=(b/a-1)*100
    if abs(pct-reported)>.08 or abs(pct)>12:return None
    return {"pct":round(pct,4),"source":"期交所已完成同月台指期日夜盤","sourceDate":base_day}

def build(now, read=None):
    read=read or (lambda p:json.loads(p.read_text(encoding="utf-8")))
    target=target_day(now)
    if target is None:return None
    if OUTPUT.exists():
        old=read(OUTPUT)
        if old.get("quality")==QUALITY and old.get("targetDate")==target:
            # One fixed score per date, with no 08:55 revision or nighttime overwrite.
            print("PREMARKET_ALREADY_FROZEN",target,old.get("score"),flush=True)
            return old
    base_day,risk,origin=get_last_cash(target,read)
    base=risk["score"]
    tx=matched_tx(target,base_day,read)
    delta=tx_delta(tx["pct"]) if tx else 0
    score=max(0,min(100,base+delta))
    here=now.astimezone(TZ)
    payload={
        "quality":QUALITY,
        "targetDate":target,
        "publishedAt":here.isoformat(timespec="seconds"),
        "lockedForTradingDate":target,
        "score":score,
        "baseScore":base,
        "baseDate":base_day,
        "adjustment":delta,
        "txPct":tx["pct"] if tx else None,
        "txSource":tx["source"] if tx else None,
        "source":"前一交易日經核對的正式 Risk Score"+("＋已完成TX夜盤調整" if tx else "；無合格TX夜盤，未調整"),
        "cashSource":origin,
        "method":"FIXED_REFERENCE_NOT_OFFICIAL_INTRADAY_RISK",
        "note":"盤前固定參考分數，全天維持不變；不是當日正式現貨 Risk Score，不覆寫選股 F/F2/G"
    }
    return payload

def main():
    now=datetime.now(TZ)
    if target_day(now) is None:
        print("PREMARKET_OUTSIDE_WINDOW",now.isoformat(),flush=True)
        return
    data=build(now)
    if not data:raise RuntimeError("PREMARKET_NOT_CREATED")
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    content=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    if OUTPUT.exists() and OUTPUT.read_text(encoding="utf-8")==content:
        print("PREMARKET_UNCHANGED",data["targetDate"],data["score"],flush=True)
        return
    tmp=OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(content,encoding="utf-8")
    tmp.replace(OUTPUT)
    print("PREMARKET_FROZEN",data["targetDate"],data["score"],"base",data["baseDate"],data["baseScore"],"adjust",data["adjustment"],flush=True)

if __name__=="__main__":
    try:main()
    except Exception as e:
        print("PREMARKET_FREEZE_FAILED",repr(e),file=sys.stderr,flush=True)
        sys.exit(1)
