"""Read-only free-data overlay for the provisional G scan.

Industry strength is RESEARCH, not the G score or a cash-flow measurement.
Method independently implemented with reference to EquiLens (MIT):
https://github.com/wakin61043/tw-trading-dashboard
Price * cumulative volume is estimated traded value, NOT an official turnover
or buy/sell net flow. Never synthesize a missing same-day quote.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import re
import requests

TZ=ZoneInfo("Asia/Taipei")
TWSE="https://www.twse.com.tw/rwd/zh/announcement/punish"
TPEX="https://www.tpex.org.tw/openapi/v1/tpex_disposal_information"
VALID_SOURCES={"last-trade","previous-trade"}
CODE=re.compile(r"^\d{4}$")
PERIOD=re.compile(r"(\d{2,3})/?(\d{2})/?(\d{2})")

def _date(text):
    match=PERIOD.search(str(text or ""))
    if not match:return None
    try:
        return "%04d-%s-%s"%(int(match[1])+1911,match[2],match[3])
    except (ValueError,TypeError):return None

def _active(period,asof):
    pieces=re.split(r"[～~至－—]",str(period or ""))
    left=_date(pieces[0]) if pieces else None
    right=_date(pieces[1]) if len(pieces)>1 else left
    return bool(left and right and left<=asof<=right)

def parse_twse_dispositions(body,asof):
    if not isinstance(body,dict) or not isinstance(body.get("data"),list):
        raise ValueError("上市處置公告資料格式無法驗證")
    fields=body.get("fields") or []
    if "證券代號" not in fields or "處置起迄時間" not in fields:
        raise ValueError("上市處置公告缺少必要欄位")
    ci=fields.index("證券代號"); pi=fields.index("處置起迄時間")
    return {str(row[ci]).strip() for row in body["data"] if len(row)>max(ci,pi)
            and CODE.fullmatch(str(row[ci]).strip()) and _active(row[pi],asof)}

def parse_tpex_dispositions(body,asof):
    if not isinstance(body,list):raise ValueError("上櫃處置公告資料格式無法驗證")
    return {str(row.get("SecuritiesCompanyCode","")).strip() for row in body
            if isinstance(row,dict) and CODE.fullmatch(str(row.get("SecuritiesCompanyCode","")).strip())
            and _active(row.get("DispositionPeriod"),asof)}

def trade_restrictions(asof,now=None,get=None):
    """No cached/old response counted as today's authoritative status."""
    now=now or datetime.now(TZ);get=get or requests.get
    begin=(datetime.fromisoformat(asof)-timedelta(days=30)).strftime("%Y%m%d")
    result={"checkedAt":now.isoformat(timespec="seconds"),"asOfDate":asof,
            "source":"TWSE／TPEx 免費官方處置公告","markets":{},"codes":[]}
    for market,url,params,parser in [
        ("上市",TWSE,{"response":"json","startDate":begin,"endDate":asof.replace("-","")},parse_twse_dispositions),
        ("上櫃",TPEX,None,parse_tpex_dispositions)]:
        try:
            response=get(url,params=params,timeout=14,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
            response.raise_for_status()
            codes=sorted(parser(response.json(),asof))
            result["markets"][market]={"status":"verified","count":len(codes),"codes":codes}
        except (requests.RequestException,ValueError,TypeError,KeyError,IndexError) as exc:
            result["markets"][market]={"status":"unavailable","count":None,"codes":[],
                                       "reason":type(exc).__name__}
    result["codes"]=sorted({(market,code) for market,info in result["markets"].items()
                            if info["status"]=="verified" for code in info["codes"]})
    return result

def sector_ranking(universe,quotes,asof,previous=None,limit=12):
    """Only same-day *trade* prices count; proxies/no-trades are excluded."""
    grouped=defaultdict(list)
    for stock in universe:
        code=str(stock.get("code") or "")
        market=stock.get("market")
        if market not in ("上市","上櫃") or not CODE.fullmatch(code):continue
        key=str(stock.get("industry") or "未分類").strip() or "未分類"
        grouped[key].append((market,code,stock.get("name") or code))
    prior={}
    if isinstance(previous,dict) and previous.get("asOfDate")==asof:
        prior={r["industry"]:r.get("rank") for r in previous.get("ranking",[]) if r.get("rank") is not None}
    rows=[];whole=0
    for industry,stocks in grouped.items():
        matched=[]
        for market,code,name in stocks:
            q=quotes.get((market,code)) or {}
            if q.get("priceSource") not in VALID_SOURCES:continue
            price=q.get("price");base=q.get("previousClose");vol=q.get("volume")
            if not all(isinstance(v,(float,int)) and not isinstance(v,bool) and v>0
                       for v in (price,base,vol)):continue
            pct=(price/base-1)*100
            if not -12<=pct<=12:continue
            amount=price*vol
            matched.append({"code":code,"name":name,"market":market,"pct":pct,"amount":amount})
        expected=len(stocks);sample=len(matched);ratio=sample/max(1,expected)
        if ratio<.60 or sample<3:continue
        whole+=sum(x["amount"] for x in matched)
        turnover=sum(x["amount"] for x in matched)
        selected=[x for x in matched if x["amount"]>=max(10_000_000,turnover*.005)]
        if len(selected)<2:continue
        weights=[x["amount"]**.5 for x in selected]
        strength=sum(x["pct"]*weight for x,weight in zip(selected,weights))/sum(weights)
        leader=sorted(selected,key=lambda x:x["amount"],reverse=True)[:3]
        rows.append({"industry":industry,"scorePct":round(strength,2),
                     "turnoverEstimatedB":round(turnover/100_000_000,2),
                     "breadthPct":round(100*sum(x["pct"]>0 for x in matched)/sample,1),
                     "quoted":sample,"total":expected,"coverage":round(ratio,3),
                     "eligible":len(selected),"leaders":[{"code":x["code"],"name":x["name"],
                                                            "market":x["market"]} for x in leader]})
    rows.sort(key=lambda x:(-x["scorePct"],-x["breadthPct"],-x["turnoverEstimatedB"],x["industry"]))
    for i,row in enumerate(rows):
        row["rank"]=i+1
        old=prior.get(row["industry"])
        row["rankMove"]=old-(i+1) if isinstance(old,int) else None
        row["sharePct"]=round(row["turnoverEstimatedB"]*100_000_000/whole*100,2) if whole>0 else None
    return {"asOfDate":asof,"method":"平方根估計成交額加權漲跌幅；排除低量與非實際成交價",
            "priceQuality":"verified-same-day-trades-only","estimatedTurnover":True,
            "notNetFlow":True,"minGroupCoverage":.60,"ranking":rows[:limit],
            "eligibleGroupCount":len(rows),"sampleGroups":len(grouped)}

def build_overlay(universe,quotes,asof,rows,previous=None,now=None,get=None):
    sectors=sector_ranking(universe,quotes,asof,previous=previous)
    restrictions=trade_restrictions(asof,now=now,get=get)
    flags=[]
    for row in rows:
        market=row.get("market");code=str(row.get("code") or "")
        source=restrictions["markets"].get(market,{})
        status=("待查證" if source.get("status")!="verified" else
                "處置公告期間" if code in source["codes"] else "未列入本次查得處置公告")
        flags.append({"market":market,"code":code,"status":status})
    return {"version":"free-market-overlay-v1","asOfDate":asof,
            "industryMomentum":sectors,"tradeRestrictions":restrictions,
            "topGRestrictions":flags,
            "note":"純研究附加資訊，不修改 G 盤中／盤後選股、分數或風險分數；處置標記非當沖資格保證"}
