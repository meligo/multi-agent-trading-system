"""
Scalping Trading Agents

Multi-agent system optimized for 10-20 minute fast momentum scalping.
Maintains the 2-agent + judge debate structure from the main system.

Architecture:
1. Fast Momentum Agent + Technical Agent → Scalp Validator (Judge)
2. Aggressive Risk Agent + Conservative Risk Agent → Risk Manager (Judge)
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from logging_config import setup_file_logging
from scalping_config import ScalpingConfig
from scalping_indicators import ScalpingIndicators
from dynamic_sltp import DynamicSLTPCalculator
from pattern_detectors import get_best_pattern, detect_all_patterns, PatternDetection
from pre_trade_gates import check_all_gates, GateResult
import pandas as pd

# Setup logging
logger = setup_file_logging("scalping_agents", console_output=False)


@dataclass
class ScalpSetup:
    """Represents a potential scalping trade setup."""
    pair: str
    direction: str  # "BUY" or "SELL"
    entry_price: float
    take_profit: float
    stop_loss: float
    confidence: float  # 0.0 to 1.0
    reasoning: List[str]
    indicators: Dict[str, any]
    spread: float
    timestamp: datetime
    approved: bool = False
    risk_tier: int = 1  # 1=highest quality, 2=medium, 3=skip


class FastMomentumAgent:
    """
    Analyzes momentum on 1-minute timeframe for scalping opportunities.
    OPTIMIZED: Uses fast EMA ribbon (3,6,12), VWAP, Donchian, RSI(7), ADX(7).
    Based on GPT-5 analysis + academic research.

    Now enhanced with professional pattern detection (ORB, SFP, IMPULSE).
    """

    def __init__(self, llm: ChatOpenAI, use_pattern_detection: bool = True):
        self.llm = llm
        self.name = "Fast Momentum Agent"
        self.use_pattern_detection = use_pattern_detection

    def analyze(self, market_data: Dict) -> Dict:
        """
        Enhanced momentum analysis with pattern detection as ADDITIONAL CONTEXT.

        Pattern detection provides rich data for the LLM to consider:
        - Pre-trade gate results (spread, ATR, session, news, HTF)
        - Detected patterns (ORB, SFP, IMPULSE) with scores
        - Pattern quality breakdown (pattern, structure, volatility)

        The LLM makes the final decision with this enhanced context.

        Args:
            market_data: Dict with price, indicators, data (DataFrame), spread, etc.

        Returns:
            Dict with momentum assessment including pattern detection context
        """
        pair = market_data['pair']
        current_price = market_data['current_price']
        data = market_data.get('data')  # DataFrame with OHLCV
        spread = market_data.get('spread', 0)
        indicators = market_data.get('indicators', {})

        # If pattern detection disabled, use original analysis
        if not self.use_pattern_detection:
            return self._analyze_llm_only(market_data)

        # 1. Check pre-trade gates (hard filters)
        gates_passed, gate_results = check_all_gates(
            data=data,
            pair=pair,
            current_spread=spread if spread is not None else 0,
            current_time=datetime.utcnow()
        )

        # 2. Run pattern detection to get context data
        best_pattern = get_best_pattern(data, pair) if data is not None and isinstance(data, pd.DataFrame) else None
        all_patterns = detect_all_patterns(data, pair) if data is not None and isinstance(data, pd.DataFrame) else []

        # 3. Build gate status summary
        gate_status = {}
        for result in gate_results:
            gate_status[result.gate_name] = {
                'passed': result.passed,
                'reason': result.reason,
                'metadata': result.metadata
            }

        # 4. Build pattern detection summary
        pattern_context = {
            'gates_passed': gates_passed,
            'gate_status': gate_status,
            'best_pattern': None,
            'all_patterns': [],
            'pattern_summary': 'No patterns detected'
        }

        if best_pattern:
            pattern_context['best_pattern'] = {
                'type': best_pattern.pattern_type,
                'score': best_pattern.score,
                'direction': best_pattern.direction,
                'confidence': best_pattern.confidence,
                'sub_scores': best_pattern.sub_scores,
                'reasoning': best_pattern.reasoning,
                'entry': best_pattern.entry_price,
                'stop': best_pattern.stop_loss,
                'target': best_pattern.take_profit
            }

            pattern_context['pattern_summary'] = (
                f"{best_pattern.pattern_type} detected (Score: {best_pattern.score}/100, "
                f"Direction: {best_pattern.direction})"
            )

        for pattern in all_patterns[:3]:  # Top 3 patterns
            pattern_context['all_patterns'].append({
                'type': pattern.pattern_type,
                'score': pattern.score,
                'direction': pattern.direction
            })

        # 5. Call LLM with ENHANCED context (original indicators + pattern detection)
        return self._analyze_with_pattern_context(market_data, pattern_context)

    def _analyze_with_pattern_context(self, market_data: Dict, pattern_context: Dict) -> Dict:
        """
        Call LLM with ENHANCED context including pattern detection data.

        The LLM receives:
        - All original indicators (EMA, VWAP, RSI, ADX, etc.)
        - Pattern detection results (ORB, SFP, IMPULSE)
        - Pre-trade gate status (spread, ATR, session, news, HTF)
        - Pattern scores and quality breakdown
        """
        pair = market_data['pair']
        current_price = market_data['current_price']
        indicators = market_data['indicators']

        # Extract original indicators
        ema_3 = indicators.get('ema_3', current_price)
        ema_6 = indicators.get('ema_6', current_price)
        ema_12 = indicators.get('ema_12', current_price)
        ema_ribbon_bullish = indicators.get('ema_ribbon_bullish', False)
        ema_ribbon_bearish = indicators.get('ema_ribbon_bearish', False)
        vwap = indicators.get('vwap', current_price)
        above_vwap = indicators.get('above_vwap', False)
        vwap_z_score = indicators.get('vwap_z_score', 0.0)
        rsi = indicators.get('rsi', 50)
        rsi_bullish = indicators.get('rsi_bullish', False)
        rsi_bearish = indicators.get('rsi_bearish', False)
        adx = indicators.get('adx', 0)
        adx_trending = indicators.get('adx_trending', False)
        volume_spike = indicators.get('volume_spike', False)
        donchian_breakout_long = indicators.get('donchian_breakout_long', False)
        donchian_breakout_short = indicators.get('donchian_breakout_short', False)

        # Determine trend
        if ema_ribbon_bullish and above_vwap:
            ema_trend = "BULLISH"
        elif ema_ribbon_bearish and not above_vwap:
            ema_trend = "BEARISH"
        else:
            ema_trend = "NEUTRAL"

        # Build pattern detection summary
        pattern_summary = pattern_context['pattern_summary']
        gates_passed = pattern_context['gates_passed']
        gate_status = pattern_context['gate_status']
        best_pattern = pattern_context['best_pattern']

        # Format gate results
        gate_info = []
        for gate_name, status in gate_status.items():
            symbol = "✅" if status['passed'] else "❌"
            gate_info.append(f"  {symbol} {gate_name}: {status['reason']}")
        gates_text = "\n".join(gate_info)

        # Format pattern detection results
        if best_pattern:
            pattern_details = f"""
