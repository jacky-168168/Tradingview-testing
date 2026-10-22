import unittest
from datetime import datetime, timedelta, timezone
from update_us_fear_greed import (
    CUTOVER_DATE, VERSION, to_archive, valid_score, wantgoo_series,
)


class TestUSFearGreed(unittest.TestCase):
    def fixtures(self):
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        history = [(start + timedelta(days=i)).date().isoformat() for i in range(255)]
        spx_history = [
            [(start - timedelta(days=400 - i)).date().isoformat(), 4200 + i, 44, 1000]
            for i in range(400)
        ]
        spx_history.extend([[d, 5000 + i, 45, 1000] for i, d in enumerate(history)])
        recent = ["2026-10-15", "2026-10-16", "2026-10-19", "2026-10-20", "2026-10-21"]
        spx_history.extend([[d, p, 45, 1000] for d, p in zip(
            recent, [7744.06, 7659.44, 7690.73, 7712.57, 7751.95]
        )])
        spx = {"columns": ["date", "spx", "dixPct", "gex"], "rows": spx_history}
        legacy = {"version": "US_CNN_FEAR_GREED_SPX_V1",
                  "columns": ["date", "fearGreed", "spx"],
                  "rows": [[d, i % 100, 5000 + i] for i, d in enumerate(history)]}
        # The page has additional macroeconomic figures, which must not be parsed as sentiment.
        html = """<html><body><h2>恐懼與貪婪指數</h2>
            <div>當日 2026/10/21</div><div>恐懼 29</div>
            <table><tr><td>2026/10/21</td><td>恐懼 29</td><td>7,751.95</td></tr>
            <tr><td>2026/10/20</td><td>恐懼 27</td><td>7,712.57</td></tr>
            <tr><td>2026/10/19</td><td>極度恐懼 23</td><td>7,690.73</td></tr>
            <tr><td>2026/10/16</td><td>極度恐懼 18</td><td>7,659.44</td></tr>
            <tr><td>2026/10/15</td><td>恐懼 32</td><td>7,744.06</td></tr></table>
            <script>2026/10/22 恐懼 99 7,888.00</script></body></html>"""
        return html, spx, legacy

    def test_date_alignment_with_legacy_provenance(self):
        html, spx, legacy = self.fixtures()
        observed = wantgoo_series(html)
        result = to_archive(observed, spx, legacy)
        self.assertEqual(result["version"], VERSION)
        self.assertEqual(result["source"], "https://www.wantgoo.com/global/macroeconomics/fearandgreed")
        self.assertEqual(result["columns"], ["date", "fearGreed", "spx"])
        self.assertEqual(result["asOf"], "2026-10-21")
        self.assertEqual(result["rows"][-1], ["2026-10-21", 29.0, 7751.95])
        self.assertEqual(result["legacyCount"], 255)
        self.assertEqual(result["wantgooCount"], 5)
        self.assertLess(result["legacyUntil"], CUTOVER_DATE)

    def test_only_public_dated_rows(self):
        html, _, _ = self.fixtures()
        rows = wantgoo_series(html)
        self.assertEqual(len(rows), 5)
        self.assertNotIn("2026-10-22", rows)
        self.assertEqual(rows["2026-10-16"], (18, 7659.44))
        with self.assertRaisesRegex(ValueError, "unavailable"):
            wantgoo_series("<html><body>恐懼與貪婪指數 29</body></html>")

    def test_no_fabricated_values_when_incomplete(self):
        html, spx, legacy = self.fixtures()
        observed = wantgoo_series(html)
        observed.pop("2026-10-20")
        result = to_archive(observed, spx, legacy)
        self.assertNotIn("2026-10-20", [r[0] for r in result["rows"]])
        self.assertIsNone(valid_score("NaN"))
        self.assertIsNone(valid_score(150))
        self.assertIsNone(valid_score(True))

    def test_reject_stale_or_mismatched_market_close(self):
        html, spx, legacy = self.fixtures()
        observed = wantgoo_series(html)
        spx["rows"][-1][0] = "2026-10-22"
        with self.assertRaisesRegex(ValueError, "DATE_NOT_ALIGNED"):
            to_archive(observed, spx, legacy)
        html, spx, legacy = self.fixtures()
        observed = wantgoo_series(html)
        spx["rows"][-1][1] = 8000
        with self.assertRaisesRegex(ValueError, "differs materially"):
            to_archive(observed, spx, legacy)

    def test_reject_schema_and_no_legacy_fabrication(self):
        html, spx, legacy = self.fixtures()
        observed = wantgoo_series(html)
        spx["columns"] = ["date", "spx", "gex", "dixPct"]
        with self.assertRaisesRegex(ValueError, "schema"):
            to_archive(observed, spx, legacy)
        html, spx, legacy = self.fixtures()
        legacy["rows"] = []
        with self.assertRaisesRegex(ValueError, "Legacy"):
            to_archive(wantgoo_series(html), spx, legacy)

    def test_append_only_verified_wantgoo_observations(self):
        html, spx, old = self.fixtures()
        first = to_archive(wantgoo_series(html), spx, old)
        # Next website table might omit an older date: preserve only scores already
        # sourced from WantGoo, not previously archived CNN post-cutover.
        new = dict(first)
        dates = {d: v for d, v in wantgoo_series(html).items() if d != "2026-10-15"}
        second = to_archive(dates, spx, new)
        self.assertEqual(second["wantgooCount"], 5)
        self.assertEqual(second["rows"], first["rows"])


if __name__ == "__main__":
    unittest.main()
