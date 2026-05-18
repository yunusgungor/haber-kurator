"""
CLI registration for Haber Kuratör v3.1.0 — News Verification System.

News-only commands:
- fetch, verify, publish, correct
- setup, status, audit, sources
- auto-publish, search, runs, archive
"""

from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from .haber_kurator_core import HaberKuratorCore

console = Console()


def register_cli(haber_parser, core: HaberKuratorCore):
    """Build the hermes haber argparse tree — news commands only."""

    subs = haber_parser.add_subparsers(dest="haber_command")

    # ══════════════════════════════════════════════════════════════
    # NEWS VERIFICATION
    # ══════════════════════════════════════════════════════════════

    fetch_parser = subs.add_parser("fetch", help="📡 Fetch & cluster latest news from all sources")
    fetch_parser.add_argument("--category", choices=["news", "technology", "business", "science"],
                              help="Filter by category")
    fetch_parser.add_argument("--country", type=str, default=None,
                              help="Filter by country (e.g. 'turkey', 'global')")
    fetch_parser.add_argument("--limit", type=int, default=10,
                              help="Max top stories to show (default: 10)")

    verify_parser = subs.add_parser("verify", help="🔍 Cross-verify news stories across sources")
    verify_parser.add_argument("--category", choices=["news", "technology", "business", "science"],
                               help="Filter by category")
    verify_parser.add_argument("--country", type=str, default=None,
                               help="Filter by country (e.g. 'turkey', 'global')")
    verify_parser.add_argument("--limit", type=int, default=10,
                               help="Max stories to verify (default: 10)")

    publish_parser = subs.add_parser("publish", help="📰 Fetch, verify & create runs for top news")
    publish_parser.add_argument("--category", choices=["news", "technology", "business", "science"],
                                help="Filter by category")
    publish_parser.add_argument("--country", type=str, default=None,
                                help="Filter by country (e.g. 'turkey', 'global')")
    publish_parser.add_argument("--limit", type=int, default=5,
                                help="Max stories to publish (default: 5)")
    publish_parser.add_argument("--auto", action="store_true",
                                help="Auto-approve verified stories (skip human review)")

    correction_parser = subs.add_parser("correct", help="✏️ Issue correction/retraction for a published news item")
    correction_parser.add_argument("slug", help="News slug to correct")
    correction_parser.add_argument("error", nargs="+", help="Error description")
    correction_parser.add_argument("--retract", action="store_true",
                                    help="Retract the story entirely")
    correction_parser.add_argument("--info", help="Correct information (required for non-retract)")

    hallucination_parser = subs.add_parser("hallucination", help="🔬 Automated hallucination detection on draft")
    hallucination_parser.add_argument("slug", help="Slug to check")

    auto_pub_parser = subs.add_parser("auto-publish", help="🤖 Writer Agent: auto-fetch, verify & publish news to Memos")
    auto_pub_parser.add_argument("--limit", type=int, default=5, help="Max articles (default: 5)")
    auto_pub_parser.add_argument("--category", choices=["news", "technology", "business", "science"],
                                  help="Category filter")
    auto_pub_parser.add_argument("--country", type=str, default=None,
                                  help="Filter by country (e.g. 'turkey', 'global')")

    subs.add_parser("sources", help="📡 List all configured news sources by credibility tier")

    # ══════════════════════════════════════════════════════════════
    # SYSTEM
    # ══════════════════════════════════════════════════════════════

    subs.add_parser("setup", help="Initialize Haber Kuratör v3.1.0 directory structure")
    subs.add_parser("status", help="Show state of all active haber runs")
    subs.add_parser("audit", help="Full system audit (directories, sources, health)")

    # ══════════════════════════════════════════════════════════════
    # INFO
    # ══════════════════════════════════════════════════════════════

    search_parser = subs.add_parser("search", help="Search runs by content")
    search_parser.add_argument("query", help="Search query")

    runs_parser = subs.add_parser("runs", help="List all runs with state, route, status")
    runs_parser.add_argument("--no-archive", action="store_true", help="Exclude archived runs")

    archive_parser = subs.add_parser("archive", help="Archive a run")
    archive_parser.add_argument("slug", help="Slug")
    archive_parser.add_argument("--force", action="store_true", help="Force archive")

    # ══════════════════════════════════════════════════════════════
    # HANDLER
    # ══════════════════════════════════════════════════════════════

    def handler(args):
        cmd = args.haber_command

        if cmd == "sources":
            console.print(Markdown(core.get_source_summary()))

        elif cmd == "fetch":
            category = getattr(args, "category", None)
            country = getattr(args, "country", None)
            limit = getattr(args, "limit", 10)
            with console.status("[bold cyan]📡 Fetching news from all sources...") as status:
                items = core.fetch_all_news(category, country)
                clusters = core.cluster_stories(items)
                limit = min(limit, len(clusters))
                top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:limit]
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
                tier_str = f"T0:{tiers.get('primary', 0)} T1:{tiers.get('major', 0)}"
                table.add_row(str(i), c["story_title"][:70], str(c["source_count"]), tier_str, badge)
            console.print(table)

        elif cmd == "verify":
            category = getattr(args, "category", None)
            country = getattr(args, "country", None)
            limit = getattr(args, "limit", 10)
            with console.status("[bold cyan]🔍 Fetching & cross-verifying news...") as status:
                items = core.fetch_all_news(category, country)
                clusters = core.cluster_stories(items)
                limit = min(limit, len(clusters))
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
                table.add_row(str(i), c["story_title"][:60], level_short, str(ver.sources_checked), publish)
            console.print(table)

        elif cmd == "publish":
            category = getattr(args, "category", None)
            country = getattr(args, "country", None)
            limit = getattr(args, "limit", 5)
            auto = getattr(args, "auto", False)
            with console.status("[bold cyan]Fetching & verifying news...") as status:
                items = core.fetch_all_news(category, country)
                clusters = core.cluster_stories(items)
                results = []
                for cluster in sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:limit]:
                    result = core.publish_verified_news(cluster, human_review=not auto)
                    results.append(result)
            console.print("[bold green]✅ Publish Results[/bold green]\n")
            for r in results:
                status_icon = "✅" if r.get("status") != "exists" else "⏭️"
                console.print(f"  {status_icon} [bold]{r.get('slug', '?')}[/bold]")
                console.print(f"     Route: {r.get('route', '?')} | State: {r.get('initial_state', '?')}")
                console.print()

        elif cmd == "correct":
            slug = args.slug
            error = " ".join(args.error)
            retract = args.retract
            info = getattr(args, "info", "")
            if not retract and not info.strip():
                console.print("[red]❌ --info <correct_information> is required for corrections (not retractions). Use --retract to retract instead.[/red]")
                return
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

        elif cmd == "auto-publish":
            limit = getattr(args, "limit", 5)
            category = getattr(args, "category", None)
            country = getattr(args, "country", None)
            from .writer_agent import WriterAgent
            agent = WriterAgent(core)
            # Enable Turkish content generation via LLM (falls back to template if unavailable)
            try:
                from agent.auxiliary_client import async_call_llm
                agent.set_llm(True)
            except ImportError:
                pass
            with console.status(f"[bold cyan]🤖 Writer Agent publishing {limit} news to Memos...[/bold cyan]"):
                results = agent.auto_publish(max_articles=limit, category=category, country=country)
            console.print(f"\n[bold green]📊 Writer Agent — RAPOR[/bold green]")
            console.print(f"   Yayınlanan: {results['published']}")
            console.print(f"   Atlanan:    {results['skipped']}")
            console.print(f"   Başarısız:  {results['failed']}")
            for a in results.get("articles", []):
                badge = "✅" if a.get("level") == "CONFIRMED" else "🟡"
                console.print(f"   {badge} {a.get('title', '?')[:70]}")

        elif cmd == "setup":
            console.print(core.setup())

        elif cmd == "status":
            table = Table(title="Haber Kuratör — Active Run States")
            table.add_column("Slug", style="cyan")
            table.add_column("State (8-stage)", style="magenta")
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
                table.add_row(r.get("slug", "?")[:30], r.get("state", "?"),
                              r.get("route", "?"), r.get("status", "?"),
                              str(len(r.get("files", []))))
            console.print(table)

        elif cmd == "archive":
            force = getattr(args, "force", False)
            console.print(core.archive_run(args.slug, force=force))

        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
            haber_parser.print_help()

    haber_parser.set_defaults(func=handler)
    return handler
