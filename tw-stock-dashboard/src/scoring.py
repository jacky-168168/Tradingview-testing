from __future__ import annotations
from typing import Dict, Any
import numpy as np
import pandas as pd

def ema(values: pd.Series, span: int) -> float:
    return float(values.ewm(span=span, adjust=False).mean().iloc[-1])

def calc_metrics(df: pd.DataFrame) -> Dict[str, float] | None:
    if df is None or len(df) < 55: return None
    d=df.dropna(subset=["close","high","low","volume"]).copy()
    if len(d)<55: return None
    c=d["close"].astype(float); v=d["volume"].astype(float); last=float(c.iloc[-1])
    ret5=(last/float(c.iloc[-6])-1)*100; ret20=(last/float(c.iloc[-21])-1)*100
    ma20=float(c.iloc[-20:].mean()); ma60=float(c.iloc[-min(60,len(c)):].mean())
    prev20=float(c.iloc[-25:-5].mean()); ma20_slope=(ma20/prev20-1)*100 if prev20 else 0.0
    av20=float(v.iloc[-21:-1].mean()); rvol=float(v.iloc[-1])/av20 if av20 else 0.0
    av10=float(v.iloc[-11:-1].mean()); rvol10=float(v.iloc[-1])/av10 if av10 else 0.0
    mom10_pct=(last/float(c.iloc[-11])-1)*100 if float(c.iloc[-11]) else 0.0
    ema20=ema(c,20); ema50=ema(c,50); ema20_prev5=ema(c.iloc[:-5],20) if len(c)>=25 else ema20
    ema20_slope5=(ema20/ema20_prev5-1)*100 if ema20_prev5 else 0.0
    prev_high20=float(d["high"].iloc[-21:-1].max()); breakout_pct=(last/prev_high20-1)*100 if prev_high20 else 0.0
    prev_close=c.shift(1)
    tr=pd.concat([d["high"]-d["low"],(d["high"]-prev_close).abs(),(d["low"]-prev_close).abs()],axis=1).max(axis=1)
    atr14=float(tr.iloc[-14:].mean()); atr_pct=atr14/last*100 if last else 0.0
    lb=d.iloc[-1]; pc=float(c.iloc[-2]); tr_d=max(float(lb.high-lb.low),abs(float(lb.high)-pc),abs(float(lb.low)-pc))
    vol_d=tr_d/abs(float(lb.low))*100 if float(lb.low) else 0.0
    br=float(lb.high-lb.low); close_position=(last-float(lb.low))/br*100 if br>0 else 50.0
    day_ret=(last/float(c.iloc[-2])-1)*100
    return {"close":last,"dayRet":day_ret,"ret5":ret5,"ret20":ret20,"ma20":ma20,"ma60":ma60,"ma20Slope":ma20_slope,
            "rvol":rvol,"rvol10":rvol10,"mom10Pct":mom10_pct,"ema20":ema20,"ema50":ema50,"ema20Slope5":ema20_slope5,
            "prevHigh20":prev_high20,"breakoutPct":breakout_pct,"atrPct":atr_pct,"volD":vol_d,"closePosition":close_position,
            "volume":float(v.iloc[-1])}

def institution_score(inst: Dict[str,float] | None) -> int:
    inst=inst or {}; f=float(inst.get("foreign",0) or 0); t=float(inst.get("trust",0) or 0); d=float(inst.get("dealer",0) or 0); total=f+t+d
    s=(3 if total>0 else 0)+(3 if f>0 else 0)+(3 if t>0 else 0)+(1 if f>0 and t>0 else 0)
    return min(10,s)

def score_a(m: Dict[str,float], rs20: float, inst=None) -> Dict[str,float]:
    momentum=0
    if m["ret5"]>1: momentum+=3
    if m["ret5"]>3: momentum+=4
    if m["ret5"]>6: momentum+=4
    if m["ret20"]>5: momentum+=3
    if m["ret20"]>10: momentum+=3
    if m["ret20"]>15: momentum+=3
    momentum=min(20,momentum)
    r=m["rvol"]; volume=15 if r>=2 else 12 if r>=1.5 else 8 if r>=1.2 else 4 if r>=1 else 0
    trend=min(15,(5 if m["close"]>m["ma20"] else 0)+(4 if m["ma20"]>m["ma60"] else 0)+(4 if m["ma20Slope"]>0 else 0)+(2 if m["close"]>m["ma60"] else 0))
    b=m["breakoutPct"]; breakout=15 if b>=3 else 14 if b>=0 else 12 if b>=-1 else 9 if b>=-3 else 5 if b>=-6 else 2 if b>=-10 else 0
    rs=15 if rs20>15 else 13 if rs20>10 else 10 if rs20>6 else 6 if rs20>3 else 3 if rs20>0 else 0
    atr=m["atrPct"]; vol=10 if 2.5<=atr<=5.5 else 7 if 1.8<=atr<7 else 4 if atr>=1.2 else 0
    ins=institution_score(inst); total=momentum+volume+trend+breakout+rs+ins+vol
    return {"total":total,"momentum":momentum,"volumeScore":volume,"trendScore":trend,"breakoutScore":breakout,"rsScore":rs,"institutionScore":ins,"volatilityScore":vol}

def d_pass(m: Dict[str,float]) -> bool:
    return m["volume"]>20_000_000 and m["rvol10"]>1.2 and m["mom10Pct"]>0 and m["volD"]>10

def score_d(m: Dict[str,float], rs20: float, inst=None) -> Dict[str,float]:
    r=m["rvol10"]; rvol=15 if r>=5 else 20 if r>=3 else 18 if r>=2 else 12 if r>=1.5 else 8 if r>=1.2 else 0
    x=m["mom10Pct"]; mom=10 if x>25 else 16 if x>15 else 20 if x>8 else 12 if x>3 else 6 if x>0 else 0
    trend=(8 if m["close"]>m["ema20"] else 0)+(8 if m["ema20"]>m["ema50"] else 0)+(4 if m["ema20Slope5"]>0 else 0)
    rs=15 if rs20>15 else 13 if rs20>10 else 10 if rs20>6 else 6 if rs20>3 else 3 if rs20>0 else 0
    b=m["breakoutPct"]; breakout=15 if -3<=b<=5 else 8 if -6<b<-3 else 10 if 5<b<=10 else 5 if 10<b<=20 else 2 if b>20 else 0
    ins=institution_score(inst); total=max(0,min(100,rvol+mom+trend+rs+breakout+ins))
    return {"total":total,"rvolScore":rvol,"momScore":mom,"trendScore":trend,"rsScore":rs,"breakoutScore":breakout,"institutionScore":ins}

def sort_key(row: Dict[str,Any]):
    return (-row["total"],-row["rs20"],-row["rvol"],-row["ret20"],-row["turnoverB"],str(row["code"]))
