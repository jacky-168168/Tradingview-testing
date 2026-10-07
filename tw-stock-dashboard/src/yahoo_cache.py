from __future__ import annotations
import time
from datetime import datetime,timedelta,timezone
from concurrent.futures import ThreadPoolExecutor,as_completed
import pandas as pd
import requests
from config import HISTORY_DIR,YAHOO_CHART,REQUEST_TIMEOUT,YAHOO_WORKERS

UA={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/1.0"}

def to_symbol(code:str,market:str)->str:
    return f"{code}.TW" if market=="上市" else f"{code}.TWO"

def _fetch(symbol:str,start:datetime,end:datetime,retries:int=3)->pd.DataFrame:
    p1=int(start.replace(tzinfo=timezone.utc).timestamp()); p2=int((end+timedelta(days=2)).replace(tzinfo=timezone.utc).timestamp())
    params={"period1":p1,"period2":p2,"interval":"1d","events":"history","includeAdjustedClose":"true"}
    err=None
    for attempt in range(retries):
        try:
            r=requests.get(YAHOO_CHART.format(symbol=symbol),params=params,headers=UA,timeout=REQUEST_TIMEOUT); r.raise_for_status()
            result=(r.json().get("chart") or {}).get("result") or []
            if not result:return pd.DataFrame()
            x=result[0]; ts=x.get("timestamp") or []; q=((x.get("indicators") or {}).get("quote") or [{}])[0]
            rows=[]
            for i,t in enumerate(ts):
                vals={k:(q.get(k) or [None]*len(ts))[i] if i<len(q.get(k) or []) else None for k in ["open","high","low","close","volume"]}
                if vals["close"] is None:continue
                rows.append({"date":datetime.fromtimestamp(t,timezone.utc).date().isoformat(),**vals})
            return pd.DataFrame(rows)
        except Exception as e:
            err=e; time.sleep(1.5*(attempt+1))
    raise RuntimeError(f"Yahoo {symbol} failed: {err}")

def load_cached(symbol:str)->pd.DataFrame:
    p=HISTORY_DIR/f"{symbol}.parquet"
    if not p.exists():return pd.DataFrame()
    try:return pd.read_parquet(p)
    except Exception:return pd.DataFrame()

def update_symbol(symbol:str,start:datetime,end:datetime):
    HISTORY_DIR.mkdir(parents=True,exist_ok=True); old=load_cached(symbol); fetch_start=start
    if not old.empty:
        last=pd.to_datetime(old["date"]).max().date(); fetch_start=max(start,datetime.combine(last+timedelta(days=1),datetime.min.time()))
    try:
        fresh=_fetch(symbol,fetch_start,end) if fetch_start.date()<=end.date() else pd.DataFrame()
        if old.empty:merged=fresh
        elif fresh.empty:merged=old
        else:merged=pd.concat([old,fresh],ignore_index=True).drop_duplicates("date",keep="last").sort_values("date")
        if not merged.empty:merged.to_parquet(HISTORY_DIR/f"{symbol}.parquet",index=False)
        return symbol,merged,None
    except Exception as e:return symbol,old,str(e)

def update_many(items,start,end):
    out={}; errors={}
    with ThreadPoolExecutor(max_workers=YAHOO_WORKERS) as ex:
        fut={ex.submit(update_symbol,to_symbol(code,market),start,end):(code,market) for code,market in items}
        for f in as_completed(fut):
            symbol,df,err=f.result(); out[symbol]=df
            if err:errors[symbol]=err
    return out,errors