PATTERN DETECTED: {best_pattern['type']}
- Overall Score: {best_pattern['score']}/100
- Direction: {best_pattern['direction']}
- Confidence: {best_pattern['confidence']:.0%}
- Sub-Scores:
  * Pattern Quality: {best_pattern['sub_scores']['pattern_quality']}/40
  * Structure/Location: {best_pattern['sub_scores']['structure_location']}/35
  * Volatility/Activity: {best_pattern['sub_scores']['volatility_activity']}/25
- Entry: {best_pattern['entry']:.5f}
- Stop Loss: {best_pattern['stop']:.5f}
- Take Profit: {best_pattern['target']:.5f}
- Reasoning: {', '.join(best_pattern['reasoning'])}"""
        else:
            pattern_details = "PATTERN DETECTED: None (no professional setups found)"

        prompt = f"""You are a Fast Momentum Scalping Expert analyzing {pair} on 1-minute chart.

CURRENT PRICE: {current_price:.5f}

========================================
MOMENTUM INDICATORS (Original):
========================================
- EMA Ribbon (3,6,12): {ema_trend}
  * EMA 3: {ema_3:.5f}
  * EMA 6: {ema_6:.5f}
  * EMA 12: {ema_12:.5f}
- VWAP: {vwap:.5f} (Price is {"ABOVE" if above_vwap else "BELOW"})
  * Z-Score: {vwap_z_score:.2f}
- RSI(7): {rsi:.1f} {"(Bullish momentum)" if rsi_bullish else "(Bearish momentum)" if rsi_bearish else ""}
- ADX(7): {adx:.1f} {"(Trending)" if adx_trending else "(Choppy)"}
- Volume Spike: {"YES" if volume_spike else "NO"}
- Donchian Breakout: {"LONG" if donchian_breakout_long else "SHORT" if donchian_breakout_short else "NONE"}

========================================
PATTERN DETECTION ANALYSIS (NEW DATA):
========================================
{pattern_details}

========================================
PRE-TRADE GATES STATUS:
========================================
{gates_text}

Overall Gates: {"✅ ALL PASSED" if gates_passed else "❌ SOME FAILED"}

========================================
YOUR ANALYSIS:
========================================
You now have BOTH traditional indicators AND professional pattern detection.
Use ALL this information to make your decision:

1. Do the indicators confirm the pattern direction?
2. Is the pattern score strong enough (≥70 recommended)?
3. Are all pre-trade gates passed?
4. Is there momentum + pattern + structure alignment?

Even if a pattern is detected, you can REJECT if:
- Indicators conflict with pattern direction
- Pattern score is borderline (60-69)
- Gates failed (spread too high, wrong session, etc.)
- Risk/reward isn't favorable

