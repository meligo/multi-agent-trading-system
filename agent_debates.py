"""
Agent Debate System for Forex Trading

Implements multi-round adversarial debates:
1. Bull vs Bear Investment Debate - Should we trade this signal?
2. Risk Management Debate - How should we size and manage the trade?

Debates stress-test trading decisions through adversarial arguments.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass
from gpt5_wrapper import GPT5Wrapper


@dataclass
class DebateState:
    """State tracking for a debate."""
    round_num: int = 0
    bull_arguments: List[str] = None
    bear_arguments: List[str] = None
    full_history: str = ""
    final_decision: str = ""

    def __post_init__(self):
        if self.bull_arguments is None:
            self.bull_arguments = []
        if self.bear_arguments is None:
            self.bear_arguments = []


class BullAgent:
    """
    Bull Agent - Argues FOR taking the trade.

    Focuses on:
    - Growth potential
    - Positive technical signals
    - Favorable market conditions
    - Opportunity cost of missing the trade
    """

    def __init__(self, llm: GPT5Wrapper, memory=None):
        self.llm = llm
        self.memory = memory
        self.role = "Bull Analyst"

    def argue(
        self,
        market_analysis: Dict,
        opponent_last_argument: str = "",
        round_num: int = 1
    ) -> str:
        """
        Present bullish argument for the trade.

        Args:
            market_analysis: Complete market analysis from agents
            opponent_last_argument: Bear's last argument to counter
            round_num: Current debate round

        Returns:
            Bull's argument as string
        """
        # Get past lessons if memory available
        past_lessons = ""
        if self.memory:
            situation_summary = f"""
            Price Action: {market_analysis.get('price_action_analysis', {}).get('summary', 'N/A')}
            Momentum: {market_analysis.get('momentum_analysis', {}).get('summary', 'N/A')}
            """
            similar = self.memory.get_similar_situations(situation_summary, n_matches=2)
            if similar:
                past_lessons = "\n".join([mem.get('reflection', '') for mem in similar])

        # Extract actual data from agents
        price_action = market_analysis.get('price_action_analysis', {})
        momentum = market_analysis.get('momentum_analysis', {})

        # Price Action uses 'reasoning', not 'summary'
        price_summary = price_action.get('reasoning', price_action.get('summary', 'N/A'))
        price_direction = price_action.get('direction', 'NONE')
        price_setup = price_action.get('setup_type', 'N/A')
        price_conf = price_action.get('confidence', 0)

        # Momentum uses 'reasoning' too
        momentum_summary = momentum.get('reasoning', momentum.get('summary', 'N/A'))
        momentum_strength = momentum.get('strength', 'N/A')
        momentum_direction = momentum.get('direction', 'NONE')

        # Build comprehensive technical picture
        indicators = market_analysis.get('indicators', {})
        if not isinstance(indicators, dict):
            indicators = {}
        rsi = indicators.get('rsi_14', 'N/A')
        macd = indicators.get('macd', 'N/A')
        adx = indicators.get('adx', 'N/A')

        prompt = f"""You are a Bull Analyst in a trading debate. Your goal is to argue FOR taking this trade.

Market Analysis:
- Price Action: {price_direction} {price_setup} (Confidence: {price_conf}%)
  {price_summary[:200]}

- Momentum: {momentum_direction} {momentum_strength}
  {momentum_summary[:200]}

- Key Indicators: RSI={rsi}, MACD={macd}, ADX={adx}
- Finnhub Consensus: {market_analysis.get('aggregate_indicators', {}).get('consensus', 'N/A')}

{"Lessons from similar past situations: " + past_lessons if past_lessons else ""}

{"Bear's argument: " + opponent_last_argument if opponent_last_argument else "Opening statement:"}

Round {round_num} - Present your {('rebuttal' if opponent_last_argument else 'opening bullish case')}:
- Focus on strengths and opportunities
- Counter bear's concerns if any were raised
- Be specific about why THIS setup is tradeable
- Keep argument under 200 words

