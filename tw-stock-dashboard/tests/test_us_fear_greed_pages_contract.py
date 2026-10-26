"""Permanent regression: Pages deployment must accept independently dated Fear/SPX V2."""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
class TestFearGreedPagesContract(unittest.TestCase):
    def test_pages_live_validator_supports_v2_without_fake_values(self):
        workflow=(ROOT/".github/workflows/tw-stock-pages.yml").read_text(encoding="utf-8")
        self.assertIn("US_CNN_FEAR_GREED_SPX_V2",workflow)
        self.assertIn("history['asOf']==max(history['cnnHistoricalLast'],history['spxLast'])",workflow)
        self.assertIn("r[1] is not None or r[2] is not None",workflow)
        self.assertIn("r[1] is None or",workflow)
        self.assertIn("r[2] is None or",workflow)
        self.assertNotIn("assert history['version']=='US_CNN_FEAR_GREED_SPX_V1'",workflow)
if __name__=="__main__":
    unittest.main()
