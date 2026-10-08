from __future__ import annotations
import argparse,json,time
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import numpy as np,pandas as pd
from config import DATA_DIR,MAX_CAPITAL_B,MIN_PRICE,MIN_TURNOVER_M,BENCHMARK,RISK_ON,RISK_STRONG,RISK_OFF
from pipeline import load_universe
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import precompute_features,score_a,score_d,d_pass,sort_key
from institution import fetch_many
from edge import build as build_edge
from risk import build_historical,f_gate
from sar import parabolic_sar
H=[1,3,5,10,20]
BUY_FEE_PCT=.1425;SELL_FEE_PCT=.1425;SELL_TAX_PCT=.30

def stat(a):
    a=sorted(float(x) for x in a if x is not None and np.isfinite(x))
    if not a:return {"n":0,"avg":None,"median":None,"win":None,"max":None,"min":None}
    return {"n":len(a),"avg":round(float(np.mean(a)),2),"median":round(float(np.median(a)),2),"win":round(sum(x>0 for x in a)/len(a)*100,1),"max":round(a[-1],2),"min":round(a[0],2)}

def num(v,d=0.0):
    try:
        x=float(v);return x if np.isfinite(x) else d
    except:return d

def metrics(r):
    ks=["close","dayRet","ret5","ret20","ma20","ma60","ma20Slope","rvol","rvol10","mom10Pct","ema20","ema50","ema20Slope5","prevHigh20","breakoutPct","atrPct","volD","closePosition","volume"]
    return {k:num(r.get(k)) for k in ks}

def _base_sort_a(r):return (-r["baseScore"],-r["rs20"],-r["rvol"],-r["ret20"],-r["turnoverB"])
def _final_sort_a(r):return (-r["total"],-r.get("sarBonus",0),-r["rs20"],-r["rvol"],-r["ret20"],-r["turnoverB"])

def _adj_price(row,field):
    raw=num(row.get(field),None);close=num(row.get("close"),None);adj=num(row.get("adjclose"),None)
    if raw is None:return None
    if close and adj and close>0:return raw*(adj/close)
    return raw

def _has_unadjusted_scale_jump(px,start_date,end_date):
    if px is None or px.empty:return False
    q=px[(px["date"].astype(str)>=start_date)&(px["date"].astype(str)<=end_date)].copy()
    if len(q)<2:return False
    # 若全段已有 adjusted close，就由 adjustment factor 處理；否則擋掉明顯非一般漲跌停可造成的價格尺度跳變。
    if "adjclose" in q.columns and q["adjclose"].notna().all():return False
    c=pd.to_numeric(q["close"],errors="coerce").dropna()
    if len(c)<2:return False
    ratio=c/c.shift(1)
    return bool(((ratio<0.55)|(ratio>1.80)).fillna(False).any())

def _historical_sar_bonus(px,date):
    if px is None or px.empty:return 0
    q=px[px["date"].astype(str)<=date].tail(100)
    if len(q)<30:return 0
    x=parabolic_sar(q[["date","open","high","low","close","volume"]])
    if not x or not x.get("bullish"):return 0
    t=int(x.get("trendBars",1));return 5 if t==1 else 4 if t==2 else 3 if t==3 else 2 if t==4 else 1 if t in (5,6) else 0

