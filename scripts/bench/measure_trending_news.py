"""Measure E-010: trending_primary_ratio for --trending --category technology."""
import sys
sys.path.insert(0, "/root/PROJECTS/haber-kurator")
from pathlib import Path
from haber_kurator_core import HaberKuratorCore

core = HaberKuratorCore(Path.cwd())
items = core.fetch_all_news("news", trending=True)
clusters = core.cluster_stories(items)

scored = [(c.get("source_count", 0), c) for c in sorted(clusters, key=lambda x: x.get("source_count", 0), reverse=True)]
scored.sort(key=lambda x: x[0], reverse=True)
top5 = scored[:5]
total = len(top5)
primary_count = 0

lines = ["=== TOP 5 TRENDING CLUSTERS ==="]
for i, (src_count, cl) in enumerate(top5, 1):
    tiers = set(it.source_tier.name for it in cl["items"])
    has_primary = any(it.source_tier.value == 0 for it in cl["items"])
    if has_primary:
        primary_count += 1
    pnames = sorted(set(it.source_name for it in cl["items"] if it.source_tier.value == 0))
    lines.append(f"  {i}. [{src_count} kaynak] {cl['story_title'][:70]}")
    lines.append(f"     Tiers: {tiers} | PRIMARY: {pnames[:3]} | HasPrimary: {has_primary}")

lines.append("")
ratio = primary_count / total if total > 0 else 0
lines.append(f"metric_trending_primary_score={ratio:.2f} ({primary_count}/{total})")
print("\n".join(lines))