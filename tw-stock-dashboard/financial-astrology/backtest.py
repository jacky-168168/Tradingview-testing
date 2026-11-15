#!/usr/bin/env python3
"""Ex-post astrology event study. Uses REAL daily closes only; never synthesizes performance."""
from __future__ import annotations
import argparse
import bisect
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HORIZONS = (1, 3, 5, 10, 20, 60, 90, 180, 360)
MARKETS = {
    "NASDAQ": ("^IXIC", "America/New_York", "Nasdaq Composite (price index)"),
    "SP500": ("^GSPC", "America/New_York", "S&P 500 (price index)"),
    "DAX": ("^GDAXI", "Europe/Berlin", "DAX (Yahoo historical close)"),
    "FTSE100": ("^FTSE", "Europe/London", "FTSE 100 (price index)"),
    "CAC40": ("^FCHI", "Europe/Paris", "CAC 40 (price index)"),
    "TAIEX": ("^TWII", "Asia/Taipei", "TAIEX (price index)"),
}
EVENT_ID = "mars_jupiter_conjunction"
SEED = 20261115

def iso_datetime(value: str) -> datetime:
    value = value.replace("Z", "+00:00")
    d = datetime.fromisoformat(value)
    if d.tzinfo is None:
        raise ValueError("Event UTC timestamp must carry offset")
    return d.astimezone(timezone.utc)

def parse_prices_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    pairs = [(date.fromisoformat(x["date"]), float(x["close"])) for x in rows]
    return clean_prices(pairs)

def clean_prices(pairs):
    prices = []
    last_date = None
    for day, close in sorted(pairs):
        if day == last_date:
            raise ValueError("Duplicate price date: "+day.isoformat())
        if not (math.isfinite(close) and close > 0):
            raise ValueError("Non-positive or non-finite price")
        if day.weekday() >= 5:
            raise ValueError("Weekend daily close: "+day.isoformat())
        prices.append((day, close))
        last_date = day
    if not prices:
        raise ValueError("No historical market prices")
    return prices

def download_prices(ticker, earliest, asof):
    try:
        import yfinance as yf
    except ImportError as ex:
        raise RuntimeError("yfinance is required for live price retrieval") from ex
    # end is exclusive; index timezone is handled only for the exchange's local date.
    table = yf.Ticker(ticker).history(start=earliest.isoformat(),
        end=(asof + timedelta(days=1)).isoformat(), interval="1d",
        auto_adjust=False, actions=False, raise_errors=True)
    if table is None or table.empty:
        raise RuntimeError("No daily prices returned for "+ticker)
    rows=[]
    for stamp, entry in table.iterrows():
        close = entry.get("Close")
        if close is None or not math.isfinite(float(close)):
            continue
        rows.append((stamp.date(), float(close)))
    return clean_prices(rows)

def event_to_session_index(event, days, market_tz):
    event_utc = iso_datetime(event["exactUtc"])
    local_day = event_utc.astimezone(ZoneInfo(market_tz)).date()
    # Conservative: first full trading session AFTER local event date;
    # enter at that session's close, then exit at close H sessions later.
    idx = bisect.bisect_right(days, local_day)
    return idx if idx < len(days) else None

def returns_for_events(events, prices, market_tz, horizon, asof=None):
    days = [p[0] for p in prices]
    closes = [p[1] for p in prices]
    valid=[]
    censored=0
    for e in sorted(events, key=lambda x:x["exactUtc"]):
        event_day = iso_datetime(e["exactUtc"]).date()
        if asof is not None and event_day > asof:
            censored+=1
            continue
        start = event_to_session_index(e, days, market_tz)
        if start is None or start + horizon >= len(prices):
            censored+=1
            continue
        path=closes[start:start+horizon+1]
        peak=path[0]
        dd=0.0
        for value in path:
            peak=max(peak,value)
            dd=min(dd,value/peak-1.0)
        ret=path[-1]/path[0]-1.0
        valid.append({"eventUtc":e["exactUtc"],"entryDate":days[start].isoformat(),
            "exitDate":days[start+horizon].isoformat(),"return":ret,
            "windowMaxDrawdown":dd,"entryIndex":start})
    return valid,censored

def percentile(values, q):
    values=sorted(values)
    if not values:return None
    ix=(len(values)-1)*q
    lower=int(ix); upper=min(lower+1,len(values)-1)
    return values[lower]*(1-(ix-lower))+values[upper]*(ix-lower)

