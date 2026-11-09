"""No-network invariants for author breakout research."""
from __future__ import annotations
import unittest
import pandas as pd
from research_author_breakout import simulate_one,tick,ceil_tick,candidates,MODELS
class AuthorBreakoutTests(unittest.TestCase):
 def bars(self,records):
  return pd.DataFrame([{'date':f'2026-10-{i+1:02d}','open':op,'high':high,'low':low,'close':close}
          for i,(op,high,low,close) in enumerate(records)])
 def test_tw_tick(self):
  self.assertEqual(tick(151),.5)
  self.assertEqual(ceil_tick(151.1),151.5)
  self.assertEqual(tick(6490),5.)
 def test_first_entry_day_stop_priority(self):
  x=self.bars([(140,145,135,140),(145,155,138,152),(153,160,151,158)])
  r=simulate_one(x,0,151,11,1,(2,5),15)
  self.assertEqual(r['status'],'stopped')
  self.assertEqual(r['barsHeld'],1)
  self.assertLess(r['netR'],-.95)
 def test_first_target_and_next_day_breakeven(self):
  x=self.bars([(100,102,98,100),(102,104,101,104),(105,112,104,112),(111,112,102,103)])
  r=simulate_one(x,0,103,3,1,(2,5),15)
  self.assertEqual(r['status'],'stopped')
  self.assertTrue(any(p['reason']=='target' for p in r['legs']))
  self.assertTrue(any(p['reason']=='stop' for p in r['legs']))
 def test_skip_excessive_entry_gap(self):
  x=self.bars([(100,102,98,100),(110,112,109,110),(113,115,110,114),(116,118,116,118)])
  self.assertIsNone(simulate_one(x,0,103,3,1,(2,5),15))
 def test_no_same_day_trade_from_signal(self):
  # D bar pierced trigger; next bar does not. No fill is possible after D close.
  x=self.bars([(100,110,90,100),(101,102,100,101)])
  self.assertIsNone(simulate_one(x,0,108,5,1,(2,5),15))
 def test_fixed_configs(self):
  self.assertEqual(len(MODELS),6)
  self.assertEqual(MODELS['CORE_1ATR_2R5R']['tp'],(2.,5.))
if __name__=='__main__':unittest.main()
