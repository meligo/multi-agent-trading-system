"""Technical indicators calculation tool."""

import yfinance as yf
from typing import Annotated
from langchain_core.tools import tool
from stockstats import wrap as stockstats_wrap

from ..core.exceptions import DataFetchError
from ..core.logging_config import get_logger
from .base import with_retry

logger = get_logger(__name__)


@tool
@with_retry(max_retries=3, delay=1.0)
def get_technical_indicators(
    symbol: Annotated[str, "ticker symbol of the company"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
) -> str:
    """Retrieve key technical indicators for a stock using stockstats library."""
    try:
        logger.info(f"Calculating technical indicators for {symbol}")
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)

        if df.empty:
            return "No data to calculate indicators."

        stock_df = stockstats_wrap(df)
        indicators = stock_df[[
            'macd', 'rsi_14', 'boll', 'boll_ub', 'boll_lb',
            'close_50_sma', 'close_200_sma'
        ]]

        return indicators.tail(10).to_csv()
    except Exception as e:
        logger.error(f"Error calculating technical indicators: {e}")
        raise DataFetchError(f"Error calculating stockstats indicators: {e}")
