"""Independent TAIFEX yearly ZIP reconciliation of FinMind date-paired TX nights.
Download only official archive (no quote construction or future prices); compare day
D contract and NIGHT assigned to following TWII trading date T at SAME contract.
"""
import csv,io,zipfile,json,re,collections
from pathlib import Path
import requests
ROOT=Path(__file__).resolve().parents[1]/"docs"/"data"/"research"/"tx_night_regime_3y"
ENDPOINT="https://www.taifex.com.tw/cht/3/futDataDown"
def annual(year,post=requests.post):
    result=post(ENDPOINT,data={"down_type":"2","his_year":str(year)},timeout=120,
        headers={"User-Agent":"Mozilla/5.0","Referer":"https://www.taifex.com.tw/cht/3/futDailyMarketView"})
    result.raise_for_status()
    blob=io.BytesIO(result.content)
    if not zipfile.is_zipfile(blob):raise ValueError("No official ZIP for "+str(year))
    pairs={}
    with zipfile.ZipFile(blob) as z:
        name=next((x for x in z.namelist() if x.lower().endswith(".csv")),None)
        if not name:raise ValueError("Annual ZIP missing CSV")
        with z.open(name) as source:
            content=source.read().decode("cp950",errors="replace")
        for x in csv.DictReader(io.StringIO(content)):
            if str(x.get("契約") or "").strip()!="TX":continue
            session=str(x.get("交易時段") or "").strip()
            if session not in ("一般","盤後"):continue
            dt=re.sub("[^0-9]","",str(x.get("交易日期") or ""))
            month=str(x.get("到期月份(週別)") or "").strip()[:6]
            if len(dt)!=8 or len(month)!=6 or not month.isdecimal():continue
            try:
                close=float(str(x.get("收盤價") or "").replace(",",""))
                volume=float(str(x.get("成交量") or "").replace(",",""))
            except (ValueError,TypeError):continue
            if close<=0 or volume<=0:continue
            key=(dt,month,session)
            if key not in pairs or volume>pairs[key][1]:pairs[key]=(close,volume)
    return pairs
def pairs_csv():
    with (ROOT/"paired_nights.csv").open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
def check(official,rows):
    compared=0;missing=[];mismatches=[]
    for x in rows:
        contract=x["contract"];day=x["cashDate"].replace("-","");nextday=x["decisionDate"].replace("-","")
        keyDay=(day,contract,"一般");keyNight=(nextday,contract,"盤後")
        if keyDay not in official or keyNight not in official:
            missing.append({"date":nextday,"missingDay":keyDay not in official,"missingNight":keyNight not in official})
            continue
        compared+=1
        try:
            old=float(x["txDay"]);night=float(x["txNight"])
            change=abs(old-official[keyDay][0])+abs(night-official[keyNight][0])
        except (TypeError,ValueError):change=9999
        if change>.10:mismatches.append({"date":nextday,"contract":contract,"cached":[old,night],"official":[official[keyDay][0],official[keyNight][0]]})
    return compared,missing,mismatches
def main():
    rows=pairs_csv();official={};result={"archiveYears":[2023,2024,2025],
        "source":ENDPOINT,"history":"official yearly futures ZIP, TX, same-month D regular vs next TWII day T overnight",
        "archivedPairs":len(rows),"applicablePairs":0,"verified":0,
        "errors":{},"missing":[],"mismatches":[],"status":"UNVERIFIED"}
    for year in result["archiveYears"]:
        try:
            data=annual(year);official.update(data)
            print("OFFICIAL_YEAR",year,"CONTRACT_DAY_NIGHT_ROWS",len(data),flush=True)
        except Exception as e:result["errors"][str(year)]=type(e).__name__+": "+str(e)[:180]
    eligible=[x for x in rows if x["decisionDate"]<"2026-01-01"]
    result["applicablePairs"]=len(eligible)
    compared,missing,mismatch=check(official,eligible)
    result["verified"]=compared;result["missing"]=missing[:25];result["missingCount"]=len(missing)
    result["mismatches"]=mismatch[:25];result["mismatchCount"]=len(mismatch)
    result["verifiedCoveragePct"]=round(compared/max(1,len(eligible))*100,2)
    if not result["errors"] and compared>=500 and result["verifiedCoveragePct"]>=95 and not mismatch:
        result["status"]="VERIFIED_OFFICIAL_YEARLY_AGREEMENT"
    elif mismatch:result["status"]="OFFICIAL_MISMATCH_DO_NOT_USE"
    else:result["status"]="INSUFFICIENT_OFFICIAL_COVERAGE"
    (ROOT/"official_yearly_reconciliation.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:result[k] for k in ("status","applicablePairs","verified","verifiedCoveragePct","missingCount","mismatchCount","errors")},ensure_ascii=False),flush=True)
if __name__=="__main__":main()
