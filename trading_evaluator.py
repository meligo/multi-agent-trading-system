"""
Trading Evaluation Framework

Provides multi-faceted evaluation of trading decisions:
1. LLM-as-a-Judge - Quality scoring of reasoning
2. Ground Truth Backtesting - Actual market performance
3. Reflection Engine - Learning from outcomes
"""

import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, Optional
from pydantic import BaseModel, Field
from gpt5_wrapper import GPT5Wrapper


class EvaluationScores(BaseModel):
    """Structured evaluation scores."""
    reasoning_quality: int = Field(description="Score 1-10 on logic and coherence", ge=1, le=10)
    evidence_based: int = Field(description="Score 1-10 on use of data/evidence", ge=1, le=10)
    actionability: int = Field(description="Score 1-10 on clarity of action", ge=1, le=10)
    risk_assessment: int = Field(description="Score 1-10 on risk consideration", ge=1, le=10)
    justification: str = Field(description="Brief justification for scores")


class LLMJudgeEvaluator:
    """
    LLM-as-a-Judge evaluation.

    Uses a powerful LLM to score the quality of trading decisions.
    """

    def __init__(self, llm: GPT5Wrapper):
        self.llm = llm

    def evaluate(
        self,
        market_analysis: Dict,
        final_decision: str,
        reasoning: str
    ) -> Dict:
        """
        Evaluate quality of trading decision.

        Args:
            market_analysis: Market analysis used for decision
            final_decision: Final decision (BUY/SELL/HOLD)
            reasoning: Reasoning for the decision

        Returns:
            Dictionary with quality scores
        """
        prompt = f"""You are an expert financial auditor evaluating trading decisions.

Market Analysis Summary:
{self._format_analysis(market_analysis)}

Final Decision: {final_decision}

Reasoning Provided:
{reasoning}

Evaluate this trading decision on the following criteria (score 1-10 each):

1. Reasoning Quality: Is the logic sound and coherent?
2. Evidence-Based: Does it properly use the market analysis data?
3. Actionability: Is the decision clear and executable?
4. Risk Assessment: Are risks properly considered?

Provide scores and justification in this EXACT format:

REASONING_QUALITY: [1-10]
EVIDENCE_BASED: [1-10]
ACTIONABILITY: [1-10]
RISK_ASSESSMENT: [1-10]
JUSTIFICATION:
[Your 2-3 sentence justification here]

Your evaluation:"""

        response = self.llm.generate(prompt, max_tokens=300)

        # Parse response
        scores = {
            'reasoning_quality': 5,
            'evidence_based': 5,
            'actionability': 5,
            'risk_assessment': 5,
            'justification': response
        }

        lines = response.split('\n')
        for line in lines:
            if line.startswith("REASONING_QUALITY:"):
                try:
                    scores['reasoning_quality'] = int(line.split(":")[1].strip())
                except:
                    pass
            elif line.startswith("EVIDENCE_BASED:"):
                try:
                    scores['evidence_based'] = int(line.split(":")[1].strip())
                except:
                    pass
            elif line.startswith("ACTIONABILITY:"):
                try:
                    scores['actionability'] = int(line.split(":")[1].strip())
                except:
                    pass
            elif line.startswith("RISK_ASSESSMENT:"):
                try:
                    scores['risk_assessment'] = int(line.split(":")[1].strip())
                except:
                    pass
            elif line.startswith("JUSTIFICATION:"):
                idx = lines.index(line)
                scores['justification'] = "\n".join(lines[idx+1:]).strip()
                break

        # Calculate average
        scores['average_score'] = (
            scores['reasoning_quality'] +
            scores['evidence_based'] +
            scores['actionability'] +
            scores['risk_assessment']
        ) / 4.0

        return scores

    def _format_analysis(self, analysis: Dict) -> str:
        """Format analysis for prompt."""
        parts = []
        if 'price_action_analysis' in analysis:
            parts.append(f"Price Action: {analysis['price_action_analysis'].get('summary', 'N/A')}")
        if 'momentum_analysis' in analysis:
            parts.append(f"Momentum: {analysis['momentum_analysis'].get('summary', 'N/A')}")
        if 'aggregate_indicators' in analysis:
            agg = analysis['aggregate_indicators']
            parts.append(f"Finnhub Consensus: {agg.get('consensus', 'N/A')} ({agg.get('buy_count', 0)} buy, {agg.get('sell_count', 0)} sell)")
        return "\n".join(parts)


