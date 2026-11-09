"""作者強勢突破訊號研究：D 收盤選股、D+1 後突破掛單、停損優先。
2026 author examples inspire features and are NOT out-of-sample data.
Trade outcomes are independent trade-level returns, NOT an investable portfolio CAGR.
"""
from __future__ import annotations
import argparse
import json
import math
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from config import DATA_DIR, BENCHMARK
from yahoo_cache import update_many, update_symbol, to_symbol
from pipeline import load_universe
from scoring import precompute_features
OUT = DATA_DIR / 'research' / 'author_breakout'
SAMPLE_CSV = DATA_DIR / 'research' / 'signal_samples_2026.csv'
CODES = ('4903','8086','1569','2466','3094','2409','6533','6456','3624','8103','6224','2489','3406','3443','3605','8155','3504','3450','1709')
TARGETS = {
 '1569':[81.3,91.8], '2409':[49.4,68,95,122], '6533':[409,561,778,995],
 '6456':[125,160,230,300], '3624':[173,210], '6224':[137,183,274,365],
 '2489':[50.5,58,73,88], '3406':[1460,2925,3905,5860,10745],
 '3443':[6975,7300,8110], '3605':[173,202,275,421,568],
 '8155':[403,441.5], '3504':[201.5,282.5,417.5,526,634],
 '3450':[580,634], '1709':[38.2,41.75],
}
BUY_FEE = .001425
SELL_FEE = .001425 + .003
SLIPPAGE = .001
START = '2023-10-09'
SPLITS = {'historical_train':('2023-10-09','2024-12-31'),
          'robustness_2025':('2025-01-01','2025-12-31'),
          'author_inspired_2026':('2026-01-01','2026-10-27')}
# Fixed configurations. Do not choose thresholds by optimizing the 19 author examples.
MODELS = {
 'CORE_1ATR_2R5R':{'ret':12,'rs':7,'slope':2,'rvol':.5,'atr':1.0,'tp':(2.,5.),'hold':15},
 'CORE_1ATR_5R10R':{'ret':12,'rs':7,'slope':2,'rvol':.5,'atr':1.0,'tp':(5.,10.),'hold':20},
 'STRONG_1ATR_2R5R':{'ret':20,'rs':15,'slope':3,'rvol':1.0,'atr':1.0,'tp':(2.,5.),'hold':15},
 'STRONG_1ATR_5R10R':{'ret':20,'rs':15,'slope':3,'rvol':1.0,'atr':1.0,'tp':(5.,10.),'hold':20},
 'CORE_0p65ATR_2R5R':{'ret':12,'rs':7,'slope':2,'rvol':.5,'atr':.65,'tp':(2.,5.),'hold':15},
 'CORE_1p35ATR_2R5R':{'ret':12,'rs':7,'slope':2,'rvol':.5,'atr':1.35,'tp':(2.,5.),'hold':15},
}
def finite(x):
 try:
  v=float(x)
  return v if math.isfinite(v) else None
 except (TypeError,ValueError):return None
def tick(price):
 if price<10:return .01
 if price<50:return .05
 if price<100:return .1
 if price<500:return .5
 if price<1000:return 1.
 return 5.
def ceil_tick(px):
 unit=tick(px)
 return round(math.ceil((px-1e-8)/unit)*unit,4)
