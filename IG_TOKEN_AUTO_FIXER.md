# IG Markets Token Auto-Fixer

## Problem

Your system gets `trading_ig.rest.TokenInvalidException` errors repeatedly because:
1. IG Markets session tokens expire after ~6 hours
2. The current refresh mechanism detects the error but fails to refresh
3. Every subsequent API call also fails

## Root Cause

The `trading_ig` library's automatic refresh doesn't always work reliably because:
- Network issues during refresh
- Race conditions (multiple threads trying to refresh simultaneously)
- The refresh itself can throw TokenInvalidException

## Solution: Decorator-Based Auto-Fixer

Add this to your `ig_trader.py` file (or wherever you have your IG trading code):

```python
import functools
import time
import logging
from trading_ig.rest import TokenInvalidException

logger = logging.getLogger(__name__)

def auto_refresh_token(max_retries=3, retry_delay=2):
    """
    Decorator to automatically handle TokenInvalidException by refreshing the session.

    Usage:
        @auto_refresh_token()
        def my_api_method(self):
            return self.ig_service.fetch_open_positions()

    Args:
        max_retries: Maximum number of refresh attempts
        retry_delay: Seconds to wait between retries
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            attempts = 0
            last_exception = None

            while attempts < max_retries:
                try:
                    # Try the API call
                    return func(self, *args, **kwargs)

                except TokenInvalidException as e:
                    attempts += 1
                    last_exception = e

                    logger.warning(f"🔄 TokenInvalidException on attempt {attempts}/{max_retries}")

                    if attempts >= max_retries:
                        logger.error(f"❌ Failed to refresh token after {max_retries} attempts")
                        raise

                    try:
                        # Force session refresh
                        logger.info(f"🔐 Refreshing IG session (attempt {attempts}/{max_retries})...")

                        # Close existing session
                        try:
                            self.ig_service.logout()
                        except:
                            pass  # Ignore logout errors

                        # Wait before reconnecting
                        time.sleep(retry_delay)

                        # Create fresh session
                        self.ig_service.create_session()

                        logger.info("✅ Session refreshed successfully")

                        # Wait a bit before retrying the original call
                        time.sleep(1)

                    except Exception as refresh_error:
                        logger.error(f"❌ Session refresh failed: {refresh_error}")

                        if attempts >= max_retries:
                            raise

                        # Exponential backoff
                        wait_time = retry_delay * (2 ** (attempts - 1))
                        logger.info(f"⏳ Waiting {wait_time}s before next attempt...")
                        time.sleep(wait_time)

            # If we get here, all retries failed
            raise last_exception

        return wrapper
    return decorator
```

## How to Apply It

### Step 1: Add the decorator to all IG API methods

```python
class IGTrader:
    def __init__(self, ...):
        # ... existing init code ...
        pass

    @auto_refresh_token(max_retries=3, retry_delay=2)
    def get_open_positions(self):
        """Fetch open positions with automatic token refresh."""
        try:
            response = self.ig_service.fetch_open_positions()
            return response['positions']
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []

    @auto_refresh_token(max_retries=3, retry_delay=2)
    def get_account_info(self):
        """Fetch account info with automatic token refresh."""
        try:
            response = self.ig_service.fetch_accounts()
            return response['accounts'][0] if response else None
        except Exception as e:
            logger.error(f"Failed to fetch account info: {e}")
            return None

    @auto_refresh_token(max_retries=3, retry_delay=2)
    def open_position(self, epic, direction, size, stop_distance, limit_distance):
        """Open position with automatic token refresh."""
        try:
            response = self.ig_service.create_open_position(
                epic=epic,
                direction=direction,
                currency_code='EUR',
                order_type='MARKET',
                expiry='DFB',
                force_open='false',
                guaranteed_stop='false',
                size=size,
                level=None,
                limit_distance=limit_distance,
                limit_level=None,
                stop_distance=stop_distance,
                stop_level=None
            )
            return response
        except Exception as e:
            logger.error(f"Failed to open position: {e}")
            raise
```

### Step 2: Alternative - Simpler Session Refresh

If the decorator is too complex, use a simple helper method:

