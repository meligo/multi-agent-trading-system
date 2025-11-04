"""
IG Markets Token Auto-Refresh Decorator

Automatically handles TokenInvalidException by refreshing the IG session.
Use this decorator on any method that calls the IG API.

Usage:
    from ig_token_auto_refresh import auto_refresh_token

    class IGTrader:
        @auto_refresh_token(max_retries=3, retry_delay=2)
        def get_open_positions(self):
            return self.ig_service.fetch_open_positions()
"""

import functools
import time
import logging
from typing import Callable, Any
from trading_ig.rest import TokenInvalidException

logger = logging.getLogger(__name__)


def auto_refresh_token(max_retries: int = 3, retry_delay: float = 2.0) -> Callable:
    """
    Decorator to automatically handle TokenInvalidException by refreshing the session.

    This decorator wraps IG API calls and automatically refreshes the session if
    a TokenInvalidException is encountered. It will retry the operation up to
    max_retries times with exponential backoff.

    Args:
        max_retries: Maximum number of refresh attempts (default: 3)
        retry_delay: Initial delay in seconds between retries (default: 2.0)
                    Uses exponential backoff: delay * (2 ** attempt)

    Returns:
        Decorator function that wraps the target method

    Example:
        @auto_refresh_token(max_retries=3, retry_delay=2)
        def get_open_positions(self):
            return self.ig_service.fetch_open_positions()

    Behavior:
        1. Attempts the API call
        2. If TokenInvalidException:
           - Logs out of current session
           - Waits retry_delay seconds
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
                        logger.info(f"✅ {func.__name__} succeeded on attempt {attempts + 1}")

                    return result

                except TokenInvalidException as e:
                    attempts += 1
                    last_exception = e

                    logger.warning(
                        f"🔄 TokenInvalidException in {func.__name__} "
                        f"(attempt {attempts}/{max_retries})"
                    )

                    if attempts >= max_retries:
                        logger.error(
                            f"❌ Failed to refresh token after {max_retries} attempts in {func.__name__}"
                        )
                        raise

                    try:
                        # Force session refresh
                        logger.info(
                            f"🔐 Refreshing IG session for {func.__name__} "
                            f"(attempt {attempts}/{max_retries})..."
                        )

                        # Step 1: Close existing session (ignore errors)
                        try:
                            logger.debug("  Logging out of current session...")
                            self.ig_service.logout()
                        except Exception as logout_error:
                            logger.debug(f"  Logout error (ignored): {logout_error}")

                        # Step 2: Wait before reconnecting
                        wait_time = retry_delay * (2 ** (attempts - 1))  # Exponential backoff
                        logger.debug(f"  Waiting {wait_time:.1f}s before reconnect...")
                        time.sleep(wait_time)

                        # Step 3: Create fresh session
                        logger.debug("  Creating new session...")
                        self.ig_service.create_session()

                        logger.info(f"✅ Session refreshed successfully for {func.__name__}")

                        # Step 4: Brief pause before retrying the original call
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


class SessionHealthMonitor:
    """
    Monitor IG session health and provide proactive refresh.

    Usage:
        monitor = SessionHealthMonitor(ig_service)
        monitor.start_proactive_refresh()  # Refreshes every 5 hours

        if not monitor.check_health():
            monitor.refresh_session()
    """

    def __init__(self, ig_service):
        """
        Initialize session health monitor.

        Args:
            ig_service: The IG service instance (from trading_ig)
        """
        self.ig_service = ig_service
        self.session_created_at = None
        self._refresh_thread = None

    def check_health(self) -> bool:
        """
        Check if the IG session is healthy.

        Returns:
            True if session is healthy, False otherwise
        """
        try:
            # Try a lightweight API call
            self.ig_service.fetch_accounts()
            logger.debug("✅ Session health check: OK")
            return True
        except TokenInvalidException:
            logger.warning("⚠️  Session health check: TOKEN INVALID")
            return False
        except Exception as e:
            logger.warning(f"⚠️  Session health check: ERROR ({e})")
            return False

    def refresh_session(self) -> bool:
        """
        Force a session refresh.

        Returns:
            True if refresh successful, False otherwise
        """
        try:
            logger.info("🔄 Forcing session refresh...")

            # Logout
            try:
                self.ig_service.logout()
            except:
                pass

            # Wait
            time.sleep(2)

            # Re-login
            self.ig_service.create_session()
            self.session_created_at = time.time()

            logger.info("✅ Session refreshed successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Session refresh failed: {e}")
            return False

    def start_proactive_refresh(self, interval_hours: float = 5.0):
        """
        Start a background thread to proactively refresh the session.

        IG tokens typically expire after 6 hours, so refreshing every 5 hours
        ensures the session stays valid.

        Args:
            interval_hours: Hours between refresh attempts (default: 5.0)
        """
        import threading

        if self._refresh_thread and self._refresh_thread.is_alive():
            logger.warning("⚠️  Proactive refresh thread already running")
            return

        def refresh_loop():
            while True:
                try:
                    # Sleep for specified interval
                    sleep_seconds = interval_hours * 60 * 60
                    logger.info(
                        f"⏰ Proactive refresh scheduled in {interval_hours:.1f} hours"
                    )
                    time.sleep(sleep_seconds)

                    logger.info(
                        f"🔄 Proactive session refresh ({interval_hours:.1f} hour timer)"
                    )

                    if self.refresh_session():
                        logger.info("✅ Proactive refresh complete")
                    else:
                        logger.error("❌ Proactive refresh failed (will retry)")

                except Exception as e:
                    logger.error(f"❌ Proactive refresh loop error: {e}")
                    time.sleep(60)  # Wait 1 minute before retrying

        self._refresh_thread = threading.Thread(
            target=refresh_loop,
            daemon=True,
            name="IGSessionRefreshThread"
        )
        self._refresh_thread.start()
        logger.info(
            f"✅ Proactive session refresh thread started (interval: {interval_hours:.1f}h)"
        )


# Convenience function for simple session refresh
def ensure_session(ig_service, logger=None) -> bool:
    """
    Simple helper to ensure IG session is valid, refresh if needed.

    Usage:
        ensure_session(self.ig_service)
        positions = self.ig_service.fetch_open_positions()

    Args:
        ig_service: The IG service instance
        logger: Optional logger instance

    Returns:
        True if session is valid/refreshed, False if refresh failed
    """
    log = logger or logging.getLogger(__name__)

    try:
        # Test if session is valid
        ig_service.fetch_accounts()
        return True

    except TokenInvalidException:
        log.warning("🔄 Session expired, refreshing...")

        try:
            # Logout
            try:
                ig_service.logout()
            except:
                pass

            # Wait and reconnect
            time.sleep(2)
            ig_service.create_session()

            log.info("✅ Session refreshed")
            return True

        except Exception as e:
            log.error(f"❌ Session refresh failed: {e}")
            return False

    except Exception as e:
        log.error(f"❌ Session check failed: {e}")
        return False


if __name__ == "__main__":
    # Example usage
    print("IG Token Auto-Refresh Decorator")
    print("=" * 50)
    print()
    print("Usage:")
    print("  from ig_token_auto_refresh import auto_refresh_token")
    print()
    print("  class IGTrader:")
    print("      @auto_refresh_token(max_retries=3, retry_delay=2)")
    print("      def get_open_positions(self):")
    print("          return self.ig_service.fetch_open_positions()")
    print()
    print("Features:")
    print("  ✅ Automatic token refresh on TokenInvalidException")
    print("  ✅ Exponential backoff for retries")
    print("  ✅ Detailed logging of refresh attempts")
    print("  ✅ Proactive refresh thread (optional)")
    print("  ✅ Session health monitoring")
