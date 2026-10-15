"""No night/day label leakage or fake score gain in pilot backtest."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from backtest_tx_night_score import delta,make_archive,test_cases,render
class TXNightPilotTests(unittest.TestCase):
    def test_exact_production_thresholds(self):
        for pct,expected in [(-2,-25),(-1.736,-15),(-1,-15),(-.7,-8),(-.5,-8),(-.49,0),(0,0),(.5,4),(1,7),(2,10)]:
            self.assertEqual(delta(pct),expected)
    def test_causal_pair_only_next_trading_day_night(self):
        risk=("date,score,dayRet,breadth\n2026-07-09,70,0,40\n2026-07-10,30,-1.3,20\n")
        fut=("Date,Contract,ContractMonth(Week),Last,Volume,TradingSession,process_timestamp\n"
             "20260709,TX,202607,100,1000,一般,2026-07-09 15:00\n"
             "20260709,TX,202607,101,1000,盤後,2026-07-10 07:00\n"
             "20260710,TX,202607,98.264,900,盤後,2026-07-10 06:00\n")
        _,data,missing=test_cases(risk,make_archive(fut))
        self.assertEqual(len(data),1)
        self.assertEqual(data[0]["cashPreviousRiskScore"],70)
        self.assertEqual(data[0]["txDelta"],-15)
        self.assertEqual(data[0]["nextCashReferenceScore"],55)
        self.assertEqual(data[0]["date"],"2026-07-10")
    def test_missing_same_contract_is_not_backfilled(self):
        risk="date,score,dayRet,breadth\n2026-07-09,70,0,40\n2026-07-10,30,-1,20\n"
        fut=("Date,Contract,ContractMonth(Week),Last,Volume,TradingSession\n"
             "20260709,TX,202607,100,1000,一般\n"
             "20260710,TX,202608,97,1000,盤後\n")
        _,data,missing=test_cases(risk,make_archive(fut))
        self.assertEqual(data,[]);self.assertEqual(len(missing),1)
if __name__=="__main__":unittest.main()
