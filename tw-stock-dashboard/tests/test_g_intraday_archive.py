"""Regression checks: full G scans are preserved and failed runs never enter history."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from g_intraday_archive import archive_intraday_payload

class GIntradayArchiveTests(unittest.TestCase):
    def payload(self, stamp, price):
        return {"asOfDate":stamp[:10],"publishedAt":stamp,"quality":"intraday-provisional-allmarket",
                "coverage":{"valid":1700},"rows":[{"code":"3535","currentPrice":price}]}
    def test_multiple_rounds_remain_immutable_and_sorted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"g_intraday"/"archive"
            first=self.payload("2026-10-16T09:19:06+08:00",90)
            second=self.payload("2026-10-16T09:45:04+08:00",99)
            p1=archive_intraday_payload(temp,first)
            p2=archive_intraday_payload(temp,second)
            self.assertNotEqual(p1,p2)
            self.assertEqual(json.loads(p1.read_text())["rows"][0]["currentPrice"],90)
            self.assertEqual(json.loads(p2.read_text())["rows"][0]["currentPrice"],99)
            manifest=json.loads((root/"2026-10-16"/"index.json").read_text())
            self.assertEqual([x["publishedAt"] for x in manifest["snapshots"]],[first["publishedAt"],second["publishedAt"]])
            self.assertEqual(json.loads((root/"index.json").read_text())["dates"],["2026-10-16"])
    def test_saves_new_day_without_discarding_prior_day(self):
        with tempfile.TemporaryDirectory() as temp:
            archive_intraday_payload(temp,self.payload("2026-10-16T13:19:06+08:00",103.5))
            archive_intraday_payload(temp,self.payload("2026-10-19T09:31:00+08:00",106))
            root=Path(temp)/"g_intraday"/"archive"
            self.assertTrue((root/"2026-10-16"/"131906.json").exists())
            self.assertEqual(json.loads((root/"index.json").read_text())["dates"],["2026-10-16","2026-10-19"])
    def test_same_second_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            p1=archive_intraday_payload(temp,self.payload("2026-10-16T10:01:00+08:00",90))
            p2=archive_intraday_payload(temp,self.payload("2026-10-16T10:01:00+08:00",91))
            self.assertEqual(p1.name,"100100.json")
            self.assertEqual(p2.name,"100100-2.json")
            self.assertEqual(json.loads(p1.read_text())["rows"][0]["currentPrice"],90)
    def test_invalid_run_or_date_cannot_be_archived(self):
        with tempfile.TemporaryDirectory() as temp:
            bad=self.payload("2026-10-16T10:00:00+08:00",90)
            bad["quality"]="partial"
            with self.assertRaises(ValueError):archive_intraday_payload(temp,bad)
            bad["quality"]="intraday-provisional-allmarket"
            bad["asOfDate"]="2026-10-15"
            with self.assertRaises(ValueError):archive_intraday_payload(temp,bad)
            self.assertFalse((Path(temp)/"g_intraday"/"archive").exists())
if __name__=="__main__":unittest.main()
