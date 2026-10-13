"""Forward G-strength lifecycle study. The cohort is fixed at signal date; later
pocket appearances are OUTCOMES, never entry filters. Requires FULL daily
unmodified Top20 snapshots, not merely the selected strategy's Top3 signals.
"""
from __future__ import annotations
from collections import defaultdict
from statistics import mean,median

BUCKETS=("fresh","repeat_1_3","repeat_4_6","repeat_7_9","repeat_10_plus")
def bucket(n):
    if n is None or int(n)<0:raise ValueError("missing/invalid previous Top20 frequency")
    n=int(n)
    return "fresh" if n==0 else "repeat_1_3" if n<=3 else "repeat_4_6" if n<=6 else "repeat_7_9" if n<=9 else "repeat_10_plus"

def lifecycle_audit(trades,dates,pockets,horizon=10,lookback=10):
    """Complete-horizon, same-symbol non-overlap entry analysis.

    dates and pockets must correspond 1:1 to each completed *signal* session.
    pocket[d] is ORIGINAL reference model Top20 observed at that day's close.
    For entry on day t, its cohort is the PREVIOUS 10 completed sessions only.
    Follow-up stages are observed on days t+1 .. t+H when the stock actually
    appears in the ORIGINAL Top20 on that day; prior10 frequency at followup
    day j uses strictly d<j (not day j itself). No day beyond study end.
    """
    if horizon<=0 or lookback<=0:raise ValueError("positive horizons required")
    if len(dates)!=len(pockets):raise ValueError("full historical Top20 pockets are required")
    if sorted(dates)!=list(dates) or len(set(dates))!=len(dates):raise ValueError("invalid daily chronology")
    ix={d:i for i,d in enumerate(dates)}
    ordered=sorted(trades,key=lambda x:(x["signalDate"],x.get("rank",99),x["code"]))
    eligible, censored, ignored=[],0,0
    last_entry={}
    for t in ordered:
        d=t.get("signalDate");i=ix.get(d)
        if i is None:continue
        p=(t.get("persistence") or {}).get("past10Top20")
        ret=t.get("ret"+str(horizon))
        if p is None or ret is None:continue
        # Complete future *pocket* observation is mandatory, not merely forward price availability.
        if i+horizon>=len(dates):
            censored+=1;continue
        code=t["code"]
        if code in last_entry and i<last_entry[code]+horizon:
            ignored+=1;continue
        last_entry[code]=i
        counts={}
        hits={4:None,7:None,10:None}
        seen_days=0
        for j in range(i+1,i+horizon+1):
            if code not in pockets[j]:continue
            seen_days+=1
            prior=sum(code in pockets[k] for k in range(max(0,j-lookback),j))
            counts[j-i]=prior
            for threshold in hits:
                if hits[threshold] is None and prior>=threshold:hits[threshold]=j-i
        eligible.append({"date":d,"code":code,"rank":t.get("rank"),"entryBucket":bucket(p),
                         "past10AtEntry":int(p),"ret":float(ret),
                         "futureTop20Days":seen_days,"futureMaxPrior10":max(counts.values()) if counts else None,
                         "firstReach4":hits[4],"firstReach7":hits[7],"firstReach10":hits[10]})
    def stats(rows):
        values=[x["ret"] for x in rows];n=len(rows)
        if not n:return {"n":0,"avgGross":None,"medianGross":None,"win":None,"reach4":0,"reach7":0,"reach10":0,"rateReach4":None,"rateReach7":None,"rateReach10":None,"avgDaysTo7":None,"distinctStocks":0}
        reach={x:sum(z["firstReach"+str(x)] is not None for z in rows) for x in (4,7,10)}
        reached7=[z["firstReach7"] for z in rows if z["firstReach7"] is not None]
        return {"n":n,"avgGross":round(mean(values),2),"medianGross":round(median(values),2),
                "win":round(100*sum(x>0 for x in values)/n,1),
                **{"reach"+str(i):reach[i] for i in (4,7,10)},
                **{"rateReach"+str(i):round(100*reach[i]/n,1) for i in (4,7,10)},
                "avgDaysTo7":round(mean(reached7),1) if reached7 else None,
                "distinctStocks":len({z["code"] for z in rows})}
    groups={k:stats([x for x in eligible if x["entryBucket"]==k]) for k in BUCKETS}
    # Ex-post reached7 is NOT observable at entry; purely descriptive outcome.
    early=[x for x in eligible if x["entryBucket"]=="repeat_1_3"]
    early_success=[x for x in early if x["firstReach7"] is not None]
    early_other=[x for x in early if x["firstReach7"] is None]
    return {"horizon":horizon,"method":"Future original Top20 snapshots on completed sessions; strictly past10 frequency, same-stock H-session entry cooldown; skip incomplete future observation. The subsequent stage is an outcome, NOT an entry feature.",
            "inputSignalRows":len(ordered),"newTrades":len(eligible),"suppressedOverlappingSignals":ignored,
            "censoredNearEnd":censored,"byEntryBucket":groups,
            "earlyEntryOutcomes":{"reached7":stats(early_success),"notObservedReach7":stats(early_other),
                "warning":"Reached7 is hindsight-known, not a deployable selection filter; notObserved includes stocks that might reach after the observation window."},
            "entries":eligible}