def _portfolio_stats(signals,idx,pos,ranks,prices,model,h):
    equity=1.0;curve=[];cohort=[];invested=0
    for si in range(0,len(signals),max(1,h)):
        d=signals[si];sip=pos.get(d)
        if sip is None or sip+1>=len(idx) or sip+h>=len(idx):continue
        buydate=str(idx.iloc[sip+1].date);exitdate=str(idx.iloc[sip+h].date);positions=[]
        for p in ranks[model].get(d,[])[:3]:
            px=prices.get(to_symbol(p["code"],p["market"]))
            if px is None or buydate not in px.index:continue
            if _has_unadjusted_scale_jump(px.reset_index(drop=True),buydate,exitdate):continue
            q=px.loc[buydate];q=q.iloc[-1] if isinstance(q,pd.DataFrame) else q;bo=_adj_price(q,"open")
            if bo and bo>0:positions.append((px,bo))
        start_eq=equity
        if positions:invested+=1
        for ti in range(sip+1,sip+h+1):
            td=str(idx.iloc[ti].date)
            if not positions:
                val=start_eq
            else:
                ratios=[]
                for px,bo in positions:
                    q=px[px["date"].astype(str)<=td].tail(1)
                    if q.empty:continue
                    ec=_adj_price(q.iloc[-1],"close")
                    if ec and ec>0:ratios.append(ec/bo)
                val=start_eq if not ratios else start_eq*(1-BUY_FEE_PCT/100)*(sum(ratios)/len(ratios))
                if ti==sip+h and ratios:val*=1-(SELL_FEE_PCT+SELL_TAX_PCT)/100
            curve.append({"date":td,"equity":val});equity=val if ti==sip+h else equity
        cohort.append((equity/start_eq-1)*100 if start_eq>0 else 0)
    if not curve:return {"horizon":h,"periods":0,"investedPeriods":0,"totalReturn":0,"cagr":0,"sharpe":None,"maxDrawdown":0,"winRate":None,"avgNet":None,"costPct":round(BUY_FEE_PCT+SELL_FEE_PCT+SELL_TAX_PCT,4)}
    vals=[float(x["equity"]) for x in curve];rets=[vals[i]/vals[i-1]-1 for i in range(1,len(vals)) if vals[i-1]>0]
    peak=vals[0];mdd=0.0
    for v in vals:peak=max(peak,v);mdd=max(mdd,(peak-v)/peak*100 if peak else 0)
    days=max(1,len({x["date"] for x in curve}));cagr=(equity**(252/days)-1)*100 if equity>0 else -100
    sh=None
    if len(rets)>1:
        sd=float(np.std(rets,ddof=1))
        if sd>0:sh=float(np.mean(rets)/sd*np.sqrt(252))
    active=[x for x in cohort if abs(x)>1e-12]
    return {"horizon":h,"periods":len(cohort),"investedPeriods":invested,"totalReturn":round((equity-1)*100,2),"cagr":round(cagr,2),"sharpe":None if sh is None else round(sh,2),"maxDrawdown":round(mdd,2),"winRate":None if not active else round(sum(x>0 for x in active)/len(active)*100,1),"avgNet":None if not active else round(float(np.mean(active)),2),"costPct":round(BUY_FEE_PCT+SELL_FEE_PCT+SELL_TAX_PCT,4)}

