#!/usr/bin/env python3
"""
Multi-Agent Trading System - Main Entry Point

This is the single file to run the entire trading system.
Works both locally and in Docker.

Usage:
    python main.py NVDA                    # Analyze NVDA
    python main.py NVDA --date 2024-01-15  # Specific date
    python main.py NVDA --debug            # Debug mode
"""

import sys
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from typing_extensions import TypedDict
from langgraph.graph import MessagesState
from langchain_core.messages import HumanMessage, RemoveMessage
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
import yfinance as yf
import finnhub
from typing import Annotated
from langchain_community.tools.tavily_search import TavilySearchResults
from stockstats import wrap as stockstats_wrap
from rich.console import Console
from rich.markdown import Markdown
from rich.progress import Progress, SpinnerColumn, TextColumn
import chromadb
from openai import OpenAI

console = Console()


# ============================================================================
# STATE DEFINITIONS
# ============================================================================

class InvestDebateState(TypedDict):
    """State for the investment research debate."""
    bull_history: str
    bear_history: str
    history: str
    current_response: str
    judge_decision: str
    count: int


class RiskDebateState(TypedDict):
    """State for the risk management debate."""
    risky_history: str
    safe_history: str
    neutral_history: str
    history: str
    latest_speaker: str
    current_risky_response: str
    current_safe_response: str
    current_neutral_response: str
    judge_decision: str
    count: int


class AgentState(MessagesState):
    """Main state that flows through the entire agent system."""
    company_of_interest: str
    trade_date: str
    sender: str
    market_report: Optional[str] = None
    sentiment_report: Optional[str] = None
    news_report: Optional[str] = None
    fundamentals_report: Optional[str] = None
    investment_debate_state: Optional[InvestDebateState] = None
    investment_plan: Optional[str] = None
    trader_investment_plan: Optional[str] = None
    risk_debate_state: Optional[RiskDebateState] = None
    final_trade_decision: Optional[str] = None


def create_initial_state(ticker: str, trade_date: str) -> AgentState:
    """Create an initial state for a trading analysis."""
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


# ============================================================================
# MEMORY SYSTEM
# ============================================================================

class FinancialSituationMemory:
    """Long-term memory for storing and retrieving financial situations."""

    def __init__(self, name: str, config):
        self.name = name
        self.config = config
        self.embedding_model = config.EMBEDDING_MODEL

        try:
            self.client = OpenAI(base_url=config.LLM_BACKEND_URL, api_key=config.OPENAI_API_KEY)
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to initialize OpenAI client for memory: {e}")
            self.client = None

        try:
            persistence_dir = Path(config.MEMORY_PERSISTENCE_DIR) / name
            persistence_dir.mkdir(parents=True, exist_ok=True)
            self.chroma_client = chromadb.PersistentClient(path=str(persistence_dir))
            self.situation_collection = self.chroma_client.get_or_create_collection(
                name=name,
                metadata={"description": f"Financial situations for {name}"}
            )
        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to initialize ChromaDB: {e}")
            self.situation_collection = None

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for text."""
        if not self.client:
            return []
        try:
            response = self.client.embeddings.create(model=self.embedding_model, input=text)
            return response.data[0].embedding
        except Exception as e:
            return []

    def add_situations(self, situations_and_advice: List[Tuple[str, str]]) -> None:
        """Add new situations and their lessons to memory."""
        if not situations_and_advice or not self.situation_collection:
            return

        try:
            offset = self.situation_collection.count()
            ids = [str(offset + i) for i, _ in enumerate(situations_and_advice)]
            situations = [s for s, r in situations_and_advice]
            recommendations = [r for s, r in situations_and_advice]
            embeddings = [self.get_embedding(s) for s in situations]

            self.situation_collection.add(
                documents=situations,
                metadatas=[{"recommendation": rec} for rec in recommendations],
                embeddings=embeddings,
                ids=ids,
            )
        except Exception as e:
            pass

    def get_memories(self, current_situation: str, n_matches: int = 1) -> List[dict]:
        """Retrieve similar past situations and their lessons."""
        if not self.situation_collection or self.situation_collection.count() == 0:
            return []

        try:
            query_embedding = self.get_embedding(current_situation)
            if not query_embedding:
                return []

            results = self.situation_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_matches, self.situation_collection.count()),
                include=["metadatas", "distances"],
            )

            memories = []
            threshold = self.config.SIMILARITY_THRESHOLD

            for meta, distance in zip(results['metadatas'][0], results['distances'][0]):
                similarity = 1 - distance
                if similarity >= threshold:
                    memories.append({
                        'recommendation': meta['recommendation'],
                        'similarity': similarity
                    })

            return memories
        except Exception as e:
            return []


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging(level: str = "INFO"):
    """Setup logging."""
    logging.basicConfig(
        level=getattr(logging, level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    # Reduce noise
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


# ============================================================================
# TOOLS
# ============================================================================

@tool
def get_yfinance_data(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "Start date yyyy-mm-dd"],
    end_date: Annotated[str, "End date yyyy-mm-dd"],
) -> str:
    """Get stock price data from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol.upper())
        data = ticker.history(start=start_date, end=end_date)
        if data.empty:
            return f"No data found for {symbol}"
        return data.to_csv()
    except Exception as e:
        return f"Error: {e}"


