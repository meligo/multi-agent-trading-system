"""
Test if system generates both BUY and SELL signals after fix.
"""

from forex_agents import ForexTradingSystem
from forex_config import ForexConfig
from dotenv import load_dotenv

load_dotenv()

print('=== TESTING BUY/SELL SIGNAL GENERATION ===\n')

# Initialize system
system = ForexTradingSystem(
    api_key=ForexConfig.FINNHUB_API_KEY,
    openai_api_key=ForexConfig.OPENAI_API_KEY
)

# Test with 10 different pairs
test_pairs = [
    'EUR_USD', 'GBP_USD', 'USD_JPY', 'AUD_USD', 'USD_CAD',
    'NZD_USD', 'EUR_GBP', 'EUR_JPY', 'GBP_JPY', 'AUD_JPY'
]

buy_count = 0
sell_count = 0
hold_count = 0

results = []

for pair in test_pairs:
    try:
        print(f'Analyzing {pair}...', end=' ')
        details = system.generate_signal_with_details(pair, '5', '1')

        pa = details['price_action']
        mom = details['momentum']
        dec = details['decision']

        signal = dec['signal']

        if signal == 'BUY':
            buy_count += 1
            print(f'✅ BUY (PA: {pa["direction"]}, Mom: {mom["momentum_direction"]})')
        elif signal == 'SELL':
            sell_count += 1
            print(f'⚠️  SELL (PA: {pa["direction"]}, Mom: {mom["momentum_direction"]})')
        else:
            hold_count += 1
            print(f'⏸  HOLD (PA: {pa["direction"]}, Mom: {mom["momentum_direction"]})')

        results.append({
            'pair': pair,
            'signal': signal,
            'pa_direction': pa['direction'],
            'mom_direction': mom['momentum_direction'],
            'trend_5m': details['analysis']['trend_primary']
        })

    except Exception as e:
        print(f'❌ ERROR: {e}')

print()
print('=' * 60)
print(f'RESULTS SUMMARY:')
print(f'  BUY:  {buy_count}/{len(test_pairs)} ({buy_count/len(test_pairs)*100:.0f}%)')
print(f'  SELL: {sell_count}/{len(test_pairs)} ({sell_count/len(test_pairs)*100:.0f}%)')
print(f'  HOLD: {hold_count}/{len(test_pairs)} ({hold_count/len(test_pairs)*100:.0f}%)')
print('=' * 60)
print()

# Show details
print('DETAILED BREAKDOWN:')
for r in results:
    if r['signal'] != 'HOLD':
        print(f"{r['pair']}: {r['signal']} (Trend: {r['trend_5m']}, PA: {r['pa_direction']}, Mom: {r['mom_direction']})")

print()

if buy_count > 0:
    print('✅ FIX SUCCESSFUL: System is now generating BUY signals!')
else:
    print('⚠️  WARNING: Still no BUY signals. Need to investigate agent prompts further.')
