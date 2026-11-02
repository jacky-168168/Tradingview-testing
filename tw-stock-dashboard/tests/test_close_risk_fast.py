"""獨立盤後 Risk Score 日期/來源驗證測試；不使用假報價對外發布。"""
import json, sys, unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
import close_risk_fast as m

class CloseRiskFastTests(unittest.TestCase):
    def test_recognize_exchange_roc_dates(self):
        self.assertEqual(m.parse_twse_day("115/11/02"),"2026-11-02")
        self.assertEqual(m.parse_twse_day("2026-11-02"),"2026-11-02")
        self.assertEqual(m.parse_twse_day("115年11月02日"),"2026-11-02")
        self.assertIsNone(m.parse_twse_day("not_a_day"))
    def test_match_requested_official_index_day(self):
        report={"stat":"OK","tables":[{"fields":["日期","發行量加權股價指數"],"data":[["115/11/01","46,123.45"],["115/11/02","45,123.45"]]}]}
        with patch.object(m,"_report",return_value=report):
            self.assertEqual(m.twse_verified_index_close("2026-11-02"),45123.45)
            with self.assertRaisesRegex(RuntimeError,"not verified"):
                m.twse_verified_index_close("2026-11-03")
    def test_no_score_outside_postclose_window(self):
        self.assertIsNone(m.compute(datetime(2026,11,2,12,0,tzinfo=ZoneInfo("Asia/Taipei"))))
    def test_never_publish_yesterday_as_today(self):
        # 此測試不需要完成 risk.build；日期未匹配即應拒絕。
        from unittest.mock import Mock
        import pandas as pd
        dates=pd.date_range("2026-04-01",periods=170, freq="B")
        fake=pd.DataFrame({"date":[x.date().isoformat() for x in dates],"close":[30000.0]*len(dates),
            "high":[30500.0]*len(dates),"low":[29500.0]*len(dates),"volume":[100000.0]*len(dates)})
        with patch.object(m,"twse_verified_index_close",return_value=45000.0),\
             patch.object(m,"update_symbol",return_value=("^TWII",fake,None)):
            with self.assertRaisesRegex(RuntimeError,"BENCHMARK_YAHOO_DATE_STALE"):
                m.compute(datetime(2026,11,2,19,0,tzinfo=ZoneInfo("Asia/Taipei")))
if __name__=="__main__":
    unittest.main()
