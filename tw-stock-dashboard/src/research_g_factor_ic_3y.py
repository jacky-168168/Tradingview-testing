"""Read-only QuantDinger-style G factor RankIC, daily quintiles, ablations and 2026 OOS."""
from __future__ import annotations
import collections,json,math,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import BENCHMARK,DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from research_g_regime_3y import START,END,COST,calc_g,stock_ret,get_risk,finite
from g_persistence import persistence_features
OUT=DATA_DIR/"research"/"g_factor_ic_3y"
FOLDS={"train":(START,"2024-12-31"),"validation":("2025-01-01","2025-12-31"),"holdout":("2026-01-01",END)}
H=(5,10,20)
FACTORS=("ret20P","slopeP","atrP","range20P","turnoverP","breakoutPct","past10Top20","score")
WEIGHTS={"ret20P":.30,"slopeP":.25,"atrP":.10,"range20P":.15,"turnoverP":.15}
def boot_ci(pairs,seed=20261011):
    blocks=collections.defaultdict(list)
    for d,x in pairs:
        if x is not None and math.isfinite(float(x)):blocks[d[:7]].append(float(x))
    if len(blocks)<4:return None
    values=np.array([np.mean(x) for x in blocks.values()])
    rng=np.random.default_rng(seed)
    z=values[rng.integers(0,len(values),(400,len(values)))].mean(axis=1)
    return [round(float(np.quantile(z,k)),5) for k in (.025,.975)]
def valid_for_fold(d,ex,fold):
    lo,hi=FOLDS[fold];return lo<=d<=hi and ex is not None and ex<=hi
def reconstruct(dates,index,universe,hist):
    daymap={d:(year,i) for year in sorted({d[:4] for d in index.date.astype(str)})
        for i,d in enumerate(k for k in index.date.astype(str) if k[:4]==year)}
    frames=[];prices={}
    for n,s in enumerate(universe,1):
        symbol=to_symbol(s["code"],s["market"]);h=hist.get(symbol)
        if h is None or h.empty:continue
        q=calc_g(h,s,daymap)
        if q is None:continue
        frames.append(q[["date","code","sym","close","ret20","ma20Slope","atrPct","range20Pct","turnoverB","breakoutPct","cap","break3","break18"]])
        prices[symbol]=q.set_index("date",drop=False)[["date","open","close","adjOpen","adjClose","volume"]]
        if n%400==0:print("G_FACTOR_STOCK_SCAN",n,len(universe),flush=True)
    if not frames:raise RuntimeError("No historical price data")
    p=pd.concat(frames,ignore_index=True)
    p=p[(p.date>=START)&(p.date<=END)].replace([np.inf,-np.inf],np.nan)
    p=p.dropna(subset=["close","ret20","ma20Slope","atrPct","range20Pct","turnoverB","breakoutPct"])
    p=p[(p.close>0)&(p.turnoverB>0)].copy()
    for raw,out in (("ret20","ret20P"),("ma20Slope","slopeP"),("atrPct","atrP"),("range20Pct","range20P"),("turnoverB","turnoverP")):
        p[out]=p.groupby("date")[raw].rank(method="average",pct=True)*100
    eligible=(p.close>=10)&(p.cap>0)&(p.ret20P>=60)&(p.slopeP>=70)&(p.atrP>=55)&(p.range20P>=65)&(p.turnoverP>=65)&(p.breakoutPct>=-25)&p.break3&p.break18
    p=p[eligible].copy()
    p["near"]=np.clip(100+p.breakoutPct/18*100,0,100)
    p["base"]=(30*p.ret20P+25*p.slopeP+10*p.atrP+15*p.range20P+15*p.turnoverP+5*p.near)/100
    p.sort_values(["date","base","code"],ascending=[True,False,True],inplace=True)
    g={d:z for d,z in p.groupby("date",sort=False)}
    recent=collections.deque(maxlen=10);year=None;groups={};picks={}
    for d in dates:
        if d[:4]!=year:recent.clear();year=d[:4]
        rows=g.get(d)
        if rows is None:recent.append({});continue
        rows=rows.copy()
        history=list(recent)
        history_features=[persistence_features(str(code),history,round(float(base),4)) for code,base in zip(rows.code,rows.base)]
        rows["past10Top20"]=[v["past10Top20"] for v in history_features]
        rows["bonus"]=[v["bonus"] for v in history_features]
        rows["score"]=[round(round(float(base),4)+float(bonus),4) for base,bonus in zip(rows.base,rows.bonus)]
        rows.sort_values(["score","base","code"],ascending=[False,False,True],inplace=True)
        groups[d]=rows;picks[d]=rows.head(3).code.astype(str).tolist()
        baseline=g[d].head(20)
        recent.append({str(code):{"rank":i+1,"score":round(float(base),4)} for i,(code,base) in enumerate(zip(baseline.code,baseline.base))})
    return groups,picks,prices,{"dailyFeatureRows":len(p),"validGSignalDays":len(groups),"top3StockSignals":sum(len(v) for v in picks.values()),"symbols":len(prices)}
