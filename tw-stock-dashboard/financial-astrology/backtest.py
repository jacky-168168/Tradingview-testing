#!/usr/bin/env python3
"""Ex-post astrology event study. Uses REAL daily closes only; never synthesizes performance."""
from __future__ import annotations
import argparse
import bisect
import csv
import json
import io
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import math
import random
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from evidence import attach_evidence
from research_methods import global_fdr, regime_control, strategy_comparison
from g_overlay_research import compute_g_overlay

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
    # Never mix a still-forming local trading session into daily close history.
    local_today=datetime.now(timezone.utc).astimezone(ZoneInfo(next((
        zone for code,(symbol,zone,_) in MARKETS.items() if symbol==ticker
    ),"America/New_York"))).date()
    cap=min(asof,local_today-timedelta(days=1))
    for stamp, entry in table.iterrows():
        close=entry.get("Close")
        if close is None or not math.isfinite(float(close)) or stamp.date()>cap:
            continue
        rows.append((stamp.date(), float(close)))
    return clean_prices(rows)

def download_fred(series_id, asof):
    """FRED published daily index closes; only derived statistics leave CI."""
    if series_id not in {"NASDAQCOM","SP500"}:
        raise ValueError("Unapproved FRED series")
    url="https://fred.stlouisfed.org/graph/fredgraph.csv?"+urlencode({
        "id":series_id,"cosd":"1990-01-01","coed":asof.isoformat()})
    request=Request(url,headers={"User-Agent":"FinancialAstrologyResearch/1.0 (historical-statistics)"})
    with urlopen(request,timeout=35) as response:
        payload=response.read(5000000).decode("utf-8-sig")
    rows=list(csv.DictReader(io.StringIO(payload)))
    if not rows or series_id not in rows[0]:
        raise RuntimeError("FRED returned no valid daily CSV series "+series_id)
    out=[]
    for row in rows:
        text=row.get(series_id,"")
        if text in ("",".","NaN",None):
            continue
        day=date.fromisoformat(row.get("DATE") or row.get("observation_date") or row.get("date"))
        if day>asof:continue
        out.append((day,float(text)))
    return clean_prices(out)


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
    ci=None;p=None;excess_ci=None
    # Ex-post descriptive bootstrap: not a causal or out-of-sample test.
    if len(xs)>=8:
        boot=[statistics.mean(rng.choices(xs,k=len(xs))) for _ in range(1000)]
        ci=[percentile(boot,0.025),percentile(boot,0.975)]
        year_baselines=[statistics.mean(group) for group in matched]
        excess_observations=[x-b for x,b in zip(xs,year_baselines)]
        excess_boot=[statistics.mean(rng.choices(excess_observations,k=len(xs)))
                     for _ in range(1000)]
        excess_ci=[percentile(excess_boot,0.025),percentile(excess_boot,0.975)]
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
        "pValue":p,"confidence95":ci,"excessConfidence95":excess_ci,
        "holdout":oos,
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

def catalog_stats(catalog, prices, market_timezone):
    """Summary-only exploratory studies; no invented inferential p-values or trading signals."""
    result={}
    for family,definition in (catalog.get("studyFamilies") or {}).items():
        if family==EVENT_ID: continue  # main predeclared event has full statistical methods
        events=definition.get("events",[])
        horizons=[]
        for h in HORIZONS:
            observed,missing=returns_for_events(events,prices,market_timezone,h)
            n=len(observed)
            if n:
                yearly=defaultdict(list)
                closes=[p[1] for p in prices]
                for i in range(len(closes)-h):
                    yearly[prices[i][0].year].append(closes[i+h]/closes[i]-1)
                overall=[v for vals in yearly.values() for v in vals]
                baseline=sum(statistics.mean(yearly.get(date.fromisoformat(x["entryDate"]).year)
                    or overall) for x in observed)/n
                mean=statistics.mean(x["return"] for x in observed)
                win=sum(x["return"]>0 for x in observed)/n
            else:
                baseline=mean=win=None
            horizons.append({"horizonSessions":h,"sampleSize":n,"censoredEvents":missing,
                "meanReturn":mean,"winRate":win,"baselineReturn":baseline,
                "excessReturn":mean-baseline if n else None,
                "pValue":None,"globalFdrQValue":None,
                "evidence":{"level":"unvalidated","label":"僅探索，未驗證",
                            "direction":"無法判定",
                            "reason":"其他星象系列尚未通過跨事件、跨市場多重檢定和真正獨立樣本外驗證。"}})
        result[family]={"eventLabel":definition.get("label",family),
             "source":"Astronomy Engine 2.1.19 exact ephemeris + real daily market closes",
             "eventCount":len(events),"horizons":horizons,
             "status":"exploratory","noTradingSignal":True}
    return result