def rankings(universe,market_universe,hist,index_df,inst,inst_errors,start,end):
    idx=index_df.copy().sort_values("date").reset_index(drop=True);idx["close"]=pd.to_numeric(idx.close,errors="coerce")
    dates=idx.date.astype(str).tolist();pos={d:i for i,d in enumerate(dates)};signals=[d for d in dates if start<=d<=end]
    feats={};prices={}
    needed={to_symbol(s["code"],s["market"]) for s in market_universe}
    for s in market_universe:
        sym=to_symbol(s["code"],s["market"]);df=hist.get(sym)
        if df is None or len(df)<25:continue
        prices[sym]=df.sort_values("date").set_index("date",drop=False)
        if sym in needed:feats[sym]=precompute_features(df).set_index("date",drop=False)
    ranks={"A":{},"D":{},"F":{}};cand={"A":{},"D":{},"F":{}};regimes={}
    selection_keys={f'{x["market"]}_{x["code"]}':x for x in universe}
    for n,d in enumerate(signals,1):
        ip=pos[d]
        if ip<25:continue
        market20=(float(idx.loc[ip,"close"])/float(idx.loc[ip-20,"close"])-1)*100;rows={"A":[],"D":[]};iday=inst.get(d,{})
        inst_ok=d not in inst_errors and bool(iday);up=down=0;foreign_value=0.0
        # 重建 Dashboard 的 breadth / 外資方向：使用當日可取得的上市股票資料，不使用未來資料。
        for s in market_universe:
            if s["market"]!="上市":continue
            sym=to_symbol(s["code"],s["market"]);ft=feats.get(sym)
            if ft is None or d not in ft.index:continue
            rr=ft.loc[d];rr=rr.iloc[-1] if isinstance(rr,pd.DataFrame) else rr
            dr=num(rr.get("dayRet"),0)
            if dr>0:up+=1
            elif dr<0:down+=1
            if inst_ok:
                ii=iday.get(f'上市_{s["code"]}',{});foreign_value+=num(ii.get("foreign"),0)*num(rr.get("close"),0)/100_000_000
        breadth=up/(up+down)*100 if up+down else 50.0
        rrisk=build_historical(idx.iloc[:ip+1],breadth,foreign_value,RISK_ON,RISK_STRONG,RISK_OFF);gate=f_gate(rrisk,RISK_ON);rrisk["fAllowed"]=gate["allowed"];rrisk["fReason"]=gate["reason"];rrisk["institutionAvailable"]=inst_ok;regimes[d]=rrisk
        for s in universe:
            sym=to_symbol(s["code"],s["market"]);ft=feats.get(sym)
            if ft is None or d not in ft.index:continue
            rr=ft.loc[d];rr=rr.iloc[-1] if isinstance(rr,pd.DataFrame) else rr
            if pd.isna(rr.get("ret20")) or pd.isna(rr.get("ma20")) or pd.isna(rr.get("ema50")):continue
            m=metrics(rr)
            if m["close"]<MIN_PRICE:continue
            rs=m["ret20"]-market20;turn=m["close"]*m["volume"]/100_000_000;base={"code":s["code"],"name":s["name"],"market":s["market"],"close":m["close"],"ret5":m["ret5"],"ret20":m["ret20"],"rs20":rs,"rvol":m["rvol"],"rvol10":m["rvol10"],"mom10Pct":m["mom10Pct"],"volD":m["volD"],"breakoutPct":m["breakoutPct"],"closePosition":m["closePosition"],"turnoverB":turn,"institutionAvailable":inst_ok}
            ii=iday.get(f'{s["market"]}_{s["code"]}',{}) if inst_ok else {}
            if turn*100>=MIN_TURNOVER_M:
                z=score_a(m,rs,ii);rows["A"].append({**base,**z,"baseScore":z["total"],"model":"A","sarBonus":0})
            if d_pass(m):
                z=score_d(m,rs,ii);rows["D"].append({**base,**z,"baseScore":z["total"],"model":"D"})
        rows["A"].sort(key=_base_sort_a)
        # 正式 A 版以 SAR bonus 作同分排序；只需計算前段候選即可覆蓋最終 Top3。
        for x in rows["A"][:50]:
            x["sarBonus"]=_historical_sar_bonus(prices.get(to_symbol(x["code"],x["market"])),d)
        rows["A"].sort(key=_final_sort_a);rows["D"].sort(key=sort_key)
        cand["A"][d]=len(rows["A"]);cand["D"][d]=len(rows["D"])
        ranks["A"][d]=[{**x,"rank":i+1} for i,x in enumerate(rows["A"][:3])]
        ranks["D"][d]=[{**x,"rank":i+1} for i,x in enumerate(rows["D"][:3])]
        frows=[]
        if gate["allowed"]:
            limit=3 if gate["exception"] else 3
            for i,x in enumerate(rows["D"][:limit]):frows.append({**x,"model":"F","rank":i+1,"fReason":gate["reason"]})
        ranks["F"][d]=frows;cand["F"][d]=(min(len(rows["D"]),3) if gate["allowed"] else 0)
        if n%10==0 or n==len(signals):print(f"rank {n}/{len(signals)} {d} risk={rrisk.get('score')} F={gate['reason']} D={len(rows['D'])}",flush=True)
    return signals,idx,pos,ranks,cand,prices,regimes