def assert_g_parity(picks,audit):
    folder=DATA_DIR/"research"/"g_regime_3y"
    ref=json.loads((folder/"summary.json").read_text(encoding="utf-8"))
    for name in ("dailyFeatureRows","validGSignalDays"):
        if audit[name]!=ref["audit"][name]:raise RuntimeError(f"G parity {name}: {audit[name]} != {ref['audit'][name]}")
    trades=json.loads((folder/"trades.json").read_text(encoding="utf-8"))
    base=next((x for x in trades["models"] if x["model"]=="SPOT_0" and x["horizon"]==5),None)
    if base is None:raise RuntimeError("Original G baseline missing")
    checked=0
    for item in base["trades"]:
        if item["codes"]!=picks.get(item["date"]):raise RuntimeError("G selection parity mismatch on "+item["date"])
        checked+=1
    if checked<500:raise RuntimeError("G parity sample insufficient")
    return checked
def add_forward_returns(groups,dates,prices):
    idx={d:i for i,d in enumerate(dates)}
    stats=collections.Counter()
    for d,df in groups.items():
        i=idx[d];df.attrs["exits"]={}
        for h in H:
            buy=dates[i+1] if i+1<len(dates) else None
            ex=dates[i+h] if i+h<len(dates) else None
            df.attrs["exits"][h]=ex
            vals=[]
            for sym in df.sym:
                if buy is None or ex is None:vals.append(np.nan);continue
                raw=stock_ret(prices,{"sym":sym},buy,ex)
                if raw is None:stats[f"h{h}_missing"]+=1;vals.append(np.nan);continue
                vals.append((1+raw)*(1-COST)-1);stats[f"h{h}_ok"]+=1
            df[f"net{h}"]=vals
    return dict(stats)
def factor_report(groups,feat,h,fold,risk,gate):
    ic=[];diff=[];Q={i:[] for i in range(1,6)};stocks=0
    for d,df in groups.items():
        if not valid_for_fold(d,df.attrs["exits"][h],fold) or (gate and risk[d]<gate):continue
        sample=df[[feat,f"net{h}"]].replace([np.inf,-np.inf],np.nan).dropna()
        if len(sample)<10 or sample[feat].nunique()<3 or sample[f"net{h}"].nunique()<3:continue
        r=float(sample[feat].corr(sample[f"net{h}"],method="spearman"))
        if not math.isfinite(r):continue
        ic.append((d,r));stocks+=len(sample)
        ranks=np.ceil(sample[feat].rank(pct=True,method="average")*5).clip(1,5).astype(int)
        means=sample.groupby(ranks)[f"net{h}"].mean()
        if len(means)!=5:continue
        for k in Q:Q[k].append(float(means[k]))
        diff.append((d,float(means[5]-means[1])))
    ci=boot_ci(ic);qci=boot_ci(diff,20261012)
    e="insufficient" if len(ic)<25 or ci is None else "positive" if ci[0]>0 else "negative" if ci[1]<0 else "inconclusive"
    return {"factor":feat,"daysIC":len(ic),"stockSignalsIC":stocks,"rankIC":round(float(np.mean([v for _,v in ic])),5) if ic else None,
      "rankICCI95":ci,"icPositiveRatePct":round(100*sum(v>0 for _,v in ic)/len(ic),2) if ic else None,"evidence":e,
      "daysQuintiles":len(diff),"QMeanNetPct":{str(k):round(np.mean(v)*100,4) if v else None for k,v in Q.items()},
      "Q5MinusQ1NetPct":round(float(np.mean([v for _,v in diff]))*100,4) if diff else None,
      "Q5MinusQ1CI95Pct":[round(100*x,4) for x in qci] if qci else None}
