"""
IG API Rate Limiter

Ensures we stay within IG's rate limits:
- Account Overall: 30 requests per minute
- Application Overall: 60 requests per minute
"""

import time
from threading import Lock
from collections import deque
from datetime import datetime, timedelta


class IGRateLimiter:
    """
    Rate limiter for IG API requests.

    Tracks request timestamps and enforces limits.
    """

    def __init__(self, account_limit: int = 30, app_limit: int = 60):
        """
        Initialize rate limiter.

        Args:
            account_limit: Max requests per minute for account (default 30)
            app_limit: Max requests per minute for application (default 60)
        """
        self.account_limit = account_limit
        self.app_limit = app_limit

        # Track request timestamps
        self.account_requests = deque()
        self.app_requests = deque()

        self.lock = Lock()

    def _clean_old_requests(self, request_queue: deque):
        """Remove requests older than 1 minute."""
        cutoff = datetime.now() - timedelta(minutes=1)
        while request_queue and request_queue[0] < cutoff:
            request_queue.popleft()

    def wait_if_needed(self, is_account_request: bool = True):
        """
        Wait if necessary to respect rate limits.

        Args:
            is_account_request: If True, counts against account limit
        """
        with self.lock:
            while True:
                now = datetime.now()

                # Clean old requests
                self._clean_old_requests(self.account_requests)
                self._clean_old_requests(self.app_requests)

                # Check account limit
                if is_account_request and len(self.account_requests) >= self.account_limit:
                    # Wait until oldest request is 1 minute old
                    wait_until = self.account_requests[0] + timedelta(minutes=1)
                    wait_seconds = (wait_until - now).total_seconds()
                    if wait_seconds > 0:
                        # Only print if wait is significant (> 1 second)
                        if wait_seconds > 1.0:
                            print(f"⏳ Rate limit: waiting {wait_seconds:.1f}s (account: {len(self.account_requests)}/{self.account_limit})")
                        time.sleep(wait_seconds + 0.1)
                        continue

                # Check app limit
                if len(self.app_requests) >= self.app_limit:
                    wait_until = self.app_requests[0] + timedelta(minutes=1)
                    wait_seconds = (wait_until - now).total_seconds()
                    if wait_seconds > 0:
                        # Only print if wait is significant (> 1 second)
                        if wait_seconds > 1.0:
                            print(f"⏳ Rate limit: waiting {wait_seconds:.1f}s (app: {len(self.app_requests)}/{self.app_limit})")
                        time.sleep(wait_seconds + 0.1)
                        continue

                # Safe to proceed
                break

            # Record this request
            now = datetime.now()
            if is_account_request:
                self.account_requests.append(now)
            self.app_requests.append(now)

    def get_stats(self) -> dict:
        """Get current rate limiter statistics."""
        with self.lock:
            self._clean_old_requests(self.account_requests)
            self._clean_old_requests(self.app_requests)

            return {
                'account_requests': len(self.account_requests),
                'account_limit': self.account_limit,
                'app_requests': len(self.app_requests),
                'app_limit': self.app_limit,
                'account_remaining': self.account_limit - len(self.account_requests),
                'app_remaining': self.app_limit - len(self.app_requests),
            }


# Global rate limiter instance
_rate_limiter = None


def get_rate_limiter() -> IGRateLimiter:
    """Get global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        # Increased limits - with Tier 1 caching, we rarely hit these
        # IG actual limits: 30 account / 60 app per minute
        _rate_limiter = IGRateLimiter(account_limit=29, app_limit=59)  # Use 29/59 for safety margin
    return _rate_limiter


# Test
if __name__ == "__main__":
    print("="*80)
    print("RATE LIMITER TEST")
    print("="*80)

    limiter = IGRateLimiter(account_limit=5, app_limit=10)

    # Simulate requests
    print("\n🔄 Making 7 requests (limit: 5/minute)...\n")

    for i in range(7):
        print(f"Request {i+1}:")
        limiter.wait_if_needed(is_account_request=True)
        print(f"  ✅ Sent at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
        stats = limiter.get_stats()
        print(f"  📊 Account: {stats['account_requests']}/{stats['account_limit']}, App: {stats['app_requests']}/{stats['app_limit']}")
        print()

    print("✅ Test complete!")
    print("="*80)
