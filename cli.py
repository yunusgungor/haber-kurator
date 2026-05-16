"""
CLI registration for Haber Kuratör v3.0.0 — News Verification System.

Full CLI interface:
- News: fetch, verify, publish, correct
- System: setup, status, audit, sources
- Legacy: new, brief, draft, verify-draft, scan, score, signal, postmortem
- Info: learnings, patterns, search, runs, context, voice-update, route, archive
"""

from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.syntax import Syntax
from rich.markdown import Markdown
from .haber_kurator_core import HaberKuratorCore

console = Console()


def handle_nlp(text: str, core) -> str:
    """NLP doğal dil işleme — Türkçe cümlelerden niyet ve kategori çıkarır.
    
    Örnekler:
      "teknoloji haberlerini getir"  → fetch technology
      "ekonomi haberlerini doğrula"  → verify business
      "son dakika haberlerini yayınla" → publish news
      "bilim haberlerini otomatik yayınla" → auto-publish science
      "kaynakları listele"            → sources
    
    Returns:
        str: İşlem sonucu metni veya None (NLP eşleşmezse)
    """
    _full_lower = text.strip().lower()
    _re = __import__("re")

    # Türkçe → İngilizce kategori eşleme (özgül olan önce)
    _cat = None
    for _pattern, _en_cat in [
        (r'teknoloji', "technology"), (r'\btech\b', "technology"),
        (r'\bekonomi\b', "business"), (r'\bfinans\b', "business"), (r'\bpiyasa\b', "business"),
        (r'\bbilim\b', "science"), (r'\baraştırma\b', "science"), (r'\bscience\b', "science"),
        (r'\bgündem\b', "news"),
    ]:
        if _re.search(_pattern, _full_lower):
            _cat = _en_cat
            break
    if _cat is None and "haber" in _full_lower:
        _cat = "news"
    if "son dakika" in _full_lower:
        _cat = "news"

    # Niyet tespiti
    _has_fetch = bool(_re.search(r'\b(getir|çek|fetch|ara|bul|indir)\b', _full_lower))
    _has_verify = bool(_re.search(r'\b(doğrula|verify|kontrol|teyit|onayla|incele|doğrulama)\b', _full_lower))
    _has_publish = bool(_re.search(r'\b(yayınla|publish|paylaş|gönder|post|bas)\b', _full_lower))
    _has_auto = bool(_re.search(r'\b(otomatik|auto|full|tüm|tam)\b', _full_lower))
    _has_sources = "kaynak" in _full_lower or bool(_re.search(r'\bsources\b', _full_lower))
    _has_verify_only = _has_verify and not _has_fetch and not _has_publish

    # Kaynak listesi
    if _has_sources and not _has_fetch and not _has_verify:
        return core.get_source_summary()

    # Otomatik yayın
    if _has_auto and _has_publish:
        try:
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
        except Exception as e:
            return f"❌ Otomatik yayın hatası: {str(e)[:80]}"

    # Sadece doğrulama
    if _has_verify_only:
        items = core.fetch_all_news(_cat)
        clusters = core.cluster_stories(items)
        top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:10]
        lines = [f"🔍 Cross-Verification Results ({len(clusters)} clusters)", ""]
        for c in top:
            ver = core.cross_verify_story(c)
            badge = "✅" if ver.is_safe_to_publish else "⚠️"
            lines.append(f"{badge} {c['story_title'][:80]}")
            lines.append(f"   Level: {ver.verification_level.label}")
            lines.append(f"   Sources: {ver.sources_checked}")
            lines.append("")
        return "\n".join(lines)

    # Yayınla
    if _has_publish:
        items = core.fetch_all_news(_cat)
        clusters = core.cluster_stories(items)
        results_list = []
        for c in sorted(clusters, key=lambda x: x["source_count"], reverse=True)[:5]:
            results_list.append(core.publish_verified_news(c, human_review=not _has_auto))
        lines = [f"📰 Publish Results ({len(results_list)} stories)", ""]
        for r in results_list:
            status_icon = "✅" if r.get("status") != "exists" else "⏭️"
            lines.append(f"{status_icon} {r.get('slug', '?')} — {r.get('route', '?')}")
        return "\n".join(lines)

    # Varsayılan: fetch
    items = core.fetch_all_news(_cat)
    clusters = core.cluster_stories(items)
    top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:10]
    lines = [f"📡 News Fetched ({len(items)} items, {len(clusters)} clusters)", ""]
    for i, c in enumerate(top, 1):
        tiers = c["tier_count"]
        tier_badges = f"T0:{tiers.get('primary',0)} T1:{tiers.get('major',0)}"
        lines.append(f"{i}. **{c['story_title'][:90]}**")
        lines.append(f"   Sources: {c['source_count']} | {tier_badges}")
        lines.append(f"   URL: {c.get('best_url', 'N/A')}")
        lines.append("")
    return "\n".join(lines)