def ablate(groups,feat,h,fold,risk,gate):
    daily=[];changed=0;nr=0
    for d,df in groups.items():
        if not valid_for_fold(d,df.attrs["exits"][h],fold) or (gate and risk[d]<gate):continue
        original=df.head(3)
        if len(original)<3 or original[f"net{h}"].isna().any():continue
        if feat=="past10Top20":newscore=df.score-df.bonus
        elif feat=="breakoutPct":newscore=df.score-5*df.near/100
        else:newscore=df.score-WEIGHTS[feat]*df[feat]
        modified=df.assign(no=newscore).sort_values(["no","base","code"],ascending=[False,False,True]).head(3)
        if len(modified)<3 or modified[f"net{h}"].isna().any():continue
        daily.append((d,float(modified[f"net{h}"].mean()-original[f"net{h}"].mean())))
        changed+=list(original.code)!=list(modified.code);nr+=1
    values=[v for _,v in daily];ci=boot_ci(daily)
    return {"removed":feat,"matchedDays":nr,"modifiedMinusOriginalNetPct":round(float(np.mean(values))*100,4) if values else None,
      "deltaCI95Pct":[round(100*x,4) for x in ci] if ci else None,"differentTop3Pct":round(changed/max(1,nr)*100,2)}
def build_report(r):
    lines=["# G 強勢股因子 Rank IC 與樣本外檢驗","","資料：2023/10/09–2026/10/08，728 個交易日；**原 G_DOUBLE_PERSIST 規則未更動**。","","2023–24 訓練、2025 驗證、2026 完全獨立稽核；只依 D 日收盤特徵選股，D+1 開盤進場，D+H 收盤出場。持有期間不得越過分段終點。個股淨報酬扣手續費及交易稅共 0.585%。","","**注意：每天重疊選股的平均報酬不是可直接投入全部本金的複利報酬。** 現存公司名單與實收資本額存在歷史存活者偏差；未檢定無完整歷史資料的法人、ROE、PB。","","## 2026 樣本外 G 合格池｜每日橫斷面 Rank IC","","| 因子 | 5D IC | 10D IC | 20D IC | 10D Q5−Q1 淨報酬百分點 | 10D 日數 |","|---|---:|---:|---:|---:|---:|"]
    for f in FACTORS:
        k={h:next(x for x in r["factors"]["gate0"]["holdout"][str(h)] if x["factor"]==f) for h in H}
        def fmt(v):return "—" if v is None else f"{v:+.4f}"
        lines.append(f"| {f} | {fmt(k[5]['rankIC'])} | {fmt(k[10]['rankIC'])} | {fmt(k[20]['rankIC'])} | {fmt(k[10]['Q5MinusQ1NetPct'])} | {k[10]['daysIC']} |")
    lines+=["","## 2026 樣本外 G Top3｜移除權重的配對平均淨報酬差異","","正值表示移除該因子權重的 Top3 表現較好，但不代表應立即刪掉。","","| 移除項目 | 5D 差異pp | 10D 差異pp | 20D 差異pp | 10D 配對日數 |","|---|---:|---:|---:|---:|"]
    for f in (*WEIGHTS,"breakoutPct","past10Top20"):
        k={h:next(x for x in r["ablations"]["gate0"]["holdout"][str(h)] if x["removed"]==f) for h in H}
        def fmt(v):return "—" if v is None else f"{v:+.4f}"
        lines.append(f"| {f} | {fmt(k[5]['modifiedMinusOriginalNetPct'])} | {fmt(k[10]['modifiedMinusOriginalNetPct'])} | {fmt(k[20]['modifiedMinusOriginalNetPct'])} | {k[10]['matchedDays']} |")
    lines+=["","## 解讀守則","","- IC 為每日橫斷面 Spearman 排名相關，門檻每日至少 10 檔且因子有變異；只解讀 G 合格池的邊際差異。","- Q5−Q1 每日分五組的平均淨報酬差，不代表可交易的多空策略。","- 95% 區間用月區塊 Bootstrap 近似，重複股票、重疊持有期間的相依性仍會降低有效樣本。","- 2026 不用於選擇權重。歷史股票池為當前成分股，未完全消除存活者偏差。","- Risk≥60 的分層檢定和完整 train/validation/holdout 結果請見 summary.json。","","## 品質稽核","",str(r["inputAudit"]),str(r["GParity"]),str(r["forwardCoverage"])]
    return "\n".join(lines)+"\n"
