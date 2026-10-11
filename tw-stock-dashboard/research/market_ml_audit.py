"""MARKET MACHINE LEARNING -- strictly research-only; never overwrites Risk Score.
Archived TWII D-close classification at D+5/D+10 close. 2023-24 training,
2025 validation, 2026 chronologically held out; purge label crossover.
A non-pass must explicitly prevent live ML buy/probability recommendations.
"""
from __future__ import annotations
import json,math,statistics
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import brier_score_loss,roc_auc_score,log_loss
ROOT=Path(__file__).resolve().parents[1]
DIR=ROOT/"docs"/"data"/"research"/"g_regime_3y"
OUT=ROOT/"docs"/"data"/"research"/"market_ml_audit"
OUT.mkdir(parents=True,exist_ok=True)
FEATURES=("originalScore","ret5","ret20","ma20Gap","breadthToday","breadth5","breadthChange5",
          "foreignSigned","vol20","closePosition","scoreChange5","indexDrawdown20")
HORIZONS=(5,10)
SPLITS={"train":("2023-10-11","2024-12-31"),"validation":("2025-01-01","2025-12-31"),
        "holdout":("2026-01-01","2026-10-08")}
def read(path):return json.loads(path.read_text(encoding="utf-8"))
def feats(a,i):
    x=a[i];closes=[float(z["index"]) for z in a]
    rets=[closes[k]/closes[k-1]-1 for k in range(i-19,i+1)]
    breadth=[float(a[k]["breadth"]) for k in range(i-4,i+1)]
    prev=[float(a[k]["breadth"]) for k in range(i-9,i-4)]
    foreign=float(x["foreign"])
    return (float(x["score"]),float(x["ret5"]),float(x["ret20"]),
        float(x["distMA20"]),float(x["breadth"]),statistics.mean(breadth),
        statistics.mean(breadth)-statistics.mean(prev),math.copysign(math.log1p(abs(foreign)/100),foreign),
        statistics.pstdev(rets)*math.sqrt(252)*100,float(x["closePosition"]),
        float(x["score"])-float(a[i-5]["score"]),
        (closes[i]/max(closes[i-20:i+1])-1)*100)
def model(name):
    if name=="SCORE_ONLY":return make_pipeline(StandardScaler(),LogisticRegression(C=1.0,max_iter=800,random_state=2026))
    if name=="L2_REGULARIZED":return make_pipeline(StandardScaler(),LogisticRegression(C=.15,max_iter=800,random_state=2026))
    if name=="L2_STANDARD":return make_pipeline(StandardScaler(),LogisticRegression(C=1.0,max_iter=800,random_state=2026))
    if name=="FOREST_SHALLOW":return RandomForestClassifier(n_estimators=160,min_samples_leaf=32,max_depth=3,
                                               max_features=.7,random_state=20261011,n_jobs=1)
    raise ValueError(name)
def metrics(ys,p,base):
    y=np.asarray(ys,dtype=int);p=np.clip(np.asarray(p,dtype=float),.02,.98)
    b=np.clip(np.asarray(base,dtype=float),.02,.98)
    n=len(y)
    return {"n":n,"positiveRatePct":round(float(y.mean()*100),2),
       "brier":round(float(brier_score_loss(y,p)),5),
       "constantBrier":round(float(brier_score_loss(y,b)),5),
       "auc":round(float(roc_auc_score(y,p)),4) if len(set(y))==2 else None,
       "logLoss":round(float(log_loss(y,p,labels=[0,1])),5),
       "brierLiftOverConstant":round(float(brier_score_loss(y,b)-brier_score_loss(y,p)),5)}
