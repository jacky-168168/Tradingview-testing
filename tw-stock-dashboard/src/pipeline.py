from __future__ import annotations
import json,sys
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
import requests
from config import *
from yahoo_cache import update_many,update_symbol,to_symbol
from scoring import calc_metrics,score_a,score_d,d_pass,sort_key
from institution import fetch_day
from risk import build as build_risk,f_gate,f2_gate
from sar import apply as apply_sar
from industry_chain import enrich as enrich_chain
from panels import institution_flow,topic_heat
from g_live import select as select_live_g,prior_pockets as load_g_prior_pockets

HEADERS={"User-Agent":"Mozilla/5.0 tw-stock-dashboard/3.0","Accept":"application/json"}

def _pick(row,*keys,default=""):
    for k in keys:
        if k in row and row[k] not in (None,""):return row[k]
    return default

def _capital_b(v):
    try:
        x=float(str(v).replace(",",""));return x/100_000_000 if x>1_000_000 else x
    except:return 0.0

def _industry(v,market):
    raw=str(v or "").strip()
    if not raw:return "未分類"
    key=raw.zfill(2) if raw.isdigit() and len(raw)<=2 else raw
    mp={"01":"水泥工業","02":"食品工業","03":"塑膠工業","04":"紡織纖維","05":"電機機械","06":"電器電纜","08":"玻璃陶瓷","09":"造紙工業","10":"鋼鐵工業","11":"橡膠工業","12":"汽車工業","14":"建材營造","15":"航運業","16":"觀光餐旅","17":"金融業" if market=="上櫃" else "金融保險","18":"貿易百貨","19":"綜合","20":"其他","21":"化學工業","22":"生技醫療業","23":"油電燃氣業","24":"半導體業","25":"電腦及週邊設備業","26":"光電業","27":"通信網路業","28":"電子零組件業","29":"電子通路業","30":"資訊服務業","31":"其他電子業","32":"文化創意業","33":"農業科技業","35":"綠能環保","36":"數位雲端","37":"運動休閒","38":"居家生活","80":"管理股票"}
    return mp.get(key,raw)

def _normalize_company(row,market):
    code=str(_pick(row,"公司代號","SecuritiesCompanyCode","Code","股票代號","公司代碼")).strip()
    if not(len(code)==4 and code.isdigit()):return None
    return {"code":code,"name":str(_pick(row,"公司簡稱","CompanyAbbreviation","CompanyName","公司名稱","Name",default=code)).strip(),"market":market,
            "capitalB":_capital_b(_pick(row,"實收資本額","PaidInCapital","Paidin.Capital.NTDollars","PaidIn.Capital.NTDollars","實收資本額(元)",default=0)),
            "industry":_industry(_pick(row,"產業別","Industry","產業類別","SecuritiesIndustryCode",default="未分類"),market)}

def fetch_json(url):
    r=requests.get(url,headers=HEADERS,timeout=25);r.raise_for_status();return r.json()

def load_universe():
    CACHE_DIR.mkdir(parents=True,exist_ok=True);listed=[];otc=[]
    try:
        for x in fetch_json(TWSE_COMPANY_URL):
            z=_normalize_company(x,"上市")
            if z:listed.append(z)
    except Exception as e:print("TWSE universe failed",e,file=sys.stderr)
    for url in TPEX_COMPANY_URLS:
        try:
            tmp=[]
            for x in fetch_json(url):
                z=_normalize_company(x,"上櫃")
                if z:tmp.append(z)
            cov=(sum(x.get("capitalB",0)>0 for x in tmp)/len(tmp)) if tmp else 0
            if len(tmp)>=MIN_OTC_UNIVERSE and cov>=.90:
                otc=tmp;break
        except Exception as e:print("TPEx universe source failed",url,e,file=sys.stderr)
    good=len(listed)>=MIN_LISTED_UNIVERSE and len(otc)>=MIN_OTC_UNIVERSE
    if not good and UNIVERSE_CACHE.exists():
        try:
            old=json.loads(UNIVERSE_CACHE.read_text(encoding="utf-8"))
            ol=[x for x in old if x.get("market")=="上市"];oo=[x for x in old if x.get("market")=="上櫃"]
            if len(ol)>=MIN_LISTED_UNIVERSE and len(oo)>=MIN_OTC_UNIVERSE:
                print(f"company universe fallback cache: listed={len(ol)} otc={len(oo)}",file=sys.stderr);return old
        except Exception:pass
    if not good:raise RuntimeError(f"公司母檔不足：上市 {len(listed)} / 上櫃 {len(otc)}")
    rows=list({f'{x["market"]}_{x["code"]}':x for x in listed+otc}.values())
    UNIVERSE_CACHE.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding="utf-8");return rows

