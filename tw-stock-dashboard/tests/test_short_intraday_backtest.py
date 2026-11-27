"""Synthetic bars exercise execution timing/costs ONLY, never fabricated research."""
import sys
import unittest
from datetime import date, datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"research"))
import short_intraday_backtest as bt

TZ=ZoneInfo("Asia/Taipei")
BASE=date(2026,11,10)

def make_day(d=BASE,price=100,gap=0):
    row=[]
    for i in range(54):
        at=datetime.combine(d,time(9,0),TZ)+timedelta(minutes=5*i)
        o=c=price*(1+gap)
        h=o+0.5;l=o-0.5
        if i==0:h=o+1.0;l=o-0.3
        if i==1:h=o+.6;l=o-.4
        if i==2:h=o+.8;l=o-.5
        if i==3:o=price*(1+gap)-.8;c=o-.7;h=o+.1;l=c-.1
        if i==4:o=price*(1+gap)-1.52;c=o-.3;h=o+.1;l=c-.6
        if i>=5:o=c=price*(1+gap)-2
        row.append({"at":at,"o":o,"h":max(h,o,c),"l":min(l,o,c),"c":c,
                    "v":50000 if i<3 else 100000})
    return row

class ShortResearchTests(unittest.TestCase):
    def test_costs_on_flat_trade_are_negative_and_sell_tax_only(self):
        bars=make_day()
        # Exact flat forced buyback isolates only commission and sell-side tax.
        for bar in bars:
            if bar["at"].strftime("%H:%M")=="13:20":
                bar["o"]=100.;bar["h"]=100.;bar["l"]=100.;bar["c"]=100.
        sample=bt.simulate_exit(bars,"13:20",100,110,80,bt.STANDARD_COMMISSION,0)
        self.assertIsNotNone(sample)
        self.assertAlmostEqual(sample["net_pct"],-.435,places=3)
        self.assertEqual(sample["exit_reason"],"time_exit_1320")
    def test_intrabars_use_stop_first_not_winning_target(self):
        bars=make_day()
        for bar in bars:
            if bar["at"].strftime("%H:%M")=="09:20":
                bar["o"]=99.;bar["h"]=103.;bar["l"]=90.;bar["c"]=96.
                break
        sample=bt.simulate_exit(bars,"09:20",99,101,96,bt.STANDARD_COMMISSION,0)
        self.assertEqual(sample["exit_reason"],"stop_first")
        self.assertLess(sample["net_pct"],0)
    def test_signal_is_finished_bar_next_open_and_no_repainting(self):
        bars=make_day()
        day=bt.group_daily(bars)[BASE]
        feats={"prev_close":101.,"atr":2.,"atr_pct":.02,
               "turnover20":5e8,"rel5":-.06,"open15median":60000.}
        out=bt.one_day("1234.TW",BASE,day,feats)
        self.assertTrue(out,"A must trigger below completed opening range and session VWAP")
        x=out[0]
        self.assertEqual(x["mode"],"A_WEAK_CONTINUATION")
        self.assertEqual(x["signal_time"],"09:15")
        self.assertEqual(x["entry_time"],"09:20")
        self.assertTrue(x["signal_at_bar_close"] and x["entry_next_bar_open"])
        self.assertLess(x["net_pct"],x["gross_pct"])
    def test_mode_b_requires_reversal_from_gapup_and_upwick(self):
        bars=make_day(gap=.025)
        day=bt.group_daily(bars)[BASE]
        feats={"prev_close":100.,"atr":3.,"atr_pct":.03,
               "turnover20":5e8,"rel5":.03,"open15median":60000.}
        got=bt.one_day("2222.TW",BASE,day,feats)
        self.assertTrue(got)
        self.assertEqual(got[0]["mode"],"B_GAPUP_FAILURE")
    def test_incomplete_session_is_rejected_and_no_price_imputation(self):
        bars=make_day()
        self.assertNotIn(BASE,bt.group_daily(bars[:28]))
        self.assertEqual(bt.group_daily(bars)[BASE]["bars"]["13:25"]["at"].hour,13)
    def test_no_market_data_does_not_return_successful_backtest(self):
        out=bt.evaluate({})
        self.assertEqual(out["status"],"unavailable")
    def test_metrics_use_net_not_gross_and_drawdown_monotonic(self):
        trades=[{"date":"2026-11-16","entry_time":"09:20","symbol":"0001","net_pct":2.0,"exit_reason":"target_limit"},
                {"date":"2026-11-17","entry_time":"10:10","symbol":"0001","net_pct":-3.0,"exit_reason":"stop_first"}]
        m=bt.metrics(trades)
        self.assertEqual(m["net_twd"],-1000)
        self.assertEqual(m["trades"],2)
        self.assertEqual(m["win_rate_pct"],50)
        self.assertLess(m["max_drawdown_twd"],0)

if __name__=="__main__":unittest.main()
