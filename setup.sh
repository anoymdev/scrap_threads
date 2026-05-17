#!/bin/bash
# =========================================
# Threads Scraper - Setup Script
# =========================================

echo "🕸️  Threads Scraper Setup"
echo "========================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Please install it first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✅ Python $PYTHON_VERSION found"

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate and install
echo "📦 Installing dependencies..."
source venv/bin/activate
pip install -q playwright requests beautifulsoup4 pandas jmespath rich typer python-dotenv aiofiles

# Install Playwright browser
echo "🌐 Installing Chromium browser..."
playwright install chromium

# Create .env from example
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "⚙️  Created .env file (edit it to customize settings)"
fi

# Create data directories
mkdir -p data/raw data/exports logs

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 Usage examples:"
echo "  source venv/bin/activate"
echo "  python main.py profile zuck --max 50"
echo "  python main.py keyword '#indonesia' --max 100"
echo "  python main.py keywords '#trending,#viral,#indonesia' --max 30 --report"
echo "  python main.py analyze data/raw/threads_TIMESTAMP.json"
echo ""
echo "📚 For programmatic use:"
echo "  python examples.py batch"
