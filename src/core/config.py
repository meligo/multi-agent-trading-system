"""Configuration management for the trading system."""

import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from pydantic import BaseModel, Field, validator


class LLMConfig(BaseModel):
    """LLM configuration."""
    provider: str = "openai"
    deep_think_model: str = "gpt-4o"
    quick_think_model: str = "gpt-4o-mini"
    temperature: float = 0.1
    backend_url: str = "https://api.openai.com/v1"
    timeout: int = 60


class DebateConfig(BaseModel):
    """Debate configuration."""
    max_debate_rounds: int = 2
    max_risk_discuss_rounds: int = 1


class ToolConfig(BaseModel):
    """Tool configuration."""
    online_tools: bool = True
    cache_enabled: bool = True
    cache_ttl: int = 3600
    data_cache_dir: str = "./data_cache"
    max_retries: int = 3
    retry_delay: float = 1.0


class MemoryConfig(BaseModel):
    """Memory configuration."""
    embedding_model: str = "text-embedding-3-small"
    max_memories: int = 100
    similarity_threshold: float = 0.7
    persistence_dir: str = "./memory_db"


class ObservabilityConfig(BaseModel):
    """Observability configuration."""
    langsmith_enabled: bool = True
    langsmith_project: str = "Production-Trading-System"
    prometheus_enabled: bool = False
    prometheus_port: int = 9090
    log_level: str = "INFO"


class BacktestingConfig(BaseModel):
    """Backtesting configuration."""
    initial_capital: float = 100000.0
    commission: float = 0.001
    slippage: float = 0.0005
    risk_free_rate: float = 0.02


class Config(BaseModel):
    """Main configuration class."""
    llm: LLMConfig = Field(default_factory=LLMConfig)
    debate: DebateConfig = Field(default_factory=DebateConfig)
    tools: ToolConfig = Field(default_factory=ToolConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)
    backtesting: BacktestingConfig = Field(default_factory=BacktestingConfig)

    # System settings
    max_recur_limit: int = 100
    results_dir: str = "./results"

    @validator("results_dir", "tools")
    def create_directories(cls, v, field):
        """Create directories if they don't exist."""
        if field.name == "results_dir":
            Path(v).mkdir(parents=True, exist_ok=True)
        elif field.name == "tools" and hasattr(v, "data_cache_dir"):
            Path(v.data_cache_dir).mkdir(parents=True, exist_ok=True)
        return v

    class Config:
        """Pydantic config."""
        env_prefix = "TRADING_"


def load_config(config_path: Optional[str] = None, env: str = "default") -> Config:
    """
    Load configuration from YAML file and environment variables.

    Args:
        config_path: Path to config file. If None, uses default locations.
        env: Environment name (default, development, production)

    Returns:
        Config object
    """
    # Default configuration
    config_dict: Dict[str, Any] = {}

    # Load base config
    if config_path:
        config_file = Path(config_path)
    else:
        # Try default locations
        config_file = Path(f"config/{env}.yaml")
        if not config_file.exists():
            config_file = Path("config/default.yaml")

    if config_file.exists():
        with open(config_file, "r") as f:
            config_dict = yaml.safe_load(f) or {}

    # Override with environment variables
    api_keys = {}
    for key in ["OPENAI_API_KEY", "FINNHUB_API_KEY", "TAVILY_API_KEY", "LANGSMITH_API_KEY"]:
        if value := os.getenv(key):
            api_keys[key] = value

    if api_keys:
        config_dict["api_keys"] = api_keys

    # Setup LangSmith if enabled
    if config_dict.get("observability", {}).get("langsmith_enabled", True):
        os.environ["LANGSMITH_TRACING"] = "true"
        if project := config_dict.get("observability", {}).get("langsmith_project"):
            os.environ["LANGSMITH_PROJECT"] = project

    return Config(**config_dict)


def get_config() -> Config:
    """Get the global configuration instance."""
    env = os.getenv("TRADING_ENV", "default")
    return load_config(env=env)
