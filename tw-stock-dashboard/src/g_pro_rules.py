"""Single frozen G Pro rule set shared by daily website and 3-year backtest."""
from __future__ import annotations
import math
import pandas as pd
import numpy as np
def finite(x):
    try:
        z=float(x)
        return z if math.isfinite(z) else None
    except (TypeError,ValueError):return None
G_PRO_RULES={"ret20PercentileMin":75,"ma20SlopePercentileMin":80,"turnoverPercentileMin":75,"prior10DaysOriginalGTop20Min":2,"relativeVolumeVsPrevious20Min":1.3,"closeAboveEma20":True,"ema20AboveEma60":True,"maxCloseToEma20":1.15}
def build_daily_indicators(hist,symbols):
    indicators={}
    for sy in symbols:
        h=hist.get(sy)
        if h is None or h.empty:continue
        q=h.sort_values("date").drop_duplicates("date").copy()
        c=pd.to_numeric(q["close"],errors="coerce")
        v=pd.to_numeric(q["volume"],errors="coerce")
        e20=c.ewm(span=20,adjust=False,min_periods=60).mean()
        e60=c.ewm(span=60,adjust=False,min_periods=60).mean()
        volbase=v.shift(1).rolling(20,min_periods=20).mean()
        rv=v/volbase.replace(0,np.nan)
        indicators[sy]={str(d):{"ema20":finite(a),"ema60":finite(b),"rvol":finite(z)}
            for d,a,b,z in zip(q["date"].astype(str),e20,e60,rv)}
    return indicators
def pro_pass(stock,record):
    if record is None:return False,"missing_indicators"
    c=finite(stock.get("close"));m20=record.get("ema20");m60=record.get("ema60")
    if c is None or m20 is None or m60 is None or m20<=0 or m60<=0:return False,"missing_indicators"
    if finite(stock.get("ret20P")) is None or stock["ret20P"]<G_PRO_RULES["ret20PercentileMin"]:return False,"ret20"
    if finite(stock.get("slopeP")) is None or stock["slopeP"]<G_PRO_RULES["ma20SlopePercentileMin"]:return False,"ma20slope"
    if finite(stock.get("turnoverP")) is None or stock["turnoverP"]<G_PRO_RULES["turnoverPercentileMin"]:return False,"turnover"
    if int(stock.get("previousTop20",stock.get("gPast10",0)) or 0)<G_PRO_RULES["prior10DaysOriginalGTop20Min"]:return False,"persistence"
    if (record.get("rvol") or 0)<G_PRO_RULES["relativeVolumeVsPrevious20Min"]:return False,"rvol"
    if not(c>m20>m60):return False,"ema_trend"
    if c/m20>G_PRO_RULES["maxCloseToEma20"]:return False,"overextended"
    return True,"passed"
