"""Frozen selector x two execution style matrix. RESEARCH / NO production change.

Signals:
  A,D: existing published all-2026 backtest archive (unchanged).
  G_BROAD, G_3D_BREAK, G_18D_BREAK, G_DOUBLE_BREAK, G_TRIGGER,
  G_ENGULF: published 2026 G candle archive (unchanged).
  G_PERSIST, G_DOUBLE_PERSIST: published persistence archive (unchanged).
  H5_FRESH_BREAK: existing GitHub Actions archived frozen H5 top3.
NO reranking, threshold optimization, or model cherry-picking before report.
Executions exactly matching backtest_g_exec_comparison.py.
"""
from __future__ import annotations
import json,time,sys
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np,pandas as pd
from yahoo_cache import update_many,update_symbol,to_symbol
from pipeline import load_universe
from config import DATA_DIR
from backtest_g_exec_comparison import prepare_bars,run_model,summary,INITIAL_WAIT_DAYS,START,END
MODELS=("A","D","G_BROAD","G_3D_BREAK","G_18D_BREAK","G_DOUBLE_BREAK",
        "G_TRIGGER","G_ENGULF","G_PERSIST","G_DOUBLE_PERSIST","H5_FRESH_BREAK")
HORIZONS=(5,10,20)
MODES=("ladder","ma")
def source_signals():
    master=json.loads((DATA_DIR/"backtest/2026-01-01_2026-10-07.json").read_text(encoding="utf-8"))
    candle=json.loads((DATA_DIR/"backtest_g/g_candle_2026.json").read_text(encoding="utf-8"))
    persist=json.loads((DATA_DIR/"backtest_g/g_persistence_2026.json").read_text(encoding="utf-8"))
    hpath=DATA_DIR/"research_input/H5_ladder_2026_top3.json"
    if not hpath.exists():raise FileNotFoundError(f"H5 source not present: {hpath}. workflow must download frozen H5 source artifact.")
    h5=json.loads(hpath.read_text(encoding="utf-8"))
    out={}
    am={str(x.get("id")):x for x in master["models"]} if isinstance(master["models"],list) else master["models"]
    for key in ("A","D"):
        if key not in am:raise RuntimeError(f"No published selector {key}")
        out[key]=am[key]["signals"]
    for key in MODELS:
        if key in candle.get("models",{}):out[key]=candle["models"][key]["signals"]
        if key in persist.get("models",{}):out[key]=persist["models"][key]["signals"]
    out["H5_FRESH_BREAK"]=[{"signalDate":x["date"],"rank":x["rank"],"code":x["code"],"name":x["name"],"market":x["market"],"score":x["score"]} for x in h5]
    for key in MODELS:
        if key not in out:raise RuntimeError("No model "+key)
        for s in out[key]:
            if not all(z in s for z in ("signalDate","rank","code","name")):raise RuntimeError(f"Malformed stock event in {key}")
    return out,{"A_D":master.get("period"),"G_CANDLE":candle.get("period"),"G_PERSIST":persist.get("period"),
        "H5_FRESH_BREAK":{"archive":"GitHub Actions run 37801819940 artifact 11561507449","n":len(h5)}}
def risk_stats(rows):
    filled=[x for x in rows if x["status"]=="filled"]
    attempted=[x for x in rows if x["status"]in("filled","unfilled","weak_cancel")]
    n=len(attempted);fv=[float(x["netOnReservedPct"]) for x in filled]
    # *Every eligible event* reserved four or five full tranches; missed limits have no profit.
    all_return=[float(x.get("netOnReservedPct",0)) for x in attempted]
    partial=[x for x in filled if x.get("date","")<="2026-05-29"]
    late=[x for x in filled if x.get("date","")>="2026-06-01"]
    def part(s):
        return {"n":len(s),"meanNetOnReservedPct":round(float(np.mean([x["netOnReservedPct"] for x in s])),3) if s else None,
            "tpPct":round(100*sum(x["tp"] for x in s)/len(s),2) if s else None}
    losers=[x for x in filled if x["netOnReservedPct"]<0]
    return {"allEligibleEvents":n,"fillPct":round(100*len(filled)/n,2) if n else None,
        "perEligibleSignalAvgNetOnReservedPct":round(float(np.mean(all_return)),3) if all_return else None,
        "filledNetOnReservedMedianPct":round(float(np.median(fv)),3) if fv else None,
        "filledNetOnReservedWorstPct":round(float(np.min(fv)),3) if fv else None,
        "p05FilledNetOnReservedPct":round(float(np.quantile(fv,.05)),3) if fv else None,
        "negativeReservedEvents":len(losers),"earlyJanMay":part(partial),"laterJuneOct":part(late),
        "avgReservedAtRiskPct":round(float(np.mean([x["tranches"]/(5 if x.get("mode")=="ladder" else 4)*100 for x in filled])),2) if filled else None}
