"""00675L dynamic defensive holding, 2024-25 model selection / frozen 2026 follow-up.
The target is retaining buy-and-hold upside with actual sell/buyback events, not optimizing
2026 results in the candidate search. ETF's inherent 2x resets daily; account does not borrow.
"""
from __future__ import annotations
import json,time,math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from research_00675l_swing_grid import data_prepare,SYMBOL,INDEX,SLIP,BROKER,ETF_SELL_TAX,CAPITAL,DATA_DIR,update_symbol
OUTPUT=DATA_DIR/"research/etf_00675l_regime_capture_2024_2026"
PERIODS={"2024":("2024-01-01","2024-12-31"),"2025":("2025-01-01","2025-12-31"),
         "2026":("2026-01-01","2026-10-08"),"train":("2024-01-01","2025-12-31"),
         "continuous":("2024-01-01","2026-10-08")}
def prepare(d):
    d=d.copy()
    for name in ("close","twii"):
        for n in (10,20,30,40,60,90,120,150,180,200):
            d[f"{name}_ema{n}"]=d[name].ewm(span=n,adjust=False,min_periods=n).mean()
            d[f"{name}_sma{n}"]=d[name].rolling(n,min_periods=n).mean()
    for n in (2,3,5,10):d[f"ret_{n}"]=d.close/d.close.shift(n)-1
    for n in (20,40,60,120,200):d[f"rollHigh{n}"]=d.close.rolling(n,min_periods=n).max()
    return d
def universe():
    x=[{"id":"BUY_HOLD","family":"buyhold","riskOffWeight":1.0}]
    for src in ("close","twii"):
        for n in (20,40,60,90,120,180):
            for out in (.00,.03,.06,.10):
                for rein in (.00,.02,.04):
                    for confirm in (1,3):
                        for risk_weight in (0.0,.5):
                            x.append({"id":f"MA_{src}_{n}_O{out}_R{rein}_C{confirm}_W{risk_weight}",
                                      "family":"ma_hysteresis","src":src,"n":n,"out":out,"rein":rein,
                                      "confirm":confirm,"riskOffWeight":risk_weight})
    for n in (20,40,60,120,200):
        for dd in (.08,.12,.16,.20,.25):
            for re in (10,20,40,60,120):
                for weight in (0.0,.5):
                    x.append({"id":f"TRAIL_{n}_{dd}_RE{re}_W{weight}","family":"peak_drawdown",
                             "n":n,"dd":dd,"re":re,"riskOffWeight":weight})
    for n in (2,3,5):
        for fall in (.06,.10,.14,.18):
            for re in (10,20,40,60):
                for filter in ("all","twii_below60"):
                    for weight in (0.0,.5):
                        x.append({"id":f"CRASH_{n}_{fall}_RE{re}_G{filter}_W{weight}",
                            "family":"crash_protection","n":n,"fall":fall,"re":re,"gate":filter,
                            "riskOffWeight":weight})
    for src in ("close","twii"):
        for trend_n in (40,60,120):
            for fast_n in (10,20,40):
                for re in (10,20):
                    for weight in (0.0,.5):
                        x.append({"id":f"DUAL_{src}_{trend_n}_{fast_n}_RE{re}_W{weight}",
                          "family":"dual_trend","src":src,"slow":trend_n,"fast":fast_n,"re":re,
                          "riskOffWeight":weight})
    assert len({c["id"] for c in x})==len(x)
    return x
def indicators(d):
    arr={k:pd.to_numeric(d[k],errors="coerce").to_numpy(dtype=float) for k in d.columns if k not in ("date",) and pd.api.types.is_numeric_dtype(d[k])}
    dates=d.date.to_numpy(dtype=str)
    return arr,dates
