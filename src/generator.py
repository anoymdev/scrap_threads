import json
import logging
import time
from pathlib import Path
from typing import List

from playwright.sync_api import sync_playwright

from .config import config

logger = logging.getLogger("generator")

class ContentGenerator:
    """
    Uses Playwright to automate Gemini web interface to generate new Threads posts.
    Requires the user to log in manually on the first run.
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self.user_data_dir = config.BASE_DIR / ".gemini_session"
        self.user_data_dir.mkdir(exist_ok=True)

    def generate_posts(
        self,
        report_path: Path,
        raw_data_path: Path,
        num_posts: int = 3,
        topic: str = None
    ) -> List[str]:
        """
        Reads analytics report and raw data, then asks Gemini Web UI to generate posts.
        """
        logger.info(f"Reading context from {report_path.name} and {raw_data_path.name}...")
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            with open(raw_data_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read data files: {e}")
            raise

        trending_topics = [t["topic"] for t in report.get("trending_topics", [])[:10]]
        
        sample_posts = []
        for post in raw_data.get("posts", [])[:15]:
            if len(post["text"]) > 20:
                sample_posts.append(post["text"])

        prompt_path = config.BASE_DIR / "prompts" / "content_generation.txt"
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
        except FileNotFoundError:
            logger.error(f"❌ Prompt template not found at {prompt_path}")
            raise

        topic_instruction = f"6. Focus the discussion specifically on this topic: {topic}" if topic else "6. Draw inspiration from the trending topics above for your content."
        
        prompt = prompt_template.format(
            trending_topics=', '.join(trending_topics),
            sample_posts=chr(10).join(f"- {text}" for text in sample_posts[:5]),
            num_posts=num_posts,
            topic_instruction=topic_instruction
        )

        logger.info("Launching browser for Gemini automation...")
        
        with sync_playwright() as p:
            # Use launch_persistent_context to keep the login session active
            launch_opts = {
                "user_data_dir": str(self.user_data_dir),
                "headless": self.headless,
                "args": ["--disable-blink-features=AutomationControlled"]
            }
            if config.BROWSER_CHANNEL:
                launch_opts["channel"] = config.BROWSER_CHANNEL
                
            browser_type = getattr(p, config.BROWSER_TYPE)
            browser = browser_type.launch_persistent_context(**launch_opts)
            
            # Close extra default pages
            if len(browser.pages) > 1:
                browser.pages[0].close()
                
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            logger.info("Opening Gemini (https://gemini.google.com/app)...")
            page.goto("https://gemini.google.com/app", wait_until="domcontentloaded")
            
            # Check for sign in
            try:
                sign_in_btn = page.wait_for_selector("a[href*='ServiceLogin']", timeout=5000)
                if sign_in_btn:
                    logger.warning("⚠️ You are not logged into Gemini!")
                    logger.warning("Please log in manually in the browser window that just opened.")
                    logger.warning("Waiting up to 120 seconds for you to log in...")
                    # Wait for the chat input to appear which means login was successful
                    page.wait_for_selector("rich-textarea", timeout=120000)
                    logger.info("✅ Login detected! Proceeding...")
                    time.sleep(3) # Let the page settle after login
            except Exception:
                # If no sign in button found, we assume we are already logged in
                pass
                
            try:
                logger.info("⌨️  Typing prompt into Gemini...")
                
                # Gemini's input is a custom element <rich-textarea>
                input_box = page.wait_for_selector("rich-textarea", timeout=15000)
                if not input_box:
                    logger.error("❌ Could not find the Gemini input box.")
                    browser.close()
                    return []
                    
                input_box.click()
                time.sleep(0.5)
                # insert_text is safer for long prompts than typing character by character
                page.keyboard.insert_text(prompt)
                time.sleep(1)
                page.keyboard.press("Enter")
                
                logger.info("⏳ Waiting for Gemini to generate the response...")
                
                # A robust way is to wait for the response container to appear and settle
                time.sleep(5)
                try:
                    # Wait until network is mostly idle or wait a fixed generous amount of time
                    # Gemini responses stream in, so we wait 15 seconds to ensure it finishes
                    time.sleep(15) 
                except Exception:
                    pass
                
                # Extract the last response
                logger.info("📥 Extracting response...")
                responses = page.query_selector_all("message-content")
                if not responses:
                    logger.error("❌ Could not find Gemini's response.")
                    browser.close()
                    return []
                    
                last_response_text = responses[-1].inner_text()
                
                raw_posts = last_response_text.split("---")
                cleaned_posts = [p.strip() for p in raw_posts if len(p.strip()) > 10]
                
                logger.info(f"✨ Successfully generated {len(cleaned_posts)} posts.")
                browser.close()
                return cleaned_posts[:num_posts]
                
            except Exception as e:
                logger.error(f"❌ Error automating Gemini: {e}")
                browser.close()
                return []