def run():
    start=time.time()
    source,meta=source_signals()
    universe=load_universe();securities={str(x["code"]):x for x in universe}
    retained={};exceptions={}
    for model in MODELS:
        src=source[model];rs=[]
        for x in src:
            code=str(x["code"]);stock=securities.get(code)
            if not stock or not START<=x["signalDate"]<=END or int(x["rank"])>3:continue
            market=x.get("market") or stock["market"]
            # Master list is source of suffix. Some backtest signals have market already.
            if market!=stock["market"]:exceptions[code]=(market,stock["market"])
            rs.append({**x,"code":code,"market":stock["market"]})
        retained[model]=rs
        print("SELECTOR_SOURCE "+json.dumps({"name":model,"rawSignals":len(src),"matched":len(rs),"days":len(set(x["signalDate"] for x in rs)),
              "symbols":len(set(x["code"] for x in rs))},ensure_ascii=False),flush=True)
    syms=sorted({(x["code"],x["market"]) for rs in retained.values() for x in rs})
    print("MATRIX_PRCACHE symbols="+str(len(syms)),flush=True)
    ds=datetime(2025,8,1);de=datetime(2026,10,8)
    hist,errors=update_many(syms,ds,de)
    _,idx,err=update_symbol("^TWII",ds,de)
    if err or idx is None or idx.empty:raise RuntimeError("Missing market dates: "+str(err))
    cal=[x for x in idx.date.astype(str) if x<=END]
    prices={sym:prepare_bars(df) for sym,df in hist.items()}
    research={}; details={};model_comp=[]
    for model in MODELS:
        research[model]={};details[model]={}
        for h in HORIZONS:
            research[model][str(h)]={};details[model][str(h)]={}
            for method in MODES:
                trades,duplicates=run_model(retained[model],prices,cal,h,method)
                for row in trades:row["mode"]=method
                stat=summary(trades,duplicates,method,h)
                extra=risk_stats(trades)
                research[model][str(h)][method]={**stat,**extra}
                details[model][str(h)][method]=trades
                print("MATRIX_CELL "+json.dumps({"model":model,"h":h,"entry":method,
                    "filled":stat["filled"],"tpPct":stat.get("takeProfitPct"),
                    "netDeployed":stat.get("avgNetOnDeployedPct"),
                    "netReserved":stat.get("avgNetOnReservedPct"),
                    "perEligible":extra.get("perEligibleSignalAvgNetOnReservedPct"),
                    "suppressed":duplicates},ensure_ascii=False),flush=True)
        # 10D MAIN diagnostic ranking: same rules across all models; no tuning beyond showing a comparison.
        for method in MODES:
            p=research[model]["10"][method]
            model_comp.append({"selector":model,"style":method,"filled":p["filled"],
              "netBudgetPct":p.get("avgNetOnReservedPct"),
              "netEligiblePct":p.get("perEligibleSignalAvgNetOnReservedPct"),
              "tpPct":p.get("takeProfitPct"),"stopPct":p.get("stopPct"),
              "capitalExposure":p.get("avgTranches"),"unique":p.get("distinctStocks")})
    matrix=sorted(model_comp,key=lambda x:(
        x["netEligiblePct"] is None,
        -(x["netEligiblePct"] if x["netEligiblePct"] is not None else -10000),
        -(x["filled"] or 0)))
    result={"version":"SELECTION_X_ENTRY_2026_V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
      "period":{"start":START,"end":END},"dataSources":meta,
      "comparisonScope":"A,D, G variants, frozen H5 selection; fixed same execution and same historical OHLC; exploratory retrospective 2026, NOT independent validation",
      "executions":{"ladder":"first signal-close -2.5% within 5 sessions, then 4×2% lower (first ACTUAL fill anchor), up to 5 equal-cash lots",
      "ma":"only touch prior confirmed SMA5/10/20/60 during daily candle, each at most once, up to 4 equal-cash lots; track stop MA60 weakness",
      "common":"average-cost TP+7% gross; SL-15% gross; holding 5/10/20 sessions after first entry, buy/sell fees and tax and assumed slippage; stock overlapping signal suppressed while own watch/position open"},
      "calendarDays":len(cal),"universe":len(universe),"selectedUniqueSymbols":len(syms),
      "priceErrorCount":len(errors),"priceErrorSample":list(errors.items())[:8],
      "marketMismatches":exceptions,"modelSources":{k:{"events":len(v),"days":len(set(x["signalDate"] for x in v)),"stocks":len(set(x["code"] for x in v))} for k,v in retained.items()},
      "scoreboard10DExploratory":matrix,"results":research,
      "limits":["2026 already used in previous model development; this IS NOT a new independent out-of-sample year.",
        "H5 Top3 had distinct forward source from previous research; no 2026 H5 selector hyperparam search in this run.",
        "A,D,G candidates may have different eligible signal day coverage and signal frequencies; compare covered days and fill counts.",
        "Same-symbol repeated signals suppressed; between-symbol overlapping baskets not shared-cash constrained.",
        "Reserved-capital per-event returns cannot be added or compounded into a realistic account strategy.",
        "MA weakness implementation is two previous completed closes below their MA60 and MA20 declines over three bars; user has not finalized this definition.",
        "Daily high/low cannot recover intraday chronology; conservative new intraday buy prevents same-day TP credit.",
        "Actual Taiwan limit lock, corporate actions and broker order queue may differ significantly from model; no 2min data."],
      "elapsedSeconds":round(time.time()-start,1)}
    path=DATA_DIR/"research_selector_matrix";path.mkdir(parents=True,exist_ok=True)
    (path/"selection_x_entry_matrix_2026.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    (path/"selection_x_entry_trades_2026.json").write_text(json.dumps(details,ensure_ascii=False,indent=2),encoding="utf-8")
    print("MATRIX_DONE "+json.dumps({"models":len(MODELS),"pairCount":len(MODELS)*2,
        "priceErrorCount":len(errors),"rank10":matrix,
        "sourceCount":{k:len(v) for k,v in retained.items()},"elapsedSeconds":result["elapsedSeconds"]},ensure_ascii=False),flush=True)
    return result
if __name__=="__main__":run()
