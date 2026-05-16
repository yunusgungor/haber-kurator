"""Haber Kuratör Plugin v3.1.0 — News Verification System.

Complete multi-source news verification platform:
- Fetches from world's leading proven-accurate media sources (Reuters, AP, AFP, BBC, etc.)
- Cross-verifies every claim across 2+ independent sources
- 4-tier source credibility system
- Hallucination protection — Writer Agent restricted to source-attributed facts
- Correction workflow for post-publication errors
- 8-state lifecycle: captured → fact_checking → cross_verified → published → correction

Registers tools, hooks, slash commands, and CLI for the Haber Kuratör workflow.
"""

from pathlib import Path
from typing import Any, Dict, Optional
import logging

from .haber_kurator_core import HaberKuratorCore, tool_haber_kurator_manager, tool_haber_kurator_retriever
from .cli import register_cli

logger = logging.getLogger(__name__)

VERSION = "3.1.0"


def register(ctx: Any) -> None:
    root = Path(__file__).parent
    core = HaberKuratorCore(root)

    # ══════════════════════════════════════════════════════════════
    # TOOL: haber_kurator_manager (News pipeline actions only)
    # ══════════════════════════════════════════════════════════════

    manager_schema = {
        "name": "haber_kurator_manager",
        "description": (
            "Complete Haber Kuratör management — News Verification Engine v3.1.0.\n"
            "News pipeline: fetch_news → verify_news → publish_verified → create_news_run.\n"
            "Verification: cross_verify_story → hallucination_check → issue_correction.\n\n"
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
                        # NEWS VERIFICATION
                        "fetch_news", "verify_news", "publish_verified",
                        "cross_verify_story",
                        # NEWS SEARCH
                        "search_news",
                        # Writer Agent — Auto Publish
                        "auto_publish",
                        # Hallucination Guard
                        "hallucination_check",
                        # Correction
                        "check_correction", "issue_correction",
                        # Run management
                        "update_state", "get_state", "sync_state",
                        "get_next_actions",
                        # Quality
                        "scan_slop",
                        # Search runs
                        "search_runs", "get_all_runs",
                        # Archive
                        "archive_run",
                    ],
                    "description": "Action to perform in the Haber Kuratör pipeline",
                },
                "slug": {"type": "string", "description": "Content slug for existing runs"},
                "state": {"type": "string", "description": "New state for update_state"},
                "text": {"type": "string", "description": "Text to scan for slop patterns"},
                "query": {"type": "string", "description": "Search query for run search"},
                "search_query": {"type": "string", "description": "Search query for news search"},
                "max_results": {"type": "integer", "description": "Max search results for search_news (default: 20)"},
                "language": {"type": "string", "description": "Language for search_news (default: 'tr')"},
                "country": {"type": "string", "description": "Country for search_news (default: 'TR')"},
                "include_archived": {"type": "boolean", "description": "Include archived runs", "default": True},
                "category": {"type": "string", "enum": ["news", "technology", "business", "science"],
                             "description": "News category filter"},
                "limit": {"type": "integer", "description": "Max results limit"},
                "human_review": {"type": "boolean", "description": "Require human review (default: true)", "default": True},
                "cluster_data": {"type": "object", "description": "Story cluster data for cross_verify_story"},
                "error_description": {"type": "string", "description": "Error description for issue_correction"},
                "correct_information": {"type": "string", "description": "Correct information for issue_correction"},
                "retract": {"type": "boolean", "description": "Retract the story entirely (vs correction)", "default": False},
            },
            "required": ["action"],
        },
    }

    ctx.register_tool(
        name="haber_kurator_manager",
        toolset="haber",
        schema=manager_schema,
        handler=lambda args, **kw: tool_haber_kurator_manager(core, args, **kw),
        description="Complete Haber Kuratör pipeline management tool — News Verification Engine v3.1.0.",
        is_async=True,
    )

    # ══════════════════════════════════════════════════════════════
    # TOOL: haber_kurator_retriever
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
                "topic": {"type": "string", "description": "Topic filter for learnings"},
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
    # SLASH COMMAND: /haber — News Only
    # ══════════════════════════════════════════════════════════════

    class _StageTracker:
        """Aşamaları süre ve durumla birlikte izler. Sonunda rapor üretir."""

        def __init__(self, title: str):
            self.title = title
            self.stages: list[dict] = []
            self._start = __import__("time").time()
            self._stage_start = self._start

        def begin(self, name: str, icon: str = "⏳"):
            now = __import__("time").time()
            if self.stages and self.stages[-1]["status"] == "running":
                self.stages[-1]["status"] = "done"
                self.stages[-1]["duration"] = f"{now - self._stage_start:.1f}s"
            self._stage_start = now
            self.stages.append({"icon": icon, "name": name, "status": "running", "duration": "..."})

        def fail(self, msg: str = ""):
            now = __import__("time").time()
            if self.stages and self.stages[-1]["status"] == "running":
                self.stages[-1]["status"] = "fail"
                self.stages[-1]["duration"] = f"{now - self._stage_start:.1f}s"
                if msg:
                    self.stages[-1]["name"] += f" — {msg}"

        def end(self):
            now = __import__("time").time()
            if self.stages and self.stages[-1]["status"] == "running":
                self.stages[-1]["status"] = "done"
                self.stages[-1]["duration"] = f"{now - self._stage_start:.1f}s"

        def report(self, extra_lines: list[str] | None = None) -> str:
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
                "Usage: /haber [fetch|verify|publish|correct|hallucination|"
                "auto-publish|search|ara|sources|status|audit|setup|runs|archive]"
            )

        sub = argv[0]

        _COMMANDS = {"fetch", "verify", "correct", "hallucination",
                     "sources", "publish", "auto-publish", "search",
                     "ara", "status", "audit", "setup", "runs", "archive"}

        if sub not in _COMMANDS:
            return f"Bilinmeyen komut: '{sub}'. Komutlar: fetch, verify, publish, auto-publish, correct, hallucination, sources, search, status, audit, setup, runs, archive"

        if sub == "fetch":
            category = argv[1] if len(argv) > 1 and argv[1] in ("news", "technology", "business", "science") else None
            _t = _StageTracker("📡 Haber Çekme İşlemi")
            ctx.reply("⏳ Haber kaynakları taranıyor, RSS beslemeleri çekiliyor...")
            _t.begin("Kaynaklardan RSS beslemeleri çekiliyor")
            items = core.fetch_all_news(category)
            ctx.reply(f"✅ {len(items)} haber maddesi çekildi, kümeleniyor...")
            _t.begin("Haberler kümeleniyor (benzerlik analizi)")
            clusters = core.cluster_stories(items)
            if not clusters:
                _t.fail("Hiç haber kümesi oluşmadı")
                ctx.reply("❌ Haber kaynaklarından veri alınamadı. RSS beslemeleri geçici olarak erişilemez olabilir.")
                return _t.report([f"\n❌ {len(items)} haber maddesinden küme oluşmadı."])
            _t.end()
            ctx.reply(f"✅ Kümelenme tamamlandı: {len(items)} madde → {len(clusters)} küme")
            top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:10]
            extra = ["", f"📊 **Özet:** {len(items)} haber maddesi, {len(clusters)} küme", "",
                     "### 🔝 En Çok Kaynağa Sahip Haberler", ""]
            for i, c in enumerate(top, 1):
                tiers = c["tier_count"]
                badge = "✅" if tiers.get("primary", 0) >= 2 else "🟡"
                tier_str = f"T0:{tiers.get('primary',0)} T1:{tiers.get('major',0)}"
                extra.append(f"{badge} **{i}.** {c['story_title'][:90]}")
                extra.append(f"   Kaynak: {c['source_count']} | {tier_str}")
                extra.append(f"   URL: {c.get('best_url', 'N/A')}")
                extra.append("")
            if len(clusters) > 10:
                extra.append(f"   _+{len(clusters)-10} küme daha_")
            return _t.report(extra)

        if sub in ("ara", "search"):
            if len(argv) < 2:
                return "Usage: /haber ara <arama metni> [--language=tr|en] [--country=TR|US]"
            query_parts = []
            max_results = 20
            language = "tr"
            country = "TR"
            for a in argv[1:]:
                if a.startswith("--max="):
                    try: max_results = int(a.split("=", 1)[1])
                    except ValueError: pass
                elif a.startswith("--language="):
                    language = a.split("=", 1)[1]
                elif a.startswith("--country="):
                    country = a.split("=", 1)[1]
                else:
                    query_parts.append(a)
            query = " ".join(query_parts)
            if not query:
                return "Usage: /haber ara <arama metni>"
            _t = _StageTracker(f"🔍 Haber Arama: '{query[:60]}...'")
            ctx.reply(f"⏳ '{query}' için haber kaynakları taranıyor...")
            _t.begin("Google Haberler RSS taranıyor")
            result = core.search_news(query, max_results, language, country)
            if result["total_results"] == 0:
                _t.fail("Sonuç bulunamadı")
                ctx.reply(f"❌ '{query}' için haber bulunamadı.")
                return _t.report([f"\n❌ '{query}' için sonuç bulunamadı."])
            ctx.reply(f"✅ {result['total_results']} kaynak bulundu, {result['clusters']} haber kümesi oluşturuluyor...")
            _t.begin("Haberler kümeleniyor ve doğrulanıyor")
            _t.end()
            verified = result["verified_count"]
            total = result["clusters"]
            ctx.reply(f"✅ Doğrulama tamamlandı: {verified}/{total} haber kümesi doğrulandı")
            extra = ["", f"📊 **Özet:** {result['total_results']} kaynak → {result['clusters']} haber kümesi | ✅ {verified} doğrulandı", "", "### 📰 Bulunan Haberler", ""]
            for r in result["results"][:5]:
                v = r["verification"]
                c = r["cluster"]
                badge = "✅" if v["is_safe_to_publish"] else "⚠️"
                level_short = v["verification_label"].split("—")[0].strip() if "—" in v["verification_label"] else v["verification_label"]
                extra.append(f"{badge} **{c['story_title'][:90]}**")
                extra.append(f"   🏷️ {level_short} | 📡 {c['source_count']} kaynak")
                extra.append(f"   🔗 {c.get('best_url', 'N/A')}")
                extra.append("")
            return _t.report(extra)

        if sub == "verify":
            category = argv[1] if len(argv) > 1 and argv[1] in ("news", "technology", "business", "science") else None
            limit = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 10
            _t = _StageTracker("🔍 Çapraz Doğrulama İşlemi")
            ctx.reply("⏳ Haber kaynakları taranıyor...")
            _t.begin("Kaynaklardan haberler çekiliyor")
            items = core.fetch_all_news(category)
            ctx.reply(f"✅ {len(items)} haber çekildi, kümeleniyor...")
            _t.begin("Haberler kümeleniyor")
            clusters = core.cluster_stories(items)
            if not clusters:
                _t.fail("Hiç haber kümesi oluşmadı")
                ctx.reply("❌ Haber kaynaklarından veri alınamadı veya kümelenecek haber bulunamadı.")
                return _t.report([f"\n❌ {len(items)} haber maddesinden küme oluşmadı. Kaynaklar geçici olarak erişilemez olabilir."])
            ctx.reply(f"✅ {len(clusters)} küme oluşturuldu. {limit} haber doğrulanıyor...")
            _t.begin(f"En yüksek puanlı {limit} haber doğrulanıyor")
            verified_count = 0; blocked_count = 0; verified_list = []
            for cluster in clusters[:limit]:
                verification = core.cross_verify_story(cluster)
                if verification.is_safe_to_publish: verified_count += 1
                else: blocked_count += 1
                verified_list.append((cluster, verification))
            _t.end()
            ctx.reply(f"✅ Doğrulama tamamlandı: ✅ {verified_count} yayınlanabilir | ⛔ {blocked_count} bloke")
            extra = ["", f"📊 **Özet:** {len(items)} madde → {len(clusters)} küme | ✅ {verified_count} yayınlanabilir | ⛔ {blocked_count} bloke", "", "### Sonuçlar", ""]
            for cluster, verification in verified_list:
                badge = "✅" if verification.is_safe_to_publish else "⛔"
                level_short = verification.verification_level.label.split("—")[0].strip()
                extra.append(f"{badge} **{cluster['story_title'][:80]}**")
                extra.append(f"   Seviye: {level_short} | Kaynak: {verification.sources_checked}")
                extra.append("")
            return _t.report(extra)

        if sub == "correct":
            if len(argv) < 2:
                return "Usage: /haber correct <slug> [--retract]"
            slug = argv[1]
            is_retract = "--retract" in argv
            error_parts = [a for a in argv[2:] if not a.startswith("--")]
            error_desc = " ".join(error_parts) if error_parts else "Unspecified error"
            _t = _StageTracker("✏️ Düzeltme İşlemi")
            ctx.reply(f"⏳ '{slug}' için düzeltme hazırlanıyor...")
            _t.begin(f"Düzeltme hazırlanıyor")
            result = core.issue_correction(slug, error_desc, "", is_retract)
            _t.end()
            ctx.reply(f"✅ Düzeltme kaydedildi: {slug}")
            extra = ["", "### 📋 İşlem Detayı", f"- **Slug:** {slug}", f"- **İşlem:** {'Geri Çekme' if is_retract else 'Düzeltme'}", f"- **Hata:** {error_desc[:100]}"]
            return _t.report(extra)

        if sub == "hallucination":
            if len(argv) < 2:
                return "Usage: /haber hallucination <slug>"
            slug = argv[1]
            _t = _StageTracker("🔬 Halüsinasyon Taraması")
            ctx.reply(f"⏳ '{slug}' taslağı taranıyor...")
            _t.begin("Taslak taranıyor")
            result = core.hallucination_check(slug)
            _t.end()
            if "error" in result:
                return _t.report([f"\n❌ {result['error']}"])
            status = "✅ GEÇTİ" if result.get("pass") else "❌ KALDI"
            extra = ["", f"**Durum:** {status}", "", "### 📊 Detaylı Rapor",
                     f"- **Toplam Bulgu:** {result['total_findings']}",
                     f"- **🔴 Yüksek Önem:** {result['high_severity']}",
                     f"- **🟡 Orta Önem:** {result['medium_severity']}"]
            if result.get("findings"):
                extra.extend(["", "### 🔍 Bulgular (ilk 10)"])
                for f in result["findings"][:10]:
                    icon = "🔴" if f["severity"] == "high" else "🟡"
                    extra.append(f"  {icon} **[{f['type']}]** {f['message']}")
            return _t.report(extra)

        if sub == "sources":
            return core.get_source_summary()

        if sub == "publish":
            category = argv[1] if len(argv) > 1 and argv[1] in ("news", "technology", "business", "science") else None
            limit = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 5
            auto = "--auto" in argv
            _t = _StageTracker("📰 Haber Yayınlama")
            ctx.reply("⏳ Haberler çekiliyor, doğrulanıyor...")
            _t.begin("Kaynaklardan haberler çekiliyor")
            items = core.fetch_all_news(category)
            ctx.reply(f"✅ {len(items)} haber çekildi, kümeleniyor...")
            _t.begin("Haberler kümeleniyor")
            clusters = core.cluster_stories(items)
            if not clusters:
                _t.fail("Hiç haber kümesi oluşmadı")
                ctx.reply("❌ Haber kaynaklarından veri alınamadı veya kümelenecek haber bulunamadı.")
                return _t.report([f"\n❌ {len(items)} haber maddesinden küme oluşmadı."])
            ctx.reply(f"✅ {len(clusters)} küme oluşturuldu.")
            _t.begin("Yayınlanıyor")
            results = []
            for c in sorted(clusters, key=lambda x: x.get("source_count", 0), reverse=True)[:limit]:
                results.append(core.publish_verified_news(c, human_review=not auto))
            _t.end()
            new_count = sum(1 for r in results if r.get("status") != "exists")
            exists_count = sum(1 for r in results if r.get("status") == "exists")
            extra = ["", f"📊 **Özet:** {new_count} yeni | ⏭️ {exists_count} mevcut", "", "### Yayınlanan Haberler", ""]
            for r in results:
                status_icon = "✅" if r.get("status") != "exists" else "⏭️"
                extra.append(f"{status_icon} **{r.get('slug', '?')}** — {r.get('route', '?')}")
            return _t.report(extra)

        if sub == "auto-publish":
            limit = int(argv[1]) if len(argv) > 1 and argv[1].isdigit() else 5
            category = argv[2] if len(argv) > 2 and argv[2] in ("news", "technology", "business", "science") else None
            _t = _StageTracker("🤖 Writer Agent — Otomatik Yayın")
            ctx.reply("⏳ Writer Agent başlatılıyor...")
            from .writer_agent import WriterAgent
            agent = WriterAgent(core)
            try:
                from agent.auxiliary_client import async_call_llm
                agent.set_llm(True)
            except ImportError:
                pass
            _t.begin("Haberler işleniyor")
            results = agent.auto_publish(max_articles=limit, category=category)
            _t.end()
            ctx.reply(f"✅ Otomatik yayın: ✅ {results['published']} | ⏭️ {results['skipped']} | ❌ {results['failed']}")
            extra = ["", f"📊 **Rapor:** ✅ {results['published']} yayın | ⏭️ {results['skipped']} atlandı | ❌ {results['failed']} başarısız", "", "### 🗞️ Yayınlanan Haberler", ""]
            for a in results.get("articles", []):
                badge = "✅" if a.get("level") == "CONFIRMED" else "🟡"
                extra.append(f"{badge} **{a.get('title', '?')[:80]}**")
            return _t.report(extra)

        if sub == "status":
            runs = core.active_runs
            if not runs.exists():
                return "📭 Henüz hiç run oluşturulmamış."
            lines = ["### 📊 Aktif Run Durumları", ""]
            total = 0; state_counts = {}
            for r in runs.iterdir():
                if r.is_dir():
                    total += 1
                    state = core.get_state(r.name)
                    state_counts[state] = state_counts.get(state, 0) + 1
                    lines.append(f"  - **{r.name}** → `{state}`")
            lines.extend(["", f"**Toplam:** {total} run",
                          f"**Dağılım:** " + ", ".join(f"{k}: {v}" for k, v in sorted(state_counts.items()))])
            return "\n".join(lines)

        if sub == "audit":
            _t = _StageTracker("🔍 Sistem Denetimi")
            ctx.reply("⏳ Sistem denetleniyor...")
            _t.begin("Tüm bileşenler taranıyor")
            report = core.audit()
            _t.end()
            return _t.report(["", report[:2000]] if report else ["\n✅ Sistem temiz."])

        if sub == "setup":
            _t = _StageTracker("⚙️ Kurulum")
            ctx.reply("⏳ Dizin yapısı oluşturuluyor...")
            _t.begin("Kurulum yapılıyor")
            result = core.setup()
            _t.end()
            return _t.report([f"\n{result}"])

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
            lines.extend(["", f"**Toplam:** {len(runs)} run",
                          f"**Dağılım:** " + ", ".join(f"{k}: {v}" for k, v in sorted(state_counts.items()))])
            return "\n".join(lines)

        if sub == "archive":
            if len(argv) < 2:
                return "Usage: /haber archive <slug>"
            slug = argv[1]
            force = "--force" in argv
            return core.archive_run(slug, force=force)

        return f"Bilinmeyen komut: {sub}"

    ctx.register_command(
        "haber",
        handler=handle_slash,
        description="Haber Kuratör v3.1.0 — News Verification System. Fetch, verify, publish, correct.",
        args_hint="[fetch|verify|publish|correct|hallucination|search|sources|status|audit|setup|runs|archive]",
    )

    # ══════════════════════════════════════════════════════════════
    # CLI COMMAND: hermes haber
    # ══════════════════════════════════════════════════════════════

    ctx.register_cli_command(
        name="haber",
        help="Haber Kuratör v3.1.0 — News Verification System",
        setup_fn=lambda sub: register_cli(sub, core),
        description=(
            "Haber Kuratör News Verification Engine v3.1.0.\n"
            "Multi-source news fetching → cross-verification → fact-check → publish.\n"
            "8-state lifecycle, 4 credibility tiers.\n"
            "Powered by Reuters, AP, AFP, BBC, Bloomberg, WSJ and more."
        ),
    )

    # ══════════════════════════════════════════════════════════════
    # HOOKS
    # ══════════════════════════════════════════════════════════════

    def on_session_start(**kwargs):
        logger.info("Haber Kuratör v%s — News Verification Engine started.", VERSION)

    def post_tool_call(tool_name: str, args: Dict[str, Any], result: str, **kwargs):
        from pathlib import Path
        if tool_name not in ("write_file", "write_to_file", "create_file"):
            return
        target_path = args.get("TargetFile", "") or args.get("path", "") or args.get("file_path", "")
        if target_path and ("runs/active/" in target_path or "runs\\active\\" in target_path):
            path = Path(target_path)
            try:
                slug = path.parent.name
                filename = path.name
                if filename == "fact-check-report.md":
                    try:
                        core.update_state(slug, "cross_verified")
                        logger.info("Auto-updated %s to cross_verified", slug)
                    except Exception:
                        pass
                elif filename == "correction.md":
                    try:
                        core.update_state(slug, "correction_needed")
                        logger.info("Auto-updated %s to correction_needed", slug)
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
            description="Haber Kuratör v3.1.0 — News Verification System: multi-source fetch, cross-verify, fact-check, publish.",
        )

    logger.info("Haber Kuratör v%s (News Verification Engine) registered.", VERSION)
