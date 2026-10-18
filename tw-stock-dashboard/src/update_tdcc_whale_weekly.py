#!/usr/bin/env python3
"""TDCC 400+ lot shareholder concentration weekly quadrants.
Three real weekly reference dates, no forward fill, no fabricated closes.
TDCC 1-5 range 12..15 means >=400,001 shares (over 400 board lots).
Snapshot history source: a public raw-CSV archival copy of official TDCC 1-5.
This panel is descriptive, NOT a recommendation or a live G/Risk Score input.
"""
from __future__ import annotations
import argparse,csv,io,json,math,re,sys,time
from collections import Counter,defaultdict
from datetime import date,datetime,timedelta,timezone
from pathlib import Path
import requests
from config import DATA_DIR
from yahoo_cache import update_many,to_symbol
from pipeline import load_universe
from config import TWSE_COMPANY_URL,TPEX_COMPANY_URLS

OUT=DATA_DIR/"research"/"tdcc_whales"
ARCHIVE="https://api.github.com/repos/wirelessr/tdcc-opendata-archive/contents/snapshots"
SOURCE="https://opendata.tdcc.com.tw/getOD.ashx?id=1-5"
ARCHIVE_RAW="https://raw.githubusercontent.com/wirelessr/tdcc-opendata-archive/main/snapshots"
HEAD={"User-Agent":"Mozilla/5.0 (compatible; weekly-tdcc-report/1.0; public research)","Accept":"application/json,text/csv,*/*"}
LEVELS={12,13,14,15}
THRESHOLD_PP=1.0
QUADRANTS={"續買":("positive","positive"),"回頭車":("negative","positive"),"下車":("positive","negative"),"續賣":("negative","negative")}
def request(url,params=None,retries=3):
    err=None
    for i in range(retries):
        try:
            r=requests.get(url,params=params,headers=HEAD,timeout=35)
            r.raise_for_status()
            if len(r.content)>8_000_000:raise ValueError("TDCC response above expected size")
            return r
        except (requests.RequestException,ValueError) as e:
            err=e
            if i+1<retries:time.sleep(1.5*(i+1))
    raise RuntimeError(f"{url}: {err}")
def dates_from_archive(year=None):
    now=date.today(); years=[year] if year else sorted({now.year,now.year-1},reverse=True)
    result=[]
    for y in years:
        try:rows=request(f"{ARCHIVE}/{y}",retries=1).json()
        except RuntimeError as e:
            if y!=now.year and ("404" in str(e)):continue  # archive started in 2026; older years not mandatory
            raise
        if not isinstance(rows,list):raise ValueError("TDCC weekly archive index shape changed")
        for x in rows:
            name=str(x.get("name") or "")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.csv",name):
                day=name[:-4]
                try:d=date.fromisoformat(day)
                except ValueError:continue
                if d<=now:result.append((day,x.get("download_url") or f"{ARCHIVE_RAW}/{y}/{name}"))
    result=sorted(set(result))
    if len(result)<3:raise ValueError("Fewer than three TDCC historical reference weeks")
    return result[-3:]
