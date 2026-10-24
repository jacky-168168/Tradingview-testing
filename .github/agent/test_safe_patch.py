import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent))
from safe_patch import allowed,check
from collect_failure import scrub
class PatchTests(unittest.TestCase):
 def test_allowed_news_repair(self):
  self.assertTrue(check(["tw-stock-dashboard/src/market_major_events.py","tw-stock-dashboard/tests/test_market_major_events.py"]))
 def test_protect_trading_logic_and_workflows(self):
  for p in ["tw-stock-dashboard/src/g_intraday.py","tw-stock-dashboard/src/g_live.py",
     "tw-stock-dashboard/docs/data/latest.json",".github/workflows/tw-stock-dashboard.yml",
     "AGENTS.md","../../escape"]:
   self.assertFalse(allowed(p))
   with self.assertRaises(ValueError):check([p])
 def test_no_deleted_or_empty_patch(self):
  with self.assertRaises(ValueError):check([])
 def test_scrub_bearer_token(self):
  self.assertNotIn("secretvalue",scrub("Authorization: Bearer secretvalue"))
if __name__=="__main__":unittest.main()
