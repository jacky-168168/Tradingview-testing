from __future__ import annotations
from typing import Dict,Any
import numpy as np,pandas as pd

def ema(v,period):
    a=pd.to_numeric(v,errors="coerce").dropna().astype(float).to_numpy()
    if len(a)==0:return 0.0
    n=min(int(period),len(a));e=float(a[:n].mean());k=2/(period+1)
    for x in a[n:]:e=float(x)*k+e*(1-k)
    return e

def rolling_gas_ema(v,period,window):
    """Exact GAS emaValue_ over a moving max-length window."""
    a=pd.to_numeric(v,errors="coerce").astype(float).reset_index(drop=True)
    n=len(a);out=np.full(n,np.nan,dtype=float)
    if n==0:return pd.Series(out,index=a.index)
    p=int(period);w=int(window);k=2/(p+1);q=1-k
    if n>=p:
        e=float(a.iloc[:p].mean());out[p-1]=e
        for i in range(p,min(n,w)):
            e=float(a.iloc[i])*k+e*q;out[i]=e
    if n>=w and w>=p:
        weights=np.empty(w,dtype=float);weights[:p]=(q**(w-p))/p
        for j in range(p,w):weights[j]=k*(q**(w-1-j))
        out[w-1:]=np.correlate(a.to_numpy(),weights,mode="valid")
    return pd.Series(out,index=a.index)

def calc_metrics(df):
    if df is None or len(df)<25:return None
    d=df.dropna(subset=["close","high","low","volume"]).copy()
    if len(d)<25:return None
    c=d.close.astype(float);v=d.volume.astype(float);last=float(c.iloc[-1]);pc=c.shift(1)
    tr=pd.concat([d.high-d.low,(d.high-pc).abs(),(d.low-pc).abs()],axis=1).max(axis=1)
    e20=ema(c,20);e50=ema(c,50);e20p=ema(c.iloc[:-5],20) if len(c)>=25 else e20
    ph=float(d.high.iloc[-21:-1].max());rng=float(d.high.iloc[-1]-d.low.iloc[-1])
    return {"close":last,"dayRet":(last/c.iloc[-2]-1)*100 if len(c)>=2 else 0.0,"ret5":(last/c.iloc[-6]-1)*100,"ret20":(last/c.iloc[-21]-1)*100,
      "ma20":float(c.iloc[-20:].mean()),"ma60":float(c.iloc[-min(60,len(c)):].mean()),"ma20Slope":(float(c.iloc[-20:].mean())/float(c.iloc[-25:-5].mean())-1)*100,
      "rvol":float(v.iloc[-1])/float(v.iloc[-21:-1].mean()) if float(v.iloc[-21:-1].mean()) else 0.0,
      "rvol10":float(v.iloc[-1])/float(v.iloc[-11:-1].mean()) if float(v.iloc[-11:-1].mean()) else 0.0,
      "mom10Pct":(last/c.iloc[-11]-1)*100 if c.iloc[-11] else 0.0,
      "ema20":e20,"ema50":e50,"ema20Slope5":(e20/e20p-1)*100 if e20p else 0.0,"prevHigh20":ph,"breakoutPct":(last/ph-1)*100 if ph else 0.0,
      "atrPct":float(tr.iloc[-14:].mean())/last*100 if last else 0.0,"volD":float(tr.iloc[-1])/abs(float(d.low.iloc[-1]))*100 if float(d.low.iloc[-1]) else 0.0,
      "closePosition":(last-float(d.low.iloc[-1]))/rng*100 if rng>0 else 50.0,"volume":float(v.iloc[-1])}

