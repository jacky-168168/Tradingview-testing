"""Independently reconcile 2025 official TAIFEX annual ZIP vs historical paired TX night dataset.
Official date label for after-market D is next trading date T. Read-only.
"""
import csv,io,requests,zipfile,collections
from pathlib import Path
U="https://www.taifex.com.tw/cht/3/futDataDown"
PAIRED=Path(__file__).resolve().parents[1]/"docs/data/research/tx_night_regime_3y/paired_nights.csv"
def report():
    r=requests.post(U,data={"down_type":"2","his_year":"2025"},timeout=115,
        headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.taifex.com.tw/cht/3/futDailyMarketView"})
    print("OFFICIAL_STATUS",r.status_code,"BYTES",len(r.content),flush=True);r.raise_for_status()
    if not zipfile.is_zipfile(io.BytesIO(r.content)):raise RuntimeError("Official annual download is not ZIP")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        items=[n for n in z.namelist() if n.endswith(".csv")]
        if items!=["2025_fut.csv"]:raise RuntimeError("Unexpected annual archive members "+str(items))
        market={}
        with z.open(items[0]) as binary,io.TextIOWrapper(binary,encoding="big5",newline="") as f:
            for row in csv.DictReader(f):
                if row.get("契約")!="TX":continue
                session=row.get("交易時段")
                if session=="一般":typ="day"
                elif session=="盤後":typ="night"
                else:continue
                month=(row.get("到期月份(週別)") or "").strip()
                d=(row.get("交易日期") or "").replace("/","-")
                close=row.get("收盤價");vol=row.get("成交量")
                try:c=float(close);v=float(vol)
                except (TypeError,ValueError):continue
                if len(d)!=10 or len(month)!=6 or c<=0 or v<=0:continue
                key=(d,typ,month)
                if key not in market or v>market[key][1]:market[key]=(c,v)
    print("OFFICIAL_TX_ROWS",len(market),flush=True)
    records=list(csv.DictReader(PAIRED.open(encoding="utf-8-sig",newline="")))
    examples=[];fail=[];both=0;dayonly=0
    for p in records:
        if p["decisionDate"][:4]!="2025":continue
        kday=(p["cashDate"],"day",p["contract"])
        knight=(p["decisionDate"],"night",p["contract"])
        official_day=market.get(kday);official_night=market.get(knight)
        if not official_day or not official_night:
            if official_night and not official_day and p["cashDate"][:4]=="2024":dayonly+=1
            else:fail.append({"date":p["decisionDate"],"error":"missing_official_pair","day":bool(official_day),"night":bool(official_night)})
            continue
        both+=1
        diff_day=float(p["txDay"])-official_day[0]
        diff_night=float(p["txNight"])-official_night[0]
        if abs(diff_day)>.51 or abs(diff_night)>.51:fail.append({"date":p["decisionDate"],"month":p["contract"],"dayDelta":diff_day,"nightDelta":diff_night})
        if len(examples)<6:examples.append({"date":p["decisionDate"],"month":p["contract"],"finDay":p["txDay"],"officialDay":official_day[0],"finNight":p["txNight"],"officialNight":official_night[0]})
    print("PAIRS_2025",sum(p["decisionDate"][:4]=="2025" for p in records),"FULL_PAIRS_COMPARED",both,"CROSS_YEAR_EXCLUDED",dayonly,flush=True)
    print("SAMPLES",examples,flush=True);print("OFFICIAL_MISMATCH_COUNT",len(fail),"EXAMPLES",fail[:12],flush=True)
    if both<200:raise RuntimeError("Insufficient official-year sample to verify TX report")
    if fail:raise RuntimeError("TX source does not fully match official 2025 data")
    print("PASS: dated 2025 official daytime AND after-hours TX prices agree with 3-year FinMind historical pairs",flush=True)
if __name__=="__main__":report()
