import unittest
import pandas as pd
from backtest_g_exec_comparison import prepare_bars,execution,MA_WINDOWS
class TestGExecutionCompare(unittest.TestCase):
    def df(self,ends):
        rows=[]
        for i in range(90):
            rows.append({"date":f"2026-01-{i+1:03d}","open":100,"high":100.5,"low":99.5,"close":100})
        for i,(o,h,l,c) in enumerate(ends):
            rows.append({"date":f"2026-02-{i+1:03d}","open":o,"high":h,"low":l,"close":c})
        return prepare_bars(pd.DataFrame(rows))
    def test_four_mas_each_once_only_when_touched(self):
        x=self.df([(101,101,99,100),(108,109,105,108)]+[(100,100,100,100)]*10)
        r=execution(x,90,100,5,"ma")
        self.assertEqual(r["status"],"filled")
        self.assertEqual(r["tranches"],4)
        self.assertEqual(sorted(r["maFilled"]),[5,10,20,60])
        self.assertTrue(r["tp"])
        self.assertEqual(r["exitDate"],"2026-02-002")
    def test_ma_no_candle_touch_no_buy(self):
        x=self.df([(110,113,108,112)]*12)
        r=execution(x,90,100,5,"ma")
        self.assertEqual(r["status"],"unfilled")
    def test_ladder_first_limit_persists_across_three_sessions(self):
        x=self.df([(100,101,99,100),(99,100,98,99),(98,99,97,98),(100,102,99,100),
                   (107,108,105,106)]+[(100,101,99,100)]*8)
        r=execution(x,90,100,5,"ladder")
        self.assertEqual(r["status"],"filled")
        self.assertEqual(r["firstEntryDate"],"2026-02-003")
        self.assertEqual(r["tranches"],1)
        self.assertTrue(r["tp"])
    def test_ladder_no_entry_in_first_five(self):
        x=self.df([(105,106,102,104)]*13)
        r=execution(x,90,100,5,"ladder")
        self.assertEqual(r["status"],"unfilled")
    def test_five_ladder_buy_orders(self):
        x=self.df([(100,102,97.4,98),(97,98,89,90)]+[(94,95,93,94)]*12)
        r=execution(x,90,100,5,"ladder")
        self.assertEqual(r["tranches"],5)
        self.assertEqual([z["type"] for z in r["fills"]],["L1","L2","L3","L4","L5"])
        self.assertEqual(r["status"],"filled")
    def test_ma_weakness_exit_and_no_tracking(self):
        x=self.df([(101,101,99,100),(101,101,99,100)]+[(100,100,99,100)]*10)
        x.loc["2026-02-001","weak"]=True
        r=execution(x,90,100,5,"ma")
        self.assertEqual(r["reason"],"weak_exit")
        self.assertEqual(r["exitDate"],"2026-02-002")
        x.loc["2026-01-090","weak"]=True
        self.assertEqual(execution(x,90,100,5,"ma")["status"],"weak_cancel")
    def test_previous_day_ma_only(self):
        x=self.df([(109,111,108,110)]*10)
        r=execution(x,90,100,5,"ma")
        self.assertEqual(r["status"],"unfilled")
if __name__=="__main__":unittest.main()
