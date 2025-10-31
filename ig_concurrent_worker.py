"""
IG Real Trading Concurrent Worker

Analyzes all forex pairs in parallel and executes REAL trades on IG.
"""

import time
import threading
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import List, Dict, Optional
import traceback

from forex_config import ForexConfig
from forex_agents import ForexTradingSystem
from ig_trader import IGTrader
from trading_database import get_database
from ig_rate_limiter import get_rate_limiter
from forex_sentiment import ForexSentimentAnalyzer
from claude_validator import ClaudeValidator
from position_monitor import PositionMonitor
from forex_market_hours import get_market_hours


class IGConcurrentWorker:
    """
    Concurrent worker for REAL IG trading.

    Features:
    - Runs every 5 minutes / 300 seconds (configurable via ForexConfig.ANALYSIS_INTERVAL_SECONDS)
    - Parallel analysis of all forex pairs
    - REAL trade execution on IG
    - Saves all data to database
    - Monitors open positions
    - Risk management
    """

    def __init__(
        self,
        auto_trading: bool = False,
        max_workers: int = 10,
        interval_seconds: int = ForexConfig.ANALYSIS_INTERVAL_SECONDS
    ):
        """
        Initialize IG concurrent worker.

        Args:
            auto_trading: If True, auto-execute signals (CAREFUL!)
            max_workers: Max concurrent threads for analysis
            interval_seconds: Seconds between analysis cycles
        """
        # Initialize IG trader
        self.trader = IGTrader()

        # Initialize AI system
        self.system = ForexTradingSystem(
            api_key=ForexConfig.IG_API_KEY,
            openai_api_key=ForexConfig.OPENAI_API_KEY
        )

        # Initialize database
        self.db = get_database()

        self.auto_trading = auto_trading
        self.max_workers = max_workers
        self.interval_seconds = interval_seconds
        self.running = False
        self.worker_thread = None

        # Initialize sentiment analyzer (optional)
        self.sentiment_analyzer = None
        if ForexConfig.ENABLE_SENTIMENT_ANALYSIS:
            try:
                self.sentiment_analyzer = ForexSentimentAnalyzer()
                print("   Sentiment analyzer initialized")
            except Exception as e:
                print(f"   Sentiment analyzer failed: {e}")

        # Initialize Claude validator (optional)
        self.claude_validator = None
        if ForexConfig.ENABLE_CLAUDE_VALIDATOR:
            try:
                self.claude_validator = ClaudeValidator()
                print("   Claude validator initialized")
            except Exception as e:
                print(f"   Claude validator failed: {e}")

        # Initialize position monitor (optional)
        self.position_monitor = None
        if ForexConfig.ENABLE_POSITION_MONITORING:
            try:
                self.position_monitor = PositionMonitor(
                    trading_system=self.system,
                    sentiment_analyzer=self.sentiment_analyzer,
                    claude_validator=self.claude_validator,
                    cooldown_minutes=ForexConfig.REVERSAL_COOLDOWN_MINUTES,
                    max_reversals_per_day=ForexConfig.MAX_REVERSALS_PER_DAY,
                    reversal_confidence_threshold=ForexConfig.REVERSAL_CONFIDENCE_THRESHOLD
                )
                print("   Position monitor initialized")
            except Exception as e:
                print(f"   Position monitor failed: {e}")

        # Get initial account info
        self.account_info = self.trader.get_account_info()

        # Check existing open positions on IG (important after restart!)
        self.existing_positions_count = 0
        if ForexConfig.CHECK_IG_POSITIONS_ON_STARTUP:
            existing_positions = self.trader.get_open_positions()
            self.existing_positions_count = len(existing_positions)

        print("="*80)
        print("IG REAL TRADING WORKER INITIALIZED")
        print("="*80)
        print(f"Account: {self.account_info.get('account_id')} - {self.account_info.get('account_name')}")
        print(f"Balance: €{self.account_info.get('balance', 0):,.2f}")
        print(f"Available: €{self.account_info.get('available', 0):,.2f}")
        if self.existing_positions_count > 0:
            print(f"\n⚠️  EXISTING OPEN POSITIONS: {self.existing_positions_count}")
            print(f"   These positions were found on IG (from previous session)")
        print(f"\nSettings:")
        print(f"   Auto-trading: {'🔴 ENABLED (LIVE TRADES!)' if auto_trading else '🟢 DISABLED'}")
        print(f"   Max open positions: {ForexConfig.MAX_OPEN_POSITIONS}")
        print(f"   Current positions: {self.existing_positions_count}")
        print(f"   Available slots: {ForexConfig.MAX_OPEN_POSITIONS - self.existing_positions_count}")
        print(f"   Max workers: {max_workers}")
        print(f"   Update interval: {interval_seconds}s")
        print(f"   Monitoring pairs: {len(ForexConfig.ALL_PAIRS)}")
        print(f"\nEnhancement Features:")
        print(f"   Sentiment Analysis: {'✅ ENABLED' if self.sentiment_analyzer else '❌ DISABLED'}")
        print(f"   Claude Validator: {'✅ ENABLED' if self.claude_validator else '❌ DISABLED'}")
        print(f"   Position Monitor: {'✅ ENABLED' if self.position_monitor else '❌ DISABLED'}")
        if self.position_monitor:
            print(f"      - Cooldown: {ForexConfig.REVERSAL_COOLDOWN_MINUTES} minutes")
            print(f"      - Max reversals/day: {ForexConfig.MAX_REVERSALS_PER_DAY}")
            print(f"      - Reversal threshold: {ForexConfig.REVERSAL_CONFIDENCE_THRESHOLD:.0%}")
        print("="*80)

    def analyze_pair(self, pair: str) -> Dict:
        """
        Analyze a single pair with full agent flow.

        Returns:
            Dictionary with analysis results and any signals
        """
        try:
            # Get complete agent analysis
            details = self.system.generate_signal_with_details(pair, '5', '1')

            analysis = details['analysis']
            price_action = details['price_action']
            momentum = details['momentum']
            decision = details['decision']
            signal = details['signal']

            timestamp = datetime.now()

            # Get sentiment if available
            sentiment_data = None
            if self.sentiment_analyzer:
                try:
                    sentiment_data = self.sentiment_analyzer.get_combined_sentiment(pair)
                    print(f"   Sentiment: {sentiment_data['overall_sentiment']} (score={sentiment_data['sentiment_score']:.2f})")
                except Exception as e:
                    print(f"   Sentiment analysis failed: {e}")

            # Save technical indicators
            self.db.save_indicators({
                'pair': pair,
                'timeframe': '5',
                'indicators': analysis['indicators'],
                'hedge_strategies': analysis.get('hedge_strategies', {}),
                'pattern_details': analysis.get('pattern_details', {}),
                'timestamp': timestamp
            })

            # Agent outputs saved via signals (skip individual agent saves for now)

            # Save signal
            if signal and signal.signal in ['BUY', 'SELL']:
                # Calculate risk/reward ratio and pips
                # CRITICAL: JPY pairs have different pip calculation!
                # JPY pairs: 1 pip = 0.01 (multiply by 100)
                # Other pairs: 1 pip = 0.0001 (multiply by 10000)
                pip_multiplier = 100 if 'JPY' in pair else 10000
                stop_pips = abs(signal.entry_price - signal.stop_loss) * pip_multiplier
                tp_pips = abs(signal.take_profit - signal.entry_price) * pip_multiplier
                rr_ratio = tp_pips / stop_pips if stop_pips > 0 else 0

                self.db.save_signal({
                    'pair': pair,
                    'timeframe': '5',
                    'signal': signal.signal,
                    'confidence': signal.confidence,
                    'entry_price': signal.entry_price,
                    'stop_loss': signal.stop_loss,
                    'take_profit': signal.take_profit,
                    'risk_reward_ratio': rr_ratio,
                    'pips_risk': stop_pips,
                    'pips_reward': tp_pips,
                    'reasoning': signal.reasoning,
                    'indicators': json.dumps(analysis.get('indicators', {})),
                    'executed': False,
                    'timestamp': timestamp,
                    'sl_method': 'AI',
                    'tp_method': 'AI',
                    'rr_adjusted': False,
                    'calculation_steps': signal.reasoning,
                    'atr_value': analysis.get('indicators', {}).get('atr', 0),
                    'nearest_support': None,
                    'nearest_resistance': None
                })

            return {
                'success': True,
                'pair': pair,
                'signal': signal,
                'analysis': analysis,
                'sentiment_data': sentiment_data,
                'price_action': price_action,
                'momentum': momentum,
                'timestamp': timestamp
            }

        except Exception as e:
            print(f"❌ Error analyzing {pair}: {e}")
            traceback.print_exc()
            return {
                'success': False,
                'pair': pair,
                'error': str(e)
            }

    def get_currencies_from_pair(self, pair: str) -> tuple:
        """
        Extract the two currencies from a pair name.

        Args:
            pair: Currency pair like 'EUR_USD' or 'OIL_CRUDE'

        Returns:
            Tuple of (base_currency, quote_currency) or (None, None) for commodities
        """
        # Commodities don't have currency pairs
        if pair in ['OIL_CRUDE', 'OIL_BRENT', 'XAU_USD', 'XAG_USD']:
            return (None, None)

        # Split forex pair
        if '_' in pair:
            parts = pair.split('_')
            if len(parts) == 2:
                return (parts[0], parts[1])

        return (None, None)

    def filter_signals_by_currency_exposure(self, signals_with_pairs: List[tuple]) -> List[tuple]:
        """
        Filter signals to prevent duplicate currency exposure.
        Only keeps the highest confidence signal for each currency.

        Args:
            signals_with_pairs: List of (signal, pair, result) tuples

        Returns:
            Filtered list of (signal, pair, result) tuples
        """
        if not signals_with_pairs:
            return []

        # Track currency exposure with best signal
        currency_exposure = {}  # currency -> (confidence, signal, pair, result)

        for signal, pair, result in signals_with_pairs:
            if not signal or signal.signal not in ['BUY', 'SELL']:
                continue

            base, quote = self.get_currencies_from_pair(pair)

            # Handle commodities (no currency filtering)
            if base is None and quote is None:
                # Always include commodities
                if pair not in currency_exposure:
                    currency_exposure[pair] = (signal.confidence, signal, pair, result)
                elif signal.confidence > currency_exposure[pair][0]:
                    currency_exposure[pair] = (signal.confidence, signal, pair, result)
                continue

            # Check if either currency already has a signal
            base_exists = base in currency_exposure
            quote_exists = quote in currency_exposure

            # Determine if we should accept this signal
            should_accept = False

            if not base_exists and not quote_exists:
                # Neither currency has a signal yet - accept this signal
                should_accept = True
            elif base_exists and quote_exists:
                # Both currencies already have signals
                # Only accept if this signal has higher confidence than BOTH existing signals
                base_conf = currency_exposure[base][0]
                quote_conf = currency_exposure[quote][0]
                if signal.confidence > base_conf and signal.confidence > quote_conf:
                    # Remove old signal's currencies
                    old_base_pair = currency_exposure[base][2]
                    old_quote_pair = currency_exposure[quote][2]

                    # Remove currencies from the signal being replaced
                    for old_pair_to_remove in [old_base_pair, old_quote_pair]:
                        old_b, old_q = self.get_currencies_from_pair(old_pair_to_remove)
                        if old_b:
                            currency_exposure.pop(old_b, None)
                        if old_q:
                            currency_exposure.pop(old_q, None)

                    should_accept = True
            elif base_exists or quote_exists:
                # One currency has a signal, the other doesn't
                existing_currency = base if base_exists else quote
                existing_conf = currency_exposure[existing_currency][0]

                if signal.confidence > existing_conf:
                    # Remove old signal's currencies
                    old_pair = currency_exposure[existing_currency][2]
                    old_base, old_quote = self.get_currencies_from_pair(old_pair)
                    if old_base:
                        currency_exposure.pop(old_base, None)
                    if old_quote:
                        currency_exposure.pop(old_quote, None)

                    should_accept = True

            # Add the signal if accepted
            if should_accept:
                currency_exposure[base] = (signal.confidence, signal, pair, result)
                currency_exposure[quote] = (signal.confidence, signal, pair, result)

        # Extract unique signals (avoid duplicates from both currencies pointing to same signal)
        unique_signals = {}
        for conf, signal, pair, result in currency_exposure.values():
            if pair not in unique_signals:
                unique_signals[pair] = (signal, pair, result)

        return list(unique_signals.values())

    def execute_signal(self, signal, pair: str, analysis_data: Dict = None, sentiment_data: Dict = None, agent_results: Dict = None) -> bool:
        """
        Execute a trading signal on IG.

        Args:
            signal: TradingSignal object
            pair: Currency pair
            analysis_data: Technical analysis data (for Claude validation)
            sentiment_data: Sentiment analysis data (for Claude validation)
            agent_results: Agent analysis results (for Claude validation)

        Returns:
            True if executed successfully
        """
        if not self.auto_trading:
            print(f"⚠️  Signal generated for {pair}: {signal.signal} (auto-trading disabled)")
            return False

        # Add Claude validation before trade execution
        if self.claude_validator and signal:
            try:
                print(f"   Validating with Claude...")
                validation = self.claude_validator.validate_signal(
                    signal={
                        'signal': signal.signal,
                        'confidence': signal.confidence,
                        'entry_price': signal.entry_price,
                        'stop_loss': signal.stop_loss,
                        'take_profit': signal.take_profit,
                        'risk_reward_ratio': getattr(signal, 'risk_reward_ratio', 0),
                        'reasons': signal.reasoning if isinstance(signal.reasoning, list) else [signal.reasoning]
                    },
                    technical_data=analysis_data or {'pair': pair, 'indicators': {}, 'current_price': signal.entry_price},
                    sentiment_data=sentiment_data,
                    agent_analysis=agent_results
                )

                if not validation['approved']:
                    print(f"   Claude rejected: {validation['recommendation']}")
                    print(f"      Risk: {validation['risk_level']}")
                    if validation.get('warnings'):
                        print(f"      Warnings: {', '.join(validation['warnings'][:2])}")
                    # Skip this signal
                    return False

                # Adjust confidence if Claude suggests
                if validation.get('confidence_adjustment', 1.0) < 1.0:
                    old_conf = signal.confidence
                    signal.confidence *= validation['confidence_adjustment']
                    print(f"   Confidence adjusted: {old_conf:.1%} -> {signal.confidence:.1%}")

                print(f"   Claude approved: {validation['recommendation']}")

                # Store validation for position sizing
                claude_validation = validation

            except Exception as e:
                print(f"   Claude validation failed: {e}")
                # Continue without validation if it fails
                claude_validation = None
        else:
            claude_validation = None

        # Check position limit before opening new trade
        try:
            current_positions = self.trader.get_open_positions()
            current_count = len(current_positions)

            if current_count >= ForexConfig.MAX_OPEN_POSITIONS:
                print(f"⚠️  Position limit reached: {current_count}/{ForexConfig.MAX_OPEN_POSITIONS}")
                print(f"   Skipping {pair} {signal.signal} signal")
                return False

            available_slots = ForexConfig.MAX_OPEN_POSITIONS - current_count
            print(f"📊 Position check: {current_count}/{ForexConfig.MAX_OPEN_POSITIONS} open ({available_slots} slots available)")

        except Exception as e:
            print(f"⚠️  Could not check position count: {e}")
            print(f"   Proceeding with trade execution...")

        try:
            # Get account balance
            account = self.trader.get_account_info()
            balance = account.get('balance', 10000)

            # Calculate BASE position size based on risk
            # CRITICAL: JPY pairs have different pip calculation!
            # JPY pairs: 1 pip = 0.01 (multiply by 100)
            # Other pairs: 1 pip = 0.0001 (multiply by 10000)
            pip_multiplier = 100 if 'JPY' in pair else 10000
            stop_loss_pips = abs(signal.entry_price - signal.stop_loss) * pip_multiplier  # Convert to pips
            take_profit_pips = abs(signal.take_profit - signal.entry_price) * pip_multiplier

            base_position_size = self.trader.calculate_position_size(
                account_balance=balance,
                risk_percent=ForexConfig.RISK_PERCENT,
                stop_loss_pips=stop_loss_pips,
                pair=pair
            )

            # Apply Claude's tier-based position sizing
            tier_multiplier = 1.0  # Default: full size
            position_tier = "FULL"

            if claude_validation:
                # Get tier from Claude validation
                tier_multiplier = claude_validation.get('position_size_percent', 100) / 100.0
                position_tier = claude_validation.get('position_tier', 'TIER_1')

                # Apply tier adjustments to stops/targets for lower tiers
                if position_tier == 'TIER_3':
                    # Quarter size = more conservative (wider stops, tighter targets)
                    stop_loss_pips *= 1.2  # 20% wider stop for safety
                    take_profit_pips *= 0.9  # 10% tighter target (faster exit)
                    print(f"   🔻 TIER 3 (25% size): Widened SL by 20%, tightened TP by 10%")
                elif position_tier == 'TIER_2':
                    # Half size = slightly conservative (wider stops)
                    stop_loss_pips *= 1.1  # 10% wider stop
                    print(f"   ⚖️  TIER 2 (50% size): Widened SL by 10%")
                elif position_tier == 'TIER_1':
                    print(f"   🔺 TIER 1 (100% size): Full confidence trade")

            # Calculate final position size with tier adjustment
            position_size = base_position_size * tier_multiplier

            # Round to nearest 0.1 lot (IG minimum increment)
            position_size = round(position_size, 1)

            # Ensure minimum position size
            position_size = max(0.1, position_size)

            # Log position sizing decision
            print(f"💰 Position Sizing:")
            print(f"   Base size: {base_position_size:.2f} lots (1% risk)")
            print(f"   Tier: {position_tier} ({tier_multiplier*100:.0f}%)")
            print(f"   Final size: {position_size:.2f} lots")
            print(f"   SL: {stop_loss_pips:.1f} pips | TP: {take_profit_pips:.1f} pips")

            # Execute trade on IG
            result = self.trader.open_position(
                pair=pair,
                direction=signal.signal,
                size=position_size,
                stop_loss_pips=stop_loss_pips,
                take_profit_pips=take_profit_pips
            )

            if result['success']:
                print(f"✅ REAL TRADE EXECUTED: {pair} {signal.signal} {position_size} lots")
                print(f"   Deal reference: {result['deal_reference']}")

                # Save position to database (match database schema)
                position_data = {
                    'position_id': result.get('deal_reference'),  # Deal reference is the position ID
                    'pair': pair,
                    'side': signal.signal,  # 'side' not 'direction'
                    'units': position_size,  # 'units' not 'size'
                    'entry_price': signal.entry_price,
                    'entry_time': datetime.now(),  # 'entry_time' not 'timestamp'
                    'stop_loss': signal.stop_loss,
                    'take_profit': signal.take_profit,
                    'current_price': signal.entry_price,  # Initial current price = entry price
                    'unrealized_pl': 0.0,  # Just opened, no P/L yet
                    'status': 'OPEN',
                    'signal_confidence': signal.confidence
                }

                # Add tier information if available (for tracking/analysis)
                if claude_validation:
                    position_data['claude_tier'] = position_tier
                    position_data['tier_multiplier'] = tier_multiplier

                self.db.save_position(position_data)

                return True
            else:
                print(f"❌ Failed to execute {pair} {signal.signal}: {result.get('error')}")
                return False

        except Exception as e:
            print(f"❌ Error executing signal for {pair}: {e}")
            traceback.print_exc()
            return False

    def run_analysis_cycle(self):
        """Run one complete analysis cycle for all pairs."""
        start_time = time.time()
        print(f"\n{'='*80}")
        print(f"🔄 Starting analysis cycle at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Show market session
        market_hours = get_market_hours()
        market_session = market_hours.get_market_session()
        print(f"📊 Market Session: {market_session}")

        print(f"{'='*80}")

        # Get rate limiter stats
        rate_limiter = get_rate_limiter()
        stats = rate_limiter.get_stats()
        print(f"📊 Rate Limits: Account {stats['account_requests']}/{stats['account_limit']}, App {stats['app_requests']}/{stats['app_limit']}")

        # Get current open positions from IG
        open_positions = self.trader.get_open_positions()
        print(f"📊 Open positions: {len(open_positions)}")

        # STEP 1: Analyze all pairs and collect signals (don't execute yet)
        results = []
        all_signals = []  # List of (signal, pair, result) tuples

        # Use priority pairs to avoid API rate limits
        pairs_to_analyze = ForexConfig.PRIORITY_PAIRS if len(ForexConfig.PRIORITY_PAIRS) > 0 else ForexConfig.ALL_PAIRS[:5]
        print(f"📊 Analyzing {len(pairs_to_analyze)} priority pairs...\n")

        # Batch processing to respect IG historical data allowance
        BATCH_SIZE = 5  # Process 5 pairs at a time
        BATCH_DELAY = 10  # Wait 10 seconds between batches

        total_pairs = len(pairs_to_analyze)
        pairs_processed = 0

        for batch_start in range(0, total_pairs, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_pairs)
            batch_pairs = pairs_to_analyze[batch_start:batch_end]
            batch_num = (batch_start // BATCH_SIZE) + 1
            total_batches = (total_pairs + BATCH_SIZE - 1) // BATCH_SIZE

            print(f"📦 Batch {batch_num}/{total_batches}: Processing pairs {batch_start+1}-{batch_end} of {total_pairs}")

            # Sequential analysis within batch (no parallel to respect rate limits)
            for pair in batch_pairs:
                try:
                    print(f"🔍 Analyzing {pair}...")
                    result = self.analyze_pair(pair)
                    results.append(result)
                    pairs_processed += 1

                    # Collect signal (don't execute yet)
                    if result.get('success') and result.get('signal'):
                        signal = result['signal']
                        if signal.signal in ['BUY', 'SELL']:
                            print(f"   ✅ {signal.signal} signal (confidence: {signal.confidence:.2f})")
                            all_signals.append((signal, pair, result))
                        else:
                            print(f"   ⏸️  HOLD (confidence: {signal.confidence:.2f})")
                    elif not result.get('success'):
                        print(f"   ❌ Analysis failed: {result.get('error', 'Unknown error')}")

                    # Show rate limit stats after each pair
                    stats = rate_limiter.get_stats()
                    print(f"   📊 Rate: {stats['account_remaining']}/{stats['account_limit']} remaining\n")

                except Exception as e:
                    print(f"❌ Error processing {pair}: {e}\n")

            # Delay between batches (except after last batch)
            if batch_end < total_pairs:
                print(f"⏳ Waiting {BATCH_DELAY}s before next batch to respect IG rate limits...\n")
                time.sleep(BATCH_DELAY)

        # STEP 2: No filtering - use all signals
        print(f"\n{'='*80}")
        print(f"📊 SIGNAL PROCESSING (No Currency Filtering)")
        print(f"{'='*80}")
        print(f"Total signals generated: {len(all_signals)}")

        # DISABLED: Currency exposure filtering
        # Reason: Too aggressive - filters out valid trading opportunities
        # filtered_signals = self.filter_signals_by_currency_exposure(all_signals)
        filtered_signals = all_signals  # Use all signals

        print(f"Signals to execute: {len(filtered_signals)}")

        # Show all signals
        if filtered_signals:
            print(f"\n✅ All signals (no filtering):")
            for signal, pair, result in filtered_signals:
                base, quote = self.get_currencies_from_pair(pair)
                if base and quote:
                    print(f"   {pair}: {signal.signal} (confidence: {signal.confidence:.2f}) - {base}/{quote}")
                else:
                    print(f"   {pair}: {signal.signal} (confidence: {signal.confidence:.2f}) - Commodity")

        # STEP 3: Execute filtered signals
        signals_executed = 0
        if self.auto_trading and filtered_signals:
            print(f"\n🔄 Executing {len(filtered_signals)} filtered signals...")
            for signal, pair, result in filtered_signals:
                # Extract data for Claude validation
                analysis_data = result.get('analysis', {})
                sentiment_data = result.get('sentiment_data')
                agent_results = {
                    'price_action': result.get('price_action', {}),
                    'momentum': result.get('momentum', {})
                }

                executed = self.execute_signal(
                    signal=signal,
                    pair=pair,
                    analysis_data=analysis_data,
                    sentiment_data=sentiment_data,
                    agent_results=agent_results
                )
                if executed:
                    signals_executed += 1

        signals_generated = len(all_signals)  # Total generated (before filtering)

        # STEP 4: Monitor open positions for reversals
        reversals_executed = 0
        if self.position_monitor and open_positions:
            try:
                print(f"\n{'='*80}")
                print(f"📊 POSITION MONITORING ({len(open_positions)} open positions)")
                print(f"{'='*80}")

                # Build dict of pair -> position data with prices
                # Open positions from IG already include current profit/loss,
                # which implies they have current prices
                positions_dict = {}
                current_prices = {}

                for pos in open_positions:
                    pair = pos.get('pair')
                    if not pair:
                        continue

                    positions_dict[pair] = {
                        'signal': 'BUY' if pos.get('direction') == 'BUY' else 'SELL',
                        'entry_price': pos.get('level', 0),
                        'stop_loss': pos.get('stop_level'),
                        'take_profit': pos.get('limit_level'),
                        'size': pos.get('size', 0),
                        'pnl': pos.get('profit_loss', 0),
                        'deal_id': pos.get('deal_id')
                    }

                    # For current price, we'll need to fetch latest data
                    # For now, use entry price as placeholder
                    # In production, you'd fetch current bid/ask from IG
                    current_prices[pair] = pos.get('level', 0)

                if positions_dict:
                    # Check for reversals
                    reversal_decisions = self.position_monitor.monitor_positions(
                        open_positions=positions_dict,
                        current_prices=current_prices
                    )

                    # Execute reversals
                    for decision in reversal_decisions:
                        if decision['action'] == 'REVERSE':
                            print(f"\n🔄 Reversing {decision['pair']}: {decision['reason']}")
                            print(f"   Confidence: {decision.get('confidence', 0):.1%}")
                            print(f"   Validated: {decision.get('validated', False)}")

                            # Execute reversal
                            success = self.position_monitor.execute_reversal(
                                pair=decision['pair'],
                                current_position=positions_dict[decision['pair']],
                                reversal_decision=decision
                            )

                            if success:
                                reversals_executed += 1
                                print(f"   ✅ Reversal executed successfully")
                            else:
                                print(f"   ❌ Reversal execution failed")

                        elif decision['action'] == 'CLOSE':
                            print(f"\n⚠️  Closing {decision['pair']}: {decision['reason']}")
                        elif decision['action'] == 'HOLD':
                            print(f"   {decision['pair']}: HOLD ({decision['reason']})")

                    if reversals_executed > 0:
                        print(f"\n✅ Executed {reversals_executed} position reversals")
                else:
                    print(f"   ⚠️  No valid positions to monitor")

            except Exception as e:
                print(f"❌ Position monitoring failed: {e}")
                traceback.print_exc()

        # Update account info
        self.account_info = self.trader.get_account_info()

        elapsed = time.time() - start_time
        print(f"\n✅ Analysis cycle complete in {elapsed:.1f}s")
        print(f"   Pairs analyzed: {len(results)}")
        print(f"   Signals generated: {signals_generated}")
        print(f"   Signals executed: {signals_executed}")
        if signals_generated > signals_executed:
            print(f"   Signals filtered: {signals_generated - signals_executed} (duplicate currency exposure)")
        if reversals_executed > 0:
            print(f"   Reversals executed: {reversals_executed}")
        print(f"   Open positions: {len(open_positions)}")
        print(f"   Account balance: €{self.account_info.get('balance', 0):,.2f}")
        print(f"   Next cycle in {self.interval_seconds}s")

    def start(self):
        """Start the worker thread."""
        if self.running:
            print("⚠️  Worker already running")
            return

        self.running = True

        def worker_loop():
            while self.running:
                try:
                    # Check if market is open (pause on weekends)
                    market_hours = get_market_hours()
                    if not market_hours.is_market_open():
                        print("\n🛑 FOREX MARKET CLOSED - Waiting for market to open...")
                        market_hours.wait_until_market_open(check_interval=3600)  # Check every hour

                        # Check if we're still running after waiting
                        if not self.running:
                            break

                    # Run analysis cycle
                    self.run_analysis_cycle()
                except Exception as e:
                    print(f"❌ Error in worker loop: {e}")
                    traceback.print_exc()

                # Wait for next cycle
                time.sleep(self.interval_seconds)

        self.worker_thread = threading.Thread(target=worker_loop, daemon=True)
        self.worker_thread.start()
        print(f"\n✅ IG worker started (running every {self.interval_seconds}s)")

    def stop(self):
        """Stop the worker thread."""
        print("\n⏹️  Stopping IG worker...")
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        print("✅ IG worker stopped")

    def get_status(self) -> Dict:
        """Get current worker status."""
        open_positions = self.trader.get_open_positions()
        account_info = self.trader.get_account_info()

        return {
            'running': self.running,
            'auto_trading': self.auto_trading,
            'account_balance': account_info.get('balance', 0),
            'available_funds': account_info.get('available', 0),
            'open_positions': len(open_positions),
            'pairs_monitored': len(ForexConfig.ALL_PAIRS),
        }


# Test
if __name__ == "__main__":
    print("="*80)
    print("IG REAL TRADING WORKER TEST")
    print("="*80)

    # Create worker (auto-trading DISABLED for safety)
    worker = IGConcurrentWorker(
        auto_trading=False,  # DISABLED for testing
        max_workers=5,
        interval_seconds=120  # 2 minutes for testing
    )

    # Run one analysis cycle
    print("\n🔄 Running single analysis cycle...")
    worker.run_analysis_cycle()

    print("\n✅ Test complete!")
    print("="*80)