def run():
    rows=read(DIR/"market_risk_daily.json");cov=read(DIR/"coverage.json")
    if len(rows)!=728 or not cov.get("complete") or [x["date"] for x in rows]!=sorted(x["date"] for x in rows):
        raise RuntimeError("Official Risk history incomplete or unsorted")
    latest=read(ROOT/"docs"/"data"/"latest.json")
    if str(latest.get("dataDate"))!=rows[-1]["date"] or int(latest["risk"]["score"])!=int(rows[-1]["score"]):
        raise RuntimeError("Latest score/day does not match official frozen archive: cannot publish current ML report")
    X=np.array([feats(rows,i) for i in range(20,len(rows))],float);dates=[rows[i]["date"] for i in range(20,len(rows))]
    if not np.isfinite(X).all():raise RuntimeError("Invalid historical feature values")
    index={d:i for i,d in enumerate(dates)};names=("CONSTANT","SCORE_ONLY","L2_REGULARIZED","L2_STANDARD","FOREST_SHALLOW")
    result={"version":"MARKET_DIRECTION_MODEL_RESEARCH_ONLY_V1","createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
      "sourceDates":{"start":rows[0]["date"],"end":rows[-1]["date"],"n":len(rows)},
      "features":list(FEATURES),"label":"Future ^TWII close D+H > close D; not a stock-specific profit label",
      "splits":SPLITS,"purging":"Require training label exit strictly before evaluation fold starts, and evaluation labels exit within each fold",
      "candidates":list(names),"horizonModels":{},"operationalStatus":"RESEARCH_ONLY",
      "limitations":["Three years / 728 sessions are too few for robust high-dimensional regime prediction",
       "Original Risk Score already optimized on historical G research; model must beat it before use",
       "Only next 5/10 session TWII direction, not A/D/F/G stock entry profit or next-open execution",
       "Overlapping 5/10 day targets are serially dependent; row counts are not independent trials",
       "Current stock universe bias does not directly affect index label but remains in stock strategy studies",
       "2026 was studied before, so chronological holdout is not pristine independent blind test",
       "No live AI recommendation unless 2025 validation and 2026 5D holdout both beat SCORE_ONLY Brier by >0.01 absolute",
       "Use as supporting evidence only, never directly override original Risk Score gates"]}
    finalApproval=False
    for h in HORIZONS:
        y=np.array([int(float(rows[i+h]["index"])>float(rows[i]["index"])) if i+h<len(rows) else -1 for i in range(20,len(rows))],int)
        train=[k for k,d in enumerate(dates) if d<=SPLITS["train"][1] and k+h<len(dates) and dates[k+h]<=SPLITS["train"][1] and y[k]>=0]
        validation=[k for k,d in enumerate(dates) if SPLITS["validation"][0]<=d<=SPLITS["validation"][1] and k+h<len(dates) and dates[k+h]<=SPLITS["validation"][1] and y[k]>=0]
        holdout=[k for k,d in enumerate(dates) if SPLITS["holdout"][0]<=d<=SPLITS["holdout"][1] and k+h<len(dates) and dates[k+h]<=SPLITS["holdout"][1] and y[k]>=0]
        fit2025=sorted(train+validation)
        if min(len(train),len(validation),len(holdout))<90:raise RuntimeError("Insufficient yearly fold coverage")
        measurements={}
        baselineVal=float(y[train].mean());baselineHold=float(y[fit2025].mean())
        for name in names:
            if name=="CONSTANT":
                pval=np.full(len(validation),baselineVal);phold=np.full(len(holdout),baselineHold)
            else:
                cols=[0] if name=="SCORE_ONLY" else list(range(X.shape[1]))
                vmodel=model(name);vmodel.fit(X[np.ix_(train,cols)],y[train])
                pval=vmodel.predict_proba(X[np.ix_(validation,cols)])[:,1]
                hmodel=model(name);hmodel.fit(X[np.ix_(fit2025,cols)],y[fit2025])
                phold=hmodel.predict_proba(X[np.ix_(holdout,cols)])[:,1]
            measurements[name]={"validation":metrics(y[validation],pval,np.full(len(validation),baselineVal)),
                                "holdout":metrics(y[holdout],phold,np.full(len(holdout),baselineHold))}
        scoreBase=measurements["SCORE_ONLY"]["validation"]["brier"]
        candidateNames=("L2_REGULARIZED","L2_STANDARD","FOREST_SHALLOW")
        selected=min(candidateNames,key=lambda n:(measurements[n]["validation"]["brier"],n))
        va=measurements[selected]["validation"];ho=measurements[selected]["holdout"]
        scoreHeld=measurements["SCORE_ONLY"]["holdout"]["brier"]
        approved=va["brier"]<=scoreBase-.01 and ho["brier"]<=scoreHeld-.01
        if h==5:finalApproval=approved
        result["horizonModels"][str(h)]={"trainSamples":len(train),"validationSamples":len(validation),
            "holdoutSamples":len(holdout),"selectedOn2025Only":selected,
            "selected2025BrierImprovementVsScore":round(scoreBase-va["brier"],5),
            "selected2026BrierImprovementVsScore":round(scoreHeld-ho["brier"],5),
            "qualifiedForAdvisory":approved,"models":measurements}
    # No model probabilities are exported to the market dashboard; don't convey
    # unvalidated model direction as an "AI says buy" label.
    result["advisoryEligible"] = bool(finalApproval)
    result["decision"]="Eligible as supplementary research-only evidence, NOT trading permission" if finalApproval else "DO_NOT_DEPLOY_ML; old score and transparent risk flags remain primary"
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("MARKET_ML_AUDIT_DONE",json.dumps({"5D":{k:result["horizonModels"]["5"][k] for k in ("selectedOn2025Only","selected2025BrierImprovementVsScore","selected2026BrierImprovementVsScore","qualifiedForAdvisory")},
       "10D":{k:result["horizonModels"]["10"][k] for k in ("selectedOn2025Only","selected2025BrierImprovementVsScore","selected2026BrierImprovementVsScore","qualifiedForAdvisory")},
       "decision":result["decision"]},ensure_ascii=False),flush=True)
if __name__=="__main__":run()