def main():
    start=time.time();now=datetime.now(ZoneInfo("Asia/Taipei"))
    if END>now.date().isoformat():raise RuntimeError("Refuse future dataset")
    universe=[s for s in load_universe() if finite(s.get("capitalB")) and float(s["capitalB"])>0]
    lo=datetime.fromisoformat(START)-timedelta(days=430);hi=datetime.fromisoformat(END)+timedelta(days=35)
    hist,errors=update_many([(s["code"],s["market"]) for s in universe],lo,hi)
    if errors:raise RuntimeError("Incomplete stock histories "+str(len(errors))+" "+str(list(errors.items())[:3]))
    _,index,err=update_symbol(BENCHMARK,lo,hi)
    if err or index is None or index.empty:raise RuntimeError("Missing ^TWII calendar")
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    # The verified official TWSE archive is the canonical signal-day calendar.
    # Yahoo ^TWII can omit or delay recent sessions: never interpolate them.
    official=json.loads((DATA_DIR/"research"/"g_regime_3y"/"market_risk_daily.json").read_text(encoding="utf-8"))
    dates=[str(z["date"]) for z in official]
    if len(dates)!=728 or dates[0]<START or dates[-1]!=END or len(set(dates))!=728:
        raise RuntimeError("Historical verified 728-session archive invalid")
    observed=set(index.date.astype(str));missing=[d for d in dates if d not in observed]
    extra=[d for d in observed if START<=d<=END and d not in set(dates)]
    print("YAHOO_VS_OFFICIAL_TWII_CALENDAR",{"observedDays":sum(START<=d<=END for d in observed),
        "officialDays":len(dates),"missing":missing[:15],"extra":extra[:15]},flush=True)
    prefix=index[index.date.astype(str)<START][["date","close"]]
    index=pd.concat([prefix,pd.DataFrame([{"date":z["date"],"close":z["index"]} for z in official])],ignore_index=True)
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    risk,_=get_risk(index,dates)
    grouped,picks,prices,info=reconstruct(dates,index,universe,hist)
    parity=assert_g_parity(picks,info)
    coverage=add_forward_returns(grouped,dates,prices)
    r={"version":"G_FACTOR_2023_26_QUANTDINGER_AUDIT_V1","generatedAt":now.isoformat(),"period":[START,END],"folds":FOLDS,"horizons":H,
      "inputAudit":{"universeNow":len(universe),"stockDataErrors":len(errors),**info},"GParity":{"passed":True,"comparedHistoricalSignalDays":parity},
      "forwardCoverage":coverage,"transactionCostPct":100*COST,
      "method":"G conditional cross-sectional Spearman IC, within-day quintile return, 400 month-block bootstrap and matched Top3 ablation; forward next-open to Hth-close net return.",
      "factors":{},"ablations":{},"limitations":["Current survivor universe and capital are not historical point-in-time.","No historical complete foreign/trust or financial statements; untested.","Daily overlapping signals are correlated; compounded portfolio return not estimated."]}
    for gate in (0,60):
        key=f"gate{gate}";r["factors"][key]={};r["ablations"][key]={}
        for fold in FOLDS:
            r["factors"][key][fold]={};r["ablations"][key][fold]={}
            for h in H:
                r["factors"][key][fold][str(h)]=[factor_report(grouped,f,h,fold,risk,gate) for f in FACTORS]
                r["ablations"][key][fold][str(h)]=[ablate(grouped,f,h,fold,risk,gate) for f in (*WEIGHTS,"breakoutPct","past10Top20")]
            print("G_FACTOR_SPLIT",key,fold,flush=True)
    r["elapsedSeconds"]=round(time.time()-start,2)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding="utf-8")
    (OUT/"report.md").write_text(build_report(r),encoding="utf-8")
    print("G_FACTOR_AUDIT_DONE",json.dumps({"audited":info,"parity":parity,"coverage":coverage,"elapsed":r["elapsedSeconds"]},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
