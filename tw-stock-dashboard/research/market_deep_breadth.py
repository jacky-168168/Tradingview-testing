"""Out-of-sample 08:59 proxy benchmark for next-session Taiwanese stock breadth.
Models: Constant, SCORE logistic, tabular logistic, shallow tree, compact RNN,
GRU, causal TCN. TFT and DRL are NOT deceptively labelled as implemented.
Extended official year shards included only as a contiguous fully verified chain.
No intraday 09:00 feature, future date, or same-day breadth label leaks.
"""
from __future__ import annotations
import copy,json,math,random,time
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import torch
from torch import nn
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import brier_score_loss,roc_auc_score,balanced_accuracy_score,log_loss
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"docs"/"data"/"research";ORIGINAL=DATA/"g_regime_3y"
OUT=DATA/"market_sequence_models";OUT.mkdir(parents=True,exist_ok=True)
WINDOW=14;SEEDS=(11,29);EPOCHS=42
def read(p):return json.loads(Path(p).read_text(encoding="utf-8"))
def load_complete():
    cov=read(ORIGINAL/"coverage.json");base=read(ORIGINAL/"market_risk_daily.json")
    if not cov.get("complete") or len(base)!=728:raise RuntimeError("Core official 728-day history unverified")
    rows=list(base);years=[]
    for year in range(2023,2014,-1):
        p=DATA/"market_history_extended"/"years"/(str(year)+".json")
        if not p.exists():break
        j=read(p);c=j["coverage"];historic=j.get("riskRows",[])
        if not c.get("complete") or c.get("riskScoredDays")!=c.get("tradingDays") or len(historic)!=c.get("tradingDays"):
            print("SKIP_INCOMPLETE_YEAR_CHAIN",year,c.get("coveragePct"),flush=True)
            break
        if any(z.get("up") is None or z.get("down") is None or z.get("index") is None for z in historic):
            raise RuntimeError("Bad officially marked historical year "+str(year))
        if historic[-1]["date"]>=rows[0]["date"]:raise RuntimeError("Old-year archive overlaps existing official history")
        rows=historic+rows;years.insert(0,year)
    d=[x["date"] for x in rows]
    if d!=sorted(d) or len(set(d))!=len(d):raise RuntimeError("Duplicate/out-of-order extended dates")
    return rows,years
def feature(r):
    foreign=float(r["foreign"]);ret=float(r["dayRet"])
    return [float(r["score"])/100.,float(r["breadth"])/100.,ret/5.,
      float(r["ret5"])/12.,float(r["ret20"])/25.,
      math.copysign(math.log1p(abs(foreign)/100),foreign),
      float(r["distMA20"])/12.,float(r["closePosition"])/100.,
      float(r.get("indexRvol",1))/3.,
      float(r.get("oversoldScore",0))/10.,float(r.get("overboughtScore",0))/10.]
def create(rows,target):
    values=np.asarray([feature(z) for z in rows],dtype=np.float32)
    if not np.isfinite(values).all():raise RuntimeError("Missing or nonfinite date-tied market observation")
    seq=[];y=[];dates=[];labels=[]
    for i in range(WINDOW-1,len(rows)-1):
        d,after=rows[i],rows[i+1]
        if target=="NEXT_BREADTH_MAJORITY":label=int(float(after["breadth"])>50)
        elif target=="NEXT_INDEX_UP":label=int(float(after["dayRet"])>0)
        else:raise ValueError(target)
        seq.append(values[i-WINDOW+1:i+1])
        y.append(label);dates.append(d["date"]);labels.append(after["date"])
    X=np.asarray(seq,dtype=np.float32);Y=np.asarray(y,dtype=np.float32)
    split={}
    for name,a,b in (("train","2015-01-01","2024-12-31"),
                     ("validation","2025-01-01","2025-12-31"),
                     ("holdout","2026-01-01","2026-10-08")):
        split[name]=np.asarray([i for i,(d,labeldate) in enumerate(zip(dates,labels)) if a<=d<=b and a<=labeldate<=b],int)
        if len(split[name])<100:raise RuntimeError("Insufficient independently dated "+name+" samples: "+str(len(split[name])))
    return X,Y,split,dates
