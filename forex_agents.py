"""
Forex Trading AI Agents

Multi-agent system for generating forex trading signals with entry, SL, and TP levels.
"""

from gpt5_wrapper import GPT5Wrapper
from forex_config import ForexConfig
from forex_data import ForexAnalyzer, ForexSignal
from finnhub_integration import FinnhubIntegration
from typing import Dict, List, Optional
from datetime import datetime
import json

# NEW IMPORTS - Multi-agent enhancements
from trading_memory import MemoryManager
from tavily_integration import TavilyIntegration
from agent_debates import InvestmentDebate


class PriceActionAgent:
    """Analyzes price action and chart patterns."""

    def __init__(self, llm: GPT5Wrapper):
        self.llm = llm
        # NEW: Memory will be set by system
        self.memory_manager = None

    def analyze(self, analysis: Dict) -> Dict:
        """
        Analyze price action on both 1m and 5m timeframes.

        Returns:
            Dictionary with price action assessment
        """
        pair = analysis['pair']
        current_price = analysis['current_price']
        trend_5m = analysis['trend_primary']
        trend_1m = analysis['trend_secondary']
        divergence = analysis['divergence']
        support = analysis['nearest_support']
        resistance = analysis['nearest_resistance']
        indicators = analysis['indicators']
        hedge_strategies = analysis.get('hedge_strategies', {})
        patterns = analysis.get('patterns', {})
        aggregate = analysis.get('aggregate_indicators', {})

        # Extract indicator values for f-string
        rsi = indicators['rsi_14']
        macd = indicators['macd']
        adx = indicators['adx']
        stoch_k = indicators['stoch_k']
        cci = indicators['cci']
        williams_r = indicators['williams_r']
        sar = indicators['sar']

        # Ichimoku values
        ichimoku_tenkan = indicators['ichimoku_tenkan']
        ichimoku_kijun = indicators['ichimoku_kijun']

        # NEW: Volume indicators
        obv_zscore = indicators.get('obv_zscore', 0.0)
        obv_change_rate = indicators.get('obv_change_rate', 0.0)

        # NEW: VPVR indicators
        vpvr_poc = indicators.get('vpvr_poc', current_price)
        vpvr_dist_poc = indicators.get('vpvr_dist_poc', 0.0)
        vpvr_position = indicators.get('vpvr_position', 0)  # -1 below VAL, 0 inside VA, 1 above VAH

        # NEW: Initial Balance indicators
        ib_range = indicators.get('ib_range', 0.0)
        ib_breakout_up = indicators.get('ib_breakout_up', 0)
        ib_breakout_down = indicators.get('ib_breakout_down', 0)
        ib_vwap = indicators.get('ib_vwap', current_price)

        # NEW: Fair Value Gaps
        fvg_bull = indicators.get('fvg_bull', 0)
        fvg_bear = indicators.get('fvg_bear', 0)
        fvg_nearest_bull_dist = indicators.get('fvg_nearest_bull_dist', 999.0)
        fvg_nearest_bear_dist = indicators.get('fvg_nearest_bear_dist', 999.0)

        # Format support/resistance
        support_str = f"{support:.5f}" if support else "N/A"
        resistance_str = f"{resistance:.5f}" if resistance else "N/A"

        # Hedge fund strategies summary
        mean_rev = hedge_strategies.get('mean_reversion', {})
        momentum_strat = hedge_strategies.get('momentum', {})
        trend_follow = hedge_strategies.get('trend_following', {})
        breakout_strat = hedge_strategies.get('breakout', {})

        strategies_summary = []
        if mean_rev.get('detected'):
            strategies_summary.append(f"Mean Reversion: {mean_rev['strength']}% strength")
        if momentum_strat.get('detected'):
            strategies_summary.append(f"Momentum ({momentum_strat['direction']}): {momentum_strat['strength']}%")
        if trend_follow.get('detected'):
            strategies_summary.append(f"Trend Following ({trend_follow['direction']}): {trend_follow['strength']}%")
        if breakout_strat.get('detected'):
            strategies_summary.append(f"Breakout ({breakout_strat['direction']}): {breakout_strat['strength']}%")

        strategies_text = "\n  ".join(strategies_summary) if strategies_summary else "No clear strategy signals"

        # ========== NEW: Retrieve past lessons from memory ==========
        past_lessons = ""
        if hasattr(self, 'memory_manager') and self.memory_manager:
            try:
                situation_summary = f"""
                Pair: {pair}
                Technical Setup: {trend_5m} trend, RSI {rsi:.1f}, MACD {"bullish" if macd > 0 else "bearish"}
                Price: {current_price:.5f}
                Support: {support_str}, Resistance: {resistance_str}
                """
                similar = self.memory_manager.price_action_memory.get_similar_situations(
                    situation_summary, n_matches=3
                )
                if similar:
                    lessons = [mem.get('reflection', '') for mem in similar if mem.get('reflection')]
                    if lessons:
                        past_lessons = f"\n\nLESSONS FROM SIMILAR PAST SITUATIONS:\n" + "\n".join(f"- {lesson}" for lesson in lessons[:3])
                        print(f"📚 Retrieved {len(lessons)} past lessons for price action analysis")
            except Exception as e:
                print(f"⚠️  Memory retrieval failed: {e}")

        # Finnhub aggregate indicators
        agg_text = "N/A"
        if aggregate and 'technicalAnalysis' in aggregate:
            ta = aggregate['technicalAnalysis']
            agg_text = f"Buy: {ta.get('count', {}).get('buy', 0)}, Sell: {ta.get('count', {}).get('sell', 0)}, Neutral: {ta.get('count', {}).get('neutral', 0)}"

        # Finnhub pattern recognition
        patterns_data = analysis.get('finnhub_patterns', {})
        patterns_text = "No patterns detected"
        if patterns_data.get('has_patterns'):
            pattern_list = []
            for p in patterns_data.get('patterns', [])[:3]:  # Show top 3 patterns
                pattern_list.append(f"{p['type'].upper()} ({p['direction']})")
            patterns_text = ", ".join(pattern_list) if pattern_list else "No patterns"

        prompt = f"""You are an Elite Price Action Trading Expert analyzing {pair} with 40+ institutional-grade indicators including advanced volume and market structure analysis.

CURRENT MARKET DATA:
- Price: {current_price:.5f}
- 5m Trend: {trend_5m} | 1m Trend: {trend_1m}
- Divergence: {divergence or 'None'}
- Support: {support_str} | Resistance: {resistance_str}

TECHNICAL INDICATORS:
- RSI: {rsi:.1f} | Stochastic: {stoch_k:.1f}
- MACD: {macd:.5f}
- ADX (Trend Strength): {adx:.1f}
- CCI: {cci:.1f} | Williams %R: {williams_r:.1f}
- Parabolic SAR: {sar:.5f} ({"Bullish" if current_price > sar else "Bearish"})
- Ichimoku: Tenkan {ichimoku_tenkan:.5f} vs Kijun {ichimoku_kijun:.5f}

VOLUME ANALYSIS (OBV):
- OBV Z-Score: {obv_zscore:.2f} (>1 = strong buying, <-1 = strong selling)
- OBV Change Rate: {obv_change_rate:.1f}% (volume momentum)

VOLUME PROFILE (VPVR):
- Point of Control (POC): {vpvr_poc:.5f} (highest volume price level)
- Distance to POC: {vpvr_dist_poc:.1f} pips
- Position vs Value Area: {"Above VAH" if vpvr_position == 1 else "Below VAL" if vpvr_position == -1 else "Inside Value Area"}
  (VAH=upper, VAL=lower, 70% volume zone acts as S/R)

INITIAL BALANCE (First Hour of Day):
- IB Range: {ib_range:.5f} (wider range = higher volatility day)
- IB VWAP: {ib_vwap:.5f}
- Breakout Status: {"UP Breakout - Bullish trend day" if ib_breakout_up else "DOWN Breakout - Bearish trend day" if ib_breakout_down else "Inside IB - Range day"}

FAIR VALUE GAPS (ICT Imbalances):
- Current Bar FVG: {"BULLISH Gap Detected" if fvg_bull else "BEARISH Gap Detected" if fvg_bear else "No new FVG"}
- Nearest Unfilled Bull FVG: {fvg_nearest_bull_dist:.1f} pips below (acts as support)
- Nearest Unfilled Bear FVG: {fvg_nearest_bear_dist:.1f} pips above (acts as resistance)

HEDGE FUND STRATEGIES DETECTED:
  {strategies_text}

FINNHUB AGGREGATE INDICATORS (Consensus from 30 indicators):
  {agg_text}

FINNHUB PATTERN RECOGNITION (Automated chart patterns):
  {patterns_text}

{past_lessons}

SOCIAL MEDIA SENTIMENT (Live web intelligence):
  {self._format_social_sentiment(analysis.get('social_sentiment', {}))}

RECENT NEWS & EVENTS:
  {self._format_news(analysis.get('live_news', {}))}

TASK: Analyze price action using ALL 40+ indicators, chart patterns, and market structure data to provide:
1. Is there a clear, high-probability trading setup? (YES/NO)
2. If YES, what type? (BULLISH_BREAKOUT, BEARISH_REJECTION, SUPPORT_BOUNCE, ICHIMOKU_CROSS, FVG_FILL, IB_BREAKOUT, VPVR_POC_BOUNCE, etc.)
3. Key price levels to watch
4. Confidence (0-100%) - be conservative, only high-probability setups with multiple confirmations

Consider for HIGH-CONFIDENCE setups:
- Hedge fund strategy alignment (multiple strategies = higher confidence)
- Volume confirmation (OBV Z-score aligning with price direction)
- VPVR confluence (price at POC/VAL/VAH + other indicators)
- Initial Balance breakout + volume surge = trend day setup
- Fair Value Gap fill + support/resistance = high-probability entry
- Ichimoku cloud position and Tenkan/Kijun relationship
- ADX trend strength (>25 = strong trend)
- Multiple oscillator confirmation (RSI, Stochastic, CCI)
- Finnhub aggregate indicator consensus (>60% agreement = strong)
- Chart pattern confirmation (Finnhub detected patterns aligning with setup)

Respond ONLY in JSON format:
{{
    "has_setup": true/false,
    "setup_type": "string or null",
    "direction": "BUY/SELL/NONE",
    "key_levels": ["level1", "level2"],
    "confidence": 0-100,
    "reasoning": "brief explanation referencing specific indicators and strategies"
}}"""

        response = self.llm.invoke([{"role": "user", "content": prompt}])

        try:
            # Clean potential markdown code fences
            content = response.content.strip()
            if content.startswith('```'):
                # Remove markdown code fences
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()

            result = json.loads(content)
        except Exception as e:
            # Fallback if JSON parsing fails - log for debugging
            print(f"⚠️  Price Action Agent JSON parsing failed for {pair}: {e}")
            print(f"   Raw response: {response.content[:200]}...")
            result = {
                "has_setup": False,
                "setup_type": None,
                "direction": "NONE",
                "key_levels": [],
                "confidence": 0,
                "reasoning": f"Failed to parse response: {str(e)[:100]}"
            }

        return result

    def _format_social_sentiment(self, sentiment_data):
        """Format social sentiment for prompt."""
        if not sentiment_data or not sentiment_data.get('search_performed'):
            return "No social sentiment data available"

        summary = sentiment_data.get('summary', 'N/A')
        sources = sentiment_data.get('sources', 0)
        return f"{sources} sources analyzed:\n{summary[:300]}..." if summary else "Limited sentiment data"

    def _format_news(self, news_data):
        """Format news for prompt."""
        if not news_data or not news_data.get('news_count'):
            return "No recent news available"

        headlines = news_data.get('headlines', [])
        if headlines:
            return "\n".join(f"- {h}" for h in headlines[:3])
        return "No significant headlines"