class GroundTruthEvaluator:
    """
    Ground truth backtesting evaluator.

    Checks if the trading decision was correct based on actual market performance.
    """

    def __init__(self):
        pass

    def evaluate(
        self,
        pair: str,
        signal_date: str,
        signal: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        days_forward: int = 5
    ) -> Dict:
        """
        Evaluate decision against actual market performance.

        Args:
            pair: Currency pair
            signal_date: Date signal was generated (YYYY-MM-DD)
            signal: BUY, SELL, or HOLD
            entry_price: Entry price
            stop_loss: Stop loss level
            take_profit: Take profit level
            days_forward: Days to evaluate forward

        Returns:
            Dictionary with outcome analysis
        """
        try:
            # Convert pair format for yfinance
            yf_symbol = pair.replace("_", "") + "=X"  # e.g., EURUSD=X

            start_date = datetime.strptime(signal_date, "%Y-%m-%d").date()
            end_date = start_date + timedelta(days=days_forward + 5)  # Extra days for trading days

            # Fetch data
            data = yf.download(yf_symbol, start=start_date.isoformat(), end=end_date.isoformat(), progress=False)

            if len(data) < 2:
                return {
                    'error': f'Insufficient data for {pair}',
                    'outcome': 'UNKNOWN'
                }

            # Get actual entry (open of first day or next available)
            actual_entry = data['Open'].iloc[0]

            # Check if SL or TP hit within period
            sl_hit = False
            tp_hit = False
            final_price = None

            for i in range(min(days_forward, len(data))):
                high = data['High'].iloc[i]
                low = data['Low'].iloc[i]

                if signal == "BUY":
                    if low <= stop_loss:
                        sl_hit = True
                        final_price = stop_loss
                        break
                    if high >= take_profit:
                        tp_hit = True
                        final_price = take_profit
                        break
                elif signal == "SELL":
                    if high >= stop_loss:
                        sl_hit = True
                        final_price = stop_loss
                        break
                    if low <= take_profit:
                        tp_hit = True
                        final_price = take_profit
                        break

            # If no SL/TP hit, use final closing price
            if not sl_hit and not tp_hit:
                final_price = data['Close'].iloc[min(days_forward-1, len(data)-1)]

            # Calculate outcome
            # CRITICAL: JPY pairs have different pip calculation!
            # JPY pairs: 1 pip = 0.01 (multiply by 100)
            # Other pairs: 1 pip = 0.0001 (multiply by 10000)
            pip_multiplier = 100 if 'JPY' in pair else 10000

            if signal == "BUY":
                pips_change = (final_price - actual_entry) * pip_multiplier
                outcome_pct = ((final_price - actual_entry) / actual_entry) * 100
            elif signal == "SELL":
                pips_change = (actual_entry - final_price) * pip_multiplier
                outcome_pct = ((actual_entry - final_price) / actual_entry) * 100
            else:  # HOLD
                return {
                    'signal': signal,
                    'outcome': 'CORRECT',  # HOLD is always "correct" in evaluation
                    'outcome_pct': 0,
                    'note': 'HOLD signal - no trade taken'
                }

            # Determine if decision was correct
            if tp_hit:
                outcome = 'WIN'
                result = 'CORRECT'
            elif sl_hit:
                outcome = 'LOSS'
                result = 'INCORRECT'
            elif outcome_pct > 0.1:  # Small profit threshold
                outcome = 'PROFIT'
                result = 'CORRECT'
            elif outcome_pct < -0.1:
                outcome = 'LOSS'
                result = 'INCORRECT'
            else:
                outcome = 'BREAKEVEN'
                result = 'NEUTRAL'

            return {
                'signal': signal,
                'entry_price': actual_entry,
                'final_price': final_price,
                'pips_change': pips_change,
                'outcome_pct': outcome_pct,
                'outcome': outcome,
                'result': result,
                'tp_hit': tp_hit,
                'sl_hit': sl_hit,
                'days_evaluated': min(days_forward, len(data))
            }

        except Exception as e:
            return {
                'error': f'Evaluation failed: {str(e)}',
                'outcome': 'ERROR'
            }


