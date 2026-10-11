"""Extend independently dated official TWSE up/down and foreign to 2015-2023.
Resumable year shards, strict source date, no interpolation; never change existing
728-day official G market Risk Score archive or live market decision thresholds.
"""
from __future__ import annotations
import argparse,json,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from config import BENCHMARK,DATA_DIR
from yahoo_cache import update_symbol
from collect_market_risk_history import atomic_json,valid_saved,update_day
from risk import build_historical
ROOT=DATA_DIR/"research"/"market_history_extended"/"years"
LAST_PRIOR_DAY="2023-10-10"
def run(year,max_days,delay,timeout):
    if year<2015 or year>2023:raise ValueError("Unsupported year")
    start=f"{year}-01-01";end=min(f"{year}-12-31",LAST_PRIOR_DAY)
    begin=datetime.fromisoformat(start)-timedelta(days=135)
    enddt=datetime.fromisoformat(end)+timedelta(days=1)
    print("HISTORY_EXTENDED_YEAR",year,"bench",BENCHMARK,"window",start,end,flush=True)
    _,ix,err=update_symbol(BENCHMARK,begin,enddt)
    if err or ix is None or ix.empty:raise RuntimeError("Historical Yahoo ^TWII missing: "+str(err))
    ix=ix.sort_values("date").drop_duplicates("date",keep="last").reset_index(drop=True)
    ix["date"]=ix.date.astype(str)
    dates=[d for d in ix.date if start<=d<=end]
    if len(dates)<120:raise RuntimeError("Historical session calendar too short: "+str(len(dates)))
    ROOT.mkdir(parents=True,exist_ok=True);path=ROOT/(str(year)+".json")
    prior=json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if prior and prior.get("year")!=year:raise RuntimeError("Year checkpoint mismatch")
    inputs=dict(prior.get("inputs",{}));position={d:i for i,d in enumerate(ix.date)}
    todo=[d for d in dates if not valid_saved(inputs.get(d))]
    todo.sort(key=lambda d:(int((inputs.get(d) or {}).get("attempts",0)),d))
    print("INDEX_SESSIONS",len(dates),"CACHED",len(dates)-len(todo),"MISSING",len(todo),flush=True)
    errors=[];attempted=0;consecutive=0
    def snapshot():
        official=sum(valid_saved(inputs.get(d)) for d in dates)
        ready=[];failed=[]
        for d in dates:
            z=inputs.get(d) or {};i=position[d]
            if not valid_saved(z):
                failed.append({"date":d,"error":z.get("error",{"status":"NOT_FETCHED"}),"attempts":z.get("attempts",0)})
                continue
            try:
                v=build_historical(ix.iloc[:i+1],breadth_value=int(z["up"])/(int(z["up"])+int(z["down"]))*100,
                    foreign_value=float(z["foreign"]))
                if v["date"]!=d or not isinstance(v["score"],int) or not 0<=v["score"]<=100:
                    raise ValueError("Invalid day / Risk Score")
                v.update({"up":int(z["up"]),"down":int(z["down"]),"source":"OFFICIAL_TWSE_DATE_LOCKED"})
                ready.append(v)
            except Exception as e:failed.append({"date":d,"error":"SCORE:"+str(e)[:170]})
        coverage={"year":year,"period":{"start":start,"end":end},"tradingDays":len(dates),
          "officialValidDays":official,"riskScoredDays":len(ready),
          "missingDays":len(dates)-len(ready),"coveragePct":round(len(ready)/len(dates)*100,3),
          "complete":len(ready)==len(dates),"sources":{"upDown":"TWSE MI_INDEX reported daily stock advances/declines",
              "foreign":"TWSE BFI82U reported daily foreign flow","index":"Yahoo ^TWII daily OHLC"},
          "warning":"Never impute official missing days or use future/stale report date",
          "lastCheckpoint":datetime.now(ZoneInfo("Asia/Taipei")).isoformat()}
        atomic_json(path,{"year":year,"coverage":coverage,"dates":dates,"inputs":inputs,
          "riskRows":ready,"errors":failed,"version":"EXTENDED_MARKET_YEAR_V1"})
        return coverage
    if todo:
        with requests.Session() as session:
            for d in todo[:max_days]:
                attempted+=1;z=update_day(session,d,inputs.get(d),timeout=timeout);inputs[d]=z
                if z.get("ok"):consecutive=0
                else:
                    consecutive+=1
                    errors.append({"date":d,"error":z.get("error")})
                if attempted%12==0 or not z.get("ok"):snapshot()
                print("BACKFILL_DAY",year,attempted,d,"OK" if z.get("ok") else "FAIL",
                    str(z.get("error",""))[:165],flush=True)
                if consecutive>=9:
                    print("STOP_SOURCE_NOT_VERIFIABLE",year,"9 consecutive missing days",flush=True)
                    break
                if delay:time.sleep(delay)
    cover=snapshot()
    print("BACKFILL_YEAR_DONE",json.dumps({"year":year,"attempted":attempted,
        "valid":cover["officialValidDays"],"scored":cover["riskScoredDays"],
        "sessions":len(dates),"coverage":cover["coveragePct"],"complete":cover["complete"],
        "sampleErrors":errors[:2]},ensure_ascii=False),flush=True)
    return cover
if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--year",type=int,required=True)
    p.add_argument("--max-days",type=int,default=280);p.add_argument("--timeout",type=int,default=13)
    p.add_argument("--delay",type=float,default=.2);a=p.parse_args()
    if a.max_days<1 or a.delay<0:raise SystemExit("Invalid download limits")
    run(a.year,a.max_days,a.delay,a.timeout)
