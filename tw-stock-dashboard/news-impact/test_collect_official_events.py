"""Official-archive ingestion tests with representative real-source URL shapes."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_official_events import (
    BLS_ROOT, FED_CALENDAR, collect, merge_events, parse_bls_index, parse_fomc_statements,
)


NOW = datetime(2026, 11, 9, 2, 0, tzinfo=timezone.utc)
BLS_HTML = """
<html><body>
<a href="/news.release/archives/cpi_10142026.pdf">PDF</a>
<a href="/news.release/archives/cpi_10142026.htm">September 2026 Consumer Price Index</a>
<a href="/news.release/archives/cpi_02132024.htm">January 2024 Consumer Price Index</a>
<a href="/news.release/archives/cpi_12102027.htm">Future meeting - not yet released</a>
<a href="/news.release/archives/ppi_02132024.htm">Not CPI</a>
<a href="https://attack.example/news.release/archives/cpi_10142026.htm">Foreign</a>
<a href="https://www.bls.gov/bls/news-release/cpi.htm#2025">Unrelated year</a>
</body></html>
"""
FED_HTML = """
<html><body>
<a href="https://www.federalreserve.gov/newsevents/pressreleases/monetary20260128a.htm">HTML</a>
<a href="/newsevents/pressreleases/monetary20190130a.htm">Statement</a>
<a href="/newsevents/pressreleases/monetary20271209a.htm">Future statement</a>
<a href="/newsevents/pressreleases/monetary20190130b.htm">Implementation note</a>
<a href="/newsevents/pressreleases/monetary20260128a.htm">HTML</a>
<a href="https://evil.example/newsevents/pressreleases/monetary20190130a.htm">Statement</a>
</body></html>
"""


class OfficialCollectorTests(unittest.TestCase):
    def test_bls_exact_release_date_from_filename_and_pdf_dedup(self):
        rows = parse_bls_index(BLS_HTML, "cpi", NOW)
        self.assertEqual([x["date"] for x in rows], ["2024-02-13", "2026-10-14"])
        self.assertEqual(rows[-1]["sourceUrl"], "https://www.bls.gov/news.release/archives/cpi_10142026.htm")
        self.assertEqual(rows[0]["localTime"], "08:30")
        self.assertFalse(rows[0]["directionKnown"])

    def test_fomc_policy_statement_dates_no_implementation_or_future(self):
        rows = parse_fomc_statements(FED_HTML, NOW)
        self.assertEqual([x["date"] for x in rows], ["2019-01-30", "2026-01-28"])
        self.assertEqual(rows[0]["category"], "FOMC")
        self.assertIsNone(rows[0]["localTime"])

    def test_curated_fomc_rate_direction_preserved_without_duplicate(self):
        curated = [{
            "id": "fomc-2019-01-30", "date": "2019-01-30", "category": "FOMC",
            "subtype": "升息", "bps": 25, "effectiveDate": "2019-01-31",
            "sourceUrl": "https://www.federalreserve.gov/monetarypolicy/openmarket.htm",
            "source": "Federal Reserve", "directionKnown": True
        }]
        merged = merge_events(curated, [], parse_fomc_statements(FED_HTML, NOW))
        self.assertEqual(len(merged), 2)
        rate = [e for e in merged if e["date"] == "2019-01-30"][0]
        self.assertEqual(rate["bps"], 25)
        self.assertEqual(rate["subtype"], "升息")
        self.assertEqual(rate["sourceUrl"], "https://www.federalreserve.gov/newsevents/pressreleases/monetary20190130a.htm")

    def test_previous_verified_records_preserved_after_outage(self):
        curated = {"schema": 1, "events": [{
            "id": "fomc-2024-09-18", "date": "2024-09-18", "category": "FOMC",
            "subtype": "降息", "sourceUrl": "https://www.federalreserve.gov/monetarypolicy/openmarket.htm",
            "source": "Fed", "title": "Cut", "timezone": "America/New_York"
        }]}
        previous = {"schema": 1, "events": [{
            "id": "bls-cpi-2024-02-13", "date": "2024-02-13", "category": "CPI",
            "subtype": "官方經濟數據公布", "sourceUrl": "https://www.bls.gov/news.release/archives/cpi_02132024.htm",
            "source": "BLS", "title": "CPI", "timezone": "America/New_York"
        }]}
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            original, output = base / "curated.json", base / "expanded.json"
            original.write_text(json.dumps(curated), encoding="utf8")
            output.write_text(json.dumps(previous), encoding="utf8")

            def unavailable(_url):
                raise OSError("simulated upstream block")

            d = collect(original, output, fetcher=unavailable, now=NOW)
            self.assertEqual(d["status"], "sources_unavailable")
            self.assertEqual(d["count"], 2)
            self.assertIn("CPI", d["countsByCategory"])
            self.assertGreater(len(d["sourceErrors"]), 7)

    def test_no_fake_generated_periodic_dates(self):
        rows = parse_bls_index("<html><p>December 2025 CPI</p></html>", "cpi", NOW)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
