"""S-A opening candidate archive. No future bars used, no raw OHLCV published."""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
import argparse, calendar, json, math, statistics, time as clock
from collections import defaultdict
TZ=ZoneInfo("Asia/Taipei")
SYMBOLS=(
 "2330.TW","2317.TW","2454.TW","2303.TW","3231.TW","2382.TW","2357.TW",
 "2360.TW","2376.TW","2345.TW","3711.TW","3037.TW","3661.TW","3443.TW",
 "2408.TW","2603.TW","2609.TW","2615.TW","2610.TW","2618.TW","2881.TW",
 "2882.TW","2884.TW","2885.TW","2886.TW","2891.TW","1301.TW","1303.TW",
 "1326.TW","2002.TW","2014.TW","3481.TW","2409.TW","2301.TW","2324.TW",
 "3034.TW","3017.TW","2379.TW","1504.TW","1519.TW","1605.TW","2356.TW",
 "2492.TW","5269.TW","3324.TWO","8299.TWO"
)
BENCHMARK="0050.TW"
def two_months_before(d):
    y,m=d.year,d.month-2
    if m<=0:y,m=y-1,m+12
    return d.replace(year=y,month=m,day=min(d.day,calendar.monthrange(y,m)[1]))
def download(symbol,today):
    import yfinance as yf
    ticker=yf.Ticker(symbol)
    daily=ticker.history(period="6mo",interval="1d",auto_adjust=False,prepost=False,timeout=20)
    opening=ticker.history(period="60d",interval="5m",auto_adjust=False,prepost=False,timeout=20)
    days={}; buckets=defaultdict(dict)
    for stamp,x in daily.iterrows():
        d=stamp.tz_convert(TZ).date() if stamp.tzinfo else stamp.date()
        if d>=today:continue
        o,h,l,c,v=map(float,(x.Open,x.High,x.Low,x.Close,x.Volume))
        if all(map(math.isfinite,(o,h,l,c,v))) and 0<l<=min(o,c)<=max(o,c)<=h and v>0:days[d]=(o,h,l,c,v)
    for stamp,x in opening.iterrows():
        if not stamp.tzinfo:continue
        s=stamp.tz_convert(TZ); t=s.strftime("%H:%M")
        if t not in ("09:00","09:05","09:10"):continue
        o,v=float(x.Open),float(x.Volume)
        if math.isfinite(o) and math.isfinite(v) and o>0 and v>0:buckets[s.date()][t]=(o,v)
    opens={d:(v["09:00"][0],sum(x[1] for x in v.values())) for d,v in buckets.items() if len(v)==3}
    return days,opens
def candidate(d,prior,days,opens,bench):
    """Returns (has sufficient input, candidate or None). Prior dates fixed by benchmark."""
    if len(prior)<22 or d not in opens or any(x not in days for x in prior[-22:]):return False,None
    prev=prior[-1]; close=days[prev][3]
    past=prior[-20:]; vol=[opens[x][1] for x in past if x in opens]
    if len(vol)<15:return False,None
    turnover=statistics.mean(days[x][3]*days[x][4] for x in past)
    atr=statistics.mean(max(days[prior[i]][1]-days[prior[i]][2],abs(days[prior[i]][1]-days[prior[i-1]][3]),abs(days[prior[i]][2]-days[prior[i-1]][3])) for i in range(-14,0))/close
    rel=close/days[prior[-6]][3]-bench[prev][3]/bench[prior[-6]][3]
    gap=opens[d][0]/close-1;rv=opens[d][1]/statistics.median(vol)
    if not (10<=close<=350 and turnover>=3e8 and .018<=atr<=.11 and rel<=-.02 and -.035<=gap<=.01 and rv>=1.3):return True,None
    return True,{"score":round(abs(rel)*100+.3*min(rv,5),5),"relative5_pctpt":round(rel*100,3),"gap_pct":round(gap*100,3),"rvol":round(rv,3),"atr_pct":round(atr*100,3),"turnover20_twd":round(turnover)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    now=datetime.now(TZ);today=now.date();start=two_months_before(today)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    old={}
    if a.output.exists():
        old=json.loads(a.output.read_text()).get("days",{})
    raw={};failures=[]
    for sym in (BENCHMARK,*SYMBOLS):
        try:
            ds,op=download(sym,today)
            if len(ds)<25 or not op:raise ValueError("missing history")
            raw[sym]=(ds,op)
        except Exception as e:failures.append(sym);print("FAILED",sym,type(e).__name__,flush=True)
        clock.sleep(.15)
    if BENCHMARK not in raw:raise SystemExit("Benchmark unavailable; no overwrite")
    bench,market_open=raw[BENCHMARK];sessions=sorted(bench)
    target=sorted({d for d in sessions if start<=d<today}|({today} if today in market_open and now.time()>=time(9,20) else set()))
    if not target:raise SystemExit("No market dates; no overwrite")
    out={}
    for d in target:
        prior=[x for x in sessions if x<d];rows=[];valid=0
        for sym in SYMBOLS:
            if sym not in raw:continue
            ds,op=raw[sym];ok,row=candidate(d,prior,ds,op,bench);valid+=ok
            if row:rows.append({"symbol":sym.split(".")[0],"market":"上市" if sym.endswith(".TW") else "上櫃",**row})
        rows.sort(key=lambda x:(-x["score"],x["symbol"]))
        coverage=valid/len(SYMBOLS)
        state="available" if coverage>=.8 else "insufficient_coverage"
        snap={"date":d.isoformat(),"status":state,"valid_symbols":valid,"pool_size":len(SYMBOLS),"qualified":len(rows),"rows":[{"rank":i+1,**x} for i,x in enumerate(rows[:10])] if state=="available" else []}
        # Preserve previously published qualified snapshots rather than revise with later data.
        previous=old.get(d.isoformat())
        if previous and previous.get("status")=="available":snap=previous
        out[d.isoformat()]=snap
    for k,v in old.items():
        if start.isoformat()<=k<=today.isoformat() and k not in out:out[k]=v
    out=dict(sorted(out.items()))
    result={"schema":"SHORT_A_TOP10_V1","generated_at":now.isoformat(),"start":start.isoformat(),"end":today.isoformat(),"benchmark":BENCHMARK,"source":"Yahoo daily and first three completed 5m bars","pool_size":len(SYMBOLS),"failed_symbols":failures,"historical_eligibility_verified":False,"days":out}
    a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+"\n")
    print("SHORT_A_HISTORY_SUMMARY",json.dumps({"first":min(out),"last":max(out),"dates":len(out),"available":sum(x["status"]=="available" for x in out.values()),"rows":sum(len(x["rows"]) for x in out.values()),"latest":out[max(out)]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
