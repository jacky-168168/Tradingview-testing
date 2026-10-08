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

def fetch_day(date,retries=3):
    DIR.mkdir(parents=True,exist_ok=True); p=DIR/f"{date}.json"
    if p.exists():
        try:
            x=json.loads(p.read_text(encoding="utf-8"))
            if x:return date,x,None
        except:pass
    url=f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date.replace('-','')}&selectType=ALLBUT0999&response=json"; err=None
    for n in range(retries):
        try:
            res=requests.get(url,headers=UA,timeout=REQUEST_TIMEOUT);res.raise_for_status(); m=parse_twse(res.json())
            if m:p.write_text(json.dumps(m,ensure_ascii=False),encoding="utf-8");return date,m,None
        except Exception as e:err=e
        time.sleep(1+n)
    return date,{},str(err or "empty T86")

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
