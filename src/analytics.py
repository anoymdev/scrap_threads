"""
Analytics module: analyze scraped Threads data for AI/ML insights.

Features:
- Trending hashtags & keywords
- Language pattern analysis
- Engagement statistics
- Posting time patterns
- Content length distribution
- Word frequency analysis
"""

import re
import json
from collections import Counter
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

import pandas as pd

from .models import ThreadsPost
from .logger import setup_logger
from .config import config

logger = setup_logger("analytics", config.LOG_DIR)


class ThreadsAnalyzer:
    """
    Analyzes a collection of ThreadsPost objects.
    Generates insights useful for AI content analysis.
    """

    # Indonesian & common Bahasa stopwords
    STOPWORDS_ID = {
        "yang", "dan", "di", "ke", "dari", "ini", "itu", "atau", "dengan",
        "untuk", "ada", "tidak", "sudah", "akan", "bisa", "lebih", "juga",
        "adalah", "dalam", "pada", "aku", "kamu", "dia", "kita", "mereka",
        "nya", "ku", "mu", "si", "lah", "pun", "ya", "sih", "nih", "gue",
        "lo", "gw", "lu", "aja", "lagi", "mau", "jadi", "kalau", "kalo",
        "udah", "masih", "belum", "saja", "banget", "tapi", "yg", "yg",
        "dgn", "utk", "dg", "sm", "krn", "tp", "jg", "sdh", "blm",
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "can", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "it", "its",
        "i", "you", "he", "she", "we", "they", "me", "him", "her",
        "us", "them", "my", "your", "his", "our", "their",
    }

    def __init__(self, posts: List[ThreadsPost]):
        self.posts = posts
        self._df: Optional[pd.DataFrame] = None

    @property
    def df(self) -> pd.DataFrame:
        """Lazy-load DataFrame from posts."""
        if self._df is None:
            self._df = self._build_dataframe()
        return self._df

    def _build_dataframe(self) -> pd.DataFrame:
        rows = []
        for p in self.posts:
            rows.append({
                "post_id": p.post_id,
                "username": p.username,
                "text": p.text,
                "timestamp": p.timestamp,
                "like_count": p.like_count or 0,
                "reply_count": p.reply_count or 0,
                "repost_count": p.repost_count or 0,
                "has_media": p.has_media,
                "media_type": p.media_type,
                "hashtags": p.hashtags,
                "mentions": p.mentions,
                "source_page": p.source_page,
                "text_length": len(p.text),
                "hashtag_count": len(p.hashtags),
                "mention_count": len(p.mentions),
                "word_count": len(p.text.split()),
                "scraped_at": p.scraped_at,
            })
        df = pd.DataFrame(rows)
        if "timestamp" in df.columns:
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        return df

    # ------------------------------------------------------------------ #
    #  Trend analysis                                                      #
    # ------------------------------------------------------------------ #

    def top_hashtags(self, top_n: int = 20) -> List[Dict[str, Any]]:
        """Return the most used hashtags across all posts."""
        all_tags = []
        for p in self.posts:
            all_tags.extend([t.lower() for t in p.hashtags])
        counter = Counter(all_tags)
        return [
            {"hashtag": f"#{tag}", "count": count, "percentage": round(count / len(self.posts) * 100, 2)}
            for tag, count in counter.most_common(top_n)
        ]

    def top_mentions(self, top_n: int = 20) -> List[Dict[str, Any]]:
        """Return the most mentioned users."""
        all_mentions = []
        for p in self.posts:
            all_mentions.extend([m.lower() for m in p.mentions])
        counter = Counter(all_mentions)
        return [
            {"mention": f"@{m}", "count": count}
            for m, count in counter.most_common(top_n)
        ]

    def top_words(
        self,
        top_n: int = 50,
        exclude_stopwords: bool = True,
        min_length: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Return the most frequent words across all posts.
        Useful for vocabulary analysis and language modeling.
        """
        word_pattern = re.compile(r"\b[a-zA-Z\u00C0-\u024F\u1E00-\u1EFF]{3,}\b")
        all_words: List[str] = []

        for p in self.posts:
            text = re.sub(r"https?://\S+", "", p.text)  # Remove URLs
            words = word_pattern.findall(text.lower())
            if exclude_stopwords:
                words = [w for w in words if w not in self.STOPWORDS_ID and len(w) >= min_length]
            all_words.extend(words)

        counter = Counter(all_words)
        return [
            {"word": word, "count": count, "frequency": round(count / len(all_words) * 100, 4)}
            for word, count in counter.most_common(top_n)
        ]

    def trending_topics(self, top_n: int = 10) -> List[Dict[str, Any]]:
        """
        Identify trending topics based on combined hashtag + keyword frequency.
        """
        topics: Counter = Counter()

        # Count hashtags
        for p in self.posts:
            for tag in p.hashtags:
                topics[tag.lower()] += 3  # Weight hashtags more

        # Count high-frequency content words
        word_stats = self.top_words(top_n=50)
        for w in word_stats:
            topics[w["word"]] += w["count"]

        return [
            {"topic": topic, "score": score}
            for topic, score in topics.most_common(top_n)
        ]

    # ------------------------------------------------------------------ #
    #  Engagement analysis                                                 #
    # ------------------------------------------------------------------ #

    def engagement_stats(self) -> Dict[str, Any]:
        """Compute engagement statistics across all posts."""
        df = self.df
        likes = df["like_count"].dropna()
        replies = df["reply_count"].dropna()
        reposts = df["repost_count"].dropna()

        stats = {
            "total_posts": len(self.posts),
            "posts_with_likes": int(likes[likes > 0].count()),
            "total_likes": int(likes.sum()),
            "avg_likes": round(float(likes.mean()), 2) if len(likes) else 0,
            "median_likes": round(float(likes.median()), 2) if len(likes) else 0,
            "max_likes": int(likes.max()) if len(likes) else 0,
            "total_replies": int(replies.sum()),
            "avg_replies": round(float(replies.mean()), 2) if len(replies) else 0,
            "posts_with_media": int(df["has_media"].sum()),
            "media_percentage": round(float(df["has_media"].mean() * 100), 2),
        }
        return stats

    def top_posts_by_engagement(self, top_n: int = 10) -> pd.DataFrame:
        """Return top posts ranked by total engagement."""
        df = self.df.copy()
        df["total_engagement"] = (
            df["like_count"].fillna(0)
            + df["reply_count"].fillna(0) * 2
            + df["repost_count"].fillna(0) * 3
        )
        return df.nlargest(top_n, "total_engagement")[
            ["username", "text", "like_count", "reply_count", "total_engagement"]
        ]

    # ------------------------------------------------------------------ #
    #  Language / content pattern analysis                                 #
    # ------------------------------------------------------------------ #

    def text_length_distribution(self) -> Dict[str, Any]:
        """Analyze text length patterns."""
        lengths = self.df["text_length"]
        word_counts = self.df["word_count"]
        return {
            "avg_char_length": round(float(lengths.mean()), 2),
            "median_char_length": round(float(lengths.median()), 2),
            "max_char_length": int(lengths.max()),
            "avg_word_count": round(float(word_counts.mean()), 2),
            "median_word_count": round(float(word_counts.median()), 2),
            "max_word_count": int(word_counts.max()),
            "length_buckets": {
                "short (< 50 chars)": int((lengths < 50).sum()),
                "medium (50-150 chars)": int(((lengths >= 50) & (lengths < 150)).sum()),
                "long (150-280 chars)": int(((lengths >= 150) & (lengths < 280)).sum()),
                "very_long (> 280 chars)": int((lengths >= 280).sum()),
            },
        }

    def posting_time_analysis(self) -> Dict[str, Any]:
        """Analyze when posts are made (hour of day, day of week)."""
        df = self.df.copy()
        df_ts = df.dropna(subset=["timestamp"])

        if df_ts.empty:
            return {"note": "No timestamp data available"}

        df_ts["hour"] = df_ts["timestamp"].dt.hour
        df_ts["day_of_week"] = df_ts["timestamp"].dt.day_name()
        df_ts["date"] = df_ts["timestamp"].dt.date

        hour_dist = df_ts["hour"].value_counts().sort_index().to_dict()
        day_dist = df_ts["day_of_week"].value_counts().to_dict()

        return {
            "posts_with_timestamp": len(df_ts),
            "hourly_distribution": {str(k): v for k, v in hour_dist.items()},
            "daily_distribution": day_dist,
            "peak_hour": int(df_ts["hour"].mode().iloc[0]) if not df_ts.empty else None,
            "peak_day": df_ts["day_of_week"].mode().iloc[0] if not df_ts.empty else None,
        }

    def media_analysis(self) -> Dict[str, Any]:
        """Analyze media usage patterns."""
        df = self.df
        media_df = df[df["has_media"]]
        return {
            "total_posts_with_media": int(df["has_media"].sum()),
            "media_rate_percent": round(float(df["has_media"].mean() * 100), 2),
            "media_type_breakdown": (
                df["media_type"].value_counts().to_dict()
                if "media_type" in df.columns
                else {}
            ),
            "avg_likes_with_media": round(
                float(media_df["like_count"].mean()), 2
            ) if len(media_df) else 0,
            "avg_likes_without_media": round(
                float(df[~df["has_media"]]["like_count"].mean()), 2
            ),
        }

    def per_user_stats(self, top_n: int = 10) -> pd.DataFrame:
        """Aggregate statistics per user."""
        df = self.df
        grouped = df.groupby("username").agg(
            post_count=("post_id", "count"),
            avg_likes=("like_count", "mean"),
            total_likes=("like_count", "sum"),
            avg_replies=("reply_count", "mean"),
            avg_text_length=("text_length", "mean"),
            media_posts=("has_media", "sum"),
        ).round(2)

        return grouped.nlargest(top_n, "post_count")

    # ------------------------------------------------------------------ #
    #  Full report                                                         #
    # ------------------------------------------------------------------ #

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive analytics report.
        Returns a dict suitable for JSON serialization.
        """
        logger.info("📊 Generating analytics report…")
        report = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "dataset_size": len(self.posts),
            "engagement_stats": self.engagement_stats(),
            "top_hashtags": self.top_hashtags(20),
            "top_words": self.top_words(50),
            "trending_topics": self.trending_topics(15),
            "top_mentions": self.top_mentions(15),
            "text_length_distribution": self.text_length_distribution(),
            "posting_time_analysis": self.posting_time_analysis(),
            "media_analysis": self.media_analysis(),
        }
        return report

    def save_report(self, output_dir: Path, filename: str = None) -> Path:
        """Save the analytics report to a JSON file."""
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not filename:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"report_{ts}.json"

        path = output_dir / filename
        report = self.generate_report()

        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"📊 Report saved → [cyan]{path}[/cyan]")
        return path
