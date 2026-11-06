#!/usr/bin/env python3
"""00631L vs 00685L 10-day TAIEX MA study. TWSE raw daily prices; pre-listing 00685L is explicitly synthetic."""
import argparse, json, math, os, random, time
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode
import requests

START="2014-10-31"
FIRST685="2017-03-30"
SPLITS={"00631L":("2026-03-25",22),"00685L":("2026-07-01",24)}
BROKER=0.001425; SLIPPAGE=0.001; SELL_TAX=0.001; ALLOCATION=0.997
INITIAL=1000000.0; SYNTH_FEE=0.0034/252
ROOT=Path(__file__).resolve().parents[1]
CACHE=ROOT/"cache/etf_10ma_twse"
OUT=ROOT/"docs/data/research/etf_10ma_comparison/latest.json"
HEAD={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
      "Referer":"https://www.twse.com.tw/","Accept":"application/json,text/plain,*/*"}
SES=requests.Session();SES.headers.update(HEAD)

def months(a,b):
    y,m=map(int,a[:7].split("-")); ey,em=map(int,b[:7].split("-"))
    while (y,m)<=(ey,em):
        yield f"{y:04d}{m:02d}01"
        m+=1
        if m>12:y,m=y+1,1

def day(s):
    a=s.strip().split("/")
    if len(a)!=3:return None
    try:
        y=int(a[0]);y+=1911 if y<1900 else 0
        return date(y,int(a[1]),int(a[2])).isoformat()
    except ValueError:return None

def number(x):
    t=str(x).replace(",","").replace("+","").strip()
    if t in ("","--","---","-","X","除權息"):return None
    try:return float(t)
    except ValueError:return None

def month_json(kind,ym,code=""):
    CACHE.mkdir(parents=True,exist_ok=True)
    name=CACHE/f"{kind}_{code}_{ym}.json"
    if name.exists():
        try:return json.loads(name.read_text())
        except Exception:name.unlink(missing_ok=True)
    endpoint="https://www.twse.com.tw/exchangeReport/STOCK_DAY" if kind=="STOCK_DAY" else "https://www.twse.com.tw/exchangeReport/FMTQIK"
    params={"response":"json","date":ym}
    if code:params["stockNo"]=code
    for i in range(5):
        try:
            r=SES.get(endpoint,params=params,timeout=35)
            r.raise_for_status()
            data=r.json()
            if not isinstance(data,dict) or not isinstance(data.get("data"),list):
                raise ValueError(str(data.get("stat","invalid response"))[:150])
            name.write_text(json.dumps(data,ensure_ascii=False))
            time.sleep(.16)
            return data
        except Exception as e:
            if i==4:raise RuntimeError(f"{kind} {code} {ym}: {e}") from e
            time.sleep(min(10,1.5*(i+1)))
    raise RuntimeError("unreachable")

def get_quotes(code,first,last):
    out={}
    for ym in months(first,last):
        try: raw=month_json("STOCK_DAY",ym,code)
        except Exception as ex: raise RuntimeError(f"{code} monthly data missing: {ex}")
        for a in raw["data"]:
            if len(a)<7:continue
            d=day(str(a[0])); op=number(a[3]);cl=number(a[6]);vol=number(a[1])
            if not d or not (first<=d<=last) or op is None or cl is None or op<=0 or cl<=0 or (vol is not None and vol<=0):continue
            div=SPLITS[code][1] if d<SPLITS[code][0] else 1
            out[d]={"open":op/div,"close":cl/div,"synthetic":False}
    return out

def get_index(first,last):
    out={}
    for ym in months(first,last):
        raw=month_json("FMTQIK",ym)
        for a in raw["data"]:
            if len(a)<5:continue
            d=day(str(a[0]));cl=number(a[4])
            if d and first<=d<=last and cl is not None and cl>0:out[d]=cl
    return out

