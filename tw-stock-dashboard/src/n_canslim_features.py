"""N: strict CANSLIM-ish fundamental growth + price strength, as-of safe dates.

This module only uses revised historical MOPS bulk files with a conservative
availability-from date; it never treats fiscal year/quarter END as announcement.
"Point in time" here is conservative release-delay PROXY, NOT verified issuer
filing timestamp and NOT immutable filing revision. This caveat is mandatory.
"""
from __future__ import annotations
import bisect,collections,json,math
from pathlib import Path
import numpy as np,pandas as pd
from yahoo_cache import to_symbol
from n_fundamental_archive import quarter_safe_date,month_safe_date
FEATURE_NAMES=("epsYtdGrowthPct","revenueYoYPct","revenueHighRatioPct",
    "rsPercentile","near52WeekHighPct","rs63","rs126","rs252","volRatio",
    "aboveMA50Pct","aboveMA200Pct","ret20Pct","ret5Pct","turnoverB",
    "marketScore","marketBreadth","marketRet5","marketRet20","marketForeign")
RULES={"EPS_YTD_YOY_MIN_PCT":20,"REV_MONTH_YOY_MIN_PCT":10,
    "REV_12MO_HIGH_MIN_RATIO":.90,"RS_CROSS_SECTION_MIN_PERCENTILE":80,
    "CLOSE_TO_52WK_HIGH_MIN_RATIO":.85,"MIN_LIQUIDITY_BILLION_TWD":.8,
    "MIN_PRICE_TWD":10,"MIN_52W_SESSIONS":200,"MAX_CONSERVATIVE_REV_AGE_DAYS":80,
    "MAX_CONSERVATIVE_EPS_AGE_DAYS":260}
def market_key(market):
    return "sii" if market=="上市" else "otc" if market=="上櫃" else None
def require_numbers(rows,keys):
    for row in rows:
        if any(k not in row for k in keys):raise RuntimeError("Malformed official fundamental record")
class FundamentalIndex:
    def __init__(self,revenue,eps):
        require_numbers(revenue,("code","market","year","month","revenue","availableFrom"))
        require_numbers(eps,("code","market","year","quarter","epsYtd","availableFrom"))
        self.rev={};self.eps={};self.coverage=collections.Counter()
        byrev=collections.defaultdict(list);byeps=collections.defaultdict(list)
        for z in revenue:
            code=str(z["code"]);market=z["market"];y=int(z["year"]);m=int(z["month"]);v=float(z["revenue"])
            if not (0<v<1e20) or z["availableFrom"]!=month_safe_date(y,m):raise RuntimeError("Invalid month provenance "+str(z))
            byrev[(market,code)].append({"date":str(z["availableFrom"]),"year":y,"month":m,"revenue":v})
        for z in eps:
            code=str(z["code"]);market=z["market"];y=int(z["year"]);q=int(z["quarter"]);v=float(z["epsYtd"])
            if not (-300<=v<=300) or z["availableFrom"]!=quarter_safe_date(y,q):raise RuntimeError("Invalid EPS provenance "+str(z))
            byeps[(market,code)].append({"date":str(z["availableFrom"]),"year":y,"quarter":q,"eps":v})
        for key,items in byrev.items():
            seen={};ordered=sorted(items,key=lambda z:(z["year"],z["month"]))
            for x in ordered:
                k=(x["year"],x["month"])
                if k in seen and x["revenue"]!=seen[k]["revenue"]:raise RuntimeError("Duplicate monthly conflict "+str((key,k)))
                seen[k]=x
            ordered=sorted(seen.values(),key=lambda z:z["date"])
            self.rev[key]=( [r["date"] for r in ordered],ordered )
        for key,items in byeps.items():
            seen={};ordered=sorted(items,key=lambda z:(z["year"],z["quarter"]))
            for x in ordered:
                k=(x["year"],x["quarter"])
                if k in seen and x["eps"]!=seen[k]["eps"]:raise RuntimeError("Duplicate EPS conflict "+str((key,k)))
                seen[k]=x
            ordered=sorted(seen.values(),key=lambda z:z["date"])
            self.eps[key]=( [r["date"] for r in ordered],ordered )
        self.coverage.update({"symbolsRev":len(self.rev),"symbolsEPS":len(self.eps),
            "rowsRevenue":sum(len(v[1]) for v in self.rev.values()),
            "rowsEPS":sum(len(v[1]) for v in self.eps.values())})
    def at(self,market,code,day):
        """Strict only-known-by-day fiscal information; None on missing comparisons."""
        key=(market,str(code))
        if key not in self.rev or key not in self.eps:return None
        rd,rr=self.rev[key];ed,ee=self.eps[key]
        i=bisect.bisect_right(rd,day)-1;j=bisect.bisect_right(ed,day)-1
        if i<0 or j<0:return None
        latest=rr[i];quarter=ee[j]
        if day<latest["date"] or day<quarter["date"]:raise AssertionError("future fundamental data used")
        if (pd.Timestamp(day)-pd.Timestamp(latest["date"])).days>RULES["MAX_CONSERVATIVE_REV_AGE_DAYS"]:return None
        if (pd.Timestamp(day)-pd.Timestamp(quarter["date"])).days>RULES["MAX_CONSERVATIVE_EPS_AGE_DAYS"]:return None
        # Compare to rows published strictly on or before signal date.
        oldrev=next((r for r in reversed(rr[:i]) if r["year"]==latest["year"]-1 and r["month"]==latest["month"]),None)
        oldeps=next((r for r in reversed(ee[:j]) if r["year"]==quarter["year"]-1 and r["quarter"]==quarter["quarter"]),None)
        if oldrev is None or oldeps is None or oldeps["eps"]<=0:return None
        if oldrev["revenue"]<=0:return None
        epsgrowth=100*(quarter["eps"]/oldeps["eps"]-1)
        revenuegrowth=100*(latest["revenue"]/oldrev["revenue"]-1)
        # Last 12 REPORTS known as-of the decision day (including latest).
        history=rr[max(0,i-11):i+1]
        if len(history)<10:return None
        revmax=max(x["revenue"] for x in history)
        highratio=latest["revenue"]/revmax if revmax>0 else 0.
        return {"epsYtdGrowthPct":epsgrowth,"revenueYoYPct":revenuegrowth,
            "revenueHighRatioPct":100*highratio,"epsYtd":quarter["eps"],
            "prevYearSameQuarterEPS":oldeps["eps"],
            "latestRevenue":latest["revenue"],
            "revAvailableFrom":latest["date"],
            "epsAvailableFrom":quarter["date"],
            "revFiscal":f'{latest["year"]}-{latest["month"]:02d}',
            "epsFiscal":f'{quarter["year"]}Q{quarter["quarter"]}',
            "asOf":day}
