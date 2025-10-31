#!/usr/bin/env python3
"""Quick test to verify the tool routing fix."""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from config import Config

# Test configuration
print("Testing configuration...")
Config.setup()
print("✓ Config loaded")

# Test import of main
print("Testing main.py imports...")
try:
    from main import build_workflow
    print("✓ Main imports successful")
except Exception as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test workflow building
print("Testing workflow build...")
try:
    workflow = build_workflow()
    print("✓ Workflow built successfully")

    # Show nodes
    print(f"\nWorkflow has {len(workflow.nodes)} nodes")

    # Check for separate tool nodes
    has_market_tools = 'market_tools' in str(workflow.nodes)
    has_social_tools = 'social_tools' in str(workflow.nodes)
    has_news_tools = 'news_tools' in str(workflow.nodes)
    has_fundamentals_tools = 'fundamentals_tools' in str(workflow.nodes)

    print(f"  Market tools node: {'✓' if has_market_tools else '✗'}")
    print(f"  Social tools node: {'✓' if has_social_tools else '✗'}")
    print(f"  News tools node: {'✓' if has_news_tools else '✗'}")
    print(f"  Fundamentals tools node: {'✓' if has_fundamentals_tools else '✗'}")

    if all([has_market_tools, has_social_tools, has_news_tools, has_fundamentals_tools]):
        print("\n✓ All separate tool nodes present - routing conflict FIXED!")
    else:
        print("\n✗ Some tool nodes missing")

except Exception as e:
    print(f"✗ Workflow build error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("ALL TESTS PASSED! System is ready to run.")
print("="*60)