```python
class IGTrader:
    def _ensure_session(self):
        """Ensure IG session is valid, refresh if needed."""
        try:
            # Test if session is valid
            self.ig_service.fetch_accounts()
        except TokenInvalidException:
            logger.warning("🔄 Session expired, refreshing...")
            try:
                self.ig_service.logout()
            except:
                pass
            time.sleep(2)
            self.ig_service.create_session()
            logger.info("✅ Session refreshed")
        except Exception as e:
            logger.error(f"Session check failed: {e}")

    def get_open_positions(self):
        """Fetch open positions with session check."""
        self._ensure_session()  # Check/refresh before API call

        try:
            response = self.ig_service.fetch_open_positions()
            return response['positions']
        except TokenInvalidException:
            # One more try after refresh
            logger.warning("🔄 Token still invalid, retrying once...")
            self._ensure_session()
            response = self.ig_service.fetch_open_positions()
            return response['positions']
        except Exception as e:
            logger.error(f"Failed to fetch positions: {e}")
            return []
```

### Step 3: Proactive Session Refresh

Add a background thread to refresh the session every 5 hours:

```python
import threading

class IGTrader:
    def __init__(self, ...):
        # ... existing init ...

        # Start proactive session refresh
        self._start_session_refresh_thread()

    def _start_session_refresh_thread(self):
        """Start background thread to refresh session every 5 hours."""
        def refresh_loop():
            while True:
                try:
                    # Sleep for 5 hours (token expires in 6)
                    time.sleep(5 * 60 * 60)

                    logger.info("🔄 Proactive session refresh (5 hour timer)")

                    # Logout and re-login
                    try:
                        self.ig_service.logout()
                    except:
                        pass

                    time.sleep(2)
                    self.ig_service.create_session()

                    logger.info("✅ Proactive session refresh complete")

                except Exception as e:
                    logger.error(f"❌ Proactive refresh failed: {e}")

        thread = threading.Thread(target=refresh_loop, daemon=True)
        thread.start()
        logger.info("✅ Proactive session refresh thread started")
```

## Testing the Fix

```python
# Test the auto-refresh in isolation
trader = IGTrader(...)

# This should auto-recover even if token is invalid
positions = trader.get_open_positions()  # Should work
account = trader.get_account_info()     # Should work
```

## Expected Behavior After Fix

```
🔄 TokenInvalidException on attempt 1/3
🔐 Refreshing IG session (attempt 1/3)...
✅ Session refreshed successfully
✅ get_open_positions succeeded
📊 Position check: 0/20 open (20 slots available)
```

Instead of:
```
Invalid session token, triggering refresh...
❌ Failed to fetch positions:
TokenInvalidException
❌ Failed to fetch account info:
TokenInvalidException
```

## Additional Recommendations

1. **Add session health monitoring**:
   ```python
   def _log_session_health(self):
       try:
           # Try a lightweight API call
           self.ig_service.fetch_accounts()
           logger.info("✅ Session health: OK")
           return True
       except:
           logger.warning("⚠️  Session health: DEGRADED")
           return False
   ```

2. **Log session creation timestamps**:
   ```python
   self.session_created_at = datetime.now()
   logger.info(f"🔐 Session created at {self.session_created_at}")
   ```

3. **Add exponential backoff** for retry delays:
   ```python
   retry_delays = [2, 5, 10]  # seconds
   for attempt, delay in enumerate(retry_delays):
       try:
           return self._api_call()
       except:
           time.sleep(delay)
   ```

## Root Cause of Your Current Failure

Looking at your logs, the issue is that **the refresh itself is failing**. This usually means:

1. **Credentials issue**: Username/password/API key expired or wrong
2. **Network issue**: Can't reach IG servers during refresh
3. **Account locked**: Too many failed login attempts
4. **Demo account expired**: IG demo accounts expire after 30 days

Check:
```python
# Verify credentials are loaded
print(f"Username: {self.username[:3]}***")
print(f"API Key: {self.api_key[:8]}***")
print(f"Account Type: {self.account_type}")

# Test basic login
try:
    self.ig_service.create_session()
    print("✅ Login successful")
except Exception as e:
    print(f"❌ Login failed: {e}")
```

## Quick Fix Without Code Changes

If you can't modify the code right now:

1. **Restart the trading system** - Gets a fresh token
2. **Check credentials** - Verify username/password/API key in `.env`
3. **Check demo account** - IG demo accounts expire after 30 days
4. **Reduce analysis frequency** - Fewer API calls = less token stress

---

**Version**: 1.0
**Last Updated**: November 2025
**Applies To**: IG Markets REST API (trading_ig library)
