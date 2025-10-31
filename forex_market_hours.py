"""
Forex Market Hours Detection

Handles market open/close times and provides intelligent sleeping
during weekends when forex markets are closed.

Forex Hours: Sunday 5 PM EST - Friday 5 PM EST
"""

from datetime import datetime, timedelta
import pytz
import os
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class ForexMarketHours:
    """
    Manages forex market hours and provides market status checks.
    
    Forex markets operate:
    - Open: Sunday 5:00 PM EST (22:00 UTC)
    - Close: Friday 5:00 PM EST (22:00 UTC)
    - Closed: Friday 5 PM - Sunday 5 PM (48 hours)
    """
    
    # Market timezone
    MARKET_TZ = pytz.timezone('America/New_York')
    
    # Market hours
    MARKET_OPEN_HOUR = 17  # 5 PM
    MARKET_OPEN_DAY = 6     # Sunday (0=Monday, 6=Sunday)
    MARKET_CLOSE_HOUR = 17  # 5 PM
    MARKET_CLOSE_DAY = 4    # Friday
    
    def __init__(self, override_enabled: bool = None):
        """
        Initialize market hours manager.
        
        Args:
            override_enabled: If True, always report market as open (for testing)
                            If None, uses FOREX_IGNORE_MARKET_HOURS env var
        """
        if override_enabled is None:
            # Check environment variable
            override_enabled = os.getenv('FOREX_IGNORE_MARKET_HOURS', 'false').lower() == 'true'
        
        self.override_enabled = override_enabled
        
        if self.override_enabled:
            logger.warning("⚠️  Market hours check DISABLED - system will run 24/7")
    
    def is_market_open(self) -> bool:
        """
        Check if forex market is currently open.
        
        Returns:
            True if market is open, False if closed
        """
        # Override for testing
        if self.override_enabled:
            return True
        
        now_ny = datetime.now(self.MARKET_TZ)
        weekday = now_ny.weekday()
        hour = now_ny.hour
        
        # Saturday = always closed
        if weekday == 5:  # Saturday
            return False
        
        # Sunday before 5 PM EST = closed
        if weekday == 6 and hour < self.MARKET_OPEN_HOUR:
            return False
        
        # Friday after 5 PM EST = closed
        if weekday == 4 and hour >= self.MARKET_CLOSE_HOUR:
            return False
        
        return True
    
    def get_market_status(self) -> dict:
        """
        Get detailed market status information.
        
        Returns:
            Dict with status, next_open, time_until_open, etc.
        """
        is_open = self.is_market_open()
        now_ny = datetime.now(self.MARKET_TZ)
        
        if is_open:
            next_close = self._calculate_next_close(now_ny)
            time_until_close = (next_close - now_ny).total_seconds()
            
            return {
                'is_open': True,
                'current_time': now_ny,
                'next_close': next_close,
                'time_until_close_seconds': time_until_close,
                'time_until_close_human': self._format_duration(time_until_close),
                'override_enabled': self.override_enabled
            }
        else:
            next_open = self._calculate_next_open(now_ny)
            time_until_open = (next_open - now_ny).total_seconds()
            
            return {
                'is_open': False,
                'current_time': now_ny,
                'next_open': next_open,
                'time_until_open_seconds': time_until_open,
                'time_until_open_human': self._format_duration(time_until_open),
                'override_enabled': self.override_enabled
            }
    
    def _calculate_next_open(self, now_ny: datetime) -> datetime:
        """Calculate next market open time."""
        weekday = now_ny.weekday()
        
        # If it's Friday after 5 PM or Saturday, next open is Sunday 5 PM
        if weekday == 4 and now_ny.hour >= self.MARKET_CLOSE_HOUR:
            # Friday after close
            days_until_sunday = 2  # Friday -> Sunday
            next_open = now_ny + timedelta(days=days_until_sunday)
            next_open = next_open.replace(hour=self.MARKET_OPEN_HOUR, minute=0, second=0, microsecond=0)
        elif weekday == 5:
            # Saturday
            days_until_sunday = 1
            next_open = now_ny + timedelta(days=days_until_sunday)
            next_open = next_open.replace(hour=self.MARKET_OPEN_HOUR, minute=0, second=0, microsecond=0)
        elif weekday == 6 and now_ny.hour < self.MARKET_OPEN_HOUR:
            # Sunday before 5 PM
            next_open = now_ny.replace(hour=self.MARKET_OPEN_HOUR, minute=0, second=0, microsecond=0)
        else:
            # Should not reach here if market is closed
            next_open = now_ny
        
        return next_open
    
    def _calculate_next_close(self, now_ny: datetime) -> datetime:
        """Calculate next market close time."""
        weekday = now_ny.weekday()
        
        # Calculate days until Friday
        if weekday < 4:  # Monday-Thursday
            days_until_friday = 4 - weekday
        elif weekday == 4:  # Friday before close
            days_until_friday = 0
        else:  # Weekend (should not be open)
            days_until_friday = 7 - weekday + 4
        
        next_close = now_ny + timedelta(days=days_until_friday)
        next_close = next_close.replace(hour=self.MARKET_CLOSE_HOUR, minute=0, second=0, microsecond=0)
        
        return next_close
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in seconds to human-readable string."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        
        if hours > 24:
            days = hours // 24
            hours = hours % 24
            return f"{days}d {hours}h {minutes}m"
        else:
            return f"{hours}h {minutes}m"
    
    def wait_until_market_open(self, check_interval: int = 3600):
        """
        Block until market opens, with periodic status updates.
        
        Args:
            check_interval: How often to log status (seconds, default 1 hour)
        """
        if self.is_market_open():
            return  # Already open
        
        status = self.get_market_status()
        
        print("=" * 80)
        print("🛑 FOREX MARKET CLOSED")
        print("=" * 80)
        print(f"Current time (NY): {status['current_time'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Next market open: {status['next_open'].strftime('%Y-%m-%d %H:%M:%S %Z')}")
        print(f"Time until open: {status['time_until_open_human']}")
        print("=" * 80)
        print()
        
        import time
        
        while not self.is_market_open():
            status = self.get_market_status()
            time_remaining = status['time_until_open_seconds']
            
            if time_remaining <= 0:
                break
            
            # Sleep for check_interval or remaining time (whichever is less)
            sleep_time = min(check_interval, time_remaining)
            
            print(f"💤 Market closed - resuming in {status['time_until_open_human']}")
            time.sleep(sleep_time)
        
        print()
        print("=" * 80)
        print("✅ FOREX MARKET OPENED - Resuming trading")
        print("=" * 80)
        print()
    
    def get_market_session(self) -> str:
        """
        Get current trading session name.
        
        Returns:
            'CLOSED', 'SYDNEY', 'TOKYO', 'LONDON', 'NEW_YORK', or 'OVERLAP'
        """
        if not self.is_market_open():
            return 'CLOSED'
        
        now_utc = datetime.now(pytz.UTC)
        hour_utc = now_utc.hour
        
        # Trading sessions (UTC):
        # Sydney: 21:00 - 06:00 UTC
        # Tokyo: 23:00 - 08:00 UTC
        # London: 07:00 - 16:00 UTC
        # New York: 12:00 - 21:00 UTC
        
        if 12 <= hour_utc < 16:
            return 'OVERLAP'  # London + New York
        elif 7 <= hour_utc < 12:
            return 'LONDON'
        elif 16 <= hour_utc < 21:
            return 'NEW_YORK'
        elif 21 <= hour_utc or hour_utc < 6:
            return 'SYDNEY'
        elif 23 <= hour_utc or hour_utc < 8:
            return 'TOKYO'
        else:
            return 'UNKNOWN'


