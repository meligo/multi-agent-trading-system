"""Custom exceptions for the trading system."""


class TradingSystemError(Exception):
    """Base exception for all trading system errors."""
    pass


class ConfigurationError(TradingSystemError):
    """Configuration related errors."""
    pass


class AgentError(TradingSystemError):
    """Agent execution errors."""
    pass


class ToolError(TradingSystemError):
    """Tool execution errors."""
    pass


class DataFetchError(ToolError):
    """Data fetching errors."""
    pass


class MemoryError(TradingSystemError):
    """Memory system errors."""
    pass


class OrchestrationError(TradingSystemError):
    """Orchestration and workflow errors."""
    pass


class ValidationError(TradingSystemError):
    """Input validation errors."""
    pass


class BacktestingError(TradingSystemError):
    """Backtesting errors."""
    pass
