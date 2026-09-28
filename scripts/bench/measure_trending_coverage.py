"""Measure E-012: trending_coverage_score — average source_count in top 5 trending clusters."""
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

lines = ["=== TOP 5 TRENDING CLUSTERS (news) ==="]
src_counts = []
for i, (src_count, cl) in enumerate(top5, 1):
    src_counts.append(src_count)
    tiers = set(it.source_tier.name for it in cl["items"])
    lines.append(f"  {i}. [{src_count} kaynak] {cl['story_title'][:70]}")
    lines.append(f"     Tiers: {tiers}")

avg = sum(src_counts) / len(src_counts) if src_counts else 0
lines.append("")
lines.append(f"metric_trending_coverage_score={avg:.1f} (5/5)")
print("\n".join(lines))