# Global instance
_market_hours = None


def get_market_hours() -> ForexMarketHours:
    """Get global market hours instance."""
    global _market_hours
    if _market_hours is None:
        _market_hours = ForexMarketHours()
    return _market_hours


# Test
if __name__ == "__main__":
    print("=" * 80)
    print("FOREX MARKET HOURS TEST")
    print("=" * 80)
    print()
    
    market = ForexMarketHours()
    status = market.get_market_status()
    
    print(f"Current Time (NY): {status['current_time'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')}")
    print(f"Market Open: {'✅ YES' if status['is_open'] else '❌ NO'}")
    print(f"Override Enabled: {status['override_enabled']}")
    print()
    
    if status['is_open']:
        print(f"Market Session: {market.get_market_session()}")
        print(f"Next Close: {status['next_close'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')}")
        print(f"Time Until Close: {status['time_until_close_human']}")
    else:
        print(f"Next Open: {status['next_open'].strftime('%A, %Y-%m-%d %H:%M:%S %Z')}")
        print(f"Time Until Open: {status['time_until_open_human']}")
    
    print()
    print("=" * 80)
    print("✅ Market hours detection working!")
    print("=" * 80)
    print()
    print("💡 To disable market hours check (for testing):")
    print("   export FOREX_IGNORE_MARKET_HOURS=true")
    print()