def continuity(quotes,first,minimum,code,last):
    keys=sorted(k for k in quotes if first<=k<=last)
    if len(keys)<minimum:raise RuntimeError(f"{code}: only {len(keys)} valid days, expected >{minimum}")
    if keys[0]>first:raise RuntimeError(f"{code}: first trading day too late {keys[0]}")
    if (date.fromisoformat(last)-date.fromisoformat(keys[-1])).days>12:raise RuntimeError(f"{code}: stale newest price {keys[-1]}")
    gaps=[(b-a).days for a,b in zip(map(date.fromisoformat,keys),map(date.fromisoformat,keys[1:]))]
    if max(gaps)>24:raise RuntimeError(f"{code}: unexplained calendar gap {max(gaps)} days")
    returns=[quotes[b]["close"]/quotes[a]["close"]-1 for a,b in zip(keys,keys[1:])]
    if any(abs(r)>0.48 for r in returns):raise RuntimeError(f"{code}: possible unadjusted split/outlier")
    return {"count":len(keys),"first":keys[0],"last":keys[-1],"largestGapDays":max(gaps),"largestAbsReturnPct":round(max(map(abs,returns))*100,3)}

def synthesize_685(index,real):
    fst=min(real); ix=sorted(index)
    if fst not in index:raise RuntimeError("00685L first listing date missing from TWII")
    j=ix.index(fst); factor=1+2*(index[ix[j]]/index[ix[j-1]]-1)-SYNTH_FEE
    px=real[fst]["close"]/factor
    synthetic={}
    for k in range(j-1,-1,-1):
        d=ix[k]
        synthetic[d]={"open":px,"close":px,"synthetic":True}
        if k>0:
            ret=index[d]/index[ix[k-1]]-1
            px/=max(.05,1+2*ret-SYNTH_FEE)
    for k in range(len(ix)-1):
        d=ix[k]
        if d in synthetic:
            synthetic[d]["open"]=synthetic[ix[k-1]]["close"] if k>0 and ix[k-1] in synthetic else synthetic[d]["close"]
    return {**synthetic,**real}

def signals(index):
    ix=sorted(index);out={};below=0
    for k,d in enumerate(ix):
        if k<9:continue
        ma=sum(index[t] for t in ix[k-9:k+1])/10
        below=below+1 if index[d]<.98*ma else 0
        out[d]={"ma":ma,"below":below,"sell":below>=3,"buy":index[d]>1.01*ma}
    return out

def test(quotes,index,period_start,end,mode):
    dates=sorted(k for k in quotes if period_start<=k<=end)
    if len(dates)<50:raise RuntimeError(f"{mode} {period_start}: too few dates")
    idxs=sorted(index); sig=signals(index)
    balance=INITIAL; shares=0; peak=INITIAL; mdd=0.; sells=0;buys=0; cash_days=0
    curve=[];trades=[];annual={};initialized=False;prev_market_day=None
    for d in dates:
        q=quotes[d]; open_=q["open"]; close_=q["close"]
        # Signals are evaluated at the previous index trading session's close; no close-to-open look-ahead.
        while prev_market_day is None or prev_market_day<d:
            previous=[x for x in idxs if x<d]
            prev_market_day=previous[-1] if previous else None
            break
        action=None
        if not initialized:
            action="BUY";initialized=True
        elif mode=="MA10" and prev_market_day in sig:
            signal=sig[prev_market_day]
            if shares>0 and signal["sell"]:action="SELL"
            elif shares==0 and signal["buy"]:action="BUY"
        if action=="SELL":
            execution=open_*(1-SLIPPAGE)
            balance+=shares*execution*(1-BROKER-SELL_TAX)
            trades.append({"date":d,"side":"SELL","price":round(execution,5),"shares":shares,"synthetic":bool(q["synthetic"])})
            shares=0;sells+=1
        elif action=="BUY" and shares==0:
            execution=open_*(1+SLIPPAGE)
            size=math.floor(balance*ALLOCATION/(execution*(1+BROKER)))
            if size>0:
                balance-=size*execution*(1+BROKER);shares=size;buys+=1
                trades.append({"date":d,"side":"BUY","price":round(execution,5),"shares":shares,"synthetic":bool(q["synthetic"])})
        if shares==0:cash_days+=1
        equity=balance+shares*close_
        if not math.isfinite(equity) or equity<=0:raise RuntimeError("bad NAV")
        peak=max(peak,equity);mdd=min(mdd,(equity/peak-1)*100)
        curve.append([d,round(equity,2)]);annual[d[:4]]=equity
    end_equity=curve[-1][1]
    yearly=[];prior=INITIAL
    for y,v in sorted(annual.items()):
        yearly.append({"year":int(y),"returnPct":round((v/prior-1)*100,3),"equityTWD":round(v,2)})
        prior=v
    # 2 trading-day sampling for lightweight GitHub Pages; full yearly and trading stats retained.
    sampled=curve[::2]
    if sampled[-1][0]!=curve[-1][0]:sampled.append(curve[-1])
    return {"first":dates[0],"last":dates[-1],"sessions":len(dates),"initialTWD":INITIAL,
            "endTWD":end_equity,"returnPct":round((end_equity/INITIAL-1)*100,3),
            "maxDrawdownPct":round(mdd,3),"buys":buys,"sells":sells,"cashDays":cash_days,
            "syntheticDays":sum(quotes[d]["synthetic"] for d in dates),
            "annual":yearly,"curve":sampled,"trades":trades}

