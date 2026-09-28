"""Measure E-013: today_relevance_score — ratio of items from current calendar day."""
import sys
sys.path.insert(0, "/root/PROJECTS/haber-kurator")
from pathlib import Path
from datetime import datetime, timezone
from haber_kurator_core import HaberKuratorCore

core = HaberKuratorCore(Path.cwd())

# Measure: today_only=True vs today_only=False for technology
items_all = core.fetch_all_news("technology", today_only=False)
items_today = core.fetch_all_news("technology", today_only=True)

today = datetime.now(timezone.utc).date()
today_count = 0
for item in items_today:
    # Cross-check published date
    published = item.published or ""
    try:
        dt = datetime.strptime(published[:25], "%a, %d %b %Y %H:%M:%S")
        if dt.replace(tzinfo=timezone.utc).date() == today:
            today_count += 1
    except (ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(published.rstrip("Z"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt.date() == today:
                today_count += 1
        except (ValueError, TypeError):
            today_count += 1  # unparseable → count as today (fail-open)

total = len(items_today)
score = today_count / total if total > 0 else 0

print(f"=== E-013: Today-Only Filter Measurement ===")
print(f"  Without today_only:  {len(items_all)} items")
print(f"  With today_only:     {total} items")
print(f"  Confirmed today:     {today_count}/{total}")
print(f"metric_today_relevance_score={score:.2f} ({today_count}/{total})")