def evaluate(signals,idx,pos,ranks,cand,prices,regimes):
    models={};edgein={}
    for model in ["A","D","F"]:
        rb={h:{1:[],2:[],3:[]} for h in H};avail={h:[] for h in H};fixed={h:[] for h in H};dated={h:[] for h in H};sig=[]
        for d in signals:
            sip=pos.get(d)
            if sip is None or sip+1>=len(idx):continue
            buydate=str(idx.iloc[sip+1].date);day={h:[] for h in H};rg=regimes.get(d,{})
            for p in ranks[model].get(d,[]):
                sym=to_symbol(p["code"],p["market"]);px=prices.get(sym);bo=None;buyrow=None
                if px is not None and buydate in px.index:
                    q=px.loc[buydate];q=q.iloc[-1] if isinstance(q,pd.DataFrame) else q;buyrow=q;bo=_adj_price(q,"open")
                rec={"model":model,"signalDate":d,"rank":p["rank"],"code":p["code"],"name":p["name"],"market":p["market"],"score":round(p["total"],2),"buyDate":buydate,"buyOpen":round(bo,4) if bo else None,"ret5Signal":round(p["ret5"],2),"ret20Signal":round(p["ret20"],2),"breakoutPct":round(p["breakoutPct"],2),"rvol":round(p["rvol"],2),"rvol10":round(p["rvol10"],2),"mom10Pct":round(p["mom10Pct"],2),"volD":round(p["volD"],2),"marketRiskScore":rg.get("score"),"marketState":rg.get("state"),"reversalState":rg.get("activeState"),"fReason":p.get("fReason")}
                for h in H:
                    target=sip+h;r=None
                    if bo and target<len(idx):
                        ed=str(idx.iloc[target].date)
                        if px is not None and ed in px.index and not _has_unadjusted_scale_jump(px.reset_index(drop=True),buydate,ed):
                            q=px.loc[ed];q=q.iloc[-1] if isinstance(q,pd.DataFrame) else q;ec=_adj_price(q,"close")
                            if ec:r=round((ec/bo-1)*100,2);day[h].append(r);rb[h][p["rank"]].append(r)
                    rec[f"ret{h}"]=r
                sig.append(rec)
            for h in H:
                if sip+h>=len(idx):continue
                if day[h]:avail[h].append(sum(day[h])/len(day[h]))
                x=sum(day[h])/3.0;fixed[h].append(x);dated[h].append({"date":d,"ret":x})
        summary=[{"group":f"Top{r}",**{f"d{h}":stat(rb[h][r]) for h in H}} for r in [1,2,3]]
        summary+=[{"group":"Top3可用等權",**{f"d{h}":stat(avail[h]) for h in H}},{"group":"Top3固定三槽",**{f"d{h}":stat(fixed[h]) for h in H}}]
        cc=list(cand[model].values());cs={"avg":round(float(np.mean(cc)),1) if cc else 0,"min":min(cc) if cc else 0,"max":max(cc) if cc else 0,"days3":sum(x>=3 for x in cc),"totalDays":len(cc)}
        name={"A":"原始版","D":"技術強勢","F":"D＋大盤濾網"}[model]
        portfolio={f"d{h}":_portfolio_stats(signals,idx,pos,ranks,prices,model,h) for h in H};models[model]={"id":model,"name":name,"summary":summary,"candidateStats":cs,"signals":sig,"portfolio":portfolio};edgein[model]=dated
    return [models["A"],models["D"],models["F"]],build_edge(edgein)