@tool
def get_technical_indicators(
    symbol: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "Start date yyyy-mm-dd"],
    end_date: Annotated[str, "End date yyyy-mm-dd"],
) -> str:
    """Get technical indicators for a stock."""
    try:
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        if df.empty:
            return "No data available"
        stock_df = stockstats_wrap(df)
        indicators = stock_df[['macd', 'rsi_14', 'boll', 'boll_ub', 'boll_lb', 'close_50_sma', 'close_200_sma']]
        return indicators.tail(10).to_csv()
    except Exception as e:
        return f"Error: {e}"


@tool
def get_finnhub_news(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "Start date yyyy-mm-dd"],
    end_date: Annotated[str, "End date yyyy-mm-dd"]
) -> str:
    """Get company news from Finnhub."""
    try:
        client = finnhub.Client(api_key=Config.FINNHUB_API_KEY)
        news = client.company_news(ticker, _from=start_date, to=end_date)
        items = [f"Headline: {n['headline']}\nSummary: {n['summary']}" for n in news[:5]]
        return "\n\n".join(items) if items else "No news found"
    except Exception as e:
        return f"Error: {e}"


def get_tavily_tool():
    """Get Tavily tool instance."""
    return TavilySearchResults(max_results=3)


@tool
def get_social_sentiment(ticker: Annotated[str, "ticker"], date: Annotated[str, "date"]) -> str:
    """Search for social media sentiment."""
    query = f"social media sentiment {ticker} stock {date}"
    tavily = get_tavily_tool()
    return str(tavily.invoke({"query": query}))


@tool
def get_fundamental_analysis(ticker: Annotated[str, "ticker"], date: Annotated[str, "date"]) -> str:
    """Search for fundamental analysis."""
    query = f"fundamental analysis {ticker} stock {date}"
    tavily = get_tavily_tool()
    return str(tavily.invoke({"query": query}))


@tool
def get_macro_news(date: Annotated[str, "date"]) -> str:
    """Search for macroeconomic news."""
    query = f"macroeconomic news market trends {date}"
    tavily = get_tavily_tool()
    return str(tavily.invoke({"query": query}))


# ============================================================================
# AGENT CREATION FACTORY
# ============================================================================

def create_analyst_agent(llm, system_msg, tools, output_field):
    """Factory to create analyst agents."""
    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are a helpful AI assistant collaborating with others. "
         "Use tools to gather data and create a comprehensive report. "
         "Current date: {current_date}. Ticker: {ticker}. "
         "Available tools: {tool_names}.\n\n" + system_msg),
        MessagesPlaceholder(variable_name="messages"),
    ])
    prompt = prompt.partial(tool_names=", ".join([t.name for t in tools]))
    chain = prompt | llm.bind_tools(tools)

    def node(state):
        result = chain.invoke({
            "messages": state["messages"],
            "current_date": state["trade_date"],
            "ticker": state["company_of_interest"]
        })
        output = {"messages": [result]}
        if not result.tool_calls:
            output[output_field] = result.content
        return output

    return node


def create_debate_agent(llm, memory, role_prompt, agent_name, is_bull=True):
    """Create bull or bear debate agent."""
    def node(state):
        debate = state["investment_debate_state"]
        situation = f"Market: {state.get('market_report', '')[:200]}\nSentiment: {state.get('sentiment_report', '')[:200]}"

        # Get memories
        memories = memory.get_memories(situation, n_matches=2) if memory else []
        memory_str = "\n".join([m['recommendation'] for m in memories]) if memories else "No past memories"

        prompt = f"""{role_prompt}

Current Analysis:
Market: {state.get('market_report', 'N/A')[:300]}
Sentiment: {state.get('sentiment_report', 'N/A')[:300]}
News: {state.get('news_report', 'N/A')[:300]}
Fundamentals: {state.get('fundamentals_report', 'N/A')[:300]}

Debate History: {debate['history'][-1000:]}
Opponent's Last: {debate['current_response'][-500:]}
Past Lessons: {memory_str}

Present your argument:"""

        response = llm.invoke([HumanMessage(content=prompt)])
        argument = f"{agent_name}: {response.content}"

        new_debate = debate.copy()
        new_debate['history'] += "\n" + argument
        if is_bull:
            new_debate['bull_history'] += "\n" + argument
        else:
            new_debate['bear_history'] += "\n" + argument
        new_debate['current_response'] = argument
        new_debate['count'] += 1

        return {"investment_debate_state": new_debate}

    return node


