"""
Core Playwright-based scraper for Threads.net.

Strategy:
 1. Launch Chromium in (headless) mode
 2. Login with credentials (if provided) & persist session cookies
 3. Intercept /api/graphql network responses
 4. Parse JSON data to extract post fields
 5. Fall back to DOM parsing when GraphQL data is unavailable
"""

import json
import time
import random
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Callable

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext, Response

from .models import ThreadsPost, ThreadsUser, ScrapeSession
from .config import config
from .logger import setup_logger

logger = setup_logger("scraper", config.LOG_DIR)


class ThreadsScraper:
    """
    Main scraper class for Threads.net.
    Uses Playwright to intercept GraphQL responses and DOM-parse as fallback.
    Supports authenticated sessions via saved cookies.
    """

    COOKIE_FILE = config.BASE_DIR / ".session_cookies.json"
    LOGIN_URL = "https://www.threads.net/login"

    def __init__(
        self,
        headless: bool = None,
        proxy: str = None,
        delay: float = None,
    ):
        self.headless = headless if headless is not None else config.HEADLESS
        self.proxy = proxy or config.PROXY_URL
        self.delay = delay if delay is not None else config.REQUEST_DELAY
        self.username = config.THREADS_USERNAME
        self.password = config.THREADS_PASSWORD
        self._captured: List[Dict[str, Any]] = []
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

    # ------------------------------------------------------------------ #
    #  Browser lifecycle                                                   #
    # ------------------------------------------------------------------ #

    def _launch(self, playwright):
        """Launch browser with optional proxy and stealth settings."""
        launch_opts: Dict[str, Any] = {
            "headless": self.headless,
            "args": [
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        }
        if self.proxy:
            launch_opts["proxy"] = {"server": self.proxy}

        self._browser = playwright.chromium.launch(**launch_opts)

        context_opts: Dict[str, Any] = {
            "user_agent": config.USER_AGENT,
            "viewport": {"width": 1280, "height": 800},
            "locale": "id-ID",  # Indonesian locale
            "timezone_id": "Asia/Jakarta",
        }
        self._context = self._browser.new_context(**context_opts)

        # Mask webdriver flag
        self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        # Restore saved session cookies if available
        if self.COOKIE_FILE.exists():
            try:
                cookies = json.loads(self.COOKIE_FILE.read_text())
                self._context.add_cookies(cookies)
                logger.info("🍪 Restored session cookies from cache")
            except Exception as exc:
                logger.warning(f"Cookie restore failed: {exc}")

    # ------------------------------------------------------------------ #
    #  Login                                                               #
    # ------------------------------------------------------------------ #

    def login(self, page) -> bool:
        """
        Authenticate with Threads using stored credentials.
        Saves session cookies on success for future reuse.
        Returns True if login was successful.
        """
        if not self.username or not self.password:
            logger.debug("No credentials configured, skipping login.")
            return False

        logger.info(f"🔐 Logging in as [bold cyan]{self.username}[/bold cyan]…")

        try:
            page.goto(self.LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
            time.sleep(random.uniform(1.5, 2.5))

            # ── Accept cookies / consent dialog if present ──────────────
            for consent_sel in [
                "button[data-cookiebanner='accept_only_essential']",
                "button:has-text('Allow essential')",
                "button:has-text('Accept')",
                "[aria-label='Allow essential and optional cookies']",
                "button:has-text('Izinkan')",
            ]:
                try:
                    btn = page.wait_for_selector(consent_sel, timeout=3000)
                    if btn:
                        btn.click()
                        time.sleep(1)
                        break
                except Exception:
                    pass

            # ── Fill username ────────────────────────────────────────────
            username_selectors = [
                "input[name='username']",
                "input[autocomplete='username']",
                "input[type='text']",
            ]
            username_field = None
            for sel in username_selectors:
                try:
                    username_field = page.wait_for_selector(sel, timeout=5000)
                    if username_field:
                        break
                except Exception:
                    pass

            if not username_field:
                logger.error("❌ Could not find username field on login page.")
                return False

            username_field.click()
            time.sleep(random.uniform(0.3, 0.7))
            # Type character-by-character to appear human
            for char in self.username:
                username_field.type(char, delay=random.randint(50, 130))
            time.sleep(random.uniform(0.5, 1.0))

            # ── Fill password ────────────────────────────────────────────
            password_selectors = [
                "input[name='password']",
                "input[type='password']",
            ]
            password_field = None
            for sel in password_selectors:
                try:
                    password_field = page.wait_for_selector(sel, timeout=5000)
                    if password_field:
                        break
                except Exception:
                    pass

            if not password_field:
                logger.error("❌ Could not find password field.")
                return False

            password_field.click()
            time.sleep(random.uniform(0.3, 0.6))
            for char in self.password:
                password_field.type(char, delay=random.randint(50, 140))
            time.sleep(random.uniform(0.5, 1.0))

            # ── Submit ───────────────────────────────────────────────────
            submit_selectors = [
                "button[type='submit']",
                "button:has-text('Log in')",
                "button:has-text('Masuk')",
                "div[role='button']:has-text('Log in')",
            ]
            submitted = False
            for sel in submit_selectors:
                try:
                    btn = page.wait_for_selector(sel, timeout=3000)
                    if btn:
                        btn.click()
                        submitted = True
                        break
                except Exception:
                    pass

            if not submitted:
                # Fallback: press Enter
                password_field.press("Enter")

            # ── Wait for navigation post-login ───────────────────────────
            try:
                page.wait_for_url(
                    lambda url: "threads.net" in url and "/login" not in url,
                    timeout=20_000,
                )
            except Exception:
                # If no redirect, check if we're past the login wall
                time.sleep(4)

            current_url = page.url
            if "/login" in current_url or "/accounts/login" in current_url:
                logger.error("❌ Login failed — still on login page. Check credentials.")
                return False

            # ── Save cookies for future sessions ─────────────────────────
            cookies = self._context.cookies()
            self.COOKIE_FILE.write_text(json.dumps(cookies, ensure_ascii=False))
            logger.info("✅ Login successful — session cookies saved")
            return True

        except Exception as exc:
            logger.error(f"❌ Login error: {exc}")
            return False

    def _ensure_authenticated(self, page) -> bool:
        """
        Ensure the session is authenticated.
        If cookies are cached, verify by checking current page URL.
        Falls back to full login if needed.
        """
        if not self.username or not self.password:
            return False

        # If we have cached cookies, do a quick check
        if self.COOKIE_FILE.exists():
            page.goto(config.BASE_URL, wait_until="domcontentloaded", timeout=20_000)
            time.sleep(2)
            if "/login" not in page.url:
                logger.info("🍪 Session valid — using cached cookies")
                return True
            else:
                logger.info("⚠️  Cached session expired, re-logging in…")
                self.COOKIE_FILE.unlink(missing_ok=True)

        return self.login(page)

    def _close(self):
        """Gracefully close browser."""
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()

    # ------------------------------------------------------------------ #
    #  Network interception                                                #
    # ------------------------------------------------------------------ #

    def _make_response_handler(self, posts_list: List[ThreadsPost], source_page: str):
        """
        Returns a closure that captures Threads GraphQL responses.
        """
        def handle_response(response: Response):
            if "/api/graphql" not in response.url:
                return
            if response.status != 200:
                return
            try:
                data = response.json()
                extracted = self._parse_graphql(data, source_page)
                posts_list.extend(extracted)
                if extracted:
                    logger.debug(f"GraphQL → captured {len(extracted)} posts")
            except Exception as exc:
                logger.debug(f"GraphQL parse error: {exc}")

        return handle_response

    def _parse_graphql(
        self, data: dict, source_page: str
    ) -> List[ThreadsPost]:
        """
        Walk the GraphQL JSON tree and extract post objects.
        Threads uses many nested structures; we traverse recursively.
        """
        posts: List[ThreadsPost] = []
        self._walk_graphql(data, posts, source_page)
        return posts

    def _walk_graphql(self, node: Any, posts: List[ThreadsPost], source_page: str):
        """Recursively walk a JSON node looking for thread_items / edges."""
        if isinstance(node, dict):
            # Common GraphQL edge patterns
            for key in ("thread_items", "edges", "nodes", "items"):
                if key in node and isinstance(node[key], list):
                    for item in node[key]:
                        post = self._extract_post_from_node(item, source_page)
                        if post:
                            posts.append(post)
                        else:
                            self._walk_graphql(item, posts, source_page)

            # Walk all values
            for value in node.values():
                if isinstance(value, (dict, list)):
                    self._walk_graphql(value, posts, source_page)

        elif isinstance(node, list):
            for item in node:
                self._walk_graphql(item, posts, source_page)

    def _extract_post_from_node(self, node: Any, source_page: str) -> Optional[ThreadsPost]:
        """
        Try to construct a ThreadsPost from a single GraphQL node.
        Returns None if the node doesn't look like a post.
        """
        if not isinstance(node, dict):
            return None

        # Threads often wraps posts under 'post' or 'thread_item'
        post_node = node.get("post") or node.get("thread_item") or node
        if not isinstance(post_node, dict):
            return None

        # Must have caption / text
        caption_node = post_node.get("caption") or {}
        text = (
            caption_node.get("text", "")
            if isinstance(caption_node, dict)
            else str(caption_node)
        )

        # Alternative text locations
        if not text:
            text = post_node.get("text", "") or post_node.get("accessibility_caption", "")

        if not text:
            return None

        # User
        user_node = post_node.get("user") or {}
        username = user_node.get("username", "unknown") if isinstance(user_node, dict) else "unknown"
        user_id = str(user_node.get("pk", "")) if isinstance(user_node, dict) else None

        # Post ID
        post_id = str(
            post_node.get("pk")
            or post_node.get("id")
            or uuid.uuid4().hex[:12]
        )

        # Timestamp
        taken_at = post_node.get("taken_at")
        timestamp = None
        if taken_at:
            try:
                timestamp = datetime.utcfromtimestamp(int(taken_at)).isoformat() + "Z"
            except Exception:
                timestamp = str(taken_at)

        # Engagement
        like_count = post_node.get("like_count")
        reply_count = (
            post_node.get("text_post_app_info", {}) or {}
        ).get("direct_reply_count") or post_node.get("comment_count")

        # Media
        has_media = bool(
            post_node.get("image_versions2")
            or post_node.get("video_versions")
            or post_node.get("carousel_media")
        )
        if post_node.get("carousel_media"):
            media_type = "carousel"
        elif post_node.get("video_versions"):
            media_type = "video"
        elif post_node.get("image_versions2"):
            media_type = "image"
        else:
            media_type = None

        # Hashtags & mentions from text
        hashtags = re.findall(r"#(\w+)", text)
        mentions = re.findall(r"@(\w+(?:\.\w+)*)", text)
        links = re.findall(r"https?://\S+", text)

        # Post URL
        code = post_node.get("code") or post_node.get("shortcode", "")
        post_url = f"https://www.threads.net/t/{code}" if code else None

        return ThreadsPost(
            post_id=post_id,
            username=username,
            user_id=user_id,
            text=text,
            timestamp=timestamp,
            like_count=like_count,
            reply_count=reply_count,
            has_media=has_media,
            media_type=media_type,
            hashtags=hashtags,
            mentions=mentions,
            links=links,
            post_url=post_url,
            source_page=source_page,
        )

    # ------------------------------------------------------------------ #
    #  DOM fallback parser                                                 #
    # ------------------------------------------------------------------ #

    def _dom_fallback(self, page: Page, source_page: str) -> List[ThreadsPost]:
        """
        Fallback: parse visible post text elements from DOM.
        Less reliable but works when GraphQL data is minimal.
        """
        posts: List[ThreadsPost] = []
        try:
            # Common selectors for Threads post text
            selectors = [
                "div[data-pressable-container] span",
                "article span",
                "[class*='x1lliihq']",  # Threads-specific class patterns
            ]
            for sel in selectors:
                elements = page.query_selector_all(sel)
                for el in elements:
                    text = el.inner_text().strip()
                    if len(text) > 20:  # Skip very short snippets
                        posts.append(
                            ThreadsPost(
                                post_id=uuid.uuid4().hex[:12],
                                username="dom_fallback",
                                text=text,
                                source_page=source_page,
                                hashtags=re.findall(r"#(\w+)", text),
                                mentions=re.findall(r"@(\w+(?:\.\w+)*)", text),
                                links=re.findall(r"https?://\S+", text),
                            )
                        )
                if posts:
                    break
        except Exception as exc:
            logger.warning(f"DOM fallback failed: {exc}")
        return posts

    # ------------------------------------------------------------------ #
    #  Public scraping methods                                             #
    # ------------------------------------------------------------------ #

    def _human_scroll(self, page: Page, times: int = 5, delay: float = None):
        """Simulate human-like scrolling to trigger lazy loading."""
        for _ in range(times):
            page.mouse.wheel(0, random.randint(600, 1200))
            time.sleep(delay or self.delay + random.uniform(0.5, 1.5))

    def scrape_profile(
        self,
        username: str,
        max_posts: int = None,
    ) -> List[ThreadsPost]:
        """
        Scrape posts from a public Threads profile.

        Args:
            username: Threads username (without @)
            max_posts: Maximum number of posts to collect

        Returns:
            List of ThreadsPost objects
        """
        max_posts = max_posts or config.MAX_POSTS
        url = f"{config.BASE_URL}/@{username.lstrip('@')}"
        logger.info(f"[bold cyan]Scraping profile:[/bold cyan] @{username}")

        posts: List[ThreadsPost] = []

        with sync_playwright() as p:
            self._launch(p)
            page = self._context.new_page()
            page.on("response", self._make_response_handler(posts, f"profile:{username}"))

            try:
                # Authenticate first for richer data
                self._ensure_authenticated(page)

                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                time.sleep(2)

                scrolls = max(3, max_posts // 10)
                self._human_scroll(page, times=scrolls)

                if not posts:
                    logger.warning("GraphQL interception empty, trying DOM fallback…")
                    dom_posts = self._dom_fallback(page, f"profile:{username}")
                    posts.extend(dom_posts)

            except Exception as exc:
                logger.error(f"Error scraping profile @{username}: {exc}")
            finally:
                self._close()

        unique = self._deduplicate(posts)[:max_posts]
        logger.info(f"✅ Collected [bold green]{len(unique)}[/bold green] posts from @{username}")
        return unique

    def scrape_keyword(
        self,
        keyword: str,
        max_posts: int = None,
    ) -> List[ThreadsPost]:
        """
        Scrape posts by searching a keyword/hashtag.

        Args:
            keyword: Search term (can include # for hashtags)
            max_posts: Maximum number of posts to collect

        Returns:
            List of ThreadsPost objects
        """
        max_posts = max_posts or config.MAX_POSTS
        # Clean keyword - remove # prefix for URL
        clean_kw = keyword.lstrip("#")
        search_url = f"{config.SEARCH_URL}?q={clean_kw}&serp_type=default"
        logger.info(f"[bold cyan]Searching keyword:[/bold cyan] {keyword}")

        posts: List[ThreadsPost] = []

        with sync_playwright() as p:
            self._launch(p)
            page = self._context.new_page()
            page.on("response", self._make_response_handler(posts, f"search:{keyword}"))

            try:
                # Authenticate first for richer data
                self._ensure_authenticated(page)

                page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
                time.sleep(3)

                scrolls = max(5, max_posts // 8)
                self._human_scroll(page, times=scrolls)

                if not posts:
                    logger.warning("GraphQL interception empty, trying DOM fallback…")
                    dom_posts = self._dom_fallback(page, f"search:{keyword}")
                    posts.extend(dom_posts)

            except Exception as exc:
                logger.error(f"Error searching '{keyword}': {exc}")
            finally:
                self._close()

        unique = self._deduplicate(posts)[:max_posts]
        logger.info(f"✅ Collected [bold green]{len(unique)}[/bold green] posts for '{keyword}'")
        return unique

    def scrape_multiple_profiles(
        self,
        usernames: List[str],
        max_posts_each: int = 30,
        progress_callback: Optional[Callable] = None,
    ) -> List[ThreadsPost]:
        """
        Scrape multiple profiles sequentially with rate-limiting.
        """
        all_posts: List[ThreadsPost] = []
        for i, username in enumerate(usernames, 1):
            logger.info(f"[{i}/{len(usernames)}] @{username}")
            try:
                posts = self.scrape_profile(username, max_posts=max_posts_each)
                all_posts.extend(posts)
                if progress_callback:
                    progress_callback(i, len(usernames), username, len(posts))
            except Exception as exc:
                logger.error(f"Failed for @{username}: {exc}")

            if i < len(usernames):
                sleep_time = self.delay * 2 + random.uniform(1, 3)
                logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)

        logger.info(f"✅ Total collected: [bold green]{len(all_posts)}[/bold green] posts")
        return all_posts

    def scrape_multiple_keywords(
        self,
        keywords: List[str],
        max_posts_each: int = 30,
    ) -> List[ThreadsPost]:
        """
        Scrape multiple keywords sequentially.
        """
        all_posts: List[ThreadsPost] = []
        for i, kw in enumerate(keywords, 1):
            logger.info(f"[{i}/{len(keywords)}] Keyword: {kw}")
            try:
                posts = self.scrape_keyword(kw, max_posts=max_posts_each)
                all_posts.extend(posts)
            except Exception as exc:
                logger.error(f"Failed for keyword '{kw}': {exc}")

            if i < len(keywords):
                sleep_time = self.delay * 2 + random.uniform(1, 3)
                time.sleep(sleep_time)

        return all_posts

    def scrape_feed(
        self,
        max_posts: int = None,
        feed_tabs: List[str] = None,
    ) -> List[ThreadsPost]:
        """
        Scrape posts from the authenticated user's home feed (beranda).

        Requires credentials in .env (THREADS_USERNAME / THREADS_PASSWORD).
        Scrapes the "For You" and optionally "Following" tabs — whatever
        Threads' algorithm is currently showing as trending/recommended.

        Args:
            max_posts:  Total maximum posts to collect across all tabs.
            feed_tabs:  List of tab names to visit. Defaults to ["for_you", "following"].
                        Options: "for_you", "following"

        Returns:
            List of ThreadsPost objects tagged with source_page="feed:for_you"
            or "feed:following".
        """
        if not self.username or not self.password:
            logger.warning(
                "⚠️ No credentials in .env. Proceeding with unauthenticated public feed scrape."
            )
            feed_tabs = ["for_you"]  # Only public feed is available without login
        else:
            feed_tabs = feed_tabs or ["for_you", "following"]

        max_posts = max_posts or config.MAX_POSTS
        all_posts: List[ThreadsPost] = []

        # Tab label → aria-label / text Threads uses in the nav
        tab_selectors = {
            "for_you": [
                "a[href='/']:has-text('For you')",
                "a[href='/']:has-text('Untuk Anda')",
                "[role='tab']:has-text('For you')",
                "[role='tab']:has-text('Untuk Anda')",
                "span:has-text('For you')",
                "span:has-text('Untuk Anda')",
            ],
            "following": [
                "a[href='/following']:has-text('Following')",
                "a[href='/following']:has-text('Mengikuti')",
                "[role='tab']:has-text('Following')",
                "[role='tab']:has-text('Mengikuti')",
                "span:has-text('Following')",
                "span:has-text('Mengikuti')",
            ],
        }

        with sync_playwright() as p:
            self._launch(p)
            page = self._context.new_page()

            try:
                # ── Authenticate ──────────────────────────────────────────
                logged_in = self._ensure_authenticated(page)
                if not logged_in and (self.username and self.password):
                    logger.error("❌ Authentication failed. Cannot scrape feed.")
                    return []

                # After auth we're already on the home feed — let it settle
                logger.info("🏠 Loading home feed…")
                time.sleep(random.uniform(2, 3))

                for tab_name in feed_tabs:
                    source = f"feed:{tab_name}"
                    tab_posts: List[ThreadsPost] = []

                    # Attach per-tab response listener
                    def _handler(response: Response, _src=source):
                        if "/api/graphql" not in response.url or response.status != 200:
                            return
                        try:
                            data = response.json()
                            extracted = self._parse_graphql(data, _src)
                            tab_posts.extend(extracted)
                            if extracted:
                                logger.debug(f"GraphQL [{_src}] → {len(extracted)} posts")
                        except Exception:
                            pass

                    page.on("response", _handler)

                    # ── Navigate to / click the correct tab ──────────────
                    if tab_name == "for_you":
                        # Home feed is the root; navigate fresh
                        page.goto(config.BASE_URL, wait_until="domcontentloaded", timeout=30_000)
                        time.sleep(random.uniform(2, 3))
                    else:
                        # Try clicking the tab button first
                        clicked = False
                        for sel in tab_selectors.get(tab_name, []):
                            try:
                                el = page.wait_for_selector(sel, timeout=4000)
                                if el:
                                    el.click()
                                    clicked = True
                                    logger.info(f"🗂️  Switched to tab: {tab_name}")
                                    time.sleep(random.uniform(1.5, 2.5))
                                    break
                            except Exception:
                                pass

                        if not clicked:
                            # Fallback: navigate directly
                            follow_url = f"{config.BASE_URL}/following"
                            page.goto(follow_url, wait_until="domcontentloaded", timeout=30_000)
                            time.sleep(random.uniform(2, 3))
                            logger.info(f"🗂️  Navigated to: {follow_url}")

                    logger.info(
                        f"📜 Scrolling [{tab_name}] feed "
                        f"(target ≈ {max_posts // len(feed_tabs)} posts)…"
                    )

                    # ── Scroll to load posts ──────────────────────────────
                    per_tab_target = max_posts // len(feed_tabs)
                    scroll_rounds = max(8, per_tab_target // 5)
                    for i in range(scroll_rounds):
                        page.mouse.wheel(0, random.randint(700, 1400))
                        time.sleep(self.delay + random.uniform(0.3, 1.2))

                        # Early exit if we have enough
                        if len(tab_posts) >= per_tab_target:
                            logger.debug(
                                f"Reached target ({len(tab_posts)} posts), stopping scroll."
                            )
                            break

                    # ── DOM fallback if GraphQL captured nothing ──────────
                    if not tab_posts:
                        logger.warning(
                            f"GraphQL interception empty for [{tab_name}], "
                            "trying DOM fallback…"
                        )
                        tab_posts = self._dom_fallback_feed(page, source)

                    page.remove_listener("response", _handler)
                    all_posts.extend(tab_posts)
                    logger.info(
                        f"  ↳ [{tab_name}] collected "
                        f"[bold green]{len(tab_posts)}[/bold green] posts"
                    )

                    # Brief pause between tabs
                    if tab_name != feed_tabs[-1]:
                        time.sleep(random.uniform(2, 4))

            except Exception as exc:
                logger.error(f"Error scraping feed: {exc}")
            finally:
                self._close()

        unique = self._deduplicate(all_posts)[:max_posts]
        logger.info(
            f"✅ Feed scrape complete — "
            f"[bold green]{len(unique)}[/bold green] total posts"
        )
        return unique

    def _dom_fallback_feed(self, page: Page, source_page: str) -> List[ThreadsPost]:
        """
        DOM fallback specifically tuned for the home feed layout.
        Tries article-level containers first for better text isolation.
        """
        posts: List[ThreadsPost] = []
        seen_texts: set = set()

        # Ordered from most- to least-specific
        selectors = [
            # Feed post containers (Threads 2024+ structure)
            "article div[dir='auto']",
            "div[data-pressable-container] div[dir='auto']",
            # Generic text spans with some minimum size
            "span[dir='auto']",
            "div[dir='auto']",
        ]

        try:
            for sel in selectors:
                elements = page.query_selector_all(sel)
                for el in elements:
                    try:
                        text = el.inner_text().strip()
                    except Exception:
                        continue

                    # Filter: must be meaningful post content
                    if len(text) < 25 or text in seen_texts:
                        continue
                    # Skip nav / UI labels
                    if text.lower() in {
                        "for you", "following", "untuk anda", "mengikuti",
                        "threads", "home", "search", "notifications",
                        "profile", "create", "more", "settings",
                    }:
                        continue

                    seen_texts.add(text)
                    posts.append(
                        ThreadsPost(
                            post_id=uuid.uuid4().hex[:12],
                            username="dom_fallback",
                            text=text,
                            source_page=source_page,
                            hashtags=re.findall(r"#(\w+)", text),
                            mentions=re.findall(r"@(\w+(?:\.\w+)*)", text),
                            links=re.findall(r"https?://\S+", text),
                        )
                    )

                if posts:
                    break

        except Exception as exc:
            logger.warning(f"DOM feed fallback error: {exc}")

        return posts

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _deduplicate(self, posts: List[ThreadsPost]) -> List[ThreadsPost]:
        """Remove duplicate posts by post_id."""
        seen = set()
        unique = []
        for post in posts:
            if post.post_id not in seen:
                seen.add(post.post_id)
                unique.append(post)
        return unique
