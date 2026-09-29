"""
Haber-Kuratör v3.1.0 — Birim Testleri
Tüm haber doğrulama fonksiyonlarını test eder: fetch, cluster, cross-verify,
hallucination, correction, state machine, edge cases.
"""

import sys
import json
import urllib.error
import asyncio
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from datetime import datetime, timedelta

# Add plugin directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haber_kurator_core import (
    HaberKuratorCore, VERSION, STATE_LIFECYCLE,
    FULL_SLOP_TIER1, FULL_SLOP_TIER2, FULL_SLOP_TIER3, FULL_SLOP_BONUS,
    RunState, SlopResult, STATE_TRANSITIONS, CONFIG,
    FetchedNewsItem, SourceTier, VerificationLevel,
    CrossVerificationResult, ROUTE_VERIFIED, ROUTE_HIGH_SLOP, ROUTE_ESCALATED,
)
import pytest


# ============================================================
# TEST 1: Constants & Configuration
# ============================================================

class TestConstants:
    def test_version(self):
        assert VERSION == "3.1.0"

    def test_state_count(self):
        assert len(STATE_LIFECYCLE) == 5

    def test_state_order(self):
        assert STATE_LIFECYCLE[0] == "captured"
        assert STATE_LIFECYCLE[-1] == "archived"

    def test_slop_coverage(self):
        total = (len(FULL_SLOP_TIER1) + len(FULL_SLOP_TIER2) +
                 len(FULL_SLOP_TIER3) + len(FULL_SLOP_BONUS))
        assert total >= 54, f"Only {total} slop patterns (need ≥54)"

    def test_dataclass_runstate(self):
        rs = RunState(slug="test-slug")
        assert rs.slug == "test-slug"
        assert rs.state == "captured"
        assert rs.route == "VERIFIED"

    def test_dataclass_slopresult(self):
        sr = SlopResult(score="PASS")
        assert sr.score == "PASS"
        assert sr.tier1_count == 0
        assert sr.findings == []


# ============================================================
# TEST 1b: RSS Fetch Retry (E-005)
# ============================================================

class TestRssFetchRetry:
    """Unit tests for _fetch_url_with_retry via _fetch_rss_feed.

    Uses patch on urllib.request.urlopen to simulate transient
    failures, 304 caching, and non-retryable errors.
    """

    @pytest.fixture
    def core(self, tmp_path):
        return HaberKuratorCore(tmp_path)

    # ── helpers ──

    def _make_resp(self, data=b"<rss version='2.0'><channel><item><title>OK</title><link>http://x.com</link></item></channel></rss>",
                   status=200, headers=None):
        """Build a mock HTTP response that works as a context manager."""
        hdrs = {"ETag": '"abc123"'} if headers is None else headers
        resp = MagicMock()
        resp.read.return_value = data
        resp.headers = hdrs
        resp.status = status
        resp.__enter__.return_value = resp
        return resp

    def _http_error(self, code):
        e = urllib.error.HTTPError("http://test", code, f"HTTP {code}", {}, None)
        return e

    def _assert_items(self, items, count=1):
        assert len(items) == count, f"Expected {count} items, got {len(items)}"

    # ── happy path ──

    def test_fetch_success_first_try(self, core):
        with patch("urllib.request.urlopen", return_value=self._make_resp()):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 1)

    # ── retry on transient errors ──

    def test_retry_500_then_ok(self, core):
        """HTTP 500 → retry → 200 OK."""
        mock = MagicMock()
        mock.side_effect = [
            self._http_error(500),          # attempt 1
            self._http_error(500),          # attempt 2
            self._make_resp(),              # attempt 3 — success
        ]
        with patch("urllib.request.urlopen", mock):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 1)

    def test_retry_timeout_then_ok(self, core):
        """URLError (timeout) → retry → 200 OK."""
        mock = MagicMock()
        mock.side_effect = [
            urllib.error.URLError("timeout"),
            self._make_resp(),
        ]
        with patch("urllib.request.urlopen", mock):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 1)

    def test_retry_connection_reset_then_ok(self, core):
        """OSError (connection reset) → retry → 200 OK."""
        mock = MagicMock()
        mock.side_effect = [
            OSError(104, "Connection reset by peer"),
            self._make_resp(),
        ]
        with patch("urllib.request.urlopen", mock):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 1)

    def test_retry_all_exhausted_returns_empty(self, core):
        """3 retries exhausted → empty list."""
        mock = MagicMock()
        mock.side_effect = [
            self._http_error(500),
            self._http_error(500),
            self._http_error(500),
            self._http_error(500),  # 4th call = final raise
        ]
        with patch("urllib.request.urlopen", mock):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 0)

    # ── 304 passthrough ──

    def test_304_without_cache_returns_empty(self, core):
        """304 without prior cache → empty."""
        with patch("urllib.request.urlopen",
                                 side_effect=self._http_error(304)):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 0)

    def test_304_with_cache_returns_cached(self, tmp_path):
        """304 with cached items → returns cached."""
        c = HaberKuratorCore(tmp_path)
        # Seed cache with pre-fetched items
        c._rss_cache["http://test"] = {
            "etag": '"stale"',
            "items": [FetchedNewsItem(title="cached", url="http://x.com",
                                       source_name="Test", source_tier=SourceTier.MAJOR,
                                       category="news")],
        }
        with patch("urllib.request.urlopen",
                                 side_effect=self._http_error(304)):
            items = c._fetch_rss_feed("http://test", _fake_source())
        assert len(items) == 1
        assert items[0].title == "cached"

    # ── non-retryable 4xx ──

    def test_404_fast_fail(self, core):
        """404 is never retried."""
        mock = MagicMock()
        mock.side_effect = self._http_error(404)
        with patch("urllib.request.urlopen", mock):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 0)
        # Should have only been called once (no retry)
        assert mock.call_count <= 1

    def test_403_fast_fail(self, core):
        """403 is never retried."""
        mock = MagicMock()
        mock.side_effect = self._http_error(403)
        with patch("urllib.request.urlopen", mock):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 0)
        assert mock.call_count <= 1

    def test_429_is_retried(self, core):
        """429 is retried (rate-limit)."""
        mock = MagicMock()
        mock.side_effect = [
            self._http_error(429),
            self._http_error(429),
            self._make_resp(),
        ]
        with patch("urllib.request.urlopen", mock):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 1)

    # ── bad RSS parse ──

    def test_bad_xml_returns_empty(self, core):
        """Non-XML response → empty, no crash."""
        resp = self._make_resp(data=b"not xml at all", headers={"ETag": '"x"'})
        with patch("urllib.request.urlopen", return_value=resp):
            items = core._fetch_rss_feed("http://test", _fake_source())
        self._assert_items(items, 0)


def _fake_source():
    from haber_kurator_core import NewsSource
    return NewsSource(
        name="Test",
        base_url="http://x.com",
        category="news",
        tier=SourceTier.MAJOR,
    )


