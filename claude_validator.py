"""
Claude Validator Agent

Final validation layer using Claude Sonnet 4.5 to review:
- Technical analysis (53 indicators)
- GPT-5 agent recommendations (4 agents)
- Sentiment analysis (news + positioning)
- Risk management (SL/TP calculations)

Provides final go/no-go decision before trade execution.
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime
import anthropic


class ClaudeValidator:
    """
    Final validation agent using Claude Sonnet 4.5.

    Reviews all analysis and provides final trading decision with:
    - Approval/rejection
    - Confidence adjustment
    - Risk warnings
    - Detailed reasoning
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Claude validator.

        Args:
            api_key: Anthropic API key (defaults to environment variable)
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')

        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment variables")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = "claude-sonnet-4-5-20250929"
        self.max_tokens = 4096
        self.temperature = 0.0  # Deterministic for trading decisions

    def validate_signal(
        self,
        signal: Dict,
        technical_data: Dict,
        sentiment_data: Optional[Dict] = None,
        agent_analysis: Optional[Dict] = None
    ) -> Dict:
        """
        Validate trading signal before execution.

        Args:
            signal: Trading signal from DecisionMaker
            technical_data: Full technical analysis (53 indicators)
            sentiment_data: Sentiment analysis from forex_sentiment.py
            agent_analysis: Full agent outputs (price_action, momentum)

        Returns:
            Dictionary with:
                - approved: bool (final go/no-go)
                - confidence_adjustment: float (0.0-1.0)
                - adjusted_confidence: float (original * adjustment)
                - warnings: List[str] (risk warnings)
                - reasoning: str (detailed explanation)
                - risk_level: str (LOW/MEDIUM/HIGH/CRITICAL)
                - recommendation: str (EXECUTE/HOLD/REJECT)
        """
        # Build comprehensive validation prompt
        prompt = self._build_validation_prompt(
            signal=signal,
            technical_data=technical_data,
            sentiment_data=sentiment_data,
            agent_analysis=agent_analysis
        )

        # Call Claude API
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse response
            content = response.content[0].text
            result = self._parse_validation_response(content)

            # Add original signal data for reference
            result['original_signal'] = signal['signal']
            result['original_confidence'] = signal['confidence']
            result['pair'] = technical_data['pair']
            result['timestamp'] = datetime.now().isoformat()

            return result

        except Exception as e:
            print(f"⚠️  Claude Validator Error: {e}")
            # Fallback: reject signal if validation fails
            return {
                'approved': False,
                'confidence_adjustment': 0.0,
                'adjusted_confidence': 0.0,
                'warnings': [f"Validation failed: {str(e)}"],
                'reasoning': f"Unable to validate signal due to error: {str(e)}",
                'risk_level': 'CRITICAL',
                'recommendation': 'REJECT',
                'original_signal': signal.get('signal', 'UNKNOWN'),
                'original_confidence': signal.get('confidence', 0),
                'pair': technical_data.get('pair', 'UNKNOWN'),
                'timestamp': datetime.now().isoformat()
            }

    def _build_validation_prompt(
        self,
        signal: Dict,
        technical_data: Dict,
        sentiment_data: Optional[Dict],
        agent_analysis: Optional[Dict]
    ) -> str:
        """
        Build comprehensive validation prompt for Claude.

        Args:
            signal: Trading signal
            technical_data: Technical analysis
            sentiment_data: Sentiment analysis (optional)
            agent_analysis: Agent outputs (optional)

        Returns:
            Formatted prompt string
        """
        # Extract key data
        pair = technical_data.get('pair', 'UNKNOWN')
        current_price = technical_data.get('current_price', 0.0)
        trend_5m = technical_data.get('trend_primary', 'UNKNOWN')
        trend_1m = technical_data.get('trend_secondary', 'UNKNOWN')
        divergence = technical_data.get('divergence', None)

        # Indicators
        indicators = technical_data.get('indicators', {})
        rsi = indicators.get('rsi_14', 50)
        macd = indicators.get('macd', 0)
        adx = indicators.get('adx', 0)
        atr = indicators.get('atr', 0)

        # Signal data
        signal_direction = signal.get('signal', 'UNKNOWN')
        signal_confidence = signal.get('confidence', 0)
        signal_reasons = signal.get('reasons', [])

        # Entry/SL/TP (if available in signal or technical_data)
        entry = signal.get('entry_price', current_price)
        stop_loss = signal.get('stop_loss', None)
        take_profit = signal.get('take_profit', None)
        risk_reward = signal.get('risk_reward_ratio', None)

        # Agent analysis
        price_action = {}
        momentum = {}
        if agent_analysis:
            price_action = agent_analysis.get('price_action', {})
            momentum = agent_analysis.get('momentum', {})

        # Sentiment
        sentiment_summary = "NOT AVAILABLE"
        if sentiment_data:
            sent_score = sentiment_data.get('sentiment_score', 0)
            sent_conf = sentiment_data.get('confidence', 0)
            sent_headlines = len(sentiment_data.get('news', {}).get('headlines', []))
            sentiment_summary = "Overall Sentiment: " + str(sentiment_data.get('overall_sentiment', 'N/A')) + "\n"
            sentiment_summary += "Sentiment Score: " + "{:.2f}".format(sent_score) + " (range -1.0 to +1.0)\n"
            sentiment_summary += "Confidence: " + "{:.2f}".format(sent_conf) + "\n"
            sentiment_summary += "Recommendation: " + str(sentiment_data.get('recommendation', 'N/A')) + "\n\n"
            sentiment_summary += "News Headlines: " + str(sent_headlines) + " articles analyzed\n"
            sentiment_summary += "Trader Positioning: " + str(sentiment_data.get('positioning', {}).get('sentiment', 'N/A')) + "\n"
            sentiment_summary += "Contrarian Signal: " + str(sentiment_data.get('positioning', {}).get('contrarian_signal', 'None'))

        # Format display strings
        sl_display = "{:.5f}".format(stop_loss) if stop_loss else 'N/A'
        tp_display = "{:.5f}".format(take_profit) if take_profit else 'N/A'
        rr_display = "{:.2f}:1".format(risk_reward) if risk_reward else 'N/A'

        # Format signal reasons
        reasons_formatted = self._format_list(signal_reasons)

        # Format price action and momentum for display
        price_action_str = json.dumps(price_action, indent=2) if price_action else 'Not available'
        momentum_str = json.dumps(momentum, indent=2) if momentum else 'Not available'

        # Format support/resistance
        support_display = str(technical_data.get('nearest_support', 'N/A'))
        resistance_display = str(technical_data.get('nearest_resistance', 'N/A'))
        divergence_display = str(divergence) if divergence else 'None'

        # Build prompt using string concatenation to avoid format specifier issues
        prompt = "You are an Elite Trading Risk Validator reviewing a forex trade proposal for " + pair + ".\n\n"
        prompt += "Your role is to provide FINAL VALIDATION before trade execution. You have access to:\n"
        prompt += "1. Complete technical analysis (53 indicators)\n"
        prompt += "2. GPT agent recommendations (Price Action + Momentum)\n"
        prompt += "3. Market sentiment analysis (news + trader positioning)\n"
        prompt += "4. Risk management calculations\n\n"
        prompt += "CRITICAL: Be conservative. Only approve high-probability setups with strong confirmations.\n\n"

        prompt += "═══════════════════════════════════════════════════════════════════\n"
        prompt += "📊 PROPOSED TRADE SIGNAL\n"
        prompt += "═══════════════════════════════════════════════════════════════════\n\n"
        prompt += "Pair: " + pair + "\n"
        prompt += "Direction: " + signal_direction + "\n"
        prompt += "Confidence: " + "{:.1%}".format(signal_confidence) + "\n"
        prompt += "Entry Price: " + "{:.5f}".format(entry) + "\n"
        prompt += "Stop Loss: " + sl_display + "\n"
        prompt += "Take Profit: " + tp_display + "\n"
        prompt += "Risk/Reward: " + rr_display + "\n\n"
        prompt += "Signal Reasons:\n" + reasons_formatted + "\n\n"

        prompt += "═══════════════════════════════════════════════════════════════════\n"
        prompt += "📈 TECHNICAL ANALYSIS (53 Indicators)\n"
        prompt += "═══════════════════════════════════════════════════════════════════\n\n"
        prompt += "Current Price: " + "{:.5f}".format(current_price) + "\n"
        prompt += "5m Trend: " + trend_5m + "\n"
        prompt += "1m Trend: " + trend_1m + "\n"
        prompt += "Divergence: " + divergence_display + "\n\n"
        prompt += "Key Indicators:\n"
        prompt += "- RSI (14): " + "{:.1f}".format(rsi) + " (Overbought above 70, Oversold below 30 - Note: Extremes with divergence are STRONG signals)\n"
        prompt += "- MACD: " + "{:.5f}".format(macd) + "\n"
        prompt += "- ADX (Trend Strength): " + "{:.1f}".format(adx) + " (15-25 = Moderate, 25-30 = Strong, >30 = Very Strong - Accept 15+ with appropriate position sizing)\n"
        prompt += "- ATR (Volatility): " + "{:.5f}".format(atr) + "\n\n"
        prompt += "Support: " + support_display + "\n"
        prompt += "Resistance: " + resistance_display + "\n\n"

        prompt += "═══════════════════════════════════════════════════════════════════\n"
        prompt += "🤖 GPT AGENT ANALYSIS\n"
        prompt += "═══════════════════════════════════════════════════════════════════\n\n"
        prompt += "PRICE ACTION AGENT:\n" + price_action_str + "\n\n"
        prompt += "MOMENTUM AGENT:\n" + momentum_str + "\n\n"

        prompt += "═══════════════════════════════════════════════════════════════════\n"
        prompt += "📰 MARKET SENTIMENT\n"
        prompt += "═══════════════════════════════════════════════════════════════════\n\n"
        prompt += sentiment_summary + "\n\n"

        prompt += "═══════════════════════════════════════════════════════════════════\n"
        prompt += "✅ VALIDATION TASK - HEDGE FUND APPROACH\n"
        prompt += "═══════════════════════════════════════════════════════════════════\n\n"
        prompt += "Analyze ALL data above using a TIERED POSITION SIZING approach:\n\n"
        prompt += "**TIER 1 - FULL SIZE (100% position):**\n"
        prompt += "- ADX > 25 (strong trend)\n"
        prompt += "- Confidence > 75%\n"
        prompt += "- 5m and 1m timeframes perfectly aligned\n"
        prompt += "- Multiple confirmations (RSI, MACD, divergence)\n"
        prompt += "- Risk/reward > 2:1\n\n"
        prompt += "**TIER 2 - HALF SIZE (50% position):**\n"
        prompt += "- ADX 15-25 (moderate trend) - THIS IS ACCEPTABLE\n"
        prompt += "- Confidence 60-75% - THIS IS ACCEPTABLE\n"
        prompt += "- 5m timeframe aligns with signal (1m may differ) - THIS IS ACCEPTABLE\n"
        prompt += "- At least 2-3 confirmations\n"
        prompt += "- Risk/reward > 1.5:1\n\n"
        prompt += "**TIER 3 - QUARTER SIZE (25% position):**\n"
        prompt += "- ADX 15-20 (weak trend)\n"
        prompt += "- Confidence 60-70%\n"
        prompt += "- Only 5m timeframe confirms\n"
        prompt += "- RSI extreme with divergence (STRONG reversal signal)\n"
        prompt += "- Risk/reward > 1.5:1\n\n"
        prompt += "**REJECT ONLY IF:**\n"
        prompt += "- ADX < 15 (no trend, ranging market)\n"
        prompt += "- Confidence < 60% (insufficient edge)\n"
        prompt += "- Both 5m and 1m contradict signal direction\n"
        prompt += "- Risk/reward < 1.5:1\n"
        prompt += "- Major news event imminent\n\n"
        prompt += "**CRITICAL INSIGHTS FROM HEDGE FUNDS:**\n"
        prompt += "1. **Timeframe Conflicts**: 60-70% of the time, 1m and 5m disagree - this is NORMAL. Trust 5m (primary trend).\n"
        prompt += "2. **ADX 15-25**: Moderate trends are tradeable with smaller positions. Most hedge funds trade these.\n"
        prompt += "3. **RSI Extremes + Divergence**: Oversold/overbought with divergence is a HIGH-PROBABILITY reversal signal, not a rejection reason.\n"
        prompt += "4. **60% Confidence**: A 60% win rate with proper risk management is a statistical edge. Don't require 75%+.\n"
        prompt += "5. **Position Sizing**: Scale position size with setup quality, not binary yes/no.\n\n"
        prompt += "**YOUR VALIDATION MUST INCLUDE:**\n"
        prompt += "- Which tier does this setup qualify for? (TIER_1/TIER_2/TIER_3/REJECT)\n"
        prompt += "- Recommended position size (100%/50%/25%/0%)\n"
        prompt += "- If rejecting, explicitly state which threshold failed\n\n"
        prompt += "Respond ONLY in JSON format:\n"
        prompt += "{\n"
        prompt += '    "approved": true/false,\n'
        prompt += '    "confidence_adjustment": 0.0-1.0,\n'
        prompt += '    "warnings": ["warning1", "warning2"],\n'
        prompt += '    "reasoning": "detailed explanation of tier classification and validation decision",\n'
        prompt += '    "risk_level": "LOW/MEDIUM/HIGH/CRITICAL",\n'
        prompt += '    "recommendation": "EXECUTE/HOLD/REJECT",\n'
        prompt += '    "position_tier": "TIER_1/TIER_2/TIER_3/REJECT",\n'
        prompt += '    "position_size_percent": 100/50/25/0,\n'
        prompt += '    "key_concerns": ["concern1", "concern2"] or [],\n'
        prompt += '    "key_confirmations": ["confirmation1", "confirmation2"] or []\n'
        prompt += "}\n\n"
        prompt += "Be thorough, balanced, and professional. Use tiered position sizing to capture more opportunities."

        return prompt

    def _format_list(self, items: List[str]) -> str:
        """Format list items with bullets."""
        if not items:
            return "  (No reasons provided)"
        return "\n".join([f"  • {item}" for item in items])

    def _parse_validation_response(self, content: str) -> Dict:
        """
        Parse Claude's validation response.

        Args:
            content: Raw response text from Claude

        Returns:
            Dictionary with validation results
        """
        try:
            # Clean markdown code fences if present
            content = content.strip()
            if content.startswith('```'):
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                content = '\n'.join(lines).strip()

            # Parse JSON
            result = json.loads(content)

            # Validate required fields
            required_fields = [
                'approved', 'confidence_adjustment', 'warnings',
                'reasoning', 'risk_level', 'recommendation'
            ]
            for field in required_fields:
                if field not in result:
                    raise ValueError(f"Missing required field: {field}")

            # Calculate adjusted confidence
            result['adjusted_confidence'] = result['confidence_adjustment']

            # Ensure warnings is a list
            if not isinstance(result['warnings'], list):
                result['warnings'] = [str(result['warnings'])]

            # Add optional fields with defaults
            result['key_concerns'] = result.get('key_concerns', [])
            result['key_confirmations'] = result.get('key_confirmations', [])

            # Add position sizing fields with defaults
            result['position_tier'] = result.get('position_tier', 'REJECT')
            result['position_size_percent'] = result.get('position_size_percent', 0)

            return result

        except json.JSONDecodeError as e:
            print(f"⚠️  Failed to parse Claude validation response: {e}")
            print(f"   Raw response: {content[:200]}...")
            # Return rejection if parsing fails
            return {
                'approved': False,
                'confidence_adjustment': 0.0,
                'adjusted_confidence': 0.0,
                'warnings': ['Failed to parse validation response'],
                'reasoning': f'JSON parsing error: {str(e)}',
                'risk_level': 'CRITICAL',
                'recommendation': 'REJECT',
                'key_concerns': ['Validation system error'],
                'key_confirmations': []
            }
        except Exception as e:
            print(f"⚠️  Error processing validation response: {e}")
            return {
                'approved': False,
                'confidence_adjustment': 0.0,
                'adjusted_confidence': 0.0,
                'warnings': [f'Processing error: {str(e)}'],
                'reasoning': f'Unexpected error: {str(e)}',
                'risk_level': 'CRITICAL',
                'recommendation': 'REJECT',
                'key_concerns': ['Validation processing error'],
                'key_confirmations': []
            }

    def validate_position_reversal(
        self,
        current_position: Dict,
        new_signal: Dict,
        technical_data: Dict,
        sentiment_data: Optional[Dict] = None
    ) -> Dict:
        """
        Validate position reversal decision.

        This is called when monitoring detects a signal reversal on an open position.
        Provides extra validation since reversals are riskier.

        Args:
            current_position: Open position details
            new_signal: Proposed reversal signal
            technical_data: Current technical analysis
            sentiment_data: Current sentiment (optional)

        Returns:
            Validation result with reversal-specific assessment
        """
        # Build reversal-specific prompt
        prompt = self._build_reversal_prompt(
            current_position=current_position,
            new_signal=new_signal,
            technical_data=technical_data,
            sentiment_data=sentiment_data
        )

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            content = response.content[0].text
            result = self._parse_validation_response(content)

            # Add reversal metadata
            result['is_reversal'] = True
            result['current_position_signal'] = current_position.get('signal', 'UNKNOWN')
            result['new_signal'] = new_signal.get('signal', 'UNKNOWN')
            result['pair'] = technical_data['pair']
            result['timestamp'] = datetime.now().isoformat()

            return result

        except Exception as e:
            print(f"⚠️  Claude Reversal Validation Error: {e}")
            return {
                'approved': False,
                'confidence_adjustment': 0.0,
                'adjusted_confidence': 0.0,
                'warnings': [f"Reversal validation failed: {str(e)}"],
                'reasoning': f"Unable to validate reversal: {str(e)}",
                'risk_level': 'CRITICAL',
                'recommendation': 'REJECT',
                'is_reversal': True,
                'current_position_signal': current_position.get('signal', 'UNKNOWN'),
                'new_signal': new_signal.get('signal', 'UNKNOWN'),
                'pair': technical_data.get('pair', 'UNKNOWN'),
                'timestamp': datetime.now().isoformat()
            }

    def _build_reversal_prompt(
        self,
        current_position: Dict,
        new_signal: Dict,
        technical_data: Dict,
        sentiment_data: Optional[Dict]
    ) -> str:
        """
        Build validation prompt for position reversal.

        Args:
            current_position: Open position
            new_signal: Reversal signal
            technical_data: Technical analysis
            sentiment_data: Sentiment (optional)

        Returns:
            Formatted prompt
        """
        pair = technical_data.get('pair', 'UNKNOWN')
        current_signal = current_position.get('signal', 'UNKNOWN')
        current_pnl = current_position.get('pnl', 0.0)

        new_signal_direction = new_signal.get('signal', 'UNKNOWN')
        new_confidence = new_signal.get('confidence', 0.0)

        # Format technical and sentiment data
        technical_json = json.dumps(technical_data, indent=2, default=str)
        sentiment_json = json.dumps(sentiment_data, indent=2, default=str) if sentiment_data else "Not available"

        # Build prompt using string concatenation
        prompt = "You are validating a POSITION REVERSAL for " + pair + ".\n\n"
        prompt += "⚠️  CRITICAL: Reversals are high-risk decisions. Be EXTRA conservative.\n\n"

        prompt += "═══════════════════════════════════════════════════════════════════\n"
        prompt += "🔄 REVERSAL PROPOSAL\n"
        prompt += "═══════════════════════════════════════════════════════════════════\n\n"
        prompt += "Current Position: " + current_signal + "\n"
        prompt += "Current P&L: $" + "{:.2f}".format(current_pnl) + "\n"
        prompt += "Proposed Reversal: " + new_signal_direction + "\n"
        prompt += "New Signal Confidence: " + "{:.1%}".format(new_confidence) + "\n\n"

        prompt += "═══════════════════════════════════════════════════════════════════\n"
        prompt += "📊 TECHNICAL DATA\n"
        prompt += "═══════════════════════════════════════════════════════════════════\n\n"
        prompt += technical_json + "\n\n"

        prompt += "═══════════════════════════════════════════════════════════════════\n"
        prompt += "📰 SENTIMENT DATA\n"
        prompt += "═══════════════════════════════════════════════════════════════════\n\n"
        prompt += sentiment_json + "\n\n"

        prompt += "═══════════════════════════════════════════════════════════════════\n"
        prompt += "✅ REVERSAL VALIDATION CRITERIA\n"
        prompt += "═══════════════════════════════════════════════════════════════════\n\n"
        prompt += "ONLY APPROVE if ALL criteria are met:\n\n"
        prompt += "1. **Strong Reversal Evidence**:\n"
        prompt += "   - Multiple indicators confirming reversal\n"
        prompt += "   - New confidence above 75%\n"
        prompt += "   - Clear trend change across timeframes\n\n"
        prompt += "2. **Risk Management**:\n"
        prompt += "   - Not reversing in a loss above 1% of account\n"
        prompt += "   - Not within 10 minutes of opening position\n"
        prompt += "   - No upcoming economic events\n\n"
        prompt += "3. **Sentiment Shift**:\n"
        prompt += "   - Sentiment supports new direction\n"
        prompt += "   - News or positioning changed dramatically\n\n"
        prompt += "4. **Technical Confirmation**:\n"
        prompt += "   - Key support/resistance broken\n"
        prompt += "   - Multiple oscillators aligned\n"
        prompt += "   - Volume confirms reversal\n\n"
        prompt += "**CRITICAL**: If ANY doubt, REJECT the reversal. It's safer to hold or close.\n\n"
        prompt += "Respond ONLY in JSON format:\n"
        prompt += "{\n"
        prompt += '    "approved": true/false,\n'
        prompt += '    "confidence_adjustment": 0.0-1.0,\n'
        prompt += '    "warnings": ["warning1", "warning2"],\n'
        prompt += '    "reasoning": "detailed explanation of reversal decision",\n'
        prompt += '    "risk_level": "LOW/MEDIUM/HIGH/CRITICAL",\n'
        prompt += '    "recommendation": "EXECUTE/HOLD/REJECT",\n'
        prompt += '    "reversal_strength": "WEAK/MODERATE/STRONG",\n'
        prompt += '    "key_concerns": ["concern1"],\n'
        prompt += '    "key_confirmations": ["confirmation1"]\n'
        prompt += "}"

        return prompt


