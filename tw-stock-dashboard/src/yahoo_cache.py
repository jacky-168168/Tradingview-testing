from __future__ import annotations
import time
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd,requests
from config import HISTORY_DIR,YAHOO_CHART,REQUEST_TIMEOUT,YAHOO_WORKERS
UA={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/2.0"}

def to_symbol(code,market):return f"{code}.TW" if market=="上市" else f"{code}.TWO"

def _fetch(symbol,start,end,retries=3):
    now_utc=datetime.now(timezone.utc).replace(tzinfo=None)
    if start>now_utc:return pd.DataFrame()
    end=min(end,now_utc)
    if start.date()>end.date():return pd.DataFrame()
    p1=int(start.replace(tzinfo=timezone.utc).timestamp());p2=int((end+timedelta(days=2)).replace(tzinfo=timezone.utc).timestamp());err=None
    for n in range(retries):
        try:
            r=requests.get(YAHOO_CHART.format(symbol=symbol),params={"period1":p1,"period2":p2,"interval":"1d","events":"history","includeAdjustedClose":"true"},headers=UA,timeout=REQUEST_TIMEOUT);r.raise_for_status()
            z=((r.json().get("chart") or {}).get("result") or [None])[0]
            if not z:return pd.DataFrame()
            ts=z.get("timestamp") or [];q=((z.get("indicators") or {}).get("quote") or [{}])[0];rows=[]
            for i,t in enumerate(ts):
                vals={k:(q.get(k) or [None]*len(ts))[i] if i<len(q.get(k) or []) else None for k in ["open","high","low","close","volume"]}
                if any(vals[k] is None for k in vals):continue
                rows.append({"date":datetime.fromtimestamp(t,timezone.utc).date().isoformat(),**vals})
            return pd.DataFrame(rows)
        except Exception as e:err=e;time.sleep(1.5*(n+1))
    raise RuntimeError(f"Yahoo {symbol} failed: {err}")

def load_cached(symbol):
    p=HISTORY_DIR/f"{symbol}.parquet"
    if not p.exists():return pd.DataFrame()
    try:return pd.read_parquet(p).sort_values("date").drop_duplicates("date",keep="last")
    except:return pd.DataFrame()

def update_symbol(symbol,start,end):
    HISTORY_DIR.mkdir(parents=True,exist_ok=True);old=load_cached(symbol);parts=[old] if not old.empty else []
    try:
        if old.empty:parts.append(_fetch(symbol,start,end))
        else:
            first=pd.to_datetime(old.date).min().date();last=pd.to_datetime(old.date).max().date()
            if start.date()<first:parts.append(_fetch(symbol,start,datetime.combine(first-timedelta(days=1),datetime.min.time())))
            if end.date()>last:parts.append(_fetch(symbol,datetime.combine(last+timedelta(days=1),datetime.min.time()),end))
        good=[p for p in parts if p is not None and not p.empty];merged=pd.concat(good,ignore_index=True) if good else pd.DataFrame()
        if not merged.empty:
            merged=merged.drop_duplicates("date",keep="last").sort_values("date").reset_index(drop=True);merged.to_parquet(HISTORY_DIR/f"{symbol}.parquet",index=False)
        return symbol,merged,None
    except Exception as e:return symbol,old,str(e)

def update_many(items,start,end):
    out={};errors={}
    with ThreadPoolExecutor(max_workers=YAHOO_WORKERS) as ex:
        fut={ex.submit(update_symbol,to_symbol(c,m),start,end):(c,m) for c,m in items}
        for f in as_completed(fut):
            s,df,e=f.result();out[s]=df
            if e:errors[s]=e
    return out,errors
