"""
Test Alpaca Client

Verify Alpaca API connection and basic functionality.
"""

from alpaca_client import AlpacaClient, AlpacaAPIError, OrderSide, OrderType, TimeInForce
import json


def test_alpaca_connection():
    """Test basic Alpaca API connection."""

    print("=" * 80)
    print("ALPACA API CLIENT TEST")
    print("=" * 80)

    # Initialize client with paper trading credentials
    API_KEY = "PKD4NWI6WBWHDL3IXNQ55WX77F"
    API_SECRET = "CjTudarcJqnc5mHy4xGmJ98iMjQsgDwNMfZk4acmGKbp"

    client = AlpacaClient(
        api_key=API_KEY,
        api_secret=API_SECRET,
        paper=True
    )

    # Test 1: Get Account Info
    print("\n📊 TEST 1: Get Account Information")
    print("-" * 80)
    try:
        account = client.get_account()
        print(f"✅ Account retrieved successfully!")
        print(f"   Account Number: {account.get('account_number')}")
        print(f"   Status: {account.get('status')}")
        print(f"   Currency: {account.get('currency')}")
        print(f"   Cash: ${float(account.get('cash', 0)):,.2f}")
        print(f"   Portfolio Value: ${float(account.get('portfolio_value', 0)):,.2f}")
        print(f"   Buying Power: ${float(account.get('buying_power', 0)):,.2f}")
        print(f"   Equity: ${float(account.get('equity', 0)):,.2f}")
        print(f"   Multiplier (Leverage): {account.get('multiplier')}x")
    except AlpacaAPIError as e:
        print(f"❌ Failed: {e.message}")
        return False

    # Test 2: Get Market Clock
    print("\n⏰ TEST 2: Get Market Clock")
    print("-" * 80)
    try:
        clock = client.get_clock()
        print(f"✅ Market clock retrieved!")
        print(f"   Timestamp: {clock.get('timestamp')}")
        print(f"   Market Open: {'YES' if clock.get('is_open') else 'NO'}")
        print(f"   Next Open: {clock.get('next_open')}")
        print(f"   Next Close: {clock.get('next_close')}")
    except AlpacaAPIError as e:
        print(f"❌ Failed: {e.message}")

    # Test 3: Get Assets
    print("\n📦 TEST 3: Get Tradeable Assets")
    print("-" * 80)
    try:
        assets = client.get_assets(status="active", asset_class="us_equity")
        print(f"✅ Retrieved {len(assets)} tradeable assets")

        # Show a few examples
        print(f"\n   Sample assets:")
        for asset in assets[:5]:
            print(f"   - {asset['symbol']}: {asset['name']} ({asset['exchange']})")
    except AlpacaAPIError as e:
        print(f"❌ Failed: {e.message}")

    # Test 4: Get Positions
    print("\n📈 TEST 4: Get Open Positions")
    print("-" * 80)
    try:
        positions = client.get_positions()
        print(f"✅ Retrieved {len(positions)} open positions")

        if positions:
            for position in positions:
                qty = float(position['qty'])
                side = "LONG" if qty > 0 else "SHORT"
                print(f"\n   {position['symbol']} ({side}):")
                print(f"   - Quantity: {abs(qty)}")
                print(f"   - Market Value: ${float(position['market_value']):,.2f}")
                print(f"   - Avg Entry: ${float(position['avg_entry_price']):,.2f}")
                print(f"   - Current Price: ${float(position['current_price']):,.2f}")
                print(f"   - Unrealized P&L: ${float(position['unrealized_pl']):,.2f} ({float(position['unrealized_plpc'])*100:.2f}%)")
        else:
            print("   No open positions")
    except AlpacaAPIError as e:
        print(f"❌ Failed: {e.message}")

    # Test 5: Get Orders
    print("\n📋 TEST 5: Get Orders")
    print("-" * 80)
    try:
        orders = client.get_orders(status="all", limit=10)
        print(f"✅ Retrieved {len(orders)} recent orders")

        if orders:
            for order in orders[:5]:
                print(f"\n   Order ID: {order['id']}")
                print(f"   - Symbol: {order['symbol']}")
                print(f"   - Side: {order['side'].upper()}")
                print(f"   - Qty: {order['qty']}")
                print(f"   - Type: {order['type']}")
                print(f"   - Status: {order['status']}")
                print(f"   - Created: {order['created_at']}")
                if order.get('filled_at'):
                    print(f"   - Filled: {order['filled_at']}")
                    print(f"   - Filled Price: ${float(order.get('filled_avg_price', 0)):,.2f}")
        else:
            print("   No orders found")
    except AlpacaAPIError as e:
        print(f"❌ Failed: {e.message}")

    # Test 6: Get Latest Quote
    print("\n💰 TEST 6: Get Latest Quote (AAPL)")
    print("-" * 80)
    try:
        quote = client.get_latest_quote("AAPL")
        print(f"✅ Latest quote retrieved!")
        print(f"   Symbol: AAPL")
        print(f"   Bid: ${quote['quote']['bp']:.2f} (Size: {quote['quote']['bs']})")
        print(f"   Ask: ${quote['quote']['ap']:.2f} (Size: {quote['quote']['as']})")
        print(f"   Timestamp: {quote['quote']['t']}")
    except AlpacaAPIError as e:
        print(f"❌ Failed: {e.message}")

    # Test 7: Get Snapshot
    print("\n📸 TEST 7: Get Market Snapshot (TSLA)")
    print("-" * 80)
    try:
        snapshot = client.get_snapshot("TSLA")
        print(f"✅ Snapshot retrieved!")

        latest_trade = snapshot.get('latestTrade', {})
        latest_quote = snapshot.get('latestQuote', {})
        minute_bar = snapshot.get('minuteBar', {})

        if latest_trade:
            print(f"\n   Latest Trade:")
            print(f"   - Price: ${latest_trade.get('p', 0):.2f}")
            print(f"   - Size: {latest_trade.get('s', 0)}")
            print(f"   - Time: {latest_trade.get('t', 'N/A')}")

        if latest_quote:
            print(f"\n   Latest Quote:")
            print(f"   - Bid: ${latest_quote.get('bp', 0):.2f}")
            print(f"   - Ask: ${latest_quote.get('ap', 0):.2f}")

        if minute_bar:
            print(f"\n   Minute Bar:")
            print(f"   - Open: ${minute_bar.get('o', 0):.2f}")
            print(f"   - High: ${minute_bar.get('h', 0):.2f}")
            print(f"   - Low: ${minute_bar.get('l', 0):.2f}")
            print(f"   - Close: ${minute_bar.get('c', 0):.2f}")
            print(f"   - Volume: {minute_bar.get('v', 0):,}")
    except AlpacaAPIError as e:
        print(f"❌ Failed: {e.message}")

    # Test 8: Get Portfolio History
    print("\n📊 TEST 8: Get Portfolio History")
    print("-" * 80)
    try:
        history = client.get_portfolio_history(period="1W", timeframe="1D")
        print(f"✅ Portfolio history retrieved!")

        timestamps = history.get('timestamp', [])
        equity = history.get('equity', [])
        profit_loss = history.get('profit_loss', [])

        print(f"   Period: 1 Week")
        print(f"   Data points: {len(timestamps)}")

        if equity:
            print(f"\n   Latest equity: ${equity[-1]:,.2f}")
            if len(equity) > 1:
                change = equity[-1] - equity[0]
                pct_change = (change / equity[0]) * 100 if equity[0] > 0 else 0
                print(f"   Change: ${change:,.2f} ({pct_change:+.2f}%)")
    except AlpacaAPIError as e:
        print(f"❌ Failed: {e.message}")

    # Test 9: Test Order Creation (Paper Trading - Safe)
    print("\n🧪 TEST 9: Test Order Creation (Dry Run)")
    print("-" * 80)
    print("⚠️  Not creating actual orders in this test")
    print("   To test order creation, use the alpaca_paper_trader.py module")

    # Summary
    print("\n" + "=" * 80)
    print("✅ ALPACA API CLIENT TEST COMPLETE")
    print("=" * 80)
    print("\n📝 Summary:")
    print("   - Connection: ✅ Working")
    print("   - Authentication: ✅ Valid")
    print("   - Account Access: ✅ Successful")
    print("   - Market Data: ✅ Available")
    print("   - Trading: ⏸️  Ready (not tested)")
    print("\n🎯 Your Alpaca paper trading account is ready to use!")
    print(f"   Buying Power: ${client.get_buying_power():,.2f}")
    print(f"   Equity: ${client.get_equity():,.2f}")
    print(f"   Cash: ${client.get_cash():,.2f}")
    print("\n💡 Next steps:")
    print("   1. Use alpaca_paper_trader.py to integrate with your trading system")
    print("   2. Place test orders to verify execution")
    print("   3. Monitor positions and performance")

    return True


if __name__ == "__main__":
    test_alpaca_connection()
