"""
Test SELL Order Execution

Tests if SELL orders work correctly with positive stop distances.
"""

from ig_trader import IGTrader
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

print("="*80)
print("TESTING SELL ORDER WITH CORRECTED PARAMETERS")
print("="*80)

trader = IGTrader()

# Test SELL order
pair = "EUR_USD"
print(f"\nTesting {pair} SELL order...")
print("Expected: Stop ABOVE entry (for SELL), Limit BELOW entry")
print()

result = trader.open_position(
    pair=pair,
    direction="SELL",
    size=0.1,  # Min size for MINI
    stop_loss_pips=20,  # Should be 200 points ABOVE entry
    take_profit_pips=40  # Should be 400 points BELOW entry
)

print(f"\n{'='*80}")
print("RESULT:")
print(f"{'='*80}")
print(f"Success: {result.get('success')}")

if result.get('success'):
    response = result.get('response', {})
    deal_status = response.get('dealStatus')
    reason = response.get('reason')
    deal_ref = response.get('dealReference')

    if deal_status == 'ACCEPTED':
        print(f"✅ SELL ORDER ACCEPTED!")
        print(f"   Deal Reference: {deal_ref}")
        print(f"   Reason: {reason}")
        print(f"\n   Check IG activity history - stop/limit levels should be correct now")
    else:
        print(f"❌ SELL ORDER REJECTED")
        print(f"   Status: {deal_status}")
        print(f"   Reason: {reason}")
        print(f"   Deal Reference: {deal_ref}")
else:
    print(f"❌ TRADE FAILED")
    print(f"   Error: {result.get('error')}")

print(f"{'='*80}")