def run(start,end):
    t=time.time();sd=datetime.fromisoformat(start);ed=datetime.fromisoformat(end)
    if sd>ed:raise ValueError("start > end")
    if (ed.date()-sd.date()).days+1>731:raise ValueError("日期區間最多 731 天")
    today=datetime.now(ZoneInfo("Asia/Taipei")).date()
    if ed.date()>today:raise ValueError(f"結束日期不可晚於今天 {today.isoformat()}")
    fs=sd-timedelta(days=180);fe=min(datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None),ed+timedelta(days=50));all_u=load_universe();u=[x for x in all_u if 0<x.get("capitalB",0)<MAX_CAPITAL_B]
    # 市場 Risk 需要較完整的上市 breadth，因此 K 線快取涵蓋公司母檔；選股仍維持 <500億股本條件。
    print(f"universe={len(u)} marketUniverse={len(all_u)} fetch={fs.date()}..{fe.date()}",flush=True)
    hist,he=update_many([(x["code"],x["market"]) for x in all_u],fs,fe);_,ix,ie=update_symbol(BENCHMARK,fs,fe)
    if ie or ix is None or len(ix)<60:raise RuntimeError(f"benchmark unavailable: {ie}")
    sdts=[d for d in ix.date.astype(str) if start<=d<=end];inst,ine=fetch_many(sdts);sdts,idx,pos,ranks,cand,prices,regimes=rankings(u,all_u,hist,ix,inst,set(ine),start,end);models,edge=evaluate(sdts,idx,pos,ranks,cand,prices,regimes)
    gate_stats={"riskOnDays":sum(r.get("score",0)>=RISK_ON for r in regimes.values()),"strongBottomExceptionDays":sum(r.get("fReason")=="STRONG_BOTTOM_REVERSAL" for r in regimes.values()),"blockedDays":sum(not r.get("fAllowed") for r in regimes.values()),"allowedDays":sum(bool(r.get("fAllowed")) for r in regimes.values())}
    compact_regime=[{"date":d,"score":r.get("score"),"state":r.get("state"),"activeState":r.get("activeState"),"breadth":r.get("breadth"),"foreign":r.get("foreign"),"fAllowed":r.get("fAllowed"),"fReason":r.get("fReason"),"institutionAvailable":r.get("institutionAvailable")} for d,r in regimes.items()]
    out={"version":"PY-BT3-F-PORTFOLIO","generatedAt":datetime.now(ZoneInfo("Asia/Taipei")).isoformat(timespec="seconds"),"period":{"start":start,"end":end},"signalDays":len(sdts),"universeCount":len(u),"marketUniverseCount":len(all_u),"historySuccess":len(hist)-len(he),"historyErrors":len(he),"institutionErrors":len(ine),"models":models,"edgeAudit":edge,"marketGateStats":gate_stats,"marketRegime":compact_regime,"elapsedSeconds":round(time.time()-t,1),"notes":["F = D 技術強勢 + 大盤濾網；Risk Score >=60 才進場，Strong Bottom Reversal 為唯一例外。","歷史 Risk 依 Dashboard 權重重建：指數趨勢 + 上市 breadth + T86 外資淨買賣估值，不使用未來資料。","A 歷史排序補上 SAR bullish trend bonus 作同分排序，對齊正式版。","回測報酬優先使用 Yahoo adjusted close factor 修正公司行動；舊快取若尚無 adjclose，偵測極端單日價格尺度跳變並排除該筆報酬。","法人失敗日期會序列重試；仍失敗者標記 institutionAvailable=false，不再默認視為資料完整。","Yahoo K 使用雙向 Parquet 增量快取；舊快取若缺 adjusted close 會補抓本次所需區間一次，後續不重抓。","資金曲線採 Top3 等權、非重疊持有週期，逐日 mark-to-market，扣買賣手續費各0.1425%與賣出證交稅0.3%。","目前公司母檔仍以現存上市櫃公司為基礎，已上市但後續下市股票可能造成 survivorship bias，結果需保守解讀。"]}
    p=DATA_DIR/"backtest";p.mkdir(parents=True,exist_ok=True)
    body=json.dumps(out,ensure_ascii=False,indent=2);(p/"latest.json").write_text(body,encoding="utf-8")
    archive=f"{start}_{end}.json";(p/archive).write_text(body,encoding="utf-8")
    ip=p/"index.json"
    try:ixj=json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else []
    except:ixj=[]
    ixj=[x for x in ixj if x.get("file")!=archive];ixj.insert(0,{"file":archive,"start":start,"end":end,"generatedAt":out["generatedAt"],"signalDays":out["signalDays"],"elapsedSeconds":out["elapsedSeconds"]})
    ip.write_text(json.dumps(ixj[:50],ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"signalDays":out["signalDays"],"historyErrors":out["historyErrors"],"institutionErrors":out["institutionErrors"],"F":gate_stats,"elapsedSeconds":out["elapsedSeconds"],"archive":archive},ensure_ascii=False),flush=True);return out

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--start");ap.add_argument("--end");a=ap.parse_args();end=a.end or datetime.now().date().isoformat();start=a.start or (datetime.fromisoformat(end)-timedelta(days=180)).date().isoformat();run(start,end)