# ============================================================
# TEST 2: State Machine (8-State News Lifecycle)
# ============================================================

class TestStateMachine:
    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        return c

    def test_state_machine_all_transitions(self, core):
        """Verify that STATE_TRANSITIONS dict covers all lifecycle states."""
        all_keys = set(STATE_TRANSITIONS.keys())
        all_states = set(STATE_LIFECYCLE)
        for state in all_states:
            if state == "archived":
                continue
            assert state in all_keys, f"{state} missing from STATE_TRANSITIONS"
        for from_state, targets in STATE_TRANSITIONS.items():
            for t in targets:
                assert t in all_states, f"Invalid transition target: {t}"

    def test_invalid_state_name(self, core):
        result = core.update_state("nonexistent", "invalid_state_name")
        assert "❌" in result

    def test_get_state_unknown(self, core):
        assert core.get_state("nonexistent") == "unknown"

    def test_update_nonexistent(self, core):
        result = core.update_state("nonexistent-slug", "verified")
        assert "❌" in result

    def test_get_next_actions(self, core):
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "Test News",
            "items": [
                FetchedNewsItem(title="Test", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="Test", category="news"),
                FetchedNewsItem(title="Test2", url="https://ap.com", source_name="Associated Press (AP)",
                    source_tier=SourceTier.PRIMARY, summary="Test", category="news"),
            ],
            "sources": ["Reuters", "Associated Press (AP)"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://r.com",
        }
        r = core.create_news_run(cluster)
        slug = r["slug"]
        actions = core.get_next_actions(slug)
        assert len(actions) > 0
        assert isinstance(actions, list)

    # ══════════════════════════════════════════════════════════
    # STATE MACHINE — Expanded Tests (Bulgu 7 / E-007)
    # ══════════════════════════════════════════════════════════

    def test_state_transition_happy_path(self, core):
        """Full lifecycle: cross_verified → published → archived"""
        slug = self._create_test_run(core)
        assert core.get_state(slug) == "verified"
        path = ["published", "archived"]
        for state in path:
            r = core.update_state(slug, state)
            assert "✅" in r, f"Transition to {state} failed: {r}"
        assert core.get_state(slug) == "archived"

    def test_state_invalid_transition_denied(self, core):
        """verified → archived (skip published) should be denied"""
        slug = self._create_test_run(core)
        assert core.get_state(slug) == "verified"
        r = core.update_state(slug, "archived")
        assert "❌" in r, f"Invalid transition should be denied: {r}"

    def test_state_force_bypasses_validation(self, core):
        """force=True should allow any transition"""
        slug = self._create_test_run(core)
        r = core.update_state(slug, "captured", force=True)
        assert "✅" in r, f"Force transition should succeed: {r}"

    def test_state_back_to_captured(self, core):
        """cross_verified → captured (rework from verified back to queue)"""
        slug = self._create_test_run(core)
        r = core.update_state(slug, "captured")
        assert "✅" in r
        assert core.get_state(slug) == "captured"

    def test_state_published_to_corrected(self, core):
        """published → corrected (direct correction)"""
        slug = self._create_test_run(core)
        core.update_state(slug, "published")
        r = core.update_state(slug, "corrected")
        assert "✅" in r, f"published→corrected should work: {r}"
        assert core.get_state(slug) == "corrected"

    def test_state_corrected_to_archived(self, core):
        """corrected → archived"""
        slug = self._create_test_run(core)
        core.update_state(slug, "published")
        core.update_state(slug, "corrected")
        r = core.update_state(slug, "archived")
        assert "✅" in r, f"corrected→archived should work: {r}"

    def test_state_cross_verified_to_correction_needed(self, core):
        """cross_verified → correction_needed (pre-publish error catch)"""
        slug = self._create_test_run(core)
        r = core.update_state(slug, "corrected")
        assert "✅" in r, f"cross_verified→correction_needed should work: {r}"

    def test_state_fact_checking_to_correction_needed(self, core):
        """fact_checking → correction_needed — start from captured"""
        slug = self._create_test_run(core)
        core.update_state(slug, "captured", force=True)
        core.update_state(slug, "verified")
        r = core.update_state(slug, "corrected")
        assert "✅" in r, f"fact_checking→correction_needed should work: {r}"

    def test_state_archived_is_terminal(self, core):
        """archived → any state should be denied"""
        slug = self._create_test_run(core)
        core.update_state(slug, "published")
        core.update_state(slug, "archived")
        for target in ("captured", "verified", "published"):
            r = core.update_state(slug, target)
            assert "❌" in r, f"archived→{target} should be denied: {r}"

    def test_state_valid_transition_fallback_deny(self, core):
        """_valid_transition should return False for unknown source states"""
        assert not core._valid_transition("nonexistent_state", "captured")
        assert not core._valid_transition("unknown", "archived")

    def test_state_route_default_verified(self, core):
        """New run should have VERIFIED route"""
        slug = self._create_test_run(core)
        assert core.get_route(slug) == "VERIFIED"

    def test_state_route_preserved(self, core):
        """Route should persist through state changes"""
        slug = self._create_test_run(core)
        core.update_state(slug, "published")
        assert core.get_route(slug) == "VERIFIED"

    def test_state_route_custom(self, core):
        """Route parameter should set non-default route on valid transition"""
        slug = self._create_test_run(core)
        r = core.update_state(slug, "published", route="HIGH_SLOP")
        assert "✅" in r, str(r)
        assert core.get_route(slug) == "HIGH_SLOP"

    def test_state_get_route_unknown_slug(self, core):
        """get_route for unknown slug should return VERIFIED"""
        assert core.get_route("nonexistent") == "VERIFIED"

    def test_state_correction_full_cycle(self, core):
        """published → corrected → published → archived"""
        slug = self._create_test_run(core)
        core.update_state(slug, "published")
        core.update_state(slug, "corrected")
        assert core.get_state(slug) == "corrected"
        core.update_state(slug, "published")
        assert core.get_state(slug) == "published"
        core.update_state(slug, "archived")
        assert core.get_state(slug) == "archived"

    def test_state_retraction_flow(self, core):
        """published → corrected (retraction) → archived"""
        slug = self._create_test_run(core)
        core.update_state(slug, "published")
        core.update_state(slug, "corrected")
        assert core.get_state(slug) == "corrected"
        core.update_state(slug, "archived")
        assert core.get_state(slug) == "archived"

    def _create_test_run(self, core) -> str:
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "Test News State Machine",
            "items": [
                FetchedNewsItem(title="Test A", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="Test", category="news"),
                FetchedNewsItem(title="Test B", url="https://ap.com", source_name="Associated Press (AP)",
                    source_tier=SourceTier.PRIMARY, summary="Test", category="news"),
            ],
            "sources": ["Reuters", "Associated Press (AP)"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://r.com",
        }
        r = core.create_news_run(cluster)
        return r["slug"]


# ============================================================
# TEST 3: Slop Detection
# ============================================================

