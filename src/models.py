"""
Data models for scraped Threads content.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List
from datetime import datetime
import json


@dataclass
class ThreadsUser:
    """Represents a Threads user."""
    username: str
    user_id: Optional[str] = None
    full_name: Optional[str] = None
    bio: Optional[str] = None
    follower_count: Optional[int] = None
    following_count: Optional[int] = None
    is_verified: bool = False
    profile_pic_url: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ThreadsPost:
    """Represents a single Threads post."""
    post_id: str
    username: str
    text: str
    scraped_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )

    # Optional fields
    user_id: Optional[str] = None
    timestamp: Optional[str] = None
    like_count: Optional[int] = None
    reply_count: Optional[int] = None
    repost_count: Optional[int] = None
    quote_count: Optional[int] = None
    has_media: bool = False
    media_type: Optional[str] = None  # image, video, carousel
    hashtags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    post_url: Optional[str] = None
    language_detected: Optional[str] = None
    is_reply: bool = False
    reply_to_username: Optional[str] = None
    source_page: Optional[str] = None  # profile, search, trending

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "ThreadsPost":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ScrapeSession:
    """Metadata for a scraping session."""
    session_id: str
    target: str  # username or keyword
    target_type: str  # profile, search, trending
    started_at: str = field(
        default_factory=lambda: datetime.utcnow().isoformat() + "Z"
    )
    completed_at: Optional[str] = None
    posts_collected: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
