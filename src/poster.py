import time
import random
import logging
from typing import List

from playwright.sync_api import sync_playwright

from .config import config
from .scraper import ThreadsScraper

logger = logging.getLogger("poster")

class ThreadsPoster(ThreadsScraper):
    """
    Extends ThreadsScraper to support posting new threads.
    Requires valid session cookies (must have logged in before).
    """

    def post_thread(self, text: str) -> bool:
        """
        Automates UI to post a new thread.
        Returns True if successful.
        """
        if not self.username or not self.password:
            logger.error("❌ Posting requires credentials in .env")
            return False

        if not self.COOKIE_FILE.exists():
            logger.error("❌ No session cookies found. Please run a scrape with login first.")
            return False

        logger.info(f"🚀 Preparing to post to Threads as @{self.username}...")

        with sync_playwright() as p:
            self._launch(p)
            page = self._context.new_page()

            try:
                # ── Authenticate ──────────────────────────────────────────
                logged_in = self._ensure_authenticated(page)
                if not logged_in:
                    logger.error("❌ Authentication failed. Cannot post.")
                    return False

                # We should be on the home feed now
                time.sleep(random.uniform(2, 4))
                
                logger.info("🖱️  Clicking 'Start a thread' button...")
                
                # Locate the new thread button. 
                # This changes often but typically it's an SVG or a button with aria-label
                button_selectors = [
                    "svg[aria-label='New thread']",
                    "svg[aria-label='Utas baru']",
                    "div[role='button']:has-text('Start a thread')",
                    "div[role='button']:has-text('Mulai utas')",
                    "a[href='/compose']", # Sometimes it's a link
                ]
                
                clicked = False
                for sel in button_selectors:
                    try:
                        btn = page.wait_for_selector(sel, timeout=3000)
                        if btn:
                            # It might be the SVG inside an anchor/button, so we click the parent
                            btn.click()
                            clicked = True
                            break
                    except Exception:
                        pass
                
                # Keyboard shortcut fallback (usually 'n' or 'c' on some platforms, or navigate to /compose)
                if not clicked:
                    logger.debug("Falling back to navigation to /compose")
                    page.goto(f"{config.BASE_URL}/compose", wait_until="domcontentloaded", timeout=15000)
                
                time.sleep(random.uniform(1, 2))
                
                # Focus the text area
                editor_selectors = [
                    "div[contenteditable='true'][role='textbox']",
                    "div[contenteditable='true']",
                    "div[role='textbox'][aria-label*='thread' i]",
                    "div[role='textbox'][aria-label*='utas' i]",
                ]
                
                editor = None
                for sel in editor_selectors:
                    try:
                        editor = page.wait_for_selector(sel, timeout=5000)
                        if editor:
                            break
                    except Exception:
                        pass
                        
                if not editor:
                    logger.error("❌ Could not find the text editor box.")
                    return False
                    
                logger.info("⌨️  Typing content...")
                editor.click()
                time.sleep(0.5)
                
                # Type out the text (simulate human typing speed)
                editor.type(text, delay=random.randint(20, 80))
                time.sleep(random.uniform(1, 2))
                
                # Find and click the Post button
                logger.info("🖱️  Clicking 'Post'...")
                post_btn_selectors = [
                    "div[role='button']:has-text('Post')",
                    "div[role='button']:has-text('Posting')",
                ]
                
                posted = False
                for sel in post_btn_selectors:
                    try:
                        # Ensure we don't click a disabled button
                        btns = page.query_selector_all(sel)
                        for btn in btns:
                            if not btn.is_disabled():
                                btn.click()
                                posted = True
                                break
                        if posted:
                            break
                    except Exception:
                        pass
                        
                if not posted:
                    logger.error("❌ Could not find or click the 'Post' button.")
                    return False
                    
                # Wait for confirmation (toast or popup usually appears)
                time.sleep(random.uniform(3, 5))
                logger.info("✅ Post successfully published!")
                return True

            except Exception as exc:
                logger.error(f"❌ Error during posting: {exc}")
                return False
            finally:
                self._close()
