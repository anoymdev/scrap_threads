#!/usr/bin/env python3
"""
Threads Scraper - Main CLI

Usage examples:
  python main.py feed --max 100                           # scrape beranda (recommended!)
  python main.py feed --tabs for_you --max 80             # For You tab only
  python main.py profile zuck --max 50
  python main.py keyword "#indonesia" --max 100
  python main.py keywords "#trending,#viral,#indonesia" --max 30
  python main.py profiles "user1,user2,user3" --max 20
  python main.py analyze data/raw/threads_20240517.json
"""

import typer
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List
import uuid

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich import print as rprint

from src.scraper import ThreadsScraper
from src.storage import DataStorage
from src.analytics import ThreadsAnalyzer
from src.config import config
from src.logger import setup_logger
from src.models import ScrapeSession
from src.generator import ContentGenerator
from src.poster import ThreadsPoster

app = typer.Typer(
    name="threads-scraper",
    help="🕷️  Threads.net scraper for AI content analysis",
    add_completion=False,
)
console = Console()
logger = setup_logger("main", config.LOG_DIR)


def _print_banner():
    console.print(
        Panel.fit(
            "[bold magenta]🕸️  Threads Scraper[/bold magenta]\n"
            "[dim]For AI/ML Research & Content Analysis[/dim]",
            border_style="magenta",
        )
    )


def _build_scraper(headless: bool, proxy: Optional[str], delay: float) -> ThreadsScraper:
    return ThreadsScraper(headless=headless, proxy=proxy, delay=delay)


def _save_all(posts, storage: DataStorage, session: ScrapeSession, formats: str):
    fmts = [f.strip().lower() for f in formats.split(",")]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = {}

    if "json" in fmts:
        p = storage.save_json(posts, f"threads_{ts}.json", session=session)
        saved["json"] = str(p)
    if "jsonl" in fmts:
        p = storage.save_jsonl(posts, f"threads_{ts}.jsonl")
        saved["jsonl"] = str(p)
    if "csv" in fmts:
        p = storage.save_csv(posts, f"threads_{ts}.csv")
        saved["csv"] = str(p)
    if "txt" in fmts:
        p = storage.save_text_corpus(posts, f"corpus_{ts}.txt")
        saved["txt"] = str(p)

    return saved


# ======================================================================== #
#  Commands                                                                 #
# ======================================================================== #

