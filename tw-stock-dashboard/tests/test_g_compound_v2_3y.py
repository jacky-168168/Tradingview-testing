"""Test consolidation intent and no-lookahead, plus V2 chronological selection."""
import unittest
import pandas as pd
from g_compound_early_setup import FAMILIES,asof_features,classify_frame,rank_stock
from research_g_compound_v2_3y import EXPECT_MODELS,candidate_id,train_validate_selection
class EarlySetupTests(unittest.TestCase):
    def _data(self,ending_close=103, ending_volume=2000000):
        days=pd.bdate_range("2026-01-02",periods=80)
        close=[100.]*79+[ending_close]
        volume=[1000000.]*79+[ending_volume]
        df=pd.DataFrame({"date":[d.strftime("%Y-%m-%d") for d in days],
          "open":close,"high":[c*1.01 for c in close],
          "low":[c*.99 for c in close],"close":close,"volume":volume})
        market={day:0 for day in df.date}
        return df,market
    def test_prior_range_and_prior_volume_use_only_earlier_bars(self):
        df,market=self._data()
        q=asof_features(df,market)
        x=q.iloc[-1]
        self.assertAlmostEqual(float(x["vol20Prior"]),1000000)
        self.assertAlmostEqual(float(x["rvol"]),2)
        self.assertAlmostEqual(float(x["prev15High"]),101)
        self.assertGreater(float(x["break15Pct"]),0)
        self.assertTrue(bool(classify_frame(q)["Box15 Breakout"].iloc[-1]))
        self.assertTrue(bool(classify_frame(q)["Box10 Tight Breakout"].iloc[-1]))
    def test_future_price_and_volume_cannot_change_old_signal(self):
        df,market=self._data()
        before=asof_features(df,market)
        flags=classify_frame(before)
        future={"date":"2026-06-01","open":70,"high":72,"low":68,"close":70,"volume":100000000}
        df2=pd.concat([df,pd.DataFrame([future])],ignore_index=True)
        market[future["date"]]=-50
        after=asof_features(df2,market)
        flags2=classify_frame(after)
        d=df.date.iloc[-1]
        a=before[before.date==d].iloc[0];b=after[after.date==d].iloc[0]
        for col in ("rvol","rs20","prev15High","prev20RangePct","break15Pct"):
            self.assertAlmostEqual(float(a[col]),float(b[col]),places=10)
        for name in FAMILIES:
            self.assertEqual(bool(flags[name].iloc[-1]),bool(flags2[name].iloc[-2]))
    def test_already_extended_or_no_volume_is_filtered(self):
        df,market=self._data(ending_close=120,ending_volume=1000000)
        q=asof_features(df,market)
        self.assertFalse(any(bool(v.iloc[-1]) for v in classify_frame(q).values()))
    def test_prebreak_near_upper_range_needs_volume_confirmation(self):
        df,market=self._data(ending_close=101.2,ending_volume=2000000)
        a=asof_features(df,market)
        self.assertTrue(bool(classify_frame(a)["Box20 Prebreak"].iloc[-1]))
        df.loc[df.index[-1],"volume"]=1000000
        b=asof_features(df,market)
        self.assertFalse(bool(classify_frame(b)["Box20 Prebreak"].iloc[-1]))
    def test_score_is_finite_and_historical_only(self):
        row={"rvol":2.,"rs20":4.,"boxRangePct":6.,"breakoutPct":1.1,"dayPct":3.,"turnoverB":3.}
        for f in FAMILIES:
            self.assertGreaterEqual(rank_stock(row,f),0)
            self.assertLessEqual(rank_stock(row,f),100)
    def test_chronological_choice_does_not_look_at_2026(self):
        self.assertEqual(EXPECT_MODELS,160)
        base={"capitalEnd":650000,"netReturnPct":30,"maxDDPct":-20,"closedTrades":24}
        z={"id":candidate_id("Box15 Breakout","SCORE60",.05,.08,5,200000.),
           "params":{"selector":"Box15 Breakout"},
           "periods":{"train":base.copy(),"validation":base.copy(),
              "audit2026":dict(base,netReturnPct=-99),
              "authorWindow2026":dict(base,netReturnPct=-99)}}
        pick=train_validate_selection([z])
        self.assertEqual(pick["id"],z["id"])
        z["periods"]["audit2026"]["netReturnPct"]=100000
        z["periods"]["authorWindow2026"]["netReturnPct"]=100000
        self.assertEqual(train_validate_selection([z])["id"],z["id"])
        z["periods"]["validation"]["closedTrades"]=4
        self.assertEqual(train_validate_selection([z])["status"],"no_setup_passed_predefined_test")
if __name__=="__main__":unittest.main()
