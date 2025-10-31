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
from scalping_config import ScalpingConfig
from scalping_indicators import ScalpingIndicators


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
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.name = "Fast Momentum Agent"

    def analyze(self, market_data: Dict) -> Dict:
        """
        Quick momentum analysis for scalping entry using optimized indicators.

        Args:
            market_data: Dict with price, indicators, volume, etc.

        Returns:
            Dict with momentum assessment
        """
        pair = market_data['pair']
        current_price = market_data['current_price']
        indicators = market_data['indicators']

        # Extract OPTIMIZED indicators (EMA 3,6,12 NOT 5,10,20)
        ema_3 = indicators.get('ema_3', current_price)
        ema_6 = indicators.get('ema_6', current_price)
        ema_12 = indicators.get('ema_12', current_price)
        ema_ribbon_bullish = indicators.get('ema_ribbon_bullish', False)
        ema_ribbon_bearish = indicators.get('ema_ribbon_bearish', False)

        # VWAP (institutional anchor)
        vwap = indicators.get('vwap', current_price)
        above_vwap = indicators.get('above_vwap', False)

        # Donchian breakout
        donchian_upper = indicators.get('donchian_upper', current_price * 1.001)
        donchian_lower = indicators.get('donchian_lower', current_price * 0.999)
        donchian_breakout_long = indicators.get('donchian_breakout_long', False)
        donchian_breakout_short = indicators.get('donchian_breakout_short', False)

        # RSI(7) NOT RSI(14)
        rsi = indicators.get('rsi', 50)
        rsi_bullish = indicators.get('rsi_bullish', False)  # RSI>55 with rising slope
        rsi_bearish = indicators.get('rsi_bearish', False)  # RSI<45 with falling slope

        # ADX(7) trend strength
        adx = indicators.get('adx', 0)
        adx_trending = indicators.get('adx_trending', False)  # ADX>18 and rising
        di_bullish = indicators.get('di_bullish', False)
        di_bearish = indicators.get('di_bearish', False)

        # Volume
        volume_spike = indicators.get('volume_spike', False)

        # Bollinger Squeeze
        squeeze_on = indicators.get('squeeze_on', False)
        squeeze_off = indicators.get('squeeze_off', False)

        # SuperTrend direction
        supertrend_direction = indicators.get('supertrend_direction', 0)

        # Determine trend direction
        if ema_ribbon_bullish and above_vwap:
            ema_trend = "BULLISH"
        elif ema_ribbon_bearish and not above_vwap:
            ema_trend = "BEARISH"
        else:
            ema_trend = "NEUTRAL"

        # RSI momentum (using RSI 7, not 14)
        if rsi_bullish:
            rsi_signal = "BULLISH_MOMENTUM"
        elif rsi_bearish:
            rsi_signal = "BEARISH_MOMENTUM"
        elif rsi < 30:
            rsi_signal = "OVERSOLD"
        elif rsi > 70:
            rsi_signal = "OVERBOUGHT"
        else:
            rsi_signal = "NEUTRAL"

        # VWAP position
        vwap_position = "ABOVE" if above_vwap else "BELOW"
        vwap_bias = "LONG_BIAS" if above_vwap else "SHORT_BIAS"

        prompt = f"""You are a Fast Momentum Scalping Expert analyzing {pair} on 1-minute chart for 10-20 minute trades.
Uses OPTIMIZED indicators: Fast EMA (3,6,12), VWAP, Donchian, RSI(7), ADX(7).

CURRENT PRICE: {current_price:.5f}

OPTIMIZED MOMENTUM INDICATORS:
- EMA Ribbon (3,6,12): {ema_trend} (3: {ema_3:.5f}, 6: {ema_6:.5f}, 12: {ema_12:.5f})
- VWAP: {vwap:.5f} → Price is {vwap_position} VWAP ({vwap_bias})
- Donchian Breakout: {"LONG" if donchian_breakout_long else "SHORT" if donchian_breakout_short else "NONE"}
- RSI(7): {rsi:.1f} ({rsi_signal})
- ADX(7): {adx:.1f} {"TRENDING" if adx_trending else "CHOPPY"} (DI: {"+" if di_bullish else "-" if di_bearish else "neutral"})
- Volume Spike: {"YES" if volume_spike else "NO"}
- BB Squeeze: {"ON (compressed)" if squeeze_on else "OFF (released)" if squeeze_off else "normal"}
- SuperTrend: {"BULLISH" if supertrend_direction == 1 else "BEARISH" if supertrend_direction == -1 else "neutral"}

SCALPING RULES:
- Only trade HIGH PROBABILITY setups with 2+ confirmations
- Look for: EMA breakouts + volume spike, RSI momentum + support bounce
- Avoid: choppy/ranging markets, weak volume, conflicting signals

Is there a CLEAR, HIGH-PROBABILITY scalping setup RIGHT NOW?

Respond in JSON format:
{{
    "has_setup": true/false,
    "direction": "BUY/SELL/NONE",
    "confidence": 0-100,
    "setup_type": "EMA_BREAKOUT" or "MOMENTUM_SURGE" or "BOUNCE" or "NONE",
    "key_triggers": ["list", "of", "signals"],
    "reasoning": "brief explanation focusing on momentum and confirmations"
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
            print(f"⚠️  Fast Momentum Agent JSON parse error: {e}")
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
        support = market_data.get('nearest_support', current_price * 0.999)
        resistance = market_data.get('nearest_resistance', current_price * 1.001)

        # Calculate distance to S/R
        dist_to_support = (current_price - support) * 10000 if support else 999
        dist_to_resistance = (resistance - current_price) * 10000 if resistance else 999

        # Position relative to S/R
        if dist_to_support < 5:
            position = "AT_SUPPORT"
        elif dist_to_resistance < 5:
            position = "AT_RESISTANCE"
        elif dist_to_support < dist_to_resistance:
            position = "ABOVE_SUPPORT"
        else:
            position = "BELOW_RESISTANCE"

        prompt = f"""You are a Technical Scalping Expert analyzing {pair} for quick 10-pip scalp opportunities.

