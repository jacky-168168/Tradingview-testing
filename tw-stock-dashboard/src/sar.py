from __future__ import annotations
import math

def parabolic_sar(df,start=.02,inc=.02,max_af=.2):
    h=df.reset_index(drop=True)
    if len(h)<10:return None
    n=len(h);sar=[None]*n;bull=[None]*n;result=maxmin=af=None;below=False
    for i in range(n):
        first=False
        if i==1:
            if float(h.loc[i,"close"])>float(h.loc[i-1,"close"]):below=True;maxmin=float(h.loc[i,"high"]);result=float(h.loc[i-1,"low"])
            else:below=False;maxmin=float(h.loc[i,"low"]);result=float(h.loc[i-1,"high"])
            first=True;af=start
        if i==0 or result is None:continue
        result=result+af*(maxmin-result)
        if below:
            if result>float(h.loc[i,"low"]):first=True;below=False;result=max(float(h.loc[i,"high"]),maxmin);maxmin=float(h.loc[i,"low"]);af=start
        else:
            if result<float(h.loc[i,"high"]):first=True;below=True;result=min(float(h.loc[i,"low"]),maxmin);maxmin=float(h.loc[i,"high"]);af=start
        if not first:
            if below and float(h.loc[i,"high"])>maxmin:maxmin=float(h.loc[i,"high"]);af=min(af+inc,max_af)
            elif (not below) and float(h.loc[i,"low"])<maxmin:maxmin=float(h.loc[i,"low"]);af=min(af+inc,max_af)
        if below:
            result=min(result,float(h.loc[i-1,"low"]))
            if i>1:result=min(result,float(h.loc[i-2,"low"]))
        else:
            result=max(result,float(h.loc[i-1,"high"]))
            if i>1:result=max(result,float(h.loc[i-2,"high"]))
        sar[i]=result;bull[i]=result<float(h.loc[i,"close"])
    ci=n-2
    if ci<1 or sar[ci] is None:return None
    flip=-1
    for i in range(ci,1,-1):
        if bull[i]!=bull[i-1]:flip=i;break
    trend=ci-flip+1 if flip>=0 else 1
    return {"value":round(float(sar[ci]),4),"bullish":bool(bull[ci]),"trendBars":max(1,int(trend)),"confirmedDate":str(h.loc[ci,"date"])}

def apply(rows,histories,symbol_fn,candidate_n=50):
    for r in rows[:max(0,candidate_n)]:
        df=histories.get(symbol_fn(r["code"],r["market"]));x=parabolic_sar(df) if df is not None and len(df)>=30 else None
        r["sarBonus"]=0;r["sarText"]="SAR資料不足"
        if x:
            t=x["trendBars"];r["sarText"]=("多 " if x["bullish"] else "空 ")+f"{t} 根K"
            if x["bullish"]:r["sarBonus"]=5 if t==1 else 4 if t==2 else 3 if t==3 else 2 if t==4 else 1 if t in (5,6) else 0
    return rows
