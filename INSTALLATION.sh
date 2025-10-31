#!/bin/bash
# Quick Installation Script for Multi-Agent Trading System

echo "=================================="
echo "Multi-Agent Trading System Setup"
echo "=================================="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version || python --version

echo ""
echo "Step 1: Installing dependencies..."
pip install -r requirements.txt

echo ""
echo "Step 2: Checking for .env file..."
if [ ! -f .env ]; then
    echo "⚠️  No .env file found!"
    echo "Creating .env from template..."
    cat > .env << 'ENVEOF'
# Multi-Agent Trading System - API Keys
OPENAI_API_KEY=your_openai_key_here
FINNHUB_API_KEY=your_finnhub_key_here
TAVILY_API_KEY=your_tavily_key_here
LANGSMITH_API_KEY=your_langsmith_key_here
ENVEOF
    echo "✓ Created .env file"
    echo ""
    echo "⚠️  IMPORTANT: Edit .env and add your API keys!"
    echo ""
else
    echo "✓ .env file exists"
fi

echo ""
echo "Step 3: Creating data directories..."
mkdir -p data_cache memory_db results
echo "✓ Directories created"

echo ""
echo "=================================="
echo "✓ Installation Complete!"
echo "=================================="
echo ""
echo "Next steps:"
echo "1. Edit .env and add your API keys"
echo "2. Run: python main.py NVDA"
echo ""
echo "Get API keys:"
echo "  - OpenAI: https://platform.openai.com/api-keys"
echo "  - Finnhub: https://finnhub.io/register"
echo "  - Tavily: https://tavily.com/"
echo "  - LangSmith: https://smith.langchain.com/"
echo ""