class ReflectionEngine:
    """
    Generates reflections/lessons from trading outcomes.

    Used to populate agent memories for learning.
    """

    def __init__(self, llm: GPT5Wrapper):
        self.llm = llm

    def reflect(
        self,
        market_analysis: Dict,
        decision: str,
        reasoning: str,
        outcome: Dict
    ) -> str:
        """
        Generate reflection/lesson from trading outcome.

        Args:
            market_analysis: Market analysis at decision time
            decision: Decision made
            reasoning: Reasoning provided
            outcome: Actual outcome from ground truth evaluation

        Returns:
            One-sentence lesson learned
        """
        if outcome.get('error'):
            return "Unable to evaluate outcome due to data issues."

        result = outcome.get('result', 'UNKNOWN')
        outcome_pct = outcome.get('outcome_pct', 0)

        prompt = f"""You are analyzing a trading decision to extract a lesson.

Market Analysis:
{self._format_analysis(market_analysis)}

Decision Made: {decision}

Reasoning: {reasoning}

Actual Outcome: {result} ({outcome_pct:+.2f}%)
{"Stop loss hit" if outcome.get('sl_hit') else ""}
{"Take profit hit" if outcome.get('tp_hit') else ""}

Generate a ONE-SENTENCE lesson or heuristic that can improve future decisions in similar situations.
Focus on the most critical factor that led to this outcome.

Lesson:"""

        response = self.llm.generate(prompt, max_tokens=100)
        return response.strip()

    def _format_analysis(self, analysis: Dict) -> str:
        """Format analysis for prompt."""
        parts = []
        if 'price_action_analysis' in analysis:
            parts.append(f"Price Action: {analysis['price_action_analysis'].get('summary', 'N/A')[:100]}")
        if 'momentum_analysis' in analysis:
            parts.append(f"Momentum: {analysis['momentum_analysis'].get('summary', 'N/A')[:100]}")
        return "\n".join(parts) if parts else "Limited analysis available"


class TradingEvaluator:
    """
    Complete trading evaluation framework.

    Combines all evaluation methods.
    """

    def __init__(self, llm: GPT5Wrapper):
        self.llm_judge = LLMJudgeEvaluator(llm)
        self.ground_truth = GroundTruthEvaluator()
        self.reflection = ReflectionEngine(llm)

    def evaluate_signal_quality(
        self,
        market_analysis: Dict,
        final_decision: str,
        reasoning: str
    ) -> Dict:
        """Evaluate quality of signal using LLM judge."""
        return self.llm_judge.evaluate(market_analysis, final_decision, reasoning)

    def evaluate_ground_truth(
        self,
        pair: str,
        signal_date: str,
        signal: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Dict:
        """Evaluate against actual market performance."""
        return self.ground_truth.evaluate(
            pair, signal_date, signal, entry_price, stop_loss, take_profit
        )

    def generate_reflection(
        self,
        market_analysis: Dict,
        decision: str,
        reasoning: str,
        outcome: Dict
    ) -> str:
        """Generate learning reflection from outcome."""
        return self.reflection.reflect(market_analysis, decision, reasoning, outcome)


# Test function
def test_trading_evaluator():
    """Test the trading evaluator."""
    print("Testing Trading Evaluator...")
    print("=" * 70)

    from dotenv import load_dotenv
    load_dotenv()

    # Create evaluator
    llm = GPT5Wrapper(model="gpt-4o-mini", temperature=0.1)
    evaluator = TradingEvaluator(llm)

    # Mock data
    market_analysis = {
        'price_action_analysis': {'summary': 'Bullish breakout above 1.0850'},
        'momentum_analysis': {'summary': 'Strong momentum, MACD positive'},
        'aggregate_indicators': {'consensus': 'BULLISH', 'buy_count': 18, 'sell_count': 5}
    }

    decision = "BUY"
    reasoning = "Strong technical setup with MACD crossover and breakout confirmation. Risk/reward 2:1."

    # Test LLM judge
    print("\n1️⃣ Testing LLM-as-a-Judge...")
    scores = evaluator.evaluate_signal_quality(market_analysis, decision, reasoning)
    print(f"   Average Score: {scores['average_score']:.1f}/10")
    print(f"   Reasoning Quality: {scores['reasoning_quality']}/10")
    print(f"   Evidence-Based: {scores['evidence_based']}/10")
    print(f"   Justification: {scores['justification'][:100]}...")

    # Test ground truth (with real market data)
    print("\n2️⃣ Testing Ground Truth Evaluator...")
    outcome = evaluator.evaluate_ground_truth(
        pair="EUR_USD",
        signal_date="2024-10-01",
        signal="BUY",
        entry_price=1.1000,
        stop_loss=1.0970,
        take_profit=1.1060
    )
    if 'error' not in outcome:
        print(f"   Result: {outcome['result']}")
        print(f"   Outcome: {outcome['outcome']} ({outcome['outcome_pct']:+.2f}%)")
        print(f"   Pips: {outcome['pips_change']:+.1f}")
    else:
        print(f"   {outcome['error']}")

    # Test reflection
    print("\n3️⃣ Testing Reflection Engine...")
    if 'error' not in outcome:
        lesson = evaluator.generate_reflection(market_analysis, decision, reasoning, outcome)
        print(f"   Lesson: {lesson}")

    print("\n✓ Trading evaluator test complete!")


if __name__ == "__main__":
    test_trading_evaluator()
