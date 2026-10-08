"""Research-only H: high estimated share turnover + confirmed momentum.
All indicators use the completed signal day; orders are next-session open.
The share-turnover denominator uses today's paid-in capital / NT$10 par
as a PROXY, not historical outstanding shares or free-float turnover.
"""
from __future__ import annotations
import numpy as np,pandas as pd
TURNOVER_MIN=5.0
RVOL10_MIN=1.4
RS20_MIN=4.0
RET5_MIN=3.0
RET20_MIN=5.0
MIN_DOLLAR_VALUE_B=1.5
def turnover_proxy_pct(volume,capital_b):
    try:
        v,c=float(volume),float(capital_b)
        if not np.isfinite(v) or not np.isfinite(c) or v<=0 or c<=0:return None
        return 100*v/(c*10_000_000)
    except (TypeError,ValueError):return None
def score_h(m,rs20,capital_b,turnover_b):
    t=turnover_proxy_pct(m.get("volume"),capital_b)
    if t is None:return None
    values=[m.get(k) for k in ("rvol10","ret5","ret20","ema20Slope5","close","ema20","closePosition","breakoutPct","atrPct","mom10Pct","dayRet")]
    if any(v is None or not np.isfinite(float(v)) for v in values):return None
    rvol,ret5,ret20,slope,close,ema20,closepos,br,atr,mom10,dayret=map(float,values)
    if not (close>=10 and turnover_b>=MIN_DOLLAR_VALUE_B and t>=TURNOVER_MIN and rvol>=RVOL10_MIN and rs20>=RS20_MIN and ret5>=RET5_MIN and ret20>=RET20_MIN and slope>0 and close>ema20 and closepos>=60 and br>=-4 and atr>=2.5 and mom10>0 and dayret<9.5):return None
    cap=lambda x:max(0.0,min(1.0,x))
    score=24*cap(t/12)+16*cap(rvol/4)+20*cap(rs20/25)+15*cap(ret5/18)+15*cap((br+4)/10)+10*cap(atr/9)
    return {"score":round(score,3),"turnoverProxyPct":round(t,3),"rvol10":round(rvol,3),"rs20":round(rs20,3),"ret5":round(ret5,3),"ret20":round(ret20,3),"breakoutPct":round(br,3)}
def adjusted_price(row,field):
    x=row.get(field);c=row.get("close");a=row.get("adjclose")
    if x is None or pd.isna(x):return None
    return float(x)*(float(a)/float(c)) if a is not None and pd.notna(a) and c is not None and pd.notna(c) and float(c)>0 else float(x)
def exit_trade(px,buydate,exitdate,take_pct=7.0,stop_pct=4.0,slippage_pct=.1):
    """OHLC bracket: bad gap at open is filled at open; both hit => stop first."""
    if px is None or buydate not in px.index or exitdate not in px.index:return None
    q=px.loc[buydate:exitdate]
    if len(q)<1:return None
    scale=pd.to_numeric(q.close,errors="coerce")
    jump=scale/scale.shift(1)
    if ((jump<.55)|(jump>1.8)).fillna(False).any():return None
    entry=adjusted_price(q.iloc[0],"open")
    if entry is None or entry<=0:return None
    paid=entry*(1+slippage_pct/100)
    target=paid*(1+take_pct/100);stop=paid*(1-stop_pct/100)
    reason="timeout";out=None;actual_day=None
    for _,bar in q.iterrows():
        op=adjusted_price(bar,"open");hi=adjusted_price(bar,"high");lo=adjusted_price(bar,"low");cl=adjusted_price(bar,"close")
        if any(x is None or x<=0 for x in (op,hi,lo,cl)):return None
        if op<=stop:out=op;reason="stop_gap"
        elif op>=target:out=op;reason="tp_gap"
        elif lo<=stop:out=stop;reason="stop"
        elif hi>=target:out=target;reason="tp"
        elif str(bar["date"])==exitdate:out=cl;reason="timeout"
        if out is not None:
            actual_day=str(bar["date"]);break
    if out is None:return None
    sell_fee=.1425/100;sell_tax=.3/100;buy_fee=.1425/100
    net=(out*(1-slippage_pct/100)*(1-sell_fee-sell_tax)/(paid*(1+buy_fee))-1)*100
    gross=(out/paid-1)*100
    return {"exitDate":actual_day,"reason":reason,"grossPct":round(gross,3),"netPct":round(net,3)}
