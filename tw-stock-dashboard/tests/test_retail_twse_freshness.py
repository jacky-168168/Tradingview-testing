import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import retail_twse_fallback as twse


def official(day="1151103", count=550):
    fields = ["股票代號", "股票名稱", "融資買進", "融資賣出", "融資現金償還", "前日餘額", "今日餘額", "融券今日餘額"]
    rows = [[f"{1000+i:04d}", "測試", "0", "0", "0", "100", "95", "9"] for i in range(count)]
    return {"stat": "OK", "date": day, "tables": [{"fields": fields, "data": rows}]}


def quotes(date="1151103", count=550):
    return [{"Date": date, "Code": f"{1000+i:04d}", "ClosingPrice": "10"} for i in range(count)]


class RetailTwseDateIntegrity(unittest.TestCase):
    def test_date_parser_reads_roc_compact_date(self):
        self.assertEqual(twse.date_of("1151103"), "2026-11-03")

    @patch.object(twse, "get")
    def test_explicit_same_day_stock_balances_are_accepted(self, getter):
        getter.return_value = official()
        rows = twse.dated_balances("2026-11-03")
        self.assertEqual(len(rows), 550)
        self.assertEqual(rows["1000"], 95)
        self.assertEqual(getter.call_args.args[0], twse.URLS["datedMargin"])
        self.assertEqual(getter.call_args.args[1]["date"], "20261103")

    @patch.object(twse, "get")
    def test_yesterday_stock_balances_rejected_even_if_loan_is_today(self, getter):
        getter.return_value = official("1151102")
        with self.assertRaisesRegex(RuntimeError, "日期不一致"):
            twse.dated_balances("2026-11-03")

    @patch.object(twse, "get")
    def test_insufficient_stock_balances_rejected(self, getter):
        getter.return_value = official(count=10)
        with self.assertRaisesRegex(RuntimeError, "樣本不足"):
            twse.dated_balances("2026-11-03")

    def test_same_day_prices_accepted(self):
        self.assertEqual(len(twse.verified_quotes(quotes(), "2026-11-03")), 550)

    def test_old_stock_quotes_cannot_mix_with_new_loan(self):
        with self.assertRaisesRegex(RuntimeError, "收盤日不一致"):
            twse.verified_quotes(quotes("1151102"), "2026-11-03")

    def test_mixed_quote_dates_cannot_pass(self):
        v = quotes()
        v[0]["Date"] = "1151102"
        with self.assertRaisesRegex(RuntimeError, "收盤日不一致"):
            twse.verified_quotes(v, "2026-11-03")

    def test_quote_without_verifiable_date_rejected(self):
        v = quotes()
        v[0].pop("Date")
        with self.assertRaisesRegex(RuntimeError, "收盤日不一致"):
            twse.verified_quotes(v, "2026-11-03")

    @patch.object(twse, "get")
    def test_dated_report_missing_date_is_rejected(self, getter):
        report = official()
        report.pop("date")
        getter.return_value = report
        with self.assertRaisesRegex(RuntimeError, "日期不一致"):
            twse.dated_balances("2026-11-03")


if __name__ == "__main__":
    unittest.main()
