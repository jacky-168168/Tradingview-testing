"""Reconstruct PRIOR G_DOUBLE_PERSIST daily Top20 on dated market candles.

These are *research reconstructions*, NEVER claimed to be genuinely frozen daily
snapshots. Exact original daily percentages/3D+18D breakout/past-ten-pocket
logic are replayed chronologically. Present-day listed universe/capital,
revised Yahoo OHLC and absent historical official SAR/institutional tape
prevent claiming original publication parity.

Pipeline creates docs/data/research/g_history_reconstruction_2m/history.json.
No existing docs/data/daily/ files are modified or fabricated.
"""
from __future__ import annotations
import argparse,collections,json,math,time
from datetime import date,datetime,timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import BENCHMARK,DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from research_g_regime_3y import calc_g,finite
from g_live import g_score
from g_persistence import persistence_features
from g_target import eligible
from repeated_rankings import months_before

OUT=DATA_DIR/"research"/"g_history_reconstruction_2m"
VERSION="G_LIVE_DOUBLE_PERSIST_HISTORICAL_RECONSTRUCTION_V1"
INDICATORS=("ret20","ma20Slope","atrPct","range20Pct","turnoverB")
PERCENTILES=("ret20P","slopeP","atrP","range20P","turnoverP")
TOP=20

def historical_panel(hist,universe,calendar,year,cutoff):
    daymap={d:(d[:4],i) for i,d in enumerate(calendar) if d[:4]==year and d<=cutoff}
    frames=[];failed=collections.Counter();symbols=0
    for number,s in enumerate(universe,1):
        sy=to_symbol(s["code"],s["market"]);h=hist.get(sy)
        if h is None or h.empty:failed["missingStockHistory"]+=1;continue
        q=h[h.date.astype(str)<=cutoff].copy()
        if len(q)<60:failed["lessThan60Bars"]+=1;continue
        try:
            z=calc_g(q,s,daymap)
            if z is None:failed["calcG"]+=1;continue
            z=z[(z.date>=year+"-01-01")&(z.date<=cutoff)]
            if z.empty:continue
            z["ret5"]=(q.set_index("date").close/q.set_index("date").close.shift(5)-1).reindex(z.date).to_numpy()*100
            z["rvol"]=(q.set_index("date").volume/q.set_index("date").volume.shift(1).rolling(20).mean()).reindex(z.date).to_numpy()
            z["theme"]=str(s.get("industry") or "")
            z["capitalB"]=float(s.get("capitalB") or 0)
            frames.append(z[["date","code","name","market","close","ret5","ret20",
                "ma20Slope","atrPct","range20Pct","turnoverB","breakoutPct","cap",
                "break3","break18","rvol","theme","capitalB"]])
            symbols+=1
        except Exception as ex:
            failed[type(ex).__name__]+=1
        if number%400==0:
            print("G_BACKFILL_STOCK_HISTORY",number,"/",len(universe),
                "good",symbols,"errs",sum(failed.values()),flush=True)
    if not frames:raise RuntimeError("No valid as-of-G features; historical backfill refused")
    p=pd.concat(frames,ignore_index=True)
    p=p.replace([np.inf,-np.inf],np.nan).dropna(subset=[
        "close","ret20","ma20Slope","atrPct","range20Pct",
        "turnoverB","breakoutPct","cap","ret5"])
    p=p[(p.close>0)&(p.turnoverB>0)].copy()
    for k,pr in zip(INDICATORS,PERCENTILES):
        p[pr]=p.groupby("date")[k].rank(method="average",pct=True)*100
    qualified=(p.close>=10)&(p.cap>0)&(p.ret20P>=60)&(p.slopeP>=70)&(p.atrP>=55)&(p.range20P>=65)&(p.turnoverP>=65)&(p.breakoutPct>=-25)
    p["eligible"]=qualified
    p=p[qualified&p.break3.fillna(False)&p.break18.fillna(False)].copy()
    # Verify identical g_live.g_score, not similar rounded proxy:
    p["baselineScore"]=[g_score(x) for x in p.to_dict("records")]
    return p,dict(failed),symbols