Your argument:"""

        response = self.llm.invoke([{"role": "user", "content": prompt}])
        return f"{self.role}: {response.content}"


class BearAgent:
    """
    Bear Agent - Argues AGAINST taking the trade.

    Focuses on:
    - Risks and downside
    - Negative signals or contradictions
    - Unfavorable market conditions
    - Opportunity to wait for better setup
    """

    def __init__(self, llm: GPT5Wrapper, memory=None):
        self.llm = llm
        self.memory = memory
        self.role = "Bear Analyst"

    def argue(
        self,
        market_analysis: Dict,
        opponent_last_argument: str = "",
        round_num: int = 1
    ) -> str:
        """Present bearish argument against the trade."""

        # Extract actual data from agents
        price_action = market_analysis.get('price_action_analysis', {})
        momentum = market_analysis.get('momentum_analysis', {})

        # Price Action uses 'reasoning', not 'summary'
        price_summary = price_action.get('reasoning', price_action.get('summary', 'N/A'))
        price_direction = price_action.get('direction', 'NONE')
        price_setup = price_action.get('setup_type', 'N/A')
        price_conf = price_action.get('confidence', 0)

        # Momentum uses 'reasoning' too
        momentum_summary = momentum.get('reasoning', momentum.get('summary', 'N/A'))
        momentum_strength = momentum.get('strength', 'N/A')
        momentum_direction = momentum.get('direction', 'NONE')

        # Get past lessons
        past_lessons = ""
        if self.memory:
            situation_summary = f"""
            Price Action: {price_direction} {price_setup}
            Momentum: {momentum_direction} {momentum_strength}
            """
            similar = self.memory.get_similar_situations(situation_summary, n_matches=2)
            if similar:
                past_lessons = "\n".join([mem.get('reflection', '') for mem in similar])

        # Build comprehensive technical picture
        indicators = market_analysis.get('indicators', {})
        if not isinstance(indicators, dict):
            indicators = {}
        rsi = indicators.get('rsi_14', 'N/A')
        macd = indicators.get('macd', 'N/A')
        adx = indicators.get('adx', 'N/A')

        prompt = f"""You are a Bear Analyst in a trading debate. Your goal is to argue AGAINST taking this trade.

Market Analysis:
- Price Action: {price_direction} {price_setup} (Confidence: {price_conf}%)
  {price_summary[:200]}

- Momentum: {momentum_direction} {momentum_strength}
  {momentum_summary[:200]}

- Key Indicators: RSI={rsi}, MACD={macd}, ADX={adx}
- Finnhub Consensus: {market_analysis.get('aggregate_indicators', {}).get('consensus', 'N/A')}

{"Lessons from similar past situations: " + past_lessons if past_lessons else ""}

{"Bull's argument: " + opponent_last_argument if opponent_last_argument else "Opening statement:"}

Round {round_num} - Present your {('rebuttal' if opponent_last_argument else 'opening bearish case')}:
- Focus on risks and weaknesses
- Counter bull's optimism if raised
- Be specific about why THIS setup is questionable
- Consider opportunity cost of taking a risky trade
- Keep argument under 200 words

Your argument:"""

        response = self.llm.invoke([{"role": "user", "content": prompt}])
        return f"{self.role}: {response.content}"


class DebateJudge:
    """
    Judge for investment debate.

    Reviews all arguments and makes final decision:
    - BUY (if bull case is stronger)
    - SELL (if both agree market is bearish)
    - HOLD (if bear case wins / too risky)
    """

    def __init__(self, llm: GPT5Wrapper):
        self.llm = llm

    def synthesize(
        self,
        market_analysis: Dict,
        debate_history: str,
        bull_arguments: List[str],
        bear_arguments: List[str]
    ) -> Dict:
        """
        Synthesize debate into final decision.

        Returns:
            Dictionary with decision, confidence, reasoning
        """
        # Extract actual data from agents
        price_action = market_analysis.get('price_action_analysis', {})
        momentum = market_analysis.get('momentum_analysis', {})

        price_summary = price_action.get('reasoning', price_action.get('summary', 'N/A'))[:150]
        price_direction = price_action.get('direction', 'NONE')
        price_setup = price_action.get('setup_type', 'N/A')

        momentum_summary = momentum.get('reasoning', momentum.get('summary', 'N/A'))[:150]
        momentum_direction = momentum.get('direction', 'NONE')
        momentum_strength = momentum.get('strength', 'N/A')

        prompt = f"""You are the Research Manager overseeing a trading debate.

Market Analysis Summary:
- Price Action: {price_direction} {price_setup} - {price_summary}
- Momentum: {momentum_direction} {momentum_strength} - {momentum_summary}

Complete Debate:
{debate_history}

Bull Arguments Summary:
{chr(10).join(f"- {arg[arg.find(':')+1:].strip()[:100]}" for arg in bull_arguments)}

Bear Arguments Summary:
{chr(10).join(f"- {arg[arg.find(':')+1:].strip()[:100]}" for arg in bear_arguments)}

Your task:
1. Critically evaluate BOTH sides
2. Identify the strongest arguments
3. Make a definitive decision: BUY, SELL, or HOLD
4. Provide confidence level (0-100)
5. Give clear reasoning

