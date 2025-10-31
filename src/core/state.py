"""State definitions for the trading system."""

from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph import MessagesState


class InvestDebateState(TypedDict):
    """State for the investment research debate."""
    bull_history: str  # Arguments from bull researcher
    bear_history: str  # Arguments from bear researcher
    history: str  # Full debate transcript
    current_response: str  # Most recent argument
    judge_decision: str  # Research manager's final decision
    count: int  # Number of debate rounds


class RiskDebateState(TypedDict):
    """State for the risk management debate."""
    risky_history: str  # Aggressive analyst arguments
    safe_history: str  # Conservative analyst arguments
    neutral_history: str  # Neutral analyst arguments
    history: str  # Full debate transcript
    latest_speaker: str  # Last agent to speak
    current_risky_response: str  # Latest risky response
    current_safe_response: str  # Latest safe response
    current_neutral_response: str  # Latest neutral response
    judge_decision: str  # Portfolio manager's final decision
    count: int  # Number of debate rounds


class AgentState(MessagesState):
    """
    Main state that flows through the entire agent system.

    Inherits from MessagesState to include conversation history.
    """
    # Core identifiers
    company_of_interest: str
    trade_date: str
    sender: str

    # Analyst reports
    market_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    news_report: Optional[str] = None
    fundamentals_report: Optional[str] = None

    # Research phase
    investment_debate_state: Optional[InvestDebateState] = None
    investment_plan: Optional[str] = None

    # Trading phase
    trader_investment_plan: Optional[str] = None

    # Risk management phase
    risk_debate_state: Optional[RiskDebateState] = None
    final_trade_decision: Optional[str] = None

    # Evaluation results
    final_signal: Optional[str] = None  # BUY, SELL, HOLD
    evaluation_results: Optional[dict] = None


def create_initial_state(ticker: str, trade_date: str) -> AgentState:
    """
    Create an initial state for a trading analysis.

    Args:
        ticker: Stock ticker symbol
        trade_date: Date for the analysis

    Returns:
        Initialized AgentState
    """
    from langchain_core.messages import HumanMessage

    return AgentState(
        messages=[HumanMessage(content=f"Analyze {ticker} for trading on {trade_date}")],
        company_of_interest=ticker,
        trade_date=trade_date,
        sender="system",
        investment_debate_state=InvestDebateState(
            history="",
            current_response="",
            count=0,
            bull_history="",
            bear_history="",
            judge_decision="",
        ),
        risk_debate_state=RiskDebateState(
            history="",
            latest_speaker="",
            current_risky_response="",
            current_safe_response="",
            current_neutral_response="",
            count=0,
            risky_history="",
            safe_history="",
            neutral_history="",
            judge_decision="",
        ),
    )