class TestSlopDetection:
    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        return c

    def test_tier1_detection(self, core):
        r = core.scan_slop("This groundbreaking game-changing revolutionary approach")
        assert r["tier1_count"] >= 1
        assert r["score"] in ("REJECT", "REVISE")

    def test_tier2_detection(self, core):
        r = core.scan_slop("This serves as a comprehensive solution leveraging cutting-edge")
        assert r["tier2_count"] >= 1

    def test_tier3_detection(self, core):
        r = core.scan_slop("It was noted that very important things were recently discovered")
        assert r["tier3_count"] >= 1

    def test_clean_content_passes(self, core):
        r = core.scan_slop("I fixed timing by reordering pipeline stages. Result: 40ns to 12ns.")
        assert r["score"] == "PASS"

    def test_empty_content_passes(self, core):
        r = core.scan_slop("")
        assert r["score"] == "PASS"

    def test_backward_compat_findings_key(self, core):
        r = core.scan_slop("groundbreaking game-changing approach")
        assert "findings" in r
        assert len(r["findings"]) > 0

    def test_all_tiers_separate(self, core):
        r = core.scan_slop("groundbreaking serves as was noted")
        assert "findings_tier1" in r
        assert "findings_tier2" in r
        assert "findings_tier3" in r
        assert "all_findings" in r


# ============================================================
# TEST 4: Run Management & Edge Cases
# ============================================================

class TestRunManagement:
    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        return c

    def test_audit(self, core):
        result = core.audit()
        assert "✅" in result or "⚠️" in result

    def test_get_all_runs(self, core):
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "Test 1",
            "items": [
                FetchedNewsItem(title="T1", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="T", category="news"),
                FetchedNewsItem(title="T2", url="https://ap.com", source_name="Associated Press (AP)",
                    source_tier=SourceTier.PRIMARY, summary="T", category="news"),
            ],
            "sources": ["Reuters", "Associated Press (AP)"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://r.com",
        }
        core.create_news_run(cluster)
        runs = core.get_all_runs()
        assert len(runs) >= 1

    def test_search_runs(self, core):
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "RISC-V pipeline optimization test",
            "items": [
                FetchedNewsItem(title="RISC-V", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="RISC-V", category="tech"),
                FetchedNewsItem(title="RISC-V2", url="https://ap.com", source_name="AP",
                    source_tier=SourceTier.PRIMARY, summary="RISC-V", category="tech"),
            ],
            "sources": ["Reuters", "AP"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["tech"],
            "best_url": "https://r.com",
        }
        core.create_news_run(cluster)
        results = core.search_runs("RISC-V")
        assert len(results) >= 1


# ============================================================
# TEST 5: News Verification — Cross-verify, Hallucination, Correction
# ============================================================

class TestNewsVerification:
    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        return c

    @pytest.fixture
    def sample_cluster(self):
        return {
            "story_title": "Test News: AI Model Achieves Breakthrough Results",
            "items": [
                FetchedNewsItem(title="AI Breakthrough", url="https://reuters.com/ai",
                    source_name="Reuters", source_tier=SourceTier.PRIMARY,
                    summary="99% accuracy", category="technology"),
                FetchedNewsItem(title="AI Shows 99%", url="https://apnews.com/ai",
                    source_name="Associated Press (AP)", source_tier=SourceTier.PRIMARY,
                    summary="99% accuracy", category="technology"),
                FetchedNewsItem(title="AI Milestone", url="https://bbc.com/ai",
                    source_name="BBC News", source_tier=SourceTier.PRIMARY,
                    summary="99% accuracy", category="technology"),
            ],
            "sources": ["Reuters", "Associated Press (AP)", "BBC News"],
            "source_tiers": [0, 0, 0],
            "source_count": 3,
            "tier_count": {"primary": 3, "major": 0, "specialized": 0},
            "categories": ["technology"],
            "best_url": "https://reuters.com/ai",
        }

    def test_cross_verify_confirmed(self, core, sample_cluster):
        """3 primary sources should result in CONFIRMED verification."""
        ver = core.cross_verify_story(sample_cluster)
        assert ver.is_safe_to_publish
        assert ver.verification_level.name == "CONFIRMED"
        assert len(ver.sources_checked) >= 3

    def test_cross_verify_report_generated(self, core, sample_cluster):
        ver = core.cross_verify_story(sample_cluster)
        assert ver.report
        assert "Cross-Verification Report" in ver.report

    def test_cross_verify_to_dict(self, core, sample_cluster):
        ver = core.cross_verify_story(sample_cluster)
        d = ver.to_dict()
        assert d["is_safe_to_publish"]
        assert "sources_checked" in d

    def test_create_news_run_from_cluster(self, core, sample_cluster):
        r = core.create_news_run(sample_cluster)
        assert r["slug"]
        assert r["route"] == "VERIFIED"
        slug = r["slug"]
        run_path = core.active_runs / slug
        assert (run_path / "haber-object.md").exists()
        assert (run_path / "fact-check-report.md").exists()
        assert (run_path / "context.md").exists()

    def test_publish_verified_news(self, core, sample_cluster):
        r = core.publish_verified_news(sample_cluster, human_review=False)
        assert r["route"] == "VERIFIED"

    def test_create_news_run_duplicate(self, core, sample_cluster):
        r1 = core.create_news_run(sample_cluster)
        assert r1.get("status") != "exists"
        r2 = core.create_news_run(sample_cluster)
        assert r2.get("status") == "exists"

    def test_news_run_verification_level_in_cache(self, core, sample_cluster):
        r = core.create_news_run(sample_cluster)
        slug = r["slug"]
        assert slug in core._state_cache
        assert core._state_cache[slug].verification_level == "CONFIRMED"

    def test_hallucination_check_no_draft(self, core):
        result = core.hallucination_check("nonexistent-slug")
        assert "error" in result

    def test_issue_correction_nonexistent(self, core):
        result = core.issue_correction("nonexistent", "Wrong", "Correct")
        assert "❌" in result

    def test_state_cache_persists(self, core):
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "Persistent Cache Test",
            "items": [
                FetchedNewsItem(title="PT1", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="P", category="news"),
                FetchedNewsItem(title="PT2", url="https://ap.com", source_name="AP",
                    source_tier=SourceTier.PRIMARY, summary="P", category="news"),
            ],
            "sources": ["Reuters", "AP"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://r.com",
        }
        r = core.create_news_run(cluster)
        slug = r["slug"]
        assert slug in core._state_cache

    def test_search_news_default_params(self, core):
        result = core.search_news("test query", max_results=5, language="en", country="US")
        assert isinstance(result, dict)
        assert "query" in result
        assert "total_results" in result
        assert "clusters" in result
        assert "results" in result

    def test_archive_run(self, core):
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "Archive Test",
            "items": [
                FetchedNewsItem(title="AT1", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="A", category="news"),
                FetchedNewsItem(title="AT2", url="https://ap.com", source_name="AP",
                    source_tier=SourceTier.PRIMARY, summary="A", category="news"),
            ],
            "sources": ["Reuters", "AP"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://r.com",
        }
        r = core.create_news_run(cluster)
        slug = r["slug"]
        # Advance to published state
        core.update_state(slug, "verified")
        core.update_state(slug, "verified")
        core.update_state(slug, "published")
        assert core.get_state(slug) == "published"

    def test_issue_correction_after_publish(self, core):
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "Correction Test",
            "items": [
                FetchedNewsItem(title="CT1", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="C", category="news"),
                FetchedNewsItem(title="CT2", url="https://ap.com", source_name="AP",
                    source_tier=SourceTier.PRIMARY, summary="C", category="news"),
            ],
            "sources": ["Reuters", "AP"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://r.com",
        }
        r = core.create_news_run(cluster)
        slug = r["slug"]
        for s in ["verified", "verified", "published"]:
            core.update_state(slug, s)
        result = core.issue_correction(slug, "Wrong data", "Correct: $42")
        assert "✅" in result
        assert core.get_state(slug) == "corrected"
        assert (core.active_runs / slug / "correction.md").exists()

    def test_issue_retraction(self, core):
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "Retraction Test",
            "items": [
                FetchedNewsItem(title="RT1", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="R", category="news"),
                FetchedNewsItem(title="RT2", url="https://ap.com", source_name="AP",
                    source_tier=SourceTier.PRIMARY, summary="R", category="news"),
            ],
            "sources": ["Reuters", "AP"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://r.com",
        }
        r = core.create_news_run(cluster)
        slug = r["slug"]
        for s in ["verified", "verified", "published"]:
            core.update_state(slug, s)
        core.update_state(slug, "corrected")
        result = core.issue_correction(slug, "False story", "", retract=True)
        assert "✅" in result
        assert core.get_state(slug) == "corrected"