def create_research_manager(llm, memory):
    """Create research manager agent."""
    def node(state):
        debate = state["investment_debate_state"]
        prompt = f"""As Research Manager, review the Bull vs Bear debate and make a decision.

Debate History:
{debate['history']}

Provide a clear recommendation (Buy, Sell, or Hold) with detailed reasoning and an investment plan."""

        response = llm.invoke([HumanMessage(content=prompt)])
        return {"investment_plan": response.content}

    return node


def create_trader(llm, memory):
    """Create trader agent."""
    def node(state):
        prompt = f"""You are a trader. Create a concrete trading plan based on:

Investment Plan: {state['investment_plan']}

End with: FINAL TRANSACTION PROPOSAL: **BUY/SELL/HOLD**"""

        response = llm.invoke([HumanMessage(content=prompt)])
        return {"trader_investment_plan": response.content, "sender": "Trader"}

    return node


def create_risk_analyst(llm, role, name):
    """Create risk analyst agent."""
    def node(state):
        risk = state["risk_debate_state"]

        prompt = f"""{role}

Trader's Plan: {state['trader_investment_plan']}
Discussion: {risk['history'][-1000:]}

Provide your perspective:"""

        response = llm.invoke([HumanMessage(content=prompt)]).content

        new_risk = risk.copy()
        new_risk['history'] += f"\n{name}: {response}"
        new_risk['latest_speaker'] = name
        if name == "Risky": new_risk['current_risky_response'] = response
        elif name == "Safe": new_risk['current_safe_response'] = response
        else: new_risk['current_neutral_response'] = response
        new_risk['count'] += 1

        return {"risk_debate_state": new_risk}

    return node


def create_portfolio_manager(llm, memory):
    """Create portfolio manager agent."""
    def node(state):
        risk = state["risk_debate_state"]

        prompt = f"""As Portfolio Manager, make the final decision.

Trader's Plan: {state['trader_investment_plan']}
Risk Discussion: {risk['history']}

Provide final decision: Buy, Sell, or Hold with brief justification."""

        response = llm.invoke([HumanMessage(content=prompt)])
        return {"final_trade_decision": response.content}

    return node


# ============================================================================
# WORKFLOW CONSTRUCTION
# ============================================================================

