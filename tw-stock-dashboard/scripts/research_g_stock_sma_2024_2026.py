"""2024-2026 G Double Persistence Top3: A (5 sessions), B (individual SMA10).
Fully chronological reconstruction uses the EXISTING 3y make_g; the 2026 execution
engine is imported unchanged, with only its date window and model set overridden.
"""
from __future__ import annotations
import collections,json,math,sys,time
from datetime import datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from yahoo_cache import update_many,update_symbol,to_symbol
from pipeline import load_universe
from research_g_regime_3y import make_g,finite
import research_g_stock_sma_2026 as engine
OUT=ROOT/"docs/data/research/g_stock_sma_2024_2026"
BEGIN="2023-10-09";START="2024-01-02";END_SIGNAL="2026-10-07";END_MARK="2026-10-16"
MODEL_NAMES=("G_HOLD5","G_SMA10")
def annual_stats(curve,trades):
    out={}
    for year in ("2024","2025","2026"):
        z=[r for r in curve if r["date"][:4]==year]
        if not z:raise RuntimeError("No portfolio marks for "+year)
        before=[r for r in curve if r["date"]<year+"-01-01"]
        init=before[-1]["equity"] if before else engine.INITIAL
        peak=init;dd=0.
        for r in z:
            peak=max(peak,r["equity"]);dd=max(dd,1-r["equity"]/peak)
        xx=[r for r in trades if r["exitDate"][:4]==year]
        w=sum(r["pnl"]>0 for r in xx)
        out[year]={"startEquity":round(init,2),"endEquity":z[-1]["equity"],
             "returnPct":round((z[-1]["equity"]/init-1)*100,3),
             "maxDDPct":round(-100*dd,3),"closedTrades":len(xx),
             "wins":w,"losses":len(xx)-w,
             "winPct":round(w/len(xx)*100,2) if xx else None}
    return out
def parity(picks):
    """Audit overlap against the previous 2026 ranking archive. Never overwrite it."""
    ref=ROOT/"docs/data/backtest_g/g_persistence_2026.json"
    d=json.loads(ref.read_text(encoding="utf-8"))["models"]["G_DOUBLE_PERSIST"]["signals"]
    dates=collections.defaultdict(list)
    for row in d:
        if START<=row["signalDate"]<=END_SIGNAL:dates[row["signalDate"]].append(str(row["code"]))
    matched=0;total=0;byyear={}
    for date,raw in sorted(dates.items()):
        benchmark=sorted(raw)
        reconstructed=sorted(x["code"] for x in picks.get(date,[]))
        overlap=len(set(benchmark)&set(reconstructed))
        matched+=overlap;total+=len(benchmark)
        year=date[:4];a=byyear.setdefault(year,{"ranked":0,"overlap":0,"exactDays":0,"days":0})
        a["ranked"]+=len(benchmark);a["overlap"]+=overlap;a["exactDays"]+=int(benchmark==reconstructed);a["days"]+=1
    return {"referenceSignals":total,"matchedCodes":matched,
            "overlapPct":round(100*matched/total,2) if total else None,
            "byYear":byyear}