def stats(events, prices, tz, horizon, seed=SEED):
    samples,censored=returns_for_events(events,prices,tz,horizon)
    if not samples:
        return {"horizonSessions":horizon,"status":"insufficient-data","sampleSize":0,
                "censoredEvents":censored,"meanReturn":None,"winRate":None,
                "baselineReturn":None,"excessReturn":None,"pValue":None,"confidence95":None}
    xs=[x["return"] for x in samples]
    closes=[p[1] for p in prices]
    daily=[closes[i+horizon]/closes[i]-1 for i in range(len(closes)-horizon)]
    years=[prices[i][0].year for i in range(len(daily))]
    by_year=defaultdict(list)
    for y,value in zip(years,daily):
        by_year[y].append(value)
    matched=[by_year.get(date.fromisoformat(x["entryDate"]).year,daily) or daily for x in samples]
    baseline=sum(statistics.mean(group) for group in matched)/len(matched)
    mean=statistics.mean(xs)
    rng=random.Random(seed+horizon)
    ci=None;p=None
    # No statistical significance claim for rare observations.
    if len(xs)>=8:
        boot=[statistics.mean(rng.choices(xs,k=len(xs))) for _ in range(1000)]
        ci=[percentile(boot,0.025),percentile(boot,0.975)]
        n=999
        dif=abs(mean-baseline)
        exceed=sum(abs(statistics.mean([rng.choice(g) for g in matched])-baseline)>=dif for _ in range(n))
        p=(exceed+1)/(n+1)
    count=len(xs)
    oos=None
    if count>=20:
        cut=int(count*0.7)
        if cut>=8 and count-cut>=6:
            oos={"method":"chronological 70/30 observational split; no parameter fitting",
                "trainCount":cut,"holdoutCount":count-cut,
                "trainMean":statistics.mean(xs[:cut]),
                "holdoutMean":statistics.mean(xs[cut:]),
                "holdoutWinRate":sum(x>0 for x in xs[cut:])/(count-cut)}
    return {"horizonSessions":horizon,"status":"exploratory" if count<30 else "descriptive",
        "sampleSize":count,"censoredEvents":censored,
        "meanReturn":mean,"medianReturn":statistics.median(xs),
        "winRate":sum(x>0 for x in xs)/count,"meanMaxDrawdown":statistics.mean(x["windowMaxDrawdown"] for x in samples),
        "baselineReturn":baseline,"excessReturn":mean-baseline,
        "pValue":p,"confidence95":ci,"holdout":oos,
        "events":[{"eventUtc":x["eventUtc"],"entryDate":x["entryDate"],
                   "exitDate":x["exitDate"],"return":x["return"],
                   "windowMaxDrawdown":x["windowMaxDrawdown"]} for x in samples]}

def bh_fdr(rows):
    # Multiplicity correction over nine tested horizons per market.
    ranked=sorted([(r["pValue"],i) for i,r in enumerate(rows) if r.get("pValue") is not None])
    m=len(ranked)
    adj=[None]*len(rows)
    run=1.0
    for reverse_index in range(m-1,-1,-1):
        p,idx=ranked[reverse_index]
        run=min(run,p*m/(reverse_index+1))
        adj[idx]=run
    for row,q in zip(rows,adj):
        row["fdrQValue"]=q
        row["significanceClaim"]=False  # V1 is hypothesis-generating, never causal proof.

def build_report(events, market, prices, asof):
    ticker,tz,label=MARKETS[market]
    clean=clean_prices(prices)
    if clean[-1][0]>asof:
        raise ValueError("Historical prices contain future observations")
    if len(clean)<500:
        raise ValueError("Insufficient daily market history (<500 sessions)")
    horizons=[stats(events,clean,tz,h) for h in HORIZONS]
    bh_fdr(horizons)
    return {"status":"ok","market":market,"ticker":ticker,"marketName":label,
        "currency":"index points","event":EVENT_ID,"timeZone":tz,
        "sampleStart":clean[0][0].isoformat(),"sampleEnd":clean[-1][0].isoformat(),
        "source":"Yahoo Finance via yfinance; daily unadjusted index Close; retrieval is best-effort",
        "entryRule":"First trading session strictly after event's exchange-local calendar date, close to close",
        "horizons":horizons,"orbDeg":2,"orbSensitivityStatus":"not-validated",
        "restrictions":["Rare events; significance is unreliable for small N.",
          "Overlapping holding periods and macro regimes are not causal evidence.",
          "Price indices exclude dividends; Yahoo Finance data is not guaranteed."],
        "sampleOutOfSample":"chronological holdout when N>=20; otherwise unavailable"}

def build_all(events, asof, csv_paths=None):
    reports={}
    for market,(ticker,tz,label) in MARKETS.items():
        try:
            path=(csv_paths or {}).get(market)
            prices=parse_prices_csv(Path(path)) if path else download_prices(ticker,date(1990,1,1),asof)
            reports[market]=build_report(events,market,prices,asof)
        except Exception as exc:
            reports[market]={"status":"unavailable","ticker":ticker,
                "errorType":type(exc).__name__,"message":str(exc)[:280],
                "horizons":[]}
    return {"schemaVersion":1,"generatedAt":datetime.now(timezone.utc).isoformat(),
        "asOf":asof.isoformat(),"event":EVENT_ID,"hypothesis":"Mars–Jupiter geocentric exact conjunction",
        "researchOnly":True,"strategySignal":False,"reports":reports}

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--events",required=True)
    cli.add_argument("--output",required=True)
    cli.add_argument("--as-of",default=datetime.now(timezone.utc).date().isoformat())
    cli.add_argument("--prices",help="Optional CSV with date,close (offline single market)")
    cli.add_argument("--market",default="NASDAQ",choices=MARKETS)
    args=cli.parse_args()
    events=json.loads(Path(args.events).read_text(encoding="utf-8"))["events"]
    asof=date.fromisoformat(args.as_of)
    if args.prices:
        try: report=build_report(events,args.market,parse_prices_csv(Path(args.prices)),asof)
        except Exception as exc:
            report={"status":"unavailable","message":str(exc)}
        payload={"schemaVersion":1,"generatedAt":datetime.now(timezone.utc).isoformat(),
            "asOf":asof.isoformat(),"event":EVENT_ID,"researchOnly":True,
            "strategySignal":False,"reports":{args.market:report}}
    else: payload=build_all(events,asof)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:r["status"] for key,r in payload["reports"].items()}))
if __name__ == "__main__": main()