def build_workflow():
    """Build the complete LangGraph workflow."""
    logger.info("Building workflow...")

    # Initialize LLMs
    deep_llm = ChatOpenAI(
        model=Config.DEEP_THINKING_MODEL,
        temperature=Config.LLM_TEMPERATURE,
        base_url=Config.LLM_BACKEND_URL
    )
    quick_llm = ChatOpenAI(
        model=Config.QUICK_THINKING_MODEL,
        temperature=Config.LLM_TEMPERATURE,
        base_url=Config.LLM_BACKEND_URL
    )

    # Initialize memories
    bull_memory = FinancialSituationMemory("bull", Config)
    bear_memory = FinancialSituationMemory("bear", Config)
    trader_memory = FinancialSituationMemory("trader", Config)
    manager_memory = FinancialSituationMemory("manager", Config)

    # Create separate tool nodes for each analyst (to avoid routing conflicts)
    market_tools = ToolNode([get_yfinance_data, get_technical_indicators])
    social_tools = ToolNode([get_social_sentiment])
    news_tools = ToolNode([get_finnhub_news, get_macro_news])
    fundamentals_tools = ToolNode([get_fundamental_analysis])

    # Create analyst agents
    market_analyst = create_analyst_agent(
        quick_llm,
        "Analyze technical indicators and price action. Create a detailed market report.",
        [get_yfinance_data, get_technical_indicators],
        "market_report"
    )

    social_analyst = create_analyst_agent(
        quick_llm,
        "Analyze social media sentiment. Create a sentiment report.",
        [get_social_sentiment],
        "sentiment_report"
    )

    news_analyst = create_analyst_agent(
        quick_llm,
        "Analyze news and macroeconomic trends. Create a news report.",
        [get_finnhub_news, get_macro_news],
        "news_report"
    )

    fundamentals_analyst = create_analyst_agent(
        quick_llm,
        "Analyze company fundamentals. Create a fundamentals report.",
        [get_fundamental_analysis],
        "fundamentals_report"
    )

    # Create debate agents
    bull_agent = create_debate_agent(quick_llm, bull_memory,
        "You are Bull Analyst. Argue FOR investing. Focus on growth, opportunities, positive indicators.",
        "Bull", is_bull=True)

    bear_agent = create_debate_agent(quick_llm, bear_memory,
        "You are Bear Analyst. Argue AGAINST investing. Focus on risks, challenges, negative indicators.",
        "Bear", is_bull=False)

    research_manager = create_research_manager(deep_llm, manager_memory)

    # Create trading agents
    trader = create_trader(quick_llm, trader_memory)

    risky_analyst = create_risk_analyst(quick_llm,
        "You are Risky Risk Analyst. Advocate for bold, high-reward strategies.", "Risky")
    safe_analyst = create_risk_analyst(quick_llm,
        "You are Safe Risk Analyst. Prioritize capital preservation and low volatility.", "Safe")
    neutral_analyst = create_risk_analyst(quick_llm,
        "You are Neutral Risk Analyst. Provide balanced perspective weighing risks and rewards.", "Neutral")

    portfolio_manager = create_portfolio_manager(deep_llm, manager_memory)

    # Message clearing node
    def clear_messages(state):
        return {"messages": [RemoveMessage(id=m.id) for m in state["messages"]] + [HumanMessage(content="Continue")]}

    # Conditional logic
    def should_continue_analyst(state):
        return "tools" if tools_condition(state) == "tools" else "continue"

    def should_continue_debate(state):
        if state["investment_debate_state"]["count"] >= 2 * Config.MAX_DEBATE_ROUNDS:
            return "Research Manager"
        return "Bear" if state["investment_debate_state"]["current_response"].startswith("Bull") else "Bull"

    def should_continue_risk(state):
        if state["risk_debate_state"]["count"] >= 3 * Config.MAX_RISK_DISCUSS_ROUNDS:
            return "Portfolio Manager"
        speaker = state["risk_debate_state"]["latest_speaker"]
        if speaker == "Risky": return "Safe"
        if speaker == "Safe": return "Neutral"
        return "Risky"

    # Build graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("Market Analyst", market_analyst)
    workflow.add_node("Social Analyst", social_analyst)
    workflow.add_node("News Analyst", news_analyst)
    workflow.add_node("Fundamentals Analyst", fundamentals_analyst)
    workflow.add_node("market_tools", market_tools)
    workflow.add_node("social_tools", social_tools)
    workflow.add_node("news_tools", news_tools)
    workflow.add_node("fundamentals_tools", fundamentals_tools)
    workflow.add_node("Clear Msgs", clear_messages)
    workflow.add_node("Bull", bull_agent)
    workflow.add_node("Bear", bear_agent)
    workflow.add_node("Research Manager", research_manager)
    workflow.add_node("Trader", trader)
    workflow.add_node("Risky", risky_analyst)
    workflow.add_node("Safe", safe_analyst)
    workflow.add_node("Neutral", neutral_analyst)
    workflow.add_node("Portfolio Manager", portfolio_manager)

    # Define flow
    workflow.set_entry_point("Market Analyst")

    # Analyst flow - each analyst has its own tool node
    workflow.add_conditional_edges("Market Analyst", should_continue_analyst,
                                  {"tools": "market_tools", "continue": "Clear Msgs"})
    workflow.add_edge("market_tools", "Market Analyst")
    workflow.add_edge("Clear Msgs", "Social Analyst")

    workflow.add_conditional_edges("Social Analyst", should_continue_analyst,
                                  {"tools": "social_tools", "continue": "News Analyst"})
    workflow.add_edge("social_tools", "Social Analyst")

    workflow.add_conditional_edges("News Analyst", should_continue_analyst,
                                  {"tools": "news_tools", "continue": "Fundamentals Analyst"})
    workflow.add_edge("news_tools", "News Analyst")

    workflow.add_conditional_edges("Fundamentals Analyst", should_continue_analyst,
                                  {"tools": "fundamentals_tools", "continue": "Bull"})
    workflow.add_edge("fundamentals_tools", "Fundamentals Analyst")

    # Debate flow
    workflow.add_conditional_edges("Bull", should_continue_debate)
    workflow.add_conditional_edges("Bear", should_continue_debate)
    workflow.add_edge("Research Manager", "Trader")

    # Risk flow
    workflow.add_edge("Trader", "Risky")
    workflow.add_conditional_edges("Risky", should_continue_risk)
    workflow.add_conditional_edges("Safe", should_continue_risk)
    workflow.add_conditional_edges("Neutral", should_continue_risk)

    workflow.add_edge("Portfolio Manager", END)

    return workflow.compile()


