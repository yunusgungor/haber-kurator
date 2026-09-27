#!/usr/bin/env python3
"""Bench: test HTTP conditional GET support of RSS feed servers.

For each feed:
  1. Send normal GET, capture ETag + Last-Modified from response headers.
  2. Resend with If-None-Match + If-Modified-Since.
  3. Record 304 Not Modified (bandwidth saving) vs full 200 body.

Output format (required by the gate):
    conditional_get_success_rate=0.xx (n/m)
"""
import urllib.request
import time

FEEDS = [
    ("BBC",          "https://feeds.bbci.co.uk/news/rss.xml"),
    ("Guardian",     "https://www.theguardian.com/world/rss"),
    ("NYT",          "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    ("Al Jazeera",   "https://www.aljazeera.com/xml/rss/all.xml"),
    ("NPR",          "https://feeds.npr.org/1001/rss.xml"),
    ("Medyascope",   "https://medyascope.tv/feed/"),
    ("Diken",        "https://www.diken.com.tr/feed/"),
    ("Bloomberg HT", "https://www.bloomberght.com/rss"),
    ("CNN",          "https://edition.cnn.com/services/rss/"),
    ("Wired",        "https://www.wired.com/feed/rss"),
    ("TechReview",   "https://www.technologyreview.com/feed/"),
    ("BBC Turkce",   "https://feeds.bbci.co.uk/turkce/rss.xml"),
    ("AA",           "https://www.aa.com.tr/tr/rss/default?cat=guncel"),
    ("WSJ",          "https://feeds.a.dj.com/rss/RSSWSJD.xml"),
    ("Bloomberg",    "https://feeds.bloomberg.com/markets/news.rss"),
]


def test_conditional_get(name, url):
    req = urllib.request.Request(url, headers={"User-Agent": "Haber-Kurator-E003/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        etag = resp.headers.get("ETag")
        last_modified = resp.headers.get("Last-Modified")
        body1_size = len(resp.read())

    if not etag and not last_modified:
        print(f"  [SKIP] {name}: no ETag/Last-Modified (unsupported)")
        return None

    # Second request with conditional headers
    req2 = urllib.request.Request(url, headers={
        "User-Agent": "Haber-Kurator-E003/1.0",
    })
    if etag:
        req2.add_header("If-None-Match", etag)
    if last_modified:
        req2.add_header("If-Modified-Since", last_modified)

    try:
        with urllib.request.urlopen(req2, timeout=15) as resp2:
            body2_size = len(resp2.read())
            print(f"  [FAIL] {name}: 200 (full body) — ETag={etag or 'none'}, LM={last_modified or 'none'}")
            return False
    except urllib.error.HTTPError as e:
        if e.code == 304:
            print(f"  [PASS] {name}: 304 Not Modified — saving ~{body1_size} bytes")
            return True
        print(f"  [FAIL] {name}: HTTP {e.code}")
        return False


ok = 0
total = 0
for name, url in FEEDS:
    print(f"  [{name}]")
    try:
        result = test_conditional_get(name, url)
        if result is not None:
            ok += int(result)
            total += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")

rate = ok / total if total else 0.0
print(f"\nconditional_get_success_rate={rate:.2f} ({ok}/{total})")
