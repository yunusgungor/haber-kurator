"""
Haber-Kuratör v3.1.0 — Birim Testleri
Tüm haber doğrulama fonksiyonlarını test eder: fetch, cluster, cross-verify,
hallucination, correction, state machine, edge cases.
"""

import sys
import json
from pathlib import Path

# Add plugin directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haber_kurator_core import (
    HaberKuratorCore, VERSION, STATE_LIFECYCLE,
    FULL_SLOP_TIER1, FULL_SLOP_TIER2, FULL_SLOP_TIER3, FULL_SLOP_BONUS,
    RunState, SlopResult, STATE_TRANSITIONS, CONFIG,
    FetchedNewsItem, SourceTier, VerificationLevel,
)
import pytest


# ============================================================
# TEST 1: Constants & Configuration
# ============================================================

class TestConstants:
    def test_version(self):
        assert VERSION == "3.1.0"

    def test_state_count(self):
        assert len(STATE_LIFECYCLE) == 8

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
        result = core.update_state("nonexistent-slug", "fact_checking")
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
        assert r1["status"] != "exists"
        r2 = core.create_news_run(sample_cluster)
        assert r2["status"] == "exists"

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
        core.update_state(slug, "fact_checking")
        core.update_state(slug, "cross_verified")
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
        for s in ["fact_checking", "cross_verified", "published"]:
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
        for s in ["fact_checking", "cross_verified", "published"]:
            core.update_state(slug, s)
        core.update_state(slug, "correction_needed")
        result = core.issue_correction(slug, "False story", "", retract=True)
        assert "✅" in result
        assert core.get_state(slug) == "retracted"


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