Respond in JSON:
{{
    "has_setup": true/false,
    "direction": "BUY/SELL/NONE",
    "confidence": 0-100,
    "setup_type": "ORB_BREAKOUT" or "SFP_FADE" or "IMPULSE_PULLBACK" or "EMA_BREAKOUT" or "NONE",
    "key_triggers": ["list", "of", "confirmed", "signals"],
    "reasoning": "explanation considering BOTH indicators and pattern detection"
}}"""

        response = self.llm.invoke([HumanMessage(content=prompt)])

        try:
            content = response.content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()
            result = json.loads(content)

            # Add pattern context to result
            if best_pattern:
                result['pattern_score'] = best_pattern['score']
                result['pattern_type'] = best_pattern['type']
                result['pattern_direction'] = best_pattern['direction']
            else:
                result['pattern_score'] = 0
                result['pattern_type'] = 'NONE'
                result['pattern_direction'] = 'NONE'

            result['gates_passed'] = gates_passed
            result['gate_summary'] = {k: v['passed'] for k, v in gate_status.items()}

        except Exception as e:
            logger.warning(f"⚠️  Fast Momentum Agent JSON parse error: {e}")
            result = {
                "has_setup": False,
                "direction": "NONE",
                "confidence": 0,
                "setup_type": "NONE",
                "key_triggers": [],
                "reasoning": f"Parse error: {str(e)}",
                "pattern_score": 0,
                "gates_passed": gates_passed
            }

        return result

    def _analyze_llm_only(self, market_data: Dict) -> Dict:
        """Original LLM-only analysis (backward compatibility when pattern detection disabled)."""
        pair = market_data['pair']
        current_price = market_data['current_price']
        indicators = market_data['indicators']

        # Extract indicators
        ema_3 = indicators.get('ema_3', current_price)
        ema_6 = indicators.get('ema_6', current_price)
        ema_12 = indicators.get('ema_12', current_price)
        ema_ribbon_bullish = indicators.get('ema_ribbon_bullish', False)
        ema_ribbon_bearish = indicators.get('ema_ribbon_bearish', False)
        vwap = indicators.get('vwap', current_price)
        above_vwap = indicators.get('above_vwap', False)
        rsi = indicators.get('rsi', 50)
        adx = indicators.get('adx', 0)
        volume_spike = indicators.get('volume_spike', False)

        # Determine trend
        if ema_ribbon_bullish and above_vwap:
            ema_trend = "BULLISH"
        elif ema_ribbon_bearish and not above_vwap:
            ema_trend = "BEARISH"
        else:
            ema_trend = "NEUTRAL"

        prompt = f"""You are a Fast Momentum Scalping Expert analyzing {pair} on 1-minute chart.

CURRENT PRICE: {current_price:.5f}

MOMENTUM INDICATORS:
- EMA Ribbon (3,6,12): {ema_trend}
- VWAP: {vwap:.5f} (Price is {"ABOVE" if above_vwap else "BELOW"})
- RSI(7): {rsi:.1f}
- ADX(7): {adx:.1f}
- Volume Spike: {"YES" if volume_spike else "NO"}

Is there a CLEAR scalping setup?

