from __future__ import annotations
import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from market_major_events import OFFICIAL,QUERIES,build,parse_feed
TZ=ZoneInfo("Asia/Taipei")
NOW=datetime(2026,10,16,18,0,tzinfo=TZ)
FEED=("報價","矽晶圓 漲價 when:7d",r"矽晶圓|wafer",["矽晶圓"])
XML='''<rss><channel>
 <item><title>矽晶圓廠傳漲價但仍待公告 - 經濟日報</title><link>https://example.com/news1</link>
 <source url="https://example.com">經濟日報</source><pubDate>Fri, 16 Oct 2026 07:00:00 GMT</pubDate></item>
 <item><title>2026球場有很多球員 - 球報</title><link>https://example.com/sport</link>
 <source url="https://example.com">球報</source><pubDate>Fri, 16 Oct 2026 07:00:00 GMT</pubDate></item>
 <item><title>矽晶圓漲價推薦哪檔飆股 - 不明來源</title><link>https://example.com/pick</link>
 <source>不明來源</source><pubDate>Fri, 16 Oct 2026 07:00:00 GMT</pubDate></item>
 </channel></rss>'''
class MajorMarketNewsTest(unittest.TestCase):
 def test_event_is_official_and_has_grounded_source(self):
  records=build(now=NOW,feeds=[None],prior=None)
  self.assertEqual(records["status"],"degraded")
  ids={x["id"] for x in records["items"]}
  self.assertIn("event-tpca-show-2026",ids)
  self.assertIn("event-impact-2026",ids)
  self.assertTrue(all(x["confirmed"] and x["url"].startswith("https://") for x in records["items"]))
 def test_reject_irrelevant_and_stock_tip(self):
  x=parse_feed(XML.encode(),FEED,now=NOW)
  self.assertEqual(len(x),1)
  self.assertEqual(x[0]["confirmed"],False)
  self.assertEqual(x[0]["source"],"經濟日報")
  self.assertEqual(x[0]["date"],"2026-10-16")
 def test_dedup_does_not_turn_news_into_facts(self):
  news=parse_feed(XML.encode(),FEED,now=NOW)
  out=build(now=NOW,feeds=[news,news],prior=None)
  self.assertEqual(out["status"],"partial")
  self.assertEqual(len([x for x in out["items"] if x["type"]=="news"]),1)
  self.assertFalse(next(x for x in out["items"] if x["type"]=="news")["confirmed"])
 def test_old_items_excluded_and_no_invented_news(self):
  old=parse_feed(XML.encode(),FEED,now=NOW)[0]
  old["publishedAt"]="2026-10-01T12:00:00+08:00"
  result=build(now=NOW,feeds=[None],prior={"items":[old]})
  self.assertEqual(len([x for x in result["items"] if x["type"]=="news"]),0)
if __name__=="__main__":unittest.main()