def risk_state(c,a,i,off):
    fam=c["family"]
    if fam=="buyhold":return True
    n=c.get("n")
    if fam=="ma_hysteresis":
        v=a[c["src"]][i];ma=a[f"{c['src']}_ema{n}"][i]
        if not np.isfinite(ma):return True
        if not off:
            conf=c["confirm"];p=v<ma*(1-c["out"])
            if conf==3 and i>=2:
                for j in (i-1,i-2):
                    m=a[f"{c['src']}_ema{n}"][j]
                    p=p and np.isfinite(m) and a[c["src"]][j]<m*(1-c["out"])
            return not p
        return v>ma*(1+c["rein"])
    if fam=="peak_drawdown":
        roll=a[f"rollHigh{n}"][i]
        if not np.isfinite(roll):return True
        if not off:return a["close"][i]>(1-c["dd"])*roll
        ma=a[f"close_ema{c['re']}"][i]
        return np.isfinite(ma) and a["close"][i]>ma
    if fam=="crash_protection":
        look=a[f"ret_{n}"][i]
        if not off:
            risk=bool(np.isfinite(look) and look<-c["fall"])
            if c["gate"]=="twii_below60":
                risk=risk and a["twii"][i]<a["twii_ema60"][i]
            return not risk
        ma=a[f"close_ema{c['re']}"][i]
        return np.isfinite(ma) and a["close"][i]>ma
    if fam=="dual_trend":
        src=c["src"];s=a[f"{src}_ema{c['slow']}"][i];f=a[f"{src}_ema{c['fast']}"][i];v=a[src][i]
        if not (np.isfinite(s) and np.isfinite(f)):return True
        if not off:return f>s and v>s
        fast=a[f"{src}_ema{c['re']}"][i]
        return v>s and v>fast
    raise ValueError(fam)