def technical_panel(hist,dates):
    q=hist.sort_values("date").drop_duplicates("date",keep="last").copy()
    if len(q)<275:return pd.DataFrame()
    for c in ("open","close","high","low","volume"):q[c]=pd.to_numeric(q[c],errors="coerce")
    px=q.close;volume=q.volume
    m50=px.rolling(50,min_periods=50).mean()
    m200=px.rolling(200,min_periods=200).mean()
    vmax=q.high.rolling(252,min_periods=200).max()
    q["high52"]=vmax
    q["near52WeekHighPct"]=100*px/vmax.replace(0,np.nan)
    q["ma50"]=m50;q["ma200"]=m200
    q["aboveMA50Pct"]=100*(px/m50-1)
    q["aboveMA200Pct"]=100*(px/m200-1)
    q["rs63"]=100*(px/px.shift(63)-1)
    q["rs126"]=100*(px/px.shift(126)-1)
    q["rs252"]=100*(px/px.shift(252)-1)
    q["ret20Pct"]=100*(px/px.shift(20)-1)
    q["ret5Pct"]=100*(px/px.shift(5)-1)
    q["momentumRS"]=.4*q.rs63+.3*q.rs126+.3*q.rs252
    q["vol20Prior"]=volume.shift(1).rolling(20,min_periods=20).mean()
    q["volRatio"]=volume/q.vol20Prior.replace(0,np.nan)
    q["turnoverB"]=px*volume/1e8
    q=q[q.date.astype(str).isin(set(dates))].copy()
    return q
