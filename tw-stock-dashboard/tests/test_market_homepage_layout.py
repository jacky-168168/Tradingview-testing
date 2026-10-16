"""Static page integrity tests for progressively disclosed market-risk dashboard.
This is not a visual screenshot test. Prevents missing/duplicate IDs, broken DOM
nesting, and accidentally putting core buy-status information in collapsed cards.
"""
from html.parser import HTMLParser
from pathlib import Path
import unittest
HTML=Path(__file__).resolve().parents[1]/"docs"/"index.html"
CSS=Path(__file__).resolve().parents[1]/"docs"/"market-command.css"
VOID={"area","base","br","col","embed","hr","img","input","link","meta","param","source","track","wbr"}
class DOMOutline(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack=[];self.ids={};self.duplicates=[];self.errors=[];self.details={}
    def handle_starttag(self,tag,attrs):
        props=dict(attrs);ident=props.get("id")
        if ident:
            if ident in self.ids:self.duplicates.append(ident)
            self.ids[ident]=tuple(x[1] for x in self.stack if x[1])
            self.details[ident]=tuple(x[1] for x in self.stack if x[0]=="details" and x[1])
        if tag not in VOID:self.stack.append((tag,ident,props))
    def handle_startendtag(self,tag,attrs):self.handle_starttag(tag,attrs);self.handle_endtag(tag)
    def handle_endtag(self,tag):
        if tag in VOID:return
        if not self.stack:self.errors.append(("unmatched close",tag));return
        top=self.stack.pop()
        if top[0]!=tag:self.errors.append(("unexpected close",tag,top[0]))
class MarketHomepageLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html=HTML.read_text(encoding="utf-8")
        cls.css=CSS.read_text(encoding="utf-8")
        cls.dom=DOMOutline();cls.dom.feed(cls.html);cls.dom.close()
    def test_tags_and_unique_dom_ids(self):
        self.assertFalse(self.dom.errors,self.dom.errors[:8]);self.assertFalse(self.dom.stack,self.dom.stack[-5:])
        self.assertFalse(self.dom.duplicates,self.dom.duplicates)
    def test_top_buy_decision_is_not_collapsed(self):
        for name in ("marketCommand","commandStatus","commandScore","commandBreadth","commandScoreChange","commandReasons","commandPrimaryLink","revState","nextEntry"):
            self.assertIn(name,self.dom.ids)
            self.assertFalse(self.dom.details[name],name+" should be visible without opening advanced section")
    def test_professional_data_is_kept_in_details_not_deleted(self):
        for ident,container in (("riskScore","marketAdvanced"),("riskLight","marketAdvanced"),("riskWarning","marketAdvanced"),
                                ("idx","marketAdvanced"),("ma5","marketAdvanced"),("ma20","marketAdvanced"),
                                ("txfDay","txfDetails"),("txfNight","txfDetails"),("txfContract","txfDetails"),
                                ("txfWidgetShell","txfLiveChart"),("extreme","reversalDetails"),
                                ("confirm","reversalDetails"),("commandVol","commandAdvanced"),
                                ("commandHigh","commandAdvanced"),("commandAi","commandAdvanced"),
                                ("buyRows","secondaryInsights"),("sellRows","secondaryInsights"),("themeRows","secondaryInsights")):
            self.assertIn(ident,self.dom.ids)
            self.assertIn(container,self.dom.details[ident],ident+" must be inside "+container)
    def test_no_autoexpanded_expert_panels(self):
        for item in ("marketAdvanced","txfDetails","txfLiveChart","reversalDetails","commandAdvanced","secondaryInsights"):
            self.assertIn(item,self.dom.ids)
        self.assertNotIn('id="marketAdvanced" open',self.html)
        self.assertNotIn('id="txfDetails" open',self.html)
    def test_single_upstream_entry_is_in_top_navigation_only(self):
        from html.parser import HTMLParser
        class NavigationLinks(HTMLParser):
            def __init__(self):
                super().__init__();self.stack=[];self.upstream=[]
            def handle_starttag(self,tag,attrs):
                props=dict(attrs);self.stack.append((tag,props))
                if tag=="a" and props.get("href")=="./upstream.html":
                    self.upstream.append(tuple(self.stack))
            def handle_endtag(self,tag):
                if self.stack:
                    self.stack.pop()
        links=NavigationLinks();links.feed(self.html)
        self.assertEqual(len(links.upstream),1,"Home should have exactly one upstream entry")
        self.assertTrue(any(x[0]=="nav" and x[1].get("class")=="site-nav" for x in links.upstream[0]),
                        "Upstream entry must be in the top navigation")
        self.assertIn('>🧩 上游類股</a>',self.html)
        self.assertNotIn('class="upstream-portal"',self.html)
        self.assertNotIn('upstream-industry-links',self.html)
        self.assertNotIn('href="./upstream.html?industry=',self.html)
        self.assertTrue((HTML.parent/"upstream.html").is_file(),"The linked detail page must remain intact")
    def test_unused_home_nav_links_hidden_but_pages_preserved(self):
        for href in ("bottom-top-trader.html","capital-water-backtest.html","margin-short-research.html"):
            expected=f'href="./{href}" hidden>'
            self.assertIn(expected,self.html,href+" should be hidden from the top navigation")
            self.assertTrue((HTML.parent/href).is_file(),href+" page should not be deleted")
        self.assertIn(".site-nav-links>a[hidden]{display:none!important}",self.html)
    def test_github_update_shortcut_is_hidden_but_reload_remains_visible(self):
        self.assertIn('class="btn btn-utility" hidden href="https://github.com/jacky-168168/Tradingview-testing/actions/workflows/tw-stock-dashboard.yml"',self.html)
        self.assertIn('.site-head-utility>a[hidden]{display:none!important}',self.html)
        self.assertIn('id="reload" class="btn btn-utility btn-reload"',self.html)
    def test_layout_responsive_and_accessible(self):
        for marker in ("market-brief-grid","brief-card","cmd-metrics","advanced-content","@media(max-width:650px)","@media(max-width:980px)"):
            self.assertIn(marker,self.css)
        self.assertIn('role="status"',self.html)
        self.assertIn('aria-live="polite"',self.html)
        self.assertNotIn('<div class="grid-top">',self.html)
if __name__=="__main__":unittest.main(verbosity=2)