def main():
    p=argparse.ArgumentParser();p.add_argument("--end",default=date.today().isoformat());a=p.parse_args()
    end=a.end
    if end<"2026-07-07":raise RuntimeError("expected both 2026 split events for this version")
    print("Fetching TWSE data: 00631L / 00685L / TAIEX",flush=True)
    index=get_index("2014-10-01",end)
    q631=get_quotes("00631L",START,end)
    q685=get_quotes("00685L",FIRST685,end)
    checks={"twii":{"count":len(index),"first":min(index),"last":max(index)},
            "00631L":continuity(q631,START,2500,"00631L",end),
            "00685L":continuity(q685,FIRST685,1900,"00685L",end)}
    if index[max(index)]<=0 or (date.fromisoformat(end)-date.fromisoformat(max(index))).days>12:raise RuntimeError("TWII stale")
    q685full=synthesize_685(index,q685)
    pairs={"2014_common":{"00631L":q631,"00685L":q685full,"start":START},
           "2017_real":{"00631L":q631,"00685L":q685,"start":FIRST685}}
    periods={}
    for name,item in pairs.items():
        periods[name]={"start":item["start"],"end":end,"isCounterfactual":name=="2014_common","models":{}}
        for code in ("00631L","00685L"):
            periods[name]["models"][code]={k:test(item[code],index,item["start"],end,k) for k in ("MA10","HOLD")}
            print(name,code,{k:(v["endTWD"],v["returnPct"]) for k,v in periods[name]["models"][code].items()},flush=True)
    output={"version":"1.0","generatedUTC":datetime.utcnow().isoformat()+"Z","priceThrough":max(min(checks[k]["last"] for k in ("00631L","00685L")),min(index)),
            "dataSources":["TWSE STOCK_DAY monthly OHLC","TWSE FMTQIK TAIEX daily close"],
            "listing":{"00631L":"2014-10-31","00685L":"2017-03-30"},
            "splits":{"00631L":{"ratio":22,"resume":"2026-03-31"},"00685L":{"ratio":24,"resume":"2026-07-07"}},
            "strategy":{"signal":"TAIEX SMA10 (not ETF price SMA10), including current-day index close",
                        "exit":"Three consecutive trading day closes below 0.98*SMA10; execute next tradable ETF open",
                        "entry":"First index close above 1.01*SMA10; execute next tradable ETF open",
                        "initialBuy":"First period trading session open","allocation":ALLOCATION,"commissionEachSide":BROKER,
                        "slippageEachSide":SLIPPAGE,"sellTax":SELL_TAX,
                        "synthetic":"00685L before 2017-03-30: daily 2x TAIEX return minus illustrative 0.34%/252 daily fee, backward-anchored to first real close, approximate open=previous synthetic close. Hypothetical, not executable."},
            "dataQuality":checks,"periods":periods}
    OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(output,ensure_ascii=False,separators=(",",":")))
    print("WROTE",OUT,OUT.stat().st_size,flush=True)

if __name__=="__main__":main()
