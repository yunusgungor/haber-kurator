"""
Haber-Kuratör v2.4.0 — Birim Testleri
Tüm temel fonksiyonları test eder: state machine, slop detection,
Idea Gate, run yönetimi, edge cases.
"""

import sys
import json
from pathlib import Path

# Add plugin directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from haber_kurator_core import (
    HaberKuratorCore, VERSION, STATE_LIFECYCLE, IDEA_ROUTES,
    FULL_SLOP_TIER1, FULL_SLOP_TIER2, FULL_SLOP_TIER3, FULL_SLOP_BONUS,
    RunState, SlopResult,
)
import pytest


# ============================================================
# TEST 1: Constants & Configuration
# ============================================================

class TestConstants:
    def test_version(self):
        assert VERSION == "2.4.0"

    def test_state_count(self):
        assert len(STATE_LIFECYCLE) == 14

    def test_state_order(self):
        assert STATE_LIFECYCLE[0] == "captured"
        assert STATE_LIFECYCLE[-1] == "archived"

    def test_route_count(self):
        assert len(IDEA_ROUTES) == 4

    def test_routes_content(self):
        assert "ORIGINAL" in IDEA_ROUTES
        assert "REPURPOSE" in IDEA_ROUTES
        assert "REWRITE" in IDEA_ROUTES
        assert "RESEARCH+IDEATE" in IDEA_ROUTES

    def test_slop_coverage(self):
        total = (len(FULL_SLOP_TIER1) + len(FULL_SLOP_TIER2) +
                 len(FULL_SLOP_TIER3) + len(FULL_SLOP_BONUS))
        assert total >= 54, f"Only {total} slop patterns (need ≥54)"

    def test_dataclass_runstate(self):
        rs = RunState(slug="test-slug")
        assert rs.slug == "test-slug"
        assert rs.state == "captured"
        assert rs.route == "ORIGINAL"

    def test_dataclass_slopresult(self):
        sr = SlopResult(score="PASS")
        assert sr.score == "PASS"
        assert sr.tier1_count == 0
        assert sr.findings == []


# ============================================================
# TEST 2: Idea Gate (4 Routes)
# ============================================================

class TestIdeaGate:
    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        return c

    def test_original_route(self, core):
        r = core.decide_route("My experience with RISC-V", "internal")
        assert r["route"] == "ORIGINAL"

    def test_rewrite_route(self, core):
        r = core.decide_route("I read an article about AI", "external")
        assert r["route"] == "REWRITE"

    def test_repurpose_route(self, core):
        r = core.decide_route("Follow-up to previous post", "existing")
        assert r["route"] == "REPURPOSE"

    def test_research_route(self, core):
        r = core.decide_route("Research edge AI trends", "research")
        assert r["route"] == "RESEARCH+IDEATE"

    def test_route_source_hint_priority(self, core):
        r = core.decide_route("Any random text", "research")
        assert r["route"] == "RESEARCH+IDEATE"

    def test_create_run_all_routes(self, core):
        for hint, expected in [
            ("internal", "ORIGINAL"),
            ("external", "REWRITE"),
            ("existing", "REPURPOSE"),
            ("research", "RESEARCH+IDEATE"),
        ]:
            r = core.create_run(f"Test {hint} idea", source_hint=hint)
            assert r["route"] == expected, f"{hint} -> {r['route']} (expected {expected})"


# ============================================================
# TEST 3: State Machine (14-State Lifecycle)
# ============================================================

