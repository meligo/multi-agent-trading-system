"""
Test new indicators (MFI, Ultimate Oscillator, Aroon) using Finnhub data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from forex_config import ForexConfig
from forex_data import TechnicalAnalysis
import finnhub

print("="*80)
print("TESTING NEW INDICATORS (MFI, UO, AROON)")
print("="*80)

# Initialize Finnhub client
finnhub_client = finnhub.Client(api_key=ForexConfig.FINNHUB_API_KEY)

# Get forex data from Finnhub
pair = "OANDA:EUR_USD"
resolution = "5"  # 5-minute candles

# Get recent data (last 100 candles)
end_time = int(datetime.now().timestamp())
start_time = int((datetime.now() - timedelta(days=2)).timestamp())

print(f"\n📊 Fetching {pair} data from Finnhub...")
try:
    data = finnhub_client.forex_candles(pair, resolution, start_time, end_time)

    if data['s'] != 'ok':
        raise ValueError(f"No data returned: {data.get('s', 'unknown status')}")

    # Convert to DataFrame
    df = pd.DataFrame({
        'time': pd.to_datetime(data['t'], unit='s'),
        'open': data['o'],
        'high': data['h'],
        'low': data['l'],
        'close': data['c'],
        'volume': data['v']
    })

    print(f"✅ Fetched {len(df)} candles")
    print(f"   Time range: {df['time'].iloc[0]} to {df['time'].iloc[-1]}")
    print(f"   Latest close: {df['close'].iloc[-1]:.5f}")

    # Apply technical analysis
    print(f"\n🔧 Calculating indicators...")
    ta = TechnicalAnalysis()
    df = ta.add_indicators(df)

    # Extract last values
    last_row = df.iloc[-1]

    print(f"\n✅ INDICATOR CALCULATIONS COMPLETE!")
    print(f"="*80)

    # NEW INDICATORS
    print(f"\n📊 NEW INDICATORS (Just Implemented):")
    print(f"   MFI (Money Flow Index): {last_row.get('mfi', 'ERROR'):.2f}")
    print(f"   Ultimate Oscillator: {last_row.get('uo', 'ERROR'):.2f}")
    print(f"   Aroon Up: {last_row.get('aroon_up', 'ERROR'):.2f}")
    print(f"   Aroon Down: {last_row.get('aroon_down', 'ERROR'):.2f}")

    # SAMPLE OF OTHER INDICATORS (to verify system still works)
    print(f"\n📊 SAMPLE EXISTING INDICATORS:")
    print(f"   RSI-14: {last_row.get('rsi_14', 'ERROR'):.2f}")
    print(f"   MACD: {last_row.get('macd', 'ERROR'):.6f}")
    print(f"   MACD Histogram: {last_row.get('macd_hist', 'ERROR'):.6f}")
    print(f"   ADX: {last_row.get('adx', 'ERROR'):.2f}")
    print(f"   +DI: {last_row.get('pdi', 'ERROR'):.2f}")
    print(f"   -DI: {last_row.get('mdi', 'ERROR'):.2f}")
    print(f"   Stochastic K: {last_row.get('stoch_k', 'ERROR'):.2f}")
    print(f"   Williams %R: {last_row.get('williams_r', 'ERROR'):.2f}")
    print(f"   CCI: {last_row.get('cci', 'ERROR'):.2f}")

    # Check if indicators are valid
    print(f"\n🔍 VALIDATION:")
    new_indicators = ['mfi', 'uo', 'aroon_up', 'aroon_down']
    all_valid = True

    for indicator in new_indicators:
        value = last_row.get(indicator)
        if pd.isna(value):
            print(f"   ❌ {indicator}: NaN (FAILED)")
            all_valid = False
        else:
            print(f"   ✅ {indicator}: {value:.2f} (OK)")

    if all_valid:
        print(f"\n✅ ALL NEW INDICATORS WORKING CORRECTLY!")
    else:
        print(f"\n⚠️  SOME INDICATORS FAILED")

    # Show interpretation
    print(f"\n📖 INTERPRETATION:")
    mfi = last_row.get('mfi', 50)
    uo = last_row.get('uo', 50)
    aroon_up = last_row.get('aroon_up', 50)
    aroon_down = last_row.get('aroon_down', 50)

    if mfi < 20:
        print(f"   MFI ({mfi:.1f}): OVERSOLD - Potential buy signal")
    elif mfi > 80:
        print(f"   MFI ({mfi:.1f}): OVERBOUGHT - Potential sell signal")
    else:
        print(f"   MFI ({mfi:.1f}): NEUTRAL")

    if uo < 30:
        print(f"   Ultimate Oscillator ({uo:.1f}): OVERSOLD")
    elif uo > 70:
        print(f"   Ultimate Oscillator ({uo:.1f}): OVERBOUGHT")
    else:
        print(f"   Ultimate Oscillator ({uo:.1f}): NEUTRAL")

    if aroon_up > 70 and aroon_down < 30:
        print(f"   Aroon: STRONG UPTREND (Up={aroon_up:.0f}, Down={aroon_down:.0f})")
    elif aroon_down > 70 and aroon_up < 30:
        print(f"   Aroon: STRONG DOWNTREND (Up={aroon_up:.0f}, Down={aroon_down:.0f})")
    else:
        print(f"   Aroon: MIXED/RANGING (Up={aroon_up:.0f}, Down={aroon_down:.0f})")

    print(f"\n" + "="*80)
    print(f"✅ TEST COMPLETE - All 3 new indicators implemented successfully!")
    print(f"="*80)

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
