"""
Haber Kuratör Core v3.1.0 — News Verification Engine
====================================================
"""

import json
import logging
import os
import re
import shutil
import sqlite3
import time
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    load_dotenv = None

from haber_kurator.modules.state_machine import StateMachineMixin
from haber_kurator.modules.fetcher import FetcherMixin
from haber_kurator.modules.scanner import ScannerMixin

from haber_kurator.modules.models import (
    VERSION, CONFIG, NEWS_SOURCES,
    STATE_LIFECYCLE, STATE_TRANSITIONS, STATE_ALIAS_MAP,
    ROUTE_VERIFIED, ROUTE_HIGH_SLOP, ROUTE_ESCALATED, WRITER_FIELDS,
    SourceTier, VerificationLevel,
    NewsSource, FactClaim, CrossVerificationResult,
    HaberKuratorError, SourceError, StateError, ConfigError, LLMError,
    RunState, SlopResult, FetchedNewsItem,
    _load_news_sources, _env_bool, _env_float_list,
)
logger = logging.getLogger(__name__)
FULL_SLOP_TIER1 = [
    r"groundbreaking", r"game-changing", r"revolutionary", r"transformative", r"paradigm-shifting",
    r"pivotal moment", r"testament to", r"a testament to", r"significant step", r"quantum leap",
    r"experts believe", r"studies show", r"research suggests", r"data shows", r"it turns out that",
    r"according to reports", r"according to sources", r"some say", r"many believe",
    r"the system compounds", r"the data tells us", r"compound interest of", r"the power of",
    r"the question is whether", r"at its core", r"what if i told you",
    r"(?i)(?:^|\n)\s*(?:no\s+\S+\.\s*){2,}", r"(?i)(?:^|\n)\s*(?:\S+\.\s*){4,}", r"(?i)(?:fail|error|bug)s?\s*\.\s*(?:fail|error|bug)s?\s*\.",
    r"(?<!\-)\-\-(?!\-)",
    r"actually", r"literally", r"quietly", r"simply", r"just\b", r"basically",
    r"it is reported that(?! by)", r"allegedly(?!,? (?:according to|Reuters|AP|AFP))",
    r"unnamed sources say", r"insiders reveal", r"sources close to",
    r"breaking:\s", r"developing story", r"this just in", r"we are learning",
]
FULL_SLOP_TIER2 = [
    r"serves as", r"stands as", r"features", r"encompasses", r"utilizes",
    r"leveraging", r"implementing", r"optimizing", r"enabling",
    r"three things", r"three reasons", r"three ways", r"triad\b",
    r"in order to", r"due to the fact that", r"at this point in time", r"in today's world",
    r"the future looks bright", r"exciting times ahead", r"the best is yet to come",
    r"let's dive in", r"here's what you need to know", r"tldr", r"in conclusion",
    r"every single", r"all the time", r"never ever", r"absolutely everyone",
    r"it could potentially", r"it might be argued", r"somewhat", r"arguably",
]
FULL_SLOP_TIER3 = [
    r"\b(?:was|were|been|being)\s+\w+ed\b",
    r"(?:\w+,\s*(?:also\s+)?known\s+as)",
    r"from basic to advanced", r"from beginner to expert",
    r"(?:^|\n)\s*(?:And|But)\s+",
    r"\bvery\b", r"\bsuch\b",
    r"it is important to note that", r"it should be noted that",
    r"(?:have you ever wondered|can you imagine|what would you do if)",
    r"there are \d+ things", r"\d+ (?:is|are) ",
    r"exactly \d+\.\d+%",
    r"level\s*up", r"dive\s*deep", r"game\s*plan", r"road\s*map",
    r"i may be wrong", r"i could be wrong",
    r"(?:^|\n)\s*\[.*?\]\s*\n", r"(?:^|\n)\s*[A-Z]{4,}\s*\n",
    r"\brecently\b", r"\blately\b", r"\bthese days\b",
    r"some say .* while others say", r"on one hand .* on the other hand",
    r"as someone who", r"having worked in",
    r"in this post, we.{0,20}(?:explore|dive|cover|discuss)",
    r"the very real possibility", r"the very real chance",
]
FULL_SLOP_BONUS = [
    r"\byou should\b", r"\byou must\b", r"never do this",
    r"it feels like", r"seems to me",
    r"here's the thing", r"the secret",
    r"\d+\s*years? ago,?.*?(?:i|we|my|our)",
    r"result\s*:\s*%\s*\w+",
    r"could potentially mean", r"might indicate that", r"may suggest that",
    r"could be a sign", r"raises questions about",
]
class HaberKuratorCore(ScannerMixin, FetcherMixin, StateMachineMixin):
    """Haber Kuratör v3.1.0 — News Verification Engine.

    Transforms raw news from world-leading sources into verified,
    source-attributed news content through multi-source cross-verification,
    fact-checking, and hallucination protection.
    """

    def __init__(self, root: Path):
        self.root = root
        self.strategy = root / "strategy"
        self.voice = root / "voice"
        self.active_runs = root / "runs" / "active"
        self.stores = root / "stores"
        self.workflows = root / "workflows"
        self.archive = root / "runs" / "archive"
        self.references = root / "references"

        # Slop patterns
        self.slop_tier1 = FULL_SLOP_TIER1
        self.slop_tier2 = FULL_SLOP_TIER2
        self.slop_tier3 = FULL_SLOP_TIER3
        self.slop_bonus = FULL_SLOP_BONUS

        # Known sources directory — try JSON first, fall back to embedded
        self.sources = _load_news_sources()

        self._init_stores_dirs()
        self._migrate_old_state()

        # State cache — SQLite backed (v3.1.0)
        self._state_cache_dir = root / '.state_cache'
        self._state_cache_dir.mkdir(parents=True, exist_ok=True)
        self._state_cache: Dict[str, RunState] = {}
        self._db_path = str(self._state_cache_dir / 'state.db')
        self._init_db()
        self._load_state_cache()

        # RSS conditional GET cache (v3.2.0) — per-session, ephemeral
        self._rss_cache: Dict[str, Dict[str, Any]] = {}

    # ──────────────────────────────────────────────────────────
    # SETUP & MIGRATION
    # ──────────────────────────────────────────────────────────

    def _init_stores_dirs(self):
        """Initialize stores subdirectories."""
        for subdir in ["ideas", "hooks", "proof", "feedback"]:
            (self.stores / subdir).mkdir(parents=True, exist_ok=True)

    def _migrate_old_state(self):
        """Auto-migrate existing runs to new state format on init."""
        if not self.active_runs.exists():
            return
        for d in self.active_runs.iterdir():
            if d.is_dir():
                try:
                    self.sync_state(d.name)
                except (OSError, PermissionError, StateError) as e:
                    logger.debug("sync_state skipped %s: %s", d.name, e)

    # ──────────────────────────────────────────────────────────
    # SETUP
    # ──────────────────────────────────────────────────────────

    def setup(self) -> str:
        """Initialize directory structure."""
        dirs = [self.strategy, self.voice, self.active_runs,
                self.stores, self.workflows, self.archive, self.references]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
        self._init_stores_dirs()
        return f"✅ Haber Kuratör v{VERSION} initialized. News verification engine ready."

    # 1. SOURCE MANAGEMENT

