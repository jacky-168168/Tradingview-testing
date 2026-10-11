"""Official ROE/PB ingestion: future leak, accounting denominator and source guards."""
import unittest
from datetime import date,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import json
from stock_quality import QualityIndex,enrich_quality

def pbs():
    out=[];d=date(2026,3,1)
    while d<=date(2026,10,8):
        if d.weekday()<5:out.append({"market":"sii","code":"2330","date":d.isoformat(),
            "pb":4+len(out)/100,"source":"TWSE_BWIBBU_d"})
        d+=timedelta(days=1)
    return out

def roe():
    return {"market":"sii","code":"2330","year":2026,"quarter":2,
        "availableFrom":"2026-08-22","netIncomeTTM":24,"equityNow":110,
        "equityYearAgo":90,"source":"MOPS_CONSOLIDATED_QUARTER",
        "equityScope":"consolidated_total","netIncomeScope":"consolidated_total"}

class QualityTests(unittest.TestCase):
    def test_valid_quality_and_asof(self):
        idx=QualityIndex(pbs(),[roe()])
        z=idx.at("sii","2330","2026-10-08")
        self.assertEqual(z["roePct"],24.0)
        self.assertGreater(z["pbHistorySamples"],120)
        self.assertTrue(0<=z["pbHistoryPercentile3Y"]<=100)
        self.assertEqual(z["pbAsOf"],"2026-10-08")
        a=idx.at("sii","2330","2026-08-21")
        self.assertIsNone(a["roePct"])
        self.assertLessEqual(a["pbAsOf"],"2026-08-21")
    def test_no_future_or_stale_pb(self):
        idx=QualityIndex(pbs(),[roe()])
        self.assertIsNone(idx.at("sii","2330","2026-10-20")["pbRatio"])
        self.assertIsNone(idx.at("sii","2330","2026-01-20")["pbRatio"])
        self.assertIsNone(idx.at("sii","2330","2027-10-20")["roePct"])
    def test_bad_accounting_scope_and_future_quarter(self):
        row=roe();row["equityScope"]="parent_only"
        with self.assertRaises(ValueError):QualityIndex([], [row])
        row=roe();row["availableFrom"]="2026-07-01"
        with self.assertRaises(ValueError):QualityIndex([], [row])
    def test_no_roe_fabrication_or_duplicate_override(self):
        with self.assertRaises(ValueError):QualityIndex([], [{**roe(),"equityNow":0}])
        with self.assertRaises(ValueError):QualityIndex([*pbs(),{**pbs()[-1],"pb":99}],[])
    def test_no_unofficial_source(self):
        with self.assertRaises(ValueError):QualityIndex([{"market":"otc","code":"3105","date":"2026-10-08","pb":2,"source":"TWSE_BWIBBU_d"}],[])
    def test_quality_snapshot_missing_is_null(self):
        with TemporaryDirectory() as directory:
            payload={"dataDate":"2026-10-08","stocks":[{"market":"上市","code":"2330","roePct":777}],"coverage":{}}
            out=enrich_quality(payload,directory)
            self.assertIsNone(out["stocks"][0]["roePct"])
            self.assertIsNone(out["stocks"][0]["pbRatio"])
            self.assertEqual(out["coverage"]["qualityArchiveStatus"],"partial")
    def test_partial_archive_pb_only(self):
        with TemporaryDirectory() as directory:
            dest=Path(directory)/"research"/"quality";dest.mkdir(parents=True)
            (dest/"pb_daily.json").write_text(json.dumps(pbs()),encoding="utf8")
            payload={"dataDate":"2026-10-08","stocks":[{"market":"上市","code":"2330"}],"coverage":{}}
            out=enrich_quality(payload,directory)
            self.assertEqual(out["coverage"]["pbAvailable"],1)
            self.assertEqual(out["coverage"]["roeAvailable"],0)

if __name__=="__main__":unittest.main()