def reconstruct(calendar,panel,start,cutoff,index):
    all_dates=[d for d in calendar if start[:4]==d[:4] and d<=cutoff]
    if not all_dates or cutoff not in all_dates:raise RuntimeError("Market calendar not aligned to latest published session")
    close=pd.to_numeric(index.close,errors="coerce")
    ret20=(close/close.shift(20)-1)*100
    mret={d:float(v) for d,v in zip(index.date.astype(str),ret20) if finite(v) is not None}
    groups={d:z.to_dict("records") for d,z in panel.groupby("date",sort=False)}
    result={};window=collections.deque(maxlen=10);per_day_stats={}
    for day in all_dates:
        dayrows=groups.get(day,[])
        dayrows.sort(key=lambda r:(-r["baselineScore"],str(r["code"])))
        baseline={str(z["code"]):{"rank":i+1,"score":float(z["baselineScore"])}
                  for i,z in enumerate(dayrows[:TOP])}
        ranked=[]
        for stock in dayrows:
            ps=persistence_features(str(stock["code"]),list(window),float(stock["baselineScore"]))
            total=round(float(stock["baselineScore"])+ps["bonus"],4)
            row={
                "code":str(stock["code"]),"name":stock["name"],"market":stock["market"],
                "theme":stock.get("theme") or "","close":round(float(stock["close"]),4),
                "capitalB":round(float(stock["capitalB"]),3),
                "turnoverB":round(float(stock["turnoverB"]),4),
                "total":total,"gScore":round(float(stock["baselineScore"]),4),
                "gExtra":ps["bonus"],"gPast10":ps["past10Top20"],
                "gStreak":ps["priorStreak"],"persistence":ps,
                "gBreak3":True,"gBreak18":True,
                "ret5":round(float(stock["ret5"]),4),
                "ret20":round(float(stock["ret20"]),4),
                "ma20Slope":round(float(stock["ma20Slope"]),4),
                "rs20":round(float(stock["ret20"])-mret.get(day,0),4) if day in mret else None,
                "rvol":round(float(stock["rvol"]),4) if finite(stock["rvol"]) is not None else None,
                "sarText":"歷史SAR未驗證",
                "foreignToday":None,"trustToday":None,
                "signal":"🔥 G雙突破持續強勢" if ps["past10Top20"]>=4
                      else "🚀 G雙突破開始轉強" if ps["past10Top20"]>=1
                      else "🆕 G雙突破新入選",
                "model":"G",
                "dataOrigin":"retrospectively_reconstructed_not_historical_snapshot",
            }
            ranked.append(row)
        ranked.sort(key=lambda x:(-x["total"],-x["gScore"],x["code"]))
        window.append(baseline)
        if day>=start:
            top=ranked[:TOP]
            result[day]={"dataDate":day,"model":"G","source":"reconstructed",
                "stocks":top,"doubleBreakCandidates":len(dayrows),
                "marketUniverseCandidates":len(dayrows)}
            per_day_stats[day]={"topCount":len(top),"qualified":len(dayrows)}
        if len(result)%12==0 and day>=start:
            print("G_BACKFILL_DAY",day,"total",len(result),
                  "topG",len(result[day]["stocks"]),flush=True)
    return result,per_day_stats

def compare_real_archive(rebuilt,actual,reference):
    official=(actual.get("models") or {}).get("G")
    if not isinstance(official,list):return {"status":"original_snapshot_unavailable","reason":"not a list"}
    proposed=rebuilt[reference]["stocks"]
    old_codes=[(str(r.get("market")),str(r.get("code"))) for r in official]
    new_codes=[(str(r.get("market")),str(r.get("code"))) for r in proposed]
    overlap=set(old_codes)&set(new_codes)
    head_overlap=set(old_codes[:3])&set(new_codes[:3])
    report={"status":"compared","officialTop20":len(old_codes),"rebuiltTop20":len(new_codes),
        "intersection":len(overlap),"top3Intersection":len(head_overlap),
        "identicalOrder":old_codes==new_codes,
        "originalTopCodes":[code for _,code in old_codes],
        "rebuiltTopCodes":[code for _,code in new_codes],
        "missingFromRebuild":[code for market,code in old_codes if (market,code) not in overlap],
        "rankDifference":[{"code":code,"originalRank":old_codes.index((market,code))+1,
            "rebuiltRank":new_codes.index((market,code))+1}
            for market,code in old_codes if (market,code) in overlap]}
    return report

