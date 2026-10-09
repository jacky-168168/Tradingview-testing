"""Exact 2024-2026 continuous 00675L buy-and-hold vs EMA10 compound and fixed account parity."""
from __future__ import annotations
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from research_00675l_reinvestment import simulate_sizing,BASE_RULE,OUT,years_from_continuous,compact,CAPITAL
from research_00675l_swing_grid import SYMBOL,INDEX,data_prepare,update_symbol
def run():
    _,etf,e=update_symbol(SYMBOL,datetime(2023,5,1),datetime(2026,10,9))
    _,idx,e2=update_symbol(INDEX,datetime(2023,5,1),datetime(2026,10,9))
    if e or e2 or etf is None or idx is None or etf.empty or idx.empty:raise RuntimeError(str((e,e2)))
    d=data_prepare(etf,idx)
    reference=json.loads((OUT/"reinvestment_summary.json").read_text(encoding="utf-8"))
    comp=reference["comparison"]["all_profit_reinvest"]["byPeriod"]["continuous_2024_2026"]
    fixed=reference["comparison"]["fixed_100m"]["byPeriod"]["continuous_2024_2026"]
    hold_rule={"id":"BUY_HOLD","family":"buy_hold"}
    hold=simulate_sizing(d,hold_rule,"2024-01-01","2026-10-08",True,1)
    hold26=simulate_sizing(d,hold_rule,"2026-01-01","2026-10-08",True,1)
    swing=simulate_sizing(d,BASE_RULE,"2024-01-01","2026-10-08",True,1)
    for v,ref in ((swing,comp),(hold26,{"returnPct":150.836})):
        assert v["returnPct"]==ref["returnPct"],(v["returnPct"],ref["returnPct"])
    h=hold["dailyEquity"][-1]["equity"]
    other=comp["endingEquityNTD"]
    data={"ticker":SYMBOL,"period":"2024-01-01 to 2026-10-08","actualCloseDate":d.iloc[-1].date,
        "initialNTD":CAPITAL,"buyHold":{**compact(hold),"endingNTD":h,
                    "yearly":years_from_continuous(hold["dailyEquity"]),"events":hold["events"]},
        "ema10Compound":{"returnPct":comp["returnPct"],"endingNTD":other,"maxDrawdownPct":comp["maxDrawdownPct"],
                         "trades":comp["trades"],"yearly":comp["yearlyReturns"]},
        "ema10Fixed":{"returnPct":fixed["returnPct"],"endingNTD":fixed["endingEquityNTD"],
                      "maxDrawdownPct":fixed["maxDrawdownPct"],"trades":fixed["trades"]},
        "buyHold2026":compact(hold26),
        "gap":{"buyHoldMinusCompoundNTD":round(h-other,2),
               "buyHoldMinusCompoundReturnPP":round(hold["returnPct"]-comp["returnPct"],3)},
        "execution":"Starting 1m TWD in ETF at first 2024 market open. Cash buy whole units; marked liquidating at final 2026 market close with fees and 0.1% slippage; dividends/splits handled by existing Yahoo adjustment model.",
        "note":"Continuous account; no new annual deposits. Buy-and-hold includes terminal hypothetical sale for fee-consistent equity comparison. No 2m signal execution."}
    (OUT/"buyhold_vs_compound_continuous.json").write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("00675L_EXACT_CONTINUOUS_COMPARISON "+json.dumps({k:data[k] for k in ("period","actualCloseDate","initialNTD","gap")},ensure_ascii=False),flush=True)
    print("BUYHOLD "+json.dumps({k:data["buyHold"][k] for k in ("endingNTD","returnPct","maxDrawdownPct","trades","yearly")},ensure_ascii=False),flush=True)
    print("SWING "+json.dumps(data["ema10Compound"],ensure_ascii=False),flush=True)
if __name__=="__main__":run()