async def tool_haber_kurator_manager(core: HaberKuratorCore, args: Dict[str, Any],
                                   **kwargs) -> str:
    """Handle all manager tool actions."""
    try:
        action = args.get("action")
        slug = args.get("slug")

        # System
        if action == "setup":
            return core.setup()
        if action == "audit":
            return core.audit()
        if action == "list":
            return json.dumps(core.get_all_runs(args.get("include_archived", True)))

        # News Source Management (NEW)
        if action == "sources":
            return core.get_source_summary()
        if action == "fetch_news":
            category = args.get("category")
            country = args.get("country")
            items = core.fetch_all_news(category, country)
            clusters = core.cluster_stories(items)
            return json.dumps({
                "total_items": len(items),
                "clusters": len(clusters),
                "top_stories": [
                    {
                        "title": c["story_title"][:100],
                        "sources": c["source_count"],
                        "best_url": c.get("best_url", ""),
                        "tiers": c["tier_count"],
                    }
                    for c in clusters[:10]
                ],
            }, indent=2, ensure_ascii=False)

        if action == "search_news":
            """Search for a specific news topic across multiple sources.

            Uses Google News RSS search + existing clustering/verification.
            Supports Turkish and English queries with language/country detection.
            """
            query = args.get("search_query", "")
            if not query:
                return "❌ 'search_query' parameter is required."
            max_results = args.get("max_results", 20)
            language = args.get("language", "tr")
            country = args.get("country", "TR")
            result = core.search_news(query, max_results, language, country)
            return json.dumps(result, indent=2, ensure_ascii=False)

        if action == "verify_news":
            """Fetch, cluster, and cross-verify all news from sources."""
            category = args.get("category")
            country = args.get("country")
            items = core.fetch_all_news(category, country)
            clusters = core.cluster_stories(items)
            verified = []
            for cluster in clusters[:args.get("limit", 10)]:
                verification = core.cross_verify_story(cluster)
                verified.append(verification.to_dict())
            return json.dumps(verified, indent=2, ensure_ascii=False)

        if action == "publish_verified":
            """Fetch, verify, and create runs for top news items."""
            category = args.get("category")
            human_review = args.get("human_review", True)
            country = args.get("country")
            items = core.fetch_all_news(category, country)
            clusters = core.cluster_stories(items)
            results = []
            for cluster in clusters[:args.get("limit", 5)]:
                result = core.publish_verified_news(cluster, human_review)
                results.append(result)
            return json.dumps(results, indent=2, ensure_ascii=False)

        if action == "cross_verify_story":
            """Cross-verify a specific story cluster."""
            cluster_data = args.get("cluster_data", {})
            if not cluster_data:
                return "❌ cluster_data required"
            # Reconstruct FetchedNewsItem from dict
            items = []
            for item_dict in cluster_data.get("items", []):
                items.append(FetchedNewsItem(
                    title=item_dict["title"],
                    url=item_dict.get("url", ""),
                    source_name=item_dict.get("source_name", "Unknown"),
                    source_tier=SourceTier(item_dict.get("source_tier", 2)),
                    published=item_dict.get("published", ""),
                    summary=item_dict.get("summary", ""),
                    category=item_dict.get("category", "general"),
                ))
            cluster_data["items"] = items
            verification = core.cross_verify_story(cluster_data)
            return json.dumps(verification.to_dict(), indent=2, ensure_ascii=False)

        # Hallucination Guard (NEW)
        if action == "hallucination_check":
            return json.dumps(core.hallucination_check(slug))

        if action == "scan_slop":
            return json.dumps(core.scan_slop(args.get("text", "")))

        # Correction Workflow (NEW)
        if action == "check_correction":
            return core.check_correction_needed(slug)

        if action == "issue_correction":
            return core.issue_correction(
                slug,
                args.get("error_description", ""),
                args.get("correct_information", ""),
                args.get("retract", False),
            )

        # Run actions
        if action == "update_state":
            if not slug:
                return json.dumps({"error": "slug parameter required"})
            return core.update_state(slug, args.get("state"))
        if action == "get_state":
            if not slug:
                return json.dumps({"error": "slug parameter required", "state": "unknown", "next_actions": []})
            return json.dumps({
                "slug": slug, "state": core.get_state(slug),
                "next_actions": core.get_next_actions(slug),
            })
        if action == "sync_state":
            return f"State: {core.sync_state(slug)}"
        if action == "get_next_actions":
            return json.dumps(core.get_next_actions(slug))

        # Writer Agent — Auto Publish
        if action == "auto_publish":
            try:
                # Force module reload to pick up code changes (Python module cache)
                import importlib as _hermes_il
                import sys as _hermes_sys
                for _mod in ['hermes_plugins.haber_kurator.writer_agent']:
                    if _mod in _hermes_sys.modules:
                        _hermes_il.reload(_hermes_sys.modules[_mod])
                from .writer_agent import WriterAgent
                agent = WriterAgent(core)
                # Enable Turkish content generation via LLM
                # (same approach as slash command handler — import-based detection)
                try:
                    from agent.auxiliary_client import async_call_llm
                    agent.set_llm(True)
                    _call_llm_logger = logging.getLogger(__name__)
                    _call_llm_logger.info("auto_publish: LLM available, set_llm(True) called")
                except ImportError as _ie:
                    # Fallback: try parent_agent from kwargs (older path)
                    llm_ctx = kwargs.get("parent_agent")
                    llm_obj = llm_ctx.ctx.llm if llm_ctx and hasattr(llm_ctx, "ctx") else None
                    if llm_obj:
                        agent.set_llm(True)
                results = agent.auto_publish(
                    max_articles=args.get("limit", 5),
                    category=args.get("category"),
                    country=args.get("country"),
                )
                return json.dumps(results, indent=2, ensure_ascii=False)
            except Exception as e:
                return f"Error in auto_publish: {str(e)}"

        # Search
        if action == "search_runs":
            return json.dumps(core.search_runs(args.get("query", "")))
        if action == "get_all_runs":
            return json.dumps(core.get_all_runs(args.get("include_archived", True)))

        # Archive
        if action == "archive_run":
            return core.archive_run(slug)

        return f"Unknown action: {action}"

    except Exception as e:
        return f"Error: {str(e)}"


