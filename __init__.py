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
from .cli import register_cli, handle_nlp

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

    # ══════════════════════════════════════════════════════════════
    # TIMED STAGE TRACKER — Her aşamayı süreyle birlikte kaydeder
    # ══════════════════════════════════════════════════════════════
    class _StageTracker:
        """Aşamaları süre ve durumla birlikte izler. Sonunda rapor üretir."""

        def __init__(self, title: str):
            self.title = title
            self.stages: list[dict] = []
            self._start = __import__("time").time()
            self._stage_start = self._start

        def begin(self, name: str, icon: str = "⏳"):
            """Yeni aşama başlat (önceki aşamayı otomatik kapatır)."""
            now = __import__("time").time()
            if self.stages and self.stages[-1]["status"] == "running":
                self.stages[-1]["status"] = "done"
                self.stages[-1]["duration"] = f"{now - self._stage_start:.1f}s"
            self._stage_start = now
            self.stages.append({"icon": icon, "name": name, "status": "running", "duration": "..."})

        def fail(self, msg: str = ""):
            """Mevcut aşamayı hata olarak işaretle."""
            now = __import__("time").time()
            if self.stages and self.stages[-1]["status"] == "running":
                self.stages[-1]["status"] = "fail"
                self.stages[-1]["duration"] = f"{now - self._stage_start:.1f}s"
                if msg:
                    self.stages[-1]["name"] += f" — {msg}"

        def end(self):
            """Son aşamayı kapat."""
            now = __import__("time").time()
            if self.stages and self.stages[-1]["status"] == "running":
                self.stages[-1]["status"] = "done"
                self.stages[-1]["duration"] = f"{now - self._stage_start:.1f}s"

        def report(self, extra_lines: list[str] | None = None) -> str:
            """Stage-by-stage rapor üret."""
            self.end()
            total = __import__("time").time() - self._start
            lines = [f"### {self.title}", ""]
            icon_map = {"done": "✅", "fail": "❌", "running": "⏳"}
            for s in self.stages:
                icon = icon_map.get(s["status"], "⏳")
                lines.append(f"  {icon} **{s['name']}** _({s['duration']})_")
            lines.append(f"\n  ⏱️ **Toplam:** {total:.1f}s")
            if extra_lines:
                lines.extend(extra_lines)
            return "\n".join(lines)

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
                           "sources", "post", "publish", "auto-publish", "search"}

        if sub not in _KNOWN_COMMANDS:
            result = handle_nlp(args, core)
            if result:
                return result
            return f"Anlaşılamadı: '{args}'. Komutlar: status, new, fetch, verify, correct, hallucination, sources, publish, auto-publish, search, runs, post, archive. Veya doğal dil: 'teknoloji haberlerini getir'"

        # ── News Verification Commands (NEW) ──

        if sub == "fetch":
            """Fetch and cluster latest news from all sources."""
            category = argv[1] if len(argv) > 1 and argv[1] in ("news", "technology", "business", "science") else None
            _t = _StageTracker("📡 Haber Çekme İşlemi")
            _t.begin("Kaynaklardan RSS beslemeleri çekiliyor")
            items = core.fetch_all_news(category)
            _t.begin("Haberler kümeleniyor (benzerlik analizi)")
            clusters = core.cluster_stories(items)
            _t.end()

            # Top stories by source count
            top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:10]
            extra = [
                "",
                f"📊 **Özet:** {len(items)} haber maddesi, {len(clusters)} küme",
                "",
                "### 🔝 En Çok Kaynağa Sahip Haberler",
                "",
            ]
            for i, c in enumerate(top, 1):
                tiers = c["tier_count"]
                badge = "✅" if tiers.get("primary", 0) >= 2 else "🟡"
                tier_str = f"T0:{tiers.get('primary',0)} T1:{tiers.get('major',0)}"
                extra.append(f"{badge} **{i}.** {c['story_title'][:90]}")
                extra.append(f"   Kaynak: {c['source_count']} | {tier_str}")
                extra.append(f"   URL: {c.get('best_url', 'N/A')}")
                extra.append("")

            if len(clusters) > 10:
                extra.append(f"   _+{len(clusters)-10} küme daha (--limit ile gösterilebilir)_")

            return _t.report(extra)

        if sub == "verify":
            """Fetch, cluster, and cross-verify news."""
            category = argv[1] if len(argv) > 1 and argv[1] in ("news", "technology", "business", "science") else None
            limit = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 10

            _t = _StageTracker("🔍 Çapraz Doğrulama İşlemi")
            _t.begin("Kaynaklardan haberler çekiliyor")
            items = core.fetch_all_news(category)
            _t.begin("Haberler kümeleniyor")
            clusters = core.cluster_stories(items)
            _t.begin(f"En yüksek puanlı {limit} haber doğrulanıyor")
            verified_count = 0
            blocked_count = 0
            verified_list = []
            for cluster in clusters[:limit]:
                verification = core.cross_verify_story(cluster)
                if verification.is_safe_to_publish:
                    verified_count += 1
                else:
                    blocked_count += 1
                verified_list.append((cluster, verification))
            _t.end()

            extra = [
                "",
                f"📊 **Özet:** {len(items)} madde → {len(clusters)} küme | ✅ {verified_count} yayınlanabilir | ⛔ {blocked_count} bloke",
                "",
                "### Sonuçlar",
                "",
            ]
            for cluster, verification in verified_list:
                badge = "✅" if verification.is_safe_to_publish else "⛔"
                level_short = verification.verification_level.label.split("—")[0].strip()
                extra.append(f"{badge} **{cluster['story_title'][:80]}**")
                extra.append(f"   Seviye: {level_short} | Kaynak: {verification.sources_checked}")
                extra.append("")

            if len(clusters) > limit:
                extra.append(f"   _+{len(clusters)-limit} küme atlandı (--limit ile artırın)_")

            return _t.report(extra)

        if sub == "correct":
            """Issue a correction for a published news item directly."""
            if len(argv) < 2:
                return "Usage: /haber correct <slug> <error> [--retract]"
            slug = argv[1]
            is_retract = "--retract" in argv
            error_parts = [a for a in argv[2:] if not a.startswith("--")]
            error_desc = " ".join(error_parts) if error_parts else "Unspecified error"

            _t = _StageTracker("✏️ Düzeltme İşlemi")
            _t.begin(f"'{slug}' için {'geri çekme' if is_retract else 'düzeltme'} hazırlanıyor")
            result = core.issue_correction(slug, error_desc, "", is_retract)
            _t.end()

            extra = [
                "",
                "### 📋 İşlem Detayı",
                f"- **Slug:** {slug}",
                f"- **İşlem:** {'🔄 Geri Çekme' if is_retract else '✏️ Düzeltme'}",
                f"- **Hata:** {error_desc[:100]}",
            ]
            return _t.report(extra)

        if sub == "hallucination":
            """Run automated hallucination check on a draft."""
            if len(argv) < 2:
                return "Usage: /haber hallucination <slug>"
            slug = argv[1]

            _t = _StageTracker("🔬 Halüsinasyon Taraması")
            _t.begin(f"'{slug}' taslağı taranıyor")
            result = core.hallucination_check(slug)
            _t.end()

            if "error" in result:
                _t.fail(result["error"])
                return _t.report([f"\n❌ {result['error']}"])

            status = "✅ GEÇTİ" if result["pass"] else "❌ KALDI"
            color = "başarılı" if result["pass"] else "başarısız"
            extra = [
                "",
                f"**Durum:** {status}",
                "",
                "### 📊 Detaylı Rapor",
                f"- **Toplam Bulgu:** {result['total_findings']}",
                f"- **🔴 Yüksek Önem:** {result['high_severity']}",
                f"- **🟡 Orta Önem:** {result['medium_severity']}",
            ]

            if result.get("findings"):
                extra.extend(["", "### 🔍 Bulgular (ilk 10)"] )
                for f in result["findings"][:10]:
                    icon = "🔴" if f["severity"] == "high" else "🟡"
                    extra.append(f"  {icon} **[{f['type']}]** {f['message']}")
                    extra.append(f"     `{f['text'][:80]}`")

            return _t.report(extra)

        if sub == "sources":
            """List all configured news sources."""
            return core.get_source_summary()

        if sub == "publish":
            """Fetch, verify & create news runs."""
            category = argv[1] if len(argv) > 1 and argv[1] in ("news", "technology", "business", "science") else None
            limit = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 5
            auto = "--auto" in argv

            _t = _StageTracker("📰 Haber Yayınlama Süreci")
            _t.begin("Kaynaklardan haberler çekiliyor")
            items = core.fetch_all_news(category)
            _t.begin("Haberler kümeleniyor")
            clusters = core.cluster_stories(items)
            _t.begin(f"En iyi {limit} haber doğrulanıp yayına hazırlanıyor")
            results = []
            for c in sorted(clusters, key=lambda x: x.get("source_count", 0), reverse=True)[:limit]:
                results.append(core.publish_verified_news(c, human_review=not auto))
            _t.end()

            new_count = sum(1 for r in results if r.get("status") != "exists")
            exists_count = sum(1 for r in results if r.get("status") == "exists")

            extra = [
                "",
                f"📊 **Özet:** {len(items)} madde → {len(clusters)} küme | ✅ {new_count} yeni | ⏭️ {exists_count} zaten var",
                "",
                "### 📋 Yayınlanan Haberler",
                "",
            ]
            for r in results:
                slug = r.get("slug", "?")
                route = r.get("route", "?")
                state = r.get("initial_state", "?")
                ver = r.get("verification", {})
                level = ver.get("verification_label", "Belirsiz")[:50]
                status_icon = "✅" if r.get("status") != "exists" else "⏭️"
                extra.append(f"{status_icon} **{slug}**")
                extra.append(f"   Rota: {route} | Durum: {state}")
                extra.append(f"   Doğrulama: {level}")
                extra.append("")
            return _t.report(extra)

        if sub == "auto-publish":
            """Writer Agent: auto-fetch, verify, generate & publish directly."""
            limit = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 5
            category = argv[2] if len(argv) > 2 and argv[2] in ("news", "technology", "business", "science") else None

            _t = _StageTracker("🤖 Writer Agent — Otomatik Yayın")
            _t.begin("Writer Agent başlatılıyor")
            from .writer_agent import WriterAgent
            agent = WriterAgent(core)
            try:
                from agent.auxiliary_client import async_call_llm
                agent.set_llm(True)
            except ImportError:
                pass
            _t.begin(f"Haberler çekiliyor, doğrulanıyor ve yayınlanıyor (limit: {limit})")
            results = agent.auto_publish(max_articles=limit, category=category)
            _t.end()

            extra = [
                "",
                f"📊 **Rapor:** ✅ {results['published']} yayınlandı | ⏭️ {results['skipped']} atlandı | ❌ {results['failed']} başarısız",
                "",
                "### 🗞️ Yayınlanan Haberler",
                "",
            ]
            for a in results.get("articles", []):
                badge = "✅" if a.get("level") == "CONFIRMED" else "🟡"
                level_name = a.get("level", "?")
                extra.append(f"{badge} **{a.get('title', '?')[:80]}**")
                extra.append(f"   Seviye: {level_name}")
                extra.append("")
            if results.get("skipped", 0) > 0:
                extra.append(f"⏭️ {results['skipped']} haber zaten mevcut olduğu için atlandı")
            if results.get("failed", 0) > 0:
                extra.append(f"❌ {results['failed']} haber yayınlanamadı (Memos bağlantı hatası)")
            extra.append("\n💡 **İpucu:** `--limit` ile haber sayısını, `--category` ile kategori filtresi ayarlayın.")

            return _t.report(extra)

        # ── Legacy Commands ──

        if sub == "status":
            runs = core.active_runs
            if not runs.exists():
                return "📭 Henüz hiç run oluşturulmamış."
            lines = ["### 📊 Aktif Run Durumları", ""]
            total = 0
            state_counts = {}
            for r in runs.iterdir():
                if r.is_dir():
                    total += 1
                    state = core.get_state(r.name)
                    state_counts[state] = state_counts.get(state, 0) + 1
                    lines.append(f"  - **{r.name}** → `{state}`")
            lines.extend([
                "",
                f"**Toplam:** {total} run",
                f"**Durum dağılımı:** " + ", ".join(f"{k}: {v}" for k, v in sorted(state_counts.items())),
                "",
                "💡 Detaylı run durumu: `/haber state <slug>`",
            ])
            return "\n".join(lines)

        if sub == "new":
            idea = " ".join(argv[1:])
            if not idea:
                return "Usage: /haber new <idea>"

            _t = _StageTracker("🆕 Yeni Run Oluşturma")
            _t.begin("Fikir analiz ediliyor ve rota belirleniyor")
            res = core.create_run(idea)
            _t.end()

            if res.get("status") == "exists":
                extra = [
                    "",
                    f"⚠️ **{res['slug']}** zaten mevcut!",
                    f"   Dizin: `{res['path']}`",
                    "",
                    "💡 Mevcut run'u güncellemek için: `/haber state <slug>`",
                ]
            else:
                extra = [
                    "",
                    "### ✅ Oluşturulan Run",
                    f"- **Slug:** {res['slug']}",
                    f"- **Rota:** {res['route']}",
                    f"- **Dizin:** `{res['path']}`",
                    "",
                    "### 📝 Oluşturulan Dosyalar",
                    "  - `haber-object.md` — Run kimliği ve metadata",
                    "  - `idea.md` — Fikir ve rota kararı",
                    "  - `context.md` — Bağlam ve referanslar",
                    "",
                    "### 👣 Sonraki Adımlar",
                ]
                route = res.get("route", "ORIGINAL")
                if route == "VERIFIED":
                    extra.append("  - `/haber fetch` ile haberleri çekip doğrulayın")
                    extra.append("  - Veya `/haber publish` ile otomatik yayınlayın")
                else:
                    extra.append(f"  - `/haber brief {res['slug']} --llm` ile brief oluşturun")
                    extra.append(f"  - `/haber draft {res['slug']} --llm` ile taslak yazdırın")
                extra.append(f"  - `/haber state {res['slug']}` ile durumu görüntüleyin")

            return _t.report(extra)

        if sub == "route":
            idea = " ".join(argv[1:])
            if not idea:
                return "Usage: /haber route <idea> [source_hint]"
            source = argv[-1] if argv[-1] in ("verified", "internal", "external", "existing", "research") else ""
            if source:
                idea = " ".join(argv[1:-1])

            _t = _StageTracker("🧭 Rota Belirleme")
            _t.begin("Fikir analiz ediliyor")
            res = core.decide_route(idea, source)
            _t.end()

            route_icons = {
                "VERIFIED": "📡", "ORIGINAL": "✍️", "REPURPOSE": "♻️",
                "REWRITE": "🔄", "RESEARCH+IDEATE": "🔬",
            }
            icon = route_icons.get(res['route'], "📌")
            extra = [
                "",
                f"{icon} **Rota:** {res['route']}",
                f"  - **Gerekçe:** {res['rationale']}",
                f"  - **Kaynak Tipi:** {res['source_type']}",
                "",
                "💡 `/haber new \"{fikir}\"` ile run oluşturun.",
            ]
            return _t.report(extra)

        if sub == "state":
            if len(argv) < 2:
                # Tüm run'ların durumu
                active = list(core.active_runs.iterdir()) if core.active_runs.exists() else []
                if not active:
                    return "📭 Henüz hiç run oluşturulmamış."
                lines = ["### 🏁 Tüm Run Durumları", ""]
                for d in active:
                    if d.is_dir():
                        state = core.get_state(d.name)
                        actions = core.get_next_actions(d.name)
                        next_a = actions[0][:50] if actions else "—"
                        lines.append(f"  - **{d.name}** → `{state}` | 👣 {next_a}")
                return "\n".join(lines)
            slug = argv[1]
            state = core.get_state(slug)
            actions = core.get_next_actions(slug)
            lines = [
                f"### 🏁 Run Durumu: {slug}",
                "",
                f"  - **Mevcut Durum:** `{state}`",
                "",
                "### 👣 Sonraki Adımlar",
            ]
            if actions:
                for i, a in enumerate(actions, 1):
                    lines.append(f"  {i}. {a}")
            else:
                lines.append("  - ✅ Bu run tamamlanmış görünüyor.")
            lines.extend([
                "",
                "💡 Durum güncelleme: `/haber state <slug> --set <yeni_durum>`",
                f"   Mevcut geçişler: — (STATE_TRANSITIONS import edilemedi)",
            ])
            return "\n".join(lines)

        if sub == "brief":
            if len(argv) < 2:
                return "Usage: /haber brief <slug> [--llm]"
            slug = argv[1]
            use_llm = "--llm" in argv

            _t = _StageTracker(f"📝 Brief Oluşturma: {slug}")
            _t.begin(f"Durum senkronize ediliyor")
            core.sync_state(slug)
            if use_llm:
                _t.begin("LLM ile brief oluşturuluyor")
                try:
                    res = core.generate_brief(slug, use_llm=True)
                    _t.end()
                    extra = [
                        "",
                        "### ✅ Brief Hazır",
                        f"  - Dosya: `{core.active_runs / slug / 'brief.md'}`",
                        "",
                        "👣 Sonraki adım: `/haber draft {slug}`",
                    ]
                    return _t.report(extra)
                except Exception as e:
                    _t.fail(f"LLM hatası: {str(e)[:60]}")
                    # Fall through to manual
            core.update_state(slug, "brief_ready")
            _t.end()
            extra = [
                "",
                "### ℹ️ Manuel Brief",
                f"  - Slug: **{slug}** durumu `brief_ready` olarak ayarlandı",
                f"  - `brief.md` dosyasını el ile oluşturun",
                "",
                "💡 LLM ile otomatik: `/haber brief {slug} --llm`",
            ]
            return _t.report(extra)

        if sub == "draft":
            if len(argv) < 2:
                return "Usage: /haber draft <slug> [--llm]"
            slug = argv[1]
            use_llm = "--llm" in argv

            _t = _StageTracker(f"✍️ Taslak Oluşturma: {slug}")
            if use_llm:
                _t.begin("LLM ile taslak oluşturuluyor")
                try:
                    res = core.generate_draft(slug, use_llm=True)
                    _t.end()
                    extra = [
                        "",
                        "### ✅ Taslak Hazır",
                        f"  - Dosya: `{core.active_runs / slug / 'draft-package.md'}`",
                        "",
                        "👣 Sonraki adım: `/haber verify-draft {slug}`",
                    ]
                    return _t.report(extra)
                except Exception as e:
                    _t.fail(f"LLM hatası: {str(e)[:60]}")
            core.update_state(slug, "drafting")
            _t.end()
            extra = [
                "",
                "### ℹ️ Manuel Taslak",
                f"  - Slug: **{slug}** → `drafting`",
                f"  - `draft-package.md` dosyasını el ile oluşturun",
                "",
                "💡 LLM ile otomatik: `/haber draft {slug} --llm`",
            ]
            return _t.report(extra)

        if sub == "verify-draft":
            if len(argv) < 2:
                return "Usage: /haber verify-draft <slug>"
            slug = argv[1]

            _t = _StageTracker(f"🔍 Taslak Doğrulama: {slug}")
            _t.begin("Taslak taranıyor (slop + halüsinasyon)")
            core.update_state(slug, "verification")
            path = core.active_runs / slug / "draft-package.md"
            if not path.exists():
                _t.fail("Taslak bulunamadı")
                return _t.report(["\n❌ `draft-package.md` bulunamadı. Önce `/haber draft` çalıştırın."])
            _t.end()
            extra = [
                "",
                f"✅ **{slug}** → `verification` durumuna alındı",
                "",
                "### 🛠️ Yapılacaklar",
                "  1. `/haber hallucination {slug}` — Halüsinasyon taraması",
                "  2. `/haber scan {slug}` — Slop taraması",
                "  3. `/haber correct {slug}` — Hata varsa düzelt",
                "",
                "💡 Tüm testler geçerse: `/haber post {slug}`",
            ]
            return _t.report(extra)

        if sub == "scan":
            if len(argv) < 2:
                return "Usage: /haber scan <slug>"
            slug = argv[1]

            _t = _StageTracker(f"🔎 Slop Taraması: {slug}")
            _t.begin("Taslak okunuyor")
            path = core.active_runs / slug / "draft-package.md"
            if not path.exists():
                return f"❌ `draft-package.md` bulunamadı: {slug}"
            text = path.read_text(encoding="utf-8")
            _t.begin("54+ slop kalıbı taranıyor")
            res = core.scan_slop(text)
            _t.end()

            total = res['tier1_count'] + res['tier2_count'] + res['tier3_count'] + res['bonus_count']
            verdict = "✅ TEMİZ" if total == 0 else "⚠️ SORUNLU" if res['tier1_count'] == 0 else "❌ KRİTİK"
            extra = [
                "",
                f"**Karar:** {verdict} | **Puan:** {res['score']}",
                "",
                "### 📊 Kategori Dağılımı",
                f"  - 🔴 **Tier 1 (Kritik):** {res['tier1_count']}",
                f"  - 🟠 **Tier 2 (Yüksek):** {res['tier2_count']}",
                f"  - 🟡 **Tier 3 (Orta):** {res['tier3_count']}",
                f"  - 🔵 **Bonus (Ton):** {res['bonus_count']}",
            ]
            if res.get('all_findings'):
                extra.extend(["", "### 🔍 Tespit Edilenler (ilk 8)"])
                for f in res['all_findings'][:8]:
                    extra.append(f"  - {f[:90]}")
            else:
                extra.append("\n✅ Hiçbir slop kalıbı bulunamadı.")
            return _t.report(extra)

        if sub == "score":
            if len(argv) < 2:
                return "Usage: /haber score <slug>"
            slug = argv[1]

            _t = _StageTracker(f"📊 Puanlama: {slug}")
            _t.begin("Taslak okunuyor")
            path = core.active_runs / slug / "draft-package.md"
            if not path.exists():
                return f"❌ Draft bulunamadı: {slug}"
            text = path.read_text(encoding="utf-8")
            _t.begin("12 kriter üzerinden değerlendirme")
            slop = core.scan_slop(text)
            _t.end()

            total_slop = slop['tier1_count'] + slop['tier2_count'] + slop['tier3_count'] + slop['bonus_count']
            # Beraberlik skoru: düşük slop = yüksek puan
            clarity_score = max(0, 10 - total_slop)
            extra = [
                "",
                "### 📋 Slop Analizi",
                f"  - **Slop Skoru:** {slop['score']}",
                f"  - **🔴 Tier 1:** {slop['tier1_count']} | **🟠 Tier 2:** {slop['tier2_count']}",
                f"  - **🟡 Tier 3:** {slop['tier3_count']} | **🔵 Bonus:** {slop['bonus_count']}",
                f"  - **Tahmini Netlik:** {clarity_score}/10",
                "",
                "💡 Tam rubrik (0-12) için: `haber_kurator_manager action='score'`",
            ]
            return _t.report(extra)

        if sub == "audit":
            _t = _StageTracker("🔍 Sistem Denetimi")
            _t.begin("Tüm bileşenler taranıyor")
            report = core.audit()
            _t.end()
            extra = ["", report[:2000]] if report else ["\n✅ Sistem temiz."]
            return _t.report(extra)

        if sub == "setup":
            _t = _StageTracker("⚙️ Kurulum")
            _t.begin("Dizin yapısı oluşturuluyor")
            result = core.setup()
            _t.end()
            return _t.report([f"\n{result}"])
        
        if sub == "signal":
            src = argv[1] if len(argv) > 1 else "x"

            _t = _StageTracker(f"📶 Sinyal Taraması: {src.upper()}")
            _t.begin(f"{src.upper()} kaynağı taranıyor")
            signals = core.process_signal(src)
            _t.end()

            extra = [""]
            if signals:
                extra.append(f"**{len(signals)} sinyal bulundu:**")
                extra.append("")
                for i, s in enumerate(signals, 1):
                    extra.append(f"  {i}. {s[:120]}")
            else:
                extra.append("📭 Sinyal bulunamadı.")
            return _t.report(extra)

        if sub == "postmortem":
            if len(argv) < 2:
                return "Usage: /haber postmortem <slug> [--okunma N] [--likes N]"
            slug = argv[1]

            _t = _StageTracker(f"📊 Postmortem Analiz: {slug}")
            _t.begin("Run durumu kontrol ediliyor")
            state = core.get_state(slug)
            if state == "published":
                core.update_state(slug, "feedback_24h")
                _t.end()
                extra = [
                    "",
                    f"✅ **{slug}** → `feedback_24h` aşamasına geçirildi",
                    "",
                    "### 📋 Toplanması Gereken Metrikler",
                    "  - Okunma sayısı",
                    "  - Beğeni/etkileşim",
                    "  - Kaynak performansı",
                    "",
                    "💡 `/haber postmortem {slug} --okunma 150 --likes 12` ile metrik gir",
                ]
                return _t.report(extra)
            elif state == "feedback_24h":
                okunma = 0
                likes = 0
                for i, a in enumerate(argv):
                    if a == "--okunma" and i + 1 < len(argv):
                        okunma = int(argv[i + 1])
                    elif a == "--likes" and i + 1 < len(argv):
                        likes = int(argv[i + 1])
                _t.begin("Postmortem raporu hazırlanıyor")
                core.update_state(slug, "feedback_72h")
                _t.end()
                extra = [
                    "",
                    f"✅ **{slug}** → `feedback_72h` derin analiz",
                    f"  - Okunma: {okunma}, Beğeni: {likes}" if okunma or likes else "",
                    "",
                    "💡 Öğrenilenler kaydedildikten sonra: `/haber archive {slug}`",
                ]
                return _t.report(extra)
            else:
                return f"📊 **{slug}** (durum: {state}). Postmortem sadece `published` run'lar için."

        if sub == "post":
            if len(argv) < 2:
                return "Usage: /haber post <slug> [--visibility PUBLIC|PRIVATE|PROTECTED]"
            slug = argv[1]

            _t = _StageTracker(f"📤 Memos'a Yayınlama: {slug}")
            _t.begin("Taslak okunuyor")
            draft_path = core.active_runs / slug / "draft-package.md"
            if not draft_path.exists():
                return f"❌ Taslak bulunamadı: {slug}"
            draft = draft_path.read_text(encoding="utf-8")
            content = draft.split("draft:")[1].split("rubric_self_assessment")[0].strip() if "draft:" in draft else draft
            _t.begin("Memos API'sine gönderiliyor")
            from .memos_cli import post_memo
            try:
                post_memo(content)
                core.update_state(slug, "published")
                _t.end()
                extra = [
                    "",
                    f"✅ **{slug}** başarıyla Memos'a yayınlandı!",
                    f"  - Platform: memos.googig.cloud",
                    "",
                    "👣 Sonraki adım: `/haber postmortem {slug}` ile metrik toplayın",
                ]
                return _t.report(extra)
            except Exception as e:
                _t.fail(str(e)[:80])
                return _t.report([f"\n❌ Yayınlama başarısız: {str(e)[:100]}"])

        if sub == "archive":
            if len(argv) < 2:
                return "Usage: /haber archive <slug> [--force]"
            slug = argv[1]
            force = "--force" in argv

            _t = _StageTracker(f"🗄️ Arşivleme: {slug}")
            _t.begin("Run arşivleniyor")
            result = core.archive_run(slug, force=force)
            _t.end()
            return _t.report([f"\n{result}"])

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
                return "📭 Hiç run bulunamadı."
            lines = ["### 🗃️ Tüm Run'lar", ""]
            state_counts = {}
            for r in runs:
                state = r.get("state", "?")
                route = r.get("route", "?")
                status = r.get("status", "?")
                files = len(r.get("files", []))
                state_counts[state] = state_counts.get(state, 0) + 1
                lines.append(f"  - **{r['slug']}** → `{state}` | {route} | {status} ({files} dosya)")
            lines.extend([
                "",
                f"**Toplam:** {len(runs)} run",
                f"**Dağılım:** " + ", ".join(f"{k}: {v}" for k, v in sorted(state_counts.items())),
                "",
                "💡 Detay: `/haber state <slug>`",
            ])
            return "\n".join(lines)

        if sub == "search":
            if len(argv) < 2:
                return "Usage: /haber search <query>"
            query = " ".join(argv[1:])

            _t = _StageTracker(f"🔎 Run Arama: {query}")
            _t.begin("Run içerikleri taranıyor")
            results = core.search_runs(query)
            _t.end()

            if not results:
                return _t.report(["\n📭 Sonuç bulunamadı."])
            extra = [
                "",
                f"**{len(results)} sonuç bulundu** (ilk 10):",
                "",
            ]
            for r in results[:10]:
                extra.append(f"  - **{r['slug']}** → {r['file']} ({r['state']})")
            if len(results) > 10:
                extra.append(f"\n  _+{len(results)-10} sonuç daha..._")
            return _t.report(extra)

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
