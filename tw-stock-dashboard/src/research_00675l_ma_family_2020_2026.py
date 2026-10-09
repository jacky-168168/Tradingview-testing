"""00675L 2020-2026 SMA/EMA/WMA/VWMA full cash-compound trend rotation research.
Replicate the previously frozen SMA10 exit/reentry strategy exactly, then do apples-to-apples
moving-average substitutions and train-only grid over 2020-2023. Later periods are frozen audits.
DO NOT pick a final winner by 2024-2026 returns. No synthetic ^TWII volume.
"""
from __future__ import annotations
import json,math,time,itertools
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np,pandas as pd
from research_00675l_near_hold_switch import bt,prepare,indicators,universe
from research_00675l_swing_grid import data_prepare,update_symbol,SYMBOL,INDEX,CAPITAL,BROKER,ETF_SELL_TAX,SLIP,DATA_DIR
OUT=DATA_DIR/"research/etf_00675l_ma_family_2020_2026"
FULL=("2020-01-01","2026-10-07")
TRAIN=("2020-01-01","2023-12-31")
VALID=("2024-01-01","2025-12-31")
AUDIT=("2026-01-01","2026-10-07")
SINCE24=("2024-01-01","2026-10-07")
MA_FAMILIES=("SMA","EMA","WMA","VWMA")
SOURCE_KEYS=("twii","close")
WINDOWS=(5,8,10,12,15,20,30,40,60)
BREAKS=(.00,.01,.02,.03,.04)
REENTERS=(.00,.01,.02,.03)
CONFIRMS=(1,2,3)
BASE_ID="SMA_twii_N10_OUT2_RE1_C3"
def basic(x):
    return {k:x[k] for k in ("start","end","returnPct","endNTD","mddPct","riskOffSells","riskOnReentries","riskOffSessions","investedSessions","sessions","switchEvents")}
def equity_years(rows):
    years=sorted(set(x["date"][:4] for x in rows));before=float(CAPITAL);out={}
    for yr in years:
        last=next(x for x in reversed(rows) if x["date"].startswith(yr))["equity"]
        out[yr]={"openingNTD":round(before,2),"closingNTD":round(last,2),
            "returnPct":round(100*(last/before-1),3)}
        before=last
    return out
def data():
    _,etf,error=update_symbol(SYMBOL,datetime(2019,1,1),datetime(2026,10,8))
    _,idx,error2=update_symbol(INDEX,datetime(2019,1,1),datetime(2026,10,8))
    if error or error2 or etf is None or idx is None or etf.empty or idx.empty:
        raise RuntimeError("No reliable market OHLC: "+str((error,error2)))
    merged=prepare(data_prepare(etf,idx))
    merged=merged[merged.date<=FULL[1]].reset_index(drop=True)
    if not set(["date","close","twii","volume"]).issubset(merged.columns):raise RuntimeError("Missing columns")
    vol=idx[["date","volume"]].copy();vol.date=vol.date.astype(str)
    vol["volume"]=pd.to_numeric(vol.volume,errors="coerce");vol=vol.rename(columns={"volume":"index_volume"})
    merged=merged.merge(vol.drop_duplicates("date",keep="last"),how="left",on="date")
    for label,column in (("etf","volume"),("taiwan_index","index_volume")):
        v=pd.to_numeric(merged.loc[merged.date>=FULL[0],column],errors="coerce")
        pct=round(float((v>0).mean())*100,3)
        metrics[label]={"validVolumeDaysPct":pct,"distinctNonzeroVolumes":int(v[v>0].nunique()),
                "minNonzeroVolume":float(v[v>0].min()) if (v>0).any() else None,
                "maxNonzeroVolume":float(v[v>0].max()) if (v>0).any() else None}
        print("MA_VOLUME_COVERAGE "+json.dumps({"source":label,**metrics[label]}),flush=True)
    if len(merged[merged.date.between(*FULL)])<1550:raise RuntimeError("Incomplete series")
    a,dates=indicators(merged)
    return merged,a,dates
