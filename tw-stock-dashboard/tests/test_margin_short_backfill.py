import importlib.util, pathlib, unittest
path=pathlib.Path(__file__).resolve().parents[1]/"scripts/backfill_margin_short.py"
spec=importlib.util.spec_from_file_location("credit",path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class OfficialCreditParsing(unittest.TestCase):
 def fixture(self):
  return {"stat":"OK","date":"20260911","creditList":[
   ["融資(交易單位)","314,089","278,616","8,333","9,102,904","9,130,044"],
   ["融券(交易單位)","24,586","25,528","463","197,447","197,926"],
   ["融資金額(仟元)","20,640,692","23,666,861","1,000,338","591,897,687","587,871,180"]]}
 def test_official_values_match_user_screenshot(self):
  x=mod.parse_payload(self.fixture(),"2026-09-11")
  self.assertAlmostEqual(x["margin_balance_100m_twd"],5878.7118,places=4)
  self.assertAlmostEqual(x["margin_delta_100m_twd"],-40.26507,places=4)
  self.assertEqual(x["short_balance_lots"],197926)
  self.assertAlmostEqual(x["short_margin_ratio_pct"],2.16786,places=4)
  self.assertIsNone(x["margin_maintenance_pct"])
 def test_not_use_wrong_date(self):
  with self.assertRaisesRegex(ValueError,"mismatched"):mod.parse_payload(self.fixture(),"2026-09-10")
 def test_report_requires_all_three_summary_rows(self):
  x=self.fixture();x["creditList"]=x["creditList"][:2]
  with self.assertRaisesRegex(ValueError,"Missing exact"):mod.parse_payload(x,"2026-09-11")
 def test_table_schema_fallback(self):
  x=self.fixture();rows=x.pop("creditList");x["tables"]=[{"title":"信用交易統計","data":rows}]
  self.assertEqual(mod.parse_payload(x,"2026-09-11")["short_delta_lots"],479)
if __name__=="__main__":unittest.main()