def build_report(events, market, prices, asof):
    ticker,tz,label=MARKETS[market]
    clean=clean_prices(prices)
    if clean[-1][0]>asof:
        raise ValueError("Historical prices contain future observations")
    if len(clean)<500:
        raise ValueError("Insufficient daily market history (<500 sessions)")
    # A stale quote feed must never be presented as current verified research.
    if (asof-clean[-1][0]).days>14:
        raise ValueError("Market history stale: last valid close "+clean[-1][0].isoformat())
    horizons=[stats(events,clean,tz,h) for h in HORIZONS]
    for row in horizons:
        horizon=row["horizonSessions"]
        samples,_=returns_for_events(events,clean,tz,horizon)
        regime=regime_control(samples,clean,horizon)
        row["regimeMatchedControl"]=regime
        # The original same-year random baseline is descriptive only, not our formal p-value.
        row["yearMatchedNaivePValue"]=row["pValue"]
        row["pValue"]=(regime.get("permutationPValue")
                       if regime.get("status")=="descriptive" else None)
        row["regimeMatchedExcessReturn"]=regime.get("meanExcessReturn")
        row["regimeMatchedCI95"]=regime.get("eventClusterBootstrap95")
    bh_fdr(horizons)
    attach_evidence(horizons)
    # Offline-only MA20 baseline; never writes into user's G/risk strategy code.
    strategy=strategy_comparison(clean,events,tz,event_to_session_index)
    return {"status":"ok","market":market,"ticker":ticker,"marketName":label,
        "currency":"index points","event":EVENT_ID,"timeZone":tz,
        "sampleStart":clean[0][0].isoformat(),"sampleEnd":clean[-1][0].isoformat(),
        "priceSampleCount":len(clean),"historicalEventsFound":len(events),
        "indexReturnBasis":("gross-dividend-reinvested-performance" if market=="DAX" else "price-only"),
        "crossMarketComparable":False,"strategyComparison":strategy,
        "source":"Yahoo Finance via yfinance; daily unadjusted index Close; retrieval is best-effort",
        "entryRule":"First trading session strictly after event's exchange-local calendar date, close to close",
        "horizons":horizons,"orbDeg":2,"orbSensitivityStatus":"not-validated",
        "restrictions":["Rare events; significance is unreliable for small N.",
          "Overlapping holding periods and macro regimes are not causal evidence.",
          "Price indices exclude dividends; Yahoo Finance data is not guaranteed."],
        "sampleOutOfSample":"chronological holdout when N>=20; otherwise unavailable",
        "researchLimitations":["DAX reflects gross dividend reinvestment, others are generally price indices.",
                               "MA20+astrology is close-to-close observational, not a trading recommendation."]}

def build_all(events, asof, csv_paths=None, catalog=None, g_trades=None, g_executive=None):
    reports={}
    catalog_reports={}
    g_overlay={"status":"unavailable","reason":"Existing G closed-trade file not configured"}
    for market,(ticker,tz,label) in MARKETS.items():
        try:
            path=(csv_paths or {}).get(market)
            source="User-supplied real daily close CSV; manual provenance required"
            if path:
                prices=parse_prices_csv(Path(path))
            else:
                source="Yahoo Finance historical index daily Close (via yfinance)"
                try:
                    prices=download_prices(ticker,date(1990,1,1),asof)
                except Exception as first:
                    fred={"NASDAQ":"NASDAQCOM","SP500":"SP500"}.get(market)
                    if not fred:
                        raise
                    try:
                        prices=download_fred(fred,asof)
                        source=("FRED / "+fred+" daily close; original Nasdaq / S&P rights apply; "+
                            "source https://fred.stlouisfed.org/series/"+fred)
                    except Exception as second:
                        raise RuntimeError("Yahoo: "+str(first)[:95]+
                            "; FRED: "+str(second)[:95]) from second
            reports[market]=build_report(events,market,prices,asof)
            reports[market]["source"]=source
            if catalog is not None:
                catalog_reports[market]=catalog_stats(catalog,prices,MARKETS[market][1])
                if market=="TAIEX" and g_trades and g_executive:
                    try:
                        g_overlay=compute_g_overlay(catalog,prices,g_trades,g_executive)
                    except Exception as exc:
                        g_overlay={"status":"unavailable","reason":str(exc)[:280]}
        except Exception as exc:
            reports[market]={"status":"unavailable","ticker":ticker,
                "errorType":type(exc).__name__,"message":str(exc)[:280],
                "horizons":[]}
    tested=global_fdr(reports)
    # Final confidence labels must use global market x horizon multiplicity.
    for result in reports.values():
        if result.get("status")=="ok":attach_evidence(result["horizons"])
    return {"schemaVersion":3,"generatedAt":datetime.now(timezone.utc).isoformat(),
        "asOf":asof.isoformat(),"event":EVENT_ID,"methodVersion":"quantitative-evidence-v3",
        "multipleTesting":{"family":"all available markets x nine horizons",
                           "hypotheses":tested,"method":"Benjamini-Hochberg global FDR"},
        "hypothesis":"Mars–Jupiter geocentric exact conjunction",
        "researchOnly":True,"strategySignal":False,"reports":reports,
        "additionalEventStudies":catalog_reports if catalog is not None else {},
        "gOverlay":g_overlay,
        "additionalEvidenceStatus":"descriptive-only; no inferential significance or OOS proof"}

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--events",required=True)
    cli.add_argument("--catalog",help="Optional predeclared event_catalog.json for descriptive event families")
    cli.add_argument("--g-trades",help="Existing readonly G selected cash-ledger archive")
    cli.add_argument("--g-executive",help="Existing G model selection metadata")
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
        if report.get("status")=="ok":
            tested=global_fdr({args.market:report})
            attach_evidence(report["horizons"])
        else:tested=0
        payload={"schemaVersion":3,"generatedAt":datetime.now(timezone.utc).isoformat(),
            "asOf":asof.isoformat(),"event":EVENT_ID,"methodVersion":"quantitative-evidence-v3",
            "multipleTesting":{"family":"single market offline CLI only",
                               "hypotheses":tested,"method":"Benjamini-Hochberg"},
            "researchOnly":True,
            "strategySignal":False,"reports":{args.market:report}}
    else:
        catalog=(json.loads(Path(args.catalog).read_text(encoding="utf-8")) if args.catalog else None)
        payload=build_all(events,asof,catalog=catalog,
                          g_trades=args.g_trades,g_executive=args.g_executive)
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({key:r["status"] for key,r in payload["reports"].items()}))
if __name__ == "__main__": main()