def _risk_signal(row,risk):
    m=row["model"];score=row["total"]
    if m=="D":sig="🔥 D強勢" if score>=80 else "✅ D觀察" if score>=65 else "👀 D候選"
    else:sig="🔥 強勢" if score>=85 else "✅ 觀察" if score>=75 else "👀 備選" if score>=65 else "一般"
    return ("⚠ Risk非ON "+sig) if risk.get("score",0)<RISK_ON else sig

def _base_sort_a(r):return (-r["baseScore"],-r["rs20"],-r["rvol"],-r["ret20"],-r["turnoverB"])
def _final_sort_a(r):return (-r["total"],-r.get("sarBonus",0),-r["rs20"],-r["rvol"],-r["ret20"],-r["turnoverB"])
def _final_sort_d(r):return sort_key(r)

def published_data_date():
    dates=[]
    try:
        if LATEST_JSON.exists():
            x=json.loads(LATEST_JSON.read_text(encoding="utf-8"));d=str(x.get("dataDate") or "")
            if d:dates.append(d)
    except Exception:pass
    try:
        p=DATA_DIR/"daily"/"index.json"
        if p.exists():
            for x in json.loads(p.read_text(encoding="utf-8")):
                d=str((x or {}).get("date") or "")
                if d:dates.append(d)
    except Exception:pass
    return max(dates) if dates else ""

def previous_f2_state(market_date):
    """Rebuild/persist the prior F2 hysteresis state from available daily snapshots."""
    state=False
    try:
        p=DATA_DIR/"daily"/"index.json";rows=json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        dates=sorted([str((x or {}).get("date") or "") for x in rows if str((x or {}).get("date") or "")<market_date])[-60:]
        for d in dates:
            q=DATA_DIR/"daily"/f"{d}.json"
            if not q.exists():continue
            old=json.loads(q.read_text(encoding="utf-8"));rr=old.get("risk") or {};g=rr.get("f2Gate") or {}
            if "stateOn" in g:state=bool(g.get("stateOn"))
            else:state=bool(f2_gate(rr,state,RISK_ON,55).get("stateOn"))
    except Exception:pass
    return state

