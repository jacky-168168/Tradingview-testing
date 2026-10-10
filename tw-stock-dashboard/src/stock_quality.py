"""ROE/PB official archival factors. Null means unverified, never estimated."""
import bisect,json,math
from collections import defaultdict
from datetime import date,timedelta
from pathlib import Path
from n_fundamental_archive import quarter_safe_date

def number(x):
    try:
        n=float(x)
        return n if math.isfinite(n) else None
    except (TypeError,ValueError):return None

class QualityIndex:
    def __init__(self,pb=(),roe=()):
        self.pb=defaultdict(dict);self.roe=defaultdict(dict)
        for z in pb:
            m,c,d=str(z["market"]),str(z["code"]),date.fromisoformat(z["date"]).isoformat()
            v=number(z["pb"]);src=z["source"]
            if m not in ("sii","otc") or not c.isdigit() or src!=("TWSE_BWIBBU_d" if m=="sii" else "TPEX_peQryDate") or v is None or not .03<=v<=200:raise ValueError("bad PB record")
            old=self.pb[(m,c)].get(d)
            if old is not None and old!=v:raise ValueError("conflicting PB record")
            self.pb[(m,c)][d]=v
        for z in roe:
            m,c=str(z["market"]),str(z["code"]);y,q=int(z["year"]),int(z["quarter"])
            a=date.fromisoformat(z["availableFrom"]).isoformat()
            p,now,prior=[number(z[k]) for k in ("netIncomeTTM","equityNow","equityYearAgo")]
            if m not in ("sii","otc") or not c.isdigit() or not 1<=q<=4 or a<quarter_safe_date(y,q):raise ValueError("bad ROE time")
            if z["source"]!="MOPS_CONSOLIDATED_QUARTER" or z["equityScope"]!="consolidated_total" or z["netIncomeScope"]!="consolidated_total":raise ValueError("inconsistent ROE accounting scope")
            if any(v is None for v in (p,now,prior)) or now<=0 or prior<=0:raise ValueError("bad ROE amount")
            ratio=100*p/((now+prior)/2)
            if not -200<=ratio<=300:raise ValueError("bad ROE ratio")
            item={"available":a,"roe":round(ratio,2),"fiscal":f"{y}Q{q}"}
            old=self.roe[(m,c)].get((y,q))
            if old is not None and old!=item:raise ValueError("conflicting ROE record")
            self.roe[(m,c)][(y,q)]=item
        self.pbkeys={k:sorted(v) for k,v in self.pb.items()}
        self.roekeys={k:sorted((v["available"],f"{y}Q{q}",v) for (y,q),v in items.items()) for k,items in self.roe.items()}
    def at(self,market,code,asof):
        day=date.fromisoformat(asof);key=(market,str(code))
        out={"pbRatio":None,"pbAsOf":None,"pbHistoryPercentile3Y":None,"pbHistorySamples":0,"roePct":None,"roeFiscal":None,"roeAvailableFrom":None}
        d=self.pbkeys.get(key,[]);idx=bisect.bisect_right(d,asof)
        if idx and (day-date.fromisoformat(d[idx-1])).days<=7:
            last=d[idx-1];pb=self.pb[key][last];out.update(pbRatio=round(pb,3),pbAsOf=last)
            lo=(day-timedelta(days=1098)).isoformat()
            vals=[self.pb[key][k] for k in d[:idx] if k>=lo]
            if len(vals)>=120:
                out["pbHistorySamples"]=len(vals)
                out["pbHistoryPercentile3Y"]=round(100*(sum(v<pb for v in vals)+.5*sum(v==pb for v in vals))/len(vals),1)
        q=self.roekeys.get(key,[])
        j=bisect.bisect_right(q,(asof,"9999Q4",{}))
        if j:
            a,f,item=q[j-1]
            if (day-date.fromisoformat(a)).days<=260:
                out.update(roePct=item["roe"],roeFiscal=f,roeAvailableFrom=a)
        return out

def enrich_quality(payload,data_dir):
    root=Path(data_dir)/"research"/"quality"
    errors=[];loaded={}
    for key,file in (("pb","pb_daily.json"),("roe","roe_quarter.json")):
        try:
            v=json.loads((root/file).read_text(encoding="utf-8"))
            if not isinstance(v,list):raise ValueError("expected JSON array")
            loaded[key]=v
        except (OSError,ValueError) as ex:errors.append(key+": "+str(ex)[:100]);loaded[key]=[]
    try:idx=QualityIndex(loaded["pb"],loaded["roe"])
    except (ValueError,KeyError,TypeError) as ex:idx=None;errors.append("validation: "+str(ex))
    cov=payload.setdefault("coverage",{})
    cov.update(pbAvailable=0,pbHistoryAvailable=0,roeAvailable=0,qualityArchiveStatus="ok" if not errors else "partial" if idx else "missing",qualityArchiveErrors=errors)
    payload.setdefault("method",{})["quality"]="ROE＝已公告同口徑近四季合計稅後淨利÷兩期平均權益；PB＝官方每日股價淨值比。欠缺官方歷史資料則為空值；歷史修訂財報不等於原始公告快照。"
    for row in payload.get("stocks",[]):
        q=idx.at("sii" if row.get("market")=="上市" else "otc",row["code"],payload["dataDate"]) if idx else {"roePct":None,"pbRatio":None,"pbAsOf":None,"pbHistoryPercentile3Y":None,"pbHistorySamples":0,"roeFiscal":None,"roeAvailableFrom":None}
        row.update(q)
        cov["roeAvailable"]+=q["roePct"] is not None
        cov["pbAvailable"]+=q["pbRatio"] is not None
        cov["pbHistoryAvailable"]+=q["pbHistoryPercentile3Y"] is not None
    return payload
