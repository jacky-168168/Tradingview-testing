"""H5 fixed stock screener / five-tranche price-averaging research execution.
No live trading; do not confuse a 15% per-position stop with 15% max portfolio risk.
Signals use completed-day close; initial buy limit can fill NEXT day only.
Add orders remain valid until basket exit or maximum holding date.
Limit ladders: actual FIRST fill × (1 - .02*n), n=1,2,3,4.
Tranches have equal notional capital, not equal share counts.
Daily OHLC ambiguity: if ANY limit filled intraday, the same day's high is
not allowed to trigger TP, while lows can trigger stop (adverse priority).
"""
from __future__ import annotations
import math
import pandas as pd
TAKE_PCT=7.0
STOP_PCT=15.0
STEP_PCT=2.0
MAX_TRANCHE=5
BUY_FEE=.001425
SELL_FEE=.001425
SELL_TAX=.003
SLIPPAGE=.001
def levels(signal_close,first_fill,initial_discount=2.5,step_pct=STEP_PCT):
    if not(0<first_fill<=signal_close*1.10):raise ValueError("Bad first fill")
    return [round(first_fill*(1-step_pct*i/100),6) for i in range(MAX_TRANCHE)]
def simulate(bars,signal_close,discount_pct=2.5,hold_days=5):
    """Returns event attributes. Single event outcome, max 5 equal-cash tranches.
    bars must be NEXT TRADING DAY through at most hold_days future trading days.
    Target / stop re-estimated from current *quantity-weighted* average after each fill.
    """
    if not (2<=discount_pct<=3):raise ValueError("First limit discount must be 2-3%")
    if hold_days<1:raise ValueError("Holding period must be positive")
    if bars is None or len(bars)<hold_days:return {"status":"missing"}
    sub=bars.iloc[:hold_days].copy()
    for k in ("open","high","low","close"):
        sub[k]=pd.to_numeric(sub[k],errors="coerce")
    if sub[["open","high","low","close"]].isna().any().any():return {"status":"missing"}
    # Reject obvious split-scale jumps. Smaller dividends / share adjustments still pose bias.
    z=sub["close"].to_numpy(dtype=float);changes=z[1:]/z[:-1]
    if any(not math.isfinite(x) or x<0.55 or x>1.80 for x in changes):return {"status":"missing"}
    first_limit=float(signal_close)*(1-discount_pct/100)
    if not math.isfinite(first_limit) or first_limit<=0:return {"status":"missing"}
    tranches=[];first_price=None;ladder=[];first_day=None
    def add(px,day):
        if not math.isfinite(px) or px<=0:raise ValueError("Bad fill price")
        paid=float(px)*(1+SLIPPAGE)
        tranches.append({"date":day,"fill":round(float(px),6),"paid":paid,"shares":1.0/paid,"notional":1.0})
    def avg():
        return len(tranches)/sum(x["shares"] for x in tranches)
    def settle(price,reason,day):
        if not tranches:return {"status":"unfilled","initialLimit":round(first_limit,4)}
        cash=len(tranches)*(1+BUY_FEE)
        gross_shares=sum(x["shares"] for x in tranches)
        proceeds=price*(1-SLIPPAGE)*(1-SELL_FEE-SELL_TAX)*gross_shares
        pnl=proceeds-cash
        a=avg()
        return {"status":"filled","discountPct":discount_pct,"holdDays":hold_days,
            "initialLimit":round(first_limit,4),"firstFill":round(first_price,4),"firstFillDate":first_day,
            "trancheCount":len(tranches),"filledPrices":[x["fill"] for x in tranches],
            "averageCost":round(a,4),"targetPrice":round(a*(1+TAKE_PCT/100),4),
            "stopPrice":round(a*(1-STOP_PCT/100),4),"exitPrice":round(price,4),
            "exitDate":day,"exitReason":reason,"targetHit":reason.startswith("tp"),
            "stopHit":reason.startswith("stop"),"grossReturnPct":round((price/a-1)*100,3),
            "netReturnOnDeployedPct":round((proceeds/cash-1)*100,3),
            "netReturnOnFiveTrancheBudgetPct":round(pnl/(MAX_TRANCHE*(1+BUY_FEE))*100,3),
            "firstEntryToExitPct":round((price/first_price-1)*100,3)}
    for d,(_,bar) in enumerate(sub.iterrows()):
        date=str(bar["date"]) if "date" in sub.columns else str(sub.index[d])
        o,h,l,c=(float(bar[k]) for k in ("open","high","low","close"))
        if min(o,h,l,c)<=0 or not all(math.isfinite(z) for z in (o,h,l,c)):return {"status":"missing"}
        if tranches:
            # Existing stop/TP orders execute at opening gap BEFORE any new averaging.
            a=avg()
            if o<=a*(1-STOP_PCT/100):return settle(o,"stop_gap",date)
            if o>=a*(1+TAKE_PCT/100):return settle(o,"tp_gap",date)
        filled_intraday=False
        if d==0:
            if o<=first_limit:
                first_price=o;first_day=date;add(o,date)
            elif l<=first_limit:
                first_price=first_limit;first_day=date;add(first_limit,date);filled_intraday=True
            else:return {"status":"unfilled","initialLimit":round(first_limit,4),"discountPct":discount_pct}
            ladder=levels(signal_close,first_price,discount_pct)
        if tranches and len(tranches)<MAX_TRANCHE:
            # Later levels pre-defined using actual first fill, never dynamically
            # moved to today's high/low. Opening gap executes at opening price.
            while len(tranches)<MAX_TRANCHE:
                target=ladder[len(tranches)]
                if o<=target and not (d==0 and filled_intraday):
                    add(o,date);continue
                if l<=target:
                    add(target,date);filled_intraday=True;continue
                break
        if tranches:
            a=avg();sl=a*(1-STOP_PCT/100);tp=a*(1+TAKE_PCT/100)
            if l<=sl:return settle(sl,"stop",date)
            if not filled_intraday and h>=tp:return settle(tp,"tp",date)
            if d==hold_days-1:return settle(c,"timeout",date)
    return {"status":"missing"}
