"""19 原始公開訊號逐筆保守評估：發文當日不假設可交易；隔一交易日開始掛單。"""
from __future__ import annotations
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from config import DATA_DIR
from yahoo_cache import update_many,to_symbol
from research_author_breakout import CODES,OUT,simulate_one,compact_stats
from pipeline import load_universe
def main():
 samples=pd.read_csv(DATA_DIR/'research'/'signal_samples_2026.csv',dtype={'code':str},encoding='utf-8-sig')
 samples=samples[samples.code.isin(CODES)].copy()
 if len(samples)!=19:raise RuntimeError('expected exactly 19 original signals')
 symbols=[(str(r.code),str(r.market)) for _,r in samples.iterrows()]
 hist,errors=update_many(symbols,datetime(2026,7,1),datetime(2026,10,27))
 plans={'hold20_stop_only':((999.,1000.),20),'twoR_fiveR':((2.,5.),15),'fiveR_tenR':((5.,10.),20)}
 rows=[];trades={k:[] for k in plans}
 for _,r in samples.iterrows():
  sym=to_symbol(str(r.code),str(r.market))
  h=hist.get(sym)
  info={'code':str(r.code),'name':str(r['name']),'postedDate':str(r.date),
        'postedTime':str(r.time) if pd.notna(r.time) else None,
        'entryTrigger':float(r.entry),'initialStop':float(r.stop),
        'initialRiskPct':round(float(r.riskPct),3),
        'initialRiskATR':round(float(r.riskATR),3)}
  if h is None or len(h)<10:
   info['error']='Historical OHLC unavailable';rows.append(info);continue
  h=h.sort_values('date').drop_duplicates('date').reset_index(drop=True)
  days=h.date.astype(str).tolist()
  idx=sum(d<=str(r.date) for d in days)-1
  if idx<0:
   info['error']='No completed bar by publication date';rows.append(info);continue
  posted_bar=h.iloc[idx]
  info['postingDayOHLCVerified']=str(posted_bar.date)==str(r.date)
  info['postingDayHighTouchesEntry']=bool(float(posted_bar.high)>=float(r.entry)) if info['postingDayOHLCVerified'] else None
  info['postingDaySequenceKnown']=False
  info['nextSession']=days[idx+1] if idx+1<len(days) else None
  info['strictDplus1']={}
  for name,(tp,hold) in plans.items():
   d=simulate_one(h,idx,float(r.entry),1.,1.,tp,hold,fixed_stop=float(r.stop))
   if d is None:info['strictDplus1'][name]={'status':'not_triggered_in_next_3_sessions'}
   elif d['status']=='censored':info['strictDplus1'][name]={'status':'still_open_or_incomplete'}
   else:
    info['strictDplus1'][name]={k:v for k,v in d.items() if k not in ('legs',)}
    trades[name].append({'code':str(r.code),**d})
  rows.append(info)
 if sum('error' not in v for v in rows)<16:raise RuntimeError('OHLC coverage below 16 of 19: refuse publish')
 out={'generatedAt':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds'),
  'asOf':'2026-10-27','sampleCount':len(rows),
  'dataCoverage':sum('error' not in z for z in rows),
  'method':'Exclude publication-day execution: next 3 exchange sessions trigger entry; 3% max gap; simultaneous stop first.',
  'criticalWarning':'2026-10-08 09:15 high >= trigger cannot prove that the level was touched after the public message; daily OHLC lacks intraday ordering.',
  'plans':{k:compact_stats(v) for k,v in trades.items()},
  'rows':rows,'quoteErrors':errors}
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'author_outcomes.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'coverage':out['dataCoverage'],'results':out['plans']},ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