class SeqNet(nn.Module):
    def __init__(self,kind,inputdim):
        super().__init__();self.kind=kind
        if kind=="RNN":self.rnn=nn.RNN(inputdim,12,batch_first=True,nonlinearity="tanh")
        elif kind=="GRU":self.rnn=nn.GRU(inputdim,12,batch_first=True)
        elif kind=="TCN":
            self.c1=nn.Conv1d(inputdim,12,kernel_size=3,padding=2)
            self.c2=nn.Conv1d(12,12,kernel_size=3,padding=4,dilation=2)
            self.act=nn.ReLU();self.drop=nn.Dropout(.10)
        else:raise ValueError(kind)
        self.out=nn.Linear(12,1)
    def forward(self,x):
        if self.kind in ("RNN","GRU"):a,_=self.rnn(x);v=a[:,-1,:]
        else:
            a=self.act(self.c1(x.transpose(1,2))[:,:,:x.shape[1]])
            a=self.drop(a);a=self.act(self.c2(a)[:,:,:x.shape[1]])
            v=a[:,:,-1]
        return self.out(v).squeeze(-1)
def metric(y,p):
    yy=np.asarray(y,dtype=int);pr=np.clip(np.asarray(p,dtype=float),.015,.985)
    result={"n":len(yy),"majorityUpPct":round(float(yy.mean()*100),2),
      "brier":round(float(brier_score_loss(yy,pr)),5),
      "balancedAccuracyPct":round(float(balanced_accuracy_score(yy,pr>=.5)*100),2),
      "logLoss":round(float(log_loss(yy,pr,labels=[0,1])),5)}
    result["auc"]=round(float(roc_auc_score(yy,pr)),4) if len(set(yy))>1 else None
    return result
def fit_nn(kind,X,y,split,seed):
    torch.manual_seed(seed);np.random.seed(seed);random.seed(seed);torch.set_num_threads(1)
    train,val,hold=split["train"],split["validation"],split["holdout"]
    net=SeqNet(kind,X.shape[-1]);opt=torch.optim.AdamW(net.parameters(),lr=.004,weight_decay=.006)
    xx=torch.as_tensor(X);yy=torch.as_tensor(y)
    best=None;bestVal=float("inf");bestEpoch=0;patience=0
    for epoch in range(EPOCHS):
        net.train();gen=np.random.default_rng(seed*100+epoch)
        for ids in np.array_split(gen.permutation(train),max(1,math.ceil(len(train)/64))):
            opt.zero_grad();loss=nn.functional.binary_cross_entropy_with_logits(net(xx[ids]),yy[ids])
            loss.backward();nn.utils.clip_grad_norm_(net.parameters(),1.0);opt.step()
        net.eval()
        with torch.no_grad():pv=torch.sigmoid(net(xx[val])).numpy()
        vl=brier_score_loss(y[val],pv)
        if vl<bestVal-0.00005:
            bestVal=vl;best=copy.deepcopy(net.state_dict());bestEpoch=epoch+1;patience=0
        else:patience+=1
        if epoch>=17 and patience>=9:break
    net.load_state_dict(best);net.eval()
    with torch.no_grad():
        return {"validation":torch.sigmoid(net(xx[val])).numpy(),
            "holdout":torch.sigmoid(net(xx[hold])).numpy()},bestEpoch