def diagnostics():
 d=pd.read_csv(SAMPLE_CSV,encoding='utf-8-sig',dtype={'code':str})
 d=d[d.code.isin(CODES)].copy()
 if len(d)!=len(CODES):raise RuntimeError(f'19-sample coverage failed: {len(d)}')
 rows=[]
 for _,a in d.iterrows():
  e=float(a.entry);s=float(a.stop);r=e-s
  rows.append({'date':a.date,'code':a.code,'name':a['name'],'asOf':a.anchorDate,
   'entry':e,'initialStop':s,'riskPct':round(r/e*100,4),'riskATR':round(float(a.riskATR),4),
   'priorRet20Pct':round(float(a.ret20),3),'priorRS20Pct':round(float(a.rs20),3),
   'priorMA20SlopePct':round(float(a.ma20Slope),3),'priorRVOL':round(float(a.rvol),3),
   'priorATRPct':round(float(a.atrPct),3),
   'publishedTargets':[{'price':v,'grossR':round((v-e)/r,3)} for v in TARGETS.get(a.code,[])],
   'notes':'目標為作者公布價位，非已實現報酬；未納交易稅費'})
 out={'generatedAt':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds'),
  'count':len(rows),'source':'docs/data/research/signal_samples_2026.csv (prior completed day)',
  'interpretation':'entry/stop published independently; targets are hypothetical. Invalidations are not stops.',
  'warnings':['2026 樣本僅用於產生假說，所有 2026 評估非真正樣本外','發文當日分鐘資料不足，無法判定發文前／後最高最低價先後順序'],
  'medians':{k:round(float(d[k].median()),4) for k in ('riskPct','riskATR','atrPct','ret20','rs20','rvol','ma20Slope')},
  'samples':rows}
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'author_samples.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 return out
def price_features(df,benchmark_ret):
 f=precompute_features(df)
 f['date']=f.date.astype(str)
 f['ma20']=pd.to_numeric(f.ma20,errors='coerce')
 f['hi5']=f.high.rolling(5).max()
 f['hi20']=f.high.rolling(20).max()
 f['atr14']=pd.concat([(f.high-f.low).abs(),(f.high-f.close.shift(1)).abs(),(f.low-f.close.shift(1)).abs()],axis=1).max(axis=1).rolling(14).mean()
 f['rs20']=f.ret20-f.date.map(benchmark_ret)
 f['turnoverM']=f.close*f.volume/1e6
 return f
def candidates(data,model):
 x=data
 valid=(x.date>=START)&(x.date<='2026-10-27')&\
  (x.close>=10)&(x.turnoverM>=100)&(x.ret20>=model['ret'])&\
  (x.rs20>=model['rs'])&(x.ma20Slope>=model['slope'])&\
  (x.rvol>=model['rvol'])&(x.atrPct.between(3,12))&\
  (x.close>x.ma20)&(x.close>=x.hi20*.82)&(x.atr14>0)
 a=x.loc[valid].copy()
 a['trigger']=[ceil_tick(v+tick(v)) for v in a.hi5]
 a['stretchPct']=(a.trigger/a.close-1)*100
 a=a[(a.stretchPct>=-.1)&(a.stretchPct<=12)].copy()
 a['score']=.45*a.ret20+.35*a.rs20+2*np.minimum(a.rvol,5)+2*a.ma20Slope
 return a
