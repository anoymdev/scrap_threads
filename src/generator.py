import json
import logging
from pathlib import Path
from typing import List, Dict, Any

from google import genai

from .config import config

logger = logging.getLogger("generator")

class ContentGenerator:
    """
    Uses Google Gemini API to generate new Threads posts based on
    scraped trending topics and language style.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key or config.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set. Please add it to your .env file.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.model_id = "gemini-2.5-flash"

    def generate_posts(
        self,
        report_path: Path,
        raw_data_path: Path,
        num_posts: int = 3,
        topic: str = None
    ) -> List[str]:
        """
        Reads analytics report and raw data, then asks Gemini to generate posts.
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
        
        # Get some sample posts to mimic style (only text)
        sample_posts = []
        for post in raw_data.get("posts", [])[:15]:
            if len(post["text"]) > 20:
                sample_posts.append(post["text"])

        prompt = f"""
Kamu adalah seorang content creator di platform Threads (seperti Twitter).
Tugasmu adalah membuat draft postingan baru berbahasa Indonesia yang organik, natural, dan menarik.

Berikut adalah topik-topik yang SEDANG TRENDING di timeline saat ini:
{', '.join(trending_topics)}

Berikut adalah contoh GAYA BAHASA dari postingan yang sedang ramai:
---
{chr(10).join(f"- {text}" for text in sample_posts[:5])}
---

Instruksi:
1. Buat {num_posts} draft postingan terpisah.
2. Gunakan gaya bahasa kasual, asik, ala anak Threads/Twitter Indonesia (bisa pakai kata ganti aku/kamu, atau lo/gue tergantung contoh gaya bahasanya).
3. Postingan TIDAK BOLEH kaku seperti robot AI. Harus senatural mungkin.
4. Jangan terlalu banyak pakai emoji (cukup 1 atau 2 jika perlu).
5. Jangan pakai hashtag (#) di setiap postingan kecuali sangat natural.
"""
        
        if topic:
            prompt += f"\n6. Fokuskan pembahasannya pada topik spesifik ini: {topic}"
        else:
            prompt += "\n6. Ambil inspirasi dari topik-topik trending di atas untuk bahan postingannya."
            
        prompt += """\n
Output Format:
Hanya keluarkan teks postingan saja. Pisahkan setiap postingan dengan pembatas "---".
"""

        logger.info("Sending request to Gemini API...")
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
            )
            if not response.text:
                logger.error("Empty response from Gemini API.")
                return []
                
            raw_posts = response.text.split("---")
            cleaned_posts = [p.strip() for p in raw_posts if len(p.strip()) > 10]
            
            logger.info(f"Successfully generated {len(cleaned_posts)} posts.")
            return cleaned_posts[:num_posts]
            
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            raise
