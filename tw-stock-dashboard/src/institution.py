from __future__ import annotations
import json,time,math
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
    # A changed official schema cannot silently convert unknown foreign/trust flows to zero.
    if ci<0 or fi<0 or ti<0:return out
    for row in j["data"]:
        try:
            code=str(row[ci]).strip()
            if len(code)!=4 or not code.isdigit():continue
            def flow_num(v):
                v=str(v).strip().replace(",","").replace("−","-").replace("－","-")
                if v in ("","--","—","-"):raise ValueError("missing cash flow")
                n=float(v)
                if not math.isfinite(n):raise ValueError("nonfinite cash flow")
                return n
            foreign=flow_num(row[fi]);trust=flow_num(row[ti]);dealer=_num(row[di]) if di>=0 else 0
        except (IndexError,TypeError,ValueError):continue
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
            if not all(math.isfinite(n) for n in (foreign,trust,dealer,total)) or abs(foreign+trust+dealer-total)>0.01:continue
        except (ValueError,TypeError):continue
        out[f"上櫃_{code}"]={"foreign":foreign,"trust":trust,"dealer":dealer,"total":total}
    return out

def coverage_ratio(rows,expected_keys,market):
    keys={k for k in (expected_keys or set()) if k.startswith(market+"_")}
    if not keys:return 1.0
    return len(keys.intersection(rows))/len(keys)

def fetch_day(date,retries=3,expected_keys=None,force_refresh=False):
    """Fetch date-matched TWSE + TPEx. Incomplete caches are NEVER silently accepted."""
    DIR.mkdir(parents=True,exist_ok=True);p=DIR/f"{date}.json";cached={}
    if p.exists():
        try:
            x=json.loads(p.read_text(encoding="utf-8"))
            if isinstance(x,dict):cached=x
        except (OSError,ValueError):pass
    listed={k:v for k,v in cached.items() if k.startswith("上市_")}
    otc={k:v for k,v in cached.items() if k.startswith("上櫃_")}
    expected=set(expected_keys) if expected_keys is not None else None
    errors=[]
    def adequate(rows,market,floor):
        if len(rows)<floor:return False
        return expected is None or coverage_ratio(rows,expected,market)>=0.80
    if force_refresh or not adequate(listed,"上市",1):
        url=f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date.replace('-','')}&selectType=ALLBUT0999&response=json"
        last="empty, wrong-date or incomplete TWSE T86"
        for n in range(retries):
            try:
                res=requests.get(url,headers=UA,timeout=REQUEST_TIMEOUT);res.raise_for_status();payload=res.json()
                reported=str(payload.get("date") or "").strip()
                if reported and reported not in (date,date.replace("-",""),date.replace("-","/"),f"{int(date[:4])-1911:03d}/{date[5:7]}/{date[8:10]}",f"{int(date[:4])-1911:03d}{date[5:7]}{date[8:10]}"):
                    last="TWSE response date mismatch: "+reported
                else:
                    fresh=parse_twse(payload)
                    if adequate(fresh,"上市",1):
                        listed=fresh;break
            except Exception as e:last=str(e)
            if n+1<retries:time.sleep(1+n)
        if not adequate(listed,"上市",1):errors.append("TWSE: "+last)
    if force_refresh or not adequate(otc,"上櫃",200):
        y,m,d=map(int,date.split("-"));roc=f"{y-1911:03d}/{m:02d}/{d:02d}"
        params={"type":"Daily","sect":"EW","date":roc,"id":"","response":"json"}
        last="empty, wrong-date or incomplete TPEx report"
        for n in range(retries):
            try:
                res=requests.get(TPEX_FLOW_URL,params=params,headers=UA,timeout=REQUEST_TIMEOUT);res.raise_for_status()
                fresh=parse_tpex(res.json(),date)
                if adequate(fresh,"上櫃",200):
                    otc=fresh;break
            except Exception as e:last=str(e)
            if n+1<retries:time.sleep(1+n)
        if not adequate(otc,"上櫃",200):errors.append("TPEx: "+last)
    merged={**listed,**otc}
    # Persist only complete responses; do not poison future runs with truncated data.
    if not errors and merged and merged!=cached:p.write_text(json.dumps(merged,ensure_ascii=False),encoding="utf-8")
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
