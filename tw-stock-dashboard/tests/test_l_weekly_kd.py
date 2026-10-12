import unittest
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd,numpy as np
from l_weekly_kd import weekly_bars,last_completed_week,revenue_ok,trades_for_stock,summarize

class Archive:
    def __init__(self,allowed):self.allowed=allowed
    def profile(self,market,code,day,price,history=None):
        if day<self.allowed:return {"revenueMoMPct":None,"revenueYoYPct":None,"revenueFiscal":None,"revenueAvailableFrom":None}
        return {"revenueMoMPct":-2,"revenueYoYPct":3,"revenueFiscal":"2026-08","revenueAvailableFrom":self.allowed}

class WeeklyKDL(unittest.TestCase):
    def setUp(self):
        self.info={"code":"2330","name":"台積電","market":"上市","industry":"半導體"}
        self.now=lambda time:datetime.fromisoformat(time).replace(tzinfo=ZoneInfo("Asia/Taipei"))
    def test_friday_only_after_close_and_monday_is_previous_week(self):
        self.assertEqual(str(last_completed_week(self.now("2026-10-12T18:00:00"),"2026-10-12")),"2026-10-03/2026-10-09")
        self.assertEqual(str(last_completed_week(self.now("2026-10-16T12:00:00"),"2026-10-16")),"2026-10-03/2026-10-09")
        self.assertEqual(str(last_completed_week(self.now("2026-10-16T14:30:00"),"2026-10-16")),"2026-10-10/2026-10-16")
    def test_kd_uses_completed_9week_rsv_recursive_50(self):
        days=pd.bdate_range("2025-01-06",periods=220)
        p=np.linspace(60,105,len(days))
        df=pd.DataFrame({"date":days.strftime("%Y-%m-%d"),"open":p,"high":p+2,"low":p-2,"close":p,"volume":1e6,"adjclose":p})
        w=weekly_bars(df)
        self.assertGreater(len(w),26)
        self.assertTrue(pd.isna(w.iloc[7]["K"]))
        self.assertTrue(np.isfinite(w.iloc[8]["K"]))
        self.assertFalse(bool(w.iloc[8]["golden"]),"First valid RSV cannot be a confirmed K-cross")
        self.assertTrue((w.K.dropna().between(0,100)).all())
        self.assertTrue((w.D.dropna().between(0,100)).all())
    def test_mops_or_filter_and_available_as_of(self):
        self.assertIsNone(revenue_ok(Archive("2026-09-16"),self.info,"2026-09-15"))
        r=revenue_ok(Archive("2026-09-16"),self.info,"2026-09-18")
        self.assertEqual(r["revenueYoYPct"],3);self.assertLess(r["revenueMoMPct"],0)
        self.assertIsNone(revenue_ok(Archive("2026-10-16"),self.info,"2026-10-12"))
    def test_partial_current_week_never_counts_as_forward_return(self):
        weeks=pd.period_range("2026-04-10",periods=28,freq="W-FRI")
        w=pd.DataFrame({"signalDate":[x.end_time.strftime("%Y-%m-%d") for x in weeks],
             "entryDate":[(x.start_time+pd.Timedelta(days=2)).strftime("%Y-%m-%d") for x in weeks],
             "close":[100.]*len(weeks),"open":[100.]*len(weeks),
             "adjopen":[100.]*len(weeks),"adjclose":[100.]*len(weeks),
             "volume":[1000]*len(weeks),"K":[25.]*len(weeks),"D":[20.]*len(weeks),
             "strict40":[False]*len(weeks)},index=weeks)
        signal=pd.Period("2026-10-03/2026-10-09",freq="W-FRI")
        self.assertIn(signal,w.index)
        w.loc[signal,"strict40"]=True
        t=trades_for_stock(self.info,w,Archive("2026-09-16"),"2026-10-12",now=self.now("2026-10-12T18:00:00"))
        self.assertEqual(t,[],"The week of 10/12 is not complete and cannot be a backtested 1W exit")
        t=trades_for_stock(self.info,w,Archive("2026-09-16"),"2026-10-16",now=self.now("2026-10-16T15:00:00"))
        self.assertEqual([z["horizon"] for z in t],[1])
        self.assertEqual(t[0]["entryDate"],"2026-10-12")
        self.assertEqual(t[0]["netPct"],-0.585)
    def test_summary_missing_forward_horizons_is_not_zero_gain(self):
        s=summarize([])
        self.assertIsNone(s["all"]["1"]["avgNetPct"])
        self.assertEqual(s["2026"]["3"]["n"],0)

if __name__=="__main__":unittest.main()