def simulate_one(df,signal_ix,trigger,atr,stop_mult,tp,hold,posted=False,fixed_stop=None):
 """Signal after close: D+1~D+3 breakout; position low wins ambiguous same-day bar."""
 h=df.reset_index(drop=True)
 risk=max(trigger*.02,min(atr*stop_mult,trigger*.11)) if fixed_stop is None else trigger-fixed_stop
 if risk<=0:return None
 stop=trigger-risk if fixed_stop is None else fixed_stop
 buy=None;entry_i=None;gap_rejected=0
 for j in range(signal_ix+1,min(len(h),signal_ix+4)):
  bar=h.iloc[j];op=finite(bar.open);hi=finite(bar.high)
  if hi is None or op is None or hi<trigger:continue
  fill=max(op,trigger)
  if (fill/trigger-1)>.03:
   gap_rejected+=1;continue
  buy=fill*(1+SLIPPAGE);entry_i=j;break
 if entry_i is None:return None
 per_share=buy-stop
 if per_share<=0:return None
 remain=1.;proceeds=0.;legs=[];next_stop=stop;status='censored'
 last_idx=min(len(h)-1,entry_i+hold-1)
 for j in range(entry_i,last_idx+1):
  bar=h.iloc[j];op=finite(bar.open);lo=finite(bar.low);hi=finite(bar.high);close=finite(bar.close)
  if any(v is None for v in [op,lo,hi,close]):continue
  if lo<=next_stop:
   px=max(0.01,min(op,next_stop)) if j>entry_i else next_stop
   proceeds+=remain*px*(1-SELL_FEE-SLIPPAGE)
   legs.append({'date':bar.date,'fraction':round(remain,3),'raw':px,'reason':'stop'})
   remain=0;status='stopped';break
  for n,target_r in enumerate(tp):
   if any(z.get('targetIndex')==n for z in legs):continue
   px=buy+per_share*target_r
   if hi>=px:
    fraction=min(.5,remain)
    proceeds+=fraction*px*(1-SELL_FEE-SLIPPAGE)
    legs.append({'date':bar.date,'fraction':fraction,'raw':round(px,4),'reason':'target','targetIndex':n})
    remain=round(remain-fraction,8)
    if n==0:next_stop=max(next_stop,buy)
   if remain<1e-8:break
  if remain<1e-8:status='targets';break
  if j==last_idx:
   status='censored' if j==len(h)-1 else 'time_exit'
   if status!='censored':
    proceeds+=remain*close*(1-SELL_FEE-SLIPPAGE)
    legs.append({'date':bar.date,'fraction':round(remain,3),'raw':close,'reason':'time_exit'})
    remain=0
 if remain>0:return {'status':'censored','signalDate':str(h.iloc[signal_ix].date)}
 net_pct=(proceeds/(buy*(1+BUY_FEE))-1)*100
 net_r=(proceeds-buy*(1+BUY_FEE))/(per_share)
 return {'status':status,'signalDate':str(h.iloc[signal_ix].date),'entryDate':str(h.iloc[entry_i].date),
  'exitDate':str(legs[-1]['date']),'entryFill':round(buy,4),'originalTrigger':trigger,
  'originalStop':round(stop,4),'riskPct':round(per_share/buy*100,4),
  'netPct':round(net_pct,4),'netR':round(net_r,4),'barsHeld':int(j-entry_i+1),
  'legs':legs,'gapRejected':gap_rejected}
def compact_stats(rows):
 if not rows:return {'trades':0,'winPct':None,'meanNetR':None,'medianNetR':None,'meanNetPct':None,'profitFactor':None,'avgHoldBars':None}
 net=np.array([x['netR'] for x in rows],dtype=float)
 pct=np.array([x['netPct'] for x in rows],dtype=float)
 gain=float(net[net>0].sum());loss=abs(float(net[net<0].sum()))
 return {'trades':len(rows),'winPct':round(float((net>0).mean()*100),2),
  'meanNetR':round(float(net.mean()),4),'medianNetR':round(float(np.median(net)),4),
  'meanNetPct':round(float(pct.mean()),3),
  'profitFactor':round(gain/loss,3) if loss>0 else None,
  'avgHoldBars':round(float(np.mean([z['barsHeld'] for z in rows])),2)}
