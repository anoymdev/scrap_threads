#!/usr/bin/env python3
"""
Quick-start example scripts for the Threads Scraper.
Run this file directly to see examples of how to use the scraper programmatically.
"""

from src.scraper import ThreadsScraper
from src.storage import DataStorage
from src.analytics import ThreadsAnalyzer
from src.config import config
from rich.console import Console

console = Console()

# ------------------------------------------------------------------ #
#  Example 1: Scrape a single profile                                 #
# ------------------------------------------------------------------ #

def example_profile():
    """Scrape posts from a single public Threads profile."""
    config.ensure_dirs()

    scraper = ThreadsScraper(headless=True, delay=3.0)
    storage = DataStorage()

    # Change username to any public Threads account
    posts = scraper.scrape_profile("zuck", max_posts=20)

    if posts:
        storage.save_json(posts, "example_profile.json")
        storage.save_csv(posts, "example_profile.csv")

        console.print(f"\n✅ Scraped {len(posts)} posts")
        for p in posts[:3]:
            console.print(f"\n[cyan]@{p.username}[/cyan]: {p.text[:100]}...")


# ------------------------------------------------------------------ #
#  Example 2: Scrape by keyword / hashtag                             #
# ------------------------------------------------------------------ #

def example_keyword():
    """Search and scrape posts by keyword."""
    config.ensure_dirs()

    scraper = ThreadsScraper(headless=True, delay=3.0)
    storage = DataStorage()

    # Try Indonesian trending keywords
    posts = scraper.scrape_keyword("#indonesia", max_posts=30)

    if posts:
        storage.save_jsonl(posts, "example_keyword.jsonl")
        storage.save_text_corpus(posts, "example_corpus.txt")
        console.print(f"\n✅ Found {len(posts)} posts for #indonesia")


# ------------------------------------------------------------------ #
#  Example 3: Batch scrape multiple keywords                          #
# ------------------------------------------------------------------ #

def example_batch_keywords():
    """Scrape multiple keywords and analyze."""
    config.ensure_dirs()

    keywords = [
        "#indonesia",
        "#viral",
        "#trending",
        "berita",
        "teknologi",
    ]

    scraper = ThreadsScraper(headless=True, delay=4.0)
    storage = DataStorage()

    all_posts = scraper.scrape_multiple_keywords(keywords, max_posts_each=20)

    if all_posts:
        storage.save_json(all_posts, "batch_keywords.json")
        storage.save_jsonl(all_posts, "batch_keywords.jsonl")

        # Analyze collected data
        analyzer = ThreadsAnalyzer(all_posts)
        report = analyzer.generate_report()

        console.print(f"\n[bold]Dataset:[/bold] {len(all_posts)} posts")
        console.print(f"[bold]Top hashtags:[/bold]")
        for h in report["top_hashtags"][:10]:
            console.print(f"  {h['hashtag']}: {h['count']}")

        console.print(f"\n[bold]Top words:[/bold]")
        for w in report["top_words"][:10]:
            console.print(f"  {w['word']}: {w['count']}")

        analyzer.save_report(config.EXPORT_DIR, "batch_report.json")


# ------------------------------------------------------------------ #
#  Example 4: Analyze existing data                                   #
# ------------------------------------------------------------------ #

def example_analyze_existing():
    """Load and analyze data from a previously saved file."""
    import json
    from pathlib import Path
    from src.models import ThreadsPost

    # Look for any existing JSON file
    data_dir = config.OUTPUT_DIR
    json_files = list(data_dir.glob("*.json"))

    if not json_files:
        console.print("[yellow]No JSON files found. Run a scrape first.[/yellow]")
        return

    latest = sorted(json_files)[-1]
    console.print(f"📂 Loading: {latest}")

    storage = DataStorage()
    posts = storage.load_json(latest)

    if posts:
        analyzer = ThreadsAnalyzer(posts)
        report = analyzer.generate_report()
        analyzer.save_report(config.EXPORT_DIR)

        console.print(f"\n[bold]Dataset stats:[/bold]")
        stats = report["engagement_stats"]
        console.print(f"  Total posts: {stats['total_posts']}")
        console.print(f"  Total likes: {stats['total_likes']}")
        console.print(f"  Avg likes: {stats['avg_likes']}")
        console.print(f"  Posts with media: {stats['posts_with_media']}")


# ------------------------------------------------------------------ #
#  Run                                                                 #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    import sys

    examples = {
        "profile": example_profile,
        "keyword": example_keyword,
        "batch": example_batch_keywords,
        "analyze": example_analyze_existing,
    }

    if len(sys.argv) > 1 and sys.argv[1] in examples:
        examples[sys.argv[1]]()
    else:
        console.print("[bold]Available examples:[/bold]")
        for name in examples:
            console.print(f"  python examples.py {name}")
