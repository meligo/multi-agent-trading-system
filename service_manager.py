"""
Service Manager - Manages all background services for the trading system

Automatically starts and monitors:
1. WebSocket Collector (optional - for Tier 3)
2. Trading Worker
3. Caching services

Usage:
    from service_manager import ServiceManager

    manager = ServiceManager()
    manager.start_all()  # Starts everything

    # Check status
    status = manager.get_status()
"""

import subprocess
import threading
import time
import os
import signal
from typing import Dict, Optional
from datetime import datetime


class ServiceManager:
    """Manages all background services for the trading system."""

    def __init__(self):
        """Initialize service manager."""
        self.services = {}
        self.lock = threading.Lock()

    def start_websocket_collector(self) -> bool:
        """
        Start WebSocket collector in background.

        Returns:
            True if started successfully, False otherwise
        """
        with self.lock:
            # Check if already running
            if 'websocket' in self.services and self._is_process_alive(self.services['websocket']['pid']):
                return True

            try:
                # Check if WebSocket dependencies are available
                try:
                    import trading_ig
                    from lightstreamer.client import LightstreamerClient
                except ImportError:
                    self.services['websocket'] = {
                        'status': 'disabled',
                        'reason': 'Dependencies not installed (trading-ig, lightstreamer-client-lib)',
                        'started_at': None,
                        'pid': None
                    }
                    return False

                # Start WebSocket collector as subprocess
                # Using DEVNULL to prevent output from cluttering dashboard
                process = subprocess.Popen(
                    ['python', 'websocket_collector.py'],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True  # Detach from parent
                )

                # Give it a moment to start
                time.sleep(2)

                # Check if it's still running
                if process.poll() is None:
                    self.services['websocket'] = {
                        'status': 'running',
                        'started_at': datetime.now(),
                        'pid': process.pid,
                        'process': process
                    }
                    return True
                else:
                    self.services['websocket'] = {
                        'status': 'failed',
                        'reason': 'Process terminated immediately',
                        'started_at': None,
                        'pid': None
                    }
                    return False

            except Exception as e:
                self.services['websocket'] = {
                    'status': 'error',
                    'reason': str(e),
                    'started_at': None,
                    'pid': None
                }
                return False

    def stop_websocket_collector(self):
        """Stop WebSocket collector."""
        with self.lock:
            if 'websocket' in self.services:
                service = self.services['websocket']
                if service.get('pid'):
                    try:
                        os.kill(service['pid'], signal.SIGTERM)
                        time.sleep(1)
                        # Force kill if still alive
                        if self._is_process_alive(service['pid']):
                            os.kill(service['pid'], signal.SIGKILL)
                    except:
                        pass

                self.services['websocket'] = {
                    'status': 'stopped',
                    'started_at': None,
                    'pid': None
                }

    def get_status(self) -> Dict:
        """
        Get status of all services.

        Returns:
            Dictionary with service statuses
        """
        with self.lock:
            status = {}

            # WebSocket Collector
            if 'websocket' in self.services:
                ws = self.services['websocket']
                status['websocket'] = {
                    'name': 'WebSocket Collector',
                    'status': ws['status'],
                    'started_at': ws.get('started_at'),
                    'uptime': self._get_uptime(ws.get('started_at')),
                    'reason': ws.get('reason'),
                    'pid': ws.get('pid')
                }
            else:
                status['websocket'] = {
                    'name': 'WebSocket Collector',
                    'status': 'not_started',
                    'started_at': None,
                    'uptime': None,
                    'reason': 'Not initialized',
                    'pid': None
                }

            # Caching services (always active with Tier 1)
            status['caching'] = {
                'name': 'Smart Caching (Tier 1)',
                'status': 'active',
                'started_at': None,
                'uptime': 'Always active',
                'reason': 'Database caching for REST API',
                'cache_hit_rate': self._get_cache_stats()
            }

            return status

    def _is_process_alive(self, pid: Optional[int]) -> bool:
        """Check if a process is still running."""
        if pid is None:
            return False

        try:
            os.kill(pid, 0)  # Signal 0 checks if process exists
            return True
        except OSError:
            return False

    def _get_uptime(self, started_at: Optional[datetime]) -> Optional[str]:
        """Get uptime string."""
        if started_at is None:
            return None

        uptime = datetime.now() - started_at
        hours = uptime.total_seconds() / 3600

        if hours < 1:
            minutes = uptime.total_seconds() / 60
            return f"{int(minutes)}m"
        elif hours < 24:
            return f"{hours:.1f}h"
        else:
            days = hours / 24
            return f"{days:.1f}d"

    def _get_cache_stats(self) -> str:
        """Get cache statistics."""
        try:
            from candle_cache import CandleCache
            cache = CandleCache()
            stats = cache.get_cache_stats()
            total = stats.get('total_candles_cached', 0)
            if total > 0:
                return f"{total:,} candles cached"
            else:
                return "No cache data yet"
        except:
            return "Cache stats unavailable"

    def start_all(self, enable_websocket: bool = False):
        """
        Start all services.

        Args:
            enable_websocket: If True, start WebSocket collector (Tier 3)
        """
        if enable_websocket:
            self.start_websocket_collector()

    def stop_all(self):
        """Stop all services."""
        self.stop_websocket_collector()

    def cleanup(self):
        """Cleanup on exit."""
        self.stop_all()


# Global singleton
_service_manager = None
_service_manager_lock = threading.Lock()


def get_service_manager() -> ServiceManager:
    """Get global service manager instance."""
    global _service_manager
    with _service_manager_lock:
        if _service_manager is None:
            _service_manager = ServiceManager()
        return _service_manager
