import unittest
from g_lifecycle import bucket,lifecycle_audit

def fixtures(n=26):
    dates=[f"2026-02-{i+1:02d}" for i in range(n)]
    # Only A persists day 2 onwards; B never reaches a sustained 7/10 state.
    pockets=[]
    for i in range(n):
        day={}
        if i>=1:day["A"]={"rank":2,"score":90}
        if i in (1,2,4,7,10,13):day["B"]={"rank":5,"score":80}
        pockets.append(day)
    def t(i,code,p,r=10):
        return {"signalDate":dates[i],"code":code,"rank":1,"persistence":{"past10Top20":p},"ret10":r,"ret5":r/2}
    return dates,pockets,t

class GStageTests(unittest.TestCase):
    def test_frequency_buckets_are_entry_time_labels(self):
        self.assertEqual([bucket(i) for i in (0,1,3,4,6,7,9,10)],
          ["fresh","repeat_1_3","repeat_1_3","repeat_4_6","repeat_4_6","repeat_7_9","repeat_7_9","repeat_10_plus"])
        with self.assertRaises(ValueError):bucket(-1)
    def test_forward_stage_comes_from_original_top20_not_later_top3(self):
        dates,pockets,t=fixtures()
        x=lifecycle_audit([t(2,"A",1,12)],dates,pockets,10)
        self.assertEqual(x["newTrades"],1)
        self.assertEqual(x["byEntryBucket"]["repeat_1_3"]["n"],1)
        self.assertEqual(x["byEntryBucket"]["repeat_1_3"]["reach7"],1)
        self.assertEqual(x["byEntryBucket"]["repeat_1_3"]["reach10"],1)
        self.assertEqual(x["entries"][0]["firstReach10"],10)
        self.assertEqual(x["entries"][0]["firstReach7"],6)
        self.assertEqual(x["entries"][0]["entryBucket"],"repeat_1_3")
    def test_holding_same_stock_disallows_reopening_and_b_weak_signal_does_not_progress(self):
        dates,pockets,t=fixtures()
        rows=[t(2,"A",1,10),t(4,"A",3,20),t(2,"B",1,-5)]
        x=lifecycle_audit(rows,dates,pockets,10)
        self.assertEqual(x["newTrades"],2)
        self.assertEqual(x["suppressedOverlappingSignals"],1)
        self.assertEqual(x["earlyEntryOutcomes"]["reached7"]["n"],1)
        self.assertEqual(x["earlyEntryOutcomes"]["notObservedReach7"]["n"],1)
    def test_near_end_horizon_is_right_censored_not_counted_as_failed(self):
        dates,pockets,t=fixtures()
        x=lifecycle_audit([t(18,"A",10)],dates,pockets,10)
        self.assertEqual(x["censoredNearEnd"],1)
        self.assertEqual(x["newTrades"],0)
    def test_no_lookahead_beyond_requested_horizon(self):
        dates,pockets,t=fixtures()
        first=lifecycle_audit([t(2,"A",1)],dates,pockets,5)
        copied=[dict(x) for x in pockets]
        for k in range(8,len(copied)):copied[k].clear()
        second=lifecycle_audit([t(2,"A",1)],dates,copied,5)
        self.assertEqual(first["entries"],second["entries"])
    def test_input_lifecycle_requires_full_daily_snapshots(self):
        dates,pockets,t=fixtures()
        with self.assertRaises(ValueError):lifecycle_audit([t(2,"A",1)],dates,pockets[:-1],10)
        with self.assertRaises(ValueError):lifecycle_audit([t(2,"A",1)],dates[::-1],pockets,10)
    def test_actual_recorded_prior_count_must_match_source_history(self):
        dates,pockets,t=fixtures()
        with self.assertRaisesRegex(ValueError,"cohort mismatch"):
            lifecycle_audit([t(2,"A",7)],dates,pockets,10)
    def test_tracked_future_does_not_reassign_early_entry_cohort(self):
        dates,pockets,t=fixtures()
        x=lifecycle_audit([t(2,"A",1)],dates,pockets,10)
        self.assertEqual(x["byEntryBucket"]["repeat_1_3"]["n"],1)
        self.assertEqual(x["byEntryBucket"]["repeat_7_9"]["n"],0)

if __name__=="__main__":unittest.main()
