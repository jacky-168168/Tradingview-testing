#!/usr/bin/env python3
"""M10/M11 2026 audit. Official EOD institutional/margin data; no same-day trades.
M10: >=30% eligible stocks of SAME industry with trust net buy, stock adj 5D >10%.
M11: both financing and short-sale balances strictly increase on EACH of last 5 sessions.
No model can be promoted to live before source completeness and execution audit.
"""
from __future__ import annotations
import argparse,collections,json,math,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime
from pathlib import Path
import numpy as np,pandas as pd,requests
from config import CACHE_DIR,DATA_DIR
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from institution import fetch_many
OUT=DATA_DIR/"research"/"m10_m11_2026"
CACHE=CACHE_DIR/"m10_m11_2026"
START="2026-01-01";END="2026-10-16"
BROKER=.001425;SELL_TAX=.003;SLIP=.001
HEAD={"User-Agent":"Mozilla/5.0 (compatible; quantitative-research/1.0)","Accept":"application/json"}
def integer(v):
    s=str(v if v is not None else "").strip().replace(",","")
    if s in ("","--","-"):return 0
    if not s.lstrip("-").isdigit():raise ValueError("invalid integer "+s[:30])
    return int(s)
def parse_margin(payload,market,day):
    """Read only dated official security rows; field names not assumed identical across markets."""
    if not isinstance(payload,dict):raise ValueError("margin payload not object")
    if market=="上市":
        report=str(payload.get("date") or "").replace("-","").replace("/","")
        if report!=day.replace("-",""):raise ValueError("TWSE margin wrong date "+report)
        tables=payload.get("tables") or []
    else:
        y,m,d=map(int,day.split("-"));roc=f"{y-1911:03d}/{m:02d}/{d:02d}"
        tables=payload.get("tables") or []
        reported=str(payload.get("date") or (tables[0].get("date") if tables else "") or "").strip()
        if reported not in (roc,day,day.replace("-","/")):raise ValueError("TPEx margin wrong date "+reported)
    result={}
    for tab in tables:
        fields=[str(x).replace(" ","").replace("\n","") for x in tab.get("fields",[])]
        rows=tab.get("data") or []
        if not fields or not rows:continue
        code_id=next((i for i,f in enumerate(fields) if f in ("代號","股票代號","證券代號","股票代碼")),None)
        if code_id is None:continue
        if market=="上市":
            balances=[i for i,f in enumerate(fields) if f in ("今日餘額","當日餘額")]
            if len(balances)>=2:mi,si=balances[:2]
            else:
                mi=next((i for i,f in enumerate(fields) if "融資" in f and ("今日餘額" in f or "當日餘額" in f)),None)
                si=next((i for i,f in enumerate(fields) if "融券" in f and ("今日餘額" in f or "當日餘額" in f)),None)
        else:
            mi=next((i for i,f in enumerate(fields) if f=="資餘額" or "融資當日餘額" in f),None)
            si=next((i for i,f in enumerate(fields) if f=="券餘額" or "融券當日餘額" in f),None)
        if mi is None or si is None:continue
        for row in rows:
            try:
                code=str(row[code_id]).strip()
                if len(code)!=4 or not code.isdigit():continue
                a,b=integer(row[mi]),integer(row[si])
                if a>=0 and b>=0:result[market+"_"+code]=[a,b]
            except (TypeError,ValueError,IndexError):continue
    min_size=500 if market=="上市" else 300
    if len(result)<min_size:raise ValueError(f"{market} margin rows insufficient: {len(result)}")
    return result
