import datetime as dt
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/"scripts"/"collect_social_sentiment.py"
spec=importlib.util.spec_from_file_location("social_collector",PATH)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
NOW=dt.datetime(2026,10,24,4,0,tzinfo=dt.timezone.utc)
def atom(n=10):
    elements=[]
    for i in range(n):
        title="【討論】多頭突破" if i<7 else "【討論】崩盤跌停"
        elements.append(f'<entry><title>{title} 股票{i}</title><link href="https://www.ptt.cc/bbs/Stock/M.{i}.html"/><updated>2026-10-24T03:00:00Z</updated></entry>')
    return ('<feed xmlns="http://www.w3.org/2005/Atom">'+''.join(elements)+'</feed>').encode()

class SocialCollectorTest(unittest.TestCase):
    def test_ptt_atom_and_sentiment(self):
        rows=mod.ptt(atom(),NOW)
        self.assertEqual(len(rows),10)
        summary=mod.statistics(rows)
        self.assertEqual(summary["status"],"已有樣本｜偏多討論較多")
        self.assertEqual(summary["bull"],7)
        self.assertEqual(summary["bear"],3)
    def test_future_and_bad_url_rejected(self):
        self.assertIsNone(mod.sanitize("PTT","多頭趨勢上揚","https://evil.com/x","2026-10-24T03:00:00Z",NOW))
        self.assertIsNone(mod.sanitize("PTT","多頭趨勢上揚","https://www.ptt.cc/x","2026-10-25T03:00:00Z",NOW))
    def test_cautious_lexicon_handles_both_directions(self):
        self.assertEqual(mod.score("崩盤後多頭強勢反彈"),"中立／難判")
        self.assertEqual(mod.score("台股走勢怎麼看"),"中立／難判")
    def test_no_unapproved_platform_posts_invented(self):
        with patch.object(mod,"news_items",return_value=([],"無有效來源")):
            result=mod.collect(now=NOW,fetch=lambda url:atom(),old={},environmental={})
        self.assertEqual(result["sources"]["Threads"]["status"],"not_authorized")
        self.assertEqual(result["sources"]["Instagram"]["status"],"not_authorized")
        self.assertEqual(result["sources"]["PTT"]["status"],"ok")
        self.assertEqual(result["social"]["sample"],10)
        self.assertEqual(len(result["items"]),10)
    def test_error_retains_only_fresh_existing_evidence(self):
        old={"items":[
          {"platform":"PTT","title":"今天多頭突破上攻","url":"https://www.ptt.cc/bbs/Stock/M.1.html","publishedAt":"2026-10-24T03:00:00Z"},
          {"platform":"PTT","title":"很久以前的多頭","url":"https://www.ptt.cc/bbs/Stock/M.2.html","publishedAt":"2026-10-21T03:00:00Z"}]}
        def bad(_):raise OSError("來源失聯")
        with patch.object(mod,"news_items",return_value=([],"缺值")):
            result=mod.collect(now=NOW,fetch=bad,old=old,environmental={})
        self.assertEqual(result["sources"]["PTT"]["status"],"error")
        self.assertEqual(len(result["items"]),1)
        self.assertEqual(result["social"]["status"],"已有樣本｜偏多討論較多")
    def test_one_neutral_post_still_counts_as_valid_sample(self):
        row=mod.sanitize("PTT","台股下週大家怎麼看","https://www.ptt.cc/bbs/Stock/M.1.html",
                         "2026-10-24T03:00:00Z",NOW)
        stats=mod.statistics([row])
        self.assertEqual(stats["sample"],1)
        self.assertEqual(stats["status"],"已有樣本｜尚無明確多空方向")
        self.assertNotIn("樣本不足",stats["status"])
    def test_one_bearish_post_can_be_reported_without_claiming_consensus(self):
        x=mod.sanitize("PTT","台股崩盤跌停走勢","https://www.ptt.cc/bbs/Stock/M.2.html",
                       "2026-10-24T03:00:00Z",NOW)
        stats=mod.statistics([x])
        self.assertEqual(stats["sample"],1)
        self.assertEqual(stats["status"],"已有樣本｜偏空討論較多")
        self.assertIn("不代表市場共識",stats["method"])
    def test_duplicate_url_no_double_count(self):
        r=mod.ptt(atom(),NOW)
        self.assertEqual(len(mod.unique(r+r)),10)
    def test_fallback_lowercase_atom_then_board(self):
        calls=[]
        def partial(url):
            calls.append(url)
            if url==mod.PTT_URL:raise OSError("blocked Atom")
            if url==mod.PTT_FEEDS[1]:return b"<broken>"
            epoch=int((NOW-dt.timedelta(hours=1)).timestamp())
            return (f'<div class="r-ent"><div class="title"><a href="/bbs/Stock/M.{epoch}.A.11.html">[討論] 台積電突破</a></div></div>').encode()
        rows,state=mod.collect_ptt(NOW,partial)
        self.assertEqual(len(calls),3)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["stance"],"偏多")
        self.assertIn("推算",rows[0]["timestampBasis"])
        self.assertEqual(state["method"],"公開看板 HTML 備援")
    def test_reposted_news_and_sarcasm_do_not_inflate_sentiment(self):
        for text in ["[新聞] 明天台股暴跌","反指標又來看多突破，笑死"]:
            item=mod.sanitize("PTT",text,"https://www.ptt.cc/bbs/Stock/M.1.html","2026-10-24T03:00:00Z",NOW)
            self.assertEqual(item["stance"],"中立／難判")
        self.assertEqual(mod.score("多頭漲停突破"),"偏多")
    def test_ptt_repost_is_listed_as_news_not_survey_voter(self):
        raw='''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
          <title>[新聞] 台股明開盤恐補跌千點</title>
          <link href="https://www.ptt.cc/bbs/Stock/M.1792918324.A.BBD.html"/>
          <updated>2026-10-24T03:00:00Z</updated></entry></feed>'''.encode()
        with patch.object(mod,"news_items",return_value=([],"無新聞")):
            d=mod.collect(now=NOW,fetch=lambda url:raw if url in mod.PTT_FEEDS else
                b"<div class='title'></div>",old={},environmental={})
        self.assertEqual(len(d["pttNewsItems"]),1)
        self.assertEqual(d["pttNewsItems"][0]["contentType"],"新聞轉載")
        self.assertEqual(d["social"]["sample"],0)
        self.assertEqual(d["social"]["repostedNews"],1)
        self.assertNotIn("pushScore",d["pttNewsItems"][0])
    def test_board_supplements_delayed_atom_without_faking_official_time(self):
        newer=int((NOW-dt.timedelta(hours=1)).timestamp())
        rss='''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
        <title>[新聞] 台股空頭跌停</title>
        <link href="https://www.ptt.cc/bbs/Stock/M.1792918324.A.ABC.html"/>
        <updated>2026-10-24T03:00:00Z</updated></entry></feed>'''.encode()
        board=f'''<div class="r-ent"><div class="nrec"><span class="hl f1">爆</span></div>
        <div class="title"><a href="/bbs/Stock/M.{newer}.A.DEF.html">[新聞] 台股明開盤補跌</a></div></div>'''.encode()
        with patch.object(mod,"news_items",return_value=([],"無")):
            result=mod.collect(now=NOW,fetch=lambda u:board if u==mod.PTT_BOARD else
                               rss if u in mod.PTT_FEEDS else b'{}',old={},environmental={})
        self.assertEqual(len(result["pttNewsItems"]),2)
        by_url={x["url"]:x for x in result["pttNewsItems"]}
        board_post=by_url[f"https://www.ptt.cc/bbs/Stock/M.{newer}.A.DEF.html"]
        self.assertIn("推算",board_post["timestampBasis"])
        self.assertEqual(board_post["pushScore"],100)
        self.assertEqual(result["social"]["sample"],0)
    def test_ptt_public_push_labels_are_optional_and_not_sentiment(self):
        original="https://www.ptt.cc/bbs/Stock/M.1792918324.A.BBD.html"
        html='''<div class="r-ent"><div class="nrec"><span class="hl f1">爆</span></div>
            <div class="title"><a href="/bbs/Stock/M.1792918324.A.BBD.html">[新聞] 台股明開盤</a></div></div>'''
        votes=mod.ptt_board_reactions(html.encode())
        self.assertEqual(votes[original]["pushScore"],100)
        self.assertEqual(votes[original]["pushLabel"],"爆")
        self.assertEqual(mod.score("[新聞] 台股暴跌"),"偏空")
        self.assertEqual(mod.classify_discussion("[新聞] 台股暴跌"),("新聞轉載",False))
    def test_stock_heat_rejects_news_copy_and_substring_collision(self):
        catalog=("2026-10-24",[{"code":"2330","name":"台積電","theme":"半導體","ret20":35,"rvol":3,"ma20Slope":8}])
        titles=["[討論] 2330 又噴","[討論] 2330 強勢","[新聞] 台積電爆漲"]
        items=[mod.sanitize("PTT",t,f"https://www.ptt.cc/bbs/Stock/M.{i}.html","2026-10-24T03:00:00Z",NOW)
               for i,t in enumerate(titles)]
        heat=mod.topic_heat(items,NOW,catalog)
        self.assertEqual(heat["stocks"][0]["sample"],3)
        self.assertFalse(heat["stocks"][0]["overheatWatch"])
        items.append(mod.sanitize("PTT","[討論] 台積電怎麼看","https://www.ptt.cc/bbs/Stock/M.9.html","2026-10-24T03:00:00Z",NOW))
        self.assertTrue(mod.topic_heat(items,NOW,catalog)["stocks"][0]["overheatWatch"])
        self.assertFalse(mod.mentions_stock("12330",catalog[1][0]))
    def test_public_rss_bridge_requires_original_ptt_links(self):
        xml='<rss><channel><item><title>[討論] 台積電突破</title><link>https://www.ptt.cc/bbs/Stock/M.1792800000.A.A.html</link><pubDate>Sat, 24 Oct 2026 03:00:00 +0000</pubDate></item><item><title>[討論] 假股票文</title><link>https://evil.example/post</link><pubDate>Sat, 24 Oct 2026 03:00:00 +0000</pubDate></item></channel></rss>'.encode('utf-8')
        rows=mod.ptt_public_feed(xml,NOW)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["platform"],"PTT")
        self.assertIn("第三方",rows[0]["feedBasis"])
    def test_no_network_no_cached_posts_still_publishes_explicit_missing(self):
        with patch.object(mod,"news_items",return_value=([],"沒有新新聞")):
            result=mod.collect(now=NOW,fetch=lambda _:(_ for _ in ()).throw(OSError("blocked")),
                               old={},environmental={})
        self.assertEqual(result["sources"]["PTT"]["status"],"error")
        self.assertEqual(result["social"]["sample"],0)
        self.assertEqual(result["stockHeat"]["stocks"],[])
    def test_bluesky_official_public_search_checks_original_post_and_taiwan_context(self):
        created="2026-10-24T03:00:00Z"
        good={"uri":"at://did:plc:testabc/app.bsky.feed.post/3lxyzabc",
              "author":{"handle":"trader.bsky.social"},
              "record":{"text":"台股 2330 台積電多頭突破","createdAt":created}}
        other={"uri":"at://did:plc:testabc/app.bsky.feed.post/3lxyzabx",
               "author":{"handle":"trader.bsky.social"},
               "record":{"text":"CPO marketing unrelated technology","createdAt":created}}
        evil={"uri":"at://did:plc:testabc/app.bsky.feed.post/3lxyzaby",
              "author":{"handle":"evil.com/../"},
              "record":{"text":"台股多頭突破","createdAt":created}}
        responses=[]
        def fetch(url):
            responses.append(url)
            return json.dumps({"posts":[good,other,evil]},ensure_ascii=False).encode()
        rows=mod.bluesky(NOW,fetch)
        self.assertGreaterEqual(len(responses),len(mod.BLUESKY_QUERIES))
        self.assertLessEqual(len(responses),len(mod.BLUESKY_QUERIES)+3)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["platform"],"Bluesky")
        self.assertEqual(rows[0]["url"],"https://bsky.app/profile/trader.bsky.social/post/3lxyzabc")
        self.assertEqual(rows[0]["stance"],"偏多")
        self.assertIn("官方公開搜尋",rows[0]["method"])
    def test_bluesky_uses_documented_second_appview_host_only_on_http_access_error(self):
        import urllib.error
        calls=[]
        entry={"uri":"at://did:plc:abc/app.bsky.feed.post/3abcd",
               "author":{"handle":"hello.bsky.social"},
               "record":{"text":"台股台積電市場突破","createdAt":"2026-10-24T03:00:00Z"}}
        def fetch(url):
            calls.append(url)
            if url.startswith(mod.BLUESKY_API):raise urllib.error.HTTPError(url,403,"Restricted",{},None)
            if url.startswith(mod.BLUESKY_BACKUP_API):return json.dumps({"posts":[entry]}).encode()
            raise AssertionError("unexpected endpoint")
        rows=mod.bluesky(NOW,fetch)
        self.assertEqual(len(rows),1)
        self.assertGreaterEqual(len(calls),len(mod.BLUESKY_QUERIES)*2)
        self.assertLessEqual(len(calls),len(mod.BLUESKY_QUERIES)*2+6)
        self.assertTrue(all(x.startswith((mod.BLUESKY_API,mod.BLUESKY_BACKUP_API)) for x in calls))
    def test_bluesky_rejects_future_old_and_unverifiable_post_dates(self):
        def fetch(_):
            samples=[]
            for i,t in enumerate(["2026-10-25T06:00:00Z","2026-10-20T03:00:00Z",None]):
                samples.append({"uri":"at://did:plc:abc/app.bsky.feed.post/3abc"+str(i),
                 "author":{"handle":"valid.bsky.social"},
                 "record":{"text":"台股未來市場突破","createdAt":t}})
            return json.dumps({"posts":samples}).encode()
        self.assertEqual(mod.bluesky(NOW,fetch),[])
    def test_bluesky_api_error_keeps_explicit_missing_source_state(self):
        def fetch(url):
            if url.startswith(mod.BLUESKY_API):raise OSError("Bluesky 失聯")
            return atom()
        with patch.object(mod,"news_items",return_value=([],"沒有新新聞")):
            data=mod.collect(now=NOW,fetch=fetch,old={},environmental={})
        self.assertEqual(data["sources"]["Bluesky"]["status"],"error")
        self.assertEqual(data["sources"]["PTT"]["status"],"ok")
        self.assertEqual(data["social"]["sample"],10)
    def test_bluesky_cache_only_retains_valid_recent_public_posts(self):
        old={"items":[{"platform":"Bluesky","title":"台股 2330 走勢怎麼看",
                       "url":"https://bsky.app/profile/user.bsky.social/post/3ab",
                       "publishedAt":"2026-10-24T03:00:00Z"},
                      {"platform":"Bluesky","title":"台股過期貼文",
                       "url":"https://bsky.app/profile/user.bsky.social/post/3ac",
                       "publishedAt":"2026-10-19T03:00:00Z"}]}
        with patch.object(mod,"news_items",return_value=([],"缺值")):
            data=mod.collect(now=NOW,fetch=lambda url:(_ for _ in ()).throw(OSError("offline")),
                             old=old,environmental={})
        self.assertEqual(data["sources"]["Bluesky"]["status"],"error")
        self.assertEqual(len(data["items"]),1)
        self.assertEqual(data["items"][0]["platform"],"Bluesky")
    def test_only_real_investment_discussion_contributes_to_sentiment(self):
        samples=[
          ("台積電運動會取消但員工獎金照發","非投資話題",False,"中立／難判"),
          ("#中央社即時新聞：台積電營收成長，記者報導","新聞轉載",False,"中立／難判"),
          ("我剛加碼買進台積電，看多走勢","投資討論",True,"偏多"),
          ("台股暴跌要停損了","投資討論",True,"偏空"),
          ("感覺現在買不起台積電","投資討論",True,"中立／難判"),
        ]
        for i,(title,kind,eligible,stance) in enumerate(samples):
            row=mod.sanitize("Bluesky",title,f"https://bsky.app/profile/test.bsky.social/post/3ab{i}",
                             "2026-10-24T03:00:00Z",NOW)
            self.assertEqual(row["contentType"],kind,title)
            self.assertEqual(row["investmentEligible"],eligible,title)
            self.assertEqual(row["stance"],stance,title)
    def test_quality_report_keeps_raw_and_investment_counts_separate(self):
        examples=[
          "[新聞] 台股暴跌新聞標題",
          "[討論] 台股多頭突破",
          "[討論] 台股空頭崩盤",
          "台積電運動會舉辦"]
        xml='<feed xmlns="http://www.w3.org/2005/Atom">'+''.join(
          f'<entry><title>{t}</title><link href="https://www.ptt.cc/bbs/Stock/M.{i}.html"/>'
          '<updated>2026-10-24T03:00:00Z</updated></entry>'
          for i,t in enumerate(examples))+'</feed>'
        with patch.object(mod,"news_items",return_value=([],"無有效新聞")):
            d=mod.collect(now=NOW,fetch=lambda u:xml.encode() if u.startswith(mod.PTT_URL) else
                          json.dumps({"posts":[]}).encode(),old={},environmental={})
        summary=d["social"]
        self.assertEqual(summary["rawSample"],4)
        self.assertEqual(summary["sample"],2)
        self.assertEqual(summary["investmentDiscussion"],2)
        self.assertEqual(summary["repostedNews"],1)
        self.assertEqual(summary["unrelated"],1)
        self.assertEqual(summary["bull"],1)
        self.assertEqual(summary["bear"],1)
        self.assertEqual(len(d["items"]),4)
        self.assertEqual(summary["platformCounts"]["PTT"],2)
    def test_partial_bluesky_rate_limit_preserves_verified_posts(self):
        import urllib.error
        diagnostics={}
        calls=[]
        def fetch(url):
            calls.append(url)
            if len(calls)==1:
                return json.dumps({"posts":[{"uri":"at://did:plc:abc/app.bsky.feed.post/3abc",
                 "author":{"handle":"trader.bsky.social"},
                 "record":{"text":"台股多頭突破，想加碼","createdAt":"2026-10-24T03:00:00Z"}}]}).encode()
            raise urllib.error.HTTPError(url,429,"Too many requests",{},None)
        with patch.object(mod,"stock_catalog",return_value=("",[])):
            rows=mod.bluesky(NOW,fetch,diagnostics)
        self.assertEqual(len(rows),1)
        self.assertTrue(diagnostics["rateLimited"])
        self.assertEqual(diagnostics["queriesSucceeded"],1)
        self.assertEqual(diagnostics["queriesFailed"],1)
        self.assertEqual(diagnostics["queriesAttempted"],2)
    def test_all_bluesky_queries_fail_closed(self):
        with patch.object(mod,"stock_catalog",return_value=("",[])):
            with self.assertRaises(ValueError):
                mod.bluesky(NOW,lambda _:(_ for _ in ()).throw(OSError("offline")))
    def test_youtube_official_search_returns_only_recent_taiwan_titles(self):
        title={"id":{"kind":"youtube#video","videoId":"AbCdeF_0123"},
               "snippet":{"title":"台股 台積電股價如何分析？","publishedAt":"2026-10-24T03:00:00Z",
                          "channelTitle":"研究測試頻道"}}
        bad={"id":{"kind":"youtube#video","videoId":"evil/../../x"},
               "snippet":{"title":"台股會飆漲","publishedAt":"2026-10-24T03:00:00Z"}}
        urls=[]
        def get(url):
            urls.append(url)
            self.assertIn("key=fake_test_key",url)
            return json.dumps({"items":[title,bad]},ensure_ascii=False).encode()
        rows=mod.youtube_titles("fake_test_key",NOW,get)
        self.assertEqual(len(urls),len(mod.YOUTUBE_SEARCH_TERMS))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["platform"],"YouTube")
        self.assertEqual(rows[0]["url"],"https://www.youtube.com/watch?v=AbCdeF_0123")
        self.assertEqual(rows[0]["sourceName"],"研究測試頻道")
        self.assertNotIn("stance",rows[0])
    def test_facebook_requires_authorized_page_and_original_meta_link(self):
        def get(url,token):
            self.assertEqual(token,"authorized_test_token")
            self.assertTrue(url.startswith(mod.FACEBOOK_API+"123456789/posts?"))
            return json.dumps({"data":[
             {"message":"台股跌幅擴大，投資人觀望","created_time":"2026-10-24T03:00:00Z",
              "permalink_url":"https://www.facebook.com/page/posts/12345"},
             {"message":"台股會漲","created_time":"2026-10-24T03:00:00Z",
              "permalink_url":"https://evil.example/fake"}]}).encode()
        posts=mod.facebook_page_posts("authorized_test_token","123456789",NOW,get)
        self.assertEqual(len(posts),1)
        self.assertEqual(posts[0]["platform"],"Facebook")
        self.assertNotIn("stance",posts[0])
        with self.assertRaises(ValueError):
            mod.facebook_page_posts("token","invalid/path",NOW,get)
    def test_missing_creator_api_secrets_never_inflate_social_sentiment(self):
        with patch.object(mod,"news_items",return_value=([],"無新新聞")):
            result=mod.collect(now=NOW,fetch=lambda _:(_ for _ in ()).throw(OSError("blocked")),
                               old={},environmental={})
        self.assertEqual(result["sources"]["YouTube"]["status"],"not_configured")
        self.assertEqual(result["sources"]["Facebook"]["status"],"not_authorized")
        self.assertEqual(result["creatorMedia"],[])
        self.assertEqual(result["social"]["rawSample"],0)
    def test_creator_items_are_separate_even_when_source_and_social_both_relevant(self):
        mock_youtube={"platform":"YouTube","title":"台股正式突破",
           "url":"https://www.youtube.com/watch?v=AbCdeF_0123",
           "publishedAt":"2026-10-24T03:00:00Z","sourceName":"投資頻道"}
        mock_facebook={"platform":"Facebook","title":"台股跌幅觀察",
           "url":"https://www.facebook.com/page/posts/12345",
           "publishedAt":"2026-10-24T03:00:00Z"}
        with patch.object(mod,"youtube_titles",return_value=[mock_youtube]),\
             patch.object(mod,"facebook_page_posts",return_value=[mock_facebook]),\
             patch.object(mod,"news_items",return_value=([],"無新新聞")):
            d=mod.collect(now=NOW,fetch=lambda _:(_ for _ in ()).throw(OSError("blocked")),
               old={},environmental={"YOUTUBE_API_KEY":"stub","FACEBOOK_PAGE_ACCESS_TOKEN":"stub",
                                    "FACEBOOK_PAGE_IDS":"123456789"})
        self.assertEqual(len(d["creatorMedia"]),2)
        self.assertEqual(d["sources"]["YouTube"]["status"],"ok")
        self.assertEqual(d["sources"]["Facebook"]["status"],"ok")
        self.assertEqual(d["social"]["sample"],0)
        self.assertEqual(d["stockHeat"]["stocks"],[])
    def test_dont_use_old_news(self):
        with patch.object(mod,"NEWS_PATH",Path("/definitely/not/a/real/file.json")):
            rows,reason=mod.news_items(NOW)
        self.assertEqual(rows,[])
        self.assertTrue(reason)
if __name__=="__main__":
    unittest.main()
