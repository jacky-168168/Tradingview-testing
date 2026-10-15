from __future__ import annotations
import json,time
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
from config import CACHE_DIR,REQUEST_TIMEOUT

DIR=CACHE_DIR/"institution"; UA={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/2.0","Accept":"application/json"}

def _num(v):
    try:return float(str(v).replace(",","").replace("--","0").strip() or 0)
    except:return 0.0

def _field(fields,names):
    # Deliberately mirrors GAS findFieldIndex_: scan fields first, substring match.
    # This preserves V12.2 historical scoring parity (including its dealer-column behavior).
    for i,f in enumerate(fields):
        s=str(f).replace(" ","")
        for n in names:
            if str(n).replace(" ","") in s:return i
    return -1

def parse_twse(j):
    out={}
    if not j or not isinstance(j.get("data"),list):return out
    f=j.get("fields") or []; ci=_field(f,["證券代號"]); fi=_field(f,["外陸資買賣超股數","外資及陸資買賣超股數","外資及陸資買賣超"]); ti=_field(f,["投信買賣超股數","投信買賣超"]); di=_field(f,["自營商買賣超股數","自營商買賣超"])
    for row in j["data"]:
        code=str(row[ci if ci>=0 else 0]).strip()
        if len(code)!=4 or not code.isdigit():continue
        foreign=_num(row[fi]) if fi>=0 else 0; trust=_num(row[ti]) if ti>=0 else 0; dealer=_num(row[di]) if di>=0 else 0
        out[f"上市_{code}"]={"foreign":foreign,"trust":trust,"dealer":dealer,"total":foreign+trust+dealer}
    return out

# The current TPEx endpoint (the old 3itrade_hedge_result.php retired in 2025).
TPEX_FLOW_URL="https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade"

def parse_tpex(j,date):
    """Parse TPEx official per-stock Daily 24-column rows; units are SHARES."""
    if not isinstance(j,dict):return {}
    tables=j.get("tables") or []
    if not isinstance(tables,list) or not tables:return {}
    table=tables[0]
    if not isinstance(table,dict):return {}
    y,m,d=map(int,date.split("-"));roc=f"{y-1911:03d}/{m:02d}/{d:02d}"
    reported=str(table.get("date") or j.get("date") or "").strip()
    # Reject data not explicitly dated to the requested session; never show yesterday as today.
    if reported not in (roc,date,date.replace("-","/")):return {}
    rows=table.get("data") or []
    if not isinstance(rows,list):return {}
    out={}
    for row in rows:
        if not isinstance(row,list) or len(row)<24:continue
        code=str(row[0]).strip().strip("=").strip('"')
        if len(code)!=4 or not code.isdigit() or code.startswith("0"):continue
        try:
            def strict_num(x):
                v=str(x).strip().replace(",","").replace("−","-").replace("－","-")
                if not v or v in ("--","—","-"):raise ValueError("missing institutional flow")
                return float(v)
            foreign=strict_num(row[10]);trust=strict_num(row[13]);dealer=strict_num(row[22]);total=strict_num(row[23])
            # Financial integrity: drop partial/corrupt rows rather than inventing a zero.
            if abs(foreign+trust+dealer-total)>0.01:continue
        except (ValueError,TypeError):continue
        out[f"上櫃_{code}"]={"foreign":foreign,"trust":trust,"dealer":dealer,"total":total}
    return out

def fetch_day(date,retries=3):
    DIR.mkdir(parents=True,exist_ok=True);p=DIR/f"{date}.json";cached={}
    if p.exists():
        try:
            x=json.loads(p.read_text(encoding="utf-8"))
            if isinstance(x,dict):cached=x
        except (OSError,ValueError):pass
    listed={k:v for k,v in cached.items() if k.startswith("上市_")}
    otc={k:v for k,v in cached.items() if k.startswith("上櫃_")}
    errors=[]
    # Old caches contained only TWSE; keep them and backfill TPEx without re-fetching TWSE.
    if not listed:
        url=f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date.replace('-','')}&selectType=ALLBUT0999&response=json"
        last="empty T86"
        for n in range(retries):
            try:
                res=requests.get(url,headers=UA,timeout=REQUEST_TIMEOUT);res.raise_for_status()
                listed=parse_twse(res.json())
                if listed:break
            except Exception as e:last=str(e)
            if n+1<retries:time.sleep(1+n)
        if not listed:errors.append("TWSE: "+last)
    if not otc:
        y,m,d=map(int,date.split("-"));roc=f"{y-1911:03d}/{m:02d}/{d:02d}"
        params={"type":"Daily","sect":"EW","date":roc,"id":"","response":"json"}
        last="empty, wrong-date or incomplete TPEx report"
        for n in range(retries):
            try:
                res=requests.get(TPEX_FLOW_URL,params=params,headers=UA,timeout=REQUEST_TIMEOUT);res.raise_for_status()
                data=parse_tpex(res.json(),date)
                # A few rows is a truncated official report, not a successful market snapshot.
                if len(data)>=200:otc=data;break
            except Exception as e:last=str(e)
            if n+1<retries:time.sleep(1+n)
        if not otc:errors.append("TPEx: "+last)
    merged={**listed,**otc}
    if merged and merged!=cached:p.write_text(json.dumps(merged,ensure_ascii=False),encoding="utf-8")
    return date,merged,"; ".join(errors) if errors else None

def fetch_many(dates,workers=4):
    out={};errors={}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fut={ex.submit(fetch_day,d):d for d in dates}
        for f in as_completed(fut):
            d,m,e=f.result();out[d]=m
            if e:errors[d]=e
    # TWSE 偶爾會對平行請求限流；失敗日期改用低速序列重試，避免把 missing 當成 0。
    if errors:
        for d in list(errors):
            time.sleep(.35)
            dd,m,e=fetch_day(d,retries=5);out[dd]=m
            if e:errors[d]=e
            else:errors.pop(d,None)
    return out,errors
