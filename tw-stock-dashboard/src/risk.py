from __future__ import annotations
import math,re,requests
import numpy as np,pandas as pd
UA={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/3.0","Accept":"application/json"}

def _num(v):
    try:return float(str(v).replace(",","").strip() or 0)
    except:return 0.0

def _report(trade_date,path,params):
    """Never mix today's floating latest API data with an older Yahoo ^TWII bar."""
    if not isinstance(trade_date,str) or len(trade_date)!=10 or trade_date[4]!="-" or trade_date[7]!="-":
        raise ValueError("Explicit ISO trading date required for Risk Score")
    requested=trade_date.replace("-","")
    r=requests.get("https://www.twse.com.tw/rwd/zh/"+path,params={"response":"json",**params},headers=UA,timeout=25)
    r.raise_for_status();data=r.json()
    if data.get("stat")!="OK":raise RuntimeError("TWSE report not ready for "+trade_date+": "+str(data.get("stat")))
    # The report must belong to requested session. No implicit 'latest' fallback.
    reported=str(data.get("date") or "")
    if reported:
        compact=re.sub(r"[^0-9]","",reported)
        roc=str(int(trade_date[:4])-1911)+trade_date[5:7]+trade_date[8:10]
        if requested not in compact and roc not in compact and trade_date not in reported:
            raise RuntimeError("TWSE report date mismatch: "+reported+" != "+trade_date)
    return data

def breadth(trade_date):
    """TWSE MI_INDEX per-date 股票 column, excluding ETF and warrants."""
    j=_report(trade_date,"afterTrading/MI_INDEX",{"date":trade_date.replace("-",""),"type":"ALLBUT0999"})
    for tab in j.get("tables") or []:
        if "漲跌證券數合計" not in str(tab.get("title") or ""):continue
        fields=[str(x) for x in tab.get("fields") or []]
        if "股票" not in fields:continue
        col=fields.index("股票");up=down=None
        for row in tab.get("data") or []:
            label=str(row[0]) if row else ""
            if len(row)<=col:continue
            # E.g. "425(14)" counts 425 advancing stocks including 14 limit-up.
            value=str(row[col]).split("(",1)[0].replace(",","").strip()
            if label.startswith("上漲"):up=int(value)
            elif label.startswith("下跌"):down=int(value)
        if up is not None and down is not None and up+down>=400:return up,down
    raise RuntimeError("Missing date-specific TWSE stock breadth for "+trade_date)

def foreign_market_net(trade_date):
    """Date-pinned daily TWSE institutional flow; never take an unlabelled latest quote."""
    d=trade_date.replace("-","")
    j=_report(trade_date,"fund/BFI82U",{"dayDate":d,"type":"day"})
    for row in j.get("data") or []:
        if row and "外資" in str(row[0]) and "外資自營商" not in str(row[0]):
            return _num(row[-1])/100_000_000
    raise RuntimeError("Missing date-specific TWSE foreign net for "+trade_date)

def reversal(idx,ctx):
    closes=idx.close.astype(float).tolist();latest=idx.iloc[-1];prev=idx.iloc[-2];ma20=ctx["ma20"];dist=(float(latest.close)/ma20-1)*100 if ma20 else 0
    daily=[(closes[i]/closes[i-1]-1)*100 for i in range(1,len(closes))]
    recent_abs=float(np.mean(np.abs(daily[-5:]))) if daily[-5:] else 0;base_abs=float(np.mean(np.abs(daily[-25:-5]))) if daily[-25:-5] else 0;ve=recent_abs/base_abs if base_abs>0 else 0
    vols=pd.to_numeric(idx.volume,errors="coerce").fillna(0).tolist();av=float(np.mean([x for x in vols[-21:-1] if x>0])) if [x for x in vols[-21:-1] if x>0] else 0;rvol=float(latest.volume)/av if av else 0
    rng=max(0,float(latest.high)-float(latest.low));cp=(float(latest.close)-float(latest.low))/rng*100 if rng>0 else 50
    bph=float(latest.close)>float(prev.high);bpl=float(latest.close)<float(prev.low);ros=rob=False
    for i in range(max(20,len(closes)-5),len(closes)):
        m20=float(np.mean(closes[i-19:i+1]));r5=(closes[i]/closes[i-5]-1)*100 if i>=5 else 0;d=(closes[i]/closes[i-1]-1)*100 if i>=1 else 0;di=(closes[i]/m20-1)*100 if m20 else 0
        if r5<=-8 or di<=-6 or d<=-3:ros=True
        if r5>=8 or di>=6 or d>=3:rob=True
    bp=ctx["ret5"]<=-3 or dist<=-3 or ros;tp=ctx["ret5"]>=3 or dist>=3 or rob
    mode="NORMAL"
    if bp and tp:mode="BOTTOM" if ctx["ret5"]+dist+ctx["ret20"]*.25<0 else "TOP"
    elif bp:mode="BOTTOM"
    elif tp:mode="TOP"
    os=bc=ob=tc=0;bs="⚪ Inactive";ts="⚪ Inactive";active="⚪ Normal"
    if mode=="BOTTOM":
        if ctx["ret5"]<=-8:os+=2
        if ctx["ret20"]<=-12:os+=1
        if ctx["breadth"]<=30:os+=2
        if dist<=-6:os+=2
        if ctx["dayRet"]<=-3:os+=1
        if ve>=1.5:os+=1
        if ros or os>=3:
            if ctx["dayRet"]>=2:bc+=2
            if ctx["breadth"]>=55:bc+=2
            if bph:bc+=2
            if rvol>=1.3:bc+=1
            if ctx["foreign"]>0:bc+=1
            if cp>=70:bc+=1
        bs="⚪ Bottom Watch"
        if ros and bc>=6:bs="🟢 Strong Bottom Reversal"
        elif ros and bc>=4:bs="🟠 Bottom Reversal Attempt"
        elif os>=5:bs="🟣 Extreme Oversold"
        elif ros or os>=3:bs="🟣 Oversold Watch"
        active=bs
    elif mode=="TOP":
        if ctx["ret5"]>=8:ob+=2
        if ctx["ret20"]>=12:ob+=1
        if ctx["breadth"]>=70:ob+=2
        if dist>=6:ob+=2
        if ctx["dayRet"]>=3:ob+=1
        if ve>=1.5:ob+=1
        if rob or ob>=3:
            if ctx["dayRet"]<=-2:tc+=2
            if ctx["breadth"]<=45:tc+=2
            if bpl:tc+=2
            if rvol>=1.3:tc+=1
            if ctx["foreign"]<0:tc+=1
            if cp<=30:tc+=1
        ts="⚪ Top Watch"
        if rob and tc>=6:ts="🔴 Strong Top Reversal"
        elif rob and tc>=4:ts="🟠 Top Reversal Attempt"
        elif ob>=5:ts="🔴 Extreme Overbought"
        elif rob or ob>=3:ts="🟡 Overbought Watch"
        active=ts
    return {"mode":mode,"activeState":active,"oversoldScore":os,"bottomConfirmScore":bc,"bottomState":bs,"overboughtScore":ob,"topConfirmScore":tc,"topState":ts,"distMA20":round(dist,2),"indexRvol":round(rvol,2),"closePosition":round(cp,1),"breakPrevHigh":bph,"breakPrevLow":bpl,"recentOversold":ros,"recentOverbought":rob,"volExpansion":round(ve,2)}

def build(index_df,risk_on=60,risk_strong=75,risk_off=45):
    idx=index_df.copy().sort_values("date").reset_index(drop=True)
    if len(idx)<25:return {"state":"尚未分析","score":0}
    for c in ["close","high","low","volume"]:idx[c]=pd.to_numeric(idx[c],errors="coerce")
    closes=idx.close.tolist();latest=idx.iloc[-1];prev=idx.iloc[-2];ma5=float(np.mean(closes[-5:]));ma20=float(np.mean(closes[-20:]));old=float(np.mean(closes[-25:-5]))
    r5=(float(latest.close)/closes[-6]-1)*100;r20=(float(latest.close)/closes[-21]-1)*100;dr=(float(latest.close)/float(prev.close)-1)*100;trade_date=str(latest.date);up,down=breadth(trade_date);br=up/(up+down)*100;foreign=foreign_market_net(trade_date)
    s=0
    if latest.close>ma20:s+=15
    if ma5>ma20:s+=10
    if ma20>old:s+=5
    s+=20 if br>=55 else 12 if br>=50 else 5 if br>=45 else 0
    s+=15 if foreign>0 else 6 if foreign>-50 else 0
    s+=15 if r5>2 else 10 if r5>0 else 4 if r5>-2 else 0
    s+=10 if r20>5 else 6 if r20>0 else 2 if r20>-5 else 0
    if latest.close>prev.close:s+=10
    s=min(100,s);state="🟢 Strong Risk ON" if s>=risk_strong else "🟢 Risk ON" if s>=risk_on else "🟡 Neutral" if s>=risk_off else "🔴 Risk OFF"
    rv=reversal(idx,{"ret5":r5,"ret20":r20,"ma20":ma20,"breadth":br,"foreign":foreign,"dayRet":dr})
    return {"date":str(latest.date),"index":round(float(latest.close),2),"ma5":round(ma5,2),"ma20":round(ma20,2),"ret5":round(r5,2),"ret20":round(r20,2),"trend":"多" if latest.close>ma20 else "空","up":up,"down":down,"breadth":round(br,1),"foreign":round(foreign,1),"score":s,"state":state,"dayRet":round(dr,2),**rv}


def build_historical(index_df,breadth_value=50.0,foreign_value=0.0,risk_on=60,risk_strong=75,risk_off=45):
    """Dashboard-compatible historical regime without live network calls."""
    idx=index_df.copy().sort_values("date").reset_index(drop=True)
    if len(idx)<25:return {"state":"尚未分析","score":0}
    for col in ["close","high","low","volume"]:idx[col]=pd.to_numeric(idx[col],errors="coerce")
    closes=idx.close.tolist();latest=idx.iloc[-1];prev=idx.iloc[-2];ma5=float(np.mean(closes[-5:]));ma20=float(np.mean(closes[-20:]));old=float(np.mean(closes[-25:-5]))
    r5=(float(latest.close)/closes[-6]-1)*100;r20=(float(latest.close)/closes[-21]-1)*100;dr=(float(latest.close)/float(prev.close)-1)*100;br=float(breadth_value);foreign=float(foreign_value)
    s=0
    if latest.close>ma20:s+=15
    if ma5>ma20:s+=10
    if ma20>old:s+=5
    s+=20 if br>=55 else 12 if br>=50 else 5 if br>=45 else 0
    s+=15 if foreign>0 else 6 if foreign>-50 else 0
    s+=15 if r5>2 else 10 if r5>0 else 4 if r5>-2 else 0
    s+=10 if r20>5 else 6 if r20>0 else 2 if r20>-5 else 0
    if latest.close>prev.close:s+=10
    s=min(100,s);state="🟢 Strong Risk ON" if s>=risk_strong else "🟢 Risk ON" if s>=risk_on else "🟡 Neutral" if s>=risk_off else "🔴 Risk OFF"
    rv=reversal(idx,{"ret5":r5,"ret20":r20,"ma20":ma20,"breadth":br,"foreign":foreign,"dayRet":dr})
    return {"date":str(latest.date),"index":round(float(latest.close),2),"ma5":round(ma5,2),"ma20":round(ma20,2),"ret5":round(r5,2),"ret20":round(r20,2),"trend":"多" if latest.close>ma20 else "空","breadth":round(br,1),"foreign":round(foreign,1),"score":s,"state":state,"dayRet":round(dr,2),**rv}

def f_gate(risk,risk_on=60):
    score=float((risk or {}).get("score",0) or 0)
    strong_bottom=(risk or {}).get("bottomState")=="🟢 Strong Bottom Reversal" or (risk or {}).get("activeState")=="🟢 Strong Bottom Reversal"
    if score>=risk_on:return {"allowed":True,"reason":"RISK_ON","exception":False}
    if strong_bottom:return {"allowed":True,"reason":"STRONG_BOTTOM_REVERSAL","exception":True}
    return {"allowed":False,"reason":"MARKET_BLOCK","exception":False}

def f2_gate(risk,was_on=False,entry=60,hold=55):
    """Dynamic market gate: 60 entry / 55 hold, Strong Bottom exception, confirmed-top and extreme-overbought veto."""
    r=risk or {};score=float(r.get("score",0) or 0);active=str(r.get("activeState") or "");top=str(r.get("topState") or "")
    strong_bottom=active=="🟢 Strong Bottom Reversal" or str(r.get("bottomState") or "")=="🟢 Strong Bottom Reversal"
    hard_top=active in ("🔴 Strong Top Reversal","🟠 Top Reversal Attempt") or top in ("🔴 Strong Top Reversal","🟠 Top Reversal Attempt")
    extreme_ob=active=="🔴 Extreme Overbought" or top=="🔴 Extreme Overbought"
    # Strong Bottom 只放行當日，不把 regime 狀態強制翻成 ON。
    if strong_bottom:return {"allowed":True,"reason":"STRONG_BOTTOM_REVERSAL","exception":True,"stateOn":bool(was_on),"topVeto":False}
    # 已確認頂部反轉時直接關閉 hysteresis，下一次必須重新 >=60 才能開啟。
    if hard_top:return {"allowed":False,"reason":"TOP_REVERSAL_VETO","exception":False,"stateOn":False,"topVeto":True}
    # 極端過熱禁止新倉，但保留原 regime 狀態；過熱解除後若仍 >=55 可恢復。
    if extreme_ob:return {"allowed":False,"reason":"EXTREME_OVERBOUGHT_VETO","exception":False,"stateOn":bool(was_on or score>=entry),"topVeto":True}
    if was_on and score>=hold:return {"allowed":True,"reason":"HYSTERESIS_HOLD","exception":False,"stateOn":True,"topVeto":False}
    if score>=entry:return {"allowed":True,"reason":"RISK_ON_ENTRY","exception":False,"stateOn":True,"topVeto":False}
    return {"allowed":False,"reason":"MARKET_BLOCK","exception":False,"stateOn":False,"topVeto":False}