def main():
    now=datetime.now(ZoneInfo("Asia/Taipei")).replace(tzinfo=None);start=min(now-timedelta(days=LOOKBACK_CALENDAR_DAYS),datetime(now.year,1,1)-timedelta(days=90))
    _,idx,idxerr=update_symbol(BENCHMARK,start,now)
    if idxerr or idx is None or len(idx)<25:raise RuntimeError(f"benchmark unavailable: {idxerr}")
    market_date=str(idx.iloc[-1]["date"]);published=published_data_date()
    if published and market_date<published:
        print(json.dumps({"generatedAt":now.isoformat(timespec="seconds"),"dataDate":market_date,"publishedDate":published,"skipped":"stale-market-date"},ensure_ascii=False));return
    universe=load_universe();eligible=[x for x in universe if 0<x.get("capitalB",0)<MAX_CAPITAL_B]
    histories,errors=update_many([(x["code"],x["market"]) for x in universe],start,now)
    risk=build_risk(idx,RISK_ON,RISK_STRONG,RISK_OFF);mkt20=float(risk.get("ret20",0) or 0)
    _,inst,insterr=fetch_day(market_date);names={f'{x["market"]}_{x["code"]}':x["name"] for x in universe}
    a=[];d_strict=[];d_backup=[];known_g_metrics={}
    for s in eligible:
        h=histories.get(to_symbol(s["code"],s["market"]));m=calc_metrics(h.tail(75)) if h is not None and len(h)>=60 else None
        if m and h is not None and str(h.date.iloc[-1])[:10]==market_date:known_g_metrics[to_symbol(s["code"],s["market"])]=m
        if not m or m["close"]<MIN_PRICE:continue
        rs20=m["ret20"]-mkt20;turnover_b=m["close"]*m["volume"]/100_000_000;ii=inst.get(f'{s["market"]}_{s["code"]}',{})
        base={**s,"close":m["close"],"dayRet":m["dayRet"],"ret5":m["ret5"],"ret20":m["ret20"],"marketRet20":mkt20,"rs20":rs20,"rvol":m["rvol"],"rvol10":m["rvol10"],"mom10Pct":m["mom10Pct"],"volD":m["volD"],"atrPct":m["atrPct"],"breakoutPct":m["breakoutPct"],"ma20Slope":m["ma20Slope"],"turnoverB":turnover_b,
              "foreignToday":round(float(ii.get("foreign",0) or 0)/1000,1),"trustToday":round(float(ii.get("trust",0) or 0)/1000,1)}
        liquid=turnover_b*100>=MIN_TURNOVER_M
        if liquid:
            z=score_a(m,rs20,ii);a.append({**base,**z,"baseScore":z["total"],"model":"A","sarBonus":0,"sarText":"讀取中"})
        strict=d_pass(m);z=score_d(m,rs20,ii);row={**base,**z,"baseScore":z["total"],"model":"D","sarBonus":0,"sarText":"讀取中","strictPass":strict,"candidateTier":"正式" if strict else "候補"}
        if strict:d_strict.append(row)
        elif liquid:d_backup.append(row)
    a.sort(key=_base_sort_a);d_strict.sort(key=sort_key);d_backup.sort(key=sort_key)
    strict_d_count=len(d_strict);d_all=d_strict+d_backup
    candidate_counts={"A":len(a),"D":len(d_all)};strict_candidate_counts={"D":strict_d_count}
    apply_sar(a,market_date,min(len(a),max(TOP_N*2,SAR_CANDIDATES)));apply_sar(d_all,market_date,min(len(d_all),max(TOP_N*2,SAR_CANDIDATES)))
    for x in a:x["signal"]=_risk_signal(x,risk)
    for x in d_all:x["signal"]=_risk_signal(x,risk) if x.get("strictPass") else "🟡 D候補"
    a=sorted(a,key=_final_sort_a)[:TOP_N]
    # 正式頁固定保留 20 檔：嚴格 D 通過者永遠排前面，不足 20 才由高分高流動性的次級候選補足。
    d=(sorted(d_strict,key=_final_sort_d)+sorted(d_backup,key=_final_sort_d))[:TOP_N]
    enrich_chain(a);enrich_chain(d)
    # G uses an independent ALL-market 2026 cross section, unlike capital-capped A/D/F.
    # 3D/18D structures must be confirmed. Prior G pockets come only from older
    # daily snapshots (missing snapshots are empty; never fetch future lists).
    year_market_days=[str(x) for x in idx.date.astype(str) if str(x).startswith(market_date[:4]) and str(x)<=market_date]
    old_g_pockets,g_pocket_found=load_g_prior_pockets(DATA_DIR,year_market_days,market_date)
    g,g_pocket_baseline,g_selection=select_live_g(universe,histories,year_market_days,market_date,inst,old_g_pockets,known_g_metrics)
    g_selection["pocketSnapshotsFound"]=g_pocket_found
    g_selection["pocketWarmup"]=g_pocket_found<min(10,max(0,len(year_market_days)-1))
    enrich_chain(g)
    apply_sar(g,market_date,min(len(g),TOP_N))
    gate=f_gate(risk,RISK_ON);prev_f2_on=previous_f2_state(market_date);gate2=f2_gate(risk,prev_f2_on,RISK_ON,55)
    # 正式選股頁是候選清單，不是實際下單：D/F/F2 一律保留最多 TOP_N(20)；只有回測才限制進場 Top3。
    fsrc=d if gate["allowed"] else []
    f=[{**x,"model":"F","marketGate":gate["reason"],"signal":("🟣 F強反轉例外" if gate["exception"] else "🟢 F Risk ON") if x.get("strictPass") else "🟡 F候補"} for x in fsrc]
    f2src=d if gate2["allowed"] else []
    f2sig="🟣 F2 強反轉例外" if gate2["exception"] else "⛔ F2 Top Veto" if gate2["topVeto"] else "🟢 F2 維持ON" if gate2["reason"]=="HYSTERESIS_HOLD" else "🟢 F2 Risk ON"
    f2=[{**x,"model":"F2","marketGate":gate2["reason"],"signal":f2sig if x.get("strictPass") else "🟡 F2候補"} for x in f2src]
    candidate_counts["F"]=len(f);candidate_counts["F2"]=len(f2);candidate_counts["G"]=g_selection["doubleBreakCandidates"]
    strict_candidate_counts["F"]=sum(bool(x.get("strictPass")) for x in f);strict_candidate_counts["F2"]=sum(bool(x.get("strictPass")) for x in f2);strict_candidate_counts["G"]=len(g)
    flow=institution_flow(inst,names);heat=topic_heat(market_date)
    payload={"generatedAt":now.isoformat(timespec="seconds"),"dataDate":market_date,"benchmarkRet20":round(mkt20,4),"universeCount":len(eligible),
             "historyOk":len(histories)-len(errors),"historyErrors":len(errors),"models":{"A":a,"D":d,"F":f,"F2":f2,"G":g},"gSelection":g_selection,"gPocketBaseline":g_pocket_baseline,"risk":{**risk,"fGate":gate,"f2Gate":gate2},
             "panels":{"institutionFlow":flow,"topicHeat":heat,"institutionSource":"TWSE T86／上櫃暫為0","topicSource":heat[0]["source"] if heat else "暫無題材資料"},
             "candidateCounts":candidate_counts,"strictCandidateCounts":strict_candidate_counts,"phase":"github-python-v8-g-default","notes":["F = D 技術強勢 + 固定大盤濾網；Risk Score >=60 允許進場，Strong Bottom Reversal 為唯一例外。","F2 = D + 動態大盤濾網：60 進場、55 維持、Strong Bottom Reversal 單日例外；Strong Top Reversal / Top Reversal Attempt 關閉狀態，Extreme Overbought 禁止新進場。","Phase 6：A/D/F、Risk、Top/Bottom Watch、官方SAR、法人、題材與產業鏈已接入。","SAR改用TWSE/TPEx官方未還原日K，避免除權息/分割造成Yahoo調整價差異。","上櫃法人仍依V12.2口徑暫時視為0分。","正式選股 D/F/F2 固定保留 Top20 候選：嚴格通過 D 的股票優先，不足 20 才用高分且流動性合格的候補補齊；候補會明確標示。回測實際進場仍只使用嚴格通過 D 的 Rank1~3。","G 預設模型：G_DOUBLE_PERSIST，先使用全市場強勢候選，再要求 3D/18D 前一完整 K 棒高點雙突破，最後按過去10交易日的原 G 雙突破 Top20 入選紀錄加分。首次上線歷史資料未滿10天時仍正常選股但不填補假歷史。","G 今日選股只根據完整更新的日 K 資料，盤中只更新選中股票的最新價格，不會把回測歷史 Top20 偽裝成今日選股。"]}
    DATA_DIR.mkdir(parents=True,exist_ok=True);body=json.dumps(payload,ensure_ascii=False,indent=2);LATEST_JSON.write_text(body,encoding="utf-8")
    daily=DATA_DIR/"daily";daily.mkdir(parents=True,exist_ok=True);(daily/f"{market_date}.json").write_text(body,encoding="utf-8")
    ip=daily/"index.json"
    try:di=json.loads(ip.read_text(encoding="utf-8")) if ip.exists() else []
    except:di=[]
    item={"date":market_date,"generatedAt":payload["generatedAt"],"riskScore":risk.get("score"),"riskState":risk.get("state"),"aCount":len(a),"dCount":len(d),"fCount":len(f),"f2Count":len(f2),"gCount":len(g),"gPocketHistory":g_pocket_found}
    di=[x for x in di if x.get("date")!=market_date];di.insert(0,item);di.sort(key=lambda x:x.get("date",""),reverse=True)
    ip.write_text(json.dumps(di[:750],ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"generatedAt":payload["generatedAt"],"dataDate":market_date,"universeCount":len(eligible),"A":len(a),"D":len(d),"F":len(f),"F2":len(f2),"G":len(g),"gHistoryDays":g_pocket_found,"risk":risk.get("score"),"f2Gate":gate2.get("reason"),"historyErrors":len(errors),"institutionError":insterr},ensure_ascii=False))
if __name__=="__main__":main()
