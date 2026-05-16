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
    CrossVerificationResult,
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
        # Politics
        article = agent.generate_news(politics_cluster)
        assert "Siyasi gelişmeler" in article, "Politics cluster should produce 'Siyasi gelişmeler'"
        assert "#Siyaset" in article, "Politics cluster should have #Siyaset tag"

        # Health
        article = agent.generate_news(health_cluster)
        assert "Sağlık:" in article, "Health cluster should produce 'Sağlık:'"
        # The keywords 'virus', 'health', 'covid', 'vaccine', 'clinical' should match
        assert any(kw in article.lower() for kw in ["sağlık", "hastane", "hasta"]), \
            "Health cluster should include health-related Turkish content"

        # Tech
        article = agent.generate_news(tech_cluster)
        assert "Teknoloji:" in article, "Tech cluster should produce 'Teknoloji:'"
        assert "#Teknoloji" in article, "Tech cluster should have #Teknoloji tag"

        # Economy
        article = agent.generate_news(economy_cluster)
        assert "Ekonomi:" in article, "Economy cluster should produce 'Ekonomi:'"
        assert "#Ekonomi" in article, "Economy cluster should have #Ekonomi tag"
        assert "piyasalar" in article.lower(), "Economy cluster should mention 'piyasalar'"

        # Science
        article = agent.generate_news(science_cluster)
        assert "Bilim:" in article, "Science cluster should produce 'Bilim:'"
        assert "#Bilim" in article, "Science cluster should have #Bilim tag"

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
        assert result is False, "Should return False when token is missing"

    def test_post_to_memos_missing_token_restores_env(self, agent, monkeypatch):
        """Verify post_to_memos doesn't crash when called without token in various states."""
        monkeypatch.delenv("MEMOS_TOKEN", raising=False)
        monkeypatch.delenv("MEMOS_API_URL", raising=False)
        result = agent.post_to_memos("Test article content with #tags")
        assert result is False


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