def pull_margin(day):
    CACHE.mkdir(parents=True,exist_ok=True);p=CACHE/("margin_"+day+".json")
    if p.exists():
        obj=json.loads(p.read_text(encoding="utf-8"))
        if obj.get("day")==day and len(obj.get("rows",{}))>=900:return obj["rows"]
    y,m,d=map(int,day.split("-"));roc=f"{y-1911:03d}/{m:02d}/{d:02d}"
    urls=[
        ("上市","https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN",{"date":day.replace("-",""),"selectType":"ALL","response":"json"}),
        ("上櫃","https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php",{"d":roc,"l":"zh-tw","o":"json","s":"0,asc"})]
    merged={}
    for market,url,params in urls:
        error=None
        for attempt in range(3):
            try:
                r=requests.get(url,params=params,headers=HEAD,timeout=35)
                r.raise_for_status();rows=parse_margin(r.json(),market,day)
                merged.update(rows);break
            except (requests.RequestException,ValueError,KeyError) as exc:
                error=exc
                if attempt<2:time.sleep(1+attempt)
        else:raise RuntimeError(f"{day} {market}: {error}")
    p.write_text(json.dumps({"day":day,"rows":merged},ensure_ascii=False),encoding="utf-8")
    return merged
def safe_margin(day):
    try:return day,pull_margin(day),None
    except Exception as e:return day,None,str(e)
def build_prices(universe,days):
    start=datetime(2025,11,1);end=datetime(2026,10,19)
    items=[(x["code"],x["market"]) for x in universe]
    px,errors=update_many(items,start,end)
    histories={};valid=0
    for x in universe:
        k=x["market"]+"_"+x["code"];df=px.get(to_symbol(x["code"],x["market"]))
        if df is None or len(df)<10:continue
        q=df.sort_values("date").drop_duplicates("date",keep="last").copy()
        for fld in ("open","close","adjclose","volume"):q[fld]=pd.to_numeric(q[fld],errors="coerce")
        q["adjOpen"]=q.open*q.adjclose/q.close
        q["adjClose"]=q.adjclose
        q["ret5"]=100*(q.adjClose/q.adjClose.shift(5)-1)
        q["turnoverB"]=q.close*q.volume/100_000_000
        histories[k]={str(z["date"]):z for z in q.to_dict("records")};valid+=1
    return histories,errors,valid
def growing_five(day_index,days,key,credits):
    if day_index<5:return False
    balances=[]
    for j in range(day_index-5,day_index+1):
        v=credits.get(days[j],{}).get(key)
        if v is None:return False
        balances.append(v)
    return all(balances[i][k]>balances[i-1][k] for i in range(1,6) for k in (0,1))
def select_models(days,universe,hist,credits,inst):
    by_industry=collections.defaultdict(list)
    info={}
    for x in universe:
        key=x["market"]+"_"+x["code"]
        info[key]=x
        if str(x.get("industry") or "未分類")!="未分類":
            by_industry[(x["market"],x["industry"])].append(key)
    result={"M10":{},"M11":{}}
    for i,day in enumerate(days):
        credit=credits.get(day);flow=inst.get(day)
        if not credit and not flow:continue
        ratios={}
        for g,keys in by_industry.items():
            present=[k for k in keys if flow and k in flow]
            if len(present)>=8:
                ratios[g]=sum(float(flow[k]["trust"])>0 for k in present)/len(present)
        ten=[];eleven=[]
        for key,meta in info.items():
            bar=hist.get(key,{}).get(day)
            if not bar:continue
            price=float(bar["close"]);turn=float(bar["turnoverB"])
            cap=float(meta.get("capitalB") or 0)
            if not(10<=price and turn>=1 and 0<cap<500):continue
            ret5=float(bar["ret5"]);ret5=ret5 if math.isfinite(ret5) else -999
            ratio=ratios.get((meta["market"],meta.get("industry")),0)
            base={"date":day,"code":meta["code"],"name":meta["name"],"market":meta["market"],
                  "industry":meta.get("industry"),"ret5":round(ret5,3),"turnoverB":round(turn,3)}
            if ratio>=.30 and ret5>10:
                ten.append(dict(base,trustIndustryRatio=round(100*ratio,2),rankScore=round(ratio*100+ret5,3)))
            if credit and growing_five(i,days,key,credits):
                v=credit.get(key)
                if v:
                    b=credits[days[i-5]][key]
                    eleven.append(dict(base,marginBalance=v[0],shortBalance=v[1],
                                       marginRise5=v[0]-b[0],shortRise5=v[1]-b[1],
                                       rankScore=round(ret5+20*math.log1p(v[1]-b[1]),3)))
        result["M10"][day]=sorted(ten,key=lambda x:(-x["rankScore"],-x["turnoverB"],x["code"]))[:20]
        result["M11"][day]=sorted(eleven,key=lambda x:(-x["rankScore"],-x["turnoverB"],x["code"]))[:20]
    return result
