from __future__ import annotations
import json,sys
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import requests
from config import *
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import calc_metrics,score_a,score_d,d_pass,sort_key
from institution import fetch_day
from risk import build as build_risk
from sar import apply as apply_sar
from industry_chain import enrich as enrich_chain
from panels import institution_flow,topic_heat

HEADERS={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/3.0","Accept":"application/json"}

def _pick(row,*keys,default=""):
    for k in keys:
        if k in row and row[k] not in (None,""):return row[k]
    return default

def _capital_b(v):
    try:
        x=float(str(v).replace(",",""));return x/100_000_000 if x>1_000_000 else x
    except:return 0.0

def _normalize_company(row,market):
    code=str(_pick(row,"公司代號","SecuritiesCompanyCode","Code","股票代號","公司代碼")).strip()
    if not(len(code)==4 and code.isdigit()):return None
    return {"code":code,"name":str(_pick(row,"公司簡稱","CompanyName","公司名稱","Name",default=code)).strip(),"market":market,
            "capitalB":_capital_b(_pick(row,"實收資本額","PaidInCapital","實收資本額(元)",default=0)),
            "industry":str(_pick(row,"產業別","Industry","產業類別",default="未分類"))}

def fetch_json(url):
    r=requests.get(url,headers=HEADERS,timeout=25);r.raise_for_status();return r.json()

def load_universe():
    CACHE_DIR.mkdir(parents=True,exist_ok=True);rows=[]
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
    UNIVERSE_CACHE.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8");return rows

def _risk_signal(row,risk):
    m=row["model"];score=row["total"]
    if m=="D":sig="🔥 D強勢" if score>=80 else "✅ D觀察" if score>=65 else "👀 D候選"
    else:sig="🔥 強勢" if score>=85 else "✅ 觀察" if score>=75 else "👀 備選" if score>=65 else "一般"
    return ("⚠ Risk非ON "+sig) if risk.get("score",0)<RISK_ON else sig

def _base_sort_a(r):return (-r["baseScore"],-r["rs20"],-r["rvol"],-r["ret20"],-r["turnoverB"])
def _final_sort_a(r):return (-r["total"],-r.get("sarBonus",0),-r["rs20"],-r["rvol"],-r["ret20"],-r["turnoverB"])
def _final_sort_d(r):return sort_key(r)

def main():
    now=datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None);start=now-timedelta(days=LOOKBACK_CALENDAR_DAYS);universe=load_universe()
    eligible=[x for x in universe if 0<x.get("capitalB",0)<MAX_CAPITAL_B]
    histories,errors=update_many([(x["code"],x["market"]) for x in eligible],start,now)
    _,idx,idxerr=update_symbol(BENCHMARK,start,now)
    if idxerr or idx is None or len(idx)<25:raise RuntimeError(f"benchmark unavailable: {idxerr}")
    market_date=str(idx.iloc[-1]["date"]);risk=build_risk(idx,RISK_ON,RISK_STRONG,RISK_OFF);mkt20=float(risk.get("ret20",0) or 0)
    _,inst,insterr=fetch_day(market_date);names={f'{x["market"]}_{x["code"]}':x["name"] for x in universe}
    a=[];d=[]
    for s in eligible:
        h=histories.get(to_symbol(s["code"],s["market"]));m=calc_metrics(h.tail(75)) if h is not None and len(h)>=60 else None
        if not m or m["close"]<MIN_PRICE:continue
        rs20=m["ret20"]-mkt20;turnover_b=m["close"]*m["volume"]/100_000_000;ii=inst.get(f'{s["market"]}_{s["code"]}',{})
        base={**s,"close":m["close"],"dayRet":m["dayRet"],"ret5":m["ret5"],"ret20":m["ret20"],"marketRet20":mkt20,"rs20":rs20,"rvol":m["rvol"],"rvol10":m["rvol10"],"mom10Pct":m["mom10Pct"],"volD":m["volD"],"atrPct":m["atrPct"],"breakoutPct":m["breakoutPct"],"ma20Slope":m["ma20Slope"],"turnoverB":turnover_b,
              "foreignToday":round(float(ii.get("foreign",0) or 0)/1000,1),"trustToday":round(float(ii.get("trust",0) or 0)/1000,1)}
        if turnover_b*100>=MIN_TURNOVER_M:
            z=score_a(m,rs20,ii);a.append({**base,**z,"baseScore":z["total"],"model":"A","sarBonus":0,"sarText":"讀取中"})
        if d_pass(m):
            z=score_d(m,rs20,ii);d.append({**base,**z,"baseScore":z["total"],"model":"D","sarBonus":0,"sarText":"讀取中"})
    a.sort(key=_base_sort_a);d.sort(key=sort_key)
    candidate_counts={"A":len(a),"D":len(d)}
    apply_sar(a,market_date,min(len(a),max(TOP_N*2,SAR_CANDIDATES)));apply_sar(d,market_date,min(len(d),max(TOP_N*2,SAR_CANDIDATES)))
    for x in a+d:x["signal"]=_risk_signal(x,risk)
    a=sorted(a,key=_final_sort_a)[:TOP_N];d=sorted(d,key=_final_sort_d)[:TOP_N]
    enrich_chain(a);enrich_chain(d)
    flow=institution_flow(inst,names);heat=topic_heat(market_date)
    payload={"generatedAt":now.isoformat(timespec="seconds"),"dataDate":market_date,"benchmarkRet20":round(mkt20,4),"universeCount":len(eligible),
             "historyOk":len(histories)-len(errors),"historyErrors":len(errors),"models":{"A":a,"D":d},"risk":risk,
             "panels":{"institutionFlow":flow,"topicHeat":heat,"institutionSource":"TWSE T86／上櫃暫為0","topicSource":heat[0]["source"] if heat else "暫無題材資料"},
             "candidateCounts":candidate_counts,"phase":"github-python-v5","notes":["Phase 5：A/D、Risk、Top/Bottom Watch、官方SAR、法人、題材與產業鏈已接入。","SAR改用TWSE/TPEx官方未還原日K，避免除權息/分割造成Yahoo調整價差異。","上櫃法人仍依V12.2口徑暫時視為0分。"]}
    DATA_DIR.mkdir(parents=True,exist_ok=True);LATEST_JSON.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"generatedAt":payload["generatedAt"],"dataDate":market_date,"universeCount":len(eligible),"A":len(a),"D":len(d),"risk":risk.get("score"),"historyErrors":len(errors),"institutionError":insterr},ensure_ascii=False))
if __name__=="__main__":main()
