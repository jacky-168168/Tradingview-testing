"""Conservative market-regime controls, global multiple testing and offline-only strategies.

Neither celestial events nor this code produce trading instructions. Controls are ex-post
descriptions; real market timestamps and close-only execution are never backfilled.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import date, datetime, timezone
from math import isfinite, sqrt, prod
from random import Random
import statistics

FEE_PER_SIDE_BPS=5.0  # Study assumption; NOT an existing user strategy cost.

def global_fdr(reports):
    """BH across every successfully evaluated market x horizon, not each market alone."""
    entries=[]
    for market,result in reports.items():
        if result.get("status")!="ok":continue
        for item in result.get("horizons",[]):
            p=item.get("pValue")
            if isinstance(p,(float,int)) and isfinite(p) and 0<=p<=1:
                entries.append((float(p),market,item))
    entries.sort(key=lambda x:x[0])
    total=len(entries)
    q=1.0
    for i in range(total-1,-1,-1):
        p,_,row=entries[i]
        q=min(q,p*total/(i+1))
        row["globalFdrQValue"]=q
        row["globalFdrHypotheses"]=total
        row["significanceClaim"]=False
    for result in reports.values():
        for row in result.get("horizons",[]):
            row.setdefault("globalFdrQValue",None)
            row.setdefault("globalFdrHypotheses",total)
    return total

def _features(prices):
    """MA60 sign and trailing 20-day realized volatility, no future prices."""
    close=[p[1] for p in prices]
    info=[]
    for i in range(len(close)):
        if i<61:
            info.append(None);continue
        trend=close[i]>statistics.mean(close[i-59:i+1])
        gains=[close[j]/close[j-1]-1 for j in range(i-19,i+1)]
        vol=statistics.stdev(gains)
        info.append((trend,vol))
    return info

def regime_control(events,prices,horizon,seed=20261116,draws=1000):
    """Year+MA60 trend+trailing volatility matched, event-purged spaced comparisons.
    Return null explicitly when a matched regime has inadequate controls.
    """
    close=[p[1] for p in prices]
    features=_features(prices)
    event_entries=[e["entryIndex"] for e in events if e.get("entryIndex") is not None]
    if len(events)<3 or len(prices)<100+horizon:
        return {"status":"insufficient","matchedEvents":0,"controlsPerEvent":[],
                "reason":"Not enough events or historical index closes."}
    # Event windows are purged by H sessions on both sides to avoid overlapping returns.
    blocked=set()
    for idx in event_entries:
        blocked.update(range(max(61,idx-horizon),min(len(close)-horizon,idx+horizon+1)))
    by_year=defaultdict(list)
    for i in range(61,len(close)-horizon):
        if i in blocked or features[i] is None:continue
        by_year[prices[i][0].year].append(i)
    rng=Random(seed+horizon)
    groups=[]
    for event in events:
        i=event["entryIndex"]
        if i<61 or i+horizon>=len(close) or features[i] is None:continue
        year=prices[i][0].year
        pool=by_year.get(year,[])
        if not pool:continue
        trend,vol=features[i]
        controls=[j for j in pool if features[j][0]==trend
                  and abs(features[j][1]-vol)<=max(vol*.5,.0001)]
        if len(controls)<5:continue
        # Keep comparison starts separated by a minimum of H/2 sessions
        # to reduce overlapping return windows and serial-dependence.
        stride=max(1,horizon//2)
        spaced=[]
        for j in sorted(controls):
            if not spaced or j-spaced[-1]>=stride:spaced.append(j)
        if len(spaced)<3:continue
        groups.append((close[i+horizon]/close[i]-1,
                       [close[j+horizon]/close[j]-1 for j in spaced]))
    if len(groups)<5:
        return {"status":"insufficient","matchedEvents":len(groups),
                "controlsPerEvent":[len(x[1]) for x in groups],
                "reason":"Fewer than 5 events with same-year, same-trend and similar-volatility controls."}
    observed=statistics.mean([event-statistics.mean(pool) for event,pool in groups])
    null=[]
    for _ in range(draws):
        null.append(statistics.mean([rng.choice(pool)-statistics.mean(pool)
                                     for _,pool in groups]))
    extreme=sum(abs(x)>=abs(observed) for x in null)
    p=(extreme+1)/(draws+1)
    # Cluster bootstrap at the event level: does not assume daily independent returns.
    delta=[e-statistics.mean(pool) for e,pool in groups]
    boot=[statistics.mean(rng.choices(delta,k=len(delta))) for _ in range(draws)]
    boot.sort()
    return {"status":"descriptive","matchedEvents":len(groups),
            "controlsPerEvent":[len(x[1]) for x in groups],
            "meanExcessReturn":observed,
            "permutationPValue":p,
            "eventClusterBootstrap95":[boot[int(.025*(draws-1))],boot[int(.975*(draws-1))]],
            "matching":"calendar-year + prior MA60 trend + trailing20-session volatility ±50%",
            "purge":"exclude control starts inside ±H sessions of any event; control starts >=H/2 apart",
            "limitations":"Post-hoc regime matching; calendar clustering and data-mining may remain; no causal claim"}

def strategy_comparison(prices, events, market_tz, event_to_session_index,
                        horizon=20,fee_bps=FEE_PER_SIDE_BPS,oos_start=date(2020,1,1)):
    """Close-to-close MA20, MA20+astronomical gate and passive index benchmark.
    At t close, signal uses information only through close t; held from t to t+1.
    Cost charged when entering/exiting at that signal close, not tick execution.
    """
    closes=[x[1] for x in prices]
    dates=[x[0] for x in prices]
    starts=[]
    for event in events:
        j=event_to_session_index(event,dates,market_tz)
        if j is not None and j+horizon<len(prices):starts.append(j)
    starts=set(starts)
    gate=[False]*len(prices)
    for j in starts:
        for t in range(j,min(len(gate),j+horizon)):gate[t]=True
    strategies={"passive":[],"ma20":[],"ma20_plus_astrology":[]}
    positions={"passive":False,"ma20":False,"ma20_plus_astrology":False}
    trades=dict.fromkeys(strategies,0)
    exposure=dict.fromkeys(strategies,0)
    sessions=[]
    for i in range(20,len(closes)-1):
        # Signal computed from close i; the next close-to-close return is i->i+1.
        ma=statistics.mean(closes[i-19:i+1])
        signals={"passive":True,"ma20":closes[i]>ma,
                 "ma20_plus_astrology":closes[i]>ma and gate[i]}
        gain=closes[i+1]/closes[i]-1
        sessions.append(dates[i+1])
        for name,enabled in signals.items():
            changed=enabled!=positions[name]
            cost=(fee_bps/10000) if changed else 0.0
            strategies[name].append((gain if enabled else 0.0)-cost)
            trades[name]+=bool(changed and enabled)
            exposure[name]+=bool(enabled)
            positions[name]=enabled
    def metrics(daily):
        if not daily:return None
        wealth=1.0;max_wealth=1.0;dd=0.0
        for value in daily:
            wealth*=1+value
            max_wealth=max(wealth,max_wealth)
            dd=min(dd,wealth/max_wealth-1)
        avg=statistics.mean(daily)
        sd=statistics.stdev(daily) if len(daily)>1 else 0
        downside=sqrt(sum(min(0,x)**2 for x in daily)/len(daily))
        years=len(daily)/252
        ann=wealth**(1/years)-1 if years and wealth>0 else None
        return {"observations":len(daily),"totalReturn":wealth-1,"cagr":ann,
                "sharpe":avg/sd*sqrt(252) if sd>0 else None,
                "sortino":avg/downside*sqrt(252) if downside>0 else None,
                "maxDrawdown":dd,
                "calmar":ann/abs(dd) if dd<0 and ann is not None else None}
    output={}
    first_oos=next((i for i,d in enumerate(sessions) if d>=oos_start),len(sessions))
    for name,series in strategies.items():
        output[name]={"all":metrics(series),"since2020":metrics(series[first_oos:]),
            "entryCount":trades[name],"exposureFraction":exposure[name]/max(1,len(series))}
    return {"status":"observational_only","costBpsPerSide":fee_bps,"eventHorizonSessions":horizon,
            "signalTiming":"close(t) -> return from close(t) to close(t+1); no intraday fills",
            "baseline":"passive index and MA20 long/flat",
            "test":"MA20+event-window long/flat, no parameter fitting",
            "sampleOutOfSample":"since2020 descriptive only; not independent after research selection",
            "eventStarts":len(starts),"report":output,
            "limitations":["Index values are not necessarily directly tradeable.",
                           "Dividend conventions differ across indices.",
                           "Short event windows can produce too few trades for meaningful Sharpe."]}
