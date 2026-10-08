"""2026 G_STRICT stop-loss investigation. NO changes to live stock selection.
Only contemporaneous completed signal-date metrics used for risk filters.
Outcomes fixed in prior G_STRICT 10D study; filter diagnostic is post-hoc,
NOT new independent out-of-sample evidence.
"""
from __future__ import annotations
import json,math
from datetime import datetime
from pathlib import Path
import numpy as np,pandas as pd
from scipy.stats import fisher_exact
from yahoo_cache import update_symbol
from config import DATA_DIR
OUT=DATA_DIR/"research/model_execution_2026/g_strict_stop_diagnostic_2026.json"
PERIODS={"early":("2026-01-01","2026-04-30"),"middle":("2026-05-01","2026-07-31"),"late":("2026-08-01","2026-10-07")}
def avg(items,field):
    return round(float(np.mean([x[field] for x in items])),3) if items else None
def metrics(rows):
    filled=[x for x in rows if x["status"]=="filled"]
    n=len(filled);stop=[x for x in filled if x["stop"]];tp=[x for x in filled if x["tp"]]
    return {"allEvents":len(rows),"filled":n,"stopN":len(stop),"stopPct":round(100*len(stop)/n,2) if n else None,
        "tpN":len(tp),"tpPct":round(100*len(tp)/n,2) if n else None,
        "avgNetReservedPct":avg(filled,"netOnReservedPct"),
        "netReservedPerEventPct":round(sum(x["netOnReservedPct"] for x in filled)/len(rows),3) if rows else None,
        "netReservedSum":round(sum(x["netOnReservedPct"] for x in filled),3)}
def values(items,column):
    z=[x["signal"][column] for x in items if x.get("signal") and x["signal"].get(column)is not None]
    return round(float(np.median(z)),2) if z else None
def signal_market():
    _,df,err=update_symbol("^TWII",datetime(2025,5,1),datetime(2026,10,8))
    if err or df is None or df.empty:raise RuntimeError("Index fetch failure "+str(err))
    z=df.sort_values("date").reset_index(drop=True);c=pd.to_numeric(z.close,errors="coerce")
    ma20=c.rolling(20).mean();ma60=c.rolling(60).mean()
    z["ma20"]=ma20;z["ma60"]=ma60;z["ret5"]=(c/c.shift(5)-1)*100
    z["ret10"]=(c/c.shift(10)-1)*100;z["ma20trend"]=ma20/ma20.shift(5)-1
    z["draw20"]=(c/c.shift(1).rolling(20).max()-1)*100
    z["belowMA20"]=c<ma20;z["belowMA60"]=c<ma60;z["ma20down"]=z["ma20trend"]<0
    z["bad5"]=z["ret5"]<(-2);z["bad10"]=z["ret10"]<(-4)
    z["down5"]=c<c.shift(5)
    hi60=c.shift(1).rolling(60,min_periods=45).max();lo60=c.shift(1).rolling(60,min_periods=45).min()
    hi120=c.shift(1).rolling(120,min_periods=80).max();lo120=c.shift(1).rolling(120,min_periods=80).min()
    z["position60"]=(c-lo60)/(hi60-lo60).replace(0,np.nan)*100
    z["position120"]=(c-lo120)/(hi120-lo120).replace(0,np.nan)*100
    z["distHigh60"]=(c/hi60-1)*100
    z["distMA60"]=(c/ma60-1)*100
    z["distMA20"]=(c/ma20-1)*100
    z["favorable"]=(~z["belowMA20"])&(~z["ma20down"])&(z["position60"]>=50)
    z["caution"]=(z["position60"]<35)|(z["belowMA60"]&z["ma20down"])
    return {str(r.date):r for r in z.itertuples(index=False)}
