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


def register_cli(haber_parser, core: HaberKuratorCore):
    """Build the hermes haber argparse tree."""
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

    # ══════════════════════════════════════════════════════════════
    # HANDLER
    # ══════════════════════════════════════════════════════════════

    def handler(args):
        cmd = args.haber_command

        # ── NEWS VERIFICATION ──

        if cmd == "sources":
            console.print(Markdown(core.get_source_summary()))

        elif cmd == "fetch":
            items = core.fetch_all_news(getattr(args, "category", None))
            clusters = core.cluster_stories(items)
            limit = min(getattr(args, "limit", 10), len(clusters))
            top = sorted(clusters, key=lambda c: c["source_count"], reverse=True)[:limit]

            console.print(f"[bold cyan]📡 News Fetch Results[/bold cyan]")
            console.print(f"  {len(items)} items from sources → {len(clusters)} story clusters\n")

            table = Table(title=f"Top {limit} Stories by Source Coverage")
            table.add_column("#", style="dim")
            table.add_column("Title", style="white", no_wrap=False)
            table.add_column("Sources", style="cyan")
            table.add_column("Tiers", style="yellow")
            table.add_column("Verified?", style="green")

            for i, c in enumerate(top, 1):
                ver = core.cross_verify_story(c)
                badge = "✅" if ver.is_safe_to_publish else "⚠️"
                tiers = c["tier_count"]
                tier_str = f"T0:{tiers.get('primary',0)} T1:{tiers.get('major',0)}"
                table.add_row(str(i), c["story_title"][:70], str(c["source_count"]), tier_str, badge)
            console.print(table)

        elif cmd == "verify":
            items = core.fetch_all_news(getattr(args, "category", None))
            clusters = core.cluster_stories(items)
            limit = min(getattr(args, "limit", 10), len(clusters))

            console.print(f"[bold cyan]🔍 Cross-Verification Report[/bold cyan]")
            console.print(f"  {len(items)} items → {len(clusters)} clusters\n")

            table = Table(title=f"Verification Results (top {limit})")
            table.add_column("#")
            table.add_column("Title", no_wrap=False)
            table.add_column("Level", style="yellow")
            table.add_column("Sources", style="cyan")
            table.add_column("Publish?", style="green bold")

            for i, c in enumerate(sorted(clusters, key=lambda x: x["source_count"], reverse=True)[:limit], 1):
                ver = core.cross_verify_story(c)
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
            from writer_agent import WriterAgent
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
            console.print(f"[cyan]📝[/cyan] Brief requested for [bold]{args.slug}[/bold]")
            console.print("Run via Hermes chat: use `/haber brief <slug>` or ask the agent.")

        elif cmd == "draft":
            console.print(f"[cyan]✍️[/cyan] Draft requested for [bold]{args.slug}[/bold]")
            console.print("Run via Hermes chat.")

        elif cmd == "verify-draft":
            console.print(f"[cyan]🔍[/cyan] Verification requested for [bold]{args.slug}[/bold]")
            console.print("Run via Hermes chat.")

        elif cmd == "post":
            console.print(f"[cyan]📤[/cyan] Post requested for [bold]{args.slug}[/bold]")

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
            console.print(f"[cyan]📊[/cyan] Scoring for [bold]{args.slug}[/bold]")
            console.print("Run via Hermes chat for LLM-based scoring.")

        elif cmd == "signal":
            src = args.source
            signals = core.process_signal(src)
            console.print(f"[bold]Signals from {src.upper()}:[/bold]")
            for i, s in enumerate(signals, 1):
                console.print(f"  {i}. {s}")

        elif cmd == "postmortem":
            console.print(f"[cyan]📊[/cyan] Postmortem for [bold]{args.slug}[/bold]")

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
            console.print(core.archive_run(args.slug))

        else:
            console.print(f"[red]Unknown command: {cmd}[/red]")
            haber_parser.print_help()

    haber_parser.set_defaults(func=handler)
    return handler