Format your response EXACTLY as:
DECISION: [BUY/SELL/HOLD]
CONFIDENCE: [0-100]
REASONING:
[Your detailed reasoning here]

Your judgment:"""

        response = self.llm.invoke([{"role": "user", "content": prompt}])
        response_text = response.content

        # Parse response
        decision = "HOLD"
        confidence = 50
        reasoning = response_text

        lines = response_text.split('\n')
        for line in lines:
            if line.startswith("DECISION:"):
                decision = line.split(":")[1].strip().upper()
            elif line.startswith("CONFIDENCE:"):
                try:
                    confidence = int(line.split(":")[1].strip())
                except:
                    confidence = 50
            elif line.startswith("REASONING:"):
                reasoning = "\n".join(lines[lines.index(line)+1:])
                break

        return {
            "decision": decision,
            "confidence": confidence / 100.0,
            "reasoning": reasoning.strip(),
            "debate_summary": f"Bull made {len(bull_arguments)} arguments, Bear made {len(bear_arguments)} arguments"
        }


class InvestmentDebate:
    """
    Orchestrates Bull vs Bear investment debate.

    Process:
    1. Bull presents opening case
    2. Bear presents counterargument
    3. Bull rebuts (Round 2)
    4. Bear counters (Round 2)
    5. Judge synthesizes decision
    """

    def __init__(
        self,
        llm: GPT5Wrapper,
        bull_memory=None,
        bear_memory=None,
        max_rounds: int = 2
    ):
        self.bull = BullAgent(llm, bull_memory)
        self.bear = BearAgent(llm, bear_memory)
        self.judge = DebateJudge(llm)
        self.max_rounds = max_rounds

    def run_debate(self, market_analysis: Dict) -> Dict:
        """
        Run complete Bull vs Bear debate.

        Args:
            market_analysis: Complete market analysis from agents

        Returns:
            Dictionary with final decision, confidence, reasoning, debate_history
        """
        print(f"\n🎭 Starting Investment Debate ({self.max_rounds} rounds)...")

        state = DebateState()

        for round_num in range(1, self.max_rounds + 1):
            print(f"\n--- Round {round_num} ---")

            # Bull argues
            bear_last = state.bear_arguments[-1] if state.bear_arguments else ""
            bull_arg = self.bull.argue(market_analysis, bear_last, round_num)
            state.bull_arguments.append(bull_arg)
            state.full_history += f"\n{bull_arg}\n"
            print(f"🐂 Bull: {bull_arg[bull_arg.find(':')+1:].strip()[:100]}...")

            # Bear argues
            bear_arg = self.bear.argue(market_analysis, bull_arg, round_num)
            state.bear_arguments.append(bear_arg)
            state.full_history += f"\n{bear_arg}\n"
            print(f"🐻 Bear: {bear_arg[bear_arg.find(':')+1:].strip()[:100]}...")

        # Judge synthesizes
        print("\n⚖️  Judge deliberating...")
        final_decision = self.judge.synthesize(
            market_analysis,
            state.full_history,
            state.bull_arguments,
            state.bear_arguments
        )

        final_decision['debate_history'] = state.full_history
        final_decision['bull_arguments'] = state.bull_arguments
        final_decision['bear_arguments'] = state.bear_arguments

        print(f"\n✅ Final Decision: {final_decision['decision']} (Confidence: {final_decision['confidence']:.0%})")

        return final_decision


# Test function
def test_investment_debate():
    """Test the investment debate system."""
    print("Testing Investment Debate System...")
    print("=" * 70)

    from dotenv import load_dotenv
    load_dotenv()

    # Create LLM
    llm = GPT5Wrapper(model="gpt-4o-mini", temperature=0.3)

    # Mock market analysis
    market_analysis = {
        'price_action_analysis': {
            'summary': 'Bullish breakout above resistance, strong momentum on 5m timeframe'
        },
        'momentum_analysis': {
            'summary': 'MACD bullish crossover, RSI at 68, ADX showing strong trend'
        },
        'indicators': 'RSI: 68, MACD: +0.0012, ADX: 32, Bollinger: expanding',
        'aggregate_indicators': {
            'consensus': 'BULLISH',
            'buy_count': 18,
            'sell_count': 5
        }
    }

    # Run debate
    debate = InvestmentDebate(llm, max_rounds=2)
    result = debate.run_debate(market_analysis)

    print("\n" + "=" * 70)
    print("FINAL JUDGMENT:")
    print(f"Decision: {result['decision']}")
    print(f"Confidence: {result['confidence']:.0%}")
    print(f"\nReasoning:\n{result['reasoning']}")
    print("\n✓ Investment debate test complete!")


if __name__ == "__main__":
    test_investment_debate()
