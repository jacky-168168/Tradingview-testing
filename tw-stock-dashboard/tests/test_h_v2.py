import unittest
from datetime import date,timedelta
import numpy as np,pandas as pd
from h_v2 import indicators,exit_trade,turnover_proxy_pct,SPEC
class TestH2(unittest.TestCase):
    def bar(self,d,op,hi,lo,cl,vol):
        return {"date":str(d),"open":op,"high":hi,"low":lo,"close":cl,"adjclose":cl,"volume":vol}
    def setup_bars(self):
        start=date(2025,1,1)
        xs=[]
        for i in range(135):
            d=start+timedelta(days=i)
            xs.append(self.bar(d,101,102,100,101.5,1_000_000))
        for i in range(127,135):
            xs[i]=self.bar(start+timedelta(days=i),103.5,106 if i<131 else 105,100 if i<131 else 103,104,800_000)
        xs.append(self.bar(start+timedelta(days=135),104,108,103,107,2_200_000))
        return pd.DataFrame(xs)
    def test_turnover_proxy(self):
        self.assertAlmostEqual(turnover_proxy_pct(1_000_000,3),3.333333,places=4)
        self.assertIsNone(turnover_proxy_pct(1_000_000,0))
    def test_signal_is_consolidation_breakout_without_other_models(self):
        df=self.setup_bars()
        selected=indicators(df,3)
        d=df.iloc[-1]["date"]
        self.assertIn(d,set(selected["date"].astype(str)))
        assert float(selected.iloc[-1]["breakout8Pct"])>0.2
        assert float(selected.iloc[-1]["turnoverAvg5"])>1.5
    def test_future_bars_do_not_change_past_signals(self):
        df=self.setup_bars()
        signals_before=indicators(df,3)
        df2=pd.concat([df,pd.DataFrame([self.bar(date(2025,5,17),130,150,125,140,5_000_000)])],ignore_index=True)
        signals_after=indicators(df2,3)
        d=df.iloc[-1]["date"]
        self.assertEqual((signals_before.date.astype(str)==d).any(),(signals_after.date.astype(str)==d).any())
    def make_trade(self,rows):
        df=pd.DataFrame([self.bar(*x) for x in rows])
        return df.set_index("date",drop=False)
    def test_tp_stop_first_and_costs(self):
        d="2026-02-02"
        q=self.make_trade([(d,100,110,98,105,1_000_000)])
        out=exit_trade(q,d,d,99.0)
        self.assertEqual(out["status"],"filled")
        self.assertEqual(out["reason"],"tp")
        self.assertLess(out["netPct"],7)
        q=self.make_trade([(d,100,115,95,100,1_000_000)])
        out=exit_trade(q,d,d,99.0)
        self.assertEqual(out["reason"],"stop")
        self.assertLess(out["netPct"],-3.5)
    def test_open_gap_limit_and_gap_loss(self):
        d="2026-02-02"
        x=self.make_trade([(d,104,108,102,105,1_000_000)])
        self.assertEqual(exit_trade(x,d,d,100)["status"],"gap_skip")
        x=self.make_trade([(d,91,93,90,92,1_000_000)])
        out=exit_trade(x,d,d,100)
        self.assertEqual(out["status"],"filled")
        self.assertLess(out["netPct"],0)
if __name__=="__main__":unittest.main()