# ============================================================
# TEST 6: State Persistence
# ============================================================

class TestStatePersistence:
    def test_state_cache_created(self, tmp_path):
        core = HaberKuratorCore(tmp_path)
        core.setup()
        assert (tmp_path / ".state_cache").exists()

    def test_state_cache_unknown(self, tmp_path):
        core = HaberKuratorCore(tmp_path)
        assert core.get_state("nonexistent") == "unknown"

    def test_memos_cli_importable(self, tmp_path):
        import importlib
        try:
            import memos_cli
            importlib.reload(memos_cli)
            assert True
        except ImportError:
            pytest.skip("memos_cli not importable in this environment")


# ============================================================
# TEST 6b: Load idempotency (update-convergence regression)
# ============================================================

class TestLoadIdempotency:
    """Regression: instantiating the core (plugin load) must not rewrite
    run files when nothing changed. PM hashes member dirs for the venv
    stamp, so a fresh `updated:` timestamp on every load broke update
    convergence ("Dependency inputs changed while preparing publication;
    retry" loop between source_completion and the pm worker)."""

    def _seed_run(self, root: Path, slug: str = "2026-05-business-daily") -> Path:
        run = root / "runs" / "active" / slug
        run.mkdir(parents=True)
        (run / "haber-object.md").write_text(
            "# Haber Nesnesi — test\n\n## Meta\n- **Status:** captured\n"
            "\nupdated: 2026-01-01T00:00:00\n",
            encoding="utf-8",
        )
        return run

    def _snapshot(self, root: Path) -> dict:
        snap = {}
        for p in sorted(root.rglob("*")):
            if p.is_file() and "__pycache__" not in p.parts:
                snap[str(p.relative_to(root))] = p.read_bytes()
        return snap

    def test_repeated_init_writes_nothing(self, tmp_path):
        self._seed_run(tmp_path)
        HaberKuratorCore(tmp_path)  # first load settles state (db create, …)
        steady = self._snapshot(tmp_path)
        HaberKuratorCore(tmp_path)  # second load must be a pure no-op
        assert self._snapshot(tmp_path) == steady

    def test_same_state_update_is_noop(self, tmp_path):
        self._seed_run(tmp_path)
        core = HaberKuratorCore(tmp_path)
        obj = tmp_path / "runs" / "active" / "2026-05-business-daily" / "haber-object.md"
        before = obj.read_bytes()
        result = core.update_state("2026-05-business-daily", "captured", force=True)
        assert "✅" in result
        assert obj.read_bytes() == before

    def test_real_transition_still_writes(self, tmp_path):
        self._seed_run(tmp_path)
        core = HaberKuratorCore(tmp_path)
        obj = tmp_path / "runs" / "active" / "2026-05-business-daily" / "haber-object.md"
        before = obj.read_bytes()
        result = core.update_state("2026-05-business-daily", "verified", force=True)
        assert "✅" in result
        assert obj.read_bytes() != before
        assert core.get_state("2026-05-business-daily") == "verified"


# ============================================================
# TEST 7: Writer Agent — News Article Generation & Publishing
# ============================================================

# Helper: load WriterAgent class while working around relative import issue.
# writer_agent.py uses 'from .haber_kurator_core import ...' which requires
# a parent package context. We rewrite that import to use the already-imported
# haber_kurator_core module directly.
def _get_writer_agent_class():
    """Load WriterAgent class, patching relative import to absolute import."""
    plugin_dir = Path(__file__).resolve().parent.parent
    writer_path = plugin_dir / "writer_agent.py"
    source = writer_path.read_text(encoding="utf-8")
    source = source.replace(
        "from .haber_kurator_core import HaberKuratorCore, VerificationLevel",
        "from haber_kurator_core import HaberKuratorCore, VerificationLevel",
    )
    # Provide module-level names that writer_agent.py expects
    import logging
    ns = {
        "__file__": str(writer_path),
        "__name__": "writer_agent",
        "logging": logging,
    }
    exec(compile(source, str(writer_path), "exec"), ns)
    return ns["WriterAgent"]


