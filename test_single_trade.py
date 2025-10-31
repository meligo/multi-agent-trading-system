"""
Test Single Trade Execution

Tests if we can execute a single trade successfully with the fixed parameters.
"""

from ig_trader import IGTrader
from forex_config import ForexConfig
import logging

logging.basicConfig(level=logging.INFO)

print("="*80)
print("TESTING SINGLE TRADE EXECUTION")
print("="*80)

# Create trader
trader = IGTrader()

# Get account info
account = trader.get_account_info()
print(f"\nAccount: {account.get('account_id')}")
print(f"Balance: €{account.get('balance', 0):,.2f}")
print(f"Available: €{account.get('available', 0):,.2f}")

# Test pair
pair = "EUR_USD"
print(f"\n{'='*80}")
print(f"Testing {pair} trade...")
print(f"{'='*80}")

# Get current price
from ig_rate_limiter import get_rate_limiter
rate_limiter = get_rate_limiter()

epic = trader._get_epic(pair)
rate_limiter.wait_if_needed(is_account_request=True)
market_info = trader.ig_service.fetch_market_by_epic(epic)

snapshot = market_info.get('snapshot', {})
dealing_rules = market_info.get('dealingRules', {})

print(f"\nMarket Status: {snapshot.get('marketStatus')}")
print(f"Bid: {snapshot.get('bid')}")
print(f"Offer: {snapshot.get('offer')}")
print(f"Market Order Preference: {dealing_rules.get('marketOrderPreference')}")
print(f"Min Deal Size: {dealing_rules.get('minDealSize')}")

# Try to open a SMALL test position
print(f"\n{'='*80}")
print("Attempting to open 0.01 lot BUY position...")
print(f"{'='*80}")

result = trader.open_position(
    pair=pair,
    direction="BUY",
    size=0.01,  # Smallest size
    stop_loss_pips=20,
    take_profit_pips=40
)

print(f"\nResult:")
print(f"Success: {result.get('success')}")

if result.get('success'):
    print(f"✅ TRADE EXECUTED!")
    print(f"Deal Reference: {result.get('deal_reference')}")
    print(f"Response: {result.get('response')}")
else:
    print(f"❌ TRADE FAILED")
    print(f"Error: {result.get('error')}")

print(f"\n{'='*80}")
print("Check your IG activity history to verify if trade was accepted or rejected")
print(f"{'='*80}")
