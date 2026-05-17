"""
Data storage module: save scraped posts to JSON, CSV, and JSONL formats.
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List

import pandas as pd

from .models import ThreadsPost, ScrapeSession
from .config import config
from .logger import setup_logger

logger = setup_logger("storage", config.LOG_DIR)


class DataStorage:
    """
    Handles persisting scraped data in multiple formats suitable for AI/ML.
    """

    def __init__(self, output_dir: Path = None, export_dir: Path = None):
        self.output_dir = Path(output_dir or config.OUTPUT_DIR)
        self.export_dir = Path(export_dir or config.EXPORT_DIR)
        config.ensure_dirs()

    # ------------------------------------------------------------------ #
    #  Save methods                                                        #
    # ------------------------------------------------------------------ #

    def save_json(
        self,
        posts: List[ThreadsPost],
        filename: str = None,
        session: ScrapeSession = None,
    ) -> Path:
        """
        Save posts as a structured JSON file (best for ML pipelines).
        """
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"threads_{ts}.json"

        path = self.output_dir / filename
        data = {
            "schema_version": "1.0",
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "total_posts": len(posts),
            "session": session.to_dict() if session else None,
            "posts": [p.to_dict() for p in posts],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"💾 Saved [bold]{len(posts)}[/bold] posts → [cyan]{path}[/cyan]")
        return path

    def save_jsonl(
        self,
        posts: List[ThreadsPost],
        filename: str = None,
    ) -> Path:
        """
        Save as JSONL (JSON Lines) — ideal for streaming ML training data.
        Each line is a valid JSON object.
        """
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"threads_{ts}.jsonl"

        path = self.output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            for post in posts:
                f.write(json.dumps(post.to_dict(), ensure_ascii=False) + "\n")

        logger.info(f"💾 Saved [bold]{len(posts)}[/bold] posts (JSONL) → [cyan]{path}[/cyan]")
        return path

    def save_csv(
        self,
        posts: List[ThreadsPost],
        filename: str = None,
    ) -> Path:
        """
        Save as CSV — easy to open in Excel/Sheets for quick review.
        """
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"threads_{ts}.csv"

        path = self.export_dir / filename
        if not posts:
            logger.warning("No posts to save as CSV.")
            return path

        fieldnames = list(posts[0].to_dict().keys())
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for post in posts:
                row = post.to_dict()
                # Convert lists to pipe-separated strings for CSV
                for k, v in row.items():
                    if isinstance(v, list):
                        row[k] = " | ".join(v)
                writer.writerow(row)

        logger.info(f"💾 Saved [bold]{len(posts)}[/bold] posts (CSV) → [cyan]{path}[/cyan]")
        return path

    def save_text_corpus(
        self,
        posts: List[ThreadsPost],
        filename: str = None,
    ) -> Path:
        """
        Save only the post texts as a plain text corpus.
        Useful for LLM fine-tuning or NLP preprocessing.
        """
        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"corpus_{ts}.txt"

        path = self.export_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            for post in posts:
                if post.text.strip():
                    f.write(post.text.strip() + "\n\n")

        logger.info(f"💾 Saved text corpus ({len(posts)} entries) → [cyan]{path}[/cyan]")
        return path

    def append_jsonl(self, posts: List[ThreadsPost], filename: str) -> Path:
        """
        Append posts to an existing JSONL file (useful for incremental collection).
        """
        path = self.output_dir / filename
        with open(path, "a", encoding="utf-8") as f:
            for post in posts:
                f.write(json.dumps(post.to_dict(), ensure_ascii=False) + "\n")

        logger.info(f"➕ Appended [bold]{len(posts)}[/bold] posts → [cyan]{path}[/cyan]")
        return path

    # ------------------------------------------------------------------ #
    #  Load methods                                                        #
    # ------------------------------------------------------------------ #

    def load_json(self, path: Path) -> List[ThreadsPost]:
        """Load posts from a previously saved JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        posts = [ThreadsPost.from_dict(p) for p in data.get("posts", [])]
        logger.info(f"📂 Loaded {len(posts)} posts from {path}")
        return posts

    def load_jsonl(self, path: Path) -> List[ThreadsPost]:
        """Load posts from a JSONL file."""
        posts = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    posts.append(ThreadsPost.from_dict(json.loads(line)))
        logger.info(f"📂 Loaded {len(posts)} posts from {path}")
        return posts

    def to_dataframe(self, posts: List[ThreadsPost]) -> "pd.DataFrame":
        """Convert posts to a Pandas DataFrame for analysis."""
        rows = []
        for post in posts:
            row = post.to_dict()
            # Flatten list fields
            row["hashtags"] = " | ".join(row.get("hashtags", []))
            row["mentions"] = " | ".join(row.get("mentions", []))
            row["links"] = " | ".join(row.get("links", []))
            rows.append(row)
        return pd.DataFrame(rows)
