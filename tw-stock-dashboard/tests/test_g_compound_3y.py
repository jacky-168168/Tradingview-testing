"""Regression coverage of G Compound cash execution and causality."""
import unittest
from research_g_compound_3y import study_one,market_allows,PRINCIPAL
class CompoundTests(unittest.TestCase):
    def _bars(self,rows):
        # rows: date, open, high, low, close; adj=raw, volume=100k
        return {d:(o,h,l,c,o,h,l,c,100000.) for d,o,h,l,c in rows}
    def _sample(self,dates,raw,stock="1101",tp=.05,sl=.05,h=5,cap=500000.,g="SCORE60"):
        picks={dates[0]:[{"sym":stock+".TW","code":stock,"name":"Demo","close":100.}]}
        market={d:{"score":75,"topState":"⚪ Inactive"} for d in dates}
        prices={stock+".TW":self._bars(raw)}
        return study_one(dates,picks,prices,market,g,tp,sl,h,cap,logs=True)
    def test_gap_above_three_pct_cancels_buy(self):
        dates=["2026-01-05","2026-01-06"]
        rows=[(dates[1],104.,106.,99.,100.)]
        stats,_,trades=self._sample(dates,rows)
        self.assertEqual(stats["filledBuys"],0)
        self.assertEqual(stats["blocked"]["open_over_plus3pct"],1)
        self.assertEqual(stats["capitalEnd"],PRINCIPAL)
    def test_same_bar_stop_and_target_uses_stop_first(self):
        dates=["2026-01-05","2026-01-06"]
        rows=[(dates[1],100.,111.,90.,100.)]
        stats,_,trades=self._sample(dates,rows)
        self.assertEqual(stats["closedTrades"],1)
        self.assertEqual(stats["wins"],0)
        self.assertEqual(trades[0]["exitReason"],"intraday_stop")
        self.assertLess(stats["capitalEnd"],PRINCIPAL)
    def test_target_immediate_and_compound_next_entry(self):
        dates=["2026-01-05","2026-01-06","2026-01-07"]
        bars={"1101.TW":self._bars([(dates[1],100.,108.,100.,106.)]),
              "1102.TW":self._bars([(dates[2],100.,108.,100.,106.)])}
        picks={dates[0]:[{"sym":"1101.TW","code":"1101","name":"A","close":100.}],
               dates[1]:[{"sym":"1102.TW","code":"1102","name":"B","close":100.}]}
        risk={d:{"score":80} for d in dates}
        r,_,trades=study_one(dates,picks,bars,risk,"SCORE60",.05,.08,5,500000.,logs=True)
        self.assertEqual(r["filledBuys"],2)
        self.assertEqual(r["closedTrades"],2)
        self.assertEqual(r["wins"],2)
        self.assertGreater(trades[1]["invested"],trades[0]["invested"])
        self.assertGreater(r["capitalEnd"],PRINCIPAL)
    def test_time_exit_precedes_next_day_high(self):
        dates=["2026-01-05","2026-01-06","2026-01-07","2026-01-08"]
        rows=[(dates[1],100.,104.,96.,100.),
              (dates[2],100.,104.,96.,100.),
              (dates[3],100.,120.,99.,110.)]
        r,_,trades=self._sample(dates,rows,tp=.05,sl=None,h=2)
        self.assertEqual(r["closedTrades"],1)
        self.assertEqual(trades[0]["exitReason"],"time_next_open")
        self.assertEqual(trades[0]["sellDate"],dates[3])
        self.assertAlmostEqual(trades[0]["sellAdjusted"],100.)
    def test_many_tickets_never_reuse_invested_cash(self):
        dates=["2026-01-05","2026-01-06","2026-01-07","2026-01-08"]
        picks={d:[{"sym":f"{n}.TW","code":str(n),"name":"X","close":100.}]
               for d,n in zip(dates,(1111,2222,3333,4444))}
        bars={f"{n}.TW":self._bars([(day,100.,101.,99.,100.)])
              for day,n in zip(dates[1:],(1111,2222,3333))}
        market={d:{"score":80} for d in dates}
        r,_,_=study_one(dates,picks,bars,market,"SCORE60",.10,None,10,200000.)
        self.assertEqual(r["filledBuys"],3)
        self.assertEqual(r["closedTrades"],0)
        self.assertEqual(r["openAtEnd"],3)
        self.assertGreaterEqual(r["cashAtEnd"],0)
        self.assertLess(r["cashAtEnd"],110000.)
    def test_risk_permission_only_asof_close(self):
        self.assertFalse(market_allows("SCORE60",{"score":49}))
        self.assertTrue(market_allows("SCORE60",{"score":60}))
        self.assertFalse(market_allows("SCORE60_NOT_STRONG_TOP",{"score":90,"topState":"🔴 Strong Top Reversal"}))
if __name__=="__main__":unittest.main()
