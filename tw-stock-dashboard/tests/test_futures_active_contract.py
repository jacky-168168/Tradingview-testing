"""2026-10-21 TX rollover: the October expiry must never be used as 10/22 08:45 front month."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from futures_night import day_from_openapi,day_from_html,night_from_html,build
from datetime import datetime
from zoneinfo import ZoneInfo
class FuturesRolloverTest(unittest.TestCase):
 def setUp(self):
  self.rows=[
   {"Date":"20261021","Contract":"TX","ContractMonth(Week)":"202610","TradingSession":"一般","Last":"46648","Volume":"23455"},
   {"Date":"20261021","Contract":"TX","ContractMonth(Week)":"202611","TradingSession":"一般","Last":"46992","Volume":"40515"},
   {"Date":"20261021","Contract":"TX","ContractMonth(Week)":"202612","TradingSession":"一般","Last":"47178","Volume":"261"}]
 def test_roll_openapi(self):
  selected=day_from_openapi(self.rows)
  self.assertEqual((selected["contract"],selected["date"],selected["close"]),("202611","20261021",46992))
 def test_non_expiry_stays_current(self):
  rows=[{**x,"Date":"20261008","Volume":"45000" if x["ContractMonth(Week)"]=="202610" else "400"} for x in self.rows]
  self.assertEqual(day_from_openapi(rows)["contract"],"202610")
 def test_roll_official_html_even_when_prior_contract_was_october(self):
  html='''<div>2026/10/21 08:45~13:45 一般交易時段行情表</div><table class="table_f">
  <tr><td>TX</td><td>202610</td><td>47240</td><td>47288</td><td>46596</td><td>46648</td><td>307</td><td>0.66%</td><td>30400</td><td>23455</td><td>53855</td><td>-</td></tr>
  <tr><td>TX</td><td>202611</td><td>47388</td><td>47450</td><td>46872</td><td>46992</td><td>482</td><td>1.04%</td><td>8063</td><td>40515</td><td>48578</td><td>47013</td></tr></table>'''
  result=day_from_html(html,"2026-10-21","202610")
  self.assertIsNotNone(result)
  self.assertEqual(result["contract"],"202611")
 def test_expired_month_cannot_be_paired_to_next_session(self):
  day=day_from_openapi(self.rows)
  html='''2026/10/21 15:00~次日05:00 盤後交易時段行情表
  <table class="table_f"><tr><td>TX</td><td>202611</td><td>47200</td><td>47555</td><td>46983</td><td>47482</td><td>▲469</td><td>+1.00%</td><td>35753</td></tr></table>'''
  night=night_from_html(html,"2026-10-21","202611","2026-10-22")
  self.assertIsNotNone(night)
  result=build(day,night,datetime(2026,10,22,8,45,tzinfo=ZoneInfo("Asia/Taipei")))
  self.assertEqual(result["quality"],"paired-day-night")
  self.assertEqual(result["contract"],"202611")
  self.assertEqual(result["night"]["reportQueryDate"],"2026-10-22")
  self.assertNotEqual(result["night"]["close"],result["day"]["close"])
if __name__=="__main__":unittest.main()
