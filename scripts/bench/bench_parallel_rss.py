#!/usr/bin/env python3
"""Bench: parallel RSS speedup — batch measurement.

3 batches, each: run all feeds sequentially (median with delay), then
all feeds in parallel (median). Speedup = seq_median / par_median.
Gate: parallel_speedup_ok_rate = fraction of batches where speedup >= 3.0.
"""
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

FEEDS = [
    "https://feeds.bbci.co.uk/news/rss.xml",
    "https://www.theguardian.com/world/rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://feeds.npr.org/1001/rss.xml",
    "https://www.wired.com/feed/rss",
    "https://www.technologyreview.com/feed/",
    "https://feeds.bbci.co.uk/turkce/rss.xml",
    "https://medyascope.tv/feed/",
    "https://www.diken.com.tr/feed/",
    "https://www.bloomberght.com/rss",
    "https://edition.cnn.com/services/rss/",
    "https://www.sciencedaily.com/rss/all.xml",
]

RSS_DELAY = 0.5
BATCHES = 6
UA = "Haber-Kurator-Bench-E004/1.0"
TIMEOUT = 8


def fetch_one(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def run_sequential(feeds):
    total = 0.0
    for url in feeds:
        t0 = time.time()
        try:
            fetch_one(url)
        except Exception:
            pass
        total += time.time() - t0
        time.sleep(RSS_DELAY)
    return total


def run_parallel(feeds, workers=8):
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_one, url): url for url in feeds}
        for f in as_completed(futures):
            try:
                f.result()
            except Exception:
                pass
    return time.time() - t0


oks = 0
for batch in range(BATCHES):
    seq_times = [run_sequential(FEEDS) for _ in range(3)]
    seq_med = statistics.median(seq_times)
    par_times = [run_parallel(FEEDS, workers=8) for _ in range(3)]
    par_med = statistics.median(par_times)
    speedup = seq_med / par_med if par_med > 0 else 0.0
    ok = speedup >= 3.0
    if ok:
        oks += 1
    print(f"  [batch-{batch+1}] seq_med={seq_med:.2f}s  par_med={par_med:.2f}s  speedup={speedup:.2f}x  {'OK' if ok else 'FAIL'}")

rate = oks / BATCHES if BATCHES > 0 else 0.0
print(f"\nparallel_speedup_ok_rate={rate:.2f} ({oks}/{BATCHES})")
