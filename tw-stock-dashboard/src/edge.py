from __future__ import annotations
import hashlib,math
import numpy as np
from scipy.stats import t as student_t

BOOTSTRAP_REPS=600; OOS_BOOTSTRAP_REPS=300; MONTE_CARLO_REPS=300

def rnd(x,n=2): return None if x is None or not np.isfinite(x) else round(float(x),n)
def mean(a): return float(np.mean(a)) if len(a) else 0.0
def sample_std(a): return float(np.std(a,ddof=1)) if len(a)>1 else 0.0

def max_drawdown(vals):
    eq=peak=1.0;mdd=0.0
    for v in vals:
        eq*=max(0.000001,1+float(v)/100);peak=max(peak,eq);mdd=max(mdd,(peak-eq)/peak*100)
    return round(mdd,2)

def longest_loss(vals):
    cur=best=0
    for v in vals:
        if v<0:cur+=1;best=max(best,cur)
        else:cur=0
    return best

def concentration(vals):
    p=sorted([float(v) for v in vals if v>0],reverse=True);s=sum(p)
    return round(sum(p[:3])/s*100,1) if s>0 else 0.0

def t_p(vals):
    a=np.asarray(vals,dtype=float);n=len(a)
    if n<2:return 1.0
    m=float(a.mean());sd=float(a.std(ddof=1))
    if sd==0:return 0.0 if m>0 else 1.0
    return round(max(0,min(1,1-float(student_t.cdf(m/(sd/math.sqrt(n)),df=n-1)))),5)

def seed(vals,salt):
    s="|".join(f"{float(v):.6f}" for v in vals)+f"|{salt}"
    return int(hashlib.sha256(s.encode()).hexdigest()[:8],16)

def bootstrap_p(vals,reps=BOOTSTRAP_REPS,salt=0):
    a=np.asarray(vals,dtype=float);n=len(a)
    if n<2 or a.mean()<=0:return 1.0
    obs=float(a.mean());centered=a-obs;rng=np.random.default_rng(seed(a,salt));B=max(100,int(reps));ext=0
    for _ in range(B):
        if float(rng.choice(centered,size=n,replace=True).mean())>=obs-1e-12:ext+=1
    return round((ext+1)/(B+1),5)

def monte_carlo(vals,reps=MONTE_CARLO_REPS,salt=0):
    a=np.asarray(vals,dtype=float);n=len(a)
    if n<5:return {"valid":False,"p95Mdd":None,"risk20":None}
    rng=np.random.default_rng(seed(a,991+salt));dds=[];over=0
    for _ in range(max(100,int(reps))):
        m=max_drawdown(rng.choice(a,size=n,replace=True));dds.append(m);over+=m>=20
    return {"valid":True,"p95Mdd":round(float(np.percentile(dds,95,method="higher")),2),"risk20":round(over/len(dds)*100,1)}

def nonoverlap(pairs,h):return [x for i,x in enumerate(pairs) if i%max(1,h)==0 and x.get("ret") is not None]

def oos(pairs,h):
    a=nonoverlap(pairs,h);n=len(a);cut=int(n*0.7)
    if cut<10 or n-cut<10:return {"valid":False,"n":n,"text":"樣本不足"}
    iv=[x["ret"] for x in a[:cut]];ov=[x["ret"] for x in a[cut:]];im=mean(iv);om=mean(ov)
    ip=max(t_p(iv),bootstrap_p(iv,OOS_BOOTSTRAP_REPS,101+h));op=max(t_p(ov),bootstrap_p(ov,OOS_BOOTSTRAP_REPS,211+h));deg=(im-om)/abs(im)*100 if im>0 else None
    passed=im>0 and om>0 and ip<.05 and op<.05 and (deg is None or deg<50)
    return {"valid":True,"n":n,"isN":len(iv),"oosN":len(ov),"isMean":rnd(im),"oosMean":rnd(om),"degradation":rnd(deg,1),"isP":rnd(ip,5),"oosP":rnd(op,5),"pass":passed,"text":"通過" if passed else "未通過"}

def metric(pairs,h):
    full=[float(x["ret"]) for x in pairs if x.get("ret") is not None];test=[float(x["ret"]) for x in nonoverlap(pairs,h)];n=len(full);wins=[x for x in full if x>0];loss=[x for x in full if x<0]
    gw=sum(wins);gl=abs(sum(loss));aw=mean(wins);al=abs(mean(loss)) if loss else 0;sd=sample_std(full);ann=math.sqrt(252/max(1,h));down=[x for x in full if x<0];dd=math.sqrt(sum(x*x for x in down)/len(down)) if down else 0
    pf=gw/gl if gl>0 else None;pay=aw/al if al>0 else None;sh=mean(full)/sd*ann if sd>0 else None;so=mean(full)/dd*ann if dd>0 else None;tp=t_p(test);bp=bootstrap_p(test,BOOTSTRAP_REPS,401+h);mdd=max_drawdown(full);conc=concentration(full);ls=longest_loss(full);oo=oos(pairs,h);mc=monte_carlo(test,MONTE_CARLO_REPS,601+h);exp=mean(full);wr=len(wins)/n if n else 0;bew=al/(aw+al)*100 if aw>0 and al>0 else None;bep=(1-wr)/wr if wr>0 else None
    if exp< -1e-10:v="gambling"
    elif len(test)<20 or abs(exp)<=1e-10:v="insufficient"
    elif tp>=.05 or bp>=.05:v="luck_suspected"
    elif (pf is not None and pf<1.2) or mdd>20 or conc>50 or ls>=6 or (oo.get("valid") and not oo.get("pass")):v="fragile_edge"
    else:v="statistical_edge"
    return {"n":n,"testN":len(test),"expectancy":rnd(exp),"winRate":rnd(wr*100,1),"payoff":rnd(pay),"breakEvenWinRate":rnd(bew,1),"breakEvenPayoff":rnd(bep),"profitFactor":rnd(pf),"profitFactorInfinite":pf is None and gw>0,"sharpe":rnd(sh),"sortino":rnd(so),"maxDrawdown":mdd,"longestLossStreak":ls,"profitConcentrationTop3":conc,"tP":tp,"bootstrapP":bp,"oos":oo,"monteCarlo":mc,"verdict":v}

def build(models):
    out={"version":"EDGE-AUDIT-PY-V1","method":"Top3固定三槽；非重疊近似樣本；單尾t-test + centered bootstrap；OOS 70/30；Monte Carlo重抽樣","bootstrapReps":BOOTSTRAP_REPS,"monteCarloReps":MONTE_CARLO_REPS,"models":{}}
    for mid,series in models.items():out["models"][mid]={f"d{h}":metric(series[h],h) for h in [1,3,5,10,20]}
    return out