metrics={}
def ma_array(x,volume,method,n):
    s=pd.Series(x)
    if method=="SMA":return s.rolling(n,min_periods=n).mean().to_numpy(float)
    if method=="EMA":return s.ewm(span=n,adjust=False,min_periods=n).mean().to_numpy(float)
    if method=="WMA":
        weights=np.arange(1,n+1,dtype=float)
        return s.rolling(n,min_periods=n).apply(lambda v:np.dot(v,weights)/weights.sum(),raw=True).to_numpy(float)
    if method=="VWMA":
        if volume is None:raise ValueError("Missing appropriate traded volume source")
        v=pd.Series(volume).where(lambda z:z>0)
        # No carry-forward, no fake volume. A volume-weighted MA requires n real sessions.
        raw=(s*v).rolling(n,min_periods=n).sum()/v.rolling(n,min_periods=n).sum()
        return raw.where(v.rolling(n,min_periods=n).count()==n).to_numpy(float)
    raise ValueError("Unknown MA "+method)
def mkcfg(family,src,n,down,up,confirm):
    return {"id":f"{family}_{src}_N{n}_OUT{int(round(down*100))}_RE{int(round(up*100))}_C{confirm}",
            "family":"ma_hysteresis","src":src,"n":n,"out":down,"rein":up,
            "confirm":confirm,"riskOffWeight":0.0,"maType":family}
def localarrays(a,means,conf):
    z=dict(a);z[f"{conf['src']}_ema{conf['n']}"]=means[(conf["maType"],conf["src"],conf["n"])]
    return z
def simulate(a,dates,means,conf,period,full=False):
    return bt(localarrays(a,means,conf),dates,conf,*period,detailed=full)
def score(result):
    # Rank only training-window net account returns. Mild max-DD and over-trading penalty;
    # no outcomes from 2024 onward can affect this score.
    return round(result["returnPct"]-.55*abs(result["mddPct"])-1.0*result["riskOffSells"],3)
