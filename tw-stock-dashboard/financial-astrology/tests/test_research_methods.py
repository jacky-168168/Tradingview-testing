import sys
import unittest
from datetime import date,timedelta
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_methods import global_fdr,regime_control,strategy_comparison
from backtest import event_to_session_index,catalog_stats

class FinancialAstrologyResearchMethodsTests(unittest.TestCase):
    def setUp(self):
        first=date(2010,1,4)
        calendar=[first+timedelta(days=i) for i in range(6000)]
        trading_days=[d for d in calendar if d.weekday()<5]
        self.prices=[(d,100+0.03*i+1.4*((i%45)/45)) for i,d in enumerate(trading_days)]
        self.events=[{"exactUtc":datetime_str(self.prices[i][0])}
                     for i in range(150,3500,300)]
    def test_global_fdr_stricter_than_one_market_bh(self):
        markets={"NASDAQ":{"status":"ok","horizons":[{"pValue":0.01},{"pValue":0.5}]},
                 "DAX":{"status":"ok","horizons":[{"pValue":0.02},{"pValue":0.7}]},
                 "FTSE100":{"status":"unavailable","horizons":[]}}
        total=global_fdr(markets)
        self.assertEqual(total,4)
        for record in [x for v in markets.values() for x in v["horizons"]]:
            self.assertGreaterEqual(record["globalFdrQValue"],record["pValue"])
            self.assertEqual(record["globalFdrHypotheses"],4)
            self.assertFalse(record["significanceClaim"])
    def test_strategies_are_offline_long_flat_with_positive_cost(self):
        strategy=strategy_comparison(self.prices,self.events,"Asia/Taipei",event_to_session_index,20)
        self.assertEqual(strategy["status"],"observational_only")
        self.assertEqual(strategy["costBpsPerSide"],5.0)
        self.assertGreater(strategy["eventStarts"],3)
        self.assertEqual(set(strategy["report"]),{"passive","ma20","ma20_plus_astrology"})
        self.assertLessEqual(strategy["report"]["ma20_plus_astrology"]["exposureFraction"],
                             strategy["report"]["ma20"]["exposureFraction"])
        for item in strategy["report"].values():
            self.assertGreater(item["all"]["observations"],100)
            self.assertLessEqual(item["all"]["maxDrawdown"],0)
    def test_regime_controls_exclude_event_windows_and_never_claim_trading_signal(self):
        for h in (5,20,60):
            event_samples=[]
            for event in self.events:
                idx=event_to_session_index(event,[x[0] for x in self.prices],"Asia/Taipei")
                if idx and idx+h<len(self.prices):
                    event_samples.append({"entryIndex":idx,"return":self.prices[idx+h][1]/self.prices[idx][1]-1})
            first=regime_control(event_samples,self.prices,h,draws=100)
            second=regime_control(event_samples,self.prices,h,draws=100)
            self.assertEqual(first,second)
            self.assertIn(first["status"],{"insufficient","descriptive"})
            if first["status"]=="descriptive":
                self.assertGreaterEqual(first["matchedEvents"],5)
                self.assertLessEqual(first["permutationPValue"],1)
    def test_other_event_types_are_summary_only(self):
        catalog={"studyFamilies":{
            "full_moon":{"label":"滿月","events":self.events},
            "mars_jupiter_conjunction":{"label":"原有","events":self.events}}}
        result=catalog_stats(catalog,self.prices,"Asia/Taipei")
        self.assertNotIn("mars_jupiter_conjunction",result)
        item=result["full_moon"]["horizons"][4]
        self.assertGreater(item["sampleSize"],0)
        self.assertIsNone(item["globalFdrQValue"])
        self.assertEqual(item["evidence"]["direction"],"無法判定")
        self.assertNotIn("events",item)

def datetime_str(d):
    return d.isoformat()+"T10:00:00.000Z"

if __name__=="__main__":unittest.main()
