"""Merge per-run official market risk checkpoints after syncing latest GitHub main.

Use only on a runner where local archive was checkpointed to another directory
BEFORE git reset --hard origin/main. A retry resets to the latest remote and
re-merges, so simultaneous unrelated commits cannot lose confirmed dates.
This module NEVER invents daily Risk Score entries for missing official dates.
"""
from __future__ import annotations
import argparse,csv,json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

NAMES=("risk_inputs.json","risk_errors.json","market_risk_daily.json","coverage.json","market_risk_daily.csv")

def read_json(path,default):
    try:return json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:return default

def valid(z):
    if not isinstance(z,dict) or not z.get("ok"):return False
    try:
        up=int(z["up"]);down=int(z["down"]);f=float(z["foreign"])
        return up>=0 and down>=0 and up+down>=500 and -5000<f<5000
    except (KeyError,ValueError,TypeError):return False

def combine_rows(a,b):
    a=a if isinstance(a,dict) else {}
    b=b if isinstance(b,dict) else {}
    if valid(a) and not valid(b):return dict(a)
    if valid(b) and not valid(a):return dict(b)
    if valid(a) and valid(b):
        return dict(a if str(a.get("checkedAt",""))>=str(b.get("checkedAt","")) else b)
    z=dict(a);z.update({k:v for k,v in b.items() if v is not None and v!=""})
    # Complementary fields from two partial runs can complete a date.
    if valid({**z,"ok":True}):
        z["ok"]=True;z.pop("error",None)
    else:z["ok"]=False
    z["attempts"]=max(int(a.get("attempts") or 0),int(b.get("attempts") or 0))
    return z

def merge(latest,local,out):
    out.mkdir(parents=True,exist_ok=True)
    merged=dict(read_json(latest/"risk_inputs.json",{}))
    for d,z in read_json(local/"risk_inputs.json",{}).items():
        merged[d]=combine_rows(merged.get(d),z)
    daily={}
    # Only preserve actual previously computed score rows with BOTH dated official inputs.
    for folder in (latest,local):
        for row in read_json(folder/"market_risk_daily.json",[]):
            if not isinstance(row,dict):continue
            d=str(row.get("date") or "")
            if valid(merged.get(d)) and isinstance(row.get("score"),int) and 0<=row["score"]<=100:
                daily[d]=row
    good=[daily[d] for d in sorted(daily)]
    # Historical days are fixed to Yahoo ^TWII calendar: union of scored and missing days.
    cal=set(daily)
    failure={}
    for folder in (latest,local):
        for z in read_json(folder/"risk_errors.json",[]):
            d=str(z.get("date") or "")
            if d:cal.add(d);failure[d]=z
    # All cache dates may be valid/partial, preserve for the next retry.
    cal.update(merged)
    risk_errors=[]
    for d in sorted(cal):
        if d in daily:continue
        z=merged.get(d) or {}
        missing=[]
        if not isinstance(z.get("up"),int) or not isinstance(z.get("down"),int):missing.append("breadth")
        if not isinstance(z.get("foreign"),(int,float)):missing.append("foreign")
        err={"date":d,"missing":missing,"attempts":int(z.get("attempts") or 0),"error":z.get("error")}
        if not missing and d not in daily:err["error"]="OFFICIAL_INPUT_PRESENT_BUT_SCORE_NOT_YET_CALCULATED"
        risk_errors.append(err)
    old=read_json(latest/"coverage.json",{})
    new=read_json(local/"coverage.json",{})
    trading_days=max(int(old.get("tradingDays") or 0),int(new.get("tradingDays") or 0),len(cal))
    # A mismatched index calendar should be a loud failure, never silent output.
    if trading_days==0 or len(good)>trading_days:raise RuntimeError("Invalid merged market calendar")
    period=new.get("period") or old.get("period") or {}
    count=len(good)
    cov={"period":period,"tradingDays":trading_days,
         "officialValidDays":sum(1 for d in cal if valid(merged.get(d))),
         "riskScoredDays":count,"missingDays":trading_days-count,
         "coveragePct":round(count/trading_days*100,3),
         "complete":count==trading_days,
         "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
         "calendar":new.get("calendar") or old.get("calendar") or "Yahoo ^TWII trading dates",
         "sources":new.get("sources") or old.get("sources") or {},
         "warning":"Incomplete dates have no score. Do not use for complete three-year backtest." if count<trading_days else ""}
    for name,value in [("risk_inputs.json",merged),("market_risk_daily.json",good),("risk_errors.json",risk_errors),("coverage.json",cov)]:
        target=out/name
        with target.open("w",encoding="utf-8") as fp:json.dump(value,fp,ensure_ascii=False,indent=2,allow_nan=False)
    csvfile=out/"market_risk_daily.csv"
    if good:
        with csvfile.open("w",encoding="utf-8-sig",newline="") as fp:
            writer=csv.DictWriter(fp,fieldnames=list(good[0]),extrasaction="ignore");writer.writeheader();writer.writerows(good)
    print("ARCHIVE_MERGED",json.dumps({"previousSaved":len(read_json(latest/"market_risk_daily.json",[])),
        "collectedLocally":len(read_json(local/"market_risk_daily.json",[])),
        "newSaved":count,"tradingDays":trading_days,"coveragePct":cov["coveragePct"]},ensure_ascii=False),flush=True)
    return cov

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--base",required=True)
    parser.add_argument("--local",required=True);parser.add_argument("--out",required=True)
    a=parser.parse_args()
    merge(Path(a.base),Path(a.local),Path(a.out))
