import unittest
from g_persistence import persistence_features,pocket_snapshot,repeat_audit,pocket_segment_stats

def fake_day(rows):
    return {code:{"rank":rank,"score":score} for code,rank,score in rows}

class TestGPersistence(unittest.TestCase):
    def test_no_future_current_day_or_feedback(self):
        days=[fake_day([("A",1,92)]) for _ in range(3)]
        before=persistence_features("A",days,95)
        self.assertEqual(before["past10Top20"],3)
        self.assertEqual(before["past5Top3"],3)
        self.assertEqual(before["priorStreak"],3)
        after=persistence_features("A",days+[fake_day([("A",1,99)])],95)
        self.assertEqual(after["past10Top20"],4)
        self.assertGreater(after["strength"],before["strength"])
        self.assertEqual(len(days),3)
    def test_first_selection_neutral(self):
        prev=[fake_day([("B",1,95)]) for _ in range(6)]
        x=persistence_features("A",prev,95)
        self.assertEqual(x["past10Top20"],0)
        self.assertEqual(x["strength"],0)
        self.assertEqual(x["bonus"],0)
        self.assertEqual(x["priorStreak"],0)
    def test_repeated_no_forced_buy(self):
        p=fake_day([("A",1,95)])
        days=[p]*10
        a=persistence_features("A",days,96)
        self.assertEqual(a["past10Top20"],10)
        self.assertEqual(a["past5Top3"],5)
        self.assertEqual(a["priorStreak"],10)
        self.assertLessEqual(a["bonus"],7)
        self.assertGreater(a["bonus"],5)
    def test_streak_breaks_after_missing_day(self):
        rows=[fake_day([("A",1,92)]),fake_day([("B",1,95)]),fake_day([("A",4,90)])]
        a=persistence_features("A",rows,96)
        self.assertEqual(a["past10Top20"],2)
        self.assertEqual(a["priorStreak"],1)
    def test_lookback_excludes_old_events(self):
        rows=[fake_day([("A",2,91)])]+[fake_day([("B",2,91)])]*10
        self.assertEqual(persistence_features("A",rows,100)["past10Top20"],0)
    def test_snapshot_top20_unique_and_baseline_only(self):
        rows=[{"code":f"{i:04}","baselineScore":100-i,"persistenceScore":140-i} for i in range(23)]
        snap=pocket_snapshot(rows)
        self.assertEqual(len(snap),20)
        self.assertEqual(snap["0000"]["score"],100)
        self.assertNotIn("0020",snap)
    def test_repeated_stock_held_no_duplicate_new_trade(self):
        dates=["2026-01-%02d"%i for i in range(1,18)]
        events=[{"signalDate":dates[i],"code":"A","rank":1,"ret5":2+i,"ret10":4+i,"ret20":7+i} for i in (0,1,2,3,5,10)]
        audit=repeat_audit(events,dates,5)
        self.assertEqual(audit["raw"]["n"],6)
        self.assertEqual(audit["newTrades"]["n"],3)
        self.assertEqual(audit["overlappingSignalsSuppressed"],3)
    def test_segmentation_uses_prior_only(self):
        rows=[{"persistence":{"past10Top20":p},"ret10":r} for p,r in [(0,3),(1,-2),(3,4),(4,6),(10,-1)]]
        out=pocket_segment_stats(rows,10)
        self.assertEqual(out["fresh"]["n"],1)
        self.assertEqual(out["emerging_1_3"]["n"],2)
        self.assertEqual(out["persistent_4plus"]["n"],2)

if __name__=="__main__":unittest.main()
