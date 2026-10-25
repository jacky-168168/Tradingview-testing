import datetime as dt
import importlib.util
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch
N=dt.datetime(2026,10,25,3,0,tzinfo=dt.timezone.utc)
SOURCE=Path(__file__).resolve().parents[1]/"scripts"/"collect_orion_news.py"
spec=importlib.util.spec_from_file_location("orion_news",SOURCE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def feed():
    return b"""<rss><channel><item>
      <title>台股大漲！台積電利多創新高</title>
      <link>https://www.cna.com.tw/news/afe/202610240001.aspx</link>
      <pubDate>Sat, 24 Oct 2026 23:00:00 +0000</pubDate>
    </item><item><title>台股跌停市場恐慌</title>
      <link>https://evil.example/unsafe</link>
      <pubDate>Sat, 24 Oct 2026 23:00:00 +0000</pubDate>
    </item></channel></rss>"""
class TestOrionNews(unittest.TestCase):
    def test_official_rss_parsing_rejects_offsite_articles_and_preserves_date(self):
        rows=mod.parse_feed(feed(),"中央通訊社","產經證券",("www.cna.com.tw",),N)
        self.assertEqual(len(rows),1)
        x=rows[0];self.assertEqual(x["source"],"中央通訊社")
        self.assertEqual(x["headlineRuleTone"],"偏多")
        self.assertEqual(x["publishedAt"],"2026-10-24T23:00:00Z")
        self.assertIn("AI／半導體",x["themes"])
    def test_external_entity_not_followed_and_unverifiable_dates_rejected(self):
        future=b"""<rss><channel><item><title>台股大漲</title>
          <link>https://www.cna.com.tw/news/afe/202610240001.aspx</link>
          <pubDate>Sun, 25 Oct 2026 08:00:00 +0000</pubDate></item></channel></rss>"""
        self.assertEqual(mod.parse_feed(future,"中央通訊社","金融",("www.cna.com.tw",),N),[])
        with self.assertRaises(ET.ParseError):mod.parse_feed(b"<broken>","中央通訊社","金融",("www.cna.com.tw",),N)
    def test_dedup_source_and_ignore_repeats(self):
        rows=mod.parse_feed(feed(),"中央通訊社","產經證券",("www.cna.com.tw",),N)
        clean=mod.unique_articles(rows+rows)
        self.assertEqual(len(clean),1)
        self.assertEqual(len(clean[0]["id"]),20)
        self.assertEqual(len(clean[0]["headlineGroup"]),14)
    def test_failed_feeds_report_truth_and_can_include_verified_success(self):
        def mock(url):
            if "rsscna/finance" in url:return feed()
            raise OSError("unavailable")
        with patch.object(mod,"old_market_events",return_value=[]):
            result=mod.collect(N,mock)
        self.assertEqual(result["coverage"]["healthyFeeds"],1)
        self.assertEqual(len(result["items"]),1)
        self.assertEqual(result["coverage"]["allTaiwanMediaCovered"],False)
        self.assertEqual(result["coverage"]["sources"]["自由時報／財經"]["status"],"error")
        self.assertEqual(result["ruleTone"]["偏多"],1)
    def test_archive_daily_dedupe_and_runs(self):
        with patch.object(mod,"old_market_events",return_value=[]):
            report=mod.collect(N,lambda url:feed() if "rsscna/finance" in url else b"<rss><channel></channel></rss>")
        first=mod.archive(report,now=N)
        second=mod.archive(report,now=N+dt.timedelta(minutes=8),old=first)
        self.assertEqual(first["day"],"2026-10-25")
        self.assertEqual(len(first["items"]),1)
        self.assertEqual(len(second["items"]),1)
        self.assertEqual(len(second["runs"]),2)
    def test_no_feeds_and_stale_existing_news_cannot_be_a_real_signal(self):
        with patch.object(mod,"old_market_events",return_value=[]):
            result=mod.collect(N,lambda _:(_ for _ in ()).throw(OSError("offline")),previous={"items":[{"fake":True}]})
        self.assertEqual(result["items"],[])
        self.assertEqual(result["coverage"]["healthyFeeds"],0)
        self.assertEqual(result["coverage"]["sources"]["history"]["status"],"no_fresh_articles")
if __name__=="__main__":unittest.main()
