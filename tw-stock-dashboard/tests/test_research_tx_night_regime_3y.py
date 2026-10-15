import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from research_tx_night_regime_3y import delta,normalize,pair,compare
class TestTXBacktest(unittest.TestCase):
    def test_shared_thresholds(self):
        for pct,expected in [(-2.1,-25),(-2,-25),(-1.8,-15),(-1,-15),(-.7,-8),(-.5,-8),(-.4,0),(0,0),(.5,4),(1,7),(2,10)]:
            self.assertEqual(delta(pct),expected)
    def test_next_trading_day_night_and_matching_contract(self):
        risk=[{"date":"2025-10-06","score":"70","index":"20000"},
              {"date":"2025-10-07","score":"50","index":"19400"},
              {"date":"2025-10-08","score":"70","index":"19500"}]
        futures=[{"date":"2025-10-06","contract_date":"202510","trading_session":"position","close":20000,"volume":45000},
          {"date":"2025-10-07","contract_date":"202510","trading_session":"after_market","close":19600,"volume":30000},
          {"date":"2025-10-07","contract_date":"202510","trading_session":"position","close":19400,"volume":45000},
          {"date":"2025-10-08","contract_date":"202511","trading_session":"after_market","close":19650,"volume":60000}]
        rows,missing=pair(risk,normalize(futures))
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]["decisionDate"],"2025-10-07")
        self.assertEqual(rows[0]["txDelta"],-25);self.assertEqual(rows[0]["adjusted"],45)
        self.assertEqual(rows[0]["outcomeCloseToClosePct"],-3)
        self.assertEqual(missing["near_month_roll_mismatch"],1)
    def test_no_future_or_unmatched_night(self):
        risk=[{"date":"2025-10-06","score":"70","index":"20000"},{"date":"2025-10-07","score":"70","index":"19000"}]
        tx=normalize([{"date":"2025-10-07","contract_date":"202510","trading_session":"position","close":19000,"volume":30000},
          {"date":"2025-10-07","contract_date":"202510","trading_session":"after_market","close":19300,"volume":30000}])
        rows,missing=pair(risk,tx);self.assertEqual(len(rows),0);self.assertEqual(missing["prior_day_regular_missing"],1)
    def test_same_sample_loss_vs_opportunity(self):
        row={"score":70,"adjusted":55,"txPct":-1.5,"outcomeCloseToClosePct":-3.2}
        result=compare([row]);self.assertEqual(result["official60"]["pass"],1)
        self.assertEqual(result["TXadjust60"]["pass"],0);self.assertEqual(result["TXadjust60"]["avoidedOfAllLoss3Pct"],100)
if __name__=="__main__":unittest.main()
