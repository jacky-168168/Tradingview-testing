"""Run historical MOPS growth baseline vs fully verified ROE/PB fixed-rule overlay.
No returns will be invented if historical quotes or ROE/PB are unavailable.
"""
import json,math,sys
from datetime import datetime,timedelta
from pathlib import Path
from config import DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol
from stock_fundamentals import read_archive
from stock_quality import read_quality_archive
from quality_backtest_core import adjopen,rows_by_day,simulate,summary,BUY
OUT=DATA_DIR/"research"/"quality"/"backtest.json"
FOLDS={"validation2024":("2024-01-01","2024-12-31"),
       "oos2025":("2025-01-01","2025-12-31"),
       "audit2026":("2026-01-01","2026-10-09")}
def benchmark(bars,records):
    if not records:return {"status":"no_periods"}
    first=records[0]["entry"];last=records[-1]["exit"]
    v=bars.get("0050.TW",{})
    p=adjopen(v.get(first,{}));q=adjopen(v.get(last,{}))
    if p is None or q is None:return {"status":"missing_adjusted_open"}
    etf_sell=.003425 # 0.1425% brokerage + 0.1% ETF tax + 0.1% slippage
    value=1_000_000*q/p*(1-etf_sell)/(1+BUY)
    years=(datetime.fromisoformat(last)-datetime.fromisoformat(first)).days/365.2425
    return {"status":"ok","symbol":"0050.TW","entry":first,"exit":last,
        "totalReturnPct":round((value/1_000_000-1)*100,3),
        "cagrPct":round(((value/1_000_000)**(1/years)-1)*100,3) if years>0 else None,
        "method":"One-time buy-and-hold, Yahoo adjusted open, brokerage+tax+0.1% side slippage"}
def main():
    archive,error=read_archive(DATA_DIR)
    if archive is None:raise RuntimeError("Historical official MOPS archive incomplete: "+str(error))
    quality,quality_errors=read_quality_archive(DATA_DIR)
    valid_quality=bool(quality and len(quality.pbkeys)>=200 and len(quality.roekeys)>=200)
    if not valid_quality:quality=None
    source=DATA_DIR/"research"/"g_regime_3y"/"market_risk_daily.json"
    dates=sorted(x["date"] for x in json.loads(source.read_text(encoding="utf-8")) if "2023-01-01"<=x["date"]<="2026-10-09")
    if len(dates)<600:raise RuntimeError("Insufficient market calendar; cannot backtest 3-year history")
    universe=load_universe()
    begin=datetime(2022,10,1);end=datetime(2026,10,10)
    histories,errors=update_many([(s["code"],s["market"]) for s in universe],begin,end)
    _,etf,e=update_symbol("0050.TW",begin,end)
    if e or etf is None or etf.empty:raise RuntimeError("0050 adjusted benchmark absent: "+str(e))
    missing=[s for s in universe if histories.get(s["code"]+(".TW" if s["market"]=="上市" else ".TWO")) is None]
    if len(missing)>len(universe)*.08:raise RuntimeError("More than 8% of universe has no market quotes")
    bars={symbol:rows_by_day(df) for symbol,df in histories.items() if df is not None and not df.empty}
    bars["0050.TW"]=rows_by_day(etf)
    all_months=simulate(universe,bars,archive,quality,dates)
    folds={}
    for name,(start,end_day) in FOLDS.items():
        groups={strategy:[r for r in rows if start<=r["signal"]<=end_day]
                for strategy,rows in all_months.items()}
        periods=groups["growth"]
        if not periods:raise RuntimeError("Missing evaluation intervals "+name)
        folds[name]={"growth":summary(groups["growth"],periods[0]["entry"],periods[-1]["exit"]),
          "quality":summary(groups["quality"],periods[0]["entry"],periods[-1]["exit"]),
          "benchmark0050":benchmark(bars,periods),
          "monthlyIntervals":len(periods)}
    report={"version":"FUNDAMENTAL_QUALITY_ROE_PB_GROWTH_V1",
      "status":"full_quality_ready" if valid_quality else "growth_baseline_only",
      "rules":{"signal":"previous month last complete daily close","entry":"next trading session adjusted open",
        "exit":"one month later next trading session adjusted open",
        "growth":"EPS YTD YoY>=10%, revenue YoY>=10%, positive TTM EPS, revenue 12-month high ratio>=80%",
        "quality":"growth + ROE>=15%, official 0.3<=PB<=12, trailing 3y PB percentile<=50, >=120 PB samples",
        "topN":10,"minStocks":5,"buyCostPct":.2425,"sellCostPct":.5425,
        "qualityIfMissing":"do not calculate; NEVER treat as zero return",
        "capitalTWD":1000000},
      "limitations":["Current survivor company universe; historical delistings not reconstructed",
        "Revised MOPS fiscal data with conservative publication-delay proxy, not immutable original filings",
        "Returns use Yahoo adjusted daily OHLC proxies; financial events and open execution may differ",
        "CAGR and drawdown based on monthly NAV, not intra-month risk",
        "Fixed screening thresholds selected BEFORE looking at results; no parameter fitting"],
      "priceErrorsCount":len(errors),"historicalUniverse":len(universe),
      "roeSymbols":len(quality.roekeys) if quality else 0,
      "pbSymbols":len(quality.pbkeys) if quality else 0,
      "missingQualityReasons":quality_errors if not valid_quality else [],
      "folds":folds,"monthly":all_months}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,separators=(",",":")),encoding="utf8")
    print("FUNDAMENTAL_BACKTEST",json.dumps({"status":report["status"],"folds":folds},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