def main():
    started=time.time();rows,years=load_complete()
    info={"version":"TWSE_BREADTH_SEQUENCE_OOS_2026_10_V1",
      "createdAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(),
      "officialRows":len(rows),"verifiedExtraYears":years,
      "dates":[rows[0]["date"],rows[-1]["date"]],
      "snapshot":"At 08:59 D+1, use only facts finalized by close D; no true 09:00 intraday data is present",
      "windowDays":WINDOW,"features":["riskScore","breadth","dayReturn","ret5","ret20","foreignSignedLog",
        "ma20Gap","closePosition","indexRvol","oversold","overbought"],
      "seedList":list(SEEDS),"tasks":{},
      "validationPolicy":"2025 used only for model/epoch selection; 2026 chronologically held out, NOT pristine because previous studies inspected 2026",
      "candidateModels":["BASE_RATE","RISK_SCORE_LOGIT","TABULAR_LOGIT","SHALLOW_TREE","RNN","GRU","TCN"],
      "intentionallyNotImplemented":{"TFT":"Complex multi-horizon model needs larger official history and verified known-future covariates; too much overfit risk with a single short TWII series",
        "DRL":"Requires executable market environment, stocks, action sizing, costs, and rewards; not suitable as direct classifier of next-day stock breadth"},
      "limitations":["All same-day breadth and foreigners are observed AFTER session close D, not during 09:00 of D",
        "Windowed daily data are serially correlated; n is NOT number of independent experiments",
        "Historical breadth covers TWSE listed stocks, not TPEx OTC",
        "No 9:00 exchange feed or historical intraday preview exists: only 08:59 proxy predictions",
        "2026 outcomes have been viewed before and are NOT pristine blind holdout",
        "Benchmark has no 09:00 stock transaction fill, cost, slippage or executable returns",
        "Small RNN/GRU/TCN are real fitted networks but not proof of stock trading edge",
        "Supplementary probability does not replace official Risk Score or F/F2/G market gate"]}
    for target in ("NEXT_BREADTH_MAJORITY","NEXT_INDEX_UP"):
        X,Y,split,dates=create(rows,target);tr=split["train"];va=split["validation"];ho=split["holdout"]
        # Normalize with training ONLY; never learn 2025 or 2026 feature statistics.
        mean=X[tr].reshape(-1,X.shape[-1]).mean(axis=0)
        std=X[tr].reshape(-1,X.shape[-1]).std(axis=0)
        Z=np.clip((X-mean)/np.maximum(std,.05),-5,5).astype(np.float32)
        predictions={}
        rate=float(Y[tr].mean())
        predictions["BASE_RATE"]={"validation":np.full(len(va),rate),"holdout":np.full(len(ho),rate)}
        for kind in ("RISK_SCORE_LOGIT","TABULAR_LOGIT","SHALLOW_TREE"):
            if kind=="RISK_SCORE_LOGIT":
                cols=[0];model=make_pipeline(StandardScaler(),LogisticRegression(C=.5,max_iter=1200))
            elif kind=="TABULAR_LOGIT":
                cols=list(range(Z.shape[-1]));model=make_pipeline(StandardScaler(),LogisticRegression(C=.2,max_iter=1200))
            else:
                cols=list(range(Z.shape[-1]))
                model=HistGradientBoostingClassifier(max_iter=70,max_depth=2,max_leaf_nodes=6,
                  min_samples_leaf=25,l2_regularization=8,random_state=2026)
            model.fit(Z[tr,-1][:,cols],Y[tr])
            predictions[kind]={"validation":model.predict_proba(Z[va,-1][:,cols])[:,1],
                 "holdout":model.predict_proba(Z[ho,-1][:,cols])[:,1]}
        deep_epochs={}
        for kind in ("RNN","GRU","TCN"):
            trials=[]
            for seed in SEEDS:
                pred,ep=fit_nn(kind,Z,Y,split,seed)
                b=brier_score_loss(Y[va],pred["validation"])
                trials.append((b,seed,pred,ep))
            trials.sort(key=lambda z:(z[0],z[1]))
            _,bestSeed,bestPred,epochs=trials[0]
            predictions[kind]=bestPred
            deep_epochs[kind]={"selectedSeedOn2025":bestSeed,"bestEpoch":epochs,
                "validationBrierBySeed":{str(seed):round(float(b),5) for b,seed,_,_ in trials}}
        ratings={kind:{splitName:metric(Y[split[splitName]],pred[splitName])
             for splitName in ("validation","holdout")} for kind,pred in predictions.items()}
        winner=min((k for k in ratings if k!="BASE_RATE"),
                   key=lambda k:(ratings[k]["validation"]["brier"],k))
        gapVal=round(ratings["RISK_SCORE_LOGIT"]["validation"]["brier"]-ratings[winner]["validation"]["brier"],5)
        gapTest=round(ratings["RISK_SCORE_LOGIT"]["holdout"]["brier"]-ratings[winner]["holdout"]["brier"],5)
        info["tasks"][target]={"sizes":{k:len(v) for k,v in split.items()},
          "trainBaseRatePct":round(rate*100,2),"models":ratings,"modelSelectedOn2025Only":winner,
          "selectedValidationBrierAdvantageVsRiskScore":gapVal,
          "selected2026BrierAdvantageVsRiskScore":gapTest,
          "deepTraining":deep_epochs,
          "researchGateAccepted":bool(len(tr)>=400 and gapVal>=.01 and gapTest>=.01 and
               ratings[winner]["holdout"]["brier"]<ratings["BASE_RATE"]["holdout"]["brier"])}
    info["deployment"]="NEVER_USE_AS_LIVE_BUY_SIGNAL: market breadth and index direction are not tested individual-stock executable payoffs"
    info["elapsedSec"]=round(time.time()-started,2)
    (OUT/"summary.json").write_text(json.dumps(info,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print("DEEP_BREADTH_AUDIT_DONE",json.dumps({"days":info["officialRows"],"additionalYears":years,
      "breadthWinner":info["tasks"]["NEXT_BREADTH_MAJORITY"]["modelSelectedOn2025Only"],
      "breadthBrier":{m:{"2025":z["validation"]["brier"],"2026":z["holdout"]["brier"]}
          for m,z in info["tasks"]["NEXT_BREADTH_MAJORITY"]["models"].items()},
      "selected":{task:z["modelSelectedOn2025Only"] for task,z in info["tasks"].items()},
      "elapsedSec":info["elapsedSec"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