def run_backtest(max_symbols=0):
 universe=load_universe()
 base_by_code={x['code']:x for x in universe}
 assert all(s in base_by_code for s in CODES),'one or more original signal codes missing in current universe'
 ordered=sorted(universe,key=lambda s:(s['code'] not in CODES,s['code']))
 if max_symbols>0:
  ordered=ordered[:max(max_symbols,len(CODES))]
 start=datetime(2022,8,1);end=datetime(2026,10,27)
 hist,errors=update_many([(x['code'],x['market']) for x in ordered],start,end)
 _,benchmark,be=update_symbol(BENCHMARK,start,end)
 if be or benchmark.empty:raise RuntimeError(f'benchmark not ready {be}')
 bx=benchmark.copy().sort_values('date');bx['ret20']=bx.close.pct_change(20)*100
 benchmark_ret=dict(zip(bx.date.astype(str),bx.ret20))
 by_sym={};signals={k:defaultdict(list) for k in MODELS}
 for i,item in enumerate(ordered):
  sym=to_symbol(item['code'],item['market']);h=hist.get(sym)
  if h is None or len(h)<100:continue
  h=h.sort_values('date').drop_duplicates('date').reset_index(drop=True)
  ft=price_features(h,benchmark_ret);by_sym[sym]=h
  for model_id,conf in MODELS.items():
   cand=candidates(ft,conf)
   for ix,r in cand.iterrows():
    signals[model_id][str(r['date'])].append({'sym':sym,'code':item['code'],'i':int(ix),
     'trigger':float(r.trigger),'atr':float(r.atr14),'score':float(r.score)})
  if (i+1)%200==0:print('processed',i+1,'of',len(ordered),flush=True)
 result={};trade_rows={};sample_codes=set(CODES)
 for model_id,conf in MODELS.items():
  all_trades=[];eligible_days=0;candidate_total=0;busy_until={}
  for day,rows in sorted(signals[model_id].items()):
   eligible_days+=1;candidate_total+=len(rows)
   top=sorted(rows,key=lambda z:(-z['score'],z['code']))[:3]
   for p in top:
    if day<=busy_until.get(p['sym'],''):continue
    deal=simulate_one(by_sym[p['sym']],p['i'],p['trigger'],p['atr'],conf['atr'],conf['tp'],conf['hold'])
    if deal and deal['status']!='censored':
     busy_until[p['sym']]=deal['exitDate']
     all_trades.append({'code':p['code'],'symbol':p['sym'],'model':model_id,**deal})
  result[model_id]={'candidateSignalDays':eligible_days,'eligibleCandidatePairs':candidate_total,
   'executed':len(all_trades),'authorExampleExecutions':sum(t['code'] in sample_codes for t in all_trades),
   'folds':{k:compact_stats([z for z in all_trades if lo<=z['signalDate']<=hi]) for k,(lo,hi) in SPLITS.items()}}
  trade_rows[model_id]=all_trades
 out={'generatedAt':datetime.now(ZoneInfo('Asia/Taipei')).isoformat(timespec='seconds'),
  'status':'historical_backtest_completed','scope':'FULL_CURRENT_UNIVERSE' if max_symbols==0 else 'ALPHABETIC_PILOT_NOT_REPRESENTATIVE',
  'testedUniverse':len(ordered),'usablePriceSeries':len(by_sym),'historyFetchErrors':{k:v for k,v in list(errors.items())[:50]},
  'benchmark':BENCHMARK,'dateRange':{'start':START,'end':'2026-10-27'},'sampleN':19,
  'costs':{'buyBrokerFee':BUY_FEE,'sellBrokerFeePlusTax':SELL_FEE,'slippageEachSide':SLIPPAGE},
  'executionAssumptions':['D 收盤以完成資料選股，D+1 至 D+3 才允許突破買進','每天按 D 收盤資料排序，最多三檔候選',
    '突破時若開盤高於觸發價則以開盤成交，開盤溢價超過 3% 則放棄當日','同日停損與目標同觸及，保守判定停損優先',
    '停利後下一交易日才開始保本；嚴格不假設分鐘 K 先後','剩餘持倉到期以收盤出場；尚未結束者剔除統計'],
  'limitations':['2026 樣本啟發了規則，2026 不能被稱為真正的樣本外回測',
    '當前上市上櫃母體回推至歷史，存在存活者偏差','未處理停牌、漲跌停無法成交與買賣價差的全部影響',
    '獨立交易統計不等於具有資金佔用與部位上限的投組年化報酬',
    '歷史日 K 僅能採保守同日停損優先，無法還原真實分鐘成交順序'],
  'models':result}
 OUT.mkdir(parents=True,exist_ok=True)
 (OUT/'backtest_summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
 (OUT/'backtest_trades.json').write_text(json.dumps({'models':trade_rows},ensure_ascii=False),encoding='utf-8')
 print(json.dumps({'scope':out['scope'],'usable':len(by_sym),'models':result},ensure_ascii=False)[:8000],flush=True)
 return out
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--diagnostics-only',action='store_true')
 parser.add_argument('--max-symbols',type=int,default=0,help='0 means full current universe')
 a=parser.parse_args();x=diagnostics()
 print('author reference sample diagnostics:',x['count'],x['medians'],flush=True)
 if not a.diagnostics_only:run_backtest(a.max_symbols)
if __name__=='__main__':main()