class MomentumAgent:
    """Analyzes momentum and trend strength."""

    def __init__(self, llm: GPT5Wrapper):
        self.llm = llm
        # NEW: Memory will be set by system
        self.memory_manager = None

    def analyze(self, analysis: Dict) -> Dict:
        """
        Analyze momentum across timeframes.

        Returns:
            Dictionary with momentum assessment
        """
        pair = analysis['pair']
        current_price = analysis['current_price']
        trend_5m = analysis['trend_primary']
        trend_1m = analysis['trend_secondary']
        indicators = analysis['indicators']
        hedge_strategies = analysis.get('hedge_strategies', {})

        # Calculate momentum strength
        rsi = indicators['rsi_14']
        macd = indicators['macd']
        macd_signal = indicators['macd_signal']
        macd_hist = indicators['macd_hist']
        adx = indicators['adx']
        pdi = indicators['pdi']
        mdi = indicators['mdi']
        stoch_k = indicators['stoch_k']
        stoch_d = indicators['stoch_d']
        williams_r = indicators['williams_r']
        cci = indicators['cci']

        # Moving averages for trend context
        ma_9 = indicators['ma_9']
        ma_21 = indicators['ma_21']
        ma_50 = indicators['ma_50']

        # Bollinger and Keltner for squeeze detection
        bb_upper = indicators['bb_upper']
        bb_lower = indicators['bb_lower']
        keltner_upper = indicators['keltner_upper']
        keltner_lower = indicators['keltner_lower']

        # Hedge fund momentum strategy
        momentum_strat = hedge_strategies.get('momentum', {})
        momentum_detected = momentum_strat.get('detected', False)
        momentum_strength = momentum_strat.get('strength', 0)
        momentum_direction = momentum_strat.get('direction', 'NEUTRAL')

        # Trend following strategy
        trend_strat = hedge_strategies.get('trend_following', {})
        trend_detected = trend_strat.get('detected', False)
        trend_strength = trend_strat.get('strength', 0)

        # MA alignment
        ma_alignment = "Bullish" if ma_9 > ma_21 > ma_50 else "Bearish" if ma_9 < ma_21 < ma_50 else "Mixed"

        # Bollinger/Keltner squeeze
        squeeze = "YES" if bb_upper < keltner_upper and bb_lower > keltner_lower else "NO"

        # ========== NEW: Retrieve past lessons from memory ==========
        past_lessons = ""
        if hasattr(self, 'memory_manager') and self.memory_manager:
            try:
                situation_summary = f"""
                Pair: {pair}
                Momentum: MACD {macd:.5f}, {"bullish" if macd > macd_signal else "bearish"} crossover
                RSI: {rsi:.1f}
                Trend Strength: ADX {adx:.1f}
                Direction: {momentum_direction if momentum_detected else "NEUTRAL"}
                """
                similar = self.memory_manager.momentum_memory.get_similar_situations(
                    situation_summary, n_matches=3
                )
                if similar:
                    lessons = [mem.get('reflection', '') for mem in similar if mem.get('reflection')]
                    if lessons:
                        past_lessons = f"\n\nLESSONS FROM SIMILAR PAST SITUATIONS:\n" + "\n".join(f"- {lesson}" for lesson in lessons[:3])
                        print(f"📚 Retrieved {len(lessons)} past lessons for momentum analysis")
            except Exception as e:
                print(f"⚠️  Memory retrieval failed: {e}")

        prompt = f"""You are an Elite Momentum Trading Expert analyzing {pair} with institutional-grade indicators.

PRICE & TREND:
- Current Price: {current_price:.5f}
- 5m Trend: {trend_5m} | 1m Trend: {trend_1m}
- MA Alignment: {ma_alignment} (9: {ma_9:.5f}, 21: {ma_21:.5f}, 50: {ma_50:.5f})

MOMENTUM OSCILLATORS:
- RSI: {rsi:.1f} (Overbought >70, Oversold <30)
- Stochastic: %K={stoch_k:.1f}, %D={stoch_d:.1f} (Overbought >80, Oversold <20)
- Williams %R: {williams_r:.1f} (Overbought >-20, Oversold <-80)
- CCI: {cci:.1f} (Overbought >100, Oversold <-100)

TREND STRENGTH:
- ADX: {adx:.1f} (>25 = strong trend, >30 = very strong)
- +DI: {pdi:.1f} vs -DI: {mdi:.1f} ({"Bullish" if pdi > mdi else "Bearish"})

MACD:
- MACD: {macd:.5f} | Signal: {macd_signal:.5f}
- Histogram: {macd_hist:.5f} ({"Bullish" if macd > macd_signal else "Bearish"} crossover)

HEDGE FUND STRATEGIES:
- Momentum Strategy: {"DETECTED" if momentum_detected else "NOT DETECTED"}
  {f"Direction: {momentum_direction}, Strength: {momentum_strength}%" if momentum_detected else ""}
- Trend Following: {"DETECTED" if trend_detected else "NOT DETECTED"}
  {f"Strength: {trend_strength}%" if trend_detected else ""}

VOLATILITY:
- Bollinger/Keltner Squeeze: {squeeze} {"(Breakout imminent!)" if squeeze == "YES" else ""}

{past_lessons}

TASK: Assess momentum using ALL indicators and provide:
1. Is momentum strong and confirmed by multiple indicators? (YES/NO)
2. Direction of momentum (UP/DOWN/NEUTRAL)
3. Are both timeframes aligned? (YES/NO)
4. Entry timing (NOW/WAIT/AVOID)
5. Confidence (0-100%) - be strict, require confirmation from multiple sources

Consider:
- ADX > 25 for strong trend confirmation
- Multiple oscillators aligned (RSI, Stochastic, Williams %R, CCI)
- MACD crossover direction
- Hedge fund momentum and trend following strategies
- Bollinger squeeze = potential explosive move
- +DI/-DI relationship confirms trend direction

Respond ONLY in JSON format:
{{
    "momentum_strong": true/false,
    "momentum_direction": "UP/DOWN/NEUTRAL",
    "timeframes_aligned": true/false,
    "entry_timing": "NOW/WAIT/AVOID",
    "confidence": 0-100,
    "reasoning": "brief explanation citing specific indicators"
}}"""

        response = self.llm.invoke([{"role": "user", "content": prompt}])

        try:
            # Clean potential markdown code fences
            content = response.content.strip()
            if content.startswith('```'):
                # Remove markdown code fences
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()

            result = json.loads(content)
        except Exception as e:
            # Fallback if JSON parsing fails - log for debugging
            print(f"⚠️  Momentum Agent JSON parsing failed for {pair}: {e}")
            print(f"   Raw response: {response.content[:200]}...")
            result = {
                "momentum_strong": False,
                "momentum_direction": "NEUTRAL",
                "timeframes_aligned": False,
                "entry_timing": "AVOID",
                "confidence": 0,
                "reasoning": f"Failed to parse response: {str(e)[:100]}"
            }

        return result


