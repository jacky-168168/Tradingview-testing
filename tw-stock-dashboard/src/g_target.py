"""G_TARGET: chronological label fit against same-date peers, no code whitelist."""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize
from scipy.special import logsumexp
FEATURES=("ret20P","slopeP","atrP","range20P","turnoverP","ret5P","mom10P","range10P","rvol10P","positionP","dayP","emaSlopeP","v520P","breakout","smallCap")
PRIOR=np.array([2.0,1.7,0.9,1.2,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.20,0.30])
def eligible(r):
    return bool(r["close"]>=10 and r["capitalB"]>0 and r["ret20P"]>=60 and r["slopeP"]>=70 and r["atrP"]>=55 and r["range20P"]>=65 and r["turnoverP"]>=65 and r["breakoutPct"]>=-25)
def features(r):
    q=np.array([float(r[x]) for x in FEATURES[:13]],dtype=float)
    pct=np.clip(q/50-1,-1,1)
    breakout=np.clip(float(r["breakoutPct"])/20,-1,1)
    cap=np.clip((1.5-np.log10(max(.1,float(r["capitalB"]))))/2,-1,1)
    return np.concatenate((pct,np.array([breakout,cap])))
def fit(groups,lambda_reg=.11):
    """One positive or more per date; constrained softmax with prior shrinkage."""
    if not groups:return PRIOR.copy(),{"trainPosts":0,"groups":0,"optimized":False}
    mats=[]
    for rows,positive_codes in groups:
        xx=np.vstack([features(x) for x in rows])
        ix=[i for i,x in enumerate(rows) if x["code"] in positive_codes]
        if ix:mats.append((xx,ix))
    if not mats:return PRIOR.copy(),{"trainPosts":0,"groups":0,"optimized":False}
    def fun(w):
        loss=0.0;grad=np.zeros(len(w))
        for x,idx in mats:
            logits=x@w
            v=logsumexp(logits)
            weights=np.exp(logits-v)
            loss+=v-np.mean(logits[idx])
            grad+=weights@x-np.mean(x[idx],axis=0)
        loss/=len(mats);grad/=len(mats)
        delta=w-PRIOR
        return loss+lambda_reg*float(delta@delta),grad+2*lambda_reg*delta
    solved=minimize(fun,PRIOR.copy(),jac=True,method="L-BFGS-B",bounds=[(-8,8)]*len(PRIOR),options={"maxiter":200,"ftol":1e-10})
    w=np.clip(solved.x,-8,8)
    return w,{"trainPosts":sum(len(idx) for _,idx in mats),"groups":len(mats),"optimized":bool(solved.success),"objective":round(float(solved.fun),5)}
def score(row,w):
    return round(float(np.clip(50.0+3.0*float(features(row)@w),0,100)),6)