@app.command("profile")
def scrape_profile(
    username: str = typer.Argument(..., help="Threads username (without @)"),
    max: int = typer.Option(50, "--max", "-m", help="Maximum posts to collect"),
    formats: str = typer.Option("json,csv", "--formats", "-f", help="Output formats: json,jsonl,csv,txt"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser in headless mode"),
    proxy: Optional[str] = typer.Option(None, "--proxy", help="Proxy URL"),
    delay: float = typer.Option(3.0, "--delay", "-d", help="Delay between requests (seconds)"),
    report: bool = typer.Option(False, "--report", "-r", help="Generate analytics report"),
):
    """Scrape posts from a single Threads profile."""
    _print_banner()

    scraper = _build_scraper(headless, proxy, delay)
    storage = DataStorage()
    session = ScrapeSession(
        session_id=uuid.uuid4().hex[:8],
        target=username,
        target_type="profile",
    )

    with console.status(f"[bold cyan]Scraping @{username}...[/bold cyan]"):
        posts = scraper.scrape_profile(username, max_posts=max)

    session.completed_at = datetime.now(timezone.utc).isoformat()
    session.posts_collected = len(posts)

    if not posts:
        console.print("[red]❌ No posts collected.[/red]")
        raise typer.Exit(1)

    saved = _save_all(posts, storage, session, formats)
    _print_summary(posts, saved)

    if report:
        _run_report(posts, storage)


@app.command("keyword")
def scrape_keyword(
    keyword: str = typer.Argument(..., help="Search keyword or #hashtag"),
    max: int = typer.Option(50, "--max", "-m", help="Maximum posts to collect"),
    formats: str = typer.Option("json,csv", "--formats", "-f", help="Output formats"),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
    proxy: Optional[str] = typer.Option(None, "--proxy"),
    delay: float = typer.Option(3.0, "--delay", "-d"),
    report: bool = typer.Option(False, "--report", "-r"),
):
    """Scrape posts matching a keyword or hashtag search."""
    _print_banner()

    scraper = _build_scraper(headless, proxy, delay)
    storage = DataStorage()
    session = ScrapeSession(
        session_id=uuid.uuid4().hex[:8],
        target=keyword,
        target_type="search",
    )

    with console.status(f"[bold cyan]Searching '{keyword}'...[/bold cyan]"):
        posts = scraper.scrape_keyword(keyword, max_posts=max)

    session.completed_at = datetime.now(timezone.utc).isoformat()
    session.posts_collected = len(posts)

    if not posts:
        console.print("[red]❌ No posts collected.[/red]")
        raise typer.Exit(1)

    saved = _save_all(posts, storage, session, formats)
    _print_summary(posts, saved)

    if report:
        _run_report(posts, storage)


@app.command("keywords")
def scrape_keywords(
    keywords: str = typer.Argument(..., help="Comma-separated keywords: '#trending,viral,indonesia'"),
    max_each: int = typer.Option(30, "--max-each", "-m", help="Max posts per keyword"),
    formats: str = typer.Option("json,jsonl,csv", "--formats", "-f"),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
    proxy: Optional[str] = typer.Option(None, "--proxy"),
    delay: float = typer.Option(4.0, "--delay", "-d"),
    report: bool = typer.Option(True, "--report/--no-report"),
):
    """Scrape multiple keywords in one session (batch mode)."""
    _print_banner()

    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    console.print(f"[bold]Keywords to scrape:[/bold] {', '.join(kw_list)}")

    scraper = _build_scraper(headless, proxy, delay)
    storage = DataStorage()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping keywords...", total=len(kw_list))
        posts = []
        for kw in kw_list:
            progress.update(task, description=f"Searching: {kw}")
            batch = scraper.scrape_keyword(kw, max_posts=max_each)
            posts.extend(batch)
            progress.advance(task)

    session = ScrapeSession(
        session_id=uuid.uuid4().hex[:8],
        target=",".join(kw_list),
        target_type="multi_search",
        posts_collected=len(posts),
        completed_at=datetime.now(timezone.utc).isoformat(),
    )

    saved = _save_all(posts, storage, session, formats)
    _print_summary(posts, saved)

    if report:
        _run_report(posts, storage)


@app.command("profiles")
def scrape_profiles(
    usernames: str = typer.Argument(..., help="Comma-separated usernames: 'user1,user2,user3'"),
    max_each: int = typer.Option(20, "--max-each", "-m", help="Max posts per profile"),
    formats: str = typer.Option("json,jsonl,csv", "--formats", "-f"),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
    proxy: Optional[str] = typer.Option(None, "--proxy"),
    delay: float = typer.Option(4.0, "--delay", "-d"),
    report: bool = typer.Option(True, "--report/--no-report"),
):
    """Scrape multiple Threads profiles in one session (batch mode)."""
    _print_banner()

    user_list = [u.strip().lstrip("@") for u in usernames.split(",") if u.strip()]
    console.print(f"[bold]Profiles to scrape:[/bold] {', '.join(['@' + u for u in user_list])}")

    scraper = _build_scraper(headless, proxy, delay)
    storage = DataStorage()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Scraping profiles...", total=len(user_list))
        all_posts = []
        for username in user_list:
            progress.update(task, description=f"@{username}")
            batch = scraper.scrape_profile(username, max_posts=max_each)
            all_posts.extend(batch)
            progress.advance(task)

    session = ScrapeSession(
        session_id=uuid.uuid4().hex[:8],
        target=",".join(user_list),
        target_type="multi_profile",
        posts_collected=len(all_posts),
        completed_at=datetime.now(timezone.utc).isoformat(),
    )

    saved = _save_all(all_posts, storage, session, formats)
    _print_summary(all_posts, saved)

    if report:
        _run_report(all_posts, storage)


@app.command("feed")
def scrape_feed(
    max: int = typer.Option(
        100, "--max", "-m",
        help="Total posts to collect from feed",
    ),
    tabs: str = typer.Option(
        "for_you,following",
        "--tabs", "-t",
        help="Feed tabs (comma-sep): for_you,following",
    ),
    formats: str = typer.Option("json,jsonl,csv", "--formats", "-f"),
    headless: bool = typer.Option(True, "--headless/--no-headless"),
    proxy: Optional[str] = typer.Option(None, "--proxy"),
    delay: float = typer.Option(3.0, "--delay", "-d"),
    report: bool = typer.Option(True, "--report/--no-report"),
):
    """
    Scrape posts directly from YOUR home feed (beranda) — no keyword needed!

    Visits the 'For You' and 'Following' tabs and collects whatever
    Threads' algorithm is currently recommending / trending for your account.
    Requires THREADS_USERNAME and THREADS_PASSWORD to be set in .env.
    """
    _print_banner()

    tab_list = [t.strip() for t in tabs.split(",") if t.strip()]
    console.print(
        f"[bold]📋 Feed tabs:[/bold] {', '.join(tab_list)}  |  "
        f"[bold]🎯 Target:[/bold] {max} posts"
    )

    scraper = _build_scraper(headless, proxy, delay)
    storage = DataStorage()

    with console.status("[bold cyan]🏠 Scraping your home feed (beranda)…[/bold cyan]"):
        posts = scraper.scrape_feed(max_posts=max, feed_tabs=tab_list)

    if not posts:
        console.print(
            "[red]❌ No posts collected.[/red]\n"
            "[dim]Mungkin koneksi internet sedang lambat atau Threads sedang membatasi akses (coba gunakan opsi --no-headless)[/dim]"
        )
        raise typer.Exit(1)

    session = ScrapeSession(
        session_id=uuid.uuid4().hex[:8],
        target=f"feed:{','.join(tab_list)}",
        target_type="feed",
        posts_collected=len(posts),
        completed_at=datetime.now(timezone.utc).isoformat(),
    )

    saved = _save_all(posts, storage, session, formats)
    _print_summary(posts, saved)

    if report:
        _run_report(posts, storage)


@app.command("analyze")
def analyze_data(
    file_path: str = typer.Argument(..., help="Path to scraped JSON or JSONL file"),
    top_n: int = typer.Option(20, "--top", "-n", help="Number of top items to show"),
    save_report: bool = typer.Option(True, "--save/--no-save", help="Save report to file"),
):
    """
    Analyze previously scraped data and generate insights report.
    """
    _print_banner()
    path = Path(file_path)

    if not path.exists():
        console.print(f"[red]❌ File not found: {path}[/red]")
        raise typer.Exit(1)

    storage = DataStorage()
    if path.suffix == ".jsonl":
        posts = storage.load_jsonl(path)
    else:
        posts = storage.load_json(path)

    if not posts:
        console.print("[red]❌ No posts found in file.[/red]")
        raise typer.Exit(1)

    analyzer = ThreadsAnalyzer(posts)
    report = analyzer.generate_report()

    # Print to console
    _print_report_console(analyzer, report, top_n)

    if save_report:
        report_path = analyzer.save_report(config.EXPORT_DIR)
        console.print(f"\n[green]📄 Full report saved → {report_path}[/green]")


# ======================================================================== #
#  Display helpers                                                          #
# ======================================================================== #

def _print_summary(posts, saved: dict):
    """Print a summary table after scraping."""
    table = Table(title="✅ Scraping Complete", border_style="green")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Posts collected", str(len(posts)))
    table.add_row("Posts with media", str(sum(1 for p in posts if p.has_media)))
    table.add_row(
        "Unique users",
        str(len(set(p.username for p in posts if p.username != "dom_fallback"))),
    )
    for fmt, path in saved.items():
        table.add_row(f"Saved ({fmt.upper()})", path)
    console.print(table)


def _print_report_console(analyzer: ThreadsAnalyzer, report: dict, top_n: int):
    """Print analytics report in a rich format."""
    console.print("\n[bold magenta]═══ Analytics Report ═══[/bold magenta]\n")

    # Engagement stats
    stats = report["engagement_stats"]
    es = Table(title="📊 Engagement Stats", border_style="blue")
    es.add_column("Metric", style="cyan")
    es.add_column("Value", style="white")
    for k, v in stats.items():
        es.add_row(k.replace("_", " ").title(), str(v))
    console.print(es)

    # Top hashtags
    hashtags = report["top_hashtags"][:top_n]
    if hashtags:
        ht = Table(title="🏷️  Top Hashtags", border_style="yellow")
        ht.add_column("Hashtag", style="yellow")
        ht.add_column("Count", style="white")
        ht.add_column("% of Posts", style="dim")
        for h in hashtags:
            ht.add_row(h["hashtag"], str(h["count"]), f"{h['percentage']}%")
        console.print(ht)

    # Top words
    words = report["top_words"][:top_n]
    if words:
        wt = Table(title="📝 Top Words", border_style="green")
        wt.add_column("Word", style="green")
        wt.add_column("Count", style="white")
        for w in words[:20]:
            wt.add_row(w["word"], str(w["count"]))
        console.print(wt)

    # Trending topics
    topics = report["trending_topics"][:top_n]
    if topics:
        tt = Table(title="🔥 Trending Topics", border_style="red")
        tt.add_column("Topic", style="red")
        tt.add_column("Score", style="white")
        for t in topics:
            tt.add_row(t["topic"], str(t["score"]))
        console.print(tt)

    # Text length
    tl = report["text_length_distribution"]
    console.print(
        Panel(
            f"Avg chars: [bold]{tl.get('avg_char_length', '-')}[/bold]  |  "
            f"Avg words: [bold]{tl.get('avg_word_count', '-')}[/bold]  |  "
            f"Max chars: [bold]{tl.get('max_char_length', '-')}[/bold]",
            title="📏 Text Length",
            border_style="cyan",
        )
    )


def _run_report(posts, storage: DataStorage):
    """Run full analytics and print."""
    if not posts:
        return
    analyzer = ThreadsAnalyzer(posts)
    report = analyzer.generate_report()
    _print_report_console(analyzer, report, top_n=15)
    report_path = analyzer.save_report(config.EXPORT_DIR)
    console.print(f"\n[green]📄 Analytics report saved → {report_path}[/green]")


@app.command("generate")
def generate_content(
    report_file: str = typer.Argument(..., help="Path to analytics report JSON"),
    data_file: str = typer.Argument(..., help="Path to raw scraped data JSON"),
    num: int = typer.Option(3, "--num", "-n", help="Number of posts to generate"),
    topic: Optional[str] = typer.Option(None, "--topic", "-t", help="Specific topic to focus on"),
):
    """Generate new Threads content based on scraped trends using Gemini AI."""
    _print_banner()
    
    report_path = Path(report_file)
    data_path = Path(data_file)
    
    if not report_path.exists() or not data_path.exists():
        console.print("[red]❌ Report or data file not found.[/red]")
        raise typer.Exit(1)
        
    try:
        generator = ContentGenerator()
        with console.status("[bold cyan]🤖 AI is generating posts...[/bold cyan]"):
            posts = generator.generate_posts(report_path, data_path, num_posts=num, topic=topic)
            
        if not posts:
            console.print("[red]❌ Failed to generate posts.[/red]")
            raise typer.Exit(1)
            
        console.print("\n[bold green]✨ Generated Posts:[/bold green]")
        for i, post in enumerate(posts, 1):
            console.print(Panel(post, title=f"Draft {i}", border_style="green"))
            
    except Exception as e:
        console.print(f"[red]❌ Error:[/red] {e}")
        raise typer.Exit(1)


@app.command("autopost")
def autopost(
    text: str = typer.Argument(..., help="Text content to post"),
    headless: bool = typer.Option(False, "--headless/--no-headless", help="Run browser in headless mode"),
):
    """Automatically publish a new thread to your account."""
    _print_banner()
    
    console.print(Panel(text, title="Content to Post", border_style="cyan"))
    confirm = typer.confirm("Are you sure you want to post this to Threads?")
    if not confirm:
        console.print("[yellow]Posting cancelled.[/yellow]")
        raise typer.Exit()
        
    poster = ThreadsPoster(headless=headless, delay=config.REQUEST_DELAY)
    with console.status("[bold cyan]🚀 Publishing post to Threads...[/bold cyan]"):
        success = poster.post_thread(text)
        
    if success:
        console.print("[bold green]✅ Successfully published![/bold green]")
    else:
        console.print("[red]❌ Failed to publish post.[/red]")
        raise typer.Exit(1)


# ======================================================================== #
#  Entry point                                                              #
# ======================================================================== #

if __name__ == "__main__":
    config.ensure_dirs()
    app()
