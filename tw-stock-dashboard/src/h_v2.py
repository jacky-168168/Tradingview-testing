"""H2 independent high-turnover consolidation breakout, precommitted before 2026 test.
References: Taiwan intraday-momentum / persistent-momentum studies and breakout-consolidation research.
No A/D/F/G stock selection scores, thresholds, candidates or market regime inputs.
"""
from __future__ import annotations
import numpy as np,pandas as pd

SPEC={
    "turnover_proxy_today_pct_min":3.0,
    "turnover_proxy_previous5_pct_min":1.5,
    "volume_ratio_10_min":1.3,
    "prior8day_range_pct_max":18.0,
    "prior4_range_as_fraction_prior8_max":0.90,
    "prior3_volume_vs_prior20_max":1.15,
    "prior5_return_pct_min":-4.0,
    "prior5_return_pct_max":8.0,
    "close_to_prior120high_min":0.82,
    "breakout_above_prior8high_min_pct":0.2,
    "breakout_above_prior8high_max_pct":7.0,
    "signal_day_gain_pct_min":0.5,
    "signal_day_gain_pct_max":7.0,
    "signal_body_pct_min":0.5,
    "signal_close_range_position_min":0.70,
    "share_price_min":15.0,
    "traded_value_ntd_min":100_000_000,
    "overnight_buy_limit_pct":2.5,
    "take_profit_gross_pct":7.0,
    "stop_loss_gross_pct":3.5,
    "slippage_each_side_pct":0.1,
    "buy_broker_fee_pct":0.1425,
    "sell_broker_fee_pct":0.1425,
    "sell_tax_pct":0.30,
}
def turnover_proxy_pct(volume,capital_b):
    """Current paid-in capital / nominal 10 TWD share value is only an estimate."""
    try:
        v,c=float(volume),float(capital_b)
        if not np.isfinite(v) or not np.isfinite(c) or v<=0 or c<=0:return None
        return 100*v/(c*10_000_000)
    except (TypeError,ValueError):return None
def indicators(df,capital_b):
    if df is None or df.empty:return pd.DataFrame()
    x=df.sort_values("date").drop_duplicates("date",keep="last").reset_index(drop=True).copy()
    for k in ("open","high","low","close","volume"):x[k]=pd.to_numeric(x[k],errors="coerce")
    o,h,l,c,v=(x[k] for k in ("open","high","low","close","volume"))
    shares=capital_b*10_000_000
    x["turnoverProxyPct"]=v/shares*100
    x["turnoverAvg5"]=v.shift(1).rolling(5).mean()/shares*100
    x["volumeRatio10"]=v/v.shift(1).rolling(10).mean()
    high8=h.shift(1).rolling(8).max();low8=l.shift(1).rolling(8).min()
    high4=h.shift(1).rolling(4).max();low4=l.shift(1).rolling(4).min()
    range8=high8/low8-1;range4=high4/low4-1
    x["prior8RangePct"]=range8*100
    x["prior4to8Range"]=range4/range8.replace(0,np.nan)
    x["prior3Vs20Volume"]=v.shift(1).rolling(3).mean()/v.shift(1).rolling(20).mean()
    x["prior5RetPct"]=(c.shift(1)/c.shift(6)-1)*100
    x["near120High"]=c/h.shift(1).rolling(120,min_periods=90).max()
    x["breakout8Pct"]=(c/high8-1)*100
    x["dayGainPct"]=(c/c.shift(1)-1)*100
    x["bodyPct"]=(c/o-1)*100
    x["closePos"]=(c-l)/(h-l).replace(0,np.nan)
    x["tradedValue"]=c*v
    cols=["turnoverProxyPct","turnoverAvg5","volumeRatio10","prior8RangePct",
          "prior4to8Range","prior3Vs20Volume","prior5RetPct","near120High",
          "breakout8Pct","dayGainPct","bodyPct","closePos","tradedValue"]
    valid=np.isfinite(x[cols].to_numpy(dtype=float)).all(axis=1)
    s=SPEC
    good=valid&(c>=s["share_price_min"])&(x.tradedValue>=s["traded_value_ntd_min"])
    good&=(x.turnoverProxyPct>=s["turnover_proxy_today_pct_min"])&(x.turnoverAvg5>=s["turnover_proxy_previous5_pct_min"])
    good&=(x.volumeRatio10>=s["volume_ratio_10_min"])
    good&=(x.prior8RangePct<=s["prior8day_range_pct_max"])&(x.prior8RangePct>0)
    good&=(x.prior4to8Range<=s["prior4_range_as_fraction_prior8_max"])
    good&=(x.prior3Vs20Volume<=s["prior3_volume_vs_prior20_max"])
    good&=x.prior5RetPct.between(s["prior5_return_pct_min"],s["prior5_return_pct_max"],inclusive="both")
    good&=(x.near120High>=s["close_to_prior120high_min"])
    good&=x.breakout8Pct.between(s["breakout_above_prior8high_min_pct"],s["breakout_above_prior8high_max_pct"],inclusive="both")
    good&=x.dayGainPct.between(s["signal_day_gain_pct_min"],s["signal_day_gain_pct_max"],inclusive="both")
    good&=(x.bodyPct>=s["signal_body_pct_min"])&(x.closePos>=s["signal_close_range_position_min"])
    # Score only compares stocks already passing H2; uses no D/G factors.
    clip=lambda z:np.clip(z,0,1)
    x["HScore"]=(25*clip((x.turnoverAvg5-1.5)/4)+20*clip((x.turnoverProxyPct-3)/9)+
        20*clip((x.volumeRatio10-1.3)/2.5)+20*clip((x.near120High-0.82)/0.18)+
        15*clip((x.closePos-0.70)/0.30)).round(3)
    return x.loc[good].copy()
