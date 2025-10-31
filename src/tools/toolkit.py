"""Unified toolkit interface."""

import os
import finnhub
from typing import List
from langchain_core.tools import BaseTool
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.tools import tool
from typing import Annotated

from ..core.config import Config
from ..core.logging_config import get_logger
from .market_data import get_yfinance_data
from .technical_indicators import get_technical_indicators
from .base import with_retry

logger = get_logger(__name__)


@tool
@with_retry(max_retries=3, delay=1.0)
def get_finnhub_news(
    ticker: Annotated[str, "Stock ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"]
) -> str:
    """Get company news from Finnhub within a date range."""
    try:
        finnhub_client = finnhub.Client(api_key=os.environ.get("FINNHUB_API_KEY"))
        news_list = finnhub_client.company_news(ticker, _from=start_date, to=end_date)

        news_items = []
        for news in news_list[:5]:  # Limit to 5 results
            news_items.append(f"Headline: {news['headline']}\nSummary: {news['summary']}")

        return "\n\n".join(news_items) if news_items else "No Finnhub news found."
    except Exception as e:
        logger.error(f"Error fetching Finnhub news: {e}")
        return f"Error fetching Finnhub news: {e}"


class Toolkit:
    """Unified toolkit providing access to all data fetching tools."""

    def __init__(self, config: Config):
        """
        Initialize toolkit.

        Args:
            config: System configuration
        """
        self.config = config

        # Initialize Tavily search tool
        self.tavily_tool = TavilySearchResults(max_results=3)

        # Create specialized search tools
        self._setup_search_tools()

        logger.info("Toolkit initialized with all tools")

    def _setup_search_tools(self):
        """Setup specialized search tools."""

        @tool
        def get_social_media_sentiment(
            ticker: Annotated[str, "Stock ticker symbol"],
            trade_date: Annotated[str, "Date in yyyy-mm-dd format"]
        ) -> str:
            """Performs a live web search for social media sentiment regarding a stock."""
            query = f"social media sentiment and discussions for {ticker} stock around {trade_date}"
            return self.tavily_tool.invoke({"query": query})

        @tool
        def get_fundamental_analysis(
            ticker: Annotated[str, "Stock ticker symbol"],
            trade_date: Annotated[str, "Date in yyyy-mm-dd format"]
        ) -> str:
            """Performs a live web search for recent fundamental analysis of a stock."""
            query = f"fundamental analysis and key financial metrics for {ticker} stock published around {trade_date}"
            return self.tavily_tool.invoke({"query": query})

        @tool
        def get_macroeconomic_news(
            trade_date: Annotated[str, "Date in yyyy-mm-dd format"]
        ) -> str:
            """Performs a live web search for macroeconomic news relevant to the stock market."""
            query = f"macroeconomic news and market trends affecting the stock market on {trade_date}"
            return self.tavily_tool.invoke({"query": query})

        # Store tools as instance attributes
        self.get_social_media_sentiment = get_social_media_sentiment
        self.get_fundamental_analysis = get_fundamental_analysis
        self.get_macroeconomic_news = get_macroeconomic_news

    def get_all_tools(self) -> List[BaseTool]:
        """Get list of all available tools."""
        return [
            get_yfinance_data,
            get_technical_indicators,
            get_finnhub_news,
            self.get_social_media_sentiment,
            self.get_fundamental_analysis,
            self.get_macroeconomic_news,
        ]

    def get_market_tools(self) -> List[BaseTool]:
        """Get tools for market analysis."""
        return [get_yfinance_data, get_technical_indicators]

    def get_news_tools(self) -> List[BaseTool]:
        """Get tools for news analysis."""
        return [get_finnhub_news, self.get_macroeconomic_news]

    def get_sentiment_tools(self) -> List[BaseTool]:
        """Get tools for sentiment analysis."""
        return [self.get_social_media_sentiment]

    def get_fundamentals_tools(self) -> List[BaseTool]:
        """Get tools for fundamental analysis."""
        return [self.get_fundamental_analysis]
