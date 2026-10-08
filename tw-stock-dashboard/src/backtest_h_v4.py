"""H4 ML screener: learns turnover/price/volume relationships from 2025 only.
Rules and labels are independent from all A/D/F/G filters and ranks.
2026 Jan-May chooses probability threshold; June-Oct is checked exactly once.
Prior H1-H3 did inspect 2026, so global true OOS status is not claimed.
"""
from __future__ import annotations
import json,time,itertools
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,HistGradientBoostingClassifier
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from backtest_h_v3 import features,stat,percent_wilson_lower
from config import DATA_DIR
from backtest_h_v3 import START,END,labels
# Independent training, chronological threshold calibration, single later evaluation.
TRAIN_START="2025-07-01";TRAIN_END="2025-12-31"
VALID_START="2026-01-01";VALID_END="2026-05-29"
TEST_START="2026-06-01";TEST_END=END
INPUTS=["turn","turn5","vrel","p120","b8","b20","draw20","ret5","prev5","ret20","day",
        "priorDay","range8","vcon","pos","body","aboveEma","emaSlope","aboveMa60","atr","tradedM"]
TOP=3
def build_dataset():
    start=datetime(2024,8,1);end=datetime(2026,10,8)
    company=load_universe()
    print("H4 Fetch 2024 warmup/2025 training/2026 validation and test",len(company),flush=True)
    hist,errs=update_many([(x["code"],x["market"]) for x in company],start,end)
    _,index,error=update_symbol("^TWII",start,end)
    if error or index is None or len(index)<400:raise RuntimeError("Index calendar insufficient")
    dates=index.date.astype(str).tolist();ipos={d:i for i,d in enumerate(dates)}
    event=[];names=["code","market","name"]+labels
    for i,stock in enumerate(company):
        cap=float(stock.get("capitalB") or 0.)
        if cap<=0:continue
        sym=to_symbol(stock["code"],stock["market"])
        frame=hist.get(sym)
        if frame is None or len(frame)<160:continue
        rows=features(frame,cap,dates,ipos,sample_start=TRAIN_START,sample_end=TEST_END)
        if rows:event.extend((str(stock["code"]),stock["market"],stock["name"],*v) for v in rows)
        if (i+1)%350==0:print(f"H4 loaded {i+1}/{len(company)} eventRows={len(event)}",flush=True)
    df=pd.DataFrame(event,columns=names)
    if df.empty:raise RuntimeError("No feature events")
    df["net"]=pd.to_numeric(df.net,errors="coerce")
    df["period"]=np.select([df.date<=TRAIN_END,df.date<=VALID_END],["train","valid"],default="test")
    print("H4 dataset",df.groupby("period").size().to_dict(),"filled",df[df.status==1].groupby("period").size().to_dict(),flush=True)
    return df,{"universe":len(company),"dataErrors":len(errs),"candidateStockDays":len(df),"byPeriod":df.groupby("period").size().to_dict()}
def pick(df,cut,turn_min,near_min):
    mask=(df["score"]>=cut)&(df.turn>=turn_min)&(df.p120>=near_min)
    a=df.loc[mask].sort_values(["date","score","turn","code"],ascending=[True,False,False,True])
    return a.groupby("date",sort=False).head(TOP)
def results(rows):
    return stat(rows)
def train_models(frame):
    tr=frame[(frame.period=="train")&(frame.status==1)]
    y=tr.tp.astype(int).to_numpy()
    if len(tr)<500 or y.sum()<60:raise RuntimeError("Insufficient 2025 training examples")
    x=tr[INPUTS].to_numpy(dtype=float)
    specs=[
        ("regularized_logistic",make_pipeline(SimpleImputer(strategy="median"),StandardScaler(),LogisticRegression(C=.1,max_iter=600,class_weight="balanced",random_state=42))),
        ("shallow_forest",RandomForestClassifier(n_estimators=160,max_depth=5,min_samples_leaf=90,min_samples_split=200,max_features=.6,class_weight="balanced_subsample",n_jobs=-1,random_state=42)),
        ("boosted_tree",HistGradientBoostingClassifier(max_iter=120,max_depth=3,min_samples_leaf=100,learning_rate=.05,l2_regularization=10,random_state=42))
    ]
    result={}
    for name,model in specs:
        t=time.time()
        model.fit(x,y)
        prob=model.predict_proba(frame[INPUTS].to_numpy(dtype=float))[:,1]
        result[name]={"model":model,"scores":prob}
        print("H4 fit",name,"seconds",round(time.time()-t,2),flush=True)
    return result
