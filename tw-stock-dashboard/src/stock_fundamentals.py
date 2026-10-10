"""個股體檢公開 MOPS 財報因子：累計 EPS / 月營收 / TTM PE 與有限歷史估值分位。
本資料源為 MOPS 歷史修訂版，公布日採保守規則代理；不是原始當日不可變快照。
財務欄位缺值必須是 None，不填零、不用財報季末日冒充可用日。
"""
from __future__ import annotations
import bisect,json,math
from collections import defaultdict
from datetime import date
from pathlib import Path
from n_fundamental_archive import month_safe_date,quarter_safe_date

def val(x):
    try:
        y=float(x)
        return y if math.isfinite(y) else None
    except (TypeError,ValueError):return None

def pct(a,b):
    return round(100*(a/b-1),2) if a is not None and b is not None and b>0 else None

def _previous_month(y,m):
    return (y-1,12) if m==1 else (y,m-1)

def _previous_quarter(y,q):
    return (y-1,4) if q==1 else (y,q-1)

class MopsArchive:
    def __init__(self,revenue,eps):
        self.months=defaultdict(dict);self.quarters=defaultdict(dict)
        for r in revenue:
            try:
                code=str(r["code"]);market=str(r["market"]);y=int(r["year"]);m=int(r["month"])
                v=val(r["revenue"]);available=str(r["availableFrom"])
                if market not in ("sii","otc") or not code.isdigit() or not 1<=m<=12 or v is None or v<0 or available!=month_safe_date(y,m):continue
                k=(market,code);period=(y,m)
                old=self.months[k].get(period)
                if old is not None and old["value"]!=v:raise ValueError("duplicate revenue conflict "+str(k)+str(period))
                self.months[k][period]={"value":v,"available":available}
            except (KeyError,TypeError,ValueError) as ex:
                if "conflict" in str(ex):raise
                continue
        for r in eps:
            try:
                code=str(r["code"]);market=str(r["market"]);y=int(r["year"]);q=int(r["quarter"])
                v=val(r["epsYtd"]);available=str(r["availableFrom"])
                if market not in ("sii","otc") or not code.isdigit() or not 1<=q<=4 or v is None or not -300<=v<=300 or available!=quarter_safe_date(y,q):continue
                k=(market,code);period=(y,q)
                old=self.quarters[k].get(period)
                if old is not None and old["value"]!=v:raise ValueError("duplicate EPS conflict "+str(k)+str(period))
                self.quarters[k][period]={"value":v,"available":available}
            except (KeyError,TypeError,ValueError) as ex:
                if "conflict" in str(ex):raise
                continue
        self.rev_index={k:sorted((r["available"],y,m) for (y,m),r in v.items()) for k,v in self.months.items()}
        self.eps_index={k:sorted((r["available"],y,q) for (y,q),r in v.items()) for k,v in self.quarters.items()}
    def _latest(self,idx,key,day):
        values=idx.get(key,())
        i=bisect.bisect_right(values,(day,9999,99))-1
        return (values[i][1],values[i][2]) if i>=0 else None
    def _standalone(self,qmap,y,q,day):
        current=qmap.get((y,q))
        if current is None or current["available"]>day:return None
        if q==1:return current["value"]
        prev=qmap.get((y,q-1))
        return current["value"]-prev["value"] if prev is not None and prev["available"]<=day else None
    def ttm(self,key,day):
        qmap=self.quarters.get(key,{})
        latest=self._latest(self.eps_index,key,day)
        if latest is None:return None
        newest=qmap[latest]
        if (date.fromisoformat(day)-date.fromisoformat(newest["available"])).days>245:return None
        seq=[];period=latest
        for _ in range(4):
            y,q=period
            v=self._standalone(qmap,y,q,day)
            if v is None:return None
            seq.append(v);period=_previous_quarter(y,q)
        return round(sum(seq),3)
    def profile(self,market,code,day,price,history=None):
        key=("sii" if market=="上市" else "otc",str(code))
        rmap=self.months.get(key,{});qmap=self.quarters.get(key,{})
        z={"revenueFiscal":None,"revenueAvailableFrom":None,"revenueYi":None,"revenueMoMPct":None,
            "revenueYoYPct":None,"revenue12mHighRatioPct":None,
            "epsFiscal":None,"epsAvailableFrom":None,"epsYtd":None,"epsYtdYoYPct":None,
            "epsTurnaround":False,"ttmEPS":None,"peTTM":None,"earningsYieldPct":None,
            "peHistoryPercentile120D":None,"peHistorySamples":0,"roePct":None}
        rm=self._latest(self.rev_index,key,day)
        if rm:
            r=rmap[rm];age=(date.fromisoformat(day)-date.fromisoformat(r["available"])).days
            if age<=80:
                y,m=rm;v=r["value"];last=rmap.get(_previous_month(y,m));year=rmap.get((y-1,m))
                z.update(revenueFiscal=f"{y}-{m:02d}",revenueAvailableFrom=r["available"],
                    revenueYi=round(v/100000,3),revenueMoMPct=pct(v,last["value"]) if last and last["available"]<=day else None,
                    revenueYoYPct=pct(v,year["value"]) if year and year["available"]<=day else None)
                vals=[];p=(y,m)
                for _ in range(12):
                    x=rmap.get(p)
                    if x is None or x["available"]>day:break
                    vals.append(x["value"]);p=_previous_month(*p)
                if len(vals)==12 and max(vals)>0:z["revenue12mHighRatioPct"]=round(v/max(vals)*100,2)
        eq=self._latest(self.eps_index,key,day)
        if eq:
            q=qmap[eq];age=(date.fromisoformat(day)-date.fromisoformat(q["available"])).days
            if age<=245:
                y,qu=eq;v=q["value"];older=qmap.get((y-1,qu))
                growth=pct(v,older["value"]) if older and older["available"]<=day else None
                turn=bool(older and older["available"]<=day and older["value"]<=0<v)
                z.update(epsFiscal=f"{y}Q{qu}",epsAvailableFrom=q["available"],
                         epsYtd=round(v,3),epsYtdYoYPct=growth,epsTurnaround=turn)
                ttm=self.ttm(key,day);z["ttmEPS"]=ttm
                if ttm is not None and ttm>0 and price is not None and price>0:
                    z["peTTM"]=round(price/ttm,2)
                    z["earningsYieldPct"]=round(100*ttm/price,2)
        if z["peTTM"] is not None and history is not None and len(history)>=60:
            hist=[]
            # Use only prior completed sessions and conservative quarter-availability dates.
            for dt,px in history[-120:]:
                p=val(px)
                if p is None or p<=0 or str(dt)>day:continue
                eps4=self.ttm(key,str(dt))
                if eps4 is not None and eps4>0:hist.append(p/eps4)
            if len(hist)>=60:
                cur=price/z["ttmEPS"]
                z["peHistoryPercentile120D"]=round(100*(sum(v<cur for v in hist)+.5*sum(v==cur for v in hist))/len(hist),1)
                z["peHistorySamples"]=len(hist)
        return z