def main():
    tic=time.monotonic()
    engine.START=START
    engine.MARKET_END=END_MARK
    engine.synthetic_test()
    # Historical make_g requires all listed and OTC issues for genuine cross-sectional percentiles.
    universe=[x for x in load_universe() if finite(x.get("capitalB")) and float(x["capitalB"])>0]
    if len(universe)<1700:raise RuntimeError("Stock universe unexpectedly small: "+str(len(universe)))
    fetchBegin=datetime.fromisoformat(BEGIN)-timedelta(days=430)
    fetchEnd=datetime.fromisoformat(END_MARK)+timedelta(days=3)
    print("G3Y_PREP",len(universe),"companies","start",fetchBegin.date(),"end",fetchEnd.date(),flush=True)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],fetchBegin,fetchEnd)
    _,ix,error=update_symbol("^TWII",fetchBegin,fetchEnd)
    if error or ix is None or ix.empty:raise RuntimeError("TWII missing "+str(error))
    ix=ix.sort_values("date").drop_duplicates("date",keep="last")
    fullDates=sorted(set(ix.date.astype(str)))
    signalDates=[d for d in fullDates if BEGIN<=d<=END_SIGNAL]
    backtestDates=[d for d in fullDates if "2023-12-01"<=d<=END_MARK]
    if len(signalDates)<680:raise RuntimeError("G 3year calendar missing signal sessions: "+str(len(signalDates)))
    if len([d for d in backtestDates if START<=d<=END_MARK])<660:raise RuntimeError("Insufficient 2024-2026 price calendar")
    if backtestDates[-1]!=END_MARK:raise RuntimeError("Latest market close stale "+backtestDates[-1])
    if len(errors)>max(100,len(universe)*.1):
        raise RuntimeError("Excessive stock OHLC retrieval errors "+str(len(errors)))
    rawPicks,_,audit=make_g(signalDates,ix,universe,hist)
    # The same selection order and universe used in all A/B tests; no future-day stock information.
    picks={d:[{"code":str(x["code"]),"name":x["name"],"market":x["market"],
        "sym":x["sym"],"rank":n+1}
        for n,x in enumerate(rawPicks.get(d,[])[:3])]
        for d in signalDates}
    pAudit=parity(picks)
    print("G3Y_PARITY",json.dumps(pAudit,ensure_ascii=False),flush=True)
    # Preserve 2026 G signal vintage disagreement as explicit caveat; parity must not be invented.
    syms={x["sym"] for p in picks.values() for x in p}
    if len(syms)<150:raise RuntimeError("Suspiciously small 3-year G universe "+str(len(syms)))
    bars={sym:engine.compile_bars(hist.get(sym)) for sym in syms}
    good={s for s,v in bars.items() if len(v)>=60}
    if len(good)<len(syms)*.95:raise RuntimeError(f"Incomplete selected-symbol bars {len(good)}/{len(syms)}")
    rows=[];trades={};curves={}
    for name in MODEL_NAMES:
        metric,log,curve=engine.run_one(name,backtestDates,picks,bars)
        metric["annual"]=annual_stats(curve,log)
        rows.append(metric);trades[name]=log;curves[name]=curve
        print("G3Y_MODEL_OK",name,json.dumps({"netReturnPct":metric["netReturnPct"],
             "endEquity":metric["endEquity"],"maxDrawdownPct":metric["maxDrawdownPct"],
             "closedTrades":metric["closedTrades"],"annual":metric["annual"]},ensure_ascii=False),flush=True)
    details={"version":"G_STOCK_SMA_2024_2026_AB_V1",
      "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "period":{"firstSignal":BEGIN,"portfolioStart":START,"lastSignal":END_SIGNAL,"lastMark":END_MARK},
      "source":{"G":"research_g_regime_3y.make_g; 3D/18D confirmed break and 10-day previous Top20 persistence",
        "GBackfilledNotOriginalArchive":True,"selectedStockCount":len(syms),
        "validSelectedBars":len(good),"universeCount":len(universe),
        "historyErrors":len(errors),"historyErrorExamples":dict(list(errors.items())[:20]),
        "selectedDays":sum(bool(v) for v in picks.values()),"selectedSignals":sum(len(v) for v in picks.values()),
        "parity2026":pAudit,"gRebuildAudit":audit},
      "method":{"initialCapital":engine.INITIAL,"maxPositions":engine.MAX_SLOTS,
        "initialPositionCapPct":100*engine.MAX_WEIGHT,"buyFactor":engine.BUY_FACTOR,
        "sellFactor":engine.SELL_FACTOR,"fill":"D-close signal -> next trade day opening",
        "A":"G Top3 bought next session, held five index sessions",
        "B":"G Top3 and close > own stock SMA10*1.01. Exit on 3 consecutive closes < own SMA10*0.98",
        "executionLimits":"One share units, idealized daily opening, zero borrowing; no gap or stop order assumptions.",
        "caveats":["2024-2025 historical G lists recreated using current listed universe and current paid-in capital.",
          "No daily liquidity / limit-up queue modelling; small share opening fills hypothetical.",
          "Unadjusted stock prices may differ across corporate actions; dividends not separately credited.",
          "Ranking developed from 2026 observations; backtest isn't independently preregistered.",
          "No limit for SMA10 holding time; open positions valued at mark at END_MARK."]},
      "models":rows,"elapsedSeconds":round(time.monotonic()-tic,2)}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"trades.json").write_text(json.dumps({"version":details["version"],"models":trades},ensure_ascii=False),encoding="utf-8")
    (OUT/"equity.json").write_text(json.dumps({"version":details["version"],"models":curves},ensure_ascii=False),encoding="utf-8")
    print("G_AB_THREE_YEAR_SUCCESS",json.dumps({"models":len(rows),"days":len(backtestDates),
      "symbols":len(good),"elapsed":details["elapsedSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
