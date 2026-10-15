"""Tests that a new JS/CSS byte version always gets a new Pages URL."""
import importlib.util
from pathlib import Path
import unittest

SOURCE=Path(__file__).resolve().parents[1]/"src"/"homepage_asset_versions.py"
spec=importlib.util.spec_from_file_location("homepage_asset_versions", SOURCE)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class CacheVersionTests(unittest.TestCase):
    def setUp(self):
        self.current={name: (mod.DOCS/name).read_bytes() for name in mod.ASSETS}
        self.html=(mod.DOCS/"index.html").read_text(encoding="utf-8")
    def test_all_four_risk_assets_get_content_based_versions(self):
        out=mod.stamp(self.html,self.current)
        for name in mod.ASSETS:
            self.assertIn("./"+name+"?v="+mod.hash_asset(self.current[name]),out)
        self.assertEqual(out,mod.stamp(out,self.current))
    def test_any_asset_change_automatically_invalidates_cache(self):
        old=mod.stamp(self.html,self.current)
        for name in mod.ASSETS:
            changed={**self.current,name:self.current[name]+b"\nversion test"}
            new=mod.stamp(old,changed)
            self.assertNotEqual(old,new)
            self.assertIn("./"+name+"?v="+mod.hash_asset(changed[name]),new)
    def test_fails_closed_for_missing_links_or_assets(self):
        with self.assertRaises(ValueError):mod.stamp(self.html.replace("./market-sentiment.js","./removed.js"),self.current)
        with self.assertRaises(ValueError):mod.stamp(self.html,{k:v for k,v in self.current.items() if k!="market-sentiment.js"})
    def test_new_bearish_names_are_in_actual_shipped_source(self):
        s=self.current["market-sentiment.js"].decode("utf-8")
        self.assertIn('label:"極度偏空"',s)
        self.assertIn('label:"偏空觀察"',s)
        self.assertNotIn('label:"極高風險"',s)
        self.assertNotIn('label:"風險偏高"',s)
if __name__=="__main__":
    unittest.main(verbosity=2)
