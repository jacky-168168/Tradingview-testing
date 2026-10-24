"""Hard allowlist for automatically generated Codex patches; no trading logic."""
from __future__ import annotations
import re,subprocess,sys
ALLOWED_EXACT={
 "tw-stock-dashboard/src/market_major_events.py",
 "tw-stock-dashboard/docs/market-events.js",
}
def allowed(path):
 if path in ALLOWED_EXACT:return True
 if re.fullmatch(r"tw-stock-dashboard/tests/test_[A-Za-z0-9_-]+\.(py|cjs|js)",path):return True
 if re.fullmatch(r"\.github/monitor/test_[A-Za-z0-9_-]+\.py",path):return True
 return False
def check(paths):
 bad=[path for path in paths if not allowed(path) or path.startswith("/") or ".." in path.split("/")]
 if bad:raise ValueError("AI patch changed protected/unreviewed paths: "+", ".join(bad))
 if not paths:raise ValueError("AI patch is empty")
 return True
def main():
 subprocess.run(["git","diff","--check"],check=True)
 raw=subprocess.check_output(["git","diff","--name-only","--diff-filter=ACMR"],text=True).splitlines()
 deleted=subprocess.check_output(["git","diff","--name-only","--diff-filter=D"],text=True).splitlines()
 if deleted:raise ValueError("AI cannot delete repository files: "+", ".join(deleted))
 check(raw)
 print("SAFE_AI_PATCH",len(raw),"files")
if __name__=="__main__":main()
