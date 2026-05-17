# Threads Scraper

![Python](https://img.shields.io/badge/python-3.10+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

A robust and automated Playwright-based scraper for Threads.net, designed specifically for AI/ML research, content analysis, and trend monitoring.

This tool extracts data via GraphQL response interception with a seamless fallback to DOM parsing, ensuring high reliability even when the platform updates its structure.

## 🚀 Features

- **Profile Scraping**: Extract posts from public Threads accounts.
- **Keyword & Hashtag Scraping**: Discover posts matching specific topics or trends.
- **Home Feed Scraping**: Collect the latest trending content directly from the "For You" and "Following" timelines.
- **AI Content Generator**: Automatically draft new, culturally relevant posts based on trending topics and local language styles using the Gemini API.
- **Auto-Poster**: Automate the publishing of generated text to your Threads account via Playwright.
- **Session Persistence**: Securely save login cookies to reduce redundant authentications and bypass strict anti-bot measures.
- **Batch Processing**: Scrape multiple profiles or keywords concurrently.
- **Analytics Engine**: Generate rich reports on trending topics, word frequencies, and engagement statistics.
- **Multi-Format Export**: Save data in JSON, JSONL (ideal for LLM training), CSV, and raw TXT corpus.

## 📋 Prerequisites

- Python 3.10 or higher
- Chromium browser (installed automatically via Playwright)
- Google Gemini API Key (optional, for AI content generation)

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/scrap_threads.git
   cd scrap_threads
   ```

2. **Run the automated setup script:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

   *Alternatively, install manually:*
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Open `.env` and fill in your details (see the Configuration section below).

## ⚙️ Configuration

Edit the `.env` file to customize the scraper's behavior:

```env
# Scraping Settings
REQUEST_DELAY=3
MAX_POSTS=100
HEADLESS=true

# Authentication (Required for Feed scraping and Auto-Posting)
# WARNING: Use a dedicated/dummy account to avoid bans on your main account.
THREADS_USERNAME=your_username
THREADS_PASSWORD=your_password

# AI Integration
GEMINI_API_KEY=your_gemini_api_key

# Optional Proxy
# PROXY_URL=http://host:port
```

## 💻 Usage

Activate your virtual environment before running the commands:
```bash
source venv/bin/activate
```

### 1. Scrape Home Feed (Trending Data)
The best method for gathering random, algorithmically-curated trending text.
```bash
python main.py feed --max 100 --report
python main.py feed --tabs "for_you" --max 80
```

### 2. Scrape a User Profile
```bash
python main.py profile zuck --max 50
python main.py profile target_account --max 100 --formats "json,csv,txt"
```

### 3. Scrape Keywords or Hashtags
```bash
python main.py keyword "#technology" --max 100
python main.py keywords "#trending,#viral,#news" --max-each 50 --report
```

### 4. Generate AI Content
Create new draft posts imitating the scraped trending topics and language style.
*(Requires `GEMINI_API_KEY` in `.env`)*
```bash
python main.py generate data/exports/report_20260517.json data/raw/threads_20260517.json --num 3
```

### 5. Auto-Post to Threads
Automatically publish a post to your account.
*(Requires `THREADS_USERNAME` and `THREADS_PASSWORD` in `.env`)*
```bash
python main.py autopost "Hello world! This is my first automated thread." --no-headless
```

### 6. Analyze Data Offline
```bash
python main.py analyze data/raw/threads_20240517_123456.json --top 25
```

## 📊 Data Output Formats

All scraped data is saved in the `data/raw/` and `data/exports/` directories.

- **JSON**: Fully structured data with metadata (timestamps, like counts, mentions, etc.).
- **JSONL**: One JSON object per line. Perfect for fine-tuning Large Language Models.
- **CSV**: Standard tabular format for data science and visualization tools.
- **TXT**: Pure text corpus, ideal for NLP tasks like Tokenizer training.
- **Analytics Report**: A summarized JSON containing top words, hashtags, and calculated trending scores.

## 🛡️ Ethical & Legal Disclaimer

> **IMPORTANT**: This tool is provided for educational and research purposes only.

- Scraping social media platforms may violate their Terms of Service. Use this software responsibly and at your own risk.
- Do not scrape private data, aggressive volumes of data, or use the gathered information for unauthorized commercial purposes.
- The developers assume no liability for account bans, legal disputes, or damages arising from the use of this software.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
Feel free to check [issues page](https://github.com/yourusername/scrap_threads/issues).

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
