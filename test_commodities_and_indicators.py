"""
Test Commodity EPICs and All 53 TA Indicators

Verifies that:
1. All commodity EPICs are accessible on IG account
2. Price data can be fetched for each commodity
3. All 53 technical indicators work correctly with commodity data
"""

from ig_trader import IGTrader
from forex_config import ForexConfig
from ig_data_fetcher import IGDataFetcher
import traceback

def test_epic_availability():
    """Test if commodity EPICs are available on IG account."""
    print("="*80)
    print("TESTING COMMODITY EPIC AVAILABILITY")
    print("="*80)

    trader = IGTrader()
    results = {}

    for symbol in ForexConfig.COMMODITY_PAIRS:
        epic = ForexConfig.IG_EPIC_MAP.get(symbol)
        if not epic:
            print(f"\n❌ {symbol}: No EPIC mapping found")
            results[symbol] = {"available": False, "error": "No EPIC mapping"}
            continue

        print(f"\n🔍 Testing {symbol} ({epic})...")

        try:
            # Fetch market info
            market_info = trader.ig_service.fetch_market_by_epic(epic)

            snapshot = market_info.get('snapshot', {})
            instrument = market_info.get('instrument', {})

            market_name = instrument.get('name', 'N/A')
            market_status = snapshot.get('marketStatus', 'N/A')
            bid = snapshot.get('bid', 'N/A')
            offer = snapshot.get('offer', 'N/A')

            print(f"   Name: {market_name}")
            print(f"   Status: {market_status}")
            print(f"   Bid: {bid}")
            print(f"   Offer: {offer}")

            if market_status == 'TRADEABLE':
                print(f"   ✅ AVAILABLE AND TRADEABLE")
                results[symbol] = {
                    "available": True,
                    "epic": epic,
                    "name": market_name,
                    "status": market_status,
                    "bid": bid,
                    "offer": offer
                }
            else:
                print(f"   ⚠️  AVAILABLE BUT NOT TRADEABLE (status: {market_status})")
                results[symbol] = {
                    "available": True,
                    "epic": epic,
                    "name": market_name,
                    "status": market_status,
                    "warning": "Not currently tradeable"
                }

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results[symbol] = {"available": False, "error": str(e)}

    return results


def test_price_data_fetching(epic_results):
    """Test fetching price data for each commodity."""
    print("\n" + "="*80)
    print("TESTING PRICE DATA FETCHING")
    print("="*80)

    fetcher = IGDataFetcher(api_key=ForexConfig.IG_API_KEY)
    results = {}

    for symbol, epic_info in epic_results.items():
        if not epic_info.get('available'):
            print(f"\n⏭️  Skipping {symbol} (not available)")
            results[symbol] = {"data_fetch": False, "reason": "Epic not available"}
            continue

        print(f"\n📊 Fetching data for {symbol}...")

        try:
            # Fetch 5-minute data
            df = fetcher.fetch_prices(symbol, '5', 50)

            if df is not None and len(df) > 0:
                print(f"   ✅ DATA FETCHED: {len(df)} candles")
                print(f"      Latest Close: {df['close'].iloc[-1]:.4f}")
                print(f"      Latest Volume: {df['volume'].iloc[-1]}")
                print(f"      Date Range: {df.index[0]} to {df.index[-1]}")

                results[symbol] = {
                    "data_fetch": True,
                    "candles": len(df),
                    "latest_close": float(df['close'].iloc[-1]),
                    "latest_volume": int(df['volume'].iloc[-1])
                }
            else:
                print(f"   ❌ NO DATA RETURNED")
                results[symbol] = {"data_fetch": False, "reason": "No data returned"}

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            traceback.print_exc()
            results[symbol] = {"data_fetch": False, "error": str(e)}

    return results