def bt(a,dates,c,begin,end,detailed=False):
    idx=np.where((dates>=begin)&(dates<=end))[0]
    if len(idx)<50:raise RuntimeError("insufficient bars "+begin)
    cash=float(CAPITAL);shares=0;state=True;trades=[];events=[];equity=[];regime_days=0;traded_days=0
    opens=a["open"];closes=a["close"];buy_factor=(1+SLIP)*(1+BROKER);sell_factor=(1-SLIP)*(1-BROKER-ETF_SELL_TAX)
    for pos,i in enumerate(idx):
        date=dates[i];px=float(opens[i]);mark=float(closes[i]);oldshares=shares
        if pos==0:
            desired=True
        else:
            # Causal: previous close decides trades at today's open, never today's close.
            j=i-1;desired=risk_state(c,a,j,not state)
        if desired!=state:state=desired
        # Align to target allocation *only on regime changes* (or first open).
        if pos==0 or desired!=bool(prev_target):
            want=1. if state else c.get("riskOffWeight",0.0)
            gross=cash+shares*px*sell_factor
            target=int(max(0,gross*want)//(px*buy_factor))
            if shares>target:
                n=shares-target
                proceeds=n*px*sell_factor;cash+=proceeds;shares-=n
                events.append({"date":str(date),"side":"SELL","shares":n,"grossPrice":round(px*(1-SLIP),4),
                               "netCash":round(proceeds,2),"accountCash":round(cash,2),"phase":"risk_off"})
            elif shares<target:
                count=min(target-shares,int(cash//(px*buy_factor)))
                if count>0:
                    paid=count*px*buy_factor;cash-=paid;shares+=count
                    events.append({"date":str(date),"side":"BUY","shares":count,"grossPrice":round(px*(1+SLIP),4),
                                   "netCash":round(-paid,2),"accountCash":round(cash,2),"phase":"risk_on"})
        prev_target=state
        if shares>0:traded_days+=1
        if not state:regime_days+=1
        account=cash+shares*mark*sell_factor
        equity.append({"date":str(date),"equity":round(account,2),"heldShares":int(shares),"riskOn":bool(state)})
    if shares>0:
        px=float(closes[idx[-1]])
        proceeds=shares*px*sell_factor
        cash+=proceeds
        events.append({"date":str(dates[idx[-1]]),"side":"SELL","shares":shares,
                       "grossPrice":round(px*(1-SLIP),4),"netCash":round(proceeds,2),
                       "accountCash":round(cash,2),"phase":"period_end"})
        shares=0
        equity[-1]["equity"]=round(cash,2);equity[-1]["heldShares"]=0
    vals=np.array([x["equity"] for x in equity])
    m=np.maximum.accumulate(np.r_[CAPITAL,vals])[1:]
    dd=float(min((vals/m-1)*100))
    sells=sum(e["side"]=="SELL" and e["phase"]=="risk_off" for e in events)
    rebuys=sum(e["side"]=="BUY" and e["phase"]=="risk_on" for e in events)-1
    result={"start":str(dates[idx[0]]),"end":str(dates[idx[-1]]),
            "returnPct":round((cash/CAPITAL-1)*100,3),"endNTD":round(cash,2),
            "mddPct":round(dd,3),"riskOffSessions":int(regime_days),
            "investedSessions":int(traded_days),"sessions":len(idx),
            "riskOffSells":int(sells),"riskOnReentries":int(max(rebuys,0)),
            "switchEvents":int(len(events)-2 if events[-1]["phase"]=="period_end" else len(events)-1)}
    if detailed:result.update({"equity":equity,"orders":events})
    return result
def compact(z):return {k:v for k,v in z.items() if k not in ("equity","orders")}
def cap_ratio(ret,bh):return round(ret/max(1e-10,bh)*100,2)
def main():
    now=time.monotonic()
    _,etf,e=update_symbol(SYMBOL,datetime(2023,1,1),datetime(2026,10,9))
    _,index,e2=update_symbol(INDEX,datetime(2023,1,1),datetime(2026,10,9))
    if e or e2 or etf is None or index is None or etf.empty or index.empty:raise RuntimeError(str({"etf":e,"idx":e2}))
    d=prepare(data_prepare(etf,index));a,dates=indicators(d)
    allcases=universe()
    bh={year:bt(a,dates,allcases[0],*period) for year,period in PERIODS.items()}
    assert bh["train"]["returnPct"]==133.131,(bh["train"],"frozen pre-2026 parity")
    assert bh["continuous"]["sessions"]>=669 and bh["2026"]["sessions"]>=184,(bh["continuous"],bh["2026"])
    print("ETF_NEAR_HOLD_START "+json.dumps({"variants":len(allcases),"lastBar":str(d.iloc[-1].date),"buyhold":{k:v["returnPct"] for k,v in bh.items()}}),flush=True)
    eligible=[]
    family_summary={}
    for k,c in enumerate(allcases[1:],1):
        y24=bt(a,dates,c,*PERIODS["2024"])
        y25=bt(a,dates,c,*PERIODS["2025"])
        both=bt(a,dates,c,*PERIODS["train"])
        fs=family_summary.setdefault(c["family"],{"tested":0,"eligible":0})
        fs["tested"]+=1
        good=(both["riskOffSells"]>=2 and both["riskOnReentries"]>=1
              and y24["riskOffSells"]>=1 and y25["riskOffSells"]>=1
              and both["riskOffSessions"]>=8
              and y24["returnPct"]>0 and y25["returnPct"]>0)
        if good:
            fs["eligible"]+=1
            # Capture of high long-run upside dominates but a modest MDD cost matters.
            # Use *only* 2024-2025. No 2026 outcomes for selection.
            ret_score=round(both["returnPct"]-.35*abs(both["mddPct"])-.2*max(0,-min(y24["returnPct"],y25["returnPct"])),4)
            defense_score=round(both["returnPct"]-.9*abs(both["mddPct"])+.15*min(y24["returnPct"],y25["returnPct"]),4)
            eligible.append({"id":c["id"],"family":c["family"],"params":c,"2024":compact(y24),
                     "2025":compact(y25),"train":compact(both),
                     "upsideScore":ret_score,"defenseScore":defense_score})
        if k%500==0:print("ETF_NEAR_HOLD_PROGRESS",k,"/",len(allcases)-1,flush=True)
    if not eligible:raise RuntimeError("No eligible roundtrip models")
    by_id={x["id"]:x for x in eligible}
    # Select unique performance variants by training scores, plus one for each family.
    up=sorted(eligible,key=lambda x:(-x["upsideScore"],x["id"]))
    defensive=sorted(eligible,key=lambda x:(-x["defenseScore"],x["id"]))
    chosen_ids=[]
    for pool in (up[:6],defensive[:6]):
        for r in pool:
            if r["id"] not in chosen_ids:chosen_ids.append(r["id"])
    for fam in family_summary:
        for pool in (up,defensive):
            k=next((x["id"] for x in pool if x["family"]==fam),None)
            if k and k not in chosen_ids:chosen_ids.append(k)
    checks=[]
    for k in chosen_ids:
        c=by_id[k]["params"]
        oos=bt(a,dates,c,*PERIODS["2026"],detailed=True)
        full=bt(a,dates,c,*PERIODS["continuous"],detailed=True)
        checks.append({**by_id[k],"2026":compact(oos),"continuous":compact(full),
            "heldOutCaptureVsHoldPct":cap_ratio(oos["returnPct"],bh["2026"]["returnPct"]),
            "continuousCaptureVsHoldPct":cap_ratio(full["returnPct"],bh["continuous"]["returnPct"]),
            "orders":full["orders"],"equity":full["equity"]})
        print("ETF_NEAR_HOLD_FROZEN "+json.dumps({"id":k,"train":by_id[k]["train"]["returnPct"],
              "2026":oos["returnPct"],"full":full["returnPct"],"dd":full["mddPct"],
              "actualExitBuyback":full["riskOffSells"],"pctBuyhold":round(100*(full["endNTD"]-CAPITAL)/(bh["continuous"]["endNTD"]-CAPITAL),2)}),flush=True)
    output={"version":"00675L_LONG_HOLD_SWITCH_GRID_2026_V1",
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "ticker":SYMBOL,"dateEnd":str(d.iloc[-1].date),
        "originalCapitalNTD":CAPITAL,
        "baseline":{k:compact(v) for k,v in bh.items()},
        "universe":{"total":len(allcases),"eligible":len(eligible),"family":family_summary},
        "selection":{"train":"2024+2025 only","holdout":"2026 frozen, no picking winner on 2026",
            "criteria":"at least 2 sell events plus 1 rebuy 2024-25, ≥1 sell in EACH of 2024 and 2025, ≥8 reduced exposure sessions, positive 2024 and 2025 accounts",
            "upsideScore":"train net return% − 0.35*absolute(train maximum drawdown%)",
            "defenseScore":"train net return% − 0.90*abs(train maximum drawdown%) + 0.15*min(2024%,2025%)",
            "chosen":"unique 6 best each by 2024-25 upside and defensive criteria plus best per strategy family",
            "2026":str(PERIODS["2026"])},
        "assumptions":{"capital":"one NT$1m cash account; reinvest 100% realized cash profits; integer ETF units",
            "signals":"completed daily closes only, orders at NEXT trading-day open; first session buys ETF at open",
            "fees":{"brokerEachSidePct":BROKER*100,"etfTaxSellPct":ETF_SELL_TAX*100,"slippageEachSidePct":SLIP*100},
            "riskOffAllocation":"sell all or half stock shares depending rule; reenter full weight when recovery; no arbitrary take profit cap",
            "mark":"daily account liquidation value net of simulated selling fee and slippage",
            "dateIsolation":"all 2024/25 score calculations completed before reading any 2026 candidate outcomes"},
        "topTrainUpside":up[:20],"topTrainDefensive":defensive[:20],
        "frozenComparisons":[{k:v for k,v in z.items() if k not in ("orders","equity")} for z in checks],
        "warnings":["The researcher has already inspected 2026 for this ETF in earlier backtests, so 2026 is NOT pristine researcher-level holdout.",
           "Parameter search over many related rules can overfit 2024-25 despite frozen 2026 evaluation.",
           "A model with zero exits is not counted as an actual roundtrip winner.",
           "Year-by-year and continuous backtests start separately in their own period; only continuous account never resets 100萬.",
           "Strong underlying 2x ETF uptrend makes buy and hold hard to beat; market timing may lose despite lower drawdown.",
           "Prices from Yahoo adjusted daily OHLC are not 2-minute intraday Bottom/Top fills; no lending or margin modeled."],
        "elapsedSeconds":round(time.monotonic()-now,1)}
    OUTPUT.mkdir(parents=True,exist_ok=True)
    (OUTPUT/"summary.json").write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUTPUT/"frozen_orders_equity.json").write_text(json.dumps({"version":output["version"],
       "models":[{"id":r["id"],"equity":r["equity"],"orders":r["orders"]} for r in checks]},ensure_ascii=False),encoding="utf-8")
    (OUTPUT/"training_all.json").write_text(json.dumps({"version":output["version"],"models":eligible},ensure_ascii=False),encoding="utf-8")
    print("ETF_NEAR_HOLD_DONE "+json.dumps({"count":len(allcases),"eligible":len(eligible),"frozen":len(checks),
       "bestTrainingId":up[0]["id"],"buyHoldContinuous":bh["continuous"]["returnPct"],
       "elapsed":output["elapsedSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