def pretty_pct(z):return f"{z:+,.3f}%"
def main():
    started=time.monotonic()
    d,a,dates=data()
    sessions=int(((dates>=FULL[0])&(dates<=FULL[1])).sum())
    if dates[0]>"2019-03-01":raise RuntimeError("Insufficient 2019 warmup before 2020")
    print("MA_DATA_READY "+json.dumps({"first":dates[0],"last":dates[-1],"sessions":sessions}),flush=True)
    available={}
    for key,source in (("twii","taiwan_index"),("close","etf")):
        available[key]=metrics[source]["validVolumeDaysPct"]>99 and metrics[source]["distinctNonzeroVolumes"]>100
    print("MA_VWMA_ALLOWED "+json.dumps(available),flush=True)
    means={}
    for typ,src,n in itertools.product(MA_FAMILIES,SOURCE_KEYS,WINDOWS):
        if typ=="VWMA" and not available[src]:continue
        vol=a["index_volume" if src=="twii" else "volume"] if typ=="VWMA" else None
        means[typ,src,n]=ma_array(a[src],vol,typ,n)
    base=mkcfg("SMA","twii",10,.02,.01,3)
    holding={"id":"BUY_HOLD","family":"buyhold","riskOffWeight":1.0}
    hold_full=bt(a,dates,holding,*FULL,detailed=True)
    sma_full=simulate(a,dates,means,base,FULL,True)
    assert hold_full["returnPct"]==1653.043,("BUY_HOLD_PARITY",hold_full)
    assert sma_full["returnPct"]==3312.334,("SMA10_PARITY",sma_full)
    assert sma_full["riskOffSells"]==15 and sma_full["riskOnReentries"]==15
    sma_24=simulate(a,dates,means,base,SINCE24)
    assert sma_24["returnPct"]==600.612,("SMA10_2024_PARITY",sma_24)
    print("MA_FROZEN_BASELINE_PASS "+json.dumps({"hold":hold_full["returnPct"],"SMA10":sma_full["returnPct"],"SMA10_2024_26":sma_24["returnPct"]}),flush=True)
    # Apples-to-apples: same 10-day lookback, 2% exit buffer, 1% reentry buffer, 3 closes.
    uniform=[]
    for typ,src in itertools.product(MA_FAMILIES,SOURCE_KEYS):
        if (typ,src,10) not in means:continue
        c=mkcfg(typ,src,10,.02,.01,3)
        uniform.append({"id":c["id"],"cfg":c})
    frozen_ids={v["id"] for v in uniform}
    for item in uniform:
        cfg=item["cfg"]
        item["training2020_2023"]=basic(simulate(a,dates,means,cfg,TRAIN))
        item["validation2024_2025"]=basic(simulate(a,dates,means,cfg,VALID))
        item["audit2026"]=basic(simulate(a,dates,means,cfg,AUDIT))
        item["continuous2020_2026"]=basic(simulate(a,dates,means,cfg,FULL))
        print("MA_APPL2APPL "+json.dumps({"id":item["id"],"train":item["training2020_2023"]["returnPct"],
          "validation":item["validation2024_2025"]["returnPct"],
          "audit":item["audit2026"]["returnPct"],"full":item["continuous2020_2026"]["returnPct"]}),flush=True)
    # Research search: all candidate rules ranked using 2020-2023 only.
    train_rows=[]
    tested=0
    for typ,src,n,down,up,confirm in itertools.product(MA_FAMILIES,SOURCE_KEYS,WINDOWS,BREAKS,REENTERS,CONFIRMS):
        if (typ,src,n) not in means:continue
        cfg=mkcfg(typ,src,n,down,up,confirm)
        train=basic(simulate(a,dates,means,cfg,TRAIN))
        row={"id":cfg["id"],"maType":typ,"signalSource":src,"window":n,
             "sellBufferPct":round(100*down,2),"rebuyBufferPct":round(100*up,2),
             "confirmationDays":confirm,"score2020_23":score(train),
             "training2020_2023":train}
        train_rows.append(row)
        tested+=1
        if tested%360==0:print("MA_GRID_TRAIN_PROGRESS "+json.dumps({"tested":tested}),flush=True)
    print("MA_GRID_TRAIN_COMPLETE "+json.dumps({"tested":tested}),flush=True)
    # Pre-freeze finalists per MA family and signal source: best 2020-23 risk score
    # and highest raw 2020-23 net return, 1-2 from each category.
    finalists=set(frozen_ids)
    decisions=[]
    for typ,src in itertools.product(MA_FAMILIES,SOURCE_KEYS):
        group=[r for r in train_rows if r["maType"]==typ and r["signalSource"]==src and
               r["training2020_2023"]["riskOffSells"]>=2 and r["training2020_2023"]["riskOnReentries"]>=2]
        risk=sorted(group,key=lambda r:(-r["score2020_23"],r["id"]))[:2]
        absolute=sorted(group,key=lambda r:(-r["training2020_2023"]["returnPct"],r["id"]))[:1]
        for r in risk+absolute:
            finalists.add(r["id"]);decisions.append({"id":r["id"],"reason":"2020_23_risk_score" if r in risk else "2020_23_absolute_profit",
                "score2020_23":r["score2020_23"],"trainReturnPct":r["training2020_2023"]["returnPct"]})
    by_id={r["id"]:r for r in train_rows}
    frozen=[]
    detail={}
    for id in sorted(finalists):
        row=by_id[id]
        cfg=mkcfg(row["maType"],row["signalSource"],row["window"],
                  row["sellBufferPct"]/100,row["rebuyBufferPct"]/100,row["confirmationDays"])
        train=row["training2020_2023"]
        validation=basic(simulate(a,dates,means,cfg,VALID))
        audit=basic(simulate(a,dates,means,cfg,AUDIT))
        since24=basic(simulate(a,dates,means,cfg,SINCE24))
        full=simulate(a,dates,means,cfg,FULL,True)
        f={"id":id,"maType":row["maType"],"signalSource":row["signalSource"],
           "window":row["window"],"sellBufferPct":row["sellBufferPct"],
           "rebuyBufferPct":row["rebuyBufferPct"],"confirmationDays":row["confirmationDays"],
           "selection":"apples_to_apples" if id in frozen_ids else "2020_23_only_rank",
           "score2020_23":row["score2020_23"],
           "training2020_2023":train,
           "validation2024_2025":validation,"audit2026":audit,
           "independent2024_2026":since24,
           "continuous2020_2026":basic(full),
           "compoundedYears":equity_years(full["equity"])}
        frozen.append(f)
        detail[id]={"equity":full["equity"],"transactions":full["orders"]}
        print("MA_GRID_FROZEN_AUDIT "+json.dumps({"id":id,"train":train["returnPct"],"validation":validation["returnPct"],
            "audit2026":audit["returnPct"],"full":full["returnPct"],"dd":full["mddPct"],
            "roundTrips":full["riskOffSells"]}),flush=True)
    for row in uniform:
        r=next(z for z in frozen if z["id"]==row["id"])
        assert r["continuous2020_2026"]==row["continuous2020_2026"],r["id"]
    # Re-run previous fixed SMA under exactly identical data, ensure all 2019-26 continuity.
    assert next(z for z in frozen if z["id"]==BASE_ID)["continuous2020_2026"]["returnPct"]==3312.334
    # Conservative execution stress for all fixed 10-day comparisons, and the pre-chosen
    # best train-only risk rank per family (not the winner chosen by 2024-26).
    stress_ids=sorted(set([z["id"] for z in uniform]+[r["id"] for r in decisions if r["reason"]=="2020_23_risk_score"]))
    import research_00675l_near_hold_switch as original_module
    import research_00675l_near_hold_stress as lag_module
    slippage={}
    for slip in (.001,.003,.005,.01):
        original_module.SLIP=slip
        lag_module.SLIP=slip
        slippage[str(slip)]={}
        for id in stress_ids+["BUY_HOLD"]:
            if id=="BUY_HOLD":result=bt(a,dates,holding,*FULL)
            else:
                r=by_id[id]
                cfg=mkcfg(r["maType"],r["signalSource"],r["window"],r["sellBufferPct"]/100,
                          r["rebuyBufferPct"]/100,r["confirmationDays"])
                result=simulate(a,dates,means,cfg,FULL)
            slippage[str(slip)][id]=basic(result)
    original_module.SLIP=SLIP
    lag_module.SLIP=SLIP
    lagging={}
    for lag in (0,1,2):
        lagging[str(lag)]={}
        for id in stress_ids:
            r=by_id[id];cfg=mkcfg(r["maType"],r["signalSource"],r["window"],r["sellBufferPct"]/100,
                      r["rebuyBufferPct"]/100,r["confirmationDays"])
            from research_00675l_near_hold_stress import bt_lag
            result=bt_lag(localarrays(a,means,cfg),dates,cfg,*FULL,lag=lag)
            lagging[str(lag)][id]=basic(result)
    for id in stress_ids:
        actual=next(z for z in frozen if z["id"]==id)["continuous2020_2026"]["returnPct"]
        assert lagging["0"][id]["returnPct"]==actual,(id,actual,lagging["0"][id]["returnPct"])
    baseline={"buyHold2020_2026":basic(hold_full),"buyHoldCompoundedYears":equity_years(hold_full["equity"]),
        "SMA10Previous2020_2026":basic(sma_full),"SMA10Previous2024_2026":basic(sma_24)}
    report={"version":"00675L_MA_FAMILY_2020_2026_V1",
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "symbol":SYMBOL,"index":INDEX,"firstWarmupDate":dates[0],"lastDate":dates[-1],
        "sessions2020_2026":sessions,
        "volumeCoverage":metrics,"vwmaAllowed":available,"missingVWMA":{src:"Yahoo ^TWII volume absent/incomplete" if src=="twii" else "ETF volume absent/incomplete" for src,can in available.items() if not can},
        "feeAssumptions":{"capitalNTD":CAPITAL,"brokerPctEachSide":round(BROKER*100,5),
            "etfTaxPctOnSell":round(ETF_SELL_TAX*100,5),"slippagePctEachSide":round(SLIP*100,5),
            "allProfitsReinvested":True,"integerETFUnits":True,"margin":False,
            "orders":"Completed daily close crossover thresholds; NEXT session opening price; first open buys entire cash account."},
        "experiment":{"families":MA_FAMILIES,"signalSources":{"twii":"^TWII index close, Yahoo index total daily volume for VWMA","close":"00675L adjusted close and ETF daily traded volume for VWMA"},
            "windows":WINDOWS,"sellBuffersPct":[int(x*100) for x in BREAKS],"rebuyBuffersPct":[int(x*100) for x in REENTERS],
            "confirmDays":CONFIRMS,"fixedComparison":"n=10, sell gap=2%, buy gap=1%, 3 consecutive closes",
            "rankingTrainingOnly":"2020-2023; score netReturnPct minus 0.55*abs(maxDDPct) minus 1*numberRiskSells",
            "selection":"Top two train score and top one train raw return per each source×MA family + fixed-comparison, no 2024-2026 returns used to select",
            "validation":"2024-2025 audit, followed by already researcher-exposed 2026; displayed independent and continuous account periods",
            "preExisting2024_2026BaseCheck":"Original SMA10 fixed rule +600.612% in 2024-2026, and +3312.334% 2020-2026",
            "allMAResultsNotOptimized":"fixed 10d comparison shows direct effect of replacing mean formula, not searching best params"},
        "nTrainModels":len(train_rows),"nFrozenFinalists":len(frozen),
        "baseline":baseline,"fixedParameterComparison":uniform,
        "freezeList":decisions,"finalists":frozen,
        "robustness":{"slippageEachSide":slippage,"extraSignalDaysDelayed":lagging},
        "warnings":["2020-2023 and 2024-2026 have already been viewed in the research process, so none are truly independent prospective returns; the period split only limits new code selection.",
            "VWMA input Yahoo index volume may have scaling/market-definition changes; no substitution with ETF volume for index price is permitted.",
            "Adjusted ETF price series paired with unadjusted exchange volume can be affected by corporate-action adjustments; check price adjustment factor for discontinuities.",
            "Parameter search has thousands of similar variants: top in-sample selection is subject to multiple-test and survivor bias.",
            "SMA/EMA/WMA/VWMA are all price-following, not independent risk hedges; large 2x ETF crashes and opening gaps may cause >30% portfolio drawdown.",
            "No borrowing and no imaginary after-close fills; model assumes next-open liquidity at assumed slippage and omits real broker limitations.",
            "VWMA rolling window is entirely invalid if any source bar has zero/missing/nonpositive volume; no fabricated volume."],
        "elapsedSeconds":round(time.monotonic()-started,1)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"all_training_results.json").write_text(json.dumps({"version":report["version"],"results":train_rows},ensure_ascii=False),encoding="utf-8")
    (OUT/"finalist_trades_daily_equity.json").write_text(json.dumps({"version":report["version"],
       "buyhold":{"equity":hold_full["equity"],"transactions":hold_full["orders"]},"candidates":detail},ensure_ascii=False),encoding="utf-8")
    text=[]
    text.extend(["# 00675L SMA / EMA / WMA / VWMA 2020-2026",
      "","Principal NT$1,000,000 fully reinvested, brokerage 0.1425% each side, ETF sell tax 0.1%, slippage 0.1% each side.",
      "Run 2020/01/02–2026/10/07; index ^TWII and 00675L signals; completed close to next open orders.","",
      "## Equal-parameter experiment","",
      "| MA | Source | 2020–2023 % | 2024–2025 % | 2026 % | Full % | Full maxDD % | Sells |",
      "|---|---|---:|---:|---:|---:|---:|---:|"])
    for v in sorted(uniform,key=lambda v:(v["cfg"]["src"],v["cfg"]["maType"])):
        t=v["training2020_2023"];y=v["validation2024_2025"];z=v["audit2026"];f=v["continuous2020_2026"]
        text.append(f'| {v["cfg"]["maType"]} | {v["cfg"]["src"]} | {t["returnPct"]:+.3f}% | {y["returnPct"]:+.3f}% | {z["returnPct"]:+.3f}% | {f["returnPct"]:+.3f}% | {f["mddPct"]:.3f}% | {f["riskOffSells"]} |')
    text.extend(["","## Training-frozen finalist comparisons","",
      "| ID | Train % | 2024–25 % | 2026 % | Full % | Full maxDD % | End NT$ |",
      "|---|---:|---:|---:|---:|---:|---:|"])
    for v in sorted(frozen,key=lambda v:-v["training2020_2023"]["returnPct"]):
        text.append(f'| {v["id"]} | {v["training2020_2023"]["returnPct"]:+.3f}% | {v["validation2024_2025"]["returnPct"]:+.3f}% | {v["audit2026"]["returnPct"]:+.3f}% | {v["continuous2020_2026"]["returnPct"]:+.3f}% | {v["continuous2020_2026"]["mddPct"]:+.3f}% | {v["continuous2020_2026"]["endNTD"]:,.2f} |')
    text.extend(["","## Volume coverage",json.dumps(metrics,ensure_ascii=False,indent=2),
      "","## Caveats","This is historical simulated performance, subject to selection bias, adjusted OHLC, future execution slippage, 2x leveraged ETF drawdowns, and prior exposure to ALL years."])
    (OUT/"report.md").write_text("\n".join(text),encoding="utf-8")
    print("MA_ALL_DONE "+json.dumps({"modelsTrained":len(train_rows),"finalists":len(frozen),
          "fixedCases":len(uniform),"vwmaAllowed":available,"seconds":report["elapsedSeconds"],
          "fixedComparison":[{"id":v["id"],"fullPct":v["continuous2020_2026"]["returnPct"],"maxDD":v["continuous2020_2026"]["mddPct"]} for v in uniform]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
