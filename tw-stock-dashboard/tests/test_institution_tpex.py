import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import institution
from institution import fetch_day,parse_tpex
from pipeline import mask_unverified_institutional_values

def row(code,foreign=1200,trust=-300,dealer=100):
    data=["0"]*24
    data[0]=str(code);data[1]="測試股票"
    data[10]=f"{foreign:,}";data[13]=f"{trust:,}";data[22]=f"{dealer:,}"
    data[23]=f"{foreign+trust+dealer:,}"
    return data

def report(*rows,date="115/10/15"):
    return {"tables":[{"date":date,"data":list(rows)}]}

class TPExFlowTests(unittest.TestCase):
    def test_correct_columns_and_units_are_shares(self):
        m=parse_tpex(report(row("3265"),row("1569",0,0,0)),"2026-10-15")
        self.assertEqual(m["上櫃_3265"],{"foreign":1200,"trust":-300,"dealer":100,"total":1000})
        self.assertEqual(m["上櫃_1569"]["trust"],0)
    def test_wrong_session_never_uses_yesterday(self):
        self.assertFalse(parse_tpex(report(row("3265"),date="115/10/14"),"2026-10-15"))
        self.assertFalse(parse_tpex({"tables":[{"data":[row("3265")]}]},"2026-10-15"))
    def test_corrupt_total_and_non_stocks_are_dropped(self):
        bad=row("3265");bad[23]="999"
        missing=row("4903");missing[10]="--"
        m=parse_tpex(report(bad,missing,row("00679B"),row("0001"),row("1569")),"2026-10-15")
        self.assertEqual(list(m),["上櫃_1569"])
    def test_legacy_twse_only_cache_backfills_tpex_and_preserves_twse(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"2026-10-15.json"
            p.write_text(json.dumps({"上市_2330":{"foreign":0,"trust":0,"dealer":0,"total":0}}),encoding="utf-8")
            fake=Mock();fake.json.return_value=report(*(row(3000+i) for i in range(220)))
            with patch.object(institution,"DIR",Path(tmp)),patch.object(institution.requests,"get",return_value=fake) as req:
                date,m,err=fetch_day("2026-10-15",retries=1)
                self.assertEqual(date,"2026-10-15");self.assertIsNone(err)
                self.assertEqual(m["上市_2330"]["foreign"],0)
                self.assertEqual(m["上櫃_3000"]["foreign"],1200)
                self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["上櫃_3001"]["trust"],-300)
                self.assertEqual(req.call_args.kwargs["params"]["date"],"115/10/15")
                req.reset_mock()
                _,again,err=fetch_day("2026-10-15",retries=1)
                self.assertEqual(again,m);self.assertIsNone(err);req.assert_not_called()
    def test_partial_market_cache_is_refetched_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"2026-10-15.json"
            cached={f"上市_{i}":{"foreign":0,"trust":0} for i in range(2000,2100)}
            cached.update({f"上櫃_{i}":{"foreign":0,"trust":0} for i in range(3000,3220)})
            p.write_text(json.dumps(cached),encoding="utf-8")
            expected=set(cached)|{f"上櫃_{i}" for i in range(3220,3600)}
            fake=Mock();fake.json.return_value=report(*(row(i) for i in range(3000,3220)))
            with patch.object(institution,"DIR",Path(tmp)),patch.object(institution.requests,"get",return_value=fake) as req:
                date,rows,err=fetch_day("2026-10-15",expected_keys=expected,retries=1)
            self.assertIn("TPEx",err);self.assertEqual(req.call_count,1)
            self.assertEqual(json.loads(p.read_text(encoding="utf-8")),cached)
    def test_incomplete_cache_recovers_from_full_official_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"2026-10-15.json"
            cached={f"上市_{i}":{"foreign":0,"trust":0} for i in range(2000,2100)}
            cached.update({f"上櫃_{i}":{"foreign":0,"trust":0} for i in range(3000,3220)})
            p.write_text(json.dumps(cached),encoding="utf-8")
            expected=set(cached)|{f"上櫃_{i}" for i in range(3220,3600)}
            fake=Mock();fake.json.return_value=report(*(row(i) for i in range(3000,3600)))
            with patch.object(institution,"DIR",Path(tmp)),patch.object(institution.requests,"get",return_value=fake):
                _,rows,err=fetch_day("2026-10-15",expected_keys=expected,retries=1)
            self.assertIsNone(err);self.assertEqual(len([k for k in rows if k.startswith("上櫃_")]),600)
            self.assertIn("上櫃_3500",json.loads(p.read_text(encoding="utf-8")))
    def test_nonfinite_official_flow_is_rejected(self):
        nan=row("3265");nan[10]="NaN"
        self.assertNotIn("上櫃_3265",parse_tpex(report(nan),"2026-10-15"))
    def test_failed_tpex_does_not_make_missing_flow_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/"2026-10-15.json";p.write_text(json.dumps({"上市_2330":{"foreign":0,"trust":0}}),encoding="utf-8")
            with patch.object(institution,"DIR",Path(tmp)),patch.object(institution.requests,"get",side_effect=RuntimeError("TPEx blocked")):
                _,m,err=fetch_day("2026-10-15",retries=1)
            self.assertIn("TPEx",err)
            rows={"G":[{"market":"上櫃","code":"3265","foreignToday":0,"trustToday":0},{"market":"上市","code":"2330","foreignToday":0,"trustToday":0}]}
            mask_unverified_institutional_values(rows,m)
            self.assertIsNone(rows["G"][0]["foreignToday"])
            self.assertEqual(rows["G"][1]["foreignToday"],0)

if __name__=="__main__":unittest.main()
