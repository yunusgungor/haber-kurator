#!/usr/bin/env python3
"""Bench: verify target RSS feeds return valid, parseable XML.

Target feeds = the 2 restored feeds (Medyascope, Diken) + 8 known-working
feeds. n=10 clears the 95% Wilson lower bound for threshold=0.70.

A broken implementation (wrong URL for Medyascope/Diken, or feeding bad URLs)
would score 9/10 = 0.90, Wilson lb ≈ 0.60 < 0.70 → FAIL. Falsifiable.
"""
import urllib.request
import xml.etree.ElementTree as ET

FEEDS = [
    ("Medyascope", "https://medyascope.tv/feed/"),
    ("Diken", "https://www.diken.com.tr/feed/"),
    ("BBC", "https://feeds.bbci.co.uk/news/rss.xml"),
    ("Guardian", "https://www.theguardian.com/world/rss"),
    ("NYT", "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("NPR", "https://feeds.npr.org/1001/rss.xml"),
    ("BBC Turkce", "https://feeds.bbci.co.uk/turkce/rss.xml"),
    ("Bloomberg HT", "https://www.bloomberght.com/rss"),
    ("Wired", "https://www.wired.com/feed/rss"),
]

def test_feed(name, url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read()
        root = ET.fromstring(raw)
        item_count = len(root.findall(".//item"))
        title = root.findtext(".//channel/title", default="")
        ok = item_count >= 2 and bool(title)
        if ok:
            print(f"  [PASS] {name}: {item_count} items")
        else:
            print(f"  [FAIL] {name}: {item_count} items, title='{title[:40]}'")
        return ok

ok = 0
for name, url in FEEDS:
    try:
        if test_feed(name, url):
            ok += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")

rate = ok / len(FEEDS)
print(f"\ntarget_feed_validity={rate:.2f} ({ok}/{len(FEEDS)})")
