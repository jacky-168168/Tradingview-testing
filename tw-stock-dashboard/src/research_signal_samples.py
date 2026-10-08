from __future__ import annotations
import json,math
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR,MAX_CAPITAL_B,BENCHMARK
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import precompute_features

SAMPLES=[
{"date":"2026-10-08","time":"13:18","code":"3374","entry":498.5,"stop":471.5},
{"date":"2026-10-08","time":"09:41","code":"4903","entry":50.4,"stop":46.8,"invalidate":45.6},
{"date":"2026-10-08","time":"09:15","code":"8086","entry":151.0,"stop":140.0},
{"date":"2026-10-07","time":"12:27","code":"1569","entry":74.4,"stop":70.9},
{"date":"2026-10-05","time":"09:36","code":"2466","entry":151.0,"stop":141.0},
{"date":"2026-10-04","code":"3094","entry":72.5,"stop":67.7},
{"date":"2026-10-02","code":"2409","entry":41.35,"stop":38.70,"invalidate":28.0},
{"date":"2026-10-02","code":"6533","entry":345.0,"stop":323.0,"invalidate":285.0},
{"date":"2026-10-02","code":"6456","entry":89.3,"stop":82.5,"invalidate":69.0},
{"date":"2026-09-20","code":"3624","entry":137.0,"stop":133.5},
{"date":"2026-09-20","code":"8103","entry":131.0,"stop":124.0},
{"date":"2026-09-17","code":"6224","entry":91.0,"stop":82.0},
{"date":"2026-09-16","code":"2489","entry":43.15,"stop":41.65},
{"date":"2026-09-15","code":"3406","entry":973.0,"stop":875.0},
{"date":"2026-09-14","code":"3443","entry":6490.0,"stop":6330.0},
{"date":"2026-09-09","code":"3605","entry":128.5,"stop":114.0},
{"date":"2026-08-28","code":"8155","entry":364.5,"stop":357.0},
{"date":"2026-08-27","code":"3504","entry":93.3,"stop":91.2},
{"date":"2026-08-25","code":"3450","entry":527.0,"stop":516.0},
{"date":"2026-08-24","code":"1709","entry":34.65,"stop":33.95},
]

def num(v,d=None):
    try:
        x=float(v);return x if np.isfinite(x) else d
    except:return d

def pct(v,base):
    return (v/base-1)*100 if v is not None and base else None

def qtile(v,arr):
    a=np.array([x for x in arr if x is not None and np.isfinite(x)],dtype=float)
    if v is None or not np.isfinite(v) or not len(a):return None
    return round(float((a<=v).mean()*100),1)

def previous_completed_date(df,post_date):
    ds=sorted(str(x) for x in df["date"].astype(str).unique() if str(x)<post_date)
    return ds[-1] if ds else None

def row_at(ft,date):
    if ft is None or date not in ft.index:return None
    r=ft.loc[date];return r.iloc[-1] if isinstance(r,pd.DataFrame) else r