Respond in JSON:
{{
    "has_setup": true/false,
    "direction": "BUY/SELL/NONE",
    "confidence": 0-100,
    "setup_type": "EMA_BREAKOUT" or "MOMENTUM_SURGE" or "NONE",
    "key_triggers": ["list", "of", "signals"],
    "reasoning": "brief explanation"
}}"""

        response = self.llm.invoke([HumanMessage(content=prompt)])

        try:
            content = response.content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()
            result = json.loads(content)
        except Exception as e:
            logger.warning(f"⚠️  Fast Momentum Agent JSON parse error: {e}")
            result = {
                "has_setup": False,
                "direction": "NONE",
                "confidence": 0,
                "setup_type": "NONE",
                "key_triggers": [],
                "reasoning": f"Parse error: {str(e)}"
            }

        return result


class TechnicalAgent:
    """
    Analyzes technical levels and patterns for scalping confirmation.
    Focuses on: Support/Resistance, price action, recent structure.
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.name = "Technical Agent"

    def analyze(self, market_data: Dict) -> Dict:
        """
        Quick technical analysis for scalping confirmation.

        Args:
            market_data: Dict with price, support/resistance, patterns

        Returns:
            Dict with technical assessment
        """
        pair = market_data['pair']
        current_price = market_data['current_price']
        indicators = market_data['indicators']
        support = market_data.get('nearest_support', current_price * 0.999)
        resistance = market_data.get('nearest_resistance', current_price * 1.001)

        # Calculate distance to S/R
        pip_value = 0.0001 if 'JPY' not in pair else 0.01
        dist_to_support = (current_price - support) / pip_value if support else 999
        dist_to_resistance = (resistance - current_price) / pip_value if resistance else 999

        # Position relative to S/R
        if dist_to_support < 5:
            position = "AT_SUPPORT"
        elif dist_to_resistance < 5:
            position = "AT_RESISTANCE"
        elif dist_to_support < dist_to_resistance:
            position = "ABOVE_SUPPORT"
        else:
            position = "BELOW_RESISTANCE"

        # NEW: Professional Technical Levels
        # Floor Pivot Points
        pivot_pp = indicators.get('pivot_PP', current_price)
        pivot_r1 = indicators.get('pivot_R1', current_price * 1.001)
        pivot_s1 = indicators.get('pivot_S1', current_price * 0.999)
        pivot_r2 = indicators.get('pivot_R2', current_price * 1.002)
        pivot_s2 = indicators.get('pivot_S2', current_price * 0.998)

        # Big Figure Levels (nearest)
        nearest_big_figure = indicators.get('nearest_big_figure', current_price)
        dist_to_big_figure = abs(current_price - nearest_big_figure) / pip_value

        # Opening Range levels
        or_high = indicators.get('OR_high', current_price * 1.001)
        or_low = indicators.get('OR_low', current_price * 0.999)

        # Inside Bar Compression
        inside_bar_compression = indicators.get('inside_bar_compression', False)
        nr_bars = indicators.get('nr_bars', 0)

        # ADR Position (% of daily range used)
        adr_pct_used = indicators.get('adr_pct_used', 0.0)

        # Determine which pivot level is closest
        pivot_levels = {
            'PP': pivot_pp,
            'R1': pivot_r1,
            'S1': pivot_s1,
            'R2': pivot_r2,
            'S2': pivot_s2
        }
        closest_pivot = min(pivot_levels.items(), key=lambda x: abs(current_price - x[1]))
        dist_to_pivot = abs(current_price - closest_pivot[1]) / pip_value

        prompt = f"""You are a Technical Scalping Expert analyzing {pair} for quick 10-pip scalp opportunities.
Uses INSTITUTIONAL LEVELS: Floor Pivots, Big Figures, Opening Range, Compression Patterns.

CURRENT PRICE: {current_price:.5f}

CLASSIC S/R STRUCTURE:
- Nearest Support: {support:.5f} ({dist_to_support:.1f} pips away)
- Nearest Resistance: {resistance:.5f} ({dist_to_resistance:.1f} pips away)
- Position: {position}

INSTITUTIONAL LEVELS (Banks/Funds watch these):
- Floor Pivots: PP={pivot_pp:.5f}, R1={pivot_r1:.5f}, S1={pivot_s1:.5f}, R2={pivot_r2:.5f}, S2={pivot_s2:.5f}
- Closest Pivot: {closest_pivot[0]} at {closest_pivot[1]:.5f} ({dist_to_pivot:.1f} pips away)
- Big Figure: {nearest_big_figure:.5f} ({dist_to_big_figure:.1f} pips away) - Options/stops cluster here
- Opening Range: High={or_high:.5f}, Low={or_low:.5f} - Breakout zones

COMPRESSION PATTERNS:
- Inside Bar Sequence: {"YES - Compression building" if inside_bar_compression else "NO"}
- Narrow Range: {"NR{nr_bars} detected - Volatility squeeze" if nr_bars >= 4 else "Normal range"}

DAILY CONTEXT:
- ADR % Used: {adr_pct_used:.0f}% {"(Extended - fade setups)" if adr_pct_used > 80 else "(Room to run)" if adr_pct_used < 60 else "(Mid-range)"}

SCALPING CONTEXT:
- We need 10 pips to TP, 6 pips to SL (16 pips total range)
- BEST setups: Pivot bounces, big figure bounces, ORB breakouts, compression breakouts
- AVOID: Price stuck between tight levels, extended past 80% ADR

Does the technical structure support a scalp trade?

Respond in JSON format:
{{
    "supports_trade": true/false,
    "direction_preferred": "BUY/SELL/NONE",
    "confidence": 0-100,
    "entry_quality": "EXCELLENT/GOOD/POOR",
    "space_to_target": "SUFFICIENT/LIMITED/INSUFFICIENT",
    "key_levels": ["which institutional levels support this trade"],
    "reasoning": "brief explanation focusing on institutional levels and patterns"
}}"""

        response = self.llm.invoke([HumanMessage(content=prompt)])

        try:
            content = response.content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()
            result = json.loads(content)
        except Exception as e:
            logger.warning(f"⚠️  Technical Agent JSON parse error: {e}")
            result = {
                "supports_trade": False,
                "direction_preferred": "NONE",
                "confidence": 0,
                "entry_quality": "POOR",
                "space_to_target": "INSUFFICIENT",
                "key_levels": [],
                "reasoning": f"Parse error: {str(e)}"
            }

        return result