# ============================================================================
# EVALUATION
# ============================================================================

def extract_signal(decision_text: str) -> str:
    """Extract BUY/SELL/HOLD signal from text."""
    text_upper = decision_text.upper()
    if "BUY" in text_upper:
        return "BUY"
    elif "SELL" in text_upper:
        return "SELL"
    elif "HOLD" in text_upper:
        return "HOLD"
    return "UNCLEAR"


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_analysis(ticker: str, trade_date: Optional[str] = None) -> dict:
    """Run the complete trading analysis."""

    # Default to yesterday
    if not trade_date:
        trade_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    console.print(f"\n[bold cyan]Analyzing {ticker} for {trade_date}[/bold cyan]\n")

    # Create initial state
    state = create_initial_state(ticker, trade_date)

    # Build workflow
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
        task = progress.add_task("Building workflow...", total=None)
        graph = build_workflow()
        progress.update(task, completed=True)

    # Execute workflow
    console.print("[bold green]Executing multi-agent analysis...[/bold green]\n")

    final_state = None
    step_count = 0

    for chunk in graph.stream(state, {"recursion_limit": Config.MAX_RECURSION_LIMIT}):
        node_name = list(chunk.keys())[0]
        step_count += 1
        console.print(f"[dim]Step {step_count}: {node_name}[/dim]")
        final_state = chunk[node_name]

    console.print(f"\n[bold green]✓ Analysis complete ({step_count} steps)[/bold green]\n")

    # Extract results
    signal = extract_signal(final_state.get("final_trade_decision", ""))

    return {
        "ticker": ticker,
        "trade_date": trade_date,
        "signal": signal,
        "market_report": final_state.get("market_report", ""),
        "sentiment_report": final_state.get("sentiment_report", ""),
        "news_report": final_state.get("news_report", ""),
        "fundamentals_report": final_state.get("fundamentals_report", ""),
        "investment_plan": final_state.get("investment_plan", ""),
        "trader_plan": final_state.get("trader_investment_plan", ""),
        "final_decision": final_state.get("final_trade_decision", ""),
        "full_state": final_state
    }


def display_results(result: dict):
    """Display analysis results in a nice format."""
    console.print("\n" + "="*80)
    console.print(f"[bold]TRADING ANALYSIS RESULTS[/bold]")
    console.print("="*80)

    console.print(f"\n[bold cyan]Ticker:[/bold cyan] {result['ticker']}")
    console.print(f"[bold cyan]Date:[/bold cyan] {result['trade_date']}")
    console.print(f"[bold cyan]Signal:[/bold cyan] [bold yellow]{result['signal']}[/bold yellow]\n")

    console.print("[bold]Market Analysis:[/bold]")
    console.print(Markdown(result['market_report'][:500] + "..." if len(result['market_report']) > 500 else result['market_report']))

    console.print("\n[bold]Sentiment Analysis:[/bold]")
    console.print(Markdown(result['sentiment_report'][:500] + "..." if len(result['sentiment_report']) > 500 else result['sentiment_report']))

    console.print("\n[bold]Investment Plan:[/bold]")
    console.print(Markdown(result['investment_plan'][:800] + "..." if len(result['investment_plan']) > 800 else result['investment_plan']))

    console.print("\n[bold]Final Decision:[/bold]")
    console.print(Markdown(result['final_decision']))

    console.print("\n" + "="*80 + "\n")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Agent Trading System")
    parser.add_argument("ticker", type=str, help="Stock ticker symbol (e.g., NVDA)")
    parser.add_argument("--date", type=str, default=None, help="Trade date (YYYY-MM-DD)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--show-config", action="store_true", help="Show configuration")

    args = parser.parse_args()

    try:
        # Setup configuration FIRST (loads environment variables)
        Config.setup()
        setup_logging("DEBUG" if args.debug else Config.LOG_LEVEL)

        if args.show_config:
            Config.display()

        # Validate
        Config.validate()

        # Run analysis
        result = run_analysis(args.ticker, args.date)

        # Display results
        display_results(result)

        return 0

    except KeyboardInterrupt:
        console.print("\n[yellow]Analysis interrupted by user[/yellow]")
        return 130
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
