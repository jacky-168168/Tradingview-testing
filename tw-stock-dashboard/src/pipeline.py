from __future__ import annotations
import json,sys
from datetime import datetime,timedelta
import requests
from config import *
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import calc_metrics,score_a,score_d,d_pass,sort_key

HEADERS={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/1.0","Accept":"application/json"}

def _pick(row,*keys,default=""):
    for k in keys:
        if k in row and row[k] not in (None,""):return row[k]
    return default

def _capital_b(v):
    try:
        x=float(str(v).replace(",","")); return x/100_000_000 if x>1_000_000 else x
    except Exception:return 0.0

def _normalize_company(row,market):
    code=str(_pick(row,"公司代號","SecuritiesCompanyCode","Code","股票代號","公司代碼")).strip()
    if not(len(code)==4 and code.isdigit()):return None
    return {"code":code,"name":str(_pick(row,"公司簡稱","CompanyName","公司名稱","Name",default=code)).strip(),"market":market,
            "capitalB":_capital_b(_pick(row,"實收資本額","PaidInCapital","實收資本額(元)",default=0)),
            "industry":str(_pick(row,"產業別","Industry","產業類別",default="未分類"))}

def fetch_json(url):
    r=requests.get(url,headers=HEADERS,timeout=25); r.raise_for_status(); return r.json()

def load_universe():
    CACHE_DIR.mkdir(parents=True,exist_ok=True); rows=[]
    try:
        for x in fetch_json(TWSE_COMPANY_URL):
            z=_normalize_company(x,"上市")
            if z:rows.append(z)
    except Exception as e:print("TWSE universe failed",e,file=sys.stderr)
    otc=[]
    for url in TPEX_COMPANY_URLS:
        try:
            for x in fetch_json(url):
                z=_normalize_company(x,"上櫃")
                if z:otc.append(z)
            if len(otc)>500:break
        except Exception as e:print("TPEx universe source failed",url,e,file=sys.stderr)
    rows.extend(otc)
    if len(rows)<1000 and UNIVERSE_CACHE.exists():return json.loads(UNIVERSE_CACHE.read_text(encoding="utf-8"))
    rows=list({f'{x["market"]}_{x["code"]}':x for x in rows}.values())
    UNIVERSE_CACHE.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8"); return rows

def benchmark_ret20(end):
    start=end-timedelta(days=120); _,df,err=update_symbol(BENCHMARK,start,end)
    if err or df is None or len(df)<21:return 0.0
    c=df["close"].astype(float); return (float(c.iloc[-1])/float(c.iloc[-21])-1)*100

def main():
    now=datetime.now(); start=now-timedelta(days=LOOKBACK_CALENDAR_DAYS); universe=load_universe()
    eligible=[x for x in universe if x.get("capitalB",0)<=0 or x["capitalB"]<MAX_CAPITAL_B]
    histories,errors=update_many([(x["code"],x["market"]) for x in eligible],start,now); mkt20=benchmark_ret20(now); a=[]; d=[]
    for s in eligible:
        h=histories.get(to_symbol(s["code"],s["market"])); m=calc_metrics(h) if h is not None and not h.empty else None
        if not m or m["close"]<MIN_PRICE:continue
        rs20=m["ret20"]-mkt20; turnover_b=m["close"]*m["volume"]/100_000_000
        base={**s,"close":m["close"],"dayRet":m["dayRet"],"ret5":m["ret5"],"ret20":m["ret20"],"rs20":rs20,"rvol":m["rvol"],"rvol10":m["rvol10"],"mom10Pct":m["mom10Pct"],"volD":m["volD"],"atrPct":m["atrPct"],"breakoutPct":m["breakoutPct"],"ma20Slope":m["ma20Slope"],"turnoverB":turnover_b}
        if turnover_b*100>=MIN_TURNOVER_M:a.append({**base,**score_a(m,rs20,None),"model":"A"})
        if d_pass(m):d.append({**base,**score_d(m,rs20,None),"model":"D"})
    a=sorted(a,key=sort_key)[:TOP_N]; d=sorted(d,key=sort_key)[:TOP_N]
    payload={"generatedAt":now.isoformat(timespec="seconds"),"benchmarkRet20":round(mkt20,4),"universeCount":len(eligible),
             "historyOk":len(histories)-len(errors),"historyErrors":len(errors),"models":{"A":a,"D":d},"phase":"github-python-v1",
             "notes":["A/D核心技術評分已移植；法人、Risk、Top Watch、題材與完整回測將於下一階段移植。"]}
    DATA_DIR.mkdir(parents=True,exist_ok=True); LATEST_JSON.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({k:payload[k] for k in ["generatedAt","universeCount","historyOk","historyErrors"]},ensure_ascii=False))
if __name__=="__main__":main()
