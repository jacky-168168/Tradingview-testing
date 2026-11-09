from __future__ import annotations
import sys
import re
import unittest
from datetime import datetime,timedelta
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
 def test_promotional_blog_filtered_out(self):
  feed=("AI需求","AI 晶片需求",r"AI|晶片",["AI"])
  xml='''<rss><channel><item><title>AI晶片需求暴增！趕緊搶進熱門股 - CMoney投資網誌</title><link>https://example.com/blog</link><source>CMoney投資網誌</source><pubDate>Fri, 16 Oct 2026 07:00:00 GMT</pubDate></item></channel></rss>'''
  self.assertEqual(parse_feed(xml.encode(),feed,now=NOW),[])
 def test_rss_articles_older_than_48h_never_display_as_latest(self):
  stale_time=NOW-timedelta(hours=49)
  old_rss=f'''<rss><channel><item><title>矽晶圓廠報價上漲 最新觀察 - 經濟日報</title>
   <link>https://example.com/old</link><source>經濟日報</source>
   <pubDate>{stale_time.strftime("%a, %d %b %Y %H:%M:%S %z")}</pubDate></item></channel></rss>'''
  self.assertEqual(parse_feed(old_rss.encode(),FEED,now=NOW),[])
 def test_recent_rss_articles_must_still_pass(self):
  self.assertEqual(len(parse_feed(XML.encode(),FEED,now=NOW)),1)
 def test_ptt_atom_posts_include_only_current_original_news_reposts(self):
  from market_major_events import parse_ptt_stock_news
  raw='''<feed xmlns="http://www.w3.org/2005/Atom">
   <entry><title>[新聞] 台股明開盤恐補跌千點</title>
    <link href="https://www.ptt.cc/bbs/Stock/M.1792918324.A.BBD.html"/>
    <updated>2026-10-16T07:00:00Z</updated></entry>
   <entry><title>[閒聊] 台股明開盤</title>
    <link href="https://www.ptt.cc/bbs/Stock/M.1792918325.A.BBD.html"/>
    <updated>2026-10-16T07:00:00Z</updated></entry>
   <entry><title>[新聞] 台股暴跌 假文章</title>
    <link href="https://evil.example/bbs/Stock/M.1792918326.A.BBD.html"/>
    <updated>2026-10-16T07:00:00Z</updated></entry>
   </feed>'''
  result=parse_ptt_stock_news(raw.encode(),now=NOW)
  self.assertEqual(len(result),1)
  self.assertEqual(result[0]["category"],"PTT轉載")
  self.assertEqual(result[0]["originType"],"forum_repost")
  self.assertFalse(result[0]["confirmed"])
 def test_ptt_atom_excludes_expired_news(self):
  from market_major_events import parse_ptt_stock_news
  raw='''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
   <title>[新聞] 台股明開盤恐補跌千點</title>
   <link href="https://www.ptt.cc/bbs/Stock/M.1792918324.A.BBD.html"/>
   <updated>2026-10-13T07:00:00Z</updated></entry></feed>'''
  self.assertEqual(parse_ptt_stock_news(raw.encode(),now=NOW),[])
 def test_commodity_query_coverage_is_independent(self):
  expected={
   "原油／能源":("WTI","EIA","天然氣"),
   "貴金屬":("黃金","白銀","鉑金"),
   "農產品":("黃豆","咖啡","USDA"),
  }
  for category,topics in expected.items():
   queries=[q for q in QUERIES if q[0]==category]
   self.assertGreaterEqual(len(queries),3,category)
   self.assertTrue(all("when:2d" in q[1] and q[2] and q[3] for q in queries))
   for topic in topics:
    self.assertTrue(any(topic in q[1] for q in queries),(category,topic))
 def test_commodity_news_are_classified_and_dated_without_inventing_confirmation(self):
  examples=[
   ("原油／能源","OPEC 宣布減產 原油價格上漲"),
   ("貴金屬","白銀報價大漲 工業需求增溫"),
   ("農產品","黃豆乾旱歉收 USDA 下修產量"),
  ]
  candidates=[]
  for index,(category,title) in enumerate(examples):
   spec=next(q for q in QUERIES if q[0]==category and re.search(q[2],title,re.I))
   xml=f"""<rss><channel><item><title>{title} - 經濟日報</title>
    <link>https://example.com/commodity/{index}</link><source>經濟日報</source>
    <pubDate>Fri, 16 Oct 2026 07:00:00 GMT</pubDate></item></channel></rss>"""
   rows=parse_feed(xml.encode(),spec,now=NOW)
   self.assertEqual(len(rows),1,(category,title))
   self.assertEqual(rows[0]["category"],category)
   self.assertFalse(rows[0]["confirmed"])
   candidates.extend(rows)
  out=build(now=NOW,feeds=[candidates],prior=None)
  self.assertEqual(len([x for x in out["items"] if x["type"]=="news"]),3)
  self.assertEqual({x["category"] for x in out["items"] if x["type"]=="news"},
                   {"原油／能源","貴金屬","農產品"})
 def test_commodity_stale_headlines_do_not_pass_age_gate(self):
  for category,word in (("原油／能源","WTI 油價上漲"),("貴金屬","黃金價格下跌"),
                        ("農產品","黃豆收成下修")):
   spec=next(q for q in QUERIES if q[0]==category)
   stale=(NOW-timedelta(hours=49)).strftime("%a, %d %b %Y %H:%M:%S %z")
   xml=f"""<rss><channel><item><title>{word} - 經濟日報</title>
    <link>https://example.com/commodity/stale</link><source>經濟日報</source>
    <pubDate>{stale}</pubDate></item></channel></rss>"""
   self.assertFalse(parse_feed(xml.encode(),spec,now=NOW),category)
 def test_empty_successful_feed_is_not_marked_live_with_news(self):
  result=build(now=NOW,feeds=[[] for _ in QUERIES],prior=None)
  self.assertEqual(result["status"],"empty")
  self.assertEqual(result["newsCount"],0)
  self.assertIsNone(result["newestNewsAt"])
 def test_prior_news_not_reused_beyond_48h(self):
  sample=parse_feed(XML.encode(),FEED,now=NOW)[0]
  sample["publishedAt"]=(NOW-timedelta(hours=49)).isoformat()
  result=build(now=NOW,feeds=[None],prior={"items":[sample]})
  self.assertEqual([x for x in result["items"] if x["type"]=="news"],[])
 def test_old_items_excluded_and_no_invented_news(self):
  old=parse_feed(XML.encode(),FEED,now=NOW)[0]
  old["publishedAt"]="2026-10-01T12:00:00+08:00"
  result=build(now=NOW,feeds=[None],prior={"items":[old]})
  self.assertEqual(len([x for x in result["items"] if x["type"]=="news"]),0)