def main():
    began=time.monotonic();OUT.mkdir(parents=True,exist_ok=True)
    lastfile=DATA_DIR/"latest.json";daily=DATA_DIR/"daily"
    if not lastfile.exists():raise RuntimeError("Verified current G snapshot not present")
    live=json.loads(lastfile.read_text(encoding="utf-8"))
    cutoff=str(live.get("dataDate") or "")
    if not cutoff or not (daily/(cutoff+".json")).exists():
        raise RuntimeError("Latest trading day and archived original daily snapshot not aligned")
    real=json.loads((daily/(cutoff+".json")).read_text(encoding="utf-8"))
    if real.get("dataDate")!=cutoff or not isinstance((real.get("models") or {}).get("G"),list):
        raise RuntimeError("No real frozen G reference day to audit exact-date overlap")
    start=months_before(cutoff)
    if start[:4]!=cutoff[:4]:raise RuntimeError("This collector needs one calendar-year start for G 3D/18D anchoring")
    universe=[x for x in load_universe() if finite(x.get("capitalB")) and float(x["capitalB"])>0]
    begin=datetime.fromisoformat(cutoff[:4]+"-01-01")-timedelta(days=210)
    end=datetime.fromisoformat(cutoff)+timedelta(days=2)
    hist,errors=update_many([(x["code"],x["market"]) for x in universe],begin,end)
    _,index,indexerr=update_symbol(BENCHMARK,begin,end)
    if indexerr or index is None or index.empty:raise RuntimeError("Cannot retrieve historical TWII exchange calendar: "+str(indexerr))
    index=index.sort_values("date").drop_duplicates("date").reset_index(drop=True)
    dates=[d for d in index.date.astype(str) if d[:4]==cutoff[:4] and d<=cutoff]
    if len([d for d in dates if d>=start])<35:raise RuntimeError("Trading history incomplete for rolling two months")
    if len(dates)<120:raise RuntimeError("No 10-day G warmup/calendar window")
    print("G_BACKFILL_MARKET",start,cutoff,"calendarDays",len(dates),
          "stocks",len(universe),"stockFetchErrors",len(errors),flush=True)
    panel,excluded,valid_symbols=historical_panel(hist,universe,dates,cutoff[:4],cutoff)
    if valid_symbols<1200:raise RuntimeError("Insufficient market breadth for time-travel reconstruction "+str(valid_symbols))
    rebuilt,day_stats=reconstruct(dates,panel,start,cutoff,index)
    parity=compare_real_archive(rebuilt,real,cutoff)
    print("G_BACKFILL_OFFICIAL_PARITY",json.dumps(parity,ensure_ascii=False),flush=True)
    if parity["status"]!="compared" or parity["intersection"]<12 or parity["top3Intersection"]<1:
        raise RuntimeError("Reconstructed G 10/08 has insufficient overlap with actual frozen default G; refuse publication.")
    coverage={
        "version":VERSION,"windowStart":start,"referenceDate":cutoff,
        "generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),
        "backfilledTradeDays":len(rebuilt),"currentUniverse":len(universe),
        "validSymbolPriceSeries":valid_symbols,"downloadErrors":len(errors),
        "featureExclusions":excluded,"GParityAgainstRealFrozenReference":parity,
        "dataProvenance":"Historical Yahoo OHLC + current TWSE/TPEx listed universe. Not actual historic published Top20.",
        "modelRule":"Exact g_live.g_score / g_target.eligible / 3D+18D prior complete annual calendar high / pre-10 original G pocket persistence",
        "limitations":[
            "RECONSTRUCTED RESEARCH ONLY: output is NOT the watchlist actually published on each past date.",
            "Survivorship bias: today's still-listed stock universe and paid-in capital, not point-in-time delisted securities.",
            "Historical Yahoo OHLC can be retrospectively adjusted or revised; original live exchange source may differ.",
            "Missing issuer-specific foreign and trust historic trade tape; null, never fabricated zero.",
            "Official unadjusted historical SAR series has not been independently validated for the retrospective universe; label explicitly unavailable, not invented.",
            "Current industry/stock names may differ from past dates; thematic membership is not point-in-time verified.",
            "Parity with latest archived G Top20 is reported. Exact same ranks cannot be promised from different vintages.",
            "Model itself is not reoptimized on future data; daily cross section uses past price features only."
        ]}
    output={"version":VERSION,"windowStart":start,"referenceDate":cutoff,
        "generatedAt":coverage["generatedAt"],"model":"G","source":"historical_reconstruction",
        "dateCount":len(rebuilt),"days":rebuilt,"audit":coverage}
    (OUT/"history.json").write_text(json.dumps(output,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    (OUT/"coverage.json").write_text(json.dumps(coverage,ensure_ascii=False,indent=2),encoding="utf-8")
    print("G_BACKFILL_COMPLETE",json.dumps({"start":start,"end":cutoff,
        "days":len(rebuilt),"stocks":valid_symbols,"parityIntersection":parity["intersection"],
        "top3Overlap":parity["top3Intersection"],"totalSeconds":round(time.monotonic()-began)},ensure_ascii=False),flush=True)

if __name__=="__main__":main()