def test_technical_indicators(symbol, data_results):
    """Test all 53 TA indicators on commodity data."""
    print(f"\n" + "="*80)
    print(f"TESTING ALL 53 TA INDICATORS ON {symbol}")
    print("="*80)

    if not data_results.get('data_fetch'):
        print(f"⏭️  Skipping {symbol} (no price data)")
        return {"indicators_tested": 0, "indicators_working": 0, "reason": "No price data"}

    fetcher = IGDataFetcher(api_key=ForexConfig.IG_API_KEY)

    try:
        # Fetch data
        df = fetcher.fetch_prices(symbol, '5', 100)

        if df is None or len(df) < 50:
            print(f"❌ Insufficient data for {symbol}")
            return {"indicators_tested": 0, "indicators_working": 0, "reason": "Insufficient data"}

        # Calculate all indicators
        print(f"\n📊 Calculating indicators on {len(df)} candles...")

        indicators = fetcher.calculate_all_indicators(df)

        # Count working indicators
        indicators_working = []
        indicators_failed = []

        # Check each indicator category
        indicator_checks = {
            # Trend indicators
            'sma_9': indicators.get('sma_9'),
            'sma_21': indicators.get('sma_21'),
            'sma_50': indicators.get('sma_50'),
            'sma_200': indicators.get('sma_200'),
            'ema_9': indicators.get('ema_9'),
            'ema_21': indicators.get('ema_21'),
            'ema_50': indicators.get('ema_50'),
            'ema_200': indicators.get('ema_200'),

            # Momentum indicators
            'rsi': indicators.get('rsi'),
            'macd': indicators.get('macd'),
            'macd_signal': indicators.get('macd_signal'),
            'macd_histogram': indicators.get('macd_histogram'),
            'stochastic_k': indicators.get('stochastic_k'),
            'stochastic_d': indicators.get('stochastic_d'),
            'cci': indicators.get('cci'),
            'williams_r': indicators.get('williams_r'),
            'roc': indicators.get('roc'),
            'mfi': indicators.get('mfi'),

            # Volatility indicators
            'atr': indicators.get('atr'),
            'bb_upper': indicators.get('bb_upper'),
            'bb_middle': indicators.get('bb_middle'),
            'bb_lower': indicators.get('bb_lower'),
            'bb_width': indicators.get('bb_width'),
            'keltner_upper': indicators.get('keltner_upper'),
            'keltner_middle': indicators.get('keltner_middle'),
            'keltner_lower': indicators.get('keltner_lower'),

            # Volume indicators
            'obv': indicators.get('obv'),
            'ad_line': indicators.get('ad_line'),
            'cmf': indicators.get('cmf'),
            'vwap': indicators.get('vwap'),

            # Trend strength
            'adx': indicators.get('adx'),
            'plus_di': indicators.get('plus_di'),
            'minus_di': indicators.get('minus_di'),

            # Ichimoku Cloud
            'ichimoku_tenkan': indicators.get('ichimoku_tenkan'),
            'ichimoku_kijun': indicators.get('ichimoku_kijun'),
            'ichimoku_senkou_a': indicators.get('ichimoku_senkou_a'),
            'ichimoku_senkou_b': indicators.get('ichimoku_senkou_b'),
            'ichimoku_chikou': indicators.get('ichimoku_chikou'),

            # Parabolic SAR
            'psar': indicators.get('psar'),

            # Donchian Channels
            'donchian_upper': indicators.get('donchian_upper'),
            'donchian_middle': indicators.get('donchian_middle'),
            'donchian_lower': indicators.get('donchian_lower'),

            # Aroon
            'aroon_up': indicators.get('aroon_up'),
            'aroon_down': indicators.get('aroon_down'),
            'aroon_oscillator': indicators.get('aroon_oscillator'),

            # Additional
            'trix': indicators.get('trix'),
            'dpo': indicators.get('dpo'),
            'kama': indicators.get('kama'),
            'supertrend': indicators.get('supertrend'),
            'pivots_r1': indicators.get('pivots_r1'),
            'pivots_r2': indicators.get('pivots_r2'),
            'pivots_s1': indicators.get('pivots_s1'),
            'pivots_s2': indicators.get('pivots_s2'),
        }

        for name, value in indicator_checks.items():
            if value is not None and value == value:  # Check for not None and not NaN
                indicators_working.append(name)
            else:
                indicators_failed.append(name)

        print(f"\n✅ WORKING INDICATORS: {len(indicators_working)}/{len(indicator_checks)}")
        if indicators_failed:
            print(f"❌ FAILED INDICATORS ({len(indicators_failed)}):")
            for name in indicators_failed:
                print(f"   - {name}")

        return {
            "indicators_tested": len(indicator_checks),
            "indicators_working": len(indicators_working),
            "indicators_failed": len(indicators_failed),
            "working_list": indicators_working,
            "failed_list": indicators_failed
        }

    except Exception as e:
        print(f"❌ ERROR testing indicators: {e}")
        traceback.print_exc()
        return {"indicators_tested": 0, "indicators_working": 0, "error": str(e)}


def main():
    """Run all tests."""

    print("="*80)
    print("COMMODITY TRADING & TA INDICATORS TEST SUITE")
    print("="*80)
    print(f"Testing {len(ForexConfig.COMMODITY_PAIRS)} commodities")
    print(f"Verifying 53 technical indicators")
    print("="*80)

    # Test 1: EPIC availability
    epic_results = test_epic_availability()

    # Test 2: Price data fetching
    data_results = test_price_data_fetching(epic_results)

    # Test 3: TA indicators (test on first available commodity)
    indicator_results = {}
    tested_commodity = None

    for symbol in ForexConfig.COMMODITY_PAIRS:
        if data_results.get(symbol, {}).get('data_fetch'):
            tested_commodity = symbol
            indicator_results[symbol] = test_technical_indicators(symbol, data_results[symbol])
            break  # Test on first working commodity

    # Final Summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80)

    available_count = sum(1 for r in epic_results.values() if r.get('available'))
    tradeable_count = sum(1 for r in epic_results.values() if r.get('status') == 'TRADEABLE')
    data_fetch_count = sum(1 for r in data_results.values() if r.get('data_fetch'))

    print(f"\nCommodity EPICs:")
    print(f"  Total: {len(ForexConfig.COMMODITY_PAIRS)}")
    print(f"  Available: {available_count}")
    print(f"  Tradeable: {tradeable_count}")
    print(f"  Data Fetchable: {data_fetch_count}")

    print(f"\nAvailable Commodities:")
    for symbol, result in epic_results.items():
        status = "✅" if result.get('available') and result.get('status') == 'TRADEABLE' else "⚠️"
        print(f"  {status} {symbol}: {result.get('name', 'N/A')} - {result.get('status', 'N/A')}")

    if tested_commodity and tested_commodity in indicator_results:
        ind_result = indicator_results[tested_commodity]
        print(f"\nTechnical Indicators (tested on {tested_commodity}):")
        print(f"  Total Indicators: {ind_result.get('indicators_tested', 0)}")
        print(f"  Working: {ind_result.get('indicators_working', 0)}")
        print(f"  Failed: {ind_result.get('indicators_failed', 0)}")

        if ind_result.get('indicators_working', 0) >= 50:
            print(f"  ✅ ALL MAJOR INDICATORS WORKING!")
        elif ind_result.get('indicators_working', 0) >= 40:
            print(f"  ⚠️  Most indicators working, some issues")
        else:
            print(f"  ❌ MANY INDICATORS FAILING")

    print("\n" + "="*80)
    print("TEST COMPLETE!")
    print("="*80)

    return {
        "epic_results": epic_results,
        "data_results": data_results,
        "indicator_results": indicator_results
    }


if __name__ == "__main__":
    main()
