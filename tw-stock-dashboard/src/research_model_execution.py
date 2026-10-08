"""Research selection × execution interaction; not production, no trading.
Historical A/D/F/F2 and G variants are loaded as FROZEN published Top3.
H5 fresh-break comes from its original fixed screener (no retuning).
For each selector apply identical shared execution engine (5-entry price ladder
or MA5/10/20/60 touches), same costs and weakness. Compare 5/10/20D,
time windows, dollar-weighted reserved-lot outcomes, and sample sizes.
Data has already influenced 2026 model development: NOT independent OOS.
"""
from __future__ import annotations
import json,time,os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from collections import Counter
import numpy as np
from config import DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from backtest_g_exec_comparison import prepare_bars,run_model,summary
from backtest_h_ladder import selection as h5_selection
START="2026-01-01";END="2026-10-07";HORIZONS=(5,10,20)
PERIODS={"early":("2026-01-01","2026-04-30"),"middle":("2026-05-01","2026-07-31"),"late":("2026-08-01","2026-10-07")}
MIN_TRADES=35
SOURCES=[
    ("backtest/2026-01-01_2026-10-07.json","models"),
    ("backtest_g/2026-01-01_2026-10-07.json","models"),
    ("backtest_g/g_candle_2026.json","models"),
    ("backtest_g/g_persistence_2026.json","models")
]
INCLUDE=["A","D","F","F2","G_BASE","G_RELAXED","G_STRICT","G_BROAD","G_CANDLE",
         "G_TRIGGER","G_3D_BREAK","G_18D_BREAK","G_DOUBLE_BREAK","G_ENGULF","G_PERSIST",
         "G_DOUBLE_PERSIST","H5_FRESH_BREAK"]
def signal_sources():
    out={}
    for file,key in SOURCES:
        path=DATA_DIR/file
        d=json.loads(path.read_text(encoding="utf-8"))
        models=d[key]
        if isinstance(models,dict):seq=list(models.items())
        else:seq=[(x["id"],x) for x in models]
        for name,m in seq:
            if name in INCLUDE:
                out[name]=[x for x in m["signals"] if START<=x["signalDate"]<=END and int(x["rank"])<=3]
    return out
def model_events(rows,companies):
    # Attach actual exchange rather than guess .TW/.TWO.
    return [dict(x,market=companies[str(x["code"])]["market"]) for x in rows if str(x["code"]) in companies]
def summarize_slices(trades):
    parts={}
    for label,(lo,hi) in PERIODS.items():
        rows=[x for x in trades if lo<=x["date"]<=hi]
        a=[x for x in rows if x["status"]=="filled"]
        nets=np.array([x["netOnReservedPct"] for x in a],dtype=float)
        parts[label]={"signals":len(rows),"filled":len(a),"tpN":sum(x["tp"] for x in a),
                      "tpPct":round(100*sum(x["tp"] for x in a)/len(a),2) if a else None,
                      "avgNetReservedPct":round(float(nets.mean()),3) if a else None,
                      "totalNetReservedPct":round(float(nets.sum()),3) if a else None,
                      "distinctStocks":len(set(x["code"] for x in a))}
    return parts
