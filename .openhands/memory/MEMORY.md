# Haber-Kuratör — Project Memory

## Quick Commands
- **Run tests:** `cd /root/PROJECTS/haber-kurator && python3 -m pytest tests/test_haber_kurator_core.py --rootdir=tests -v`
- **Import core:** `cd /root/PROJECTS/haber-kurator && python3 -c "from haber_kurator_core import HaberKuratorCore, STATE_LIFECYCLE, STATE_TRANSITIONS, CONFIG, _load_news_sources"`
- **Run coverage:** `cd /root/PROJECTS/haber-kurator && rm -rf coverage_report && python3 scripts/bench/measure_coverage.py`
- **Trending publish:** `hermes haber auto-publish --trending --category news --limit 5`
- **Today's news:** `hermes haber auto-publish --today --category technology --limit 5`

## Trending Feature (E-012 APPROVED)
- `--trending` flag: sorts by cross-source coverage (most-covered story first)
- 24h recency (vs 48h normal)
- News category avg 5.4 sources/cluster (validated E-012)
- Technology category has near-zero multi-source overlap (E-010)
- PRIMARY-tier proxy was wrong metric — real value is source_count itself
- CLI: `hermes haber auto-publish --trending --category news --limit 5`

## Today-Only Filter (E-013 APPROVED)
- `--today` flag: calendar-day filter (not rolling 24/48h)
- `_is_today()` parses RFC 2822, ISO-8601, date prefix
- Validated: 4/4 items from current calendar day (1.00 score)
- CLI: `hermes haber auto-publish --today --category technology --limit 5`

## State Machine
- 8 states: captured → fact_checking → cross_verified → published → correction_needed → corrected → retracted → archived
- `STATE_TRANSITIONS` dict maps each state to allowed next states; validated by `update_state()`
- No external-state leaks (feedback_72h/learned removed)

## Key Architecture Decisions
- `_scan_rss_signals()` delegates to `_fetch_rss_feed()` — no duplicate RSS XML parser
- GBrain integration is a stub (never enabled in practice)
- Tests use `--rootdir=tests` to avoid `__init__.py` relative-import conflict

## Externalization (E-016, E-018 APPROVED)
- **CONFIG** → env vars: `HABER_RSS_TIMEOUT`, `HABER_RSS_MAX_WORKERS`, `HABER_NEWS_MAX_AGE_HOURS`, etc.
  - `.env.example` has both Memos and Haber-Kuratör sections
  - `load_dotenv()` optional (graceful if python-dotenv missing)
  - `cache_enabled` config key exposed (#981)
- **36 NEWS_SOURCES** → `sources/news_sources.json`
  - JSON loader: `_load_news_sources()` (tries JSON path → embedded fallback)
  - Path: explicit arg > `$HABER_SOURCES_JSON` > `sources/news_sources.json` > embedded
  - One-time export: `scripts/export_sources_to_json.py`

## Coverage Infrastructure (E-015 APPROVED)
- `pytest-cov` installed via uv: `pytest --cov=haber_kurator_core --cov=writer_agent --cov-report=html:coverage_report`
- Current: core 54%, writer 64%, total 56%
- HTML report: `coverage_report/index.html` (gitignored)
- Measurement: `scripts/bench/measure_coverage.py`

## Source Health
- 36 active RSS feeds (now externalized to sources/news_sources.json)
- 4 known-broken Turkish sources (T24, Medyascope, Diken — 403; DW Türkçe — RSS kapandı)
- `gazete_duvar` removed from NEWS_SOURCES (site kapandı 2025-03-12)
