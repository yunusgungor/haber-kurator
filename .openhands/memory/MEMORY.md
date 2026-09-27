# Haber-Kuratör — Project Memory

## Quick Commands
- **Run tests:** `cd /root/PROJECTS/haber-kurator && python3 -m pytest tests/test_haber_kurator_core.py --rootdir=tests -v`
- **Import core:** `cd /root/PROJECTS/haber-kurator && python3 -c "from haber_kurator_core import HaberKuratorCore, STATE_LIFECYCLE, STATE_TRANSITIONS, CONFIG, NEWS_SOURCES"`

## State Machine
- 8 states: captured → fact_checking → cross_verified → published → correction_needed → corrected → retracted → archived
- `STATE_TRANSITIONS` dict maps each state to allowed next states; validated by `update_state()`
- No external-state leaks (feedback_72h/learned removed)

## Key Architecture Decisions
- `_scan_rss_signals()` delegates to `_fetch_rss_feed()` — no duplicate RSS XML parser
- `CONFIG` is minimal: only `version`, `min_verification_level`, `rss_timeout`, `rss_delay`
- GBrain integration is a stub (never enabled in practice)
- Tests use `--rootdir=tests` to avoid `__init__.py` relative-import conflict

## Source Health
- 33 active RSS feeds, 4 known-broken Turkish sources (T24, Medyascope, Diken — 403; DW Türkçe — RSS kapandı)
- `gazete_duvar` removed from NEWS_SOURCES (site kapandı 2025-03-12)
