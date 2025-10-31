#!/usr/bin/env python3
"""Quick script to check if .env file has valid API keys."""

import os
from pathlib import Path

# Load .env file
env_file = Path('.env')
if not env_file.exists():
    print("❌ No .env file found!")
    print("\nCreate one with:")
    print("  cp .env .env")
    print("  Then edit .env and add your API keys")
    exit(1)

# Read .env
with open('.env') as f:
    lines = f.readlines()

# Check keys
keys_to_check = {
    'OPENAI_API_KEY': 'sk-',
    'FINNHUB_API_KEY': '',
    'TAVILY_API_KEY': 'tvly-',
    'LANGSMITH_API_KEY': 'lsv2_pt_'
}

print("\n" + "="*60)
print("API KEYS CHECK")
print("="*60)

all_good = True
for line in lines:
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    
    if '=' in line:
        key, value = line.split('=', 1)
        key = key.strip()
        value = value.strip()
        
        if key in keys_to_check:
            expected_prefix = keys_to_check[key]
            
            # Check if it's a placeholder
            if 'your' in value.lower() or 'here' in value.lower():
                print(f"❌ {key}: Placeholder detected - replace with real key")
                all_good = False
            # Check if it's empty
            elif not value:
                print(f"❌ {key}: Empty - add your key")
                all_good = False
            # Check prefix if expected
            elif expected_prefix and not value.startswith(expected_prefix):
                print(f"⚠️  {key}: Looks suspicious (expected to start with '{expected_prefix}')")
                all_good = False
            # Looks good!
            else:
                masked = value[:10] + '...' + value[-4:] if len(value) > 14 else value[:5] + '...'
                print(f"✓ {key}: {masked}")

print("="*60)

if all_good:
    print("\n✅ All API keys look good! Ready to run:")
    print("   python main.py NVDA")
else:
    print("\n❌ Please fix the issues above, then try again.")
    print("\nGet your API keys:")
    print("  • OpenAI: https://platform.openai.com/api-keys")
    print("  • Finnhub: https://finnhub.io/register")
    print("  • Tavily: https://tavily.com/")
    print("  • LangSmith: https://smith.langchain.com/")

print()
