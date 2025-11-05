"""
IG Token Refresh for Custom IGClient

Automatically handles 401 authentication errors by refreshing the IG session.
Designed for the custom ig_client.py used in the scalping engine.

Usage:
    from ig_token_refresh import auto_refresh_ig_token

    class ScalpingEngine:
        @auto_refresh_ig_token(max_retries=3, retry_delay=2)
        def _execute_trade(self, ...):
            response = self.ig_client.create_position(...)
"""

import functools
import time
import logging
from typing import Callable, Any
from ig_client import IGApiError

logger = logging.getLogger(__name__)


def auto_refresh_ig_token(max_retries: int = 3, retry_delay: float = 2.0) -> Callable:
    """
    Decorator to automatically handle 401 errors by refreshing the IG session.

    This decorator wraps IG API calls (via ig_client.py) and automatically
    refreshes the session if a 401 authentication error is encountered.

    Args:
        max_retries: Maximum number of refresh attempts (default: 3)
        retry_delay: Initial delay in seconds between retries (default: 2.0)
                    Uses exponential backoff: delay * (2 ** attempt)

    Returns:
        Decorator function that wraps the target method

    Example:
        @auto_refresh_ig_token(max_retries=3, retry_delay=2)
        def _execute_trade(self, scalp_setup, position_size):
            response = self.ig_client.create_position(...)
            return response

    Behavior:
        1. Attempts the API call
        2. If IGApiError with status 401:
           - Logs warning
           - Creates new session
           - Retries the original call
        3. Uses exponential backoff for subsequent retries
        4. Raises exception if all retries fail
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> Any:
            attempts = 0
            last_exception = None

            while attempts < max_retries:
                try:
                    # Try the API call
                    result = func(self, *args, **kwargs)

                    # Success! Log if this was a retry
                    if attempts > 0:
                        logger.info(f"✅ {func.__name__} succeeded after {attempts + 1} attempts")

                    return result

                except IGApiError as e:
                    attempts += 1
                    last_exception = e

                    # Only handle 401 auth errors
                    if e.status != 401:
                        logger.error(f"❌ Non-auth error in {func.__name__}: {e}")
                        raise

                    logger.warning(
                        f"🔄 401 Authentication error in {func.__name__} "
                        f"(attempt {attempts}/{max_retries}): {e.error_code}"
                    )

                    if attempts >= max_retries:
                        logger.error(
                            f"❌ Failed to refresh token after {max_retries} attempts in {func.__name__}"
                        )
                        raise

                    try:
                        # Check if ig_client exists
                        if not hasattr(self, 'ig_client') or self.ig_client is None:
                            logger.error(f"❌ No ig_client available for token refresh in {func.__name__}")
                            raise

                        # Get credentials from config or environment
                        from scalping_config import ScalpingConfig
                        import os

                        username = os.getenv('IG_USERNAME')
                        password = os.getenv('IG_PASSWORD')

                        if not username or not password:
                            logger.error(f"❌ Missing IG credentials for token refresh")
                            raise

                        # Refresh the session
                        logger.info(
                            f"🔐 Refreshing IG session for {func.__name__} "
                            f"(attempt {attempts}/{max_retries})..."
                        )

                        # Wait before reconnecting (exponential backoff)
                        wait_time = retry_delay * (2 ** (attempts - 1))
                        logger.debug(f"  Waiting {wait_time:.1f}s before reconnect...")
                        time.sleep(wait_time)

                        # Create fresh session
                        logger.debug("  Creating new session...")
                        self.ig_client.create_session(
                            username=username,
                            password=password
                        )

                        logger.info(f"✅ Session refreshed successfully for {func.__name__}")

                        # Brief pause before retrying
                        time.sleep(0.5)

                    except Exception as refresh_error:
                        logger.error(
                            f"❌ Session refresh failed for {func.__name__}: {refresh_error}"
                        )

                        if attempts >= max_retries:
                            logger.error("   No more retries available, raising exception")
                            raise

                        # Calculate next wait time
                        next_wait = retry_delay * (2 ** attempts)
                        logger.info(f"⏳ Waiting {next_wait:.1f}s before next attempt...")
                        time.sleep(next_wait)

            # If we get here, all retries failed
            logger.error(f"❌ All {max_retries} attempts failed for {func.__name__}")
            raise last_exception

        return wrapper
    return decorator


# Simpler version for methods that don't need full retry logic
def ensure_ig_session(ig_client, username: str, password: str, logger=None) -> bool:
    """
    Simple helper to ensure IG session is valid, refresh if needed.

    Usage:
        if not ensure_ig_session(self.ig_client, username, password):
            # Handle failure

    Args:
        ig_client: The IGClient instance
        username: IG username
        password: IG password
        logger: Optional logger instance

    Returns:
        True if session is valid/refreshed, False if refresh failed
    """
    log = logger or logging.getLogger(__name__)

    try:
        # Test if session is valid with a lightweight call
        ig_client.get_account()
        return True

    except IGApiError as e:
        if e.status == 401:
            log.warning("🔄 Session expired (401), refreshing...")

            try:
                # Wait and reconnect
                time.sleep(2)
                ig_client.create_session(username=username, password=password)

                log.info("✅ Session refreshed")
                return True

            except Exception as refresh_error:
                log.error(f"❌ Session refresh failed: {refresh_error}")
                return False
        else:
            log.error(f"❌ Non-auth API error: {e}")
            return False

    except Exception as e:
        log.error(f"❌ Session check failed: {e}")
        return False


if __name__ == "__main__":
    # Example usage
    print("IG Token Refresh for IGClient")
    print("=" * 50)
    print()
    print("Usage:")
    print("  from ig_token_refresh import auto_refresh_ig_token")
    print()
    print("  class ScalpingEngine:")
    print("      @auto_refresh_ig_token(max_retries=3, retry_delay=2)")
    print("      def _execute_trade(self, scalp_setup, position_size):")
    print("          response = self.ig_client.create_position(...)")
    print("          return response")
    print()
    print("Features:")
    print("  ✅ Automatic token refresh on 401 errors")
    print("  ✅ Exponential backoff for retries")
    print("  ✅ Detailed logging of refresh attempts")
    print("  ✅ Designed for custom ig_client.py")
    print()
