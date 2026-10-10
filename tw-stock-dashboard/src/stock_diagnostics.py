"""全市場個股量化體檢：使用自有 TWSE/TPEx 股票池與既有日 K，不擷取 FinLab 資料。"""
import json,math
from pathlib import Path
import pandas as pd

def _num(v):
    try:
        n=float(v)
        return round(n,4) if math.isfinite(n) else None
    except (TypeError,ValueError):return None

def _ret(close,n):
    if len(close)<n+1:return None
    base=_num(close.iloc[-n-1]);end=_num(close.iloc[-1])
    return round(100*(end/base-1),4) if base is not None and base>0 and end is not None else None

def _percentiles(rows,key,output,invert=False):
    values=sorted(float(x[key]) for x in rows if x.get(key) is not None and math.isfinite(float(x[key])))
    if not values:return
    from bisect import bisect_left,bisect_right
    for x in rows:
        v=x.get(key)
        if v is None:continue
        lo=bisect_left(values,float(v));hi=bisect_right(values,float(v))
        pct=100*(lo+hi)/(2*len(values))
        x[output]=round(100-pct if invert else pct,1)

def build_snapshot(universe,histories,market_date,benchmark_ret20,inst=None,models=None,generated_at=None):
    """僅統計截至 market_date 已完整收盤的股票，缺少財報與法人資料保留 null。"""
    inst=inst or {};models=models or {}
    memberships={}
    for model,stocks in models.items():
        for s in stocks:memberships.setdefault(str(s.get("code")),set()).add(model)
    rows=[]
    for s in universe:
        code=str(s.get("code") or "");market=s.get("market")
        if not code or market not in ("上市","上櫃"):continue
        symbol=code+(".TW" if market=="上市" else ".TWO")
        h=histories.get(symbol)
        if h is None or len(h)<21:continue
        h=h.sort_values("date")
        if str(h.iloc[-1]["date"])[:10]!=str(market_date):continue
        close=pd.to_numeric(h["close"],errors="coerce")
        volume=pd.to_numeric(h["volume"],errors="coerce") if "volume" in h else pd.Series(dtype=float)
        price=_num(close.iloc[-1]);r20=_ret(close,20)
        if price is None or price<=0 or r20 is None:continue
        r5=_ret(close,5);r60=_ret(close,60);r120=_ret(close,120);r240=_ret(close,240)
        prev20=volume.iloc[-21:-1] if len(volume)>=21 else pd.Series(dtype=float)
        rv=float(prev20.median()) if not prev20.empty else 0
        volratio=_num(volume.iloc[-1]/rv) if rv>0 else None
        daily=close.pct_change(fill_method=None).iloc[-20:].dropna()
        vol20=_num(float(daily.std())*math.sqrt(252)*100) if len(daily)>=15 else None
        highs=pd.to_numeric(h["high"],errors="coerce") if "high" in h else close
        hi120=_num(highs.iloc[-120:].max()) if len(highs)>=120 else None
        hi252=_num(highs.iloc[-252:].max()) if len(highs)>=252 else None
        k=market+"_"+code;ii=inst.get(k,{})
        has_inst=market=="上市" and bool(ii)
        foreign=_num(float(ii.get("foreign",0))/1000) if has_inst else None
        trust=_num(float(ii.get("trust",0))/1000) if has_inst else None
        cap=_num(s.get("capitalB"))
        turnover=_num(price*float(volume.iloc[-1])/100_000_000) if len(volume) and pd.notna(volume.iloc[-1]) else None
        rows.append({"code":code,"name":s.get("name") or code,"market":market,"industry":s.get("industry") or "未分類",
            "close":price,"ret5":r5,"ret20":r20,"ret60":r60,"ret120":r120,"ret240":r240,
            "rs20":_num(r20-float(benchmark_ret20 or 0)),"rvol20":volratio,"volatility20":vol20,
            "high120":hi120,"high252":hi252,"distanceHigh120":_num((price/hi120-1)*100) if hi120 and hi120>0 else None,
            "capitalB":cap,"turnoverB":turnover,"foreignToday":foreign,"trustToday":trust,
            "models":sorted(memberships.get(code,set()))})
    for key,out,inv in [("ret20","momentum20P",False),("ret60","momentum60P",False),("rs20","rs20P",False),
                        ("volatility20","lowVolP",True),("turnoverB","liquidityP",False)]:
        _percentiles(rows,key,out,inv)
    for row in rows:
        ps=[row.get("momentum20P"),row.get("momentum60P"),row.get("rs20P")]
        usable=[p for p in ps if p is not None]
        row["momentumScore"]=round(sum(usable)/len(usable),1) if usable else None
        row["signals"]=[name for name,active in [
            ("20日正報酬",row["ret20"] is not None and row["ret20"]>0),
            ("相對大盤走強",row["rs20"] is not None and row["rs20"]>0),
            ("120日高點5%內",row["distanceHigh120"] is not None and row["distanceHigh120"]>=-5),
            ("相對量>1.5",row["rvol20"] is not None and row["rvol20"]>1.5),
            ("外資當日買超",row["foreignToday"] is not None and row["foreignToday"]>0)
        ] if active]
    rows.sort(key=lambda x:(-(x["momentumScore"] if x["momentumScore"] is not None else -1),x["code"]))
    return {"schema":"stock-diagnostics-v1","dataDate":str(market_date),"generatedAt":generated_at,
            "source":"自建 TWSE/TPEx 股票池、既有 Yahoo 日K 快取、TWSE T86（限有取得者）",
            "coverage":{"universe":len(universe),"withValidDailyK":len(rows),"financialsIncluded":False,"signalWinRateIncluded":False},
            "method":{"momentumScore":"20D、60D 與 RS20 的全市場百分位等權平均（有缺值則以可得值平均）；非原選股 A/D/F/G 分數。",
                      "lowVolP":"近20日年化歷史波動率反向全市場百分位；高分代表相對低波動。",
                      "signals":"觀察條件的當日布林標記；沒有對應歷史勝率檢定，不可誤認為經回測訊號。",
                      "caveat":"只有已完成日K；資料及歷史期間不足的欄位為 null，並非零。未納入財報 ROE/EPS、本益比與 FinLab 專有資料。"},
            "stocks":rows}

def write_snapshot(data_dir,universe,histories,market_date,benchmark_ret20,inst=None,models=None,generated_at=None):
    payload=build_snapshot(universe,histories,market_date,benchmark_ret20,inst,models,generated_at)
    out=Path(data_dir)/"stocks";out.mkdir(parents=True,exist_ok=True)
    path=out/"latest.json";path.write_text(json.dumps(payload,ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    return payload