CURRENT PRICE: {current_price:.5f}

TECHNICAL STRUCTURE:
- Nearest Support: {support:.5f} ({dist_to_support:.1f} pips away)
- Nearest Resistance: {resistance:.5f} ({dist_to_resistance:.1f} pips away)
- Position: {position}

SCALPING CONTEXT:
- We need 10 pips to TP, 6 pips to SL
- Best setups: bounces from S/R, clear breakouts with space to run
- Avoid: price stuck between tight S/R, no room for 10-pip move

Does the technical structure support a scalp trade?

Respond in JSON format:
{{
    "supports_trade": true/false,
    "direction_preferred": "BUY/SELL/NONE",
    "confidence": 0-100,
    "entry_quality": "EXCELLENT/GOOD/POOR",
    "space_to_target": "SUFFICIENT/LIMITED/INSUFFICIENT",
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
            print(f"⚠️  Technical Agent JSON parse error: {e}")
            result = {
                "supports_trade": False,
                "direction_preferred": "NONE",
                "confidence": 0,
                "entry_quality": "POOR",
                "space_to_target": "INSUFFICIENT",
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

    def validate(self, momentum_analysis: Dict, technical_analysis: Dict, market_data: Dict) -> ScalpSetup:
        """
        Final validation: Should we take this scalp?

        Args:
            momentum_analysis: Output from FastMomentumAgent
            technical_analysis: Output from TechnicalAgent
            market_data: Current market data

        Returns:
            ScalpSetup object with final decision
        """
        pair = market_data['pair']
        current_price = market_data['current_price']
        spread = market_data.get('spread', 1.0)

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

        prompt = f"""You are the SCALP VALIDATOR (Final Judge) for {pair}.

Two agents have analyzed the setup:

FAST MOMENTUM AGENT:
- Has Setup: {momentum_analysis.get('has_setup')}
- Direction: {momentum_analysis.get('direction')}
- Confidence: {momentum_analysis.get('confidence')}%
- Setup Type: {momentum_analysis.get('setup_type')}
- Reasoning: {momentum_analysis.get('reasoning')}

TECHNICAL AGENT:
- Supports Trade: {technical_analysis.get('supports_trade')}
- Direction: {technical_analysis.get('direction_preferred')}
- Confidence: {technical_analysis.get('confidence')}%
- Entry Quality: {technical_analysis.get('entry_quality')}
- Space to Target: {technical_analysis.get('space_to_target')}

MARKET CONDITIONS:
- Current Price: {current_price:.5f}
- Spread: {spread:.1f} pips (Max allowed: {ScalpingConfig.MAX_SPREAD_PIPS})
- Target: {ScalpingConfig.TAKE_PROFIT_PIPS} pips TP / {ScalpingConfig.STOP_LOSS_PIPS} pips SL

YOUR TASK: Make the final decision. This is a 10-20 minute scalp.
- Only approve if BOTH agents are confident and aligned
- Spread cost is {spread:.1f} pips = {(spread/ScalpingConfig.TAKE_PROFIT_PIPS)*100:.0f}% of profit
- Need HIGH probability setup to overcome spread cost

Respond in JSON format:
{{
    "approved": true/false,
    "direction": "BUY/SELL/NONE",
    "final_confidence": 0-100,
    "risk_tier": 1-3 (1=highest quality, 3=skip),
    "reasoning": "your decision explanation",
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
            print(f"⚠️  Scalp Validator JSON parse error: {e}")
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
            print(f"❌ Daily trade limit reached: {account_state['trades_today']}")
            return False, 0.0

        if account_state.get('open_positions', 0) >= ScalpingConfig.MAX_OPEN_POSITIONS:
            print(f"❌ Max open positions reached: {account_state['open_positions']}")
            return False, 0.0

        if account_state.get('daily_pnl', 0) <= -ScalpingConfig.MAX_DAILY_LOSS_PERCENT:
            print(f"❌ Daily loss limit hit: {account_state['daily_pnl']:.2f}%")
            return False, 0.0

        if account_state.get('consecutive_losses', 0) >= ScalpingConfig.MAX_CONSECUTIVE_LOSSES:
            print(f"❌ Consecutive loss limit: {account_state['consecutive_losses']}")
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
            print(f"⚠️  Risk Manager parse error: {e}")
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

        # Adjust for spread if enabled
        if ScalpingConfig.REDUCE_SIZE_HIGH_SPREAD and scalp_setup.spread > ScalpingConfig.SPREAD_PENALTY_THRESHOLD:
            base_size *= 0.75

        final_size = min(position_size, base_size)

        print(f"\n🎯 Risk Manager Decision: {'EXECUTE' if execute else 'SKIP'}")
        print(f"   Position Size: {final_size:.2f} lots")
        print(f"   Reasoning: {decision.get('reasoning', 'N/A')}")

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
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4",  # Using GPT-4 for better decision-making
        temperature=0.1,
        api_key=config.OPENAI_API_KEY,
        timeout=config.CLAUDE_TIMEOUT_SECONDS
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
    print("Scalping Agents Module")
    print("=" * 80)
    print("\nAgent Architecture:")
    print("1. Fast Momentum Agent - analyzes 1m momentum")
    print("2. Technical Agent - validates technical structure")
    print("3. Scalp Validator (JUDGE) - final setup approval")
    print("4. Aggressive Risk Agent - maximize opportunity")
    print("5. Conservative Risk Agent - protect capital")
    print("6. Risk Manager (JUDGE) - final position sizing")
    print("\nMaintains 2-agent + judge structure for quality control")