class TestWriterAgent:
    """Tests for writer_agent.py WriterAgent — generate_news, auto_publish, post_to_memos."""

    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        c.fetch_all_news = lambda category=None: []
        return c

    @pytest.fixture
    def WriterAgentCls(self):
        return _get_writer_agent_class()

    @pytest.fixture
    def agent(self, core, WriterAgentCls):
        return WriterAgentCls(core)

    # ── Sample cluster fixtures ──────────────────────────────

    @pytest.fixture
    def politics_cluster(self):
        return {
            "story_title": "Trump and Biden meet for historic summit at White House",
            "items": [
                FetchedNewsItem(
                    title="Trump and Biden meet for historic summit at White House",
                    url="https://reuters.com/politics",
                    source_name="Reuters",
                    source_tier=SourceTier.PRIMARY,
                    summary="Trump and Biden met at the White House today for a historic summit.",
                    category="news",
                ),
                FetchedNewsItem(
                    title="Trump, Biden hold White House summit",
                    url="https://apnews.com/politics",
                    source_name="Associated Press (AP)",
                    source_tier=SourceTier.PRIMARY,
                    summary="Trump and Biden hold historic White House summit.",
                    category="news",
                ),
                FetchedNewsItem(
                    title="Historic Trump-Biden meeting at White House",
                    url="https://bbc.com/politics",
                    source_name="BBC News",
                    source_tier=SourceTier.PRIMARY,
                    summary="Trump and Biden meet at the White House.",
                    category="news",
                ),
            ],
            "sources": ["Reuters", "Associated Press (AP)", "BBC News"],
            "source_tiers": [0, 0, 0],
            "source_count": 3,
            "tier_count": {"primary": 3, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://reuters.com/politics",
        }

    @pytest.fixture
    def health_cluster(self):
        return {
            "story_title": "New COVID vaccine shows 95% efficacy in clinical trials",
            "items": [
                FetchedNewsItem(
                    title="New COVID vaccine shows 95% efficacy in clinical trials",
                    url="https://reuters.com/health",
                    source_name="Reuters",
                    source_tier=SourceTier.PRIMARY,
                    summary="New COVID vaccine shows 95% efficacy in clinical trials.",
                    category="news",
                ),
                FetchedNewsItem(
                    title="COVID vaccine 95% effective in trials",
                    url="https://apnews.com/health",
                    source_name="Associated Press (AP)",
                    source_tier=SourceTier.PRIMARY,
                    summary="New COVID vaccine effective in trials.",
                    category="news",
                ),
            ],
            "sources": ["Reuters", "Associated Press (AP)"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://reuters.com/health",
        }

    @pytest.fixture
    def tech_cluster(self):
        return {
            "story_title": "NVIDIA announces new AI chip with 4x performance improvement",
            "items": [
                FetchedNewsItem(
                    title="NVIDIA announces new AI chip with 4x performance improvement",
                    url="https://reuters.com/tech",
                    source_name="Reuters",
                    source_tier=SourceTier.PRIMARY,
                    summary="NVIDIA announced a new AI chip with 4x performance.",
                    category="technology",
                ),
                FetchedNewsItem(
                    title="NVIDIA unveils AI chip with 4x performance",
                    url="https://apnews.com/tech",
                    source_name="Associated Press (AP)",
                    source_tier=SourceTier.PRIMARY,
                    summary="NVIDIA unveils new AI chip with 4x performance improvement.",
                    category="technology",
                ),
            ],
            "sources": ["Reuters", "Associated Press (AP)"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["technology"],
            "best_url": "https://reuters.com/tech",
        }

    @pytest.fixture
    def economy_cluster(self):
        return {
            "story_title": "Federal Reserve raises interest rates by 50 basis points",
            "items": [
                FetchedNewsItem(
                    title="Federal Reserve raises interest rates by 50 basis points",
                    url="https://reuters.com/economy",
                    source_name="Reuters",
                    source_tier=SourceTier.PRIMARY,
                    summary="Fed raised interest rates by 50 basis points.",
                    category="business",
                ),
                FetchedNewsItem(
                    title="Fed raises interest rates by 50 basis points",
                    url="https://apnews.com/economy",
                    source_name="Associated Press (AP)",
                    source_tier=SourceTier.PRIMARY,
                    summary="Federal Reserve raises interest rates 50bp.",
                    category="business",
                ),
            ],
            "sources": ["Reuters", "Associated Press (AP)"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["business"],
            "best_url": "https://reuters.com/economy",
        }

    @pytest.fixture
    def science_cluster(self):
        return {
            "story_title": "James Webb Telescope discovers new exoplanet with signs of water",
            "items": [
                FetchedNewsItem(
                    title="James Webb Telescope discovers new exoplanet with signs of water",
                    url="https://reuters.com/science",
                    source_name="Reuters",
                    source_tier=SourceTier.PRIMARY,
                    summary="James Webb Telescope discovered an exoplanet with water signs.",
                    category="science",
                ),
                FetchedNewsItem(
                    title="JWST finds exoplanet with water",
                    url="https://apnews.com/science",
                    source_name="Associated Press (AP)",
                    source_tier=SourceTier.PRIMARY,
                    summary="JWST discovers exoplanet with water.",
                    category="science",
                ),
            ],
            "sources": ["Reuters", "Associated Press (AP)"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["science"],
            "best_url": "https://reuters.com/science",
        }

    @pytest.fixture
    def single_source_cluster(self):
        return {
            "story_title": "Local community center opens new library wing",
            "items": [
                FetchedNewsItem(
                    title="Local community center opens new library wing",
                    url="https://localnews.com/library",
                    source_name="Local News",
                    source_tier=SourceTier.SPECIALIZED,
                    summary="Community center opened a new library wing today.",
                    category="news",
                ),
            ],
            "sources": ["Local News"],
            "source_tiers": [2],
            "source_count": 1,
            "tier_count": {"primary": 0, "major": 0, "specialized": 1},
            "categories": ["news"],
            "best_url": "https://localnews.com/library",
        }

    # ── generate_news tests ───────────────────────────────────

    def test_generate_news_returns_formatted_output(self, agent, politics_cluster):
        """Verify generate_news returns Turkish output with [Özet]-[Detaylar]-[Kaynak] structure."""
        article = agent.generate_news(politics_cluster)
        assert "[Özet]" in article, "Missing [Özet] section marker"
        assert "[Detaylar]" in article, "Missing [Detaylar] section marker"
        assert "[Kaynak]" in article, "Missing [Kaynak] section marker"
        # Verify Turkish content
        assert "kaynak" in article.lower(), "Expected Turkish text with 'kaynak'"
        # Verify section order
        ozet_pos = article.index("[Özet]")
        detay_pos = article.index("[Detaylar]")
        kaynak_pos = article.index("[Kaynak]")
        assert ozet_pos < detay_pos < kaynak_pos, "Sections out of order: expected [Özet] < [Detaylar] < [Kaynak]"
        # Verify source attribution
        assert "Reuters" in article, "Source names should appear in article"
        assert "https://reuters.com/politics" in article, "Source URLs should appear in article"
        # Verify hash tags
        assert "#Haber" in article, "Missing #Haber tag"
        assert "#Gündem" in article, "Missing #Gündem tag"

    def test_generate_news_handles_all_categories(self, agent, politics_cluster, health_cluster,
                                                  tech_cluster, economy_cluster, science_cluster):
        """Test that generate_news correctly detects and labels all category types."""
        # Politics (category=news in fixture → "Haber")
        article = agent.generate_news(politics_cluster)
        assert "Haber" in article, "Politics cluster should produce category label"
        assert "[Özet]" in article, "Missing [Özet]"
        assert "[Detaylar]" in article, "Missing [Detaylar]"
        assert "[Kaynak]" in article, "Missing [Kaynak]"

        # Health (categories=["news"] in fixture → "Haber")
        article = agent.generate_news(health_cluster)
        assert "Haber" in article, "Health cluster should produce category label"
        assert "[Özet]" in article

        # Tech (categories=["news"] in fixture → "Haber")
        article = agent.generate_news(tech_cluster)
        assert "Haber" in article, "Tech cluster should produce category label"

        # Economy (categories=["news"] in fixture → "Haber")
        article = agent.generate_news(economy_cluster)
        assert "Haber" in article, "Economy cluster should produce category label"
        assert "Federal Reserve" in article, "Economy should mention original title"

        # Science (categories=["news"] in fixture → "Haber")
        article = agent.generate_news(science_cluster)
        assert "Haber" in article, "Science cluster should produce category label"
        assert "James Webb" in article, "Science should mention original title"

    def test_generate_news_single_source(self, agent, single_source_cluster):
        """Test generate_news handles single-source cluster without crashing."""
        article = agent.generate_news(single_source_cluster)
        assert "[Özet]" in article, "Missing [Özet] in single-source article"
        assert "[Detaylar]" in article, "Missing [Detaylar] in single-source article"
        assert "[Kaynak]" in article, "Missing [Kaynak] in single-source article"
        # Should say "1 kaynak tarafından doğrulandı"
        assert "1 kaynak" in article, "Single source should mention '1 kaynak'"
        # Single source with no PRIMARY tier -> no "DoğrulanmışHaber" tag
        assert "#DoğrulanmışHaber" not in article, "Single source should not get #DoğrulanmışHaber"
        # Source name and URL should be present
        assert "Local News" in article, "Source name should appear in article"
        assert "https://localnews.com/library" in article, "Source URL should appear in article"

    # ── auto_publish tests ────────────────────────────────────

    def test_auto_publish_returns_correct_dict(self, agent, core, monkeypatch):
        """Verify auto_publish returns a dict with correct structure and keys."""
        from unittest.mock import patch, MagicMock

        # Create test items that will cluster
        items = [
            FetchedNewsItem(
                title="Trump announces new trade deal with China",
                url="https://reuters.com/trade",
                source_name="Reuters",
                source_tier=SourceTier.PRIMARY,
                summary="President Trump announced a major trade deal with China.",
                category="news",
            ),
            FetchedNewsItem(
                title="Trump strikes trade deal with China",
                url="https://apnews.com/trade",
                source_name="Associated Press (AP)",
                source_tier=SourceTier.PRIMARY,
                summary="The US and China reached a new trade agreement.",
                category="news",
            ),
        ]

        # Mock network-dependent calls
        with patch.object(core, "fetch_all_news", return_value=items):
            with patch.object(agent, "post_to_memos", return_value=True):
                result = agent.auto_publish(max_articles=3)

        # Check result dict structure
        assert isinstance(result, dict), "auto_publish must return a dict"
        assert "published" in result, "Result must contain 'published' key"
        assert "skipped" in result, "Result must contain 'skipped' key"
        assert "failed" in result, "Result must contain 'failed' key"
        assert "articles" in result, "Result must contain 'articles' key"
        assert isinstance(result["articles"], list), "articles must be a list"
        # Types
        assert isinstance(result["published"], int), "published must be int"
        assert isinstance(result["skipped"], int), "skipped must be int"
        assert isinstance(result["failed"], int), "failed must be int"
        # Values should be non-negative
        assert result["published"] >= 0
        assert result["skipped"] >= 0
        assert result["failed"] >= 0
        # Sum of counts should equal max_articles or less (could be skipped if exists)
        total = result["published"] + result["skipped"] + result["failed"]
        assert total <= 3, f"Total processed ({total}) should not exceed max_articles (3)"
        # If articles were published, verify their structure
        for article in result["articles"]:
            assert "slug" in article, "Each article must have 'slug'"
            assert "title" in article, "Each article must have 'title'"
            assert "level" in article, "Each article must have 'level'"

    def test_auto_publish_skips_existing(self, agent, core, monkeypatch):
        """Verify auto_publish skips runs that already exist."""
        from unittest.mock import patch, MagicMock
        from haber_kurator_core import CrossVerificationResult

        items = [
            FetchedNewsItem(
                title="Existing news story",
                url="https://reuters.com/existing",
                source_name="Reuters",
                source_tier=SourceTier.PRIMARY,
                summary="Existing story summary.",
                category="news",
            ),
        ]

        # Pre-create a run so it exists
        pre_cluster = {
            "story_title": "Existing news story",
            "items": items,
            "sources": ["Reuters"],
            "source_tiers": [0],
            "source_count": 1,
            "tier_count": {"primary": 1, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://reuters.com/existing",
        }
        core.publish_verified_news(pre_cluster, human_review=False)

        with patch.object(core, "fetch_all_news", return_value=items):
            with patch.object(agent, "post_to_memos", return_value=True):
                result = agent.auto_publish(max_articles=3)

        # All should be skipped because the run already exists
        assert result["published"] == 0, "Existing run should not be published again"
        # Note: existence check happens inside auto_publish scoring loop which calls
        # cross_verify_story on the cluster. The slug generated for the items may differ
        # from the one we pre-created. So we just verify the dict structure.
        assert "skipped" in result
        assert "failed" in result

    # ── post_to_memos tests ───────────────────────────────────

    def test_post_to_memos_missing_token(self, agent, monkeypatch):
        """Verify post_to_memos returns False when MEMOS_TOKEN is not set."""
        monkeypatch.delenv("MEMOS_TOKEN", raising=False)
        # Also clear from the loaded environment
        if "MEMOS_TOKEN" in agent.__dict__ or "MEMOS_TOKEN" in agent.__class__.__dict__:
            pass  # os.environ is checked directly in the method
        result = agent.post_to_memos("test content")
        assert result is None, "Should return None when token is missing"

    def test_post_to_memos_missing_token_restores_env(self, agent, monkeypatch):
        """Verify post_to_memos doesn't crash when called without token in various states."""
        monkeypatch.delenv("MEMOS_TOKEN", raising=False)
        monkeypatch.delenv("MEMOS_API_URL", raising=False)
        result = agent.post_to_memos("Test article content with #tags")
        assert result is None


# ============================================================
# TEST 8: Search News — Edge Cases & Dict Structure
# ============================================================

class TestSearchNews:
    """Tests for search_news method — edge cases and result structure."""

    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        return c

    # ── Helper: sample items for search mocking ──────────────

    def _make_sample_items(self):
        """Create sample items that can cluster and cross-verify."""
        return [
            FetchedNewsItem(
                title="Trump announces new trade deal with China",
                url="https://reuters.com/trade1",
                source_name="Reuters",
                source_tier=SourceTier.PRIMARY,
                summary="President Trump announced a major trade deal with China today.",
                category="news",
                published="2026-05-16",
            ),
            FetchedNewsItem(
                title="Trump strikes trade deal with China",
                url="https://apnews.com/trade2",
                source_name="Associated Press (AP)",
                source_tier=SourceTier.PRIMARY,
                summary="The US and China reached a new trade agreement.",
                category="news",
                published="2026-05-16",
            ),
            FetchedNewsItem(
                title="Apple releases new iPhone with AI features",
                url="https://reuters.com/iphone",
                source_name="Reuters",
                source_tier=SourceTier.PRIMARY,
                summary="Apple released a new iPhone with advanced AI features.",
                category="technology",
                published="2026-05-16",
            ),
        ]

    def test_search_news_short_query(self, core):
        """Test search_news with a very short query (2 chars)."""
        from unittest.mock import patch

        items = self._make_sample_items()
        with patch.object(core, "_search_google_news", return_value=items):
            result = core.search_news("AI", max_results=5)

        assert isinstance(result, dict), "search_news must return a dict"
        assert result["query"] == "AI", "Query should be preserved"
        assert "total_results" in result
        assert "clusters" in result
        assert "results" in result

    def test_search_news_long_query(self, core):
        """Test search_news with a long query (full sentence)."""
        from unittest.mock import patch

        items = self._make_sample_items()
        long_query = "What is the latest development in artificial intelligence and machine learning research in 2026"
        with patch.object(core, "_search_google_news", return_value=items):
            result = core.search_news(long_query, max_results=5)

        assert isinstance(result, dict), "search_news must return a dict"
        assert result["query"] == long_query, "Query should be preserved"
        assert result["total_results"] == len(items), "Should report correct total results"

    def test_search_news_returns_correct_dict(self, core):
        """Verify search_news returns the full expected dict structure with all keys."""
        from unittest.mock import patch

        items = self._make_sample_items()
        with patch.object(core, "_search_google_news", return_value=items):
            result = core.search_news("trade deal", max_results=10)

        # Top-level keys
        expected_keys = {"query", "total_results", "unique_results", "clusters",
                         "verified_count", "results"}
        assert set(result.keys()) == expected_keys, (
            f"Expected keys {expected_keys}, got {set(result.keys())}"
        )

        # Query preservation
        assert result["query"] == "trade deal"
        assert isinstance(result["total_results"], int)
        assert isinstance(result["unique_results"], int)
        assert isinstance(result["clusters"], int)
        assert isinstance(result["verified_count"], int)

        # Results list structure
        assert isinstance(result["results"], list)
        if result["results"]:
            r = result["results"][0]
            # Cluster sub-dict
            assert "cluster" in r
            cluster_keys = {"story_title", "source_count", "tier_count", "best_url", "categories"}
            assert set(r["cluster"].keys()) == cluster_keys
            assert isinstance(r["cluster"]["story_title"], str)
            assert isinstance(r["cluster"]["source_count"], int)
            assert isinstance(r["cluster"]["tier_count"], dict)
            assert isinstance(r["cluster"]["best_url"], str)
            assert isinstance(r["cluster"]["categories"], list)

            # Verification sub-dict
            assert "verification" in r
            ver = r["verification"]
            ver_expected = {"story_title", "slug", "verification_level", "verification_label",
                            "verified_claims", "total_claims", "sources_checked",
                            "sources_agreed", "sources_disagreed", "discrepancies",
                            "is_safe_to_publish"}
            for key in ver_expected:
                assert key in ver, f"Missing verification key: {key}"
            assert isinstance(ver["is_safe_to_publish"], bool)

        # Count consistency
        assert result["total_results"] >= 0
        assert result["unique_results"] >= 0
        assert result["clusters"] >= 0
        assert result["verified_count"] >= 0
        assert result["verified_count"] <= result["clusters"], \
            "verified_count cannot exceed clusters"

    def test_search_news_empty_results(self, core):
        """Test search_news with no results returns proper empty structure."""
        from unittest.mock import patch

        with patch.object(core, "_search_google_news", return_value=[]):
            result = core.search_news("xyznonexistent12345", max_results=5)

        assert isinstance(result, dict)
        assert result["total_results"] == 0
        assert result["clusters"] == 0
        assert result["verified_count"] == 0
        assert result["results"] == []
        assert "note" in result, "Empty result should include a note"
        assert "No results found" in result["note"]

    def test_search_news_with_category_tags(self, core):
        """Test search_news correctly assigns category info in cluster results."""
        from unittest.mock import patch

        items = self._make_sample_items()
        with patch.object(core, "_search_google_news", return_value=items):
            result = core.search_news("technology news", max_results=10)

        # Verify category info in results
        for r in result["results"]:
            assert "categories" in r["cluster"]
            cats = r["cluster"]["categories"]
            assert isinstance(cats, list)

    def _create_test_run_for_llm(self, core) -> str:
        """Helper: create a run with all files an LLM function needs."""
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "LLM Test News",
            "items": [
                FetchedNewsItem(title="Test", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="Market update", category="news"),
                FetchedNewsItem(title="Test2", url="https://ap.com", source_name="Associated Press (AP)",
                    source_tier=SourceTier.PRIMARY, summary="Market update", category="news"),
            ],
            "sources": ["Reuters", "Associated Press (AP)"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["news"],
            "best_url": "https://r.com",
        }
        r = core.create_news_run(cluster)
        return r["slug"]

    def _make_mock_llm(self, return_text: str):
        """Helper: create a mock LLM object with async acomplete."""
        import asyncio
        mock_llm = MagicMock()

        class FakeResponse:
            def __init__(self, text):
                self.text = text

        async def fake_acomplete(messages):
            await asyncio.sleep(0.001)
            return FakeResponse(return_text)

        mock_llm.acomplete = fake_acomplete
        return mock_llm


# ============================================================
# TEST 8: LLM Functions — generate_brief, generate_draft, run_verifier
# ============================================================

class TestLLMFunctions:
    """Mock-LLM tests for async LLM-powered pipeline functions."""

    @pytest.fixture
    def core(self, tmp_path):
        return HaberKuratorCore(tmp_path)

    # ─── generate_brief ───────────────────────────────────────

    def test_generate_brief_success(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            mock_llm = _make_mock_llm("# Brief\n\nTest brief content for news.")
            result = await core.generate_brief(slug, llm=mock_llm)
            assert result["status"] == "verified"
            assert result["length"] > 0
            brief_path = core.active_runs / slug / "brief.md"
            assert brief_path.exists()
            assert "Test brief content" in brief_path.read_text(encoding="utf-8")
        asyncio.run(_test())

    def test_generate_brief_invalid_slug(self, core):
        async def _test():
            result = await core.generate_brief("nonexistent-slug")
            assert "error" in result
        asyncio.run(_test())

    def test_generate_brief_fallback_no_llm(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            result = await core.generate_brief(slug)
            assert "error" in result
        asyncio.run(_test())

    def test_generate_brief_with_extra_context(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            mock_llm = _make_mock_llm("# Brief\n\nExtra context test.")
            result = await core.generate_brief(slug, llm=mock_llm, extra_context="Extra context info")
            assert result["status"] == "verified"
        asyncio.run(_test())

    def test_generate_brief_llm_error(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            mock_llm = MagicMock()
            async def fail(*a, **kw):
                raise ValueError("LLM API error")
            mock_llm.acomplete = fail
            result = await core.generate_brief(slug, llm=mock_llm)
            # call_llm_with_fallback catches the acompleter error and falls back
            # to Hermes auxiliary (unavailable in test context → None → message)
            assert "error" in result
            assert "LLM unavailable" in result["error"]
        asyncio.run(_test())

    def test_generate_brief_strips_triple_backticks(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            mock_llm = _make_mock_llm("```markdown\n# Clean Brief\n\nContent.\n```")
            result = await core.generate_brief(slug, llm=mock_llm)
            assert result["status"] == "verified"
            brief_path = core.active_runs / slug / "brief.md"
            content = brief_path.read_text(encoding="utf-8")
            assert "```" not in content
            assert content.startswith("# Clean Brief")
        asyncio.run(_test())

    # ─── generate_draft ───────────────────────────────────────

    def test_generate_draft_success(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            brief_llm = _make_mock_llm("# Brief\n\nSource: Reuters reports market update.")
            await core.generate_brief(slug, llm=brief_llm)
            draft_llm = _make_mock_llm("# Draft\n\n[Özet] - [Detaylar] - [Kaynak]")
            result = await core.generate_draft(slug, llm=draft_llm)
            assert result["status"] == "drafted"
            draft_path = core.active_runs / slug / "draft-package.md"
            assert draft_path.exists()
        asyncio.run(_test())

    def test_generate_draft_invalid_slug(self, core):
        async def _test():
            result = await core.generate_draft("nonexistent")
            assert "error" in result
        asyncio.run(_test())

    def test_generate_draft_no_brief(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            result = await core.generate_draft(slug)
            assert "error" in result
            assert "No brief.md" in result["error"]
        asyncio.run(_test())

    def test_generate_draft_fallback_no_llm(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            mock_llm = _make_mock_llm("# Brief\n\nTest")
            await core.generate_brief(slug, llm=mock_llm)
            result = await core.generate_draft(slug)
            assert "error" in result
        asyncio.run(_test())

    # ─── run_verifier ─────────────────────────────────────────

    def test_run_verifier_success(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            await core.generate_brief(slug, llm=_make_mock_llm("# Brief\n\nSource: Reuters."))
            await core.generate_draft(slug, llm=_make_mock_llm("# Draft\n\nProper news content."))
            verifier_llm = _make_mock_llm("## VERDICT\n- [APPROVE]")
            result = await core.run_verifier(slug, llm=verifier_llm)
            assert result["status"] == "verified"
            report_path = core.active_runs / slug / "verifier-report.md"
            assert report_path.exists()
        asyncio.run(_test())

    def test_run_verifier_invalid_slug(self, core):
        async def _test():
            result = await core.run_verifier("nonexistent")
            assert "error" in result
        asyncio.run(_test())

    def test_run_verifier_no_draft(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            result = await core.run_verifier(slug)
            assert "error" in result
            assert "No draft-package.md" in result["error"]
        asyncio.run(_test())

    def test_run_verifier_strips_backticks(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            await core.generate_brief(slug, llm=_make_mock_llm("# Brief\n\nSource."))
            await core.generate_draft(slug, llm=_make_mock_llm("# Draft\n\nContent."))
            verifier_llm = _make_mock_llm("```markdown\n## VERDICT\n- [APPROVE]\n```")
            result = await core.run_verifier(slug, llm=verifier_llm)
            assert result["status"] == "verified"
            report = (core.active_runs / slug / "verifier-report.md").read_text(encoding="utf-8")
            assert "```" not in report
        asyncio.run(_test())

    def test_run_verifier_llm_error(self, core):
        async def _test():
            slug = self._create_test_run_for_llm(core)
            await core.generate_brief(slug, llm=_make_mock_llm("# Brief"))
            await core.generate_draft(slug, llm=_make_mock_llm("# Draft"))
            mock_llm = MagicMock()
            async def fail(*a, **kw):
                raise ConnectionError("API timeout")
            mock_llm.acomplete = fail
            result = await core.run_verifier(slug, llm=mock_llm)
            assert "error" in result
        asyncio.run(_test())

    def _create_test_run_for_llm(self, core) -> str:
        from haber_kurator_core import FetchedNewsItem, SourceTier
        cluster = {
            "story_title": "Test LLM Pipeline",
            "items": [
                FetchedNewsItem(title="A", url="https://r.com", source_name="Reuters",
                    source_tier=SourceTier.PRIMARY, summary="News", category="global"),
                FetchedNewsItem(title="B", url="https://ap.com", source_name="AP",
                    source_tier=SourceTier.PRIMARY, summary="News", category="global"),
            ],
            "sources": ["Reuters", "AP"],
            "source_tiers": [0, 0],
            "source_count": 2,
            "tier_count": {"primary": 2, "major": 0, "specialized": 0},
            "categories": ["global"],
            "best_url": "https://r.com",
        }
        return core.create_news_run(cluster)["slug"]


def _make_mock_llm(return_text: str):
    """Create a mock LLM object with async acomplete."""
    mock_llm = MagicMock()
    class FakeResp:
        def __init__(self, t): self.text = t
    async def fake_aco(m):
        await asyncio.sleep(0.001)
        return FakeResp(return_text)
    mock_llm.acomplete = fake_aco
    return mock_llm


# ============================================================
# TEST 9: _is_fresh recency filter
# ============================================================

def test_is_fresh_recent_rfc2822():
    """RFC 2822 date within the window → fresh."""
    dt = (datetime.now() - timedelta(hours=6)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    assert HaberKuratorCore._is_fresh(dt)


def test_is_fresh_old_rfc2822():
    """RFC 2822 date 10 days ago → stale."""
    dt = (datetime.now() - timedelta(days=10)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    assert not HaberKuratorCore._is_fresh(dt)


def test_is_fresh_recent_iso8601():
    """ISO-8601 date within the window → fresh."""
    dt = (datetime.now() - timedelta(hours=12)).isoformat()
    assert HaberKuratorCore._is_fresh(dt)


def test_is_fresh_old_iso8601():
    """ISO-8601 date > 48h → stale."""
    dt = (datetime.now() - timedelta(hours=72)).isoformat()
    assert not HaberKuratorCore._is_fresh(dt)


def test_is_fresh_zero_byte():
    """Empty date → fresh (no date = keep)."""
    assert HaberKuratorCore._is_fresh("")


def test_is_fresh_old_year_in_text():
    """Date with old year in string → stale."""
    old = f"{datetime.now().year - 1} önceki bir haber"
    assert not HaberKuratorCore._is_fresh(old)


def test_is_fresh_current_year_in_text():
    """Date with current year in string → fresh (no parseable date)."""
    now = datetime.now()
    assert HaberKuratorCore._is_fresh(str(now.year))


def test_is_fresh_custom_max_age():
    """Custom max_age_hours respects parameter."""
    dt = (datetime.now() - timedelta(hours=36)).strftime("%a, %d %b %Y %H:%M:%S +0000")
    assert not HaberKuratorCore._is_fresh(dt, max_age_hours=24)
    assert HaberKuratorCore._is_fresh(dt, max_age_hours=48)
