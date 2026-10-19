"""Offline tests for Cboe daily-price CSV parsing (no synthetic quotes are published)."""
import unittest
from datetime import datetime, timedelta, timezone
from src.us_vix import parse_csv

class VixCsvParsingTests(unittest.TestCase):
    def test_standard_csv(self):
        today = datetime.now(timezone.utc).date()
        lines = ["DATE,OPEN,HIGH,LOW,CLOSE"]
        for i in range(50, -1, -1):
            day = today - timedelta(days=i)
            lines.append(f"{day:%m/%d/%Y},12,25,10,{18+i/100:.2f}")
        rows = parse_csv(("\n".join(lines)+"\n").encode())
        self.assertEqual(len(rows), 51)
        self.assertEqual(rows[-1][0], today.isoformat())
        self.assertGreater(rows[-1][1], 0)

    def test_reject_stale(self):
        today = datetime.now(timezone.utc).date()
        lines = ["DATE,CLOSE"] + [f"{today-timedelta(days=i+90):%m/%d/%Y},25" for i in range(60)]
        with self.assertRaises(ValueError):
            parse_csv("\n".join(lines).encode())

    def test_reject_missing_close_column(self):
        csv_data = "DATE,OPEN\n" + "\n".join("01/01/2026,20" for _ in range(35))
        with self.assertRaises(ValueError):
            parse_csv(csv_data.encode())

if __name__ == "__main__":
    unittest.main()