def precompute_features(df,ema_window=120):
    """Vectorized backtest features matching GAS h=bars[-120:] semantics."""
    if df is None or df.empty:return pd.DataFrame()
    x=df.copy().sort_values("date").reset_index(drop=True)
    for k in ["open","high","low","close","volume"]:x[k]=pd.to_numeric(x[k],errors="coerce")
    c=x.close;v=x.volume;pc=c.shift(1);tr=pd.concat([x.high-x.low,(x.high-pc).abs(),(x.low-pc).abs()],axis=1).max(axis=1)
    x["dayRet"]=c.pct_change()*100;x["ret5"]=c.pct_change(5)*100;x["ret20"]=c.pct_change(20)*100
    x["ma20"]=c.rolling(20).mean();x["ma60"]=c.rolling(60,min_periods=1).mean();x["ma20Slope"]=(x.ma20/x.ma20.shift(5)-1)*100
    x["rvol"]=v/v.shift(1).rolling(20).mean();x["rvol10"]=v/v.shift(1).rolling(10).mean();x["mom10Pct"]=c.pct_change(10)*100
    x["ema20"]=rolling_gas_ema(c,20,ema_window);x["ema50"]=rolling_gas_ema(c,50,ema_window)
    prev_window=max(20,ema_window-5);x["ema20Slope5"]=(x.ema20/rolling_gas_ema(c,20,prev_window).shift(5)-1)*100
    x["range20Pct"]=(x.high.rolling(20).max()-x.low.rolling(20).min())/x.low.rolling(20).min().replace(0,np.nan)*100
    x["prevHigh20"]=x.high.shift(1).rolling(20).max();x["breakoutPct"]=(c/x.prevHigh20-1)*100
    x["atrPct"]=tr.rolling(14).mean()/c*100;x["volD"]=tr/x.low.abs()*100
    rng=x.high-x.low;x["closePosition"]=np.where(rng>0,(c-x.low)/rng*100,50.0)
    return x

def institution_score(inst):
    inst=inst or {};f=float(inst.get("foreign",0) or 0);t=float(inst.get("trust",0) or 0);d=float(inst.get("dealer",0) or 0);tot=f+t+d
    return min(10,(4 if t>0 else 0)+(2 if f>0 else 0)+(1 if d>0 else 0)+(3 if tot>0 else 0))

def score_a(m,rs20,inst=None):
    mom=(3 if m["ret5"]>1 else 0)+(4 if m["ret5"]>3 else 0)+(4 if m["ret5"]>6 else 0)+(3 if m["ret20"]>5 else 0)+(3 if m["ret20"]>10 else 0)+(3 if m["ret20"]>15 else 0);mom=min(20,mom)
    r=m["rvol"];vol=15 if r>=2 else 12 if r>=1.5 else 8 if r>=1.2 else 4 if r>=1 else 0
    tr=min(15,(5 if m["close"]>m["ma20"] else 0)+(4 if m["ma20"]>m["ma60"] else 0)+(4 if m["ma20Slope"]>0 else 0)+(2 if m["close"]>m["ma60"] else 0))
    b=m["breakoutPct"];br=15 if b>=3 else 14 if b>=0 else 12 if b>=-1 else 9 if b>=-3 else 5 if b>=-6 else 2 if b>=-10 else 0
    rs=15 if rs20>15 else 13 if rs20>10 else 10 if rs20>6 else 6 if rs20>3 else 3 if rs20>0 else 0
    a=m["atrPct"];vs=10 if 2.5<=a<=5.5 else 7 if 1.8<=a<7 else 4 if a>=1.2 else 0;ins=institution_score(inst)
    return {"total":mom+vol+tr+br+rs+ins+vs,"momentum":mom,"volumeScore":vol,"trendScore":tr,"breakoutScore":br,"rsScore":rs,"institutionScore":ins,"volatilityScore":vs}

def d_pass(m):return m["volume"]>20_000_000 and m["rvol10"]>1.2 and m["mom10Pct"]>0 and m["volD"]>10

def score_d(m,rs20,inst=None):
    r=m["rvol10"];rv=15 if r>=5 else 20 if r>=3 else 18 if r>=2 else 12 if r>=1.5 else 8 if r>=1.2 else 0
    x=m["mom10Pct"];mo=10 if x>25 else 16 if x>15 else 20 if x>8 else 12 if x>3 else 6 if x>0 else 0
    tr=(8 if m["close"]>m["ema20"] else 0)+(8 if m["ema20"]>m["ema50"] else 0)+(4 if m["ema20Slope5"]>0 else 0)
    rs=15 if rs20>15 else 13 if rs20>10 else 10 if rs20>6 else 6 if rs20>3 else 3 if rs20>0 else 0
    b=m["breakoutPct"];br=15 if -3<=b<=5 else 8 if -6<b<-3 else 10 if 5<b<=10 else 5 if 10<b<=20 else 2 if b>20 else 0;ins=institution_score(inst)
    return {"total":max(0,min(100,rv+mo+tr+rs+br+ins)),"rvolScore":rv,"momScore":mo,"trendScore":tr,"rsScore":rs,"breakoutScore":br,"institutionScore":ins}

def sort_key(r):return (-r["total"],-r["rs20"],-r["rvol"],-r["ret20"],-r["turnoverB"],str(r["code"]))
