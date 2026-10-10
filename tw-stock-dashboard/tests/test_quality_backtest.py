"""As-of monthly fundamental backtest must not leak future or hide missing data."""
import unittest
from quality_backtest_core import adjopen,period_return,summary,simulate,screen

class FakeMops:
    def profile(self,market,code,day,price):
        return {"epsYtdYoYPct":25,"revenueYoYPct":20,"ttmEPS":8,
            "revenue12mHighRatioPct":90,"epsAvailableFrom":"2026-04-12",
            "revenueAvailableFrom":"2026-07-16"}

class FakeQuality:
    def at(self,market,code,day):
        return {"roePct":20 if day>="2026-08-22" else None,
            "pbRatio":2,"pbHistoryPercentile3Y":25,"roeAvailableFrom":"2026-08-22","pbAsOf":day}

def history():
    universe=[{"code":str(2000+i),"market":"上市"} for i in range(7)]
    days=["2026-07-30","2026-07-31","2026-08-03","2026-08-31","2026-09-01"]
    bars={}
    for i in range(7):
        key=str(2000+i)+".TW"
        bars[key]={d:{"open":10+i+j,"close":10+i+j,"adjclose":10+i+j} for j,d in enumerate(days)}
    return universe,bars,days

class FactorBacktestTests(unittest.TestCase):
    def test_adjusted_price_corporate_action(self):
        self.assertEqual(adjopen({"open":100,"close":100,"adjclose":50}),50)
        self.assertIsNone(adjopen({"open":0,"close":1,"adjclose":1}))
    def test_future_quality_does_not_apply_in_july(self):
        universe,bars,days=history()
        g,q=screen(universe,bars,FakeMops(),FakeQuality(),"2026-07-31")
        self.assertEqual(len(g),7)
        self.assertEqual(q,[])
        g,q=screen(universe,bars,FakeMops(),FakeQuality(),"2026-08-31")
        self.assertEqual(len(q),7)
    def test_asof_entry_and_fees(self):
        universe,bars,days=history()
        rows=simulate(universe,bars,FakeMops(),FakeQuality(),days)
        self.assertEqual(rows["growth"][0]["entry"],"2026-08-03")
        self.assertEqual(rows["growth"][0]["exit"],"2026-09-01")
        self.assertEqual(rows["growth"][0]["status"],"ok")
        self.assertEqual(rows["quality"][0]["status"],"cash")
        self.assertLess(rows["growth"][0]["netReturn"],1)
    def test_partial_cannot_be_successful_backtest(self):
        z=[{"status":"ok","netReturn":.2},{"status":"missing_adjusted_open","netReturn":None}]
        self.assertEqual(summary(z,"2026-01-01","2026-03-01")["status"],"incomplete_history")
        self.assertEqual(summary([{"status":"cash","netReturn":0}],"2026-01-01","2026-02-01")["status"],"insufficient_data")
    def test_missing_quality_never_zero_return(self):
        universe,bars,days=history()
        rows=simulate(universe,bars,FakeMops(),None,days)
        self.assertIsNone(rows["quality"][0]["netReturn"])
        self.assertEqual(rows["quality"][0]["status"],"missing_quality_archive")
    def test_profit_is_net_of_all_costs(self):
        universe,bars,days=history()
        picks=[{"symbol":str(2000+i)+".TW"} for i in range(5)]
        gross=sum((15+i)/(12+i)-1 for i in range(5))/5
        ret,flag=period_return(picks,bars,"2026-08-03","2026-09-01")
        self.assertEqual(flag,"ok")
        self.assertLess(ret,gross)

if __name__=="__main__":unittest.main()
