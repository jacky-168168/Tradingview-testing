"""2026 G_TARGET study: train on early disclosed signals, test later held-out posts."""
from __future__ import annotations
import argparse,json,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR,MIN_PRICE,MAX_CAPITAL_B
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import precompute_features
from research_signal_samples import SAMPLES
from backtest_signal_model import stat,price_return,phase_portfolio,score_row,pass_variant,VARIANTS,H
from g_target import eligible,features,fit,score,FEATURES
TRAIN_END="2026-09-18"
FIELDS={"ret20":"ret20P","ma20Slope":"slopeP","atrPct":"atrP","range20Pct":"range20P","turnoverB":"turnoverP","ret5":"ret5P","mom10Pct":"mom10P","range10Pct":"range10P","rvol10":"rvol10P","closePosition":"positionP","dayRet":"dayP","ema20Slope5":"emaSlopeP","vol5vs20":"v520P"}
def run(start,end):
    began=time.time()
    if start!="2026-01-01" or not end.startswith("2026-"):raise ValueError("G_TARGET 研究限定自2026/01/01起")
    today=datetime.now(ZoneInfo("Asia/Taipei")).date().isoformat()
    if end>today:raise ValueError("不可回測未來日期")
    fs=datetime.fromisoformat(start)-timedelta(days=180);fe=datetime.fromisoformat(end)+timedelta(days=35)
    universe=load_universe();meta={x["code"]:x for x in universe if float(x.get("capitalB") or 0)>0}
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],fs,fe)
    _,idx,error=update_symbol("^TWII",fs,fe)
    if error or idx is None or idx.empty:raise RuntimeError(f"benchmark unavailable: {error}")
    dates=sorted(set(idx.date.astype(str)));pos={d:i for i,d in enumerate(dates)}
    signals=[d for d in dates if start<=d<=end]
    targets={}
    samples=[]
    for s in SAMPLES:
        if not s["date"].startswith("2026-"):continue
        earlier=[d for d in dates if d<s["date"] and d in signals]
        if not earlier:continue
        anchor=earlier[-1]
        targets.setdefault(anchor,set()).add(s["code"])
        samples.append({**s,"anchorDate":anchor})
    feats={};prices={}
    for n,s in enumerate(universe,1):
        sy=to_symbol(s["code"],s["market"]);px=hist.get(sy)
        if px is None or len(px)<60:continue
        q=precompute_features(px)
        hi=pd.to_numeric(q.high,errors="coerce");lo=pd.to_numeric(q.low,errors="coerce");vol=pd.to_numeric(q.volume,errors="coerce")
        q["range20Pct"]=(hi.rolling(20).max()/lo.rolling(20).min()-1)*100
        q["range10Pct"]=(hi.rolling(10).max()/lo.rolling(10).min()-1)*100
        q["vol5vs20"]=vol.rolling(5).mean()/vol.rolling(20).mean()
        q["turnoverB"]=pd.to_numeric(q.close,errors="coerce")*vol/100_000_000
        feats[sy]=q.set_index("date",drop=False)
        prices[sy]=px.sort_values("date").set_index("date",drop=False)
    daily={};all_sample_rows={};base_rank={}
    for n,d in enumerate(signals,1):
        rows=[]
        for c,info in meta.items():
            sy=to_symbol(c,info["market"]);ft=feats.get(sy)
            if ft is None or d not in ft.index:continue
            q=ft.loc[d];q=q.iloc[-1] if isinstance(q,pd.DataFrame) else q
            raw=[q.get(k) for k in FIELDS]
            if any(pd.isna(z) or not np.isfinite(float(z)) for z in raw):continue
            close=float(q["close"]);cap=float(info.get("capitalB") or 0);br=float(q.get("breakoutPct",np.nan))
            if not np.isfinite(br) or close<=0 or cap<=0:continue
            rows.append({"code":c,"name":info["name"],"market":info["market"],"capitalB":cap,"close":close,"breakoutPct":br,**{k:float(q[k]) for k in FIELDS}})
        if not rows:daily[d]=[];continue
        df=pd.DataFrame(rows)
        for raw,pct in FIELDS.items():df[pct]=df[raw].rank(pct=True,method="average")*100
        allrows=df.to_dict("records")
        baseline=[x for x in allrows if pass_variant(x,VARIANTS["G_BASE"])]
        baseline.sort(key=lambda x:(-score_row(x),-x["ret20P"],-x["slopeP"],x["code"]))
        base_rank[d]={x["code"]:i+1 for i,x in enumerate(baseline)}
        controls=[x for x in allrows if eligible(x)]
        daily[d]=controls
        if d in targets:
            for x in allrows:
                if x["code"] in targets[d]:all_sample_rows[(d,x["code"])]=x
        if n%40==0 or n==len(signals):print(f"G_TARGET feature rows {n}/{len(signals)} {d} eligible={len(controls)}",flush=True)
    train=[(daily[d],targets[d]) for d in sorted(targets) if d<=TRAIN_END and daily.get(d)]
    full=[(daily[d],targets[d]) for d in sorted(targets) if daily.get(d)]
    locked,fit_early=fit(train)
    diagnostic,fit_all=fit(full)
    models={}
    for model,weights in (("G_TARGET",locked),("G_TARGET_FULL20",diagnostic)):
        rankmaps={};ranktop={};candidate_stats=[]
        for d in signals:
            arr=daily.get(d,[])
            xs=sorted(arr,key=lambda x:(-score(x,weights),-x["ret20P"],x["code"]))
            rankmaps[d]={x["code"]:i+1 for i,x in enumerate(xs)}
            candidate_stats.append(len(xs))
            ranktop[d]=[{**x,"rank":i+1,"gScore":score(x,weights)} for i,x in enumerate(xs[:20])]
        daily_return={h:[] for h in H};daily_forward={h:[] for h in H};rank_returns={h:{1:[],2:[],3:[]} for h in H}
        trades=[]
        for d in signals:
            ip=pos[d]
            if ip+1>=len(dates):continue
            buydate=dates[ip+1]
            by_h={h:[] for h in H}
            for x in ranktop.get(d,[]):
                rec={"signalDate":d,"rank":x["rank"],"code":x["code"],"name":x["name"],"market":x["market"],"score":x["gScore"],"capitalB":round(x["capitalB"],2),"breakoutPct":round(x["breakoutPct"],2),"percentiles":{k:round(x[k],1) for k in FIELDS.values()}}
                px=prices.get(to_symbol(x["code"],x["market"]))
                for h in H:
                    rr=price_return(px,buydate,dates[ip+h]) if ip+h<len(dates) else None
                    rec[f"ret{h}"]=round(rr,2) if rr is not None else None
                    if rr is not None and x["rank"]<=3:
                        by_h[h].append(rr);rank_returns[h][x["rank"]].append(rr)
                if x["rank"]<=3:trades.append(rec)
            for h in H:
                if by_h[h]:
                    avg=float(np.mean(by_h[h]))
                    daily_return[h].append(avg)
                    if d>TRAIN_END:daily_forward[h].append(avg)
        summary=[{"horizon":h,"top3Daily":stat(daily_return[h]),"postTrainTop3Daily":stat(daily_forward[h]),"rank1":stat(rank_returns[h][1]),"rank2":stat(rank_returns[h][2]),"rank3":stat(rank_returns[h][3]),"phasePortfolio":phase_portfolio(signals,dates,pos,ranktop,prices,meta,h)} for h in H]
        checks=[]
        for s in sorted(samples,key=lambda x:(x["date"],x.get("time",""),x["code"])):
            d=s["anchorDate"];code=s["code"];rank=rankmaps.get(d,{}).get(code);r=all_sample_rows.get((d,code))
            subset="train" if d<=TRAIN_END else "heldout"
            checks.append({"code":code,"name":r["name"] if r else None,"date":s["date"],"time":s.get("time"),"anchor":d,"rank":rank,"eligible":eligible(r) if r else False,"top3":bool(rank is not None and rank<=3),"top20":bool(rank is not None and rank<=20),"subset":subset,"baselineRank":base_rank.get(d,{}).get(code),"percentiles":{k:round(r[k],1) for k in FIELDS.values()} if r else None})
        def summarize(z):
            return {"n":len(z),"eligible":sum(x["eligible"] for x in z),"top20":sum(x["top20"] for x in z),"top3":sum(x["top3"] for x in z),"baselineTop20":sum(x["baselineRank"] is not None and x["baselineRank"]<=20 for x in z),"baselineTop3":sum(x["baselineRank"] is not None and x["baselineRank"]<=3 for x in z)}
        models[model]={"weights":{f:round(float(w),4) for f,w in zip(FEATURES,weights)},"fit":fit_early if model=="G_TARGET" else fit_all,"candidateStats":{"avg":round(float(np.mean(candidate_stats)),1),"min":min(candidate_stats),"max":max(candidate_stats),"days":len(candidate_stats)},"summary":summary,"sampleAudit":{"all":summarize(checks),"train":summarize([x for x in checks if x["subset"]=="train"]),"heldout":summarize([x for x in checks if x["subset"]=="heldout"]),"checks":checks},"signals":trades}
    # Research reference: contrasts versus eligible controls on the sample dates.
    keys=["ret20P","slopeP","atrP","range20P","turnoverP","ret5P","mom10P","range10P","rvol10P","positionP","dayP","emaSlopeP","v520P","breakoutPct","capitalB"]
    positive=[all_sample_rows.get((s["anchorDate"],s["code"])) for s in samples]
    positive=[x for x in positive if x is not None]
    peer=[x for d in targets for x in daily.get(d,[])]
    def median(a,k):return round(float(np.median([x[k] for x in a])),2) if a else None
    contrasts={k:{"targetMedian":median(positive,k),"peerMedian":median(peer,k)} for k in keys}
    out={"version":"G-TARGET-2026-V1","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),"period":{"start":start,"end":end},"trainingEnd":TRAIN_END,"labelsCount":len(samples),"historyErrors":len(errors),"signalDays":len(signals),"universeCount":len(meta),"candidateRule":{"priceMin":10,"ret20PMin":60,"slopePMin":70,"atrPMin":55,"range20PMin":65,"turnoverPMin":65,"breakoutMin":-25,"shareCapitalCeiling":None},"models":models,"featureContrast":contrasts,"notes":["G_TARGET 僅訓練2026/08/24～09/20發布的11筆，2026/10/02～10/08發布的9筆作為時間順序留出驗證。","G_TARGET_FULL20 用全部20筆建模，僅供樣本內貼合程度診斷，不代表可預測同批已知訊號。","所有日期的股票候選都只以當時已完整日K計算百分位；20筆發布訊號用發文日前最後完整交易日做命中稽核。","股票代碼只作事後核對及訓練標籤，模型評分絕不使用代碼或名稱、未來漲幅或發文後行情。","整年度2026報酬屬回顧性研究；因G_TARGET權重由2026/8～9的樣本學習，2026/1～9績效並非真正前瞻樣本外。","10/02～10/08留出訊號命中是日期前推的外部檢查，但僅9筆樣本，沒有證實穩健交易獲利。","不限制股本500億以保留2409友達訊號；股票池可能存在存活者偏差。","回測固定下一交易日開盤買進Top3、未實作個別突破價等待與風控。"]}
    p=DATA_DIR/"backtest_g";p.mkdir(parents=True,exist_ok=True);fn="target_2026.json"
    (p/fn).write_text(json.dumps(out,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    print(json.dumps({"period":out["period"],"historyErrors":out["historyErrors"],"models":{k:{"audit":v["sampleAudit"]["all"],"heldout":v["sampleAudit"]["heldout"],"10D":next(s["top3Daily"] for s in v["summary"] if s["horizon"]==10)} for k,v in models.items()},"elapsed":round(time.time()-began,1)},ensure_ascii=False),flush=True)
    return out
if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--start",default="2026-01-01");ap.add_argument("--end",default="2026-10-07");a=ap.parse_args();run(a.start,a.end)
