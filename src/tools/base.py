"""Base tool interface."""

from abc import ABC, abstractmethod
from typing import Any, Optional
from functools import wraps
import time

from ..core.exceptions import ToolError
from ..core.logging_config import get_logger

logger = get_logger(__name__)


def with_retry(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator for retrying failed operations.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"All {max_retries} attempts failed")

            raise ToolError(f"Operation failed after {max_retries} attempts") from last_exception

        return wrapper
    return decorator


class BaseTool(ABC):
    """Base class for all tools."""

    def __init__(self, name: str, description: str):
        """
        Initialize tool.

        Args:
            name: Tool name
            description: Tool description
        """
        self.name = name
        self.description = description

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute the tool.

        Args:
            **kwargs: Tool-specific arguments

        Returns:
            Tool result
        """
        pass

    def __call__(self, **kwargs) -> Any:
        """Make tool callable."""
        return self.execute(**kwargs)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
