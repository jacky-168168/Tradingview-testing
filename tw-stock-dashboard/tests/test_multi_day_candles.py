import unittest
import pandas as pd
from multi_day_candles import aggregate_bars,candle_test,latest_pair,rel_pct

class TestMultiDayCandles(unittest.TestCase):
    def make_df(self,n=40):
        days=pd.bdate_range("2026-01-01",periods=n)
        rows=[{"date":d.strftime("%Y-%m-%d"),"open":100.0,"high":105.0,"low":95.0,"close":101.0,"volume":10000} for d in days]
        return pd.DataFrame(rows),[x["date"] for x in rows]
    def test_3d_group_ohlc(self):
        df,cal=self.make_df(9)
        df.loc[0,"open"]=100;df.loc[0,"low"]=93
        df.loc[1,"high"]=110;df.loc[2,"close"]=108
        bars=aggregate_bars(df,cal,3)
        self.assertEqual(len(bars),3)
        self.assertEqual(bars.iloc[0]["open"],100)
        self.assertEqual(bars.iloc[0]["high"],110)
        self.assertEqual(bars.iloc[0]["low"],93)
        self.assertEqual(bars.iloc[0]["close"],108)
        self.assertTrue(bool(bars.complete.all()))
    def test_incomplete_18d_never_confirmed(self):
        df,cal=self.make_df(40)
        part=df.iloc[:25]
        bars=aggregate_bars(part,cal,18)
        self.assertEqual(len(bars),2)
        self.assertTrue(bool(bars.iloc[0].complete))
        self.assertFalse(bool(bars.iloc[1].complete))
        p,c=latest_pair(bars,cal[24],True)
        self.assertIsNone(c)
    def test_only_confirmed_3d_pattern(self):
        df,cal=self.make_df(7)
        a=aggregate_bars(df,cal,3)
        self.assertEqual([bool(x) for x in a.complete],[True,True,False])
        p,c=latest_pair(a,cal[6],True)
        self.assertEqual(c["expectedEnd"],cal[5])
        p,c=latest_pair(a,cal[6],False)
        self.assertEqual(c["date"],cal[6])
        self.assertFalse(c["complete"])
    def test_bull_body_engulf_not_equal_range_engulf(self):
        prev={"open":105,"close":98,"high":110,"low":96}
        curr={"open":97,"close":106,"high":107,"low":97}
        flags=candle_test(prev,curr)
        self.assertTrue(flags["bodyEngulf"])
        self.assertFalse(flags["rangeEngulf"])
        self.assertTrue(flags["halfRecover"])
    def test_bullish_outside_range_engulf(self):
        a={"open":105,"close":99,"high":108,"low":95}
        b={"open":97,"close":109,"high":112,"low":94}
        f=candle_test(a,b)
        self.assertTrue(f["bodyEngulf"]);self.assertTrue(f["rangeEngulf"])
    def test_no_reversal_if_prev_up(self):
        f=candle_test({"open":98,"close":100,"high":104,"low":93},{"open":97,"close":110,"high":112,"low":90})
        self.assertFalse(f["bodyEngulf"])
    def test_asof_requires_data_trim(self):
        df,cal=self.make_df(18)
        first=aggregate_bars(df.iloc[:12],cal,3)
        self.assertEqual(str(first.iloc[-1].date),cal[11])
        self.assertEqual(len(first),4)
        self.assertEqual(first.iloc[-1].expectedEnd,cal[11])
    def test_percent(self):
        self.assertEqual(rel_pct(105,100),5.0)

if __name__=="__main__":unittest.main()