def run():
    t=time.time();universe=load_universe()
    companies={str(x["code"]):x for x in universe}
    signals=signal_sources()
    print("SELECTOR_FILES "+json.dumps({k:len(v) for k,v in signals.items()},ensure_ascii=False),flush=True)
    h5_enabled=os.environ.get("G_COMPARE_SKIP_H5","0")!="1"
    fs=datetime(2025,4,1);fe=datetime(2026,10,8)
    # Fetch entire stock history exactly once to derive same-day frozen H5 signal
    # plus all A/D/F2/F and G stock open/high/low/close sequences.
    symbols=sorted({(str(x["code"]),x["market"]) for x in universe}) if h5_enabled else sorted({
        (str(s["code"]),companies[str(s["code"])]["market"]) for rows in signals.values()
        for s in rows if str(s["code"]) in companies})
    print("HIST_UNIVERSE "+str(len(symbols)),flush=True)
    hist,errors=update_many(symbols,fs,fe)
    _,idx,idxerror=update_symbol("^TWII",fs,fe)
    if idxerror or idx is None or idx.empty:raise RuntimeError("Cannot load historical market calendar "+str(idxerror))
    md=[str(x) for x in idx.date.astype(str).tolist() if str(x)<=END]
    mi={x:i for i,x in enumerate(md)}
    hcoverage=None
    if h5_enabled:
        selected,hcoverage=h5_selection(hist,universe,md,mi)
        hr=[]
        for x in selected.to_dict("records"):
            hr.append({"signalDate":x["date"],"rank":int(x["rank"]),"code":str(x["code"]),"market":x["market"],
                       "name":x["name"],"score":round(float(x["score"]),3)})
        signals["H5_FRESH_BREAK"]=hr
        print("FROZEN_H5 "+json.dumps(hcoverage,ensure_ascii=False),flush=True)
    raw={key: model_events(rows,companies) for key,rows in signals.items()}
    prices={symbol:prepare_bars(df) for symbol,df in hist.items()
            if df is not None and len(df)>60}
    statistics={};raw_trades={};runs=0
    for name in INCLUDE:
        if name not in raw:continue
        statistics[name]={};raw_trades[name]={}
        for h in HORIZONS:
            statistics[name][str(h)]={};raw_trades[name][str(h)]={}
            for mode in ("ladder","ma"):
                trades,dupes=run_model(raw[name],prices,md,h,mode)
                x=summary(trades,dupes,mode,h)
                x["timeSlices"]=summarize_slices(trades)
                statistics[name][str(h)][mode]=x
                raw_trades[name][str(h)][mode]=trades
                runs+=1
                if h==10:print("SELECTOR_10D "+json.dumps({"model":name,"mode":mode,"stats":{k:v for k,v in x.items() if k not in("timeSlices", "maFillCounts","trancheCounts")},"slices":x["timeSlices"]},ensure_ascii=False),flush=True)
    rows=[]
    for name,x in statistics.items():
        for h in HORIZONS:
            for mode in ("ladder","ma"):
                d=x[str(h)][mode]
                if d.get("filled",0)==0:continue
                rows.append({"model":name,"hold":h,"execution":mode,
                             "filled":d["filled"],"tpPct":d["takeProfitPct"],"stops":d["stopPct"],
                             "avgNetReservedPct":d["avgNetOnReservedPct"],
                             "avgNetDeployedPct":d["avgNetOnDeployedPct"],
                             "profitFactor":d["profitFactor"],
                             "lateFills":d["timeSlices"]["late"]["filled"],
                             "lateNetReservedPct":d["timeSlices"]["late"]["avgNetReservedPct"]})
    # No post-hoc retuning; descriptive rank only on predeclared 10D method,
    # and require >=35 trade events and >=15 'late' trades to avoid 1-2 lucky stocks.
    ranked={}
    for mode in ("ladder","ma"):
        a=[x for x in rows if x["hold"]==10 and x["execution"]==mode]
        ranked[mode]=sorted(a,key=lambda x:(x["filled"]>=MIN_TRADES and x["lateFills"]>=15,x["avgNetReservedPct"]),reverse=True)
    report={"version":"A_D_F_G_H_SELECTION_BY_EXEC_2026_V1",
       "period":{"start":START,"end":END},"generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
       "eligibleModelIds":INCLUDE,"availableModelIds":list(statistics),
       "publishedSignalCounts":{k:len(v) for k,v in raw.items()},
       "h5RebuiltFrozenCoverage":hcoverage,
       "marketUniverse":len(universe),"symbolsFetched":len(symbols),"stockPriceHistoryErrors":len(errors),
       "commonExecution":"A: 2.5% next 5-day price discount then P1×(.98,.96,.94,.92) 5 equal-cash orders. B: prev completed day SMA5/10/20/60 actual OHLC-touch each one equal-cash order (4 tranches), weak=2 closes<MA60 and MA20 declining, exit next open. Both basket TP+7%, SL-15% from dynamic weighted average; 5/10/20 sessions counted from first fill.",
       "overlappingSignalSuppression":"one active watch/position per model and stock; rank 4 does NOT replace blocked Top3",
       "tradingCosts":"buy/sell fees 0.1425% each, sell tax 0.30%, slippage 0.1% each side, conservative newly filled same-day TP",
       "timeSlices":PERIODS,
       "ranked10DayByReservedBudgetEventMean":ranked,
       "allModelStatistics":statistics,
       "warnings":["Same 2026 window influenced G and H design, NOT untouched holdout, research exploratory only.",
         "Raw signals across models highly correlated, cannot treat 17 models as 17 independent proof points.",
         "Model Top3 signals on a given date use close and may NOT be known until final close; orders no earlier than next trading session.",
         "Prices obtained from Yahoo daily OHLCV and actual historical listing is survivor-biased; abnormal corporate actions/nominal shares approximations may bias findings.",
         "Within-day MA touch / multi-order fills unknown sequence; conservative rule not a fill guarantee.",
         "Repeated signals of same code while tracking/open are suppressed independently for EACH model/mode.",
         "Event-level average returns use deployed and reserved capital but NOT shared-account cash allocation / true marked-to-market equity.",
         "Model time slices are descriptive not prospective out of sample; 2026 model research has used the entire period."],
       "elapsedSeconds":round(time.time()-t,1)}
    path=DATA_DIR/"research/model_execution_2026";path.mkdir(parents=True,exist_ok=True)
    (path/"selector_execution_2026_summary.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    # Trades in JSON may be megabytes; stored only CI artifact, never main.
    (path/"selector_execution_2026_trades.json").write_text(json.dumps(raw_trades,ensure_ascii=False),encoding="utf-8")
    print("SELECTOR_COMPARE_RESULT "+json.dumps({"models":list(statistics),"ranked10D":{k:v[:8] for k,v in ranked.items()},"elapsedSeconds":report["elapsedSeconds"]},ensure_ascii=False),flush=True)
    return report
if __name__=="__main__":run()