def run():
    began=time.time()
    frame,coverage=build_dataset()
    models=train_models(frame)
    tested=[];guardrails={"minValidationFills":35,"minTrainingFills":80,"minHoldoutFills":35,"holdoutHitTargetPct":58,"holdoutAvgNetGtPct":0}
    for name,entry in models.items():
        current=frame.assign(score=entry["scores"])
        for threshold,turn,near in itertools.product((.35,.4,.45,.5,.55,.6),(1.5,3.0),(.80,.92)):
            rule={"model":name,"minScore":threshold,"minTurnoverProxyPct":turn,"minPriceTo120dayHigh":near}
            p=pick(current,threshold,turn,near)
            train=results(p[p.period=="train"])
            valid=results(p[p.period=="valid"])
            if train["n"]<80 or valid["n"]<35:continue
            # Selection ONLY train + validation; test rows not read until leader frozen.
            mismatch=abs(train["hitPct"]-valid["hitPct"])
            measure=valid["hitPct"]+0.3*max(-5,train["avgNet"])+1.5*max(-5,valid["avgNet"])-0.2*max(0,mismatch-10)+3*np.log1p(valid["n"])
            tested.append({"config":rule,"train":train,"valid":valid,"utility":round(float(measure),4)})
    tested.sort(key=lambda x:(-x["utility"],-x["valid"]["n"]))
    best=tested[0] if tested else None
    result_test=None;held=[]
    if best is not None:
        info=best["config"]
        pred=frame.assign(score=models[info["model"]]["scores"])
        held=pick(pred[pred.period=="test"],info["minScore"],info["minTurnoverProxyPct"],info["minPriceTo120dayHigh"])
        result_test=results(held)
    success=bool(result_test is not None and result_test["n"]>=35 and result_test["hitPct"]>=58 and result_test["avgNet"]>0 and percent_wilson_lower(result_test["target"],result_test["n"])>.4)
    report={"version":"H4_MACHINE_LEARNING_2025_TRAIN_2026_TEST","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
        "periods":{"train":[TRAIN_START,TRAIN_END],"validation":[VALID_START,VALID_END],"holdout":[TEST_START,TEST_END]},
        "coverage":coverage,"featureNames":INPUTS,
        "precommittedModels":["regularized_logistic","shallow_forest","boosted_tree"],
        "thresholds":[.35,.4,.45,.5,.55,.6],"turnoverMin":[1.5,3.0],"nearHighMin":[.8,.92],
        "tested":3*6*2*2,"eligibleOnTrainValidation":len(tested),
        "guardrails":guardrails,"selectionOnTrainValidation":best,
        "later2026Holdout":result_test,
        "holdoutWilsonLower95":percent_wilson_lower(result_test["target"],result_test["n"]) if result_test and result_test["n"] else None,
        "goalReached":success,
        "topTenTrainValidation":tested[:10],
        "warnings":["This H4 learned from 2025 data only, but 2026 was previously inspected during H1-H3 and is not globally untouched.","Turnover uses currently reported paid-in capital / TWD10 nominal share and is not historical outstanding shares.","Universe is surviving TWSE/TPEx companies; excluding delisted stocks can bias outcomes.","The model predicts gross +7% achieved BEFORE gross -3.5% stop in up to five market days, not 60% net +7%.","No hindsight filtering of opening gaps: selected stocks may remain unfilled. Daily OHLC simultaneous target/stop assumes stop first.","Fitting many models/thresholds can inflate observed validation hit rates; do not iterate on 2026 holdout."],
        "elapsedSeconds":round(time.time()-began,1)}
    p=DATA_DIR/"backtest_h_v4";p.mkdir(parents=True,exist_ok=True)
    (p/"H4_2026_model_report.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if best is not None:
        columns=["date","code","name","market","score","turn","vrel","p120","status","tp","stop","net","reason"]
        (p/"H4_2026_holdout_signals.json").write_text(held[columns].to_json(orient="records",force_ascii=False,indent=2),encoding="utf-8")
    print("H4_RESULT "+json.dumps({k:report[k] for k in ("periods","coverage","tested","eligibleOnTrainValidation","selectionOnTrainValidation","later2026Holdout","goalReached","elapsedSeconds")},ensure_ascii=False),flush=True)
    return report
if __name__=="__main__":run()