class RiskManager:
    """Calculates stop loss and take profit levels."""

    def calculate_sl_tp(
        self,
        entry: float,
        signal: str,
        atr: float,
        nearest_support: Optional[float],
        nearest_resistance: Optional[float],
        pair: str
    ) -> Dict:
        """
        Calculate optimal SL and TP levels with detailed calculation tracking.

        Returns:
            Dictionary with SL, TP, pips, risk/reward, and calculation steps
        """
        # Determine pip size
        pip_size = 0.01 if 'JPY' in pair else 0.0001

        # Track calculation steps for logging
        calculation_steps = []

        calculation_steps.append(f"Entry: {entry:.5f}")
        calculation_steps.append(f"ATR: {atr:.5f}")
        support_str = f"{nearest_support:.5f}" if nearest_support else "N/A"
        resistance_str = f"{nearest_resistance:.5f}" if nearest_resistance else "N/A"
        calculation_steps.append(f"Support: {support_str}")
        calculation_steps.append(f"Resistance: {resistance_str}")

        # ATR-based stops (1.5x ATR for SL, 3x ATR for TP = 2:1 RR)
        if signal == 'BUY':
            sl_atr = entry - (atr * 1.5)
            tp_atr = entry + (atr * 3.0)

            calculation_steps.append(f"ATR-based SL: {sl_atr:.5f} (entry - 1.5*ATR)")
            calculation_steps.append(f"ATR-based TP: {tp_atr:.5f} (entry + 3.0*ATR)")

            # Use support if it's closer and valid
            if nearest_support and nearest_support < entry:
                sl_support = nearest_support - (10 * pip_size)
                sl = max(sl_atr, sl_support)  # Use furthest (safer)
                if sl == sl_support:
                    calculation_steps.append(f"SL adjusted to support: {sl:.5f} (10 pips below support)")
                else:
                    calculation_steps.append(f"SL using ATR: {sl:.5f} (support too close)")
            else:
                sl = sl_atr
                calculation_steps.append(f"SL using ATR: {sl:.5f} (no valid support)")

            # Use resistance if it's closer
            if nearest_resistance and nearest_resistance > entry:
                tp_resistance = nearest_resistance - (5 * pip_size)
                tp = min(tp_atr, tp_resistance)  # Use closest (safer)
                if tp == tp_resistance:
                    calculation_steps.append(f"TP adjusted to resistance: {tp:.5f} (5 pips before resistance)")
                else:
                    calculation_steps.append(f"TP using ATR: {tp:.5f} (resistance too far)")
            else:
                tp = tp_atr
                calculation_steps.append(f"TP using ATR: {tp:.5f} (no valid resistance)")

        else:  # SELL
            sl_atr = entry + (atr * 1.5)
            tp_atr = entry - (atr * 3.0)

            calculation_steps.append(f"ATR-based SL: {sl_atr:.5f} (entry + 1.5*ATR)")
            calculation_steps.append(f"ATR-based TP: {tp_atr:.5f} (entry - 3.0*ATR)")

            # Use resistance if it's closer
            if nearest_resistance and nearest_resistance > entry:
                sl_resistance = nearest_resistance + (10 * pip_size)
                sl = min(sl_atr, sl_resistance)  # Use furthest (safer)
                if sl == sl_resistance:
                    calculation_steps.append(f"SL adjusted to resistance: {sl:.5f} (10 pips above resistance)")
                else:
                    calculation_steps.append(f"SL using ATR: {sl:.5f} (resistance too close)")
            else:
                sl = sl_atr
                calculation_steps.append(f"SL using ATR: {sl:.5f} (no valid resistance)")

            # Use support if it's closer
            if nearest_support and nearest_support < entry:
                tp_support = nearest_support + (5 * pip_size)
                tp = max(tp_atr, tp_support)  # Use closest (safer)
                if tp == tp_support:
                    calculation_steps.append(f"TP adjusted to support: {tp:.5f} (5 pips above support)")
                else:
                    calculation_steps.append(f"TP using ATR: {tp:.5f} (support too far)")
            else:
                tp = tp_atr
                calculation_steps.append(f"TP using ATR: {tp:.5f} (no valid support)")

        # Calculate pips and risk/reward
        if signal == 'BUY':
            pips_risk = (entry - sl) / pip_size
            pips_reward = (tp - entry) / pip_size
        else:
            pips_risk = (sl - entry) / pip_size
            pips_reward = (entry - tp) / pip_size

        risk_reward = pips_reward / pips_risk if pips_risk > 0 else 0

        calculation_steps.append(f"Pips Risk: {pips_risk:.1f}")
        calculation_steps.append(f"Pips Reward: {pips_reward:.1f}")
        calculation_steps.append(f"Initial R:R: {risk_reward:.2f}:1")

        # Ensure minimum R:R ratio
        rr_adjusted = False
        if risk_reward < ForexConfig.MIN_RISK_REWARD:
            calculation_steps.append(f"⚠️ R:R {risk_reward:.2f} below minimum {ForexConfig.MIN_RISK_REWARD}")

            # Adjust TP to meet minimum R:R
            tp_original = tp
            if signal == 'BUY':
                tp = entry + (pips_risk * ForexConfig.MIN_RISK_REWARD * pip_size)
            else:
                tp = entry - (pips_risk * ForexConfig.MIN_RISK_REWARD * pip_size)

            pips_reward = pips_risk * ForexConfig.MIN_RISK_REWARD
            risk_reward = ForexConfig.MIN_RISK_REWARD
            rr_adjusted = True

            calculation_steps.append(f"TP extended: {tp_original:.5f} → {tp:.5f} to achieve {ForexConfig.MIN_RISK_REWARD}:1")
            calculation_steps.append(f"Final R:R: {risk_reward:.2f}:1 (adjusted)")
        else:
            calculation_steps.append(f"Final R:R: {risk_reward:.2f}:1 (no adjustment needed)")

        return {
            'stop_loss': sl,
            'take_profit': tp,
            'pips_risk': pips_risk,
            'pips_reward': pips_reward,
            'risk_reward_ratio': risk_reward,
            'calculation_steps': calculation_steps,
            'rr_adjusted': rr_adjusted,
            'sl_method': 'support' if (signal == 'BUY' and nearest_support and nearest_support < entry) else 'resistance' if (signal == 'SELL' and nearest_resistance and nearest_resistance > entry) else 'atr',
            'tp_method': 'resistance' if (signal == 'BUY' and nearest_resistance and nearest_resistance > entry) else 'support' if (signal == 'SELL' and nearest_support and nearest_support < entry) else 'atr'
        }


