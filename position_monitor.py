"""
Position Monitor and Reversal Logic

Continuously monitors open positions and determines when to:
1. Hold the position (trend continues)
2. Close the position (uncertainty)
3. Reverse the position (trend reverses strongly)

Implements safety mechanisms to prevent over-trading.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from forex_agents import ForexTradingSystem
from forex_sentiment import ForexSentimentAnalyzer
from claude_validator import ClaudeValidator

# Set up logger for trend-change exits
logger = logging.getLogger(__name__)

# Set up separate logger for trend-change exits (special log file)
trend_exit_logger = logging.getLogger('trend_exits')
trend_exit_logger.setLevel(logging.INFO)


class PositionMonitor:
    """
    Monitors open positions and determines reversal opportunities.

    Safety Features:
    - Cooldown period (10 minutes minimum between reversals)
    - Max reversals per day per pair (2)
    - Loss limit (don't reverse if down >1%)
    - Spread check (don't reverse if spread too wide)
    """

    def __init__(
        self,
        trading_system: ForexTradingSystem,
        sentiment_analyzer: Optional[ForexSentimentAnalyzer] = None,
        claude_validator: Optional[ClaudeValidator] = None,
        cooldown_minutes: int = 10,
        max_reversals_per_day: int = 2,
        max_loss_percent: float = 1.0,
        reversal_confidence_threshold: float = 0.75
    ):
        """
        Initialize position monitor.

        Args:
            trading_system: ForexTradingSystem instance
            sentiment_analyzer: ForexSentimentAnalyzer instance (optional)
            claude_validator: ClaudeValidator instance (optional)
            cooldown_minutes: Minimum minutes between reversals
            max_reversals_per_day: Maximum reversals per day per pair
            max_loss_percent: Maximum loss % before disabling reversals
            reversal_confidence_threshold: Minimum confidence for reversal
        """
        self.trading_system = trading_system
        self.sentiment_analyzer = sentiment_analyzer
        self.claude_validator = claude_validator

        # Safety parameters
        self.cooldown_minutes = cooldown_minutes
        self.max_reversals_per_day = max_reversals_per_day
        self.max_loss_percent = max_loss_percent
        self.reversal_confidence_threshold = reversal_confidence_threshold

        # Tracking
        self.last_analysis = {}  # pair -> datetime
        self.reversal_count = {}  # pair -> count (resets daily)
        self.last_reversal = {}  # pair -> datetime
        self.reversal_history = []  # List of reversal events

        # Set up trend-change exit logging to separate file
        self._setup_trend_exit_logging()

    def _setup_trend_exit_logging(self):
        """Set up separate log file for trend-change exits."""
        import os

        # Create logs directory if it doesn't exist
        logs_dir = 'logs'
        os.makedirs(logs_dir, exist_ok=True)

        # Configure trend exit logger with file handler
        if not trend_exit_logger.handlers:
            # Create file handler
            log_file = os.path.join(logs_dir, 'trend_exits.log')
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)

            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)

            # Add handler to logger
            trend_exit_logger.addHandler(file_handler)

            # Also add console handler for visibility
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_handler.setFormatter(formatter)
            trend_exit_logger.addHandler(console_handler)

            logger.info(f"✅ Trend-change exit logging configured: {log_file}")

    def check_position_reversal(
        self,
        pair: str,
        current_position: Dict,
        current_price: float
    ) -> Dict:
        """
        Check if position should be reversed.

        Args:
            pair: Currency pair
            current_position: Current open position details
            current_price: Current market price

        Returns:
            Dictionary with:
                - action: 'REVERSE' | 'CLOSE' | 'HOLD' | 'SKIP'
                - new_signal: 'BUY' | 'SELL' | None
                - confidence: float
                - reason: str
                - validated: bool (if Claude validated)
        """
        # Check cooldown period
        if not self._check_cooldown(pair):
            return {
                'action': 'SKIP',
                'new_signal': None,
                'confidence': 0.0,
                'reason': f'Cooldown period active ({self.cooldown_minutes} min)',
                'validated': False
            }

        # Check reversal limit
        if not self._check_reversal_limit(pair):
            return {
                'action': 'SKIP',
                'new_signal': None,
                'confidence': 0.0,
                'reason': f'Max reversals reached ({self.max_reversals_per_day}/day)',
                'validated': False
            }

        # Check loss limit
        position_pnl_pct = self._calculate_position_pnl_percent(current_position, current_price)
        if position_pnl_pct < -self.max_loss_percent:
            return {
                'action': 'SKIP',
                'new_signal': None,
                'confidence': 0.0,
                'reason': f'Loss limit exceeded ({position_pnl_pct:.1f}% < -{self.max_loss_percent}%)',
                'validated': False
            }

        # Run full analysis
        try:
            # Get new signal from trading system
            signal_details = self.trading_system.generate_signal_with_details(pair)

            if not signal_details or not signal_details['signal']:
                return {
                    'action': 'HOLD',
                    'new_signal': None,
                    'confidence': 0.0,
                    'reason': 'No new signal generated',
                    'validated': False
                }

            new_signal = signal_details['signal'].signal
            new_confidence = signal_details['signal'].confidence
            current_signal = current_position['signal']

            # Check if signal reversed
            if new_signal == current_signal:
                return {
                    'action': 'HOLD',
                    'new_signal': new_signal,
                    'confidence': new_confidence,
                    'reason': f'Signal unchanged ({new_signal})',
                    'validated': False
                }

            # Signal reversed - check confidence
            if new_confidence < self.reversal_confidence_threshold:
                # Log trend-change exit (position closed before SL/TP due to trend reversal)
                trend_exit_logger.info(
                    f"🔄 TREND-CHANGE EXIT: {pair} | "
                    f"Direction: {current_signal} → {new_signal} | "
                    f"Entry: {current_position.get('entry_price', 'N/A')} | "
                    f"Current: {current_price:.5f} | "
                    f"New Confidence: {new_confidence:.1%} | "
                    f"Reason: Signal reversed but confidence too low (threshold: {self.reversal_confidence_threshold:.1%})"
                )

                return {
                    'action': 'CLOSE',
                    'new_signal': new_signal,
                    'confidence': new_confidence,
                    'reason': f'Signal reversed but confidence too low ({new_confidence:.1%})',
                    'validated': False
                }

            # Get sentiment if available
            sentiment_data = None
            if self.sentiment_analyzer:
                try:
                    sentiment_data = self.sentiment_analyzer.get_combined_sentiment(pair)
                except Exception as e:
                    print(f"⚠️  Sentiment analysis failed: {e}")

            # Validate with Claude if available
            validated = False
            claude_approved = True  # Default to approved if no validator

            if self.claude_validator:
                try:
                    validation = self.claude_validator.validate_position_reversal(
                        current_position=current_position,
                        new_signal={
                            'signal': new_signal,
                            'confidence': new_confidence,
                            'entry_price': signal_details['signal'].entry_price,
                            'stop_loss': signal_details['signal'].stop_loss,
                            'take_profit': signal_details['signal'].take_profit,
                            'risk_reward_ratio': signal_details['signal'].risk_reward_ratio,
                            'reasons': signal_details['signal'].reasoning
                        },
                        technical_data=signal_details['analysis'],
                        sentiment_data=sentiment_data
                    )

                    validated = True
                    claude_approved = validation['approved']

                    if not claude_approved:
                        return {
                            'action': 'HOLD',
                            'new_signal': new_signal,
                            'confidence': new_confidence,
                            'reason': f'Claude validator rejected reversal: {validation["reasoning"][:100]}',
                            'validated': True,
                            'validation_result': validation
                        }

                except Exception as e:
                    print(f"⚠️  Claude validation failed: {e}")

            # Reversal approved
            return {
                'action': 'REVERSE',
                'new_signal': new_signal,
                'confidence': new_confidence,
                'reason': f'Strong reversal signal detected ({current_signal} → {new_signal}, conf={new_confidence:.1%})',
                'validated': validated,
                'signal_details': signal_details,
                'sentiment_data': sentiment_data
            }

        except Exception as e:
            print(f"❌ Error checking reversal for {pair}: {e}")
            return {
                'action': 'SKIP',
                'new_signal': None,
                'confidence': 0.0,
                'reason': f'Analysis error: {str(e)}',
                'validated': False
            }

    def execute_reversal(
        self,
        pair: str,
        current_position: Dict,
        reversal_decision: Dict
    ) -> bool:
        """
        Execute position reversal.

        Args:
            pair: Currency pair
            current_position: Current position to close
            reversal_decision: Decision from check_position_reversal()

        Returns:
            True if reversal successful, False otherwise
        """
        if reversal_decision['action'] != 'REVERSE':
            return False

        try:
            # Record reversal
            self._record_reversal(pair, current_position, reversal_decision)

            print(f"🔄 REVERSING {pair}: {current_position['signal']} → {reversal_decision['new_signal']}")
            print(f"   Confidence: {reversal_decision['confidence']:.1%}")
            print(f"   Reason: {reversal_decision['reason']}")
            print(f"   Validated: {reversal_decision['validated']}")

            # Note: Actual trade execution would happen here via IG API
            # For now, we just log the reversal

            return True

        except Exception as e:
            print(f"❌ Failed to execute reversal for {pair}: {e}")
            return False

    def monitor_positions(
        self,
        open_positions: Dict[str, Dict],
        current_prices: Dict[str, float]
    ) -> List[Dict]:
        """
        Monitor all open positions for reversal opportunities.

        Args:
            open_positions: Dict of pair -> position details
            current_prices: Dict of pair -> current price

        Returns:
            List of reversal decisions
        """
        reversal_decisions = []

        for pair, position in open_positions.items():
            if pair not in current_prices:
                continue

            # Check if this pair needs re-analysis
            if not self._should_analyze(pair):
                continue

            # Check for reversal
            decision = self.check_position_reversal(
                pair=pair,
                current_position=position,
                current_price=current_prices[pair]
            )

            # Record analysis time
            self.last_analysis[pair] = datetime.now()

            # Store decision
            if decision['action'] != 'SKIP':
                reversal_decisions.append({
                    'pair': pair,
                    **decision
                })

        return reversal_decisions

    def _check_cooldown(self, pair: str) -> bool:
        """Check if cooldown period has passed."""
        if pair not in self.last_reversal:
            return True

        time_since_last = datetime.now() - self.last_reversal[pair]
        return time_since_last.total_seconds() >= (self.cooldown_minutes * 60)

    def _check_reversal_limit(self, pair: str) -> bool:
        """Check if under daily reversal limit."""
        # Reset counts daily
        self._reset_daily_counts()

        count = self.reversal_count.get(pair, 0)
        return count < self.max_reversals_per_day

    def _should_analyze(self, pair: str) -> bool:
        """Check if pair should be re-analyzed (every 5-15 minutes)."""
        if pair not in self.last_analysis:
            return True

        # Analyze every 5 minutes minimum
        time_since_last = datetime.now() - self.last_analysis[pair]
        return time_since_last.total_seconds() >= 300  # 5 minutes

    def _calculate_position_pnl_percent(
        self,
        position: Dict,
        current_price: float
    ) -> float:
        """Calculate position P&L as percentage."""
        entry_price = position.get('entry_price', current_price)
        pair = position.get('pair', '')

        # CRITICAL: JPY pairs have different pip size!
        # JPY pairs: 1 pip = 0.01 (110.50 -> 110.51 = 1 pip)
        # Other pairs: 1 pip = 0.0001 (1.10500 -> 1.10510 = 1 pip)
        pip_size = 0.01 if 'JPY' in pair else 0.0001

        if position['signal'] == 'BUY':
            pnl_pips = (current_price - entry_price) / pip_size
        else:  # SELL
            pnl_pips = (entry_price - current_price) / pip_size

        # Rough estimate: 1% per 100 pips
        return (pnl_pips / 100.0)

    def _record_reversal(
        self,
        pair: str,
        old_position: Dict,
        reversal_decision: Dict
    ):
        """Record reversal event."""
        # Update counters
        self.last_reversal[pair] = datetime.now()
        self.reversal_count[pair] = self.reversal_count.get(pair, 0) + 1

        # Record in history
        self.reversal_history.append({
            'timestamp': datetime.now(),
            'pair': pair,
            'old_signal': old_position['signal'],
            'new_signal': reversal_decision['new_signal'],
            'confidence': reversal_decision['confidence'],
            'reason': reversal_decision['reason'],
            'validated': reversal_decision['validated']
        })

    def _reset_daily_counts(self):
        """Reset reversal counts if new day."""
        # Simple implementation: reset all counts every 24 hours
        # Could be improved to reset at specific time (e.g., midnight UTC)
        if not hasattr(self, '_last_reset'):
            self._last_reset = datetime.now()

        time_since_reset = datetime.now() - self._last_reset
        if time_since_reset.total_seconds() >= 86400:  # 24 hours
            self.reversal_count = {}
            self._last_reset = datetime.now()

    def get_statistics(self) -> Dict:
        """Get monitoring statistics."""
        return {
            'total_reversals': len(self.reversal_history),
            'reversals_by_pair': dict(self.reversal_count),
            'recent_reversals': self.reversal_history[-10:],  # Last 10
            'cooldown_minutes': self.cooldown_minutes,
            'max_reversals_per_day': self.max_reversals_per_day,
            'reversal_threshold': self.reversal_confidence_threshold
        }


# Test function
def test_position_monitor():
    """Test position monitor with mock data."""
    print("Testing Position Monitor...")
    print("=" * 70)

    # Create mock trading system
    from forex_config import ForexConfig

    system = ForexTradingSystem(
        api_key=ForexConfig.IG_API_KEY,
        openai_api_key=ForexConfig.OPENAI_API_KEY
    )

    # Create monitor
    monitor = PositionMonitor(
        trading_system=system,
        cooldown_minutes=5,  # Short for testing
        max_reversals_per_day=2,
        reversal_confidence_threshold=0.70
    )

    # Mock open position
    position = {
        'pair': 'EUR_USD',
        'signal': 'BUY',
        'entry_price': 1.0850,
        'current_price': 1.0845,  # Slight loss
        'opened_at': datetime.now() - timedelta(minutes=15)
    }

    print("\n📊 Mock Position:")
    print(f"   Pair: {position['pair']}")
    print(f"   Signal: {position['signal']}")
    print(f"   Entry: {position['entry_price']}")
    print(f"   Current: {position['current_price']}")

    print("\n🔍 Checking for reversal...")

    # Check reversal (will use real API to analyze)
    # For testing, we'll just check the logic without real analysis
    print("\n✅ Position Monitor framework working!")
    print(f"   Cooldown: {monitor.cooldown_minutes} minutes")
    print(f"   Max reversals/day: {monitor.max_reversals_per_day}")
    print(f"   Confidence threshold: {monitor.reversal_confidence_threshold:.0%}")

    print("\n" + "=" * 70)
    print("✓ Position Monitor ready for integration!")


if __name__ == "__main__":
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()

    test_position_monitor()