def adjusted_price(row,field):
    raw=row.get(field);close=row.get("close");adjusted=row.get("adjclose")
    if raw is None or pd.isna(raw):return None
    if close is not None and pd.notna(close) and float(close)>0 and adjusted is not None and pd.notna(adjusted):
        return float(raw)*float(adjusted)/float(close)
    return float(raw)
def exit_trade(px,buydate,exitdate,signal_close):
    """Next-session predeclared limit-at-open; conservative stop-first daily OHLC.
    A buy limit prevents paying > signal-close + 2.5%. For gaps above it, order remains
    unfilled in this model (no assumed intraday entry). Gaps down do fill at open.
    """
    if px is None or buydate not in px.index or exitdate not in px.index:return None
    q=px.loc[buydate:exitdate]
    if len(q)==0:return None
    entryrow=q.iloc[0]
    op=float(entryrow["open"])
    if not np.isfinite(op) or op<=0:return None
    buy_cap=signal_close*(1+SPEC["overnight_buy_limit_pct"]/100)
    if op>buy_cap:return {"status":"gap_skip"}
    rawcloses=pd.to_numeric(q["close"],errors="coerce")
    ratio=rawcloses/rawcloses.shift(1)
    if ((ratio<.55)|(ratio>1.8)).fillna(False).any():return None
    paid=adjusted_price(entryrow,"open")
    if paid is None or paid<=0:return None
    paid*=1+SPEC["slippage_each_side_pct"]/100
    target=paid*(1+SPEC["take_profit_gross_pct"]/100)
    stop=paid*(1-SPEC["stop_loss_gross_pct"]/100)
    result=None
    for _,row in q.iterrows():
        o,h,l,c=[adjusted_price(row,k) for k in ("open","high","low","close")]
        if any(v is None or not np.isfinite(v) or v<=0 for v in (o,h,l,c)):return None
        if o<=stop:price=o;reason="stop_gap"
        elif o>=target:price=o;reason="tp_gap"
        elif l<=stop:price=stop;reason="stop"
        elif h>=target:price=target;reason="tp"
        elif str(row["date"])==exitdate:price=c;reason="timeout"
        else:continue
        net=(price*(1-SPEC["slippage_each_side_pct"]/100)*(1-(SPEC["sell_broker_fee_pct"]+SPEC["sell_tax_pct"])/100)/(paid*(1+SPEC["buy_broker_fee_pct"]/100))-1)*100
        result={"status":"filled","exitDate":str(row["date"]),"reason":reason,
                "grossPct":round((price/paid-1)*100,4),"netPct":round(net,4)}
        break
    return result
