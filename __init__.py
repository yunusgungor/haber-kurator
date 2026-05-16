"""Haber Kuratör Plugin v3.0.0 — News Verification System.

Complete multi-source news verification platform:
- Fetches from world's leading proven-accurate media sources (Reuters, AP, AFP, BBC, etc.)
- Cross-verifies every claim across 2+ independent sources
- 4-tier source credibility system
- Hallucination protection — Writer Agent restricted to source-attributed facts
- Correction workflow for post-publication errors
- 18-state lifecycle with fact-checking pipeline

Registers tools, hooks, slash commands, and CLI for the Haber Kuratör workflow.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import logging

from .haber_kurator_core import HaberKuratorCore, tool_haber_kurator_manager, tool_haber_kurator_retriever
from .cli import register_cli

logger = logging.getLogger(__name__)

VERSION = "3.0.0"


def register(ctx: Any) -> None:
    root = Path(__file__).parent
    core = HaberKuratorCore(root)

    # ══════════════════════════════════════════════════════════════
    # TOOL: haber_kurator_manager (30+ actions — full lifecycle + news verification)
    # ══════════════════════════════════════════════════════════════

    manager_schema = {
        "name": "haber_kurator_manager",
        "description": (
            "Complete Haber Kuratör management — News Verification Engine v3.0.0.\n"
            "News pipeline: fetch_news → verify_news → publish_verified → create_news_run.\n"
            "Verification: cross_verify_story → hallucination_check → issue_correction.\n"
            "Legacy: generate_brief, generate_draft, run_verifier, scan_slop, score, etc.\n\n"
            "CRITICAL: This is a NEWS system. Every fact is cross-verified against "
            "2+ independent sources from our approved media directory before publishing."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        # System
                        "setup", "audit", "list", "sources",
                        # NEWS VERIFICATION — New v3.0
                        "fetch_news", "verify_news", "publish_verified",
                        "cross_verify_story",
                        # Writer Agent — Auto Publish
                        "auto_publish",
                        # Hallucination Guard — New v3.0
                        "hallucination_check",
                        # Correction — New v3.0
                        "check_correction", "issue_correction",
                        # Idea Gate
                        "decide_route",
                        # Run management
                        "new_run", "update_state", "get_state", "sync_state",
                        "get_next_actions",
                        # Agent Pipeline
                        "generate_brief", "generate_draft", "run_verifier",
                        # Quality
                        "scan_slop", "score",
                        # Signals
                        "signal",
                        # Postmortem
                        "postmortem",
                        # Voice
                        "update_voice",
                        # Learning
                        "get_learnings", "analyze_patterns",
                        # Search
                        "search_runs", "get_all_runs",
                        # Archive
                        "archive_run",
                    ],
                    "description": "Action to perform in the Haber Kuratör pipeline",
                },
                "idea": {"type": "string", "description": "Content idea text"},
                "source_hint": {
                    "type": "string",
                    "enum": ["verified", "internal", "external", "existing", "research"],
                    "description": "Route hint: 'verified' for multi-source news, 'internal' for personal content",
                },
                "slug": {"type": "string", "description": "Content slug for existing runs"},
                "state": {"type": "string", "description": "New state for update_state"},
                "text": {"type": "string", "description": "Text to scan for slop patterns"},
                "source": {"type": "string", "description": "Signal source: 'x' or 'rss'"},
                "metrics": {"type": "object", "description": "Metrics for postmortem"},
                "updates": {"type": "object", "description": "Voice profile updates"},
                "topic": {"type": "string", "description": "Topic filter for learnings"},
                "query": {"type": "string", "description": "Search query for run search"},
                "extra_context": {"type": "string", "description": "Extra context for brief"},
                "include_archived": {"type": "boolean", "description": "Include archived runs", "default": True},
                # NEW v3.0 parameters
                "category": {
                    "type": "string",
                    "enum": ["news", "technology", "business", "science"],
                    "description": "News category filter for fetch_news/verify_news",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results for verify_news/publish_verified (default: 10/5)",
                },
                "human_review": {
                    "type": "boolean",
                    "description": "Require human review before auto-publishing (default: true)",
                    "default": True,
                },
                # Writer Agent — Auto Publish
                "limit": {
                    "type": "integer",
                    "description": "Max articles for auto_publish (default: 5)",
                },
                "category": {
                    "type": "string",
                    "enum": ["news", "technology", "business", "science"],
                    "description": "News category filter for auto_publish",
                },
                "cluster_data": {
                    "type": "object",
                    "description": "Story cluster data for cross_verify_story",
                },
                "error_description": {
                    "type": "string",
                    "description": "Error description for issue_correction",
                },
                "correct_information": {
                    "type": "string",
                    "description": "Correct information for issue_correction",
                },
                "retract": {
                    "type": "boolean",
                    "description": "Retract the story entirely (vs correction)",
                    "default": False,
                },
            },
            "required": ["action"],
        },
    }

    ctx.register_tool(
        name="haber_kurator_manager",
        toolset="haber",
        schema=manager_schema,
        handler=lambda args, **kw: tool_haber_kurator_manager(core, args, **kw),
        description="Complete Haber Kuratör pipeline management tool — News Verification Engine v3.0.0.",
        is_async=True,
    )

    # ══════════════════════════════════════════════════════════════
    # TOOL: haber_kurator_retriever (Updated)
    # ══════════════════════════════════════════════════════════════

    retriever_schema = {
        "name": "haber_kurator_retriever",
        "description": "Retrieve strategy, voice, sources, run data, stores, or learnings from Haber Kuratör.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["sources", "source_summary", "strategy", "voice", "run", "stores", "learnings"],
                    "description": "Knowledge category to retrieve",
                },
                "slug": {"type": "string", "description": "Slug for run category"},
                "topic": {"type": "string", "description": "Optional topic filter for learnings"},
            },
            "required": ["category"],
        },
    }

    ctx.register_tool(
        name="haber_kurator_retriever",
        toolset="haber",
        schema=retriever_schema,
        handler=lambda args, **kw: tool_haber_kurator_retriever(core, args),
        description="Knowledge retrieval from Haber Kuratör stores.",
    )

    # ══════════════════════════════════════════════════════════════
    # TOOL: memos_publisher
    # ══════════════════════════════════════════════════════════════

    memos_schema = {
        "name": "memos_publisher",
        "description": "Publish a final news draft natively to the Memos Platform (memos.googig.cloud).",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The exact content to publish."},
                "visibility": {"type": "string", "description": "Visibility (PUBLIC, PRIVATE, PROTECTED)", "default": "PUBLIC"},
                "tags": {"type": "string", "description": "Comma separated tags, e.g. 'news, tech'"}
            },
            "required": ["content"],
        },
    }

    def tool_memos_publisher(args: Dict[str, Any], **kw) -> str:
        try:
            from . import memos_cli
            content = args.get("content", "")
            tags = args.get("tags", "")
            visibility = args.get("visibility", "PUBLIC")
            memos_cli.post_memo(content, tags, visibility)
            return "✅ Successfully published to Memos!"
        except RuntimeError as e:
            return f"❌ Publishing failed: {str(e)}"
        except Exception as e:
            return f"❌ Error publishing: {str(e)}"

    ctx.register_tool(
        name="memos_publisher",
        toolset="haber",
        schema=memos_schema,
        handler=tool_memos_publisher,
        description="Native publisher for Memos Platform.",
    )

    # ══════════════════════════════════════════════════════════════
    # SLASH COMMAND: /haber (Updated)
    # ══════════════════════════════════════════════════════════════

    def handle_slash(args: str) -> Optional[str]:
        argv = args.strip().split()
        if not argv:
            return (
                "Usage: /haber [status|new|fetch|verify|correct|hallucination|"
                "brief|draft|verify-draft|scan|score|audit|setup|signal|"
                "postmortem|route|state|archive|learnings|patterns|runs|"
                "context|voice-update|sources|post|auto-publish]"
            )

        sub = argv[0]

        # ══════════════════════════════════════════════════════════════
        # NATURAL LANGUAGE PROCESSING — Türkçe doğal dil anlama
        #
        # Örnekler:
        #   /haber teknoloji haberlerini getir    → fetch technology
        #   /haber ekonomi haberlerini doğrula    → verify business
        #   /haber son dakika haberlerini yayınla → publish news
        #   /haber bilim haberlerini otomatik yayınla → auto-publish science
        #   /haber haberleri getir ve doğrula      → fetch + verify
        #   /haber kaynakları listele              → sources
        # ══════════════════════════════════════════════════════════════

        _KNOWN_COMMANDS = {"status", "new", "fetch", "verify", "correct", "hallucination",
                           "brief", "draft", "verify-draft", "scan", "score", "audit",
                           "setup", "signal", "postmortem", "route", "state", "archive",
                           "learnings", "patterns", "runs", "context", "voice-update",
                           "sources", "post", "publish", "auto-publish"}

        if sub not in _KNOWN_COMMANDS:
            _full_lower = args.strip().lower()

            # Türkçe → İngilizce kategori eşleme (özgül olan önce)
            _cat = None
            for _pattern, _en_cat in [
                (r'teknoloji', "technology"), (r'\btech\b', "technology"),
                (r'ekonomi', "business"), (r'finans', "business"), (r'piyasa', "business"),
                (r'bilim', "science"), (r'araştırma', "science"), (r'\bscience\b', "science"),
                (r'gündem', "news"),
            ]:
                if __import__("re").search(_pattern, _full_lower):
                    _cat = _en_cat
                    break
            # Generic 'haber' fallback (Türkçe ekler için substring)
            if _cat is None and "haber" in _full_lower:
                _cat = "news"
            # 'son dakika' override
            if "son dakika" in _full_lower:
                _cat = "news"

            # Niyet tespiti (kelime sınırı ile)
            _has_fetch = bool(__import__("re").search(r'\b(getir|çek|fetch|ara|bul|indir)\b', _full_lower))
            _has_verify = bool(__import__("re").search(r'\b(doğrula|verify|kontrol|teyit|onayla|incele|doğrulama)\b', _full_lower))
            _has_publish = bool(__import__("re").search(r'\b(yayınla|publish|paylaş|gönder|post|bas)\b', _full_lower))
            _has_auto = bool(__import__("re").search(r'\b(otomatik|auto|full|tüm|tam)\b', _full_lower))
            _has_sources = "kaynak" in _full_lower or bool(__import__("re").search(r'\bsources\b', _full_lower))
            _has_verify_only = _has_verify and not _has_fetch and not _has_publish

            # ── Niyet → Aksiyon eşleme ──

            # Kaynak listesi isteniyorsa
            if _has_sources and not _has_fetch and not _has_verify:
                return core.get_source_summary()

            # Otomatik yayın (tam pipeline)
            if _has_auto and _has_publish:
                from .writer_agent import WriterAgent
                agent = WriterAgent(core)
                try:
                    from agent.auxiliary_client import async_call_llm
                    agent.set_llm(True)
                except ImportError:
                    pass
                results = agent.auto_publish(max_articles=5, category=_cat)
                lines = [f"### 🤖 Writer Agent — {results['published']} haber yayınlandı", ""]
                for a in results.get("articles", []):
                    badge = "✅" if a.get("level") == "CONFIRMED" else "🟡"
                    lines.append(f"{badge} **{a.get('title', '?')[:80]}**")
                if results.get("skipped", 0) > 0:
                    lines.append(f"\n⏭️ {results['skipped']} haber atlandı")
                if results.get("failed", 0) > 0:
                    lines.append(f"\n❌ {results['failed']} haber başarısız")
                return "\n".join(lines)

            # Sadece doğrulama isteniyorsa
            if _has_verify_only:
                items = core.fetch_all_news(_cat)
                clusters = core.cluster_stories(items)
                top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:10]
                lines = [f"### 🔍 Cross-Verification Results ({len(clusters)} clusters)", ""]
                for c in top:
                    ver = core.cross_verify_story(c)
                    badge = "✅" if ver.is_safe_to_publish else "⚠️"
                    lines.append(f"{badge} **{c['story_title'][:80]}**")
                    lines.append(f"   Level: {ver.verification_level.label}")
                    lines.append(f"   Sources: {ver.sources_checked}")
                    lines.append("")
                return "\n".join(lines)

            # Yayınla isteniyorsa (verify + publish)
            if _has_publish:
                items = core.fetch_all_news(_cat)
                clusters = core.cluster_stories(items)
                results = []
                for c in sorted(clusters, key=lambda x: x["source_count"], reverse=True)[:5]:
                    results.append(core.publish_verified_news(c, human_review=not _has_auto))
                lines = [f"### 📰 Publish Results ({len(results)} stories)", ""]
                for r in results:
                    status_icon = "✅" if r.get("status") != "exists" else "⏭️"
                    lines.append(f"{status_icon} **{r.get('slug', '?')}** — {r.get('route', '?')}")
                return "\n".join(lines)

            # Varsayılan: fetch + sonuçları göster
            items = core.fetch_all_news(_cat)
            clusters = core.cluster_stories(items)
            top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:10]
            lines = [f"### 📡 News Fetched ({len(items)} items, {len(clusters)} clusters)", ""]
            for i, c in enumerate(top, 1):
                tiers = c["tier_count"]
                tier_badges = f"T0:{tiers.get('primary',0)} T1:{tiers.get('major',0)}"
                lines.append(f"{i}. **{c['story_title'][:90]}**")
                lines.append(f"   Sources: {c['source_count']} | {tier_badges}")
                lines.append(f"   URL: {c.get('best_url', 'N/A')}")
                lines.append("")
            return "\n".join(lines)

        # ── News Verification Commands (NEW) ──

        if sub == "fetch":
            """Fetch and cluster latest news from all sources."""
            category = argv[1] if len(argv) > 1 and argv[1] in ("news", "technology", "business", "science") else None
            items = core.fetch_all_news(category)
            clusters = core.cluster_stories(items)
            lines = [f"### 📡 News Fetched ({len(items)} items, {len(clusters)} clusters)", ""]

            # Top stories by source count
            top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:10]
            for i, c in enumerate(top, 1):
                tiers = c["tier_count"]
                tier_badges = f"T0:{tiers.get('primary',0)} T1:{tiers.get('major',0)}"
                lines.append(f"{i}. **{c['story_title'][:90]}**")
                lines.append(f"   Sources: {c['source_count']} | {tier_badges}")
                lines.append(f"   URL: {c.get('best_url', 'N/A')}")
                lines.append("")

            return "\n".join(lines)

        if sub == "verify":
            """Fetch, cluster, and cross-verify news."""
            category = argv[1] if len(argv) > 1 and argv[1] in ("news", "technology", "business", "science") else None
            limit = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 10

            items = core.fetch_all_news(category)
            clusters = core.cluster_stories(items)
            lines = [f"### 🔍 Cross-Verification Results ({len(clusters)} clusters)", ""]

            for cluster in clusters[:limit]:
                verification = core.cross_verify_story(cluster)
                badge = "✅" if verification.is_safe_to_publish else "⚠️"
                lines.append(f"{badge} **{cluster['story_title'][:80]}**")
                lines.append(f"   Level: {verification.verification_level.label}")
                lines.append(f"   Sources: {verification.sources_checked}")
                lines.append("")

            return "\n".join(lines)

        if sub == "correct":
            """Issue a correction for a published news item directly."""
            if len(argv) < 2:
                return "Usage: /haber correct <slug> <error> [--retract]"
            slug = argv[1]
            is_retract = "--retract" in argv
            error_parts = [a for a in argv[2:] if not a.startswith("--")]
            error_desc = " ".join(error_parts) if error_parts else "Unspecified error"
            return core.issue_correction(slug, error_desc, "", is_retract)

        if sub == "hallucination":
            """Run automated hallucination check on a draft."""
            if len(argv) < 2:
                return "Usage: /haber hallucination <slug>"
            slug = argv[1]
            result = core.hallucination_check(slug)
            if "error" in result:
                return f"❌ {result['error']}"
            status = "✅ PASS" if result["pass"] else "❌ FAIL"
            return (
                f"### Hallucination Check: {slug}\n"
                f"- **Status:** {status}\n"
                f"- **Total Findings:** {result['total_findings']}\n"
                f"- **High Severity:** {result['high_severity']}\n"
                f"- **Medium Severity:** {result['medium_severity']}\n"
            )

        if sub == "sources":
            """List all configured news sources."""
            return core.get_source_summary()

        if sub == "publish":
            """Fetch, verify & create news runs."""
            category = argv[1] if len(argv) > 1 and argv[1] in ("news", "technology", "business", "science") else None
            limit = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 5
            auto = "--auto" in argv
            items = core.fetch_all_news(category)
            clusters = core.cluster_stories(items)
            results = []
            for c in sorted(clusters, key=lambda x: x.get("source_count", 0), reverse=True)[:limit]:
                results.append(core.publish_verified_news(c, human_review=not auto))
            lines = [f"### 📰 Publish Results ({len(results)} stories)", ""]
            for r in results:
                status_icon = "✅" if r.get("status") != "exists" else "⏭️"
                lines.append(f"{status_icon} **{r.get('slug', '?')}** — {r.get('route', '?')}")
            return "\n".join(lines)

        if sub == "auto-publish":
            """Writer Agent: auto-fetch, verify, generate & publish directly."""
            limit = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 5
            category = argv[2] if len(argv) > 2 and argv[2] in ("news", "technology", "business", "science") else None
            from .writer_agent import WriterAgent
            agent = WriterAgent(core)
            results = agent.auto_publish(max_articles=limit, category=category)
            lines = [f"### 🤖 Writer Agent — {results['published']} haber yayınlandı", ""]
            for a in results.get("articles", []):
                badge = "✅" if a.get("level") == "CONFIRMED" else "🟡"
                lines.append(f"{badge} **{a.get('title', '?')[:80]}**")
            if results.get("skipped", 0) > 0:
                lines.append(f"\n⏭️ {results['skipped']} haber atlandı (zaten mevcut)")
            if results.get("failed", 0) > 0:
                lines.append(f"\n❌ {results['failed']} haber başarısız")
            return "\n".join(lines)

        # ── Legacy Commands ──

        if sub == "status":
            runs = core.active_runs
            if not runs.exists():
                return "No active runs."
            lines = ["### Active Haber Runs", ""]
            for r in runs.iterdir():
                if r.is_dir():
                    state = core.get_state(r.name)
                    lines.append(f"- **{r.name}** — `{state}`")
            return "\n".join(lines)

        if sub == "new":
            idea = " ".join(argv[1:])
            if not idea:
                return "Usage: /haber new <idea>"
            res = core.create_run(idea)
            return f"✅ Created run: **{res['slug']}** (Route: {res['route']})"

        if sub == "route":
            idea = " ".join(argv[1:])
            if not idea:
                return "Usage: /haber route <idea> [source_hint]"
            source = argv[-1] if argv[-1] in ("verified", "internal", "external", "existing", "research") else ""
            if source:
                idea = " ".join(argv[1:-1])
            res = core.decide_route(idea, source)
            return (
                f"### Idea Gate — Route Decision\n"
                f"- **Route:** {res['route']}\n"
                f"- **Rationale:** {res['rationale']}\n"
                f"- **Source:** {res['source_type']}"
            )

        if sub == "state":
            if len(argv) < 2:
                active = list(core.active_runs.iterdir()) if core.active_runs.exists() else []
                lines = ["### All Run States", ""]
                for d in active:
                    if d.is_dir():
                        lines.append(f"- **{d.name}**: {core.get_state(d.name)}")
                return "\n".join(lines)
            slug = argv[1]
            state = core.get_state(slug)
            actions = core.get_next_actions(slug)
            return (
                f"### {slug}\n"
                f"- **State:** {state}\n"
                f"- **Next actions:**\n"
                + "\n".join(f"  {i+1}. {a}" for i, a in enumerate(actions))
            )

        if sub == "brief":
            if len(argv) < 2:
                return "Usage: /haber brief <slug>"
            slug = argv[1]
            core.sync_state(slug)
            core.update_state(slug, "brief_ready")
            return f"📝 Ready for brief: **{slug}**. Write brief.md manually."

        if sub == "draft":
            if len(argv) < 2:
                return "Usage: /haber draft <slug>"
            slug = argv[1]
            core.update_state(slug, "drafting")
            return f"✍️ **{slug}** → drafting. Write brief.md and create draft-package.md."

        if sub == "verify-draft":
            if len(argv) < 2:
                return "Usage: /haber verify-draft <slug>"
            slug = argv[1]
            core.update_state(slug, "verification")
            return f"🔍 **{slug}** → verification. Run hallucination_check and scan_slop."

        if sub == "scan":
            if len(argv) < 2:
                return "Usage: /haber scan <slug>"
            slug = argv[1]
            path = core.active_runs / slug / "draft-package.md"
            if not path.exists():
                return f"Draft not found for {slug}"
            res = core.scan_slop(path.read_text(encoding="utf-8"))
            return (
                f"### Slop Scan: {slug}\n"
                f"- **Score:** {res['score']}\n"
                f"- **Tier 1 (Critical):** {res['tier1_count']}\n"
                f"- **Tier 2 (High):** {res['tier2_count']}\n"
                f"- **Tier 3 (Medium):** {res['tier3_count']}\n"
                f"- **Bonus (Tone):** {res['bonus_count']}\n"
                f"- **Findings:** {', '.join(res['all_findings'][:8]) or 'None'}"
            )

        if sub == "score":
            if len(argv) < 2:
                return "Usage: /haber score <slug>"
            slug = argv[1]
            path = core.active_runs / slug / "draft-package.md"
            if not path.exists():
                return f"❌ Draft not found for {slug}"
            text = path.read_text(encoding="utf-8")
            slop = core.scan_slop(text)
            return (
                f"### 📊 Score: {slug}\n"
                f"- **Slop Score:** {slop['score']}\n"
                f"- **Tier 1:** {slop['tier1_count']} | **Tier 2:** {slop['tier2_count']}\n"
                f"- **Tier 3:** {slop['tier3_count']} | **Bonus:** {slop['bonus_count']}\n"
                f"\n🤖 Full rubric (0-12) → use haber_kurator_manager action='score'"
            )

        if sub == "audit":
            return core.audit()

        if sub == "setup":
            return core.setup()
        
        if sub == "signal":
            src = argv[1] if len(argv) > 1 else "x"
            signals = core.process_signal(src)
            lines = [f"### Signals from {src.upper()}", ""]
            for i, s in enumerate(signals, 1):
                lines.append(f"{i}. {s}")
            return "\n".join(lines)

        if sub == "postmortem":
            if len(argv) < 2:
                return "Usage: /haber postmortem <slug>"
            slug = argv[1]
            state = core.get_state(slug)
            if state == "published":
                core.update_state(slug, "feedback_24h")
                return f"📊 **{slug}** → feedback_24h. Collect metrics and run analysis."
            elif state == "feedback_24h":
                core.update_state(slug, "feedback_72h")
                return f"📊 **{slug}** → feedback_72h. Deep analysis."
            else:
                return f"📊 **{slug}** (state: {state}). Can't run postmortem until published."

        if sub == "post":
            if len(argv) < 2:
                return "Usage: /haber post <slug>"
            slug = argv[1]
            draft_path = core.active_runs / slug / "draft-package.md"
            if not draft_path.exists():
                return f"Draft not found for {slug}."
            # Read draft and post to Memos directly
            draft = draft_path.read_text(encoding="utf-8")
            content = draft.split("draft:")[1].split("rubric_self_assessment")[0].strip() if "draft:" in draft else draft
            from .memos_cli import post_memo
            try:
                post_memo(content)
                core.update_state(slug, "published")
                return f"📤 **{slug}** posted to Memos! ✅"
            except Exception as e:
                return f"❌ Post failed: {str(e)[:100]}"

        if sub == "archive":
            if len(argv) < 2:
                return "Usage: /haber archive <slug> [--force]"
            force = "--force" in argv
            return core.archive_run(argv[1], force=force)

        if sub == "learnings":
            topic = argv[1] if len(argv) > 1 else None
            return core.get_learnings_for_brief(topic)

        if sub == "patterns":
            patterns = core.analyze_run_patterns()
            if "message" in patterns:
                return patterns["message"]
            lines = ["### Run Patterns Analysis", ""]
            lines.append(f"- **Total runs:** {patterns['total_runs']}")
            lines.append(f"- **Avg okunma:** {patterns['avg_okunma']}")
            if patterns.get("top_formats"):
                lines.append("\n**Top formats:**")
                for f, c in patterns["top_formats"]:
                    lines.append(f"  - {f}: {c}")
            return "\n".join(lines)

        if sub == "runs":
            include_archived = not (len(argv) > 1 and argv[1] == "--active")
            runs = core.get_all_runs(include_archived)
            if not runs:
                return "No runs found."
            lines = ["### All Haber Runs", ""]
            for r in runs:
                state = r.get("state", "?")
                route = r.get("route", "?")
                status = r.get("status", "?")
                files = len(r.get("files", []))
                lines.append(f"- **{r['slug']}** — {state} — {route} — {status} ({files} dosya)")
            return "\n".join(lines)

        if sub == "search":
            if len(argv) < 2:
                return "Usage: /haber search <query>"
            query = " ".join(argv[1:])
            results = core.search_runs(query)
            if not results:
                return "No results found."
            lines = [f"### Search: {query}", ""]
            for r in results[:10]:
                lines.append(f"- **{r['slug']}** — {r['file']} ({r['state']})")
            return "\n".join(lines)

        if sub == "context":
            if len(argv) < 2:
                return "Usage: /haber context <slug>"
            slug = argv[1]
            for base in [core.active_runs, core.archive]:
                ctx_file = base / slug / "context.md"
                if ctx_file.exists():
                    return f"### Context for {slug}\n\n{ctx_file.read_text(encoding='utf-8')[:1500]}"
            return f"Run {slug} not found."

        if sub == "voice-update":
            vf = core.voice / "voice-profile.md"
            if vf.exists():
                return f"### Voice Profile\n\n{vf.read_text(encoding='utf-8')[:1000]}"
            return "No voice profile found."

        return f"Unknown subcommand: {sub}. Try: status, new, fetch, verify, correct, hallucination, sources, publish, auto-publish, search, runs, post, archive"

    ctx.register_command(
        "haber",
        handler=handle_slash,
        description="Haber Kuratör v3.0.0 — News Verification System. Fetch, verify, publish, auto-publish.",
        args_hint="[status|new|fetch|verify|correct|hallucination|sources|publish|auto-publish|post|scan|audit|setup|runs|search|archive]",
    )

    # ══════════════════════════════════════════════════════════════
    # CLI COMMAND: hermes haber (Updated)
    # ══════════════════════════════════════════════════════════════

    ctx.register_cli_command(
        name="haber",
        help="Haber Kuratör v3.0.0 — News Verification System",
        setup_fn=lambda sub: register_cli(sub, core),
        description=(
            "Haber Kuratör News Verification Engine v3.0.0.\n"
            "Multi-source news fetching → cross-verification → fact-check → publish.\n"
            "18-state lifecycle, 54+ slop patterns, 4 credibility tiers.\n"
            "Powered by Reuters, AP, AFP, BBC, Bloomberg, WSJ and more."
        ),
    )

    # ══════════════════════════════════════════════════════════════
    # HOOKS
    # ══════════════════════════════════════════════════════════════

    def on_session_start(**kwargs):
        logger.info("Haber Kuratör v%s — News Verification Engine started.", VERSION)

    def post_tool_call(tool_name: str, args: Dict[str, Any], result: str, **kwargs):
        """Observe file writes to auto-update Haber Kuratör states."""
        from pathlib import Path
        if tool_name not in ("write_file", "write_to_file", "create_file"):
            return

        target_path = args.get("TargetFile", "") or args.get("path", "") or args.get("file_path", "")

        if target_path and ("runs/active/" in target_path or "runs\\active\\" in target_path):
            path = Path(target_path)
            try:
                slug = path.parent.name
                filename = path.name

                state_map = {
                    "brief.md": "brief_ready",
                    "draft-package.md": "drafting",
                    "verifier-report.md": "verification",
                    "fact-check-report.md": "fact_checking",
                    "correction.md": "correction_needed",
                }

                if filename in state_map:
                    new_state = state_map[filename]
                    try:
                        core.update_state(slug, new_state)
                        logger.info("Auto-updated %s to %s (via post_tool_call)", slug, new_state)
                    except Exception:
                        pass
            except Exception:
                pass

    ctx.register_hook("on_session_start", on_session_start)
    ctx.register_hook("post_tool_call", post_tool_call)

    # ══════════════════════════════════════════════════════════════
    # SKILL REGISTRATION
    # ══════════════════════════════════════════════════════════════

    skill_path = root / "SKILL.md"
    if skill_path.exists():
        ctx.register_skill(
            "haber-kurator",
            skill_path,
            description="Haber Kuratör v3.0.0 — News Verification System: multi-source fetch, cross-verify, fact-check, publish.",
        )

    logger.info("Haber Kuratör v%s (News Verification Engine) registered.", VERSION)