def parse_snapshot(body,day):
    """Strictly parse official 17-level weekly CSV; numerator from SHARE COUNTS."""
    text=body.decode("utf-8-sig") if isinstance(body,bytes) else str(body).lstrip("\ufeff")
    reader=csv.DictReader(io.StringIO(text))
    required={"資料日期","證券代號","持股分級","人數","股數","占集保庫存數比例%"}
    if not required.issubset(set(reader.fieldnames or [])):raise ValueError("TDCC 1-5 CSV missing required fields")
    accum=defaultdict(lambda:{"holdingShares":0,"allShares":0,"seen":set()})
    count=0;all_dates=set()
    for row in reader:
        count+=1
        d=str(row.get("資料日期") or "").strip()
        all_dates.add(d)
        code=str(row.get("證券代號") or "").strip()
        if not code:continue
        try:
            level=int(row["持股分級"])
            shares=int(str(row["股數"]).replace(",","").strip())
        except (ValueError,TypeError):raise ValueError(f"Invalid TDCC holding level or count at row {count}")
        if shares<0:raise ValueError("TDCC negative share holding")
        item=accum[code]
        if level in item["seen"]:raise ValueError(f"Duplicate TDCC level {code}:{level}")
        item["seen"].add(level)
        if level in LEVELS:item["holdingShares"]+=shares
        if level==17:item["allShares"]=shares
    if all_dates!={day.replace("-","")}:raise ValueError(f"TDCC snapshot date mismatch: expected {day}, saw {all_dates}")
    if count<45_000:raise ValueError(f"TDCC snapshot truncated: {count} records")
    output={}
    for code,v in accum.items():
        if v["allShares"]<=0 or not LEVELS.issubset(v["seen"]) or 17 not in v["seen"]:continue
        ratio=100*v["holdingShares"]/v["allShares"]
        if not 0<=ratio<=100.05:continue
        output[code]={"ratio":ratio,"shares":v["holdingShares"],"total":v["allShares"]}
    if len(output)<3500:raise ValueError(f"TDCC valid security coverage insufficient: {len(output)}")
    return output
def quadrant_of(previous,current):
    if abs(previous)<THRESHOLD_PP-1e-7 or abs(current)<THRESHOLD_PP-1e-7:return None
    for k,(a,b) in QUADRANTS.items():
        if (previous>0)==(a=="positive") and (current>0)==(b=="positive"):return k
    return None
def parse_listing_day(raw):
    """Accept YYYYMMDD, ISO, Minguo 1150922, ROC/ISO slash dates."""
    if raw is None:return None
    s=str(raw).strip()
    if not s:return None
    digits=re.sub(r"[^0-9]","",s)
    try:
        if len(digits)==8 and 1950<=int(digits[:4])<=2100:
            return date(int(digits[:4]),int(digits[4:6]),int(digits[6:8]))
        if len(digits)==7 and 70<=int(digits[:3])<=189:
            return date(1911+int(digits[:3]),int(digits[3:5]),int(digits[5:7]))
    except ValueError:return None
    return None
def get_official_listing_dates():
    """Authoritative TWSE/TPEx issuer master. No inferred/synthetic listing dates."""
    dates={}
    urls=[("上市",TWSE_COMPANY_URL),("上櫃",TPEX_COMPANY_URLS[0])]
    for market,url in urls:
        try:
            rows=request(url,retries=2).json()
            if not isinstance(rows,list):raise ValueError("issuer list not array")
            valid=0
            for row in rows:
                if not isinstance(row,dict):continue
                code=str(row.get("公司代號") or row.get("SecuritiesCompanyCode") or row.get("Code") or row.get("股票代號") or "").strip()
                if not re.fullmatch(r"\d{4}",code):continue
                keys=[k for k in row if "上市" in k or "上櫃" in k or "listing" in k.lower()]
                day=next((d for k in keys if (d:=parse_listing_day(row.get(k))) is not None),None)
                if day:
                    dates[code]=day;valid+=1
            print("issuer listing dates",market,valid,"of",len(rows),flush=True)
        except (RuntimeError,ValueError) as exc:
            print("issuer listing metadata unavailable",market,str(exc)[:160],file=sys.stderr)
    return dates