class DecisionMaker:
    """Makes final trading decision based on all agent inputs."""

    def __init__(self, llm: GPT5Wrapper):
        self.llm = llm

    def decide(
        self,
        pair: str,
        price_action: Dict,
        momentum: Dict,
        analysis: Dict
    ) -> Dict:
        """
        Make final BUY/SELL/HOLD decision.

        Returns:
            Dictionary with final signal and reasoning
        """
        prompt = f"""You are a Senior Forex Trader making the FINAL DECISION on {pair}.

PRICE ACTION ANALYSIS:
{json.dumps(price_action, indent=2)}

MOMENTUM ANALYSIS:
{json.dumps(momentum, indent=2)}

CURRENT MARKET:
- Price: {analysis['current_price']:.5f}
- Trend (5m): {analysis['trend_primary']}
- Divergence: {analysis['divergence'] or 'None'}

TASK: Make the final trading decision considering:
1. Do both agents agree on direction?
2. Are confidence levels high enough (>60%)?
3. Is risk/reward favorable?
4. Is this a high-probability setup?

Provide ONLY:
1. Signal: BUY, SELL, or HOLD
2. Overall confidence: 0-100%
3. Top 3 reasons for the decision

Respond ONLY in JSON format:
{{
    "signal": "BUY/SELL/HOLD",
    "confidence": 0-100,
    "reasons": ["reason1", "reason2", "reason3"]
}}"""

        response = self.llm.invoke([{"role": "user", "content": prompt}])

        try:
            # Clean potential markdown code fences
            content = response.content.strip()
            if content.startswith('```'):
                # Remove markdown code fences
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()

            result = json.loads(content)
        except Exception as e:
            # Fallback if JSON parsing fails - log for debugging
            print(f"⚠️  Decision Maker JSON parsing failed for {pair}: {e}")
            print(f"   Raw response: {response.content[:200]}...")
            result = {
                "signal": "HOLD",
                "confidence": 0,
                "reasons": [f"Failed to parse decision: {str(e)[:100]}"]
            }

        return result


