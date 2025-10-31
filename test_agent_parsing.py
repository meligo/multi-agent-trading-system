"""
Test agent JSON parsing to identify root cause of failures.
"""

from forex_agents import ForexTradingSystem
from forex_config import ForexConfig
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
import json

load_dotenv()

print('=== TESTING AGENT JSON PARSING ===\n')
print('Testing with EUR_USD...\n')

# Initialize system
system = ForexTradingSystem(
    api_key=ForexConfig.FINNHUB_API_KEY,
    openai_api_key=ForexConfig.OPENAI_API_KEY
)

# Get analysis
analysis = system.analyzer.analyze('EUR_USD', '5', '1')

print(f'Current Price: {analysis["current_price"]:.5f}')
print(f'Trend 5m: {analysis["trend_primary"]}')
print(f'Trend 1m: {analysis["trend_secondary"]}')
print()

# Test Price Action Agent with minimal prompt
print('=' * 80)
print('TESTING PRICE ACTION AGENT - MINIMAL PROMPT')
print('=' * 80)

pair = analysis['pair']
current_price = analysis['current_price']
indicators = analysis['indicators']

prompt = f"""You are a trading expert analyzing {pair}.

Current Price: {current_price:.5f}
RSI: {indicators['rsi_14']:.1f}

Respond ONLY in valid JSON format (no markdown code fences, no extra text):
{{
    "has_setup": true,
    "setup_type": "test",
    "direction": "BUY",
    "key_levels": [],
    "confidence": 50,
    "reasoning": "test"
}}"""

response = system.llm.invoke([HumanMessage(content=prompt)])

print('\nRAW RESPONSE FROM OPENAI:')
print('-' * 80)
print(repr(response.content))
print('-' * 80)
print()

# Try to parse it
try:
    parsed = json.loads(response.content.strip())
    print('✅ JSON PARSED SUCCESSFULLY!')
    print(json.dumps(parsed, indent=2))
except Exception as e:
    print(f'❌ JSON PARSING FAILED: {e}')
    print()

    # Try to clean markdown code fences
    content = response.content.strip()

    if '```' in content:
        print('⚠️  Detected markdown code fence, attempting to clean...')
        # Remove markdown code fences
        content = content.replace('```json', '').replace('```', '').strip()

        try:
            parsed = json.loads(content)
            print('✅ JSON PARSED AFTER CLEANING!')
            print(json.dumps(parsed, indent=2))
            print()
            print('🔥 ROOT CAUSE: OpenAI is wrapping JSON in markdown code fences!')
        except Exception as e2:
            print(f'❌ STILL FAILED AFTER CLEANING: {e2}')
    else:
        print('No markdown detected. Content:')
        print(content[:500])

print()
print('=' * 80)
print()

# Now test with actual Price Action Agent
print('TESTING FULL PRICE ACTION AGENT')
print('=' * 80)

try:
    pa_result = system.price_action_agent.analyze(analysis)
    print('✅ Price Action Agent result:')
    print(json.dumps(pa_result, indent=2))
except Exception as e:
    print(f'❌ Price Action Agent failed: {e}')
    import traceback
    traceback.print_exc()

print()
print('=' * 80)
print('TESTING MOMENTUM AGENT')
print('=' * 80)

try:
    mom_result = system.momentum_agent.analyze(analysis)
    print('✅ Momentum Agent result:')
    print(json.dumps(mom_result, indent=2))
except Exception as e:
    print(f'❌ Momentum Agent failed: {e}')
    import traceback
    traceback.print_exc()
