"""No future-day pocket contamination, one-year anchoring, disclosure, parity."""
import unittest
from datetime import date
import pandas as pd
from reconstruct_g_history_2m import reconstruct,compare_real_archive,historical_panel,VERSION
from repeated_rankings import months_before

class GHistoryReconstructionTests(unittest.TestCase):
    def test_replay_previous_pockets_not_today(self):
        days=["2026-01-02","2026-01-05","2026-01-06"]
        fields={"code":"2330","name":"測試","market":"上市","theme":"半導體",
          "close":100.,"capitalB":10.,"turnoverB":2.,"ret5":3.,"ret20":5.,
          "ma20Slope":2.,"rvol":1.3,"baselineScore":80.}
        p=pd.DataFrame([{"date":d,**fields} for d in days])
        idx=pd.DataFrame({"date":days,"close":[100,102,105]})
        rows,stats=reconstruct(days,p,"2026-01-02","2026-01-06",idx)
        a,b,c=[rows[d]["stocks"][0] for d in days]
        self.assertEqual(a["gPast10"],0)
        self.assertEqual(b["gPast10"],1)
        self.assertEqual(c["gPast10"],2)
        self.assertEqual(b["signal"],"🚀 G雙突破開始轉強")
        self.assertGreater(b["total"],a["total"])
        self.assertEqual(a["foreignToday"],None)
        self.assertEqual(a["sarText"],"歷史SAR未驗證")
        self.assertEqual(len(stats),3)
    def test_original_day_parity_never_mutates_or_fills(self):
        official={"models":{"G":[{"market":"上市","code":"2330"},{"market":"上櫃","code":"1234"}]}}
        rebuilt={"2026-10-08":{"stocks":[{"market":"上市","code":"2330"},{"market":"上市","code":"1111"}]}}
        m=compare_real_archive(rebuilt,official,"2026-10-08")
        self.assertEqual(m["intersection"],1)
        self.assertEqual(m["missingFromRebuild"],["1234"])
        self.assertFalse(m["identicalOrder"])
    def test_not_claiming_pit_archive(self):
        self.assertIn("RECONSTRUCTION",VERSION)
        self.assertEqual(months_before("2026-10-08"),"2026-08-08")
if __name__=="__main__":unittest.main()