def tool_haber_kurator_retriever(core: HaberKuratorCore, args: Dict[str, Any]) -> str:
    """Retrieve knowledge from Haber Kuratör stores."""
    try:
        category = args.get("category")
        slug = args.get("slug")

        if category == "sources":
            return json.dumps(core.get_all_sources(), indent=2, ensure_ascii=False)

        if category == "source_summary":
            return core.get_source_summary()

        if category == "strategy":
            result = {}
            for f in ["positioning.md", "audience.md", "pillars.md", "source-watchlist.md"]:
                path = core.strategy / f
                if path.exists():
                    result[f.replace(".md", "")] = path.read_text(encoding="utf-8")
            return json.dumps(result) if result else "No strategy files found."

        if category == "voice":
            result = {}
            for f in ["voice-profile.md", "master-avoid-slop.md"]:
                path = core.voice / f
                if path.exists():
                    result[f.replace(".md", "")] = path.read_text(encoding="utf-8")
            return json.dumps(result) if result else "No voice files found."

        if category == "run" and slug:
            for base in [core.active_runs, core.archive]:
                rp = base / slug
                if rp.exists():
                    files = ["haber-object.md", "idea.md", "brief.md",
                             "draft-package.md", "verifier-report.md",
                             "feedback.md", "context.md", "fact-check-report.md",
                             "correction.md"]
                    result = {}
                    for f in files:
                        fp = rp / f
                        if fp.exists():
                            result[f.replace(".md", "")] = fp.read_text(encoding="utf-8")
                    return json.dumps(result) if result else f"No data for {slug}"
            return json.dumps({"error": f"Run {slug} not found."})

        if category == "stores":
            result = {}
            for subdir in ["inbox.md", "workboard.md", "ideas", "hooks", "proof", "feedback"]:
                path = core.stores / subdir
                if path.is_file():
                    result[subdir.replace(".md", "")] = path.read_text(encoding="utf-8")
                elif path.exists() and path.is_dir():
                    files = [f.name for f in path.glob("*.md")]
                    result[subdir] = files
            return json.dumps(result)

        if category == "learnings":
            return core.get_learnings_for_brief(args.get("topic"))

        return f"Unknown category: {category}"

    except Exception as e:
        return f"Error: {str(e)}"