def main():
    universe=load_universe();by_code={x["code"]:x for x in universe}
    start=datetime(2026,2,1);end=datetime(2026,10,8)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],start,end)
    _,ix,ie=update_symbol(BENCHMARK,start,end)
    if ie or ix is None or ix.empty:raise RuntimeError(f"benchmark unavailable {ie}")
    ix=ix.sort_values("date").reset_index(drop=True);ixclose=dict(zip(ix.date.astype(str),pd.to_numeric(ix.close,errors="coerce")))
    feats={}
    for s in universe:
        sym=to_symbol(s["code"],s["market"]);df=hist.get(sym)
        if df is not None and len(df)>=60:feats[sym]=precompute_features(df).set_index("date",drop=False)
    sample_rows=[];all_anchor_dates={}
    for s in SAMPLES:
        meta=by_code.get(s["code"])
        if not meta:
            sample_rows.append({**s,"error":"code not in current universe"});continue
        sym=to_symbol(meta["code"],meta["market"]);df=hist.get(sym)
        if df is None or df.empty:
            sample_rows.append({**s,**meta,"error":"no history"});continue
        anchor=previous_completed_date(df,s["date"]);ft=feats.get(sym);r=row_at(ft,anchor) if anchor else None
        if r is None:
            sample_rows.append({**s,**meta,"anchorDate":anchor,"error":"no feature row"});continue
        q=df[df.date.astype(str)<=anchor].tail(80).copy()
        highs=pd.to_numeric(q.high,errors="coerce");lows=pd.to_numeric(q.low,errors="coerce");closes=pd.to_numeric(q.close,errors="coerce");vol=pd.to_numeric(q.volume,errors="coerce")
        prevclose=float(closes.iloc[-1]);market_anchor=anchor
        # benchmark return20 using latest available benchmark date <= anchor
        bix=ix[ix.date.astype(str)<=anchor].tail(21);mret20=(float(bix.close.iloc[-1])/float(bix.close.iloc[-21])-1)*100 if len(bix)>=21 else 0.0
        vals={
          "close":num(r.get("close")),"ret5":num(r.get("ret5")),"ret20":num(r.get("ret20")),"rs20":num(r.get("ret20"))-mret20,
          "rvol":num(r.get("rvol")),"rvol10":num(r.get("rvol10")),"mom10":num(r.get("mom10Pct")),"ma20Slope":num(r.get("ma20Slope")),
          "ema20Slope5":num(r.get("ema20Slope5")),"breakoutPct":num(r.get("breakoutPct")),"atrPct":num(r.get("atrPct")),"volD":num(r.get("volD")),
          "closePosition":num(r.get("closePosition")),"ema20":num(r.get("ema20")),"ema50":num(r.get("ema50")),"ma20":num(r.get("ma20")),"ma60":num(r.get("ma60")),
          "volume":num(r.get("volume")),"turnoverB":num(r.get("close"))*num(r.get("volume"),0)/100_000_000,
          "high5":float(highs.tail(5).max()),"high10":float(highs.tail(10).max()),"high20":float(highs.tail(20).max()),"high60":float(highs.tail(60).max()),
          "low5":float(lows.tail(5).min()),"low10":float(lows.tail(10).min()),"low20":float(lows.tail(20).min()),
          "range10Pct":(float(highs.tail(10).max())/float(lows.tail(10).min())-1)*100,
          "range20Pct":(float(highs.tail(20).max())/float(lows.tail(20).min())-1)*100,
          "vol5vs20":float(vol.tail(5).mean()/vol.tail(20).mean()) if float(vol.tail(20).mean()) else None,
        }
        out={**s,"name":meta["name"],"market":meta["market"],"industry":meta.get("industry"),"capitalB":meta.get("capitalB"),"anchorDate":anchor,**vals}
        out.update({
          "entryGapPrevClosePct":pct(s["entry"],prevclose),"entryVsHigh5Pct":pct(s["entry"],vals["high5"]),"entryVsHigh10Pct":pct(s["entry"],vals["high10"]),
          "entryVsHigh20Pct":pct(s["entry"],vals["high20"]),"entryVsHigh60Pct":pct(s["entry"],vals["high60"]),
          "riskPct":(s["entry"]-s["stop"])/s["entry"]*100,"riskATR":(s["entry"]-s["stop"])/(vals["atrPct"]/100*prevclose) if vals["atrPct"] and prevclose else None,
          "stopVsMA20Pct":pct(s["stop"],vals["ma20"]),"stopVsLow5Pct":pct(s["stop"],vals["low5"]),"stopVsLow10Pct":pct(s["stop"],vals["low10"]),
          "aboveEMA20":vals["close"]>vals["ema20"],"emaBull":vals["ema20"]>vals["ema50"],"aboveMA20":vals["close"]>vals["ma20"],"maBull":vals["ma20"]>vals["ma60"],
        })
        sample_rows.append(out);all_anchor_dates.setdefault(anchor,[]).append(out)
    # same-day universe percentiles, computed without future data
    percentile_keys=["ret5","ret20","rs20","rvol","rvol10","mom10","ma20Slope","ema20Slope5","breakoutPct","atrPct","volD","closePosition","turnoverB","range10Pct","range20Pct","vol5vs20"]
    universe_by_date={}
    for anchor in sorted(all_anchor_dates):
        bix=ix[ix.date.astype(str)<=anchor].tail(21);mret20=(float(bix.close.iloc[-1])/float(bix.close.iloc[-21])-1)*100 if len(bix)>=21 else 0.0
        rows=[]
        for meta in universe:
            if not (0<num(meta.get("capitalB"),0)<MAX_CAPITAL_B):continue
            sym=to_symbol(meta["code"],meta["market"]);ft=feats.get(sym);rr=row_at(ft,anchor)
            if rr is None or pd.isna(rr.get("ret20")):continue
            df=hist.get(sym);q=df[df.date.astype(str)<=anchor].tail(20) if df is not None else pd.DataFrame()
            if len(q)<10:continue
            highs=pd.to_numeric(q.high,errors="coerce");lows=pd.to_numeric(q.low,errors="coerce");vol=pd.to_numeric(q.volume,errors="coerce")
            close=num(rr.get("close"));volume=num(rr.get("volume"),0)
            rows.append({
              "ret5":num(rr.get("ret5")),"ret20":num(rr.get("ret20")),"rs20":num(rr.get("ret20"))-mret20,"rvol":num(rr.get("rvol")),"rvol10":num(rr.get("rvol10")),
              "mom10":num(rr.get("mom10Pct")),"ma20Slope":num(rr.get("ma20Slope")),"ema20Slope5":num(rr.get("ema20Slope5")),"breakoutPct":num(rr.get("breakoutPct")),
              "atrPct":num(rr.get("atrPct")),"volD":num(rr.get("volD")),"closePosition":num(rr.get("closePosition")),"turnoverB":close*volume/100_000_000,
              "range10Pct":(float(highs.tail(10).max())/float(lows.tail(10).min())-1)*100 if float(lows.tail(10).min()) else None,
              "range20Pct":(float(highs.max())/float(lows.min())-1)*100 if float(lows.min()) else None,
              "vol5vs20":float(vol.tail(5).mean()/vol.tail(20).mean()) if float(vol.tail(20).mean()) else None,
            })
        universe_by_date[anchor]=rows
    for s in sample_rows:
        if s.get("error") or not s.get("anchorDate"):continue
        u=universe_by_date.get(s["anchorDate"],[])
        for k in percentile_keys:s[k+"Pctile"]=qtile(s.get(k),[x.get(k) for x in u])
    valid=[x for x in sample_rows if not x.get("error")]
    def summary(k):
        a=np.array([num(x.get(k),np.nan) for x in valid],dtype=float);a=a[np.isfinite(a)]
        return None if not len(a) else {"n":len(a),"min":round(float(np.min(a)),3),"p25":round(float(np.percentile(a,25)),3),"median":round(float(np.median(a)),3),"p75":round(float(np.percentile(a,75)),3),"max":round(float(np.max(a)),3),"mean":round(float(np.mean(a)),3)}
    summary_keys=["riskPct","riskATR","entryGapPrevClosePct","entryVsHigh5Pct","entryVsHigh10Pct","entryVsHigh20Pct","entryVsHigh60Pct","ret5","ret20","rs20","rvol","rvol10","mom10","ma20Slope","ema20Slope5","breakoutPct","atrPct","volD","closePosition","turnoverB","range10Pct","range20Pct","vol5vs20","rs20Pctile","ret20Pctile","ma20SlopePctile","breakoutPctPctile","turnoverBPctile"]
    bools={k:round(sum(bool(x.get(k)) for x in valid)/len(valid)*100,1) for k in ["aboveEMA20","emaBull","aboveMA20","maBull"]} if valid else {}
    out={"generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),"method":"Use previous completed trading day for every intraday/weekend post to avoid look-ahead.","samples":sample_rows,"summary":{k:summary(k) for k in summary_keys},"booleanCoveragePct":bools,"historyErrors":errors}
    p=DATA_DIR/"research";p.mkdir(parents=True,exist_ok=True);(p/"signal_samples_2026.json").write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding="utf-8")
    pd.DataFrame(sample_rows).to_csv(p/"signal_samples_2026.csv",index=False,encoding="utf-8-sig")
    print(json.dumps({"valid":len(valid),"summary":out["summary"],"booleanCoveragePct":bools},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
