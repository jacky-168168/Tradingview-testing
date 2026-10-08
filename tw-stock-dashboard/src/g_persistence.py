"""G pocket-list persistence; historical-only features from the previous trading days.
The same stock may remain on a watchlist, while trade dedup is evaluated separately.
Do not use the current day's or any future ranking in the persistence feature.
"""
from __future__ import annotations
from collections import defaultdict
import numpy as np

WINDOW=10;TOP3_WINDOW=5;STREAK_CAP=5;BONUS_MAX=7.0
def persistence_features(code,prior_pockets,current_base_score,lookback=WINDOW):
    """prior_pockets: chronological lists of {code: {rank, score}} for completed days only."""
    recent=prior_pockets[-lookback:]
    ten=sum(code in day for day in recent)
    five=sum(code in day and day[code]["rank"]<=3 for day in recent[-TOP3_WINDOW:])
    streak=0
    for day in reversed(recent):
        if code not in day:break
        streak+=1
    earlier=[day[code]["score"] for day in recent[-5:] if code in day]
    # Score trend can contribute at most 10% and is zero without a prior appearance.
    trend=0.0
    if earlier:trend=max(0.,min(1.,(float(current_base_score)-float(earlier[-1]))/5.))
    strength=45.*ten/lookback+25.*five/TOP3_WINDOW+20.*min(streak,STREAK_CAP)/STREAK_CAP+10.*trend
    strength=max(0.,min(100.,strength))
    return {"past10Top20":int(ten),"past5Top3":int(five),"priorStreak":int(streak),"scoreChange":round(float(current_base_score-earlier[-1]),2) if earlier else None,"strength":round(strength,2),"bonus":round(BONUS_MAX*strength/100.,4)}

def pocket_snapshot(ranked):
    """Snapshot original unmodified model's top20 at close; not a persistence-ranked feedback loop."""
    return {x["code"]:{"rank":i+1,"score":float(x["baselineScore"])} for i,x in enumerate(ranked[:20])}

def repeat_audit(trades,calendar,horizon):
    """Distinct open positions per code (once each horizon). Signal quality remains in separate metrics."""
    pos={d:i for i,d in enumerate(calendar)}
    seen_at={};eligible=[];blocked=[];retcol=f"ret{horizon}";stock_counts=defaultdict(int)
    for t in sorted(trades,key=lambda z:(z["signalDate"],z["rank"])):
        if t.get(retcol) is None:continue
        code=t["code"];i=pos[t["signalDate"]];stock_counts[code]+=1
        if code in seen_at and i<seen_at[code]+horizon:
            blocked.append(t)
        else:
            seen_at[code]=i;eligible.append(t)
    def stats(a):
        r=[float(x[retcol]) for x in a]
        if not r:return {"n":0,"avgGross":None,"win":None}
        return {"n":len(r),"avgGross":round(float(np.mean(r)),2),"win":round(100*sum(x>0 for x in r)/len(r),1)}
    return {"horizon":horizon,"raw":stats([x for x in trades if x.get(retcol)is not None]),"newTrades":stats(eligible),"overlappingSignalsSuppressed":len(blocked),"distinctStocks":len(stock_counts),"method":"Skip a new entry of the same stock until the previous H-day holding ends; other stocks remain eligible; diagnostic only, not a cash-constrained portfolio."}

def pocket_segment_stats(trades,horizon):
    """Conditional returns by PREVIOUS pocket frequency, not same-day or future rank."""
    groups={"fresh":[],"emerging_1_3":[],"persistent_4plus":[]}
    for row in trades:
        r=row.get(f"ret{horizon}");p=(row.get("persistence") or {}).get("past10Top20")
        if r is None or p is None:continue
        key="fresh" if p==0 else "emerging_1_3" if p<=3 else "persistent_4plus"
        groups[key].append(float(r))
    result={}
    for k,rs in groups.items():
        result[k]={"n":len(rs),"avgGross":round(float(np.mean(rs)),2) if rs else None,"win":round(100*sum(x>0 for x in rs)/len(rs),1) if rs else None}
    return result