def generate_n_candidates(hist,universe,fundamentals,risk,dates):
    """RS percentile computed across ALL tradable current-stock universe,
    not only fundamental screened survivors. Every feature known by close D.
    """
    raw=collections.defaultdict(list);market_rs=collections.defaultdict(list)
    stat=collections.Counter();valid_stocks=0
    for n,company in enumerate(universe,1):
        market=market_key(company["market"])
        if market is None:continue
        sy=to_symbol(company["code"],company["market"]);h=hist.get(sy)
        if h is None or h.empty:continue
        p=technical_panel(h,dates)
        if p.empty:continue
        valid_stocks+=1
        for z in p.itertuples(index=False):
            score=float(z.momentumRS) if pd.notna(z.momentumRS) else math.nan
            if math.isfinite(score):market_rs[str(z.date)].append(score)
            if not math.isfinite(score):continue
            if not all(math.isfinite(float(v)) for v in
                (z.near52WeekHighPct,z.ma50,z.ma200,z.volRatio,z.turnoverB,z.aboveMA50Pct,z.aboveMA200Pct,z.ret5Pct,z.ret20Pct)):
                continue
            stat["priceValid"]+=1
            if not (z.close>=RULES["MIN_PRICE_TWD"] and z.turnoverB>=RULES["MIN_LIQUIDITY_BILLION_TWD"]
                and z.near52WeekHighPct>=100*RULES["CLOSE_TO_52WK_HIGH_MIN_RATIO"]
                and z.close>z.ma50>z.ma200 and z.rs63>0):
                continue
            stat["technicalPassed"]+=1
            d=str(z.date);fm=fundamentals.at(market,company["code"],d)
            if fm is None:stat["fundamentalMissing"]+=1;continue
            if not (fm["epsYtd"]>0 and fm["epsYtdGrowthPct"]>=RULES["EPS_YTD_YOY_MIN_PCT"]
              and fm["revenueYoYPct"]>=RULES["REV_MONTH_YOY_MIN_PCT"]
              and fm["revenueHighRatioPct"]>=100*RULES["REV_12MO_HIGH_MIN_RATIO"]):
                stat["growthFailed"]+=1;continue
            stat["growthPassed"]+=1
            raw[d].append({"date":d,"sym":sy,"code":str(company["code"]),
                "name":str(company["name"]),"market":market,"close":float(z.close),
                "price":float(z.close),"techn":{k:float(getattr(z,k)) for k in
                  ("momentumRS","rs63","rs126","rs252","near52WeekHighPct",
                   "volRatio","turnoverB","aboveMA50Pct","aboveMA200Pct","ret20Pct","ret5Pct")},
                "fundamental":fm})
        if n%450==0:print("N_FULL_MARKET_SCAN",n,"/",len(universe),
            "growthCandidates",sum(map(len,raw.values())),flush=True)
    rs_sorted={d:np.sort(np.asarray(scores,dtype=float)) for d,scores in market_rs.items()}
    pool={};top3={};rows=0;missing_risk=0
    for d in dates:
        scored=[]
        daily_risk=risk.get(d)
        if daily_risk is None:raise RuntimeError("Risk missing "+d)
        for row in raw.get(d,[]):
            scores=rs_sorted.get(d)
            if scores is None or len(scores)<300:raise RuntimeError("Not enough same-day cross-sectional RS universe "+d)
            percentile=100*np.searchsorted(scores,row["techn"]["momentumRS"],side="right")/len(scores)
            if percentile<RULES["RS_CROSS_SECTION_MIN_PERCENTILE"]:continue
            rm=row["fundamental"];tm=row["techn"]
            features={
              "epsYtdGrowthPct":rm["epsYtdGrowthPct"],"revenueYoYPct":rm["revenueYoYPct"],
              "revenueHighRatioPct":rm["revenueHighRatioPct"],"rsPercentile":percentile,
              "near52WeekHighPct":tm["near52WeekHighPct"],"rs63":tm["rs63"],
              "rs126":tm["rs126"],"rs252":tm["rs252"],"volRatio":tm["volRatio"],
              "aboveMA50Pct":tm["aboveMA50Pct"],"aboveMA200Pct":tm["aboveMA200Pct"],
              "ret20Pct":tm["ret20Pct"],"ret5Pct":tm["ret5Pct"],"turnoverB":tm["turnoverB"],
              "marketScore":daily_risk.get("score"),"marketBreadth":daily_risk.get("breadth"),
              "marketRet5":daily_risk.get("ret5"),"marketRet20":daily_risk.get("ret20"),
              "marketForeign":daily_risk.get("foreign")}
            fv=[features[z] for z in FEATURE_NAMES]
            if any(v is None or not math.isfinite(float(v)) for v in fv):
                missing_risk+=1;continue
            # Untrained as-of ranking, for candidate preview only. Never label it ML.
            preliminary=(min(features["epsYtdGrowthPct"],120)*.2+
                min(features["revenueYoYPct"],120)*.2+features["rsPercentile"]*.25+
                features["near52WeekHighPct"]*.2+features["revenueHighRatioPct"]*.15)
            scored.append({k:row[k] for k in ("date","sym","code","name","close","market")}|
                {"features":[float(z) for z in fv],"sources":["N CANSLIM growth"],
                "factorScore":round(float(preliminary),4),
                "metrics":{**{k:round(float(v),3) for k,v in features.items()},
                   "epsFiscal":rm["epsFiscal"],"revFiscal":rm["revFiscal"],
                   "epsAvailableFrom":rm["epsAvailableFrom"],"revAvailableFrom":rm["revAvailableFrom"]}})
        scored.sort(key=lambda x:(-x["factorScore"],x["code"]))
        pool[d]=scored
        top3[d]=[{k:z[k] for k in ("date","sym","code","name","close","market",
             "factorScore","metrics")} for z in scored[:3]]
        rows+=len(scored)
    stat["rsAndGrowthQualifiedStockDays"]=rows
    stat["signalDays"]=sum(bool(v) for v in pool.values())
    stat["uniqueQualifiedSymbols"]=len({r["sym"] for stocks in pool.values() for r in stocks})
    stat["riskFeatureMissing"]=missing_risk
    stat["priceSeriesValidated"]=valid_stocks
    stat["universeRSDays"]=len(rs_sorted)
    return pool,top3,dict(stat)
