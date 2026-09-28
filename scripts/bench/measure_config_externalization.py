"""Measure E-018: config_externalized — env vars override CONFIG dict."""
import sys
sys.path.insert(0, "/root/PROJECTS/haber-kurator")
import os

# Set overrides BEFORE import
os.environ["HABER_RSS_TIMEOUT"] = "10"
os.environ["HABER_NEWS_MAX_AGE_HOURS"] = "24"
os.environ["HABER_MIN_VERIFICATION_LEVEL"] = "2"

from haber_kurator_core import CONFIG

checks = [
    ("rss_timeout", CONFIG["rss_timeout"], 10),
    ("news_max_age_hours", CONFIG["news_max_age_hours"], 24),
    ("min_verification_level", CONFIG["min_verification_level"], 2),
]

all_pass = True
for key, got, expected in checks:
    ok = got == expected
    status = "✅" if ok else "❌"
    print(f"  {status} {key}={got} (expected {expected})")
    if not ok:
        all_pass = False

if all_pass:
    print("\nmetric_config_externalized_score=1.00 (1/1)")
    sys.exit(0)
else:
    print("\nmetric_config_externalized_score=0.00 (0/1)")
    sys.exit(1)
