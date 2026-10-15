"""Independent official annual TAIFEX archive reconciliation vs dated risk research.
Official after-hours quote trading date is the FOLLOWING regular cash session.
Read-only: never backfill missing pairs, modify Risk Score, or claim trading P&L.
"""
import csv,io,requests,zipfile
from pathlib import Path
U="https://www.taifex.com.tw/cht/3/futDataDown"
PAIRED=Path(__file__).resolve().parents[1]/"docs/data/research/tx_night_regime_3y/paired_nights.csv"
def official(year):
    r=requests.post(U,data={"down_type":"2","his_year":str(year)},timeout=115,
        headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.taifex.com.tw/cht/3/futDailyMarketView"})
    print("OFFICIAL_ARCHIVE",year,r.status_code,"ZIP_BYTES",len(r.content),flush=True);r.raise_for_status()
    if not zipfile.is_zipfile(io.BytesIO(r.content)):raise RuntimeError("Official download is not ZIP")
    market={}
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        expected=f"{year}_fut.csv"
        if expected not in z.namelist():raise RuntimeError("Annual ZIP contains no "+expected)
        with z.open(expected) as binary,io.TextIOWrapper(binary,encoding="big5",newline="") as f:
            for row in csv.DictReader(f):
                if row.get("契約")!="TX":continue
                session=row.get("交易時段");typ="day" if session=="一般" else "night" if session=="盤後" else None
                if typ is None:continue
                month=(row.get("到期月份(週別)") or "").strip()
                d=(row.get("交易日期") or "").replace("/","-")
                try:c=float(row.get("收盤價"));v=float(row.get("成交量"))
                except (TypeError,ValueError):continue
                if len(d)!=10 or len(month)!=6 or c<=0 or v<=0:continue
                key=(d,typ,month)
                if key not in market or v>market[key][1]:market[key]=(c,v)
    print("OFFICIAL_VALID_TX_KEYS",year,len(market),flush=True)
    return market
def report():
    merged={}
    for year in (2023,2024,2025):merged.update(official(year))
    with PAIRED.open(encoding="utf-8-sig",newline="") as f:
        rows=list(csv.DictReader(f))
    compared=0;fail=[];byyear={};examples=[]
    for p in rows:
        year=p["decisionDate"][:4]
        if year not in ("2023","2024","2025"):continue
        dk=(p["cashDate"],"day",p["contract"]);nk=(p["decisionDate"],"night",p["contract"])
        day=merged.get(dk);night=merged.get(nk)
        if day is None or night is None:
            fail.append({"decision":p["decisionDate"],"contract":p["contract"],"day":bool(day),"night":bool(night),"reason":"Missing official pair"})
            continue
        compared+=1;byyear[year]=byyear.get(year,0)+1
        deltaDay=float(p["txDay"])-day[0];deltaNight=float(p["txNight"])-night[0]
        if abs(deltaDay)>.51 or abs(deltaNight)>.51:fail.append({"decision":p["decisionDate"],"contract":p["contract"],"dayDelta":deltaDay,"nightDelta":deltaNight})
        if len(examples)<4:examples.append({"date":p["decisionDate"],"contract":p["contract"],"day":day[0],"night":night[0]})
    total=sum(x["decisionDate"][:4] in ("2023","2024","2025") for x in rows)
    print("CROSSCHECK_OFFICIAL_TOTAL",compared,"OF",total,"BY_YEAR",byyear,flush=True)
    print("SAMPLES",examples,flush=True)
    print("OFFICIAL_MISMATCH_COUNT",len(fail),"MISMATCHES",fail[:15],flush=True)
    if compared<500:raise RuntimeError("Fewer than 500 historical official pairs verified")
    if fail:raise RuntimeError("Historical TX price does not fully match official annual files")
    print("PASS OFFICIAL 2023-2025 TX day/night 100 percent of research pairs compared; remainder 2026 not independently audited",flush=True)
if __name__=="__main__":report()