class TestStateMachine:
    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        return c

    @pytest.fixture
    def slug(self, core):
        return core.create_run("Test lifecycle")["slug"]

    def test_initial_state(self, core, slug):
        assert core.get_state(slug) == "captured"

    def test_full_lifecycle(self, core, slug):
        for state in STATE_LIFECYCLE[1:]:
            result = core.update_state(slug, state)
            assert "✅" in result, f"Failed at {state}: {result}"
            assert core.get_state(slug) == state, f"State mismatch after {state}"

    def test_invalid_transition_rejected(self, core, slug):
        for s in STATE_LIFECYCLE[1:]:
            core.update_state(slug, s)
        result = core.update_state(slug, "captured")
        assert "❌" in result

    def test_invalid_state_name(self, core, slug):
        result = core.update_state(slug, "invalid_state_name")
        assert "❌" in result

    def test_sync_state(self, core, slug):
        run_path = core.active_runs / slug
        (run_path / "brief.md").write_text("test brief", encoding="utf-8")
        state = core.sync_state(slug)
        assert state == "brief_ready"
        assert core.get_state(slug) == "brief_ready"

    def test_get_next_actions(self, core, slug):
        actions = core.get_next_actions(slug)
        assert len(actions) > 0
        assert isinstance(actions, list)

    def test_get_state_unknown(self, core):
        assert core.get_state("nonexistent") == "unknown"

    def test_update_nonexistent(self, core):
        result = core.update_state("nonexistent-slug", "captured")
        assert "❌" in result


# ============================================================
# TEST 4: Slop Detection
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
        # Note: 'so' was removed, using 'very'
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
# TEST 5: Run Management & Edge Cases
# ============================================================

class TestRunManagement:
    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        return c

    def test_create_run(self, core):
        r = core.create_run("Test idea")
        assert "slug" in r
        assert "path" in r

    def test_duplicate_slug(self, core):
        r1 = core.create_run("Test")
        r2 = core.create_run("Test again", slug=r1["slug"])
        assert r2.get("status") == "exists"

    def test_utf8_multiple(self, core):
        for idea, keyword in [
            ("日本語のテスト投稿", "日本語"),
            ("اختبار المحتوى العربي", "العربي"),
            ("测试中文内容", "中文"),
            ("🚀 Emoji test with 🔥", "🚀"),
        ]:
            r = core.create_run(idea)
            fp = core.active_runs / r["slug"] / "idea.md"
            content = fp.read_text(encoding="utf-8")
            assert keyword in content, f"'{keyword}' not found for '{idea[:20]}'"

    def test_special_chars_slug(self, core):
        r = core.create_run("test@#$%^&*()")
        assert r["slug"]

    def test_spaces_only(self, core):
        r = core.create_run("   ")
        assert r["slug"]

    def test_long_idea(self, core):
        r = core.create_run("X" * 500)
        assert r["slug"]

    def test_archive_learned(self, core):
        r = core.create_run("Archive test")
        slug = r["slug"]
        for s in STATE_LIFECYCLE[1:13]:
            core.update_state(slug, s)
        assert core.get_state(slug) == "learned"
        result = core.archive_run(slug)
        assert "✅" in result

    def test_archive_nonlearned_rejected(self, core):
        r = core.create_run("No archive")
        result = core.archive_run(r["slug"])
        assert "❌" in result

    def test_search_runs(self, core):
        core.create_run("RISC-V pipeline optimization")
        results = core.search_runs("RISC-V")
        assert len(results) >= 1

    def test_audit(self, core):
        result = core.audit()
        assert "✅" in result or "⚠️" in result

    def test_get_all_runs(self, core):
        core.create_run("Run 1")
        core.create_run("Run 2")
        runs = core.get_all_runs()
        assert len(runs) >= 2

    def test_analyze_patterns(self, core):
        result = core.analyze_run_patterns()
        assert "total_runs" in result or "message" in result

    def test_run_files_created(self, core):
        r = core.create_run("File check")
        slug = r["slug"]
        run_path = core.active_runs / slug
        assert (run_path / "haber-object.md").exists()
        assert (run_path / "context.md").exists()
        assert (run_path / "idea.md").exists()
        idea_content = (run_path / "idea.md").read_text(encoding="utf-8")
        assert "Route Decision" in idea_content


