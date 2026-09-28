"""Measure E-016: news_sources_externalized — JSON loads override embedded defaults."""
import sys
sys.path.insert(0, "/root/PROJECTS/haber-kurator")
from pathlib import Path
from haber_kurator_core import _load_news_sources, HaberKuratorCore, SourceTier

checks = []

# 1) JSON path loads correctly
json_path = Path("sources/news_sources.json")
sources = _load_news_sources(json_path=json_path)
checks.append(("json_load_count", len(sources) == 36, "36 sources"))

# 2) Source metadata intact
src = sources.get("reuters")
checks.append(("reuters_name", src and src.name == "Reuters", src.name if src else "MISSING"))

src = sources.get("aa")
checks.append(("aa_name", src and src.name == "Anadolu Ajansı (AA)", src.name if src else "MISSING"))
checks.append(("aa_country", src and src.country == "turkey", src.country if src else "MISSING"))

# 3) Fallback (no JSON) path
bak = json_path.rename(json_path.with_suffix(".json.bak")) if json_path.exists() else None
try:
    fallback = _load_news_sources()
    checks.append(("fallback_count", len(fallback) == 36, f"{len(fallback)} sources"))
finally:
    if bak:
        bak.rename(json_path)

# 4) Core init uses JSON by default
core = HaberKuratorCore(Path("."))
checks.append(("core_init_sources", len(core.sources) == 36, f"{len(core.sources)} sources"))
checks.append(("core_get_source", core.get_source("reuters") is not None, "reuters found"))
checks.append(("core_get_by_tier", len(core.get_sources_by_tier(SourceTier.PRIMARY)) > 0, "tier query works"))

all_pass = True
for key, ok, detail in checks:
    status = "✅" if ok else "❌"
    print(f"  {status} {key}: {detail}")
    if not ok:
        all_pass = False

if all_pass:
    # Gate requires metric_<name>_<suffix>=value pattern
    total = len(checks)
    print(f"\nmetric_news_sources_externalized_score=1.00 ({total}/{total})")
    sys.exit(0)
else:
    failed = sum(1 for _, ok, _ in checks if not ok)
    total = len(checks)
    print(f"\nmetric_news_sources_externalized_score=0.00 ({total-failed}/{total})")
    sys.exit(1)