class ScalpValidator:
    """
    JUDGE: Validates scalping setups by combining Fast Momentum + Technical analysis.
    Acts as the final decision maker on whether to take the scalp.
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.name = "Scalp Validator (Judge)"

        # Initialize dynamic SL/TP calculator (research-backed)
        self.sltp_calculator = DynamicSLTPCalculator(
            atr_period=ScalpingConfig.ATR_PERIOD,
            atr_mult_sl=ScalpingConfig.ATR_MULTIPLIER_SL,
            atr_mult_tp=ScalpingConfig.ATR_MULTIPLIER_TP,
            atr_mult_trail=ScalpingConfig.ATR_MULTIPLIER_TRAIL,
            buffer_spread_mult=ScalpingConfig.BUFFER_SPREAD_MULT,
            buffer_atr_mult=ScalpingConfig.BUFFER_ATR_MULT,
            timeout_minutes=ScalpingConfig.TIMEOUT_MINUTES,
            time_decay_lambda=ScalpingConfig.TIME_DECAY_LAMBDA,
            breakeven_trigger=ScalpingConfig.BREAKEVEN_TRIGGER
        )

    def validate(self, momentum_analysis: Dict, technical_analysis: Dict, market_data: Dict) -> ScalpSetup:
        """
        Final validation with enhanced pattern detection context.

        The Fast Momentum Agent now provides rich pattern detection data.
        Validator makes final decision considering both agents + pattern scores.

        Args:
            momentum_analysis: Output from FastMomentumAgent (includes pattern detection data)
            technical_analysis: Output from TechnicalAgent
            market_data: Current market data

        Returns:
            ScalpSetup object with final decision
        """
        pair = market_data['pair']
        current_price = market_data['current_price']
        spread = market_data.get('spread', 1.0)

        # Handle None spread (data not available yet)
        if spread is None:
            spread = 1.0  # Use safe default

        # Check spread first (critical for scalping)
        if spread > ScalpingConfig.MAX_SPREAD_PIPS:
            return ScalpSetup(
                pair=pair,
                direction="NONE",
                entry_price=current_price,
                take_profit=current_price,
                stop_loss=current_price,
                confidence=0.0,
                reasoning=[f"Spread too wide: {spread:.1f} pips > {ScalpingConfig.MAX_SPREAD_PIPS} max"],
                indicators=market_data.get('indicators', {}),
                spread=spread,
                timestamp=datetime.now(),
                approved=False
            )

        # Extract pattern detection data if available
        pattern_score = momentum_analysis.get('pattern_score', 'N/A')
        pattern_type = momentum_analysis.get('pattern_type', 'N/A')
        pattern_direction = momentum_analysis.get('pattern_direction', 'N/A')
        gates_passed = momentum_analysis.get('gates_passed', True)
        gate_summary = momentum_analysis.get('gate_summary', {})

        prompt = f"""You are the SCALP VALIDATOR (Final Judge) for {pair}.

Two agents have analyzed the setup with ENHANCED PATTERN DETECTION CONTEXT:

FAST MOMENTUM AGENT (Enhanced with Pattern Detection):
- Has Setup: {momentum_analysis.get('has_setup')}
- Direction: {momentum_analysis.get('direction')}
- Confidence: {momentum_analysis.get('confidence')}%
- Setup Type: {momentum_analysis.get('setup_type')}
- Key Triggers: {momentum_analysis.get('key_triggers')}
- Reasoning: {momentum_analysis.get('reasoning')}

PATTERN DETECTION DATA (NEW):
- Pattern Type: {pattern_type}
- Pattern Score: {pattern_score}/100
- Pattern Direction: {pattern_direction}
- Pre-Trade Gates: {"✅ ALL PASSED" if gates_passed else f"❌ FAILED: {[k for k, v in gate_summary.items() if not v]}"}

TECHNICAL AGENT:
- Supports Trade: {technical_analysis.get('supports_trade')}
- Direction: {technical_analysis.get('direction_preferred')}
- Confidence: {technical_analysis.get('confidence')}%
- Entry Quality: {technical_analysis.get('entry_quality')}
- Space to Target: {technical_analysis.get('space_to_target')}
- Key Levels: {technical_analysis.get('key_levels', [])} (Pivots/BigFigs/ORB)
- Reasoning: {technical_analysis.get('reasoning')}

MARKET CONDITIONS:
- Current Price: {current_price:.5f}
- Spread: {spread:.1f} pips (Max allowed: {ScalpingConfig.MAX_SPREAD_PIPS})
- Target: {ScalpingConfig.TAKE_PROFIT_PIPS} pips TP / {ScalpingConfig.STOP_LOSS_PIPS} pips SL

PROFESSIONAL SETUP HIERARCHY (Win Rate Priority):
1. ORB_BREAKOUT + Volume = 75%+ win rate (TIER 1)
2. SFP_FADE + RSI divergence = 70%+ win rate (TIER 1)
3. IMPULSE_PULLBACK + pivot bounce = 70%+ win rate (TIER 1)
4. BIG_FIGURE bounce + momentum = 65%+ win rate (TIER 2)
5. VWAP_REVERSION (choppy only) = 60%+ win rate (TIER 2)
6. EMA_BREAKOUT + confirmations = 60%+ win rate (TIER 2)

YOUR TASK: Make the final decision. This is a 10-20 minute scalp.
- PRIORITIZE professional setups (ORB, SFP, IMPULSE) → assign TIER 1
- Only approve if BOTH agents are confident and aligned
- Spread cost is {spread:.1f} pips = {(spread/ScalpingConfig.TAKE_PROFIT_PIPS)*100:.0f}% of profit
- Need HIGH probability setup (3+ confirmations) to overcome spread cost

Respond in JSON format:
{{
    "approved": true/false,
    "direction": "BUY/SELL/NONE",
    "final_confidence": 0-100,
    "risk_tier": 1-3 (1=professional setup, 2=good momentum, 3=skip),
    "reasoning": "your decision explanation focusing on which professional setup triggered",
    "entry_triggers": ["list", "of", "confirmed", "signals"]
}}"""

        response = self.llm.invoke([HumanMessage(content=prompt)])

        try:
            content = response.content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()
            decision = json.loads(content)
        except Exception as e:
            logger.warning(f"⚠️  Scalp Validator JSON parse error: {e}")
            decision = {
                "approved": False,
                "direction": "NONE",
                "final_confidence": 0,
                "risk_tier": 3,
                "reasoning": f"Parse error: {str(e)}",
                "entry_triggers": []
            }

        # Build ScalpSetup
        direction = decision.get('direction', 'NONE')
        if not decision.get('approved', False) or direction == 'NONE':
            return ScalpSetup(
                pair=pair,
                direction="NONE",
                entry_price=current_price,
                take_profit=current_price,
                stop_loss=current_price,
                confidence=0.0,
                reasoning=[decision.get('reasoning', 'Not approved')],
                indicators=market_data.get('indicators', {}),
                spread=spread,
                timestamp=datetime.now(),
                approved=False
            )

        # Calculate TP/SL based on direction
        pip_value = 0.0001 if 'JPY' not in pair else 0.01

        # Use dynamic SL/TP if enabled
        if ScalpingConfig.DYNAMIC_SLTP_ENABLED:
            try:
                # Get recent candles for ATR calculation
                candles = market_data.get('candles', [])

                if len(candles) >= ScalpingConfig.ATR_PERIOD:
                    # Calculate dynamic levels using research-backed method
                    levels = self.sltp_calculator.calculate_sltp(
                        entry_price=current_price,
                        direction='long' if direction == 'BUY' else 'short',
                        pair=pair,
                        candles=candles,
                        spread=spread,
                        use_structure=ScalpingConfig.USE_MARKET_STRUCTURE
                    )

                    # Apply safety constraints
                    tp_pips = max(ScalpingConfig.MIN_TP_PIPS, min(levels.tp_pips, ScalpingConfig.MAX_TP_PIPS))
                    sl_pips = max(ScalpingConfig.MIN_SL_PIPS, min(levels.sl_pips, ScalpingConfig.MAX_SL_PIPS))

                    # Calculate prices
                    if direction == 'BUY':
                        take_profit = current_price + (tp_pips * pip_value)
                        stop_loss = current_price - (sl_pips * pip_value)
                    else:  # SELL
                        take_profit = current_price - (tp_pips * pip_value)
                        stop_loss = current_price + (sl_pips * pip_value)

                    # Log comparison (for analysis)
                    logger.info(f"📊 Dynamic SL/TP for {pair} {direction}:")
                    logger.info(f"   Hardcoded: TP={ScalpingConfig.TAKE_PROFIT_PIPS} / SL={ScalpingConfig.STOP_LOSS_PIPS} pips (R:R={ScalpingConfig.TAKE_PROFIT_PIPS/ScalpingConfig.STOP_LOSS_PIPS:.2f})")
                    logger.info(f"   Dynamic:   TP={tp_pips:.1f} / SL={sl_pips:.1f} pips (R:R={tp_pips/sl_pips:.2f})")
                    logger.info(f"   Method: {levels.method}, Confidence: {levels.confidence:.0%}, ATR: {levels.metadata.get('atr_pips', 0):.1f} pips")

                else:
                    # Not enough candles, fall back to hardcoded
                    logger.warning(f"⚠️  Not enough candles for dynamic SL/TP ({len(candles)}/{ScalpingConfig.ATR_PERIOD}), using hardcoded values")
                    if direction == 'BUY':
                        take_profit = current_price + (ScalpingConfig.TAKE_PROFIT_PIPS * pip_value)
                        stop_loss = current_price - (ScalpingConfig.STOP_LOSS_PIPS * pip_value)
                    else:  # SELL
                        take_profit = current_price - (ScalpingConfig.TAKE_PROFIT_PIPS * pip_value)
                        stop_loss = current_price + (ScalpingConfig.STOP_LOSS_PIPS * pip_value)

            except Exception as e:
                # Error calculating dynamic levels, fall back to hardcoded
                logger.warning(f"⚠️  Error calculating dynamic SL/TP: {e}, using hardcoded values")
                if direction == 'BUY':
                    take_profit = current_price + (ScalpingConfig.TAKE_PROFIT_PIPS * pip_value)
                    stop_loss = current_price - (ScalpingConfig.STOP_LOSS_PIPS * pip_value)
                else:  # SELL
                    take_profit = current_price - (ScalpingConfig.TAKE_PROFIT_PIPS * pip_value)
                    stop_loss = current_price + (ScalpingConfig.STOP_LOSS_PIPS * pip_value)

        else:
            # Use hardcoded values (original behavior)
            if direction == 'BUY':
                take_profit = current_price + (ScalpingConfig.TAKE_PROFIT_PIPS * pip_value)
                stop_loss = current_price - (ScalpingConfig.STOP_LOSS_PIPS * pip_value)
            else:  # SELL
                take_profit = current_price - (ScalpingConfig.TAKE_PROFIT_PIPS * pip_value)
                stop_loss = current_price + (ScalpingConfig.STOP_LOSS_PIPS * pip_value)

        return ScalpSetup(
            pair=pair,
            direction=direction,
            entry_price=current_price,
            take_profit=take_profit,
            stop_loss=stop_loss,
            confidence=decision.get('final_confidence', 0) / 100.0,
            reasoning=decision.get('entry_triggers', []),
            indicators=market_data.get('indicators', {}),
            spread=spread,
            timestamp=datetime.now(),
            approved=True,
            risk_tier=decision.get('risk_tier', 2)
        )


class AggressiveRiskAgent:
    """
    Aggressive risk perspective: Maximize position size and frequency.
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.name = "Aggressive Risk Agent"

    def analyze(self, scalp_setup: ScalpSetup, account_state: Dict) -> Dict:
        """Analyze from aggressive risk perspective."""
        prompt = f"""You are the AGGRESSIVE RISK ANALYST reviewing a scalp trade.

PROPOSED SCALP:
- Pair: {scalp_setup.pair}
- Direction: {scalp_setup.direction}
- Entry: {scalp_setup.entry_price:.5f}
- TP: {scalp_setup.take_profit:.5f} ({ScalpingConfig.TAKE_PROFIT_PIPS} pips)
- SL: {scalp_setup.stop_loss:.5f} ({ScalpingConfig.STOP_LOSS_PIPS} pips)
- Confidence: {scalp_setup.confidence*100:.0f}%
- Spread: {scalp_setup.spread:.1f} pips

ACCOUNT STATE:
- Trades today: {account_state.get('trades_today', 0)} / {ScalpingConfig.MAX_TRADES_PER_DAY}
- Open positions: {account_state.get('open_positions', 0)} / {ScalpingConfig.MAX_OPEN_POSITIONS}
- Today's P&L: {account_state.get('daily_pnl', 0):.2f}%

YOUR PERSPECTIVE: Maximize opportunity, take calculated risks.

Respond in JSON:
{{
    "recommendation": "FULL_SIZE/REDUCE_SIZE/SKIP",
    "position_size_multiplier": 1.0-1.5,
    "reasoning": "your aggressive perspective"
}}"""

        response = self.llm.invoke([HumanMessage(content=prompt)])

        try:
            content = response.content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()
            result = json.loads(content)
        except Exception as e:
            result = {
                "recommendation": "FULL_SIZE",
                "position_size_multiplier": 1.0,
                "reasoning": f"Parse error: {str(e)}"
            }

        return result


class ConservativeRiskAgent:
    """
    Conservative risk perspective: Prioritize capital preservation.
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.name = "Conservative Risk Agent"

    def analyze(self, scalp_setup: ScalpSetup, account_state: Dict) -> Dict:
        """Analyze from conservative risk perspective."""
        prompt = f"""You are the CONSERVATIVE RISK ANALYST reviewing a scalp trade.

PROPOSED SCALP:
- Pair: {scalp_setup.pair}
- Direction: {scalp_setup.direction}
- Confidence: {scalp_setup.confidence*100:.0f}%
- Spread: {scalp_setup.spread:.1f} pips (eats {(scalp_setup.spread/ScalpingConfig.TAKE_PROFIT_PIPS)*100:.0f}% of profit)

ACCOUNT STATE:
- Trades today: {account_state.get('trades_today', 0)}
- Consecutive losses: {account_state.get('consecutive_losses', 0)}
- Daily P&L: {account_state.get('daily_pnl', 0):.2f}%

YOUR PERSPECTIVE: Protect capital, avoid overtrading.

Respond in JSON:
{{
    "recommendation": "FULL_SIZE/REDUCE_SIZE/SKIP",
    "position_size_multiplier": 0.5-1.0,
    "reasoning": "your conservative concerns"
}}"""

        response = self.llm.invoke([HumanMessage(content=prompt)])

        try:
            content = response.content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()
            result = json.loads(content)
        except Exception as e:
            result = {
                "recommendation": "REDUCE_SIZE",
                "position_size_multiplier": 0.75,
                "reasoning": f"Parse error: {str(e)}"
            }

        return result


class RiskManager:
    """
    JUDGE: Final risk management decision.
    Combines aggressive + conservative perspectives to determine final position size.
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.name = "Risk Manager (Judge)"

    def decide(self, scalp_setup: ScalpSetup, aggressive: Dict, conservative: Dict, account_state: Dict) -> Tuple[bool, float]:
        """
        Final risk management decision.

        Args:
            scalp_setup: The approved scalp setup
            aggressive: Aggressive risk agent's recommendation
            conservative: Conservative risk agent's recommendation
            account_state: Current account state

        Returns:
            Tuple of (execute: bool, position_size: float)
        """
        # Check hard limits first
        if account_state.get('trades_today', 0) >= ScalpingConfig.MAX_TRADES_PER_DAY:
            logger.error(f"❌ Daily trade limit reached: {account_state['trades_today']}")
            return False, 0.0

        if account_state.get('open_positions', 0) >= ScalpingConfig.MAX_OPEN_POSITIONS:
            logger.error(f"❌ Max open positions reached: {account_state['open_positions']}")
            return False, 0.0

        if account_state.get('daily_pnl', 0) <= -ScalpingConfig.MAX_DAILY_LOSS_PERCENT:
            logger.error(f"❌ Daily loss limit hit: {account_state['daily_pnl']:.2f}%")
            return False, 0.0

        if account_state.get('consecutive_losses', 0) >= ScalpingConfig.MAX_CONSECUTIVE_LOSSES:
            logger.error(f"❌ Consecutive loss limit: {account_state['consecutive_losses']}")
            return False, 0.0

        prompt = f"""You are the RISK MANAGER (Final Judge) for position sizing.

SCALP SETUP:
- Pair: {scalp_setup.pair}
- Confidence: {scalp_setup.confidence*100:.0f}%
- Risk Tier: {scalp_setup.risk_tier}

AGGRESSIVE ANALYST: {aggressive.get('recommendation')} (multiplier: {aggressive.get('position_size_multiplier', 1.0)})
Reasoning: {aggressive.get('reasoning')}

CONSERVATIVE ANALYST: {conservative.get('recommendation')} (multiplier: {conservative.get('position_size_multiplier', 1.0)})
Reasoning: {conservative.get('reasoning')}

ACCOUNT STATE:
- Trades today: {account_state.get('trades_today', 0)} / {ScalpingConfig.MAX_TRADES_PER_DAY}
- Daily P&L: {account_state.get('daily_pnl', 0):.2f}%

YOUR DECISION: Final position size based on both perspectives.

Respond in JSON:
{{
    "execute": true/false,
    "position_size_lots": 0.0-0.3,
    "reasoning": "your final decision balancing both perspectives"
}}"""

        response = self.llm.invoke([HumanMessage(content=prompt)])

        try:
            content = response.content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()
            decision = json.loads(content)
        except Exception as e:
            logger.warning(f"⚠️  Risk Manager parse error: {e}")
            # Default to conservative
            decision = {
                "execute": True,
                "position_size_lots": 0.1,
                "reasoning": f"Parse error, defaulting to minimum size"
            }

        execute = decision.get('execute', True)
        position_size = decision.get('position_size_lots', 0.1)

        # Apply tier-based sizing
        if scalp_setup.risk_tier == 1:
            base_size = ScalpingConfig.TIER1_SIZE
        elif scalp_setup.risk_tier == 2:
            base_size = ScalpingConfig.TIER2_SIZE
        else:
            base_size = ScalpingConfig.TIER3_SIZE

        # Adjust for spread if enabled (handle None spread)
        if (ScalpingConfig.REDUCE_SIZE_HIGH_SPREAD and
            scalp_setup.spread is not None and
            scalp_setup.spread > ScalpingConfig.SPREAD_PENALTY_THRESHOLD):
            base_size *= 0.75

        final_size = min(position_size, base_size)

        logger.info(f"\n🎯 Risk Manager Decision: {'EXECUTE' if execute else 'SKIP'}")
        logger.info(f"   Position Size: {final_size:.2f} lots")
        logger.info(f"   Reasoning: {decision.get('reasoning', 'N/A')}")

        return execute, final_size


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def create_scalping_agents(config: ScalpingConfig) -> Dict:
    """
    Initialize all scalping agents.

    Returns:
        Dict with all agent instances
    """
    # Initialize LLM with timeout and token limits
    llm = ChatOpenAI(
        model="gpt-4o-mini",  # Fast model for low latency
        temperature=0.1,
        max_tokens=400,  # Cap output to prevent long generation
        timeout=60,  # 60 second timeout (increased from default)
        max_retries=2,  # Limit retries
        api_key=config.OPENAI_API_KEY
    )

    return {
        "momentum": FastMomentumAgent(llm),
        "technical": TechnicalAgent(llm),
        "validator": ScalpValidator(llm),
        "aggressive_risk": AggressiveRiskAgent(llm),
        "conservative_risk": ConservativeRiskAgent(llm),
        "risk_manager": RiskManager(llm)
    }


if __name__ == "__main__":
    logger.info(f"Scalping Agents Module")
    logger.info(f"=" * 80)
    logger.info(f"\nAgent Architecture:")
    logger.info(f"1. Fast Momentum Agent - analyzes 1m momentum")
    logger.info(f"2. Technical Agent - validates technical structure")
    logger.info(f"3. Scalp Validator (JUDGE) - final setup approval")
    logger.info(f"4. Aggressive Risk Agent - maximize opportunity")
    logger.info(f"5. Conservative Risk Agent - protect capital")
    logger.info(f"6. Risk Manager (JUDGE) - final position sizing")
    logger.info(f"\nMaintains 2-agent + judge structure for quality control")