def price(hist,stock,day,field):
    key=stock["market"]+"_"+stock["code"];row=hist.get(key,{}).get(day)
    if row is None:return None
    v=float(row.get(field) or 0)
    return v if math.isfinite(v) and v>0 else None
def summarize_sample(returns):
    if not returns:return {"trades":0,"winPct":None,"avgNetPct":None,"medianNetPct":None}
    a=np.array(returns,float)
    return {"trades":len(a),"winPct":round(float(100*(a>0).mean()),2),
            "avgNetPct":round(float(a.mean()),3),"medianNetPct":round(float(np.median(a)),3),
            "avgWinPct":round(float(a[a>0].mean()),3) if (a>0).any() else None,
            "avgLossPct":round(float(a[a<=0].mean()),3) if (a<=0).any() else None}
def run_one(model,days,signals,hist,hold=10):
    per_h={str(h):[] for h in (5,10,20)};samples=[];sampled=set()
    for i,day in enumerate(days):
        for stock in signals.get(day,[])[:3]:
            if i+1>=len(days):continue
            opening=price(hist,stock,days[i+1],"adjOpen")
            if opening is None:continue
            for h in (5,10,20):
                j=i+h
                if j>=len(days):continue
                closing=price(hist,stock,days[j],"adjClose")
                if closing is None:continue
                net=100*((closing*(1-SLIP)*(1-BROKER-SELL_TAX))/(opening*(1+SLIP)*(1+BROKER))-1)
                per_h[str(h)].append(net)
                if h==10:samples.append({"signalDate":day,"entryDate":days[i+1],"exitDate":days[j],
                                         "code":stock["code"],"model":model,"netPct":round(net,4)})
    cash=1_000_000.0;positions={};nav=[];trades=[];pending=[]
    for idx,day in enumerate(days):
        # No same-day EOD information: only yesterday's queued signal may buy now.
        for stock in pending:
            key=stock["market"]+"_"+stock["code"]
            if key in positions or len(positions)>=3:continue
            opening=price(hist,stock,day,"adjOpen")
            if opening is None:continue
            shares=int((cash/(3-len(positions)))/(opening*(1+SLIP)*(1+BROKER))//1000)*1000
            if shares<1000:continue
            cost=shares*opening*(1+SLIP)*(1+BROKER)
            if cost>cash:continue
            cash-=cost;positions[key]={"stock":stock,"shares":shares,"entryIndex":idx,
                                       "entryDate":day,"paid":cost,"lastClose":opening}
        pending=[]
        for key,p in list(positions.items()):
            close=price(hist,p["stock"],day,"adjClose")
            if close is not None:p["lastClose"]=close
            if idx-p["entryIndex"]+1<hold:continue
            if close is None:continue  # no invented fill on missing price
            proceeds=p["shares"]*close*(1-SLIP)*(1-BROKER-SELL_TAX)
            cash+=proceeds
            trades.append({"signalDate":p["stock"]["date"],"entryDate":p["entryDate"],"exitDate":day,
                           "code":p["stock"]["code"],"netPct":round(100*(proceeds/p["paid"]-1),4),
                           "netTWD":round(proceeds-p["paid"],2)})
            del positions[key]
        equity=cash+sum(p["shares"]*p["lastClose"]*(1-SLIP)*(1-BROKER-SELL_TAX) for p in positions.values())
        nav.append({"date":day,"equity":round(equity,2)})
        pending=signals.get(day,[])[:3] # queued until next session open
    vals=np.array([1_000_000]+[z["equity"] for z in nav],float)
    peak=np.maximum.accumulate(vals)
    mdd=round(float(100*np.min(vals/peak-1)),3)
    return {"signalDays":sum(bool(x) for x in signals.values()),"candidateCount":sum(len(x) for x in signals.values()),
            "top3TradeSample":{h:summarize_sample(v) for h,v in per_h.items()},
            "top3SampleTrades10D":samples,"portfolio10D":{"capitalStart":1000000,"capitalEnd":round(float(vals[-1]),2),
                "netReturnPct":round(float(100*(vals[-1]/vals[0]-1)),3),"maxDrawdownPct":mdd,
                "closedTrades":len(trades),"openAtEnd":len(positions),
                "tradeStats":summarize_sample([t["netPct"] for t in trades])},
            "trades10D":trades,"equity10D":nav}
def main():
    arg=argparse.ArgumentParser();arg.add_argument("--from-date",default=START);arg.add_argument("--to-date",default=END)
    arg.add_argument("--workers",type=int,default=4);args=arg.parse_args()
    _,idx,err=update_symbol("^TWII",datetime(2025,11,1),datetime(2026,10,19))
    if err or idx.empty:raise RuntimeError("Cannot fetch authoritative market trading calendar "+str(err))
    days=sorted(str(d) for d in idx.date if args.from_date<=str(d)<=args.to_date)
    if len(days)<30:raise RuntimeError("Market calendar missing 2026 trading days")
    universe=load_universe();hist,price_errors,valid=build_prices(universe,days)
    credits={};credit_errors={};inst={};flow_errors={}
    with ThreadPoolExecutor(max_workers=max(1,min(6,args.workers))) as exe:
        futures={exe.submit(safe_margin,d):d for d in days}
        for f in as_completed(futures):
            day,rows,error=f.result()
            if rows is not None:credits[day]=rows
            else:credit_errors[day]=error
    # TWSE T86 and TPEx dailyTrade are date-pinned; no missing data treated as zero.
    fetched,issues=fetch_many(days,workers=max(1,min(4,args.workers)))
    for day in days:
        flow=fetched.get(day) or {}
        error=issues.get(day)
        listed=sum(k.startswith("上市_") for k in flow)
        otc=sum(k.startswith("上櫃_") for k in flow)
        if error or listed<500 or otc<250:
            flow_errors[day]=str(error or f"market coverage insufficient: listed={listed} otc={otc}")
        else:inst[day]=flow
    print("official institution sessions",len(inst),"/",len(days),flush=True)
    signal=select_models(days,universe,hist,credits,inst)
    coverage={"marketSessions":len(days),"creditSessions":len(credits),"institutionSessions":len(inst),
              "pairedSessions":len(set(credits)&set(inst)),"stockPriceHistories":valid,
              "priceErrors":len(price_errors),"creditErrors":credit_errors,"institutionErrors":flow_errors}
    complete=len(credits)/len(days)>=.90 and len(inst)/len(days)>=.90 and len(hist)>=1400
    result={"version":"M10_M11_2026_PIT_LAGGED_RESEARCH_V1","generatedAt":datetime.utcnow().isoformat()+"Z",
            "period":{"start":days[0],"end":days[-1]},"status":"PRELIMINARY_SURVIVORSHIP_BIAS" if complete else "INCOMPLETE_DO_NOT_INTERPRET",
            "coverage":coverage,"definitions":{"M10":"Industry trust buy ratio >=30% of dated reported stocks (at least 8); individual adjusted 5D gain >10%",
             "M11":"Per-security margin and short outstanding balances each strictly increase on all five past completed trading sessions",
             "base":"Current universe listed+OTC, price>=10, turnover>=100m TWD, paid-in capital 0..500 (100m TWD), no intraday information",
             "execution":"Close D signal -> D+1 adjusted open; fixed 5/10/20 trading-day close; 10D max 3 simultaneous round-lot positions; 0.1425% broker each side, 0.3% sale tax, 0.1% slippage each side.",
             "pitCaveats":"Official historical reports may be revised later. Current issuer master excludes delisted names and uses current industry/capital. Historical 2026 ROI is preliminary, not certified PIT."},
            "models":{},"picks":signal}
    for name in ("M10","M11"):result["models"][name]=run_one(name,days,signal[name],hist)
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps({"status":result["status"],"coverage":{k:v for k,v in coverage.items() if not isinstance(v,dict)},
                      "models":{m:{"signals":v["signalDays"],"portfolio":v["portfolio10D"],
                                    "top3":v["top3TradeSample"]} for m,v in result["models"].items()}},ensure_ascii=False))
if __name__=="__main__":main()
