"""One-time script: serialize current NEWS_SOURCES to JSON."""
import sys
import json
sys.path.insert(0, "/root/PROJECTS/haber-kurator")
from pathlib import Path
from haber_kurator_core import NEWS_SOURCES, SourceTier

def source_to_dict(key, src):
    return {
        "key": key,
        "name": src.name,
        "base_url": src.base_url,
        "category": src.category,
        "tier": src.tier.name,  # SourceTier enum name
        "rss_feeds": list(src.rss_feeds) if src.rss_feeds else [],
        "language": src.language,
        "country": src.country,
        "notes": src.notes,
    }

sources_list = [source_to_dict(k, v) for k, v in NEWS_SOURCES.items()]

out_path = Path("/root/PROJECTS/haber-kurator/sources/news_sources.json")
out_path.parent.mkdir(parents=True, exist_ok=True)

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(sources_list, f, ensure_ascii=False, indent=2)

print(f"✅ Exported {len(sources_list)} sources to {out_path}")