def read_archive(data_dir):
    folder=Path(data_dir)/"research"/"n_canslim"
    try:
        coverage=json.loads((folder/"fundamental_coverage.json").read_text(encoding="utf-8"))
        if coverage.get("failures") or coverage.get("revenueRows",0)<20000 or coverage.get("epsRows",0)<5000:
            return None,"歷史 MOPS 檢驗失敗或資料涵蓋率不足"
        revenue=json.loads((folder/"monthly_revenue.json").read_text(encoding="utf-8"))
        eps=json.loads((folder/"eps_ytd.json").read_text(encoding="utf-8"))
        if not isinstance(revenue,list) or not isinstance(eps,list) or len(revenue)!=coverage["revenueRows"] or len(eps)!=coverage["epsRows"]:
            return None,"營收/EPS 筆數與 MOPS 完整性報告不一致"
        return MopsArchive(revenue,eps),None
    except (OSError,ValueError,KeyError,TypeError) as ex:
        return None,"歷史 MOPS 資料不可用："+str(ex)[:200]

def enrich_profiles(payload,data_dir,histories):
    archive,error=read_archive(data_dir)
    payload["schema"]="stock-diagnostics-v2"
    payload["method"]["finance"]="官方 MOPS 歷史修訂版；月營收單位千元、表內換算億元，EPS 為年度累計，TTM 為最近4個已公告完整季度拆分後相加。公布日採保守延後日期代理，非確切首次公布日。"
    payload["method"]["peHistory"]="僅最近120個有快取行情的交易日、且當日已有可用 TTM EPS 的本益比歷史分位；越低相對過去越便宜。非多年估值百分位，未校正所有股本變動。"
    payload["method"]["roe"]="目前無經過驗證的股東權益季資料，ROE 保持 null，不得以 EPS 假算。"
    cov=payload["coverage"]
    cov.update({"financialsIncluded":archive is not None,"revenueAvailable":0,"epsAvailable":0,"peAvailable":0,"peHistoryAvailable":0,
                "roeAvailable":0,"financialArchiveStatus":"ok" if archive else "missing","financialArchiveError":error})
    if archive is None:return payload
    for row in payload["stocks"]:
        symbol=row["code"]+(".TW" if row["market"]=="上市" else ".TWO")
        h=histories.get(symbol)
        hist=None
        if h is not None and not h.empty:
            hist=list(zip(h["date"].astype(str).iloc[-120:],h["close"].iloc[-120:]))
        row.update(archive.profile(row["market"],row["code"],payload["dataDate"],row["close"],hist))
    for key,out,rev in (("revenueYoYPct","revenueGrowthP",False),("epsYtdYoYPct","epsGrowthP",False),("peTTM","peCheapP",True)):
        from stock_diagnostics import _percentiles
        _percentiles(payload["stocks"],key,out,rev)
    for row in payload["stocks"]:
        p=[row.get(k) for k in ("revenueGrowthP","epsGrowthP") if row.get(k) is not None]
        row["financialGrowthScore"]=round(sum(p)/len(p),1) if len(p)==2 else None
        cov["revenueAvailable"]+=row["revenueYi"] is not None
        cov["epsAvailable"]+=row["epsYtd"] is not None
        cov["peAvailable"]+=row["peTTM"] is not None
        cov["peHistoryAvailable"]+=row["peHistoryPercentile120D"] is not None
    return payload