# Test function
def test_claude_validator():
    """Test Claude validator with sample data."""
    print("Testing Claude Validator...")
    print("=" * 70)

    # Create validator
    validator = ClaudeValidator()

    # Sample signal data
    signal = {
        'signal': 'BUY',
        'confidence': 0.75,
        'reasons': [
            'Strong bullish momentum (ADX 32, RSI 62)',
            'Price action breakout confirmed',
            'Multiple timeframes aligned'
        ],
        'entry_price': 1.0850,
        'stop_loss': 1.0820,
        'take_profit': 1.0910,
        'risk_reward_ratio': 2.0
    }

    # Sample technical data
    technical_data = {
        'pair': 'EUR_USD',
        'current_price': 1.0850,
        'trend_primary': 'BULLISH',
        'trend_secondary': 'BULLISH',
        'divergence': None,
        'indicators': {
            'rsi_14': 62.5,
            'macd': 0.0012,
            'adx': 32.0,
            'atr': 0.0015
        },
        'nearest_support': 1.0810,
        'nearest_resistance': 1.0920
    }

    # Sample sentiment
    sentiment_data = {
        'overall_sentiment': 'bullish',
        'sentiment_score': 0.4,
        'confidence': 0.7,
        'recommendation': 'moderate_signal',
        'news': {
            'headlines': ['EUR gains on ECB comments', 'USD weakens']
        },
        'positioning': {
            'sentiment': 'neutral',
            'contrarian_signal': None
        }
    }

    # Sample agent analysis
    agent_analysis = {
        'price_action': {
            'has_setup': True,
            'setup_type': 'BULLISH_BREAKOUT',
            'direction': 'BUY',
            'confidence': 75
        },
        'momentum': {
            'momentum_strong': True,
            'momentum_direction': 'UP',
            'timeframes_aligned': True,
            'confidence': 78
        }
    }

    # Validate
    print("\n🔍 Validating sample BUY signal for EUR/USD...")
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
    print(f"Approved: {result['approved']}")
    print(f"Confidence Adjustment: {result['confidence_adjustment']:.2f}")
    print(f"Adjusted Confidence: {result['adjusted_confidence']:.1%}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Recommendation: {result['recommendation']}")
    print(f"Position Tier: {result.get('position_tier', 'N/A')}")
    print(f"Position Size: {result.get('position_size_percent', 0)}%")

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
    print("✓ Claude Validator working!")


if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    test_claude_validator()
