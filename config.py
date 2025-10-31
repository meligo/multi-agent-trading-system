"""
Single configuration file for the entire trading system.
All settings, API keys, and parameters are managed here.
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """Unified configuration for the trading system."""

    # ============================================================================
    # API KEYS (from environment variables)
    # ============================================================================
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    FINNHUB_API_KEY: str = os.getenv("FINNHUB_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")

    # ============================================================================
    # LLM CONFIGURATION
    # ============================================================================
    LLM_PROVIDER: str = "openai"
    DEEP_THINKING_MODEL: str = "gpt-4o"  # For complex reasoning
    QUICK_THINKING_MODEL: str = "gpt-4o-mini"  # For fast operations
    LLM_TEMPERATURE: float = 0.1
    LLM_BACKEND_URL: str = "https://api.openai.com/v1"
    LLM_TIMEOUT: int = 60

    # ============================================================================
    # DEBATE SETTINGS
    # ============================================================================
    MAX_DEBATE_ROUNDS: int = 2  # Bull vs Bear debate rounds
    MAX_RISK_DISCUSS_ROUNDS: int = 1  # Risk team discussion rounds

    # ============================================================================
    # TOOL SETTINGS
    # ============================================================================
    ONLINE_TOOLS: bool = True  # Use live APIs vs cached data
    CACHE_ENABLED: bool = True
    CACHE_TTL: int = 3600  # Cache time-to-live in seconds
    DATA_CACHE_DIR: str = "./data_cache"
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0

    # ============================================================================
    # MEMORY CONFIGURATION
    # ============================================================================
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    MAX_MEMORIES: int = 100
    SIMILARITY_THRESHOLD: float = 0.7
    MEMORY_PERSISTENCE_DIR: str = "./memory_db"

    # ============================================================================
    # OBSERVABILITY
    # ============================================================================
    LANGSMITH_ENABLED: bool = False  # Disabled to avoid warnings
    LANGSMITH_PROJECT: str = "Production-Trading-System"
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    LOG_FORMAT: str = "json"  # json or text
    LOG_FILE: Optional[str] = None  # Set to enable file logging

    # ============================================================================
    # SYSTEM SETTINGS
    # ============================================================================
    MAX_RECURSION_LIMIT: int = 100
    RESULTS_DIR: str = "./results"

    # ============================================================================
    # BACKTESTING (for future use)
    # ============================================================================
    INITIAL_CAPITAL: float = 100000.0
    COMMISSION: float = 0.001
    SLIPPAGE: float = 0.0005
    RISK_FREE_RATE: float = 0.02

    @classmethod
    def setup(cls):
        """Setup configuration and create necessary directories."""
        # Create directories
        Path(cls.DATA_CACHE_DIR).mkdir(parents=True, exist_ok=True)
        Path(cls.MEMORY_PERSISTENCE_DIR).mkdir(parents=True, exist_ok=True)
        Path(cls.RESULTS_DIR).mkdir(parents=True, exist_ok=True)

        # Setup LangSmith
        if cls.LANGSMITH_ENABLED and cls.LANGSMITH_API_KEY:
            os.environ["LANGSMITH_TRACING"] = "true"
            os.environ["LANGSMITH_PROJECT"] = cls.LANGSMITH_PROJECT
            os.environ["LANGSMITH_API_KEY"] = cls.LANGSMITH_API_KEY

        # Set API keys in environment (for libraries that read from env)
        if cls.OPENAI_API_KEY:
            os.environ["OPENAI_API_KEY"] = cls.OPENAI_API_KEY
        if cls.FINNHUB_API_KEY:
            os.environ["FINNHUB_API_KEY"] = cls.FINNHUB_API_KEY
        if cls.TAVILY_API_KEY:
            os.environ["TAVILY_API_KEY"] = cls.TAVILY_API_KEY

    @classmethod
    def validate(cls):
        """Validate that required configuration is present."""
        required_keys = {
            "OPENAI_API_KEY": cls.OPENAI_API_KEY,
            "FINNHUB_API_KEY": cls.FINNHUB_API_KEY,
            "TAVILY_API_KEY": cls.TAVILY_API_KEY,
        }

        missing = [key for key, value in required_keys.items() if not value]

        if missing:
            raise ValueError(
                f"Missing required API keys: {', '.join(missing)}. "
                "Please set them as environment variables."
            )

    @classmethod
    def display(cls):
        """Display current configuration (hiding sensitive data)."""
        print("\n" + "="*60)
        print("TRADING SYSTEM CONFIGURATION")
        print("="*60)
        print(f"LLM Provider: {cls.LLM_PROVIDER}")
        print(f"Deep Thinking Model: {cls.DEEP_THINKING_MODEL}")
        print(f"Quick Thinking Model: {cls.QUICK_THINKING_MODEL}")
        print(f"Temperature: {cls.LLM_TEMPERATURE}")
        print(f"\nDebate Rounds: {cls.MAX_DEBATE_ROUNDS}")
        print(f"Risk Discussion Rounds: {cls.MAX_RISK_DISCUSS_ROUNDS}")
        print(f"\nOnline Tools: {cls.ONLINE_TOOLS}")
        print(f"Cache Enabled: {cls.CACHE_ENABLED}")
        print(f"Max Retries: {cls.MAX_RETRIES}")
        print(f"\nMemory Max: {cls.MAX_MEMORIES}")
        print(f"Similarity Threshold: {cls.SIMILARITY_THRESHOLD}")
        print(f"\nLangSmith Enabled: {cls.LANGSMITH_ENABLED}")
        print(f"Log Level: {cls.LOG_LEVEL}")
        print(f"\nAPI Keys Status:")
        print(f"  OpenAI: {'✓ Set' if cls.OPENAI_API_KEY else '✗ Missing'}")
        print(f"  Finnhub: {'✓ Set' if cls.FINNHUB_API_KEY else '✗ Missing'}")
        print(f"  Tavily: {'✓ Set' if cls.TAVILY_API_KEY else '✗ Missing'}")
        print(f"  LangSmith: {'✓ Set' if cls.LANGSMITH_API_KEY else '✗ Missing'}")
        print("="*60 + "\n")