def select_owners(points,universe,listing_dates=None,as_of=None):
    a,b,c=points
    universe_by_code={x["code"]:x for x in universe if x["market"] in {"上市","上櫃"} and re.fullmatch(r"\d{4}",x["code"])}
    found=defaultdict(list);skipped=Counter();common=0
    for code,latest in c.items():
        if code not in a or code not in b:continue
        common+=1
        stock=universe_by_code.get(code)
        if not stock:
            skipped["no_current_listed_otc_universe"]+=1;continue
        if stock.get("name","").upper().endswith("-DR") or stock.get("industry")=="存託憑證":
            skipped["depositary_receipt"]+=1;continue
        listed=(listing_dates or {}).get(code)
        if listed is not None and as_of is not None and 0<=(as_of-listed).days<30:
            skipped["recent_initial_listing_under_30_days"]+=1;continue
        prev,mid=a[code],b[code]
        # Avoid corporate actions/reclassifications that change share denominator.
        totals=[prev["total"],mid["total"],latest["total"]]
        if any(not v or v<=0 for v in totals):skipped["zero_total"]+=1;continue
        if max(abs(totals[i]/totals[i-1]-1) for i in (1,2))>.05:
            skipped["large_tdcc_depository_change"]+=1;continue
        pp1=mid["ratio"]-prev["ratio"]
        pp2=latest["ratio"]-mid["ratio"]
        category=quadrant_of(pp1,pp2)
        if not category:
            skipped["below_one_pp_change"]+=1;continue
        found[category].append({
            "code":code,"name":stock.get("name") or code,"market":stock["market"],
            "previousPP":round(pp1,2),"currentPP":round(pp2,2),
            "bigHolderRatio":round(latest["ratio"],3),"priceReturnPct":None,
            "startConcentration":round(prev["ratio"],3),"middleConcentration":round(mid["ratio"],3),
            "endConcentration":round(latest["ratio"],3)
        })
    for v in found.values():v.sort(key=lambda x:(-abs(x["currentPP"]),-abs(x["previousPP"]),x["code"]))
    return found,skipped,common
def fetch_close_prices(groups,universe,start,end):
    """Yahoo verified dated adjusted closes, missing prices stay null.
       Price return = adjusted EOD at current TDCC date / adjusted EOD at
       preceding TDCC date - 1 (NO invented Friday prices).
    """
    stocks={x["code"]:x for x in universe}
    codes={r["code"] for rows in groups.values() for r in rows}
    pairs=[(code,stocks[code]["market"]) for code in codes]
    if not pairs:return {},{"attempted":0,"paired":0,"errors":0}
    begin=datetime.fromisoformat(start)-timedelta(days=8)
    finish=datetime.fromisoformat(end)+timedelta(days=1)
    prices,fail=update_many(pairs,begin,finish)
    returns={}
    for code,market in pairs:
        q=prices.get(to_symbol(code,market))
        if q is None or q.empty:continue
        frame=q.set_index(q.date.astype(str))
        if start not in frame.index or end not in frame.index:continue
        try:
            p=float(frame.loc[start,"adjclose"])
            c=float(frame.loc[end,"adjclose"])
            if all(math.isfinite(x) and x>0 for x in (p,c)):
                returns[code]=round((c/p-1)*100,2)
        except (ValueError,TypeError,KeyError):continue
    return returns,{"attempted":len(pairs),"paired":len(returns),"errors":len(fail)}