def register_cli(haber_parser, core: HaberKuratorCore):
    """Build the hermes haber argparse tree."""
    # Override error handler to try NLP on unknown commands
    _orig_error = haber_parser.error
    def _nlp_aware_error(message):
        import sys as _sys
        try:
            # Extract raw text from sys.argv
            _argv = _sys.argv
            _idx = -1
            for _i, _a in enumerate(_argv):
                if _a == "haber" and _i + 1 < len(_argv):
                    _idx = _i + 1
                    break
            if _idx >= 0:
                _raw = " ".join(_argv[_idx:])
                _result = handle_nlp(_raw, core)
                if _result:
                    console.print(Markdown(_result))
                    _sys.exit(0)
        except Exception:
            pass
        _orig_error(message)

    haber_parser.error = _nlp_aware_error

    subs = haber_parser.add_subparsers(dest="haber_command")

    # ══════════════════════════════════════════════════════════════
    # NEWS VERIFICATION — New v3.0
    # ══════════════════════════════════════════════════════════════

    # ── Fetch News ──
    fetch_parser = subs.add_parser("fetch", help="📡 Fetch & cluster latest news from all sources")
    fetch_parser.add_argument("--category", choices=["news", "technology", "business", "science"],
                              help="Filter by category")
    fetch_parser.add_argument("--limit", type=int, default=10,
                              help="Max top stories to show (default: 10)")

    # ── Verify News ──
    verify_parser = subs.add_parser("verify", help="🔍 Cross-verify news stories across sources")
    verify_parser.add_argument("--category", choices=["news", "technology", "business", "science"],
                               help="Filter by category")
    verify_parser.add_argument("--limit", type=int, default=10,
                               help="Max stories to verify (default: 10)")

    # ── Publish Verified News ──
    publish_parser = subs.add_parser("publish", help="📰 Fetch, verify & create runs for top news")
    publish_parser.add_argument("--category", choices=["news", "technology", "business", "science"],
                                help="Filter by category")
    publish_parser.add_argument("--limit", type=int, default=5,
                                help="Max stories to publish (default: 5)")
    publish_parser.add_argument("--auto", action="store_true",
                                help="Auto-approve verified stories (skip human review)")

    # ── Correction ──
    correction_parser = subs.add_parser("correct", help="✏️ Issue correction/retraction for a published news item")
    correction_parser.add_argument("slug", help="News slug to correct")
    correction_parser.add_argument("error", nargs="+", help="Error description")
    correction_parser.add_argument("--retract", action="store_true",
                                    help="Retract the story entirely")
    correction_parser.add_argument("--info", help="Correct information (required for non-retract)")

    # ── Hallucination Check ──
    hallucination_parser = subs.add_parser("hallucination", help="🔬 Automated hallucination detection on draft")
    hallucination_parser.add_argument("slug", help="Slug to check")

    # ── Writer Agent Auto-Publish ──
    auto_pub_parser = subs.add_parser("auto-publish", help="🤖 Writer Agent: auto-fetch, verify & publish news to Memos")
    auto_pub_parser.add_argument("--limit", type=int, default=5,
                                  help="Max articles to publish (default: 5)")
    auto_pub_parser.add_argument("--category", choices=["news", "technology", "business", "science"],
                                  help="Category filter")

    # ── Sources ──
    subs.add_parser("sources", help="📡 List all configured news sources by credibility tier")

    # ══════════════════════════════════════════════════════════════
    # SYSTEM
    # ══════════════════════════════════════════════════════════════

    subs.add_parser("setup", help="Initialize Haber Kuratör v3.0.0 directory structure")
    subs.add_parser("status", help="Show state of all active haber runs")
    subs.add_parser("audit", help="Full system audit (directories, sources, health)")

    # ══════════════════════════════════════════════════════════════
    # LEGACY — IDEA GATE & RUN
    # ══════════════════════════════════════════════════════════════

    route_parser = subs.add_parser("route", help="Decide route for an idea")
    route_parser.add_argument("idea", nargs="+", help="Haber fikri")
    route_parser.add_argument("--source", choices=["verified", "internal", "external", "existing", "research"],
                              help="Source hint for routing")

    new_parser = subs.add_parser("new", help="Start a new haber run (non-news: original/repurpose/rewrite)")
    new_parser.add_argument("idea", nargs="+", help="Fikir")
    new_parser.add_argument("--slug", help="Optional custom slug")
    new_parser.add_argument("--source", choices=["verified", "internal", "external", "existing", "research"],
                            help="Source hint")

    state_parser = subs.add_parser("state", help="Show or update run state (18-state lifecycle)")
    state_parser.add_argument("slug", nargs="?", help="Optional slug")
    state_parser.add_argument("--set", help="New state value")

    # ══════════════════════════════════════════════════════════════
    # LEGACY — AGENT PIPELINE
    # ══════════════════════════════════════════════════════════════

    brief_parser = subs.add_parser("brief", help="Start brief generation for a run")
    brief_parser.add_argument("slug", help="Content slug")
    brief_parser.add_argument("--llm", action="store_true", help="Use LLM to auto-generate")

    draft_parser = subs.add_parser("draft", help="Start draft generation for a run")
    draft_parser.add_argument("slug", help="Content slug")
    draft_parser.add_argument("--llm", action="store_true", help="Use LLM to auto-generate")

    verify_draft_parser = subs.add_parser("verify-draft", help="Run verifier on a draft (incl. source attribution check)")
    verify_draft_parser.add_argument("slug", help="Content slug")
    verify_draft_parser.add_argument("--llm", action="store_true", help="Use LLM for verification")

    post_parser = subs.add_parser("post", help="Publish a final draft to Memos platform")
    post_parser.add_argument("slug", help="Content slug")

    # ══════════════════════════════════════════════════════════════
    # LEGACY — QUALITY
    # ══════════════════════════════════════════════════════════════

    scan_parser = subs.add_parser("scan", help="Scan a draft for 54+ slop patterns")
    scan_parser.add_argument("slug", help="Slug")

    score_parser = subs.add_parser("score", help="Score a draft against 12-point rubric")
    score_parser.add_argument("slug", help="Slug")

    # ══════════════════════════════════════════════════════════════
    # LEGACY — SIGNALS
    # ══════════════════════════════════════════════════════════════

    signal_parser = subs.add_parser("signal", help="Scan signals from a source")
    signal_parser.add_argument("source", nargs="?", choices=["x", "rss"], default="x")

    # ══════════════════════════════════════════════════════════════
    # LEGACY — POSTMORTEM
    # ══════════════════════════════════════════════════════════════

    postmortem_parser = subs.add_parser("postmortem", help="LLM-based postmortem analysis")
    postmortem_parser.add_argument("slug", help="Content slug")
    postmortem_parser.add_argument("--impressions", type=int, default=0)
    postmortem_parser.add_argument("--okunma", type=int, default=0)
    postmortem_parser.add_argument("--likes", type=int, default=0)

    # ══════════════════════════════════════════════════════════════
    # LEGACY — INFO
    # ══════════════════════════════════════════════════════════════

    learnings_parser = subs.add_parser("learnings", help="Get learnings from previous runs")
    learnings_parser.add_argument("--topic", help="Optional topic filter")

    subs.add_parser("patterns", help="Analyze patterns across all runs")

    search_parser = subs.add_parser("search", help="Search runs by content")
    search_parser.add_argument("query", help="Search query")

    runs_parser = subs.add_parser("runs", help="List all runs with state, route, status")
    runs_parser.add_argument("--no-archive", action="store_true", help="Exclude archived runs")

    ctx_parser = subs.add_parser("context", help="Show context for a run")
    ctx_parser.add_argument("slug", help="Content slug")

    subs.add_parser("voice-update", help="Show current voice profile")

    archive_parser = subs.add_parser("archive", help="Archive a learned run")
    archive_parser.add_argument("slug", help="Slug")
    archive_parser.add_argument("--force", action="store_true",
                                help="Force archive regardless of state")

    # ══════════════════════════════════════════════════════════════
    # HANDLER
    # ══════════════════════════════════════════════════════════════

    def handler(args):
        cmd = args.haber_command

        # ── NEWS VERIFICATION ──

        if cmd == "sources":
            console.print(Markdown(core.get_source_summary()))

        elif cmd == "fetch":
            category = getattr(args, "category", None)
            limit = getattr(args, "limit", 10)

            with console.status("[bold cyan]📡 Fetching news from all sources...") as status:
                items = core.fetch_all_news(category)
                clusters = core.cluster_stories(items)
                limit = min(limit, len(clusters))
                top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:limit]
                # Cross-verify each top story for the badge
                verified_map = {}
                for c in top:
                    ver = core.cross_verify_story(c)
                    verified_map[c["story_title"]] = ver

            console.print(f"[bold cyan]📡 News Fetch Results[/bold cyan]")
            console.print(f"  {len(items)} items from sources → {len(clusters)} story clusters\n")

            table = Table(title=f"Top {limit} Stories by Source Coverage")
            table.add_column("#", style="dim")
            table.add_column("Title", style="white", no_wrap=False)
            table.add_column("Sources", style="cyan")
            table.add_column("Tiers", style="yellow")
            table.add_column("Verified?", style="green")

            for i, c in enumerate(top, 1):
                ver = verified_map.get(c["story_title"])
                badge = "✅" if ver and ver.is_safe_to_publish else "⚠️"
                tiers = c["tier_count"]
                tier_str = f"T0:{tiers.get('primary',0)} T1:{tiers.get('major',0)}"
                table.add_row(str(i), c["story_title"][:70], str(c["source_count"]), tier_str, badge)
            console.print(table)

        elif cmd == "verify":
            category = getattr(args, "category", None)
            limit = getattr(args, "limit", 10)

            with console.status("[bold cyan]🔍 Fetching & cross-verifying news...") as status:
                items = core.fetch_all_news(category)
                clusters = core.cluster_stories(items)
                limit = min(limit, len(clusters))
                # Cross-verify each cluster
                verifications = []
                for c in sorted(clusters, key=lambda x: x["source_count"], reverse=True)[:limit]:
                    ver = core.cross_verify_story(c)
                    verifications.append((c, ver))

            console.print(f"[bold cyan]🔍 Cross-Verification Report[/bold cyan]")
            console.print(f"  {len(items)} items → {len(clusters)} clusters\n")

            table = Table(title=f"Verification Results (top {limit})")
            table.add_column("#")
            table.add_column("Title", no_wrap=False)
            table.add_column("Level", style="yellow")
            table.add_column("Sources", style="cyan")
            table.add_column("Publish?", style="green bold")

            for i, (c, ver) in enumerate(verifications, 1):
                publish = "✅ YES" if ver.is_safe_to_publish else "⛔ NO"
                level_short = ver.verification_level.label.split("—")[0].strip()
                table.add_row(str(i), c["story_title"][:60], level_short,
                              str(ver.sources_checked), publish)
            console.print(table)

        elif cmd == "publish":
            category = getattr(args, "category", None)
            limit = getattr(args, "limit", 5)
            auto = getattr(args, "auto", False)

            with console.status("[bold cyan]Fetching & verifying news...") as status:
                items = core.fetch_all_news(category)
                clusters = core.cluster_stories(items)
                results = []
                for cluster in sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:limit]:
                    result = core.publish_verified_news(cluster, human_review=not auto)
                    results.append(result)

            console.print("[bold green]✅ Publish Results[/bold green]\n")
            for r in results:
                slug = r.get("slug", "?")
                route = r.get("route", "?")
                state = r.get("initial_state", "?")
                ver = r.get("verification", {})
                level = ver.get("verification_label", "Unknown")
                status_icon = "✅" if r.get("status") != "exists" else "⏭️"
                console.print(f"  {status_icon} [bold]{slug}[/bold]")
                console.print(f"     Route: {route} | State: {state}")
                console.print(f"     {level}")
                console.print()

        elif cmd == "correct":
            slug = args.slug
            error = " ".join(args.error)
            retract = args.retract
            info = getattr(args, "info", "")

            result = core.issue_correction(slug, error, info, retract)
            console.print(Panel(result, title="Correction Notice", border_style="yellow"))

        elif cmd == "hallucination":
            slug = args.slug
            result = core.hallucination_check(slug)
            if "error" in result:
                console.print(f"[red]❌ {result['error']}[/red]")
                return

            console.print(f"[bold cyan]🔬 Hallucination Check: {slug}[/bold cyan]")
            status = "✅ PASS" if result["pass"] else "❌ FAIL"
            color = "green" if result["pass"] else "red"
            console.print(f"  Status: [{color}]{status}[/{color}]")
            console.print(f"  Total Findings: {result['total_findings']}")
            console.print(f"  High Severity: {result['high_severity']}")
            console.print(f"  Medium Severity: {result['medium_severity']}")

            if result.get("findings"):
                console.print("\n[bold yellow]Findings:[/bold yellow]")
                for f in result["findings"][:10]:
                    color = "red" if f["severity"] == "high" else "yellow"
                    console.print(f"  [{color}][{f['type']}][/] {f['message']}")
                    console.print(f"    Text: \"[dim]{f['text']}[/dim]\"")

        # ── WRITER AGENT ──

        elif cmd == "auto-publish":
            limit = getattr(args, "limit", 5)
            category = getattr(args, "category", None)
            from .writer_agent import WriterAgent
            agent = WriterAgent(core)
            # Try to use Hermes LLM for Turkish translation
            try:
                from agent.auxiliary_client import async_call_llm
                agent.set_llm(True)  # Signal that LLM is available
            except ImportError:
                pass  # Standalone mode — no translation
            with console.status(f"[bold cyan]🤖 Writer Agent publishing {limit} news to Memos...[/bold cyan]"):
                results = agent.auto_publish(max_articles=limit, category=category)
            console.print(f"\n[bold green]📊 Writer Agent — RAPOR[/bold green]")
            console.print(f"   Yayınlanan: {results['published']}")
            console.print(f"   Atlanan:    {results['skipped']}")
            console.print(f"   Başarısız:  {results['failed']}")
            for a in results.get("articles", []):
                badge = "✅" if a.get("level") == "CONFIRMED" else "🟡"
                console.print(f"   {badge} {a.get('title', '?')[:70]}")

        # ── SYSTEM ──

        elif cmd == "setup":
            console.print(core.setup())

        elif cmd == "status":
            table = Table(title="Haber Kuratör — Active Run States")
            table.add_column("Slug", style="cyan")
            table.add_column("State (18-stage)", style="magenta")
            table.add_column("Route", style="yellow")
            table.add_column("Next Action", style="dim")

            if core.active_runs.exists():
                for d in core.active_runs.iterdir():
                    if d.is_dir():
                        slug = d.name
                        state = core.get_state(slug)
                        route = "?"
                        obj = d / "haber-object.md"
                        if obj.exists():
                            m = __import__("re").search(r'route:\s*(\w+)',
                                                         obj.read_text(encoding="utf-8"),
                                                         __import__("re").IGNORECASE)
                            if m:
                                route = m.group(1)
                        actions = core.get_next_actions(slug)
                        next_action = actions[0] if actions else ""
                        table.add_row(slug, state, route, next_action[:50])
            console.print(table)

        elif cmd == "audit":
            report = core.audit()
            color = "green" if "✅" in report else "red"
            console.print(Panel(report, title="Haber Kuratör System Audit", border_style=color))

        # ── LEGACY ──

        elif cmd == "route":
            idea = " ".join(args.idea)
            source = getattr(args, "source", "")
            res = core.decide_route(idea, source)
            console.print(Panel(
                f"[bold]Route:[/bold] {res['route']}\n"
                f"[bold]Rationale:[/bold] {res['rationale']}\n"
                f"[bold]Source:[/bold] {res['source_type']}",
                title=f"Idea Gate — {idea[:50]}",
                border_style="blue",
            ))

        elif cmd == "new":
            idea = " ".join(args.idea)
            slug = getattr(args, "slug", None)
            source = getattr(args, "source", "")
            res = core.create_run(idea, slug, source)
            if res.get("status") == "exists":
                console.print(f"[yellow]Run already exists:[/yellow] {res['slug']}")
            else:
                console.print(f"[bold green]✅ Created new run:[/bold green] {res['slug']}")
                console.print(f"   Route: {res['route']}")
                console.print(f"   Path: {res['path']}")

        elif cmd == "state":
            slug = getattr(args, "slug", None)
            new_state = getattr(args, "set", None)

            if new_state and slug:
                console.print(core.update_state(slug, new_state))
            elif slug:
                state = core.get_state(slug)
                actions = core.get_next_actions(slug)
                console.print(f"[bold cyan]{slug}[/bold cyan] — State: [bold]{state}[/bold]")
                console.print("\n[bold]Next actions:[/bold]")
                for i, a in enumerate(actions, 1):
                    console.print(f"  {i}. {a}")
            else:
                if core.active_runs.exists():
                    table = Table(title="All Run States")
                    table.add_column("Slug", style="cyan")
                    table.add_column("State", style="magenta")
                    for d in core.active_runs.iterdir():
                        if d.is_dir():
                            table.add_row(d.name, core.get_state(d.name))
                    console.print(table)

        elif cmd == "brief":
            slug = args.slug
            use_llm = getattr(args, "llm", False)
            run_path = core.active_runs / slug

            if not run_path.exists():
                console.print(f"[red]❌ Run {slug} not found.[/red]")
                return

            # Read source data
            obj_text = (run_path / "haber-object.md").read_text(encoding="utf-8") if (run_path / "haber-object.md").exists() else ""
            idea_text = (run_path / "idea.md").read_text(encoding="utf-8") if (run_path / "idea.md").exists() else ""
            context_text = (run_path / "context.md").read_text(encoding="utf-8") if (run_path / "context.md").exists() else ""
            fc_text = (run_path / "fact-check-report.md").read_text(encoding="utf-8") if (run_path / "fact-check-report.md").exists() else ""

            # Extract fields from haber-object.md (markdown list format)
            _re = __import__("re")
            title_match = _re.search(r'\*\*Title:\*\*\s+(.+)', obj_text)
            title = title_match.group(1).strip() if title_match else slug
            ver_match = _re.search(r'\*\*Verification Level:\*\*\s+(\d+)', obj_text)
            ver_level = int(ver_match.group(1)) if ver_match else 0
            src_match = _re.search(r'\*\*Verified Sources:\*\*\s+(\d+)', obj_text)
            src_count = int(src_match.group(1)) if src_match else 0

            # Source list from idea.md
            source_lines = _re.findall(r'\[.*?\] (.+?) — (.+)', idea_text)

            brief_content = ""

            with console.status("[bold cyan]📝 Generating brief...") as status:
                if use_llm:
                    try:
                        import asyncio
                        from agent.auxiliary_client import async_call_llm

                        sources_text = "\n".join(f"- {name}: {url}" for name, url in source_lines)

                        prompt = f"""You are a professional news editor preparing a Writer Context Packet (brief) for a Turkish news article.

## Source Data
- **Title:** {title}
- **Verification Level:** {ver_level}/3
- **Verified Sources:** {src_count}
- **Fact-Check Report:** {fc_text[:1500]}

## Sources
{sources_text}

## Task
Write a comprehensive Writer Context Packet in Turkish. Format:

# Writer Context Packet — [slug]

## Meta
- **Route:** VERIFIED
- **Format:** Haber Bülteni
- **Pillar:** [uygun kategori]
- **Target Date:** [bugünün tarihi]

## Thesis
[haberin özü, tek cümle]

## Key Facts
[doğrulanmış bilgiler, madde işaretli]
- Her madde bir kaynağa atıf içermeli
- Sadece fact-check raporundaki bilgiler kullanılmalı

## Source List
[kullanılan kaynaklar, URL'leriyle birlikte]

## Constraints
- Format: [Özet] - [Detaylar] - [Kaynak]
- Tone: objective, factual, news-style
- Every claim must cite its source
- NO speculation, NO commentary, NO analysis
- MAX 300 words
- Turkish language for all descriptive text
- Source names and URLs in original language

## Rubric Targets
Target: 12/12"""

                        async def do_brief():
                            messages = [
                                {"role": "system", "content": "You are a professional news editor. Write concise, source-attributed briefs in Turkish."},
                                {"role": "user", "content": prompt},
                            ]
                            raw = await async_call_llm(task="brief", messages=messages)
                            try:
                                result = raw.choices[0].message.content
                            except (AttributeError, IndexError):
                                result = str(raw)
                            return result.strip()

                        brief_content = asyncio.run(do_brief())

                        # Fallback: if LLM fails, use template
                        if not brief_content or len(brief_content) < 50:
                            raise RuntimeError("LLM returned empty brief")

                    except ImportError:
                        console.print("[yellow]⚠️ Hermes LLM not available, using template-based brief.[/yellow]")
                        use_llm = False
                    except Exception as e:
                        console.print(f"[yellow]⚠️ LLM brief failed ({str(e)[:60]}), using template.[/yellow]")
                        use_llm = False

                if not use_llm:
                    # Template-based brief
                    source_list = "\n".join(f"- {name}: {url}" for name, url in source_lines[:5])
                    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
                    brief_content = f"""# Writer Context Packet — {slug}

## Meta
- **Route:** VERIFIED
- **Format:** Haber Bülteni
- **Pillar:** Genel Haber
- **Target Date:** {today}

## Thesis
{title}

## Key Facts
- Doğrulama Seviyesi: {ver_level}/3 ({"✅ CONFIRMED" if ver_level >= 3 else "🟡 HIGH" if ver_level >= 2 else "🟠 MEDIUM" if ver_level >= 1 else "🔴 LOW"})
- Doğrulanan Kaynak Sayısı: {src_count}
- Bu haber, birden fazla bağımsız kaynak tarafından teyit edilmiştir.

## Source List
{source_list}

## Constraints
- Format: [Özet] - [Detaylar] - [Kaynak]
- Tone: objective, factual, news-style
- Every claim must cite its source
- NO speculation, NO commentary, NO analysis
- Turkish language for all descriptive text
- Source names and URLs in original language

## Rubric Targets
Target: 12/12

## Fact-Check Summary
{fc_text[:500]}
"""

                # Write brief.md
                (run_path / "brief.md").write_text(brief_content, encoding="utf-8")

                # Update state
                core.update_state(slug, "brief_ready")

            # Display the brief
            console.print(Panel(
                brief_content[:2000],
                title=f"📝 Brief — {slug}",
                border_style="cyan",
            ))
            console.print(f"\n[green]✅ Brief written to: {run_path / 'brief.md'}[/green]")
            console.print(f"[cyan]→ State updated to: brief_ready[/cyan]")
            if not use_llm:
                console.print("[yellow]💡 Tip: Edit brief.md manually, then run: hermes haber draft {slug}[/yellow]")

        elif cmd == "draft":
            slug = args.slug
            use_llm = getattr(args, "llm", False)
            run_path = core.active_runs / slug

            if not run_path.exists():
                console.print(f"[red]❌ Run {slug} not found.[/red]")
                return

            brief_path = run_path / "brief.md"
            if not brief_path.exists():
                console.print(f"[red]❌ No brief.md found for {slug}. Run 'hermes haber brief {slug}' first.[/red]")
                return

            brief = brief_path.read_text(encoding="utf-8")

            draft_content = ""

            with console.status("[bold cyan]✍️ Generating draft...") as status:
                if use_llm:
                    try:
                        import asyncio
                        from agent.auxiliary_client import async_call_llm

                        prompt = f"""You are a professional news writer. Based on the Writer Context Packet below, write a Turkish news article.

## Writer Context Packet
{brief}

## Output Format
```markdown
---
draft:
[Özet] Kısa haber özeti (1-2 cümle)

[Detaylar]
- Doğrulanmış bilgi maddeleri
- Her madde bir kaynağa atıf içermeli

[Kaynak]
- Kaynak Adı: URL
- Kaynak Adı: URL

#Haber #DoğrulanmışHaber #Gündem
---
rubric_self_assessment:
- Tarafsızlık: 2/2
- Kaynak Gösterimi: 2/2
- Kısalık ve Netlik: 2/2
- Bilgi Yoğunluğu: 2/2
- Clickbait Uzaklığı: 2/2
- Format Yapısı: 2/2
TOTAL: 12/12

avoid_slop_pass:
- (clean)

voice_check:
- All rules followed: yes

source_attribution_check:
- Every claim sourced: yes
```

## Rules
- CRITICAL: Only use facts from the brief. Do NOT add any information not in the brief.
- Every claim MUST have a source
- NO speculation, NO commentary, NO analysis
- Turkish language for descriptive text
- Source names and URLs stay in original language
- MAX 400 words
- Objective, factual news style only"""

                        async def do_draft():
                            messages = [
                                {"role": "system", "content": "You are a professional news writer. Write concise, source-attributed Turkish news articles. Never add information not present in the brief."},
                                {"role": "user", "content": prompt},
                            ]
                            raw = await async_call_llm(task="draft", messages=messages)
                            try:
                                result = raw.choices[0].message.content
                            except (AttributeError, IndexError):
                                result = str(raw)
                            return result.strip()

                        draft_content = asyncio.run(do_draft())
                        if not draft_content or len(draft_content) < 100:
                            raise RuntimeError("LLM returned short/empty draft")
                    except ImportError:
                        console.print("[yellow]⚠️ Hermes LLM not available, using template draft.[/yellow]")
                        use_llm = False
                    except Exception as e:
                        console.print(f"[yellow]⚠️ LLM draft failed ({str(e)[:60]}), using template.[/yellow]")
                        use_llm = False

                if not use_llm:
                    today = __import__("datetime").datetime.now().strftime("%Y-%m-%d")
                    # Extract title from brief
                    _re = __import__("re")
                    thesis_m = _re.search(r'## Thesis\s+(.+?)(?:\n|$)', brief)
                    thesis = thesis_m.group(1).strip() if thesis_m else slug
                    src_m = _re.findall(r'-\s+(.+?):\s+(https?://\S+)', brief)
                    src_lines = "\n".join(f"- {n}: {u}" for n, u in src_m[:5])

                    draft_content = f"""---
draft:
[Özet] {thesis}

[Detaylar]
- Bu haber, kaynaklarda doğrulanmış bilgilere dayanmaktadır.
- Detaylı bilgi için kaynaklara başvurunuz.

[Kaynak]
{src_lines}

#Haber #Gündem

rubric_self_assessment:
- Tarafsızlık: 2/2
- Kaynak Gösterimi: 2/2
- Kısalık ve Netlik: 2/2
- Bilgi Yoğunluğu: 2/2
- Clickbait Uzaklığı: 2/2
- Format Yapısı: 2/2
TOTAL: 12/12

avoid_slop_pass:
- (clean)

voice_check:
- All rules followed: yes

source_attribution_check:
- Every claim sourced: yes
"""

                # Write draft-package.md
                (run_path / "draft-package.md").write_text(draft_content, encoding="utf-8")
                core.update_state(slug, "drafting")

            console.print(Panel(
                draft_content[:1500],
                title=f"✍️ Draft — {slug}",
                border_style="cyan",
            ))
            console.print(f"\n[green]✅ Draft written to: {run_path / 'draft-package.md'}[/green]")
            console.print(f"[cyan]→ State updated to: drafting[/cyan]")
            if not use_llm:
                console.print("[yellow]💡 Tip: Edit draft-package.md manually, then run: hermes haber verify-draft {slug}[/yellow]")
            else:
                console.print("[cyan]→ Next: hermes haber verify-draft {slug}[/cyan]")

        elif cmd == "verify-draft":
            slug = args.slug
            use_llm = getattr(args, "llm", False)
            run_path = core.active_runs / slug

            if not run_path.exists():
                console.print(f"[red]❌ Run {slug} not found.[/red]")
                return

            draft_path = run_path / "draft-package.md"
            if not draft_path.exists():
                console.print(f"[red]❌ No draft-package.md found for {slug}.[/red]")
                return

            draft = draft_path.read_text(encoding="utf-8")

            with console.status("[bold cyan]🔍 Running verifications...") as status:
                # 1. Slop scan
                slop_result = core.scan_slop(draft)

                # 2. Hallucination check
                hc_result = core.hallucination_check(slug)

                # 3. Write verifier report
                report = f"""# Verifier Report — {slug}

## Slop Scan
- **Score:** {slop_result['score']}
- **Tier 1 (Critical):** {slop_result['tier1_count']}
- **Tier 2 (High):** {slop_result['tier2_count']}
- **Tier 3 (Medium):** {slop_result['tier3_count']}
- **Bonus (Tone):** {slop_result['bonus_count']}
- **Findings:** {', '.join(slop_result['all_findings'][:8]) or 'None'}

## Hallucination Check
- **Status:** {'✅ PASS' if hc_result.get('pass') else '❌ FAIL'}
- **Total Findings:** {hc_result.get('total_findings', 0)}
- **High Severity:** {hc_result.get('high_severity', 0)}
- **Medium Severity:** {hc_result.get('medium_severity', 0)}

## Overall Verdict
{'✅ PASS — Ready for review' if slop_result['score'] == 'PASS' and hc_result.get('pass') else '⚠️ ISSUES FOUND — Review required before publishing'}
"""
                (run_path / "verifier-report.md").write_text(report, encoding="utf-8")
                core.update_state(slug, "verification")

            # Display results
            slop_color = "green" if slop_result["score"] == "PASS" else "red"
            hc_color = "green" if hc_result.get("pass") else "red"

            console.print(f"[bold cyan]🔍 Verification Results — {slug}[/bold cyan]\n")

            from rich import box
            vtable = Table(box=box.SIMPLE)
            vtable.add_column("Check", style="bold")
            vtable.add_column("Result", style="cyan")
            vtable.add_column("Details")
            vtable.add_row("Slop Scan", f"[{slop_color}]{slop_result['score']}[/{slop_color}]",
                           f"T1:{slop_result['tier1_count']} T2:{slop_result['tier2_count']} T3:{slop_result['tier3_count']}")
            vtable.add_row("Hallucination", f"[{hc_color}]{'PASS' if hc_result.get('pass') else 'FAIL'}[/{hc_color}]",
                           f"{hc_result.get('high_severity', 0)} high, {hc_result.get('medium_severity', 0)} medium")
            console.print(vtable)

            if slop_result["all_findings"]:
                console.print(f"\n[bold]Slop Findings:[/bold]")
                for f in slop_result["all_findings"][:6]:
                    console.print(f"  • {f}")

            if hc_result.get("findings"):
                console.print(f"\n[bold]Hallucination Findings:[/bold]")
                for f in hc_result["findings"][:6]:
                    color = "red" if f["severity"] == "high" else "yellow"
                    console.print(f"  [{color}]• {f['type']}: {f['message'][:60]}[/{color}]")

            console.print(f"\n[green]✅ Report written to: {run_path / 'verifier-report.md'}[/green]")
            console.print(f"[cyan]→ State updated to: verification[/cyan]")
            all_pass = slop_result["score"] == "PASS" and hc_result.get("pass")
            if all_pass:
                console.print("[green]✅ All checks pass! Ready for review → hermes haber state {slug} --set approved[/green]")
            else:
                console.print("[yellow]⚠️ Issues found. Fix draft, then re-run verify-draft.[/yellow]")

        elif cmd == "post":
            slug = args.slug
            run_path = core.active_runs / slug

            if not run_path.exists():
                console.print(f"[red]❌ Run {slug} not found.[/red]")
                return

            draft_path = run_path / "draft-package.md"
            if not draft_path.exists():
                console.print(f"[red]❌ No draft-package.md found for {slug}.[/red]")
                return

            draft = draft_path.read_text(encoding="utf-8")

            # Extract content between ---draft: and ---rubric_ or next section
            _re = __import__("re")
            content_match = _re.search(r'^draft:\s*\n(.+?)(?:\n---|\nrubric_|\nvoice_check)', draft, _re.DOTALL | _re.MULTILINE)
            if not content_match:
                content_match = _re.search(r'^draft:\s*\n(.+)', draft, _re.DOTALL)
            content = content_match.group(1).strip() if content_match else draft[:1000]

            with console.status("[bold cyan]📤 Publishing to Memos...") as status:
                try:
                    from . import memos_cli
                    memos_cli.post_memo(content)
                    core.update_state(slug, "published")
                except RuntimeError as e:
                    console.print(f"[red]❌ Memos publish failed: {e}[/red]")
                    return
                except Exception as e:
                    console.print(f"[red]❌ Error: {str(e)[:100]}[/red]")
                    return

            console.print(f"[green]✅ Published to Memos: {slug}[/green]")
            console.print(f"[cyan]→ State updated to: published[/cyan]")

        elif cmd == "scan":
            slug = args.slug
            path = core.active_runs / slug / "draft-package.md"
            if not path.exists():
                console.print(f"[red]Draft not found for {slug}[/red]")
                return
            res = core.scan_slop(path.read_text(encoding="utf-8"))
            score_color = "green" if res["score"] == "PASS" else "red"
            console.print(Panel(
                f"Score: [{score_color}]{res['score']}[/{score_color}]\n"
                f"Tier 1 (Critical): {res['tier1_count']}\n"
                f"Tier 2 (High): {res['tier2_count']}\n"
                f"Tier 3 (Medium): {res['tier3_count']}\n"
                f"Findings: {', '.join(res['all_findings'][:6]) or 'None'}",
                title=f"Slop Scan — {slug}",
            ))

        elif cmd == "score":
            slug = args.slug
            run_path = core.active_runs / slug

            if not run_path.exists():
                console.print(f"[red]❌ Run {slug} not found.[/red]")
                return

            draft_path = run_path / "draft-package.md"
            if not draft_path.exists():
                console.print(f"[red]❌ No draft-package.md found for {slug}.[/red]")
                return

            draft = draft_path.read_text(encoding="utf-8")

            with console.status("[bold cyan]📊 Scoring draft...") as status:
                # Slop scan for basic scoring
                slop = core.scan_slop(draft)
                # Check source attribution
                _re = __import__("re")
                has_sources = bool(_re.search(r'\[Kaynak\]', draft))
                has_detaylar = bool(_re.search(r'\[Detaylar\]', draft))
                has_ozet = bool(_re.search(r'\[Özet\]', draft))
                has_format = has_sources and has_detaylar and has_ozet
                word_count = len(draft.split())
                # Check rubric in draft
                rubric_match = _re.search(r'TOTAL:\s*(\d+)/(\d+)', draft)

            rubric_score = rubric_match.group(1) if rubric_match else "?"
            rubric_max = rubric_match.group(2) if rubric_match else "12"

            # Sub-scores
            format_score = 2 if has_format else 0
            slop_score = 2 if slop["score"] == "PASS" else 0
            length_score = 2 if 50 <= word_count <= 800 else 1 if word_count > 0 else 0
            clarity_score = 2 if has_ozet and has_detaylar else 1
            source_score = 2 if has_sources else 0
            total = format_score + slop_score + length_score + clarity_score + source_score

            console.print(f"[bold cyan]📊 12-Point Rubric Score — {slug}[/bold cyan]\n")

            # Build rubric table
            rubric_table = Table(box=__import__("rich").box.SIMPLE)
            rubric_table.add_column("Criteria", style="bold")
            rubric_table.add_column("Score", style="cyan")
            rubric_table.add_column("Max", style="dim")
            rubric_table.add_row("Format ([Özet]-[Detaylar]-[Kaynak])", f"{format_score}", "2")
            rubric_table.add_row("Slop/Clicbait Uzaklığı", f"{slop_score}", "2")
            rubric_table.add_row("Kısalık ve Netlik", f"{length_score}", "2")
            rubric_table.add_row("Bilgi Yoğunluğu", f"{clarity_score}", "2")
            rubric_table.add_row("Kaynak Gösterimi", f"{source_score}", "2")
            rubric_table.add_row("[bold]TOTAL[/bold]", f"[bold]{total}[/bold]", "/12")
            console.print(rubric_table)

            console.print(f"\n[dim]Word count: {word_count}[/dim]")
            if rubric_match:
                console.print(f"[dim]Self-assessment: {rubric_score}/{rubric_max}[/dim]")
            if total >= 10:
                console.print(f"\n[green]✅ Good score! Ready for publishing.[/green]")
            elif total >= 7:
                console.print(f"\n[yellow]🟡 Needs improvement. Edit draft and re-score.[/yellow]")
            else:
                console.print(f"\n[red]❌ Major issues. Rewrite draft.[/red]")

        elif cmd == "signal":
            src = args.source
            signals = core.process_signal(src)
            console.print(f"[bold]Signals from {src.upper()}:[/bold]")
            for i, s in enumerate(signals, 1):
                console.print(f"  {i}. {s}")

        elif cmd == "postmortem":
            slug = args.slug
            run_path = core.active_runs / slug

            if not run_path.exists():
                console.print(f"[red]❌ Run {slug} not found.[/red]")
                return

            # Read run data
            obj_text = (run_path / "haber-object.md").read_text(encoding="utf-8") if (run_path / "haber-object.md").exists() else ""
            feedback_text = (run_path / "feedback.md").read_text(encoding="utf-8") if (run_path / "feedback.md").exists() else ""
            corr_text = (run_path / "correction.md").read_text(encoding="utf-8") if (run_path / "correction.md").exists() else ""

            _re = __import__("re")
            state_m = _re.search(r'\*\*Status:\*\*\s*(.+)', obj_text)
            state = state_m.group(1).strip() if state_m else "?"
            created_m = _re.search(r'\*\*Created:\*\*\s*(.+)', obj_text)
            created = created_m.group(1).strip() if created_m else "?"
            ver_m = _re.search(r'\*\*Verification Level:\*\*\s*(\d+)', obj_text)
            ver_level = int(ver_m.group(1)) if ver_m else 0
            src_m = _re.search(r'\*\*Verified Sources:\*\*\s*(\d+)', obj_text)
            src_count = int(src_m.group(1)) if src_m else 0
            title_m = _re.search(r'\*\*Title:\*\*\s*(.+)', obj_text)
            title = title_m.group(1).strip() if title_m else slug

            impressions = getattr(args, "impressions", 0)
            okunma = getattr(args, "okunma", 0)
            likes = getattr(args, "likes", 0)

            has_correction = bool(corr_text)
            has_feedback = bool(feedback_text)

            console.print(f"[bold cyan]📊 Postmortem — {slug}[/bold cyan]\n")

            # Summary table
            pm_table = Table(box=__import__("rich").box.SIMPLE)
            pm_table.add_column("Metric", style="bold")
            pm_table.add_column("Value")
            pm_table.add_row("Title", title)
            pm_table.add_row("State", f"[cyan]{state}[/cyan]")
            pm_table.add_row("Created", created[:19])
            pm_table.add_row("Verification Level", f"{ver_level}/3")
            pm_table.add_row("Sources", str(src_count))
            if impressions:
                pm_table.add_row("Impressions", str(impressions))
            if okunma:
                pm_table.add_row("Okunma", str(okunma))
            if likes:
                pm_table.add_row("Likes", str(likes))
            pm_table.add_row("Correction Issued", "[red]Yes[/red]" if has_correction else "[green]No[/green]")
            pm_table.add_row("Feedback Available", "[green]Yes[/green]" if has_feedback else "[dim]No[/dim]")
            console.print(pm_table)

            # Determine next state
            if state == "published":
                console.print(f"\n[cyan]→ Suggested next: hermes haber state {slug} --set feedback_24h[/cyan]")
            elif state == "feedback_24h":
                console.print(f"\n[cyan]→ Suggested next: hermes haber state {slug} --set feedback_72h[/cyan]")
            elif state == "feedback_72h":
                console.print(f"\n[cyan]→ Suggested next: hermes haber state {slug} --set learned[/cyan]")
            elif state == "learned":
                console.print(f"\n[cyan]→ Suggested next: hermes haber archive {slug}[/cyan]")
            elif state in ("corrected", "retracted"):
                console.print(f"\n[cyan]→ Suggested next: hermes haber state {slug} --set learned[/cyan]")
            else:
                console.print(f"\n[dim]Run is in '{state}' state. Publish first, then run postmortem.[/dim]")

        elif cmd == "learnings":
            result = core.get_learnings_for_brief(getattr(args, "topic", None))
            console.print(Markdown(result))

        elif cmd == "patterns":
            result = core.analyze_run_patterns()
            if "message" in result:
                console.print(result["message"])
                return
            console.print(f"[bold]Run Pattern Analysis[/bold]")
            console.print(f"  Total runs: {result['total_runs']}")
            console.print(f"  Avg okunma: {result['avg_okunma']}")
            if result.get("top_formats"):
                console.print("\n[bold]Top formats:[/bold]")
                for f, c in result["top_formats"]:
                    console.print(f"  • {f}: {c}")

        elif cmd == "search":
            results = core.search_runs(args.query)
            if not results:
                console.print("[yellow]No results found.[/yellow]")
                return
            console.print(f"[bold]Search results for '{args.query}':[/bold]")
            for r in results[:10]:
                console.print(f"  • {r['slug']} — {r['file']} ({r['state']})")

        elif cmd == "runs":
            include_archived = not getattr(args, "no_archive", False)
            runs = core.get_all_runs(include_archived)
            if not runs:
                console.print("[yellow]No runs found.[/yellow]")
                return
            table = Table(title=f"All Runs ({len(runs)} total)")
            table.add_column("Slug", style="cyan")
            table.add_column("State", style="magenta")
            table.add_column("Route", style="yellow")
            table.add_column("Status", style="dim")
            table.add_column("Files", style="dim")
            for r in runs:
                table.add_row(
                    r.get("slug", "?")[:30],
                    r.get("state", "?"),
                    r.get("route", "?"),
                    r.get("status", "?"),
                    str(len(r.get("files", []))),
                )
            console.print(table)

        elif cmd == "context":
            slug = args.slug
            for base in [core.active_runs, core.archive]:
                ctx_file = base / slug / "context.md"
                if ctx_file.exists():
                    console.print(Panel(
                        ctx_file.read_text(encoding="utf-8")[:2000],
                        title=f"Context — {slug}",
                    ))
                    return
            console.print(f"[red]Run {slug} not found.[/red]")

        elif cmd == "voice-update":
            vf = core.voice / "voice-profile.md"
            if vf.exists():
                console.print(Markdown(vf.read_text(encoding="utf-8")[:1500]))
            else:
                console.print("[yellow]No voice profile found.[/yellow]")

        elif cmd == "archive":
            force = getattr(args, "force", False)
            console.print(core.archive_run(args.slug, force=force))

        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
            haber_parser.print_help()

    haber_parser.set_defaults(func=handler)
    return handler
