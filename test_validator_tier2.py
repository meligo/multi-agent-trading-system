"""
Test Claude Validator with TIER 2 setup (moderate trend, 60-70% confidence)
This tests if the validator correctly accepts moderate setups with reduced position sizing.
"""

import os
from dotenv import load_dotenv
from claude_validator import ClaudeValidator

load_dotenv()

def test_tier2_setup():
    """Test validator with a TIER 2 setup - moderate trend, should get 50% position size."""
    print("Testing Claude Validator with TIER 2 Setup...")
    print("=" * 70)

    validator = ClaudeValidator()

    # TIER 2 signal: ADX ~20, confidence ~65%, 5m aligned but 1m differs
    signal = {
        'signal': 'BUY',
        'confidence': 0.65,  # TIER 2 range (60-75%)
        'reasons': [
            'Moderate bullish momentum (ADX 20, RSI 58)',
            'Price action showing bullish pattern',
            '5m timeframe bullish, 1m neutral'
        ],
        'entry_price': 1.0850,
        'stop_loss': 1.0820,
        'take_profit': 1.0895,
        'risk_reward_ratio': 1.5
    }

    # TIER 2 technical data: ADX 20 (moderate), 5m bullish but 1m ranging
    technical_data = {
        'pair': 'EUR_USD',
        'current_price': 1.0850,
        'trend_primary': 'BULLISH',      # 5m aligned
        'trend_secondary': 'RANGING',     # 1m differs - but this is acceptable per hedge fund approach
        'divergence': None,
        'indicators': {
            'rsi_14': 58.0,               # Healthy bullish zone
            'macd': 0.0008,               # Positive but moderate
            'adx': 20.0,                  # TIER 2 range (15-25)
            'atr': 0.0012
        },
        'nearest_support': 1.0810,
        'nearest_resistance': 1.0920
    }

    # Moderate sentiment
    sentiment_data = {
        'overall_sentiment': 'bullish',
        'sentiment_score': 0.3,           # Moderate bullish
        'confidence': 0.6,
        'recommendation': 'moderate_signal',
        'news': {
            'headlines': ['EUR shows mild strength', 'USD steady']
        },
        'positioning': {
            'sentiment': 'neutral',
            'contrarian_signal': None
        }
    }

    # Agent analysis with moderate confidence
    agent_analysis = {
        'price_action': {
            'has_setup': True,
            'setup_type': 'BULLISH_PATTERN',
            'direction': 'BUY',
            'confidence': 65              # TIER 2 range
        },
        'momentum': {
            'momentum_strong': False,      # Moderate, not strong
            'momentum_direction': 'UP',
            'timeframes_aligned': False,   # 1m differs - should be acceptable
            'confidence': 62
        }
    }

    # Validate
    print("\n🔍 Validating TIER 2 BUY signal for EUR/USD...")
    print("   ADX: 20 (moderate trend)")
    print("   Confidence: 65% (TIER 2 range)")
    print("   5m: BULLISH, 1m: RANGING (timeframe conflict)")
    print("   Expected: TIER_2, 50% position size")

    result = validator.validate_signal(
        signal=signal,
        technical_data=technical_data,
        sentiment_data=sentiment_data,
        agent_analysis=agent_analysis
    )

    # Display results
    print("\n" + "=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)
    print(f"✅ Approved: {result['approved']}")
    print(f"📊 Position Tier: {result.get('position_tier', 'N/A')}")
    print(f"💰 Position Size: {result.get('position_size_percent', 0)}%")
    print(f"🎯 Confidence Adjustment: {result['confidence_adjustment']:.2f}")
    print(f"📈 Adjusted Confidence: {result['adjusted_confidence']:.1%}")
    print(f"⚠️  Risk Level: {result['risk_level']}")
    print(f"🎬 Recommendation: {result['recommendation']}")

    if result['warnings']:
        print(f"\n⚠️  Warnings:")
        for warning in result['warnings']:
            print(f"  • {warning}")

    if result.get('key_concerns'):
        print(f"\n❌ Key Concerns:")
        for concern in result['key_concerns']:
            print(f"  • {concern}")

    if result.get('key_confirmations'):
        print(f"\n✅ Key Confirmations:")
        for confirmation in result['key_confirmations']:
            print(f"  • {confirmation}")

    print(f"\n📝 Reasoning:")
    print(f"{result['reasoning']}")

    print("\n" + "=" * 70)

    # Verify expected TIER 2 behavior
    expected_tier = 'TIER_2'
    expected_size = 50

    if result.get('position_tier') == expected_tier and result.get('position_size_percent') == expected_size:
        print(f"✅ SUCCESS: Validator correctly assigned {expected_tier} with {expected_size}% position!")
        print("   This confirms the hedge fund approach is working - moderate setups are now accepted.")
    else:
        print(f"⚠️  UNEXPECTED: Got tier={result.get('position_tier')}, size={result.get('position_size_percent')}%")
        print(f"   Expected: tier={expected_tier}, size={expected_size}%")
        if not result['approved']:
            print("   ❌ Signal was REJECTED - validator may still be too strict")
        else:
            print("   ℹ️  Signal was approved but with different tier/size")

    return result


if __name__ == "__main__":
    test_tier2_setup()