def render(dates,records,universe,price_returns,price_cov,listing_dates=None):
    (d0,_),(d1,_),(d2,_)=dates
    groups,skipped,common=select_owners(records,universe,listing_dates=listing_dates,as_of=date.fromisoformat(d2))
    result={}
    for name in QUADRANTS:
        rows=groups.get(name,[])
        for row in rows:row["priceReturnPct"]=price_returns.get(row["code"])
        valid=[x["priceReturnPct"] for x in rows if x["priceReturnPct"] is not None]
        result[name]={
            "count":len(rows),"priceCount":len(valid),
            "avgPriceReturnPct":round(sum(valid)/len(valid),2) if valid else None,
            "medianPriceReturnPct":round(sorted(valid)[len(valid)//2] if len(valid)%2 else
                                         (sorted(valid)[len(valid)//2-1]+sorted(valid)[len(valid)//2])/2,2) if valid else None,
            "upCount":sum(x>0 for x in valid),"rows":rows
        }
    return {
        "version":"TDCC_WHALE_400_QUADRANTS_V1","updatedAt":datetime.now(timezone.utc).isoformat(),
        "date":d2,"priorDate":d1,"twoWeeksBefore":d0,
        "title":"大戶換手四象限週報",
        "thresholdPP":THRESHOLD_PP,"minBigHolderShares":400001,
        "definitions":{
            "bigHolder":"集保持股分級12～15（400,001股以上）的股數／分級17合計股數，計算持股比率",
            "change":"上週與本週持股比率差，以百分點（pp）表示；不是大戶淨買進張數",
            "continuedBuy":"兩段變動均達+1.00pp","turnaround":"前段≤−1.00pp、本段≥+1.00pp",
            "exit":"前段≥+1.00pp、本段≤−1.00pp","continuedSell":"兩段變動均≤−1.00pp",
            "price":"本週收盤漲跌＝本期相對前一期調整後收盤價的百分比（Yahoo Finance），不可取得留空",
            "screen":"當前上市/上櫃四碼普通股（不含存託憑證及官方上市/櫃日期未滿30日的新掛牌股票），兩段絕對變動都達1pp；排除集保合計股數週變化超過5%者",
            "differenceFromImage":"原圖額外入榜規則未揭露；此處顯示完整符合公開條件的集合，不宣稱與原圖數量相同"
        },
        "source":{"official":"https://www.tdcc.com.tw/portal/zh/smWeb/qryStock",
                  "openData":SOURCE,"historicalArchive":"https://github.com/wirelessr/tdcc-opendata-archive",
                  "snapshotUrls":[url for _,url in dates]},
        "coverage":{"referenceWeeks":3,"validTDCCStocks":[len(x) for x in records],"sharedThreeWeeks":common,
                   "universe":len(universe),"excludedReasons":dict(skipped),"price":price_cov},
        "quadrants":result,
        "disclaimer":"TDCC 集保大戶持股級距變化不是主力實際買賣超；持股異動可能受帳戶歸戶、股本與交割等因素影響。非買賣建議，不納入 G 選股或大盤分數。"
    }
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--skip-price",action="store_true",help="For diagnostics only: dates+TDCC source, not publishable")
    args=parser.parse_args()
    dates=dates_from_archive()
    if (date.today()-date.fromisoformat(dates[-1][0])).days>16:
        raise RuntimeError("Official TDCC archive stale: latest week older than 16 days")
    snapshots=[]
    for day,url in dates:
        raw=request(url).content
        rows=parse_snapshot(raw,day)
        print("TDCC",day,len(rows),"codes",len(raw),"bytes",flush=True)
        snapshots.append(rows)
    universe=load_universe()
    listing_dates=get_official_listing_dates()
    if len(universe)<1400:raise RuntimeError("Listed+OTC universe unexpectedly small")
    groups,_,_=select_owners(snapshots,universe,listing_dates=listing_dates,as_of=date.fromisoformat(dates[-1][0]))
    if args.skip_price:
        print("CHECK_ONLY",json.dumps({k:len(v) for k,v in groups.items()},ensure_ascii=False))
        return
    values,cov=fetch_close_prices(groups,universe,dates[1][0],dates[2][0])
    if cov["paired"]<max(40,int(cov["attempted"]*.60)):
        raise RuntimeError(f"Price source coverage too low: {cov} (refuse to publish incomplete weekly report)")
    report=render(dates,snapshots,universe,values,cov,listing_dates=listing_dates)
    OUT.mkdir(parents=True,exist_ok=True)
    text=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    (OUT/"latest.json").write_text(text,encoding="utf-8")
    archive=OUT/"history";archive.mkdir(exist_ok=True)
    (archive/f"{report['date']}.json").write_text(text,encoding="utf-8")
    print("TDCC_400_QUADRANTS_VERIFIED",report["date"],
          {k:v["count"] for k,v in report["quadrants"].items()},"price",cov,flush=True)
if __name__=="__main__":main()
