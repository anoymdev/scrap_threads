"""
Configuration module for Threads Scraper.
Loads settings from environment variables / .env file.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # Directories
    BASE_DIR = BASE_DIR
    OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "data/raw")
    EXPORT_DIR = BASE_DIR / os.getenv("EXPORT_DIR", "data/exports")
    LOG_DIR = BASE_DIR / "logs"

    # Scraping behavior
    REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "3"))
    MAX_POSTS = int(os.getenv("MAX_POSTS", "100"))
    HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

    # Optional proxy
    PROXY_URL = os.getenv("PROXY_URL", None)

    # Optional credentials (for better access to Threads)
    THREADS_USERNAME = os.getenv("THREADS_USERNAME", None)
    THREADS_PASSWORD = os.getenv("THREADS_PASSWORD", None)

    # AI API Keys
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", None)

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # Browser
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    # Threads URLs
    BASE_URL = "https://www.threads.net"
    SEARCH_URL = "https://www.threads.net/search"

    @classmethod
    def ensure_dirs(cls):
        """Create all required directories."""
        for d in [cls.OUTPUT_DIR, cls.EXPORT_DIR, cls.LOG_DIR]:
            d.mkdir(parents=True, exist_ok=True)


config = Config()