def run():
    source=json.loads((DATA_DIR/"backtest_g/2026-01-01_2026-10-07.json").read_text(encoding="utf-8"))
    trade=json.loads((DATA_DIR/"research/model_execution_2026/trades/G_STRICT.json").read_text(encoding="utf-8"))
    signals={(x["signalDate"],x["code"]):x for x in source["models"]["G_STRICT"]["signals"]}
    market=signal_market()
    modes={}
    for mode in ("ladder","ma"):
        all=[]
        for t in trade["10"][mode]:
            s=signals.get((t["date"],t["code"]));mk=market.get(t["date"])
            if s is None:continue
            x={**t,"signal":s,"market":{key:getattr(mk,key) for key in
              ("close","ma20","ma60","ret5","ret10","ma20trend","draw20","belowMA20","belowMA60","ma20down","bad5","bad10","down5","position60","position120","distHigh60","distMA60","distMA20","favorable","caution")} if mk is not None else None}
            all.append(x)
        f=[x for x in all if x["status"]=="filled"]
        stop=[x for x in f if x["stop"]];tp=[x for x in f if x["tp"]];others=[x for x in f if not x["stop"]]
        filters={
            "All":"All signals", "only_rank1":"Rank1 only",
            "rank12":"Rank <=2",
            "exclude_breakout9":"Signal 20D breakout <9%",
            "no_negative_breakout":"Signal breakout >=0%",
            "atrTop5":"Signal ATR cross-sectional >=95th pct",
            "turnTop5":"Signal turnover cross-sectional >=95th pct",
            "score97":"Signal score >=97",
            "indexFavorable":"TWII >= MA20, MA20 not declining, position60 >=50",
            "indexNotCaution":"TWII position60 >=35, no MA60 below + MA20 down",
            "indexPosition60ge20":"TWII 60D position >=20%",
            "indexPosition60ge35":"TWII 60D position >=35%",
            "indexPosition60ge50":"TWII 60D position >=50%",
            "indexPosition60ge65":"TWII 60D position >=65%",
            "indexPosition120ge35":"TWII 120D position >=35%",
            "indexPosition120ge50":"TWII 120D position >=50%",
            "indexPosition120ge65":"TWII 120D position >=65%",
            "indexPos60ge35AboveMA20":"TWII pos60 >=35 and close>=MA20",
            "indexPos60ge35AboveMA60":"TWII pos60 >=35 and close>=MA60",
            "indexPos60ge50MA20up":"TWII pos60 >=50 and MA20 slope >=0",
            "indexAboveMA20":"TWII signal-day close >=20D MA",
            "indexAboveMA60":"TWII signal-day close >=60D MA",
            "indexMA20up":"TWII 20D MA slope over 5 sessions >=0",
            "indexNotDown2Pct5D":"TWII 5D return >=-2%",
            "indexNotDown4Pct10D":"TWII 10D return >=-4%",
            "indexNotDown5Days":"TWII close >=5D ago",
            "rank1_indexAbove20":"Rank1 and TWII >= MA20",
            "rank12_indexAbove20":"Rank <=2 and TWII >=MA20",
            "rank12_indexUp":"Rank <=2 and TWII MA20 slope >=0",
        }
        def check(k,x):
            s=x["signal"];i=x["market"]
            if k=="All":return True
            if k=="only_rank1":return s["rank"]==1
            if k=="rank12":return s["rank"]<=2
            if k=="exclude_breakout9":return s["breakoutPct"]<9
            if k=="no_negative_breakout":return s["breakoutPct"]>=0
            if k=="atrTop5":return s["atrP"]>=95
            if k=="turnTop5":return s["turnoverP"]>=95
            if k=="score97":return s["score"]>=97
            if i is None:return False
            if k=="indexFavorable":return bool(i["favorable"])
            if k=="indexNotCaution":return not bool(i["caution"])
            if k=="indexPosition60ge20":return i["position60"]>=20
            if k=="indexPosition60ge35":return i["position60"]>=35
            if k=="indexPosition60ge50":return i["position60"]>=50
            if k=="indexPosition60ge65":return i["position60"]>=65
            if k=="indexPosition120ge35":return i["position120"]>=35
            if k=="indexPosition120ge50":return i["position120"]>=50
            if k=="indexPosition120ge65":return i["position120"]>=65
            if k=="indexPos60ge35AboveMA20":return i["position60"]>=35 and not i["belowMA20"]
            if k=="indexPos60ge35AboveMA60":return i["position60"]>=35 and not i["belowMA60"]
            if k=="indexPos60ge50MA20up":return i["position60"]>=50 and not i["ma20down"]
            if k=="indexAboveMA20":return not i["belowMA20"]
            if k=="indexAboveMA60":return not i["belowMA60"]
            if k=="indexMA20up":return not i["ma20down"]
            if k=="indexNotDown2Pct5D":return not i["bad5"]
            if k=="indexNotDown4Pct10D":return not i["bad10"]
            if k=="indexNotDown5Days":return not i["down5"]
            if k=="rank1_indexAbove20":return s["rank"]==1 and not i["belowMA20"]
            if k=="rank12_indexAbove20":return s["rank"]<=2 and not i["belowMA20"]
            if k=="rank12_indexUp":return s["rank"]<=2 and not i["ma20down"]
            raise KeyError(k)
        result={}
        for key in filters:
            accept=[x for x in all if check(key,x)]
            reject=[x for x in all if not check(key,x)]
            held=[x for x in f if check(key,x)]
            sid=[x for x in stop if check(key,x)]
            lost=[x for x in tp if not check(key,x)]
            # fixed-baseline table only; event filtering does NOT re-fill empty Top3 slots
            slices={name:metrics([x for x in accept if lo<=x["date"]<=hi]) for name,(lo,hi) in PERIODS.items()}
            table=[[len(sid),len(held)-len(sid)],
                    [len(stop)-len(sid),len(f)-len(held)-(len(stop)-len(sid))]]
            fisher=float(fisher_exact(table,alternative="two-sided").pvalue) if __import__("builtins").all(sum(row)>0 for row in table) else None
            result[key]={"description":filters[key],"accepted":metrics(accept),"rejected":metrics(reject),
                         "fractionStopsAvoided":round((len(stop)-len(sid))/len(stop)*100,2) if stop else None,
                         "profitTakingSignalsLost":len(lost),
                         "fractionTPsForgone":round(len(lost)/len(tp)*100,2) if tp else None,
                         "fisherTwoSidedP":round(fisher,5) if fisher is not None else None,
                         "slices":slices,"july":metrics([x for x in accept if x["date"].startswith("2026-07")]),"julySkipped":metrics([x for x in reject if x["date"].startswith("2026-07")])}
        months={}
        for x in f:
            month=x["date"][:7]
            months.setdefault(month,[]).append(x)
        months={k:metrics(v) for k,v in sorted(months.items())}
        seen={k:{"stop":values(stop,k),"tp":values(tp,k),"other":values(others,k)} for k in
              ["score","ret20P","slopeP","atrP","range20P","turnoverP","breakoutPct","rank"]}
        ranks={str(k):metrics([x for x in f if x["rank"]==k]) for k in (1,2,3)}
        stoplog=[{"date":x["date"],"code":x["code"],"name":x["name"],"rank":x["rank"],
                  "signalScore":x["signal"]["score"],"signalBreakoutPct":x["signal"]["breakoutPct"],
                  "buyLots":x["tranches"],"start":x["firstEntryDate"],"exit":x["exitDate"],
                  "reason":x["reason"],"netReservedPct":x["netOnReservedPct"],
                  "signalTWII":{"close":round(x["market"]["close"],2),"aboveMA20":not x["market"]["belowMA20"],
                  "aboveMA60":not x["market"]["belowMA60"],"ret5":round(x["market"]["ret5"],2),
                  "position60":round(x["market"]["position60"],1),"position120":round(x["market"]["position120"],1)}
                  if x["market"] is not None else None} for x in stop]
        modes[mode]={"baseline":metrics(all),"rankSummary":ranks,"bySignalMonth":months,
                     "signalFeatureMedians":seen,"stopLots":{str(n):sum(x["tranches"]==n for x in stop) for n in range(1,6 if mode=="ladder" else 5)},
                     "tpLots":{str(n):sum(x["tranches"]==n for x in tp) for n in range(1,6 if mode=="ladder" else 5)},
                     "filters":result,"stopTrades":stoplog}
        print("RISK_DIAG "+json.dumps({"mode":mode,"baseline":metrics(all),"rank":ranks,"filters":{k:{"filled":v["accepted"]["filled"],"stops":v["accepted"]["stopN"],"stopPct":v["accepted"]["stopPct"],"meanReserved":v["accepted"]["avgNetReservedPct"],"forgoneTP":v["profitTakingSignalsLost"],"avoidedStop":v["fractionStopsAvoided"],"p":v["fisherTwoSidedP"],"late":v["slices"]["late"]["stopPct"],"july":v["july"]} for k,v in result.items()}},ensure_ascii=False),flush=True)
    report={"version":"G_STRICT_2026_STOP_SIGNAL_FEATURES_AND_TWII_MARKET_1",
            "asOf":"2026-10-07","period":"2026-01-01..2026-10-07",
            "baseline":"Frozen G_STRICT Rank1-3, 5-tranche ladder or 4-SMA touch, gross TP +7% and stop -15%, 10D maximum holding, first limit valid next 5 sessions",
            "signalFeaturesFrom":"docs/data/backtest_g/2026-01-01_2026-10-07.json",
            "tradeOutcomesFrom":"docs/data/research/model_execution_2026/trades/G_STRICT.json",
            "index":"Yahoo ^TWII signal-date completed close, only present and prior trailing values",
            "positionFormula":"100 * (signal-day TWII close - previous 60/120-session LOW) / (previous 60/120-session HIGH - LOW). It may exceed 100 or go below zero on new highs/lows; not clamped.",
            "warnings":["ALL risk factor results are post-hoc diagnostic on already-selected 2026 data; no fresh out-of-sample and numerous thresholds inspected.",
             "Filters applied to ALREADY generated and de-duplicated trade events; removing signals does NOT refill ranks or recompute altered watch occupancy. It is not a new full portfolio backtest.",
             "In 5-tranche ladder all stop-loss trades have hit all 5 tranches by construction of a downward path; this is descriptive after entry, not a usable at-selection filter.",
             "Market weakness only uses signal day and cannot prevent a subsequent sharp selloff within a 5-session pending order or while in trade.",
             "Daily OHLC cannot determine true intra-bar prices/order or limit fills; -15% stop can gap beyond.",
             "Monthly clustering and 2026 risk rules are research hypotheses, NOT an independently verified hedge.","Stock universe suffers possible survivor and corporate-action biases."],
            "modes":modes}
    OUT.parent.mkdir(exist_ok=True,parents=True);OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print("RISK_DIAG_DONE "+json.dumps({"output":str(OUT),"modes":{k:v["baseline"] for k,v in modes.items()},"sampleJuly":{k:v["bySignalMonth"].get("2026-07") for k,v in modes.items()}},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