# ============================================================
# TEST 6: GBrain Integration Skeleton
# ============================================================

class TestGBrainIntegration:
    def test_gbrain_disabled_by_default(self, tmp_path):
        core = HaberKuratorCore(tmp_path)
        assert not core.gbrain_enabled

    def test_gbrain_enable(self, tmp_path):
        core = HaberKuratorCore(tmp_path)
        core.setup()
        core.enable_gbrain()
        assert core.gbrain_enabled

    def test_gbrain_query_returns_dict(self, tmp_path):
        core = HaberKuratorCore(tmp_path)
        core.setup()
        result = core._query_gbrain("RISC-V pipeline optimization")
        assert isinstance(result, dict)


# ============================================================
# TEST 7: State Persistence
# ============================================================

class TestStatePersistence:
    def test_state_cache_created(self, tmp_path):
        core = HaberKuratorCore(tmp_path)
        core.setup()
        assert (tmp_path / ".state_cache").exists()

    def test_state_cache_persists(self, tmp_path):
        core = HaberKuratorCore(tmp_path)
        core.setup()
        r = core.create_run("Persistent test")
        slug = r["slug"]
        core.update_state(slug, "idea_review")

        core2 = HaberKuratorCore(tmp_path)
        core2.setup()
        assert core2.get_state(slug) == "idea_review"

    def test_state_cache_unknown(self, tmp_path):
        core = HaberKuratorCore(tmp_path)
        assert core.get_state("nonexistent") == "unknown"


# ============================================================
# TEST 8: Archive Cache Fix (BUG-2 Regression)
# ============================================================

class TestArchiveCache:
    @pytest.fixture
    def core(self, tmp_path):
        c = HaberKuratorCore(tmp_path)
        c.setup()
        return c

    def test_archive_sets_state_to_archived(self, core):
        """After archive_run(), get_state() must return 'archived', not 'learned'."""
        r = core.create_run("Archive cache test")
        slug = r["slug"]
        # Walk through full lifecycle to 'learned'
        for s in STATE_LIFECYCLE[1:13]:  # idea_review ... learned
            core.update_state(slug, s)
        assert core.get_state(slug) == "learned"
        result = core.archive_run(slug)
        assert "✅" in result
        # BUG-2: cache must show 'archived', not 'learned'
        assert core.get_state(slug) == "archived"

    def test_archive_content_object_updated(self, core):
        """haber-object.md in archive must have state: archived."""
        r = core.create_run("Archive file test")
        slug = r["slug"]
        for s in STATE_LIFECYCLE[1:13]:
            core.update_state(slug, s)
        core.archive_run(slug)
        archived_obj = core.archive / slug / "haber-object.md"
        if archived_obj.exists():
            content = archived_obj.read_text(encoding="utf-8")
            assert "archived" in content


# ============================================================
# TEST 9: memos_cli RuntimeError (BUG-1 Regression)
# ============================================================

class TestMemosCli:
    def test_post_memo_raises_without_token(self, tmp_path, monkeypatch):
        """post_memo must raise RuntimeError (not call sys.exit) when token is missing."""
        import sys
        # plugin root is parent of tests/
        plugin_root = str(Path(__file__).resolve().parent.parent)
        if plugin_root not in sys.path:
            sys.path.insert(0, plugin_root)
        
        import importlib, os
        
        try:
            import memos_cli
            importlib.reload(memos_cli)
            
            # Mock os.path.exists to return False for the .env file check
            original_exists = os.path.exists
            def mocked_exists(path):
                if ".env" in str(path):
                    return False
                return original_exists(path)
            
            monkeypatch.setattr(os.path, "exists", mocked_exists)
            monkeypatch.delenv("MEMOS_TOKEN", raising=False)
            
            with pytest.raises(RuntimeError, match="MEMOS_TOKEN"):
                memos_cli.post_memo("test content")
        except ImportError:
            pytest.skip("memos_cli not importable in this environment")