class ForexTradingSystem:
    """Complete multi-agent forex trading system."""

    def __init__(self, api_key: str, openai_api_key: str):
        # Initialize data analyzer
        self.analyzer = ForexAnalyzer(api_key)

        # Initialize Finnhub integration
        self.finnhub = FinnhubIntegration()

        # ========== NEW: Initialize Memory System ==========
        print("🧠 Initializing agent memory system...")
        try:
            self.memory_manager = MemoryManager("./chroma_db")
            print("✅ Memory system initialized")
        except Exception as e:
            print(f"⚠️  Memory system initialization failed: {e}")
            self.memory_manager = None

        # ========== NEW: Initialize Tavily Web Search ==========
        print("🌐 Initializing Tavily web search...")
        try:
            self.tavily = TavilyIntegration()
            print("✅ Tavily integration initialized")
        except Exception as e:
            print(f"⚠️  Tavily initialization failed: {e}")
            self.tavily = None

        # Initialize LLM (fast model for real-time)
        self.llm = GPT5Wrapper(
            api_key=openai_api_key,
            model=ForexConfig.LLM_MODEL,
            temperature=ForexConfig.LLM_TEMPERATURE,
            max_tokens=ForexConfig.LLM_MAX_TOKENS,
            timeout=ForexConfig.LLM_TIMEOUT,
            reasoning_effort="high"
        )

        # Initialize agents
        self.price_action_agent = PriceActionAgent(self.llm)
        self.momentum_agent = MomentumAgent(self.llm)
        self.risk_manager = RiskManager()
        self.decision_maker = DecisionMaker(self.llm)

        # NEW: Pass memory manager to agents
        if hasattr(self, 'memory_manager') and self.memory_manager:
            self.price_action_agent.memory_manager = self.memory_manager
            self.momentum_agent.memory_manager = self.memory_manager
            self.decision_maker.memory_manager = self.memory_manager

    def generate_signal_with_details(
        self,
        pair: str,
        primary_tf: str = '5',
        secondary_tf: str = '1'
    ) -> Dict:
        """
        Generate trading signal with complete agent flow details.

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            primary_tf: Primary timeframe ('5' for 5-min)
            secondary_tf: Secondary timeframe ('1' for 1-min)

        Returns:
            Dictionary with all agent outputs and final signal
        """
        # Step 1: Get technical analysis
        analysis = self.analyzer.analyze(pair, primary_tf, secondary_tf)

        # Step 1.5: Get Finnhub analysis (aggregate indicators + patterns)
        if self.finnhub.enabled:
            try:
                finnhub_data = self.finnhub.get_comprehensive_analysis(pair, timeframe="D")
                analysis['aggregate_indicators'] = finnhub_data['aggregate']
                analysis['finnhub_patterns'] = finnhub_data['patterns']
                analysis['finnhub_sr'] = finnhub_data['support_resistance']
            except Exception as e:
                print(f"⚠️  Finnhub fetch failed for {pair}: {e}")
                analysis['aggregate_indicators'] = {}
                analysis['finnhub_patterns'] = {'patterns': [], 'has_patterns': False}
                analysis['finnhub_sr'] = {'support': [], 'resistance': [], 'has_levels': False}
        else:
            analysis['aggregate_indicators'] = {}
            analysis['finnhub_patterns'] = {'patterns': [], 'has_patterns': False}
            analysis['finnhub_sr'] = {'support': [], 'resistance': [], 'has_levels': False}

        # ========== NEW: Step 1.6: Get Tavily Web Intelligence ==========
        if self.tavily and self.tavily.enabled:
            try:
                print(f"🌐 Fetching web intelligence for {pair}...")
                web_intel = self.tavily.get_comprehensive_analysis(pair)

                analysis['social_sentiment'] = web_intel.get('social_sentiment', {})
                analysis['live_news'] = web_intel.get('news_events', {})
                analysis['macro_context'] = web_intel.get('macro_context', {})

                print(f"✅ Web intelligence gathered: {web_intel.get('social_sentiment', {}).get('sources', 0)} social sources")
            except Exception as e:
                print(f"⚠️  Tavily fetch failed for {pair}: {e}")
                analysis['social_sentiment'] = {}
                analysis['live_news'] = {}
                analysis['macro_context'] = {}
        else:
            analysis['social_sentiment'] = {}
            analysis['live_news'] = {}
            analysis['macro_context'] = {}

        # Step 2: Price action analysis
        price_action = self.price_action_agent.analyze(analysis)

        # Step 3: Momentum analysis
        momentum = self.momentum_agent.analyze(analysis)

        # Step 4: Final decision
        print(f"🎯 Decision Maker analyzing...")

        # ========== NEW: Run Investment Debate ==========
        use_debate = hasattr(self, 'memory_manager') and self.memory_manager

        if use_debate:
            try:
                print(f"🎭 Starting Bull vs Bear debate...")
                debate = InvestmentDebate(
                    self.llm,
                    self.memory_manager.bull_memory if self.memory_manager else None,
                    self.memory_manager.bear_memory if self.memory_manager else None,
                    max_rounds=2
                )

                # Prepare analysis for debate
                debate_analysis = {
                    'price_action_analysis': price_action,
                    'momentum_analysis': momentum,
                    'indicators': analysis.get('indicators', {}),
                    'aggregate_indicators': analysis.get('aggregate_indicators', {}),
                    'social_sentiment': analysis.get('social_sentiment', {}),
                    'live_news': analysis.get('live_news', {})
                }

                # DEBUG: Print what's being passed to debate
                print(f"   [DEBUG] Price Action: {price_action.get('direction', 'N/A')} {price_action.get('setup_type', 'N/A')} (conf={price_action.get('confidence', 0)}%)")
                print(f"   [DEBUG]   Reasoning: {price_action.get('reasoning', 'N/A')[:100]}")
                print(f"   [DEBUG] Momentum: {momentum.get('direction', 'N/A')} {momentum.get('strength', 'N/A')}")
                print(f"   [DEBUG]   Reasoning: {momentum.get('reasoning', 'N/A')[:100]}")

                # DEBUG: Show ALL 53 indicators
                indicators = analysis.get('indicators', {})
                print(f"\n   [DEBUG] ALL INDICATORS ({len(indicators)} total):")
                print(f"   [DEBUG] ==========================================")

                # Oscillators
                print(f"   [DEBUG] OSCILLATORS:")
                print(f"   [DEBUG]   RSI-14: {indicators.get('rsi_14', 'N/A')}")
                print(f"   [DEBUG]   Stochastic K: {indicators.get('stoch_k', 'N/A')}")
                print(f"   [DEBUG]   Stochastic D: {indicators.get('stoch_d', 'N/A')}")
                print(f"   [DEBUG]   CCI: {indicators.get('cci', 'N/A')}")
                print(f"   [DEBUG]   Williams %R: {indicators.get('williams_r', 'N/A')}")
                print(f"   [DEBUG]   MFI: {indicators.get('mfi', 'N/A')}")
                print(f"   [DEBUG]   Ultimate Oscillator: {indicators.get('uo', 'N/A')}")

                # Trend Indicators
                print(f"   [DEBUG] TREND:")
                print(f"   [DEBUG]   MACD: {indicators.get('macd', 'N/A')}")
                print(f"   [DEBUG]   MACD Signal: {indicators.get('macd_signal', 'N/A')}")
                print(f"   [DEBUG]   MACD Histogram: {indicators.get('macd_hist', 'N/A')}")
                print(f"   [DEBUG]   ADX: {indicators.get('adx', 'N/A')}")
                print(f"   [DEBUG]   +DI (PDI): {indicators.get('pdi', 'N/A')}")
                print(f"   [DEBUG]   -DI (MDI): {indicators.get('mdi', 'N/A')}")
                print(f"   [DEBUG]   Aroon Up: {indicators.get('aroon_up', 'N/A')}")
                print(f"   [DEBUG]   Aroon Down: {indicators.get('aroon_down', 'N/A')}")
                print(f"   [DEBUG]   Parabolic SAR: {indicators.get('sar', 'N/A')}")

                # Moving Averages
                print(f"   [DEBUG] MOVING AVERAGES:")
                print(f"   [DEBUG]   MA-9: {indicators.get('ma_9', 'N/A')}")
                print(f"   [DEBUG]   MA-21: {indicators.get('ma_21', 'N/A')}")
                print(f"   [DEBUG]   MA-50: {indicators.get('ma_50', 'N/A')}")

                # Volatility
                print(f"   [DEBUG] VOLATILITY:")
                print(f"   [DEBUG]   Bollinger Upper: {indicators.get('bb_upper', 'N/A')}")
                print(f"   [DEBUG]   Bollinger Middle: {indicators.get('bb_middle', 'N/A')}")
                print(f"   [DEBUG]   Bollinger Lower: {indicators.get('bb_lower', 'N/A')}")
                print(f"   [DEBUG]   ATR: {indicators.get('atr', 'N/A')}")
                print(f"   [DEBUG]   Keltner Upper: {indicators.get('keltner_upper', 'N/A')}")
                print(f"   [DEBUG]   Keltner Lower: {indicators.get('keltner_lower', 'N/A')}")

                # Ichimoku
                print(f"   [DEBUG] ICHIMOKU:")
                print(f"   [DEBUG]   Tenkan: {indicators.get('ichimoku_tenkan', 'N/A')}")
                print(f"   [DEBUG]   Kijun: {indicators.get('ichimoku_kijun', 'N/A')}")
                print(f"   [DEBUG]   Senkou A: {indicators.get('ichimoku_senkou_a', 'N/A')}")
                print(f"   [DEBUG]   Senkou B: {indicators.get('ichimoku_senkou_b', 'N/A')}")

                # Volume
                print(f"   [DEBUG] VOLUME:")
                print(f"   [DEBUG]   OBV Z-Score: {indicators.get('obv_zscore', 'N/A')}")
                print(f"   [DEBUG]   OBV Change Rate: {indicators.get('obv_change_rate', 'N/A')}")

                # Market Structure (current candle values)
                print(f"   [DEBUG] MARKET STRUCTURE (Current Candle):")
                print(f"   [DEBUG]   VPVR POC: {indicators.get('vpvr_poc', 'N/A')}")
                print(f"   [DEBUG]   VPVR Distance to POC: {indicators.get('vpvr_dist_poc', 'N/A')}")
                print(f"   [DEBUG]   VPVR Position: {indicators.get('vpvr_position', 'N/A')}")
                print(f"   [DEBUG]   IB Range (current session): {indicators.get('ib_range', 'N/A')}")
                print(f"   [DEBUG]   IB Breakout Up (flag): {indicators.get('ib_breakout_up', 'N/A')}")
                print(f"   [DEBUG]   IB Breakout Down (flag): {indicators.get('ib_breakout_down', 'N/A')}")
                print(f"   [DEBUG]   FVG Bull (current candle flag): {indicators.get('fvg_bull', 'N/A')}")
                print(f"   [DEBUG]   FVG Bear (current candle flag): {indicators.get('fvg_bear', 'N/A')}")

                print(f"   [DEBUG] ==========================================")
                print(f"   [DEBUG] Aggregate consensus: {analysis.get('aggregate_indicators', {}).get('consensus', 'N/A')}\n")

                debate_result = debate.run_debate(debate_analysis)

                # Use debate decision
                decision = {
                    'signal': debate_result['decision'],
                    'confidence': debate_result['confidence'] * 100,  # Convert to 0-100 scale
                    'reasons': [debate_result['reasoning']],
                    'debate_history': debate_result.get('debate_history', ''),
                    'bull_arguments': debate_result.get('bull_arguments', []),
                    'bear_arguments': debate_result.get('bear_arguments', [])
                }

                print(f"✅ Debate complete: {decision['signal']} (Confidence: {decision['confidence']:.0f}%)")

            except Exception as e:
                print(f"⚠️  Debate failed, falling back to DecisionMaker: {e}")
                # Fall back to original DecisionMaker
                decision = self.decision_maker.decide(pair, price_action, momentum, analysis)
        else:
            # No debate system, use original DecisionMaker
            decision = self.decision_maker.decide(pair, price_action, momentum, analysis)

        # Step 5: Calculate SL/TP if tradeable
        signal = None
        if decision['signal'] != 'HOLD' and decision['confidence'] >= ForexConfig.MIN_CONFIDENCE * 100:
            entry_price = analysis['current_price']
            atr = analysis['indicators']['atr']

            # Use RiskManager to get detailed SL/TP calculation
            sl_tp_details = self.risk_manager.calculate_sl_tp(
                entry=entry_price,
                signal=decision['signal'],
                atr=atr,
                nearest_support=analysis['nearest_support'],
                nearest_resistance=analysis['nearest_resistance'],
                pair=pair
            )

            signal = ForexSignal(
                pair=pair,
                timeframe=primary_tf,
                signal=decision['signal'],
                confidence=decision['confidence'] / 100,
                entry_price=entry_price,
                stop_loss=sl_tp_details['stop_loss'],
                take_profit=sl_tp_details['take_profit'],
                risk_reward_ratio=sl_tp_details['risk_reward_ratio'],
                pips_risk=sl_tp_details['pips_risk'],
                pips_reward=sl_tp_details['pips_reward'],
                reasoning=decision['reasons'],
                indicators=analysis['indicators'],
                timestamp=datetime.now(),
                # SL/TP calculation details
                sl_method=sl_tp_details.get('sl_method', 'atr'),
                tp_method=sl_tp_details.get('tp_method', 'atr'),
                rr_adjusted=sl_tp_details.get('rr_adjusted', False),
                calculation_steps=sl_tp_details.get('calculation_steps', []),
                atr_value=atr,
                nearest_support=analysis['nearest_support'],
                nearest_resistance=analysis['nearest_resistance']
            )

        # Return complete details
        return {
            'pair': pair,
            'analysis': analysis,
            'price_action': price_action,
            'momentum': momentum,
            'decision': decision,
            'signal': signal
        }

    def generate_signal(
        self,
        pair: str,
        primary_tf: str = '5',
        secondary_tf: str = '1'
    ) -> Optional[ForexSignal]:
        """
        Generate complete trading signal for a pair.

        Args:
            pair: Currency pair (e.g., 'EUR_USD')
            primary_tf: Primary timeframe ('5' for 5-min)
            secondary_tf: Secondary timeframe ('1' for 1-min)

        Returns:
            ForexSignal object or None
        """
        details = self.generate_signal_with_details(pair, primary_tf, secondary_tf)
        return details['signal']

        # OLD CODE BELOW - keeping for reference but using new method above
        # Step 1: Get technical analysis
        analysis = self.analyzer.analyze(pair, primary_tf, secondary_tf)

        # Step 2: Price action analysis
        price_action = self.price_action_agent.analyze(analysis)

        # Step 3: Momentum analysis
        momentum = self.momentum_agent.analyze(analysis)

        # Step 4: Final decision
        decision = self.decision_maker.decide(pair, price_action, momentum, analysis)

        # Check if we have a tradeable signal
        if decision['signal'] == 'HOLD':
            return None

        if decision['confidence'] < ForexConfig.MIN_CONFIDENCE * 100:
            return None

        # Step 5: Calculate SL/TP
        entry_price = analysis['current_price']
        sl_tp = self.risk_manager.calculate_sl_tp(
            entry=entry_price,
            signal=decision['signal'],
            atr=analysis['indicators']['atr'],
            nearest_support=analysis['nearest_support'],
            nearest_resistance=analysis['nearest_resistance'],
            pair=pair
        )

        # Step 6: Create signal
        signal = ForexSignal(
            pair=pair,
            timeframe=f"{primary_tf}m",
            signal=decision['signal'],
            confidence=decision['confidence'] / 100.0,
            entry_price=entry_price,
            stop_loss=sl_tp['stop_loss'],
            take_profit=sl_tp['take_profit'],
            risk_reward_ratio=sl_tp['risk_reward_ratio'],
            pips_risk=sl_tp['pips_risk'],
            pips_reward=sl_tp['pips_reward'],
            reasoning=decision['reasons'],
            indicators=analysis['indicators'],
            timestamp=datetime.now()
        )

        return signal

    def batch_analyze(self, pairs: List[str]) -> List[ForexSignal]:
        """
        Analyze multiple pairs and return all signals.

        Args:
            pairs: List of currency pairs

        Returns:
            List of ForexSignal objects
        """
        signals = []

        for pair in pairs:
            try:
                print(f"Analyzing {pair}...")
                signal = self.generate_signal(pair)
                if signal:
                    signals.append(signal)
                    print(f"  → {signal.signal} signal generated")
                else:
                    print(f"  → No signal (HOLD)")
            except Exception as e:
                print(f"  → Error: {e}")

        return signals


# Quick test function
def test_forex_agents():
    """Test the forex trading agents."""
    print("Testing Forex Trading Agents...")
    print("="*60)

    system = ForexTradingSystem(
        api_key=ForexConfig.IG_API_KEY,
        openai_api_key=ForexConfig.OPENAI_API_KEY
    )

    # Test with EUR/USD
    print("\nGenerating signal for EUR/USD...")
    signal = system.generate_signal('EUR_USD', '5', '1')

    if signal:
        print(f"\n{signal}")
        print(f"\nConfidence: {signal.confidence*100:.1f}%")
        print(f"Entry: {signal.entry_price:.5f}")
        print(f"SL: {signal.stop_loss:.5f} ({signal.pips_risk:.1f} pips)")
        print(f"TP: {signal.take_profit:.5f} ({signal.pips_reward:.1f} pips)")
        print(f"R:R: {signal.risk_reward_ratio:.1f}:1")
        print(f"\nReasons:")
        for i, reason in enumerate(signal.reasoning, 1):
            print(f"  {i}. {reason}")
    else:
        print("No tradeable signal generated (HOLD)")

    print("\n" + "="*60)
    print("✓ Forex agents working!")


if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    test_forex_agents()