class GlobalSourceRegressionTest(unittest.TestCase):
 def _rss(self,source_domain="https://www.reuters.com",when="Fri, 16 Oct 2026 07:00:00 GMT"):
  return f"""<rss><channel>
   <item><title>Trump tariffs on chip imports cause fresh trade-policy uncertainty - Reuters</title>
    <link>https://news.google.com/rss/articles/example</link>
    <source url="{source_domain}">Reuters</source><pubDate>{when}</pubDate></item>
   <item><title>World Cup football results - Reuters</title>
    <link>https://news.google.com/rss/articles/sport</link>
    <source url="https://www.reuters.com">Reuters</source><pubDate>{when}</pubDate></item>
   </channel></rss>""".encode()
 def test_only_foreign_original_publisher_and_conditional_market_note(self):
  from market_global_news import GLOBAL_FEEDS,parse_global_feed
  spec=GLOBAL_FEEDS[0]
  rows=parse_global_feed(self._rss(),spec,now=NOW)
  self.assertEqual(len(rows),1)
  item=rows[0]
  self.assertEqual(item["category"],"國際政策")
  self.assertEqual(item["source"],"Reuters")
  self.assertEqual(item["originType"],"foreign_original")
  self.assertIn("半導體",item["impactAssets"])
  self.assertIn("未驗證",item["impactStatus"])
  self.assertFalse(item["confirmed"])
 def test_domestic_publisher_must_be_blocked_even_inside_google_rss(self):
  from market_global_news import GLOBAL_FEEDS,parse_global_feed
  self.assertEqual(parse_global_feed(self._rss("https://www.udn.com"),GLOBAL_FEEDS[0],now=NOW),[])
 def test_stale_foreign_news_must_be_blocked(self):
  from market_global_news import GLOBAL_FEEDS,parse_global_feed
  older=(NOW-timedelta(hours=49)).strftime("%a, %d %b %Y %H:%M:%S %z")
  self.assertFalse(parse_global_feed(self._rss(when=older),GLOBAL_FEEDS[0],now=NOW))
 def test_geopolitics_elections_and_fed_have_distinct_impact(self):
  from market_global_news import classify,LINKS
  self.assertEqual(classify("Iran missile attacks cause war escalation"),"地緣政治")
  self.assertEqual(classify("US midterm election shifts Congress balance"),"美國選舉")
  self.assertEqual(classify("Federal Reserve interest rate decision moves bond yields"),"國際總經")
  self.assertEqual(len(LINKS),4)
 def test_foreign_items_survive_local_news_capacity(self):
  from market_global_news import GLOBAL_FEEDS,parse_global_feed
  candidate=parse_global_feed(self._rss(),GLOBAL_FEEDS[0],now=NOW)[0]
  records=build(now=NOW,feeds=[[candidate]],prior=None)
  self.assertEqual(records["foreignNewsCount"],1)
  self.assertEqual(records["newsCount"],1)
  self.assertEqual(records["items"][-1]["originType"],"foreign_original")

if __name__=="__main__":unittest.main()
