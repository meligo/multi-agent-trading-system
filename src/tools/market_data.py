"""Market data fetching tool."""

import yfinance as yf
from typing import Annotated
from langchain_core.tools import tool

from ..core.exceptions import DataFetchError
from ..core.logging_config import get_logger
from .base import with_retry

logger = get_logger(__name__)


@tool
@with_retry(max_retries=3, delay=1.0)
def get_yfinance_data(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve the stock price data for a given ticker symbol from Yahoo Finance."""
    try:
        logger.info(f"Fetching YFinance data for {symbol} from {start_date} to {end_date}")
        ticker = yf.Ticker(symbol.upper())
        data = ticker.history(start=start_date, end=end_date)

        if data.empty:
            return f"No data found for symbol '{symbol}' between {start_date} and {end_date}"

        return data.to_csv()
    except Exception as e:
        logger.error(f"Error fetching Yahoo Finance data: {e}")
        raise DataFetchError(f"Error fetching Yahoo Finance data: {e}")
