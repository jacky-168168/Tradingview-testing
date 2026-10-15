"""Content-hash homepage risk JS/CSS URLs in EVERY GitHub Pages deployment.

Prevents browser cache serving an earlier dashboard model even when index.html
and the repository have been updated.  This changes artifact HTML only.
"""
from __future__ import annotations
import argparse
import hashlib
import os
from pathlib import Path
import re
import sys
import time
import urllib.request

DOCS = Path(__file__).resolve().parents[1] / "docs"
ASSETS = ("market-command.js", "market-sentiment.js", "market-command.css", "market-sentiment.css")

def hash_asset(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]

def stamp(html: str, contents: dict[str, bytes]) -> str:
    for name in ASSETS:
        if name not in contents:
            raise ValueError("missing homepage asset " + name)
        pattern = re.compile(r'(?P<head>(?:src|href)="\./' + re.escape(name) + r')(?:\?v=[^"]*)?(?P<tail>")')
        expected = hash_asset(contents[name])
        html, count = pattern.subn(lambda m: m.group("head") + "?v=" + expected + m.group("tail"), html)
        if count != 1:
            raise ValueError(f"Expected one homepage link to {name}, found {count}")
    return html

def expected() -> dict[str, bytes]:
    return {name: (DOCS / name).read_bytes() for name in ASSETS}

def prepare() -> None:
    home = DOCS / "index.html"
    current = home.read_text(encoding="utf-8")
    assets = expected()
    result = stamp(current, assets)
    if current != result:
        home.write_text(result, encoding="utf-8")
    # Both deploy workflows run this AFTER any JSON git push and BEFORE upload.
    assert stamp(result, assets) == result
    for name in ASSETS:
        print(f"PAGE_ASSET {name}?v={hash_asset(assets[name])}", flush=True)
    print("PASS artifact references content-identical market JS/CSS hashes", flush=True)

def verify_live(base: str, attempts: int = 10) -> None:
    if not base.startswith("https://"):
        raise ValueError("Expected HTTPS GitHub Pages deployment URL")
    assets = expected()
    token = os.environ.get("GITHUB_SHA", "")[:16] or str(int(time.time()))
    prefix = base.rstrip("/") + "/"
    errors = []
    for attempt in range(1, attempts + 1):
        try:
            req = urllib.request.Request(prefix + "index.html?asset_check=" + token, headers={"User-Agent": "tw-stock-live-deployment-audit/1.0"})
            with urllib.request.urlopen(req, timeout=18) as res:
                html = res.read().decode("utf-8")
            if stamp(html, assets) != html:
                raise RuntimeError("Live HTML still points at stale JS/CSS hashes")
            for name in ("market-command.js", "market-sentiment.js"):
                url = prefix + name + "?v=" + hash_asset(assets[name])
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "tw-stock-live-deployment-audit/1.0"}), timeout=18) as res:
                    live = res.read()
                if live != assets[name]:
                    raise RuntimeError(f"Deployed {name} differs from current GitHub commit")
            if "label:\"極度偏空\"" not in assets["market-sentiment.js"].decode() or "label:\"偏空觀察\"" not in assets["market-sentiment.js"].decode():
                raise RuntimeError("Expected bearish labels not present in shipped JavaScript")
            print(f"PASS public Pages HTML and JS exact bytes match current deployment (attempt {attempt})", flush=True)
            return
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            print(f"PAGE_SYNC retry {attempt}/{attempts}: {errors[-1]}", flush=True)
            if attempt < attempts:
                time.sleep(10)
    raise RuntimeError("Published site differs from deployed artifacts: " + errors[-1])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify-live"))
    parser.add_argument("page_url", nargs="?")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare()
    else:
        if not args.page_url:
            parser.error("verify-live requires URL")
        verify_live(args.page_url)
