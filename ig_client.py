"""
IG Trading REST API Client

Provides complete access to IG's REST API for forex trading.
Authentication, market data, positions, and order management.
"""

import os
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from logging_config import setup_file_logging

# Setup logging
logger = setup_file_logging("ig_client", console_output=False)


class IGApiError(Exception):
    """Custom exception for IG API errors."""

    def __init__(self, status: int, error_code: Optional[str], message: str, response_text: str = "", url: str = ""):
        super().__init__(f"IGApiError {status} {error_code or ''} {message}")
        self.status = status
        self.error_code = error_code
        self.message = message
        self.response_text = response_text
        self.url = url


class IGClient:
    """
    IG REST API Client for Forex Trading.

    Handles authentication, market data, and trade execution on IG's platform.
    Supports both demo and live accounts.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://demo-api.ig.com/gateway/deal",
        timeout: int = 20,
        retries: int = 3,
        backoff_factor: float = 0.5,
    ):
        """
        Initialize IG API client.

        Args:
            api_key: Your IG API key
            base_url: API base URL (demo or live)
            timeout: Request timeout in seconds
            retries: Number of retry attempts
            backoff_factor: Backoff multiplier for retries
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

        # Configure retry for transient errors
        retry = Retry(
            total=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        # Auth tokens set after create_session
        self.cst: Optional[str] = None
        self.x_security_token: Optional[str] = None
        self.current_account_id: Optional[str] = None
        self.lightstreamer_endpoint: Optional[str] = None

    def _default_headers(self, version: Optional[Union[int, str]] = None, include_auth: bool = True) -> Dict[str, str]:
        """Build default headers for requests."""
        headers = {
            "X-IG-API-KEY": self.api_key,
            "Accept": "application/json; charset=UTF-8",
            "Content-Type": "application/json; charset=UTF-8",
        }
        if version is not None:
            headers["Version"] = str(version)
        if include_auth and self.cst and self.x_security_token:
            headers["CST"] = self.cst
            headers["X-SECURITY-TOKEN"] = self.x_security_token
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        version: Optional[Union[int, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        include_auth: bool = True,
        expected: Optional[set] = None,
    ) -> Dict[str, Any]:
        """Make HTTP request to IG API."""
        if expected is None:
            expected = {200, 201}

        url = f"{self.base_url}{path}"
        headers = self._default_headers(version=version, include_auth=include_auth)

        try:
            resp = self.session.request(
                method=method.upper(),
                url=url,
                headers=headers,
                params=params,
                json=json_body,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise IGApiError(status=0, error_code=None, message=f"Network error: {e}") from e

        # Capture tokens if present
        cst = resp.headers.get("CST")
        xst = resp.headers.get("X-SECURITY-TOKEN")
        if cst and xst:
            self.cst = cst
            self.x_security_token = xst

        # Parse response JSON if possible
        text = resp.text or ""
        try:
            data = resp.json() if text else {}
        except ValueError:
            data = {}

        if resp.status_code not in expected:
            error_code = None
            message = f"Unexpected status {resp.status_code}"
            if isinstance(data, dict):
                error_code = data.get("errorCode") or data.get("error_code")
                message = data.get("message") or data.get("errorMessage") or message
            raise IGApiError(status=resp.status_code, error_code=error_code, message=message, response_text=text, url=url)

        return data

    @staticmethod
    def _fmt_dt(dt: datetime) -> str:
        """Format datetime for IG API (ISO8601)."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    def create_session(self, username: str, password: str, otp_code: Optional[str] = None) -> Dict[str, Any]:
        """
        Login to IG API.

        Args:
            username: IG username
            password: IG password
            otp_code: Optional 2FA code

        Returns:
            Session data including account info
        """
        headers = self._default_headers(version=2, include_auth=False)
        if otp_code:
            headers["X-IG-OTP-TOKEN"] = otp_code

        url = f"{self.base_url}/session"
        payload = {"identifier": username, "password": password}

        try:
            resp = self.session.post(url, headers=headers, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            raise IGApiError(status=0, error_code=None, message=f"Network error: {e}") from e

        # Set tokens
        self.cst = resp.headers.get("CST")
        self.x_security_token = resp.headers.get("X-SECURITY-TOKEN")

        # Handle errors
        text = resp.text or ""
        try:
            data = resp.json() if text else {}
        except ValueError:
            data = {}

        if resp.status_code not in (200, 201):
            error_code = data.get("errorCode") if isinstance(data, dict) else None
            message = data.get("message") if isinstance(data, dict) else "Login failed"
            raise IGApiError(status=resp.status_code, error_code=error_code, message=message, response_text=text, url=url)

        # Parse session info
        self.current_account_id = data.get("currentAccountId")
        self.lightstreamer_endpoint = data.get("lightstreamerEndpoint")
        return data

    def get_account(self) -> Dict[str, Any]:
        """Get account information."""
        return self._request("GET", "/accounts", version=1)

    def get_positions(self) -> Dict[str, Any]:
        """Get all open positions."""
        return self._request("GET", "/positions", version=2)

    def get_historical_prices(
        self,
        epic: str,
        resolution: str = "MINUTE",
        *,
        max_points: Optional[int] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        page_size: Optional[int] = None,
        page_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get historical price data.

        Args:
            epic: Market EPIC (e.g., "CS.D.EURUSD.TODAY.IP")
            resolution: SECOND, MINUTE, MINUTE_5, MINUTE_15, MINUTE_30, HOUR, HOUR_4, DAY, WEEK, MONTH
            max_points: Maximum number of candles
            start: Start datetime
            end: End datetime
            page_size: Results per page
            page_number: Page number

        Returns:
            Historical price data
        """
        # Use v2 API for historical data with numPoints (CORRECT endpoint!)
        # v2 uses path parameters: /prices/{epic}/{resolution}/{numPoints}
        # v3 is for recent minute data only (last 10 minutes)
        if max_points is not None and start is None and end is None:
            # Use v2 with path parameters for efficiency
            return self._request("GET", f"/prices/{epic}/{resolution}/{max_points}", version=2)

        # Use v3 for date ranges or other advanced queries
        params: Dict[str, Any] = {"resolution": resolution}
        if max_points is not None:
            params["max"] = int(max_points)
        if start is not None:
            params["from"] = self._fmt_dt(start)
        if end is not None:
            params["to"] = self._fmt_dt(end)
        if page_size is not None:
            params["pageSize"] = int(page_size)
        if page_number is not None:
            params["pageNumber"] = int(page_number)

        return self._request("GET", f"/prices/{epic}", version=3, params=params)

    def create_position(
        self,
        epic: str,
        direction: str,
        size: Union[int, float],
        *,
        order_type: str = "MARKET",
        expiry: str = "DFB",
        level: Optional[Union[int, float]] = None,
        limit_level: Optional[Union[int, float]] = None,
        limit_distance: Optional[Union[int, float]] = None,
        stop_level: Optional[Union[int, float]] = None,
        stop_distance: Optional[Union[int, float]] = None,
        guaranteed_stop: Optional[bool] = None,
        trailing_stop: Optional[bool] = None,
        trailing_stop_increment: Optional[Union[int, float]] = None,
        time_in_force: Optional[str] = None,
        force_open: Optional[bool] = True,
        currency_code: Optional[str] = None,
        deal_reference: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Open a new position.

        Args:
            epic: Market EPIC
            direction: BUY or SELL
            size: Position size
            order_type: MARKET or LIMIT
            expiry: DFB (Daily Funded Bet) or specific expiry
            level: Price level for LIMIT orders
            limit_level: Take profit level
            limit_distance: Take profit distance in pips
            stop_level: Stop loss level
            stop_distance: Stop loss distance in pips
            guaranteed_stop: Use guaranteed stop
            trailing_stop: Use trailing stop
            trailing_stop_increment: Trailing stop increment
            time_in_force: FILL_OR_KILL, EXECUTE_AND_ELIMINATE
            force_open: Force open even if hedging
            currency_code: Currency code
            deal_reference: Unique reference for this trade

        Returns:
            Deal response with deal reference
        """
        payload: Dict[str, Any] = {
            "epic": epic,
            "direction": direction.upper(),
            "size": size,
            "orderType": order_type.upper(),
            "expiry": expiry,
        }
        if level is not None:
            payload["level"] = level
        if limit_level is not None:
            payload["limitLevel"] = limit_level
        if limit_distance is not None:
            payload["limitDistance"] = limit_distance
        if stop_level is not None:
            payload["stopLevel"] = stop_level
        if stop_distance is not None:
            payload["stopDistance"] = stop_distance
        if guaranteed_stop is not None:
            payload["guaranteedStop"] = bool(guaranteed_stop)
        if trailing_stop is not None:
            payload["trailingStop"] = bool(trailing_stop)
        if trailing_stop_increment is not None:
            payload["trailingStopIncrement"] = trailing_stop_increment
        if time_in_force is not None:
            payload["timeInForce"] = time_in_force
        if force_open is not None:
            payload["forceOpen"] = bool(force_open)
        if currency_code is not None:
            payload["currencyCode"] = currency_code
        if deal_reference is not None:
            payload["dealReference"] = deal_reference

        return self._request("POST", "/positions/otc", version=2, json_body=payload, expected={200, 201})

    def close_position(
        self,
        deal_id: str,
        size: Union[int, float],
        direction: str,
        *,
        order_type: str = "MARKET",
        level: Optional[Union[int, float]] = None,
        time_in_force: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Close an existing position.

        Args:
            deal_id: Deal ID from open position
            size: Size to close
            direction: Opposite direction (SELL to close BUY)
            order_type: MARKET or LIMIT
            level: Price level for LIMIT orders
            time_in_force: Time in force

        Returns:
            Deal response
        """
        payload: Dict[str, Any] = {
            "dealId": deal_id,
            "direction": direction.upper(),
            "size": size,
            "orderType": order_type.upper(),
        }
        if level is not None:
            payload["level"] = level
        if time_in_force is not None:
            payload["timeInForce"] = time_in_force

        return self._request("DELETE", "/positions/otc", version=2, json_body=payload, expected={200, 201})

    def get_deal_confirmation(self, deal_reference: str) -> Dict[str, Any]:
        """
        Get deal confirmation status.

        Args:
            deal_reference: Deal reference from create/close position

        Returns:
            Deal confirmation with status and deal ID
        """
        return self._request("GET", f"/confirms/{deal_reference}", version=1)

    def logout(self) -> None:
        """Logout and clear session tokens."""
        try:
            self._request("DELETE", "/session", version=1, expected={200, 204})
        finally:
            self.cst = None
            self.x_security_token = None
            self.current_account_id = None
            self.lightstreamer_endpoint = None


# 28 Major Forex Pairs (IG EPICs)
IG_FOREX_PAIRS = {
    "EUR_USD": "CS.D.EURUSD.TODAY.IP",
    "USD_JPY": "CS.D.USDJPY.TODAY.IP",
    "GBP_USD": "CS.D.GBPUSD.TODAY.IP",
    "AUD_USD": "CS.D.AUDUSD.TODAY.IP",
    "USD_CAD": "CS.D.USDCAD.TODAY.IP",
    "USD_CHF": "CS.D.USDCHF.TODAY.IP",
    "NZD_USD": "CS.D.NZDUSD.TODAY.IP",
    "EUR_GBP": "CS.D.EURGBP.TODAY.IP",
    "EUR_JPY": "CS.D.EURJPY.TODAY.IP",
    "EUR_AUD": "CS.D.EURAUD.TODAY.IP",
    "EUR_CAD": "CS.D.EURCAD.TODAY.IP",
    "EUR_CHF": "CS.D.EURCHF.TODAY.IP",
    "EUR_NZD": "CS.D.EURNZD.TODAY.IP",
    "GBP_JPY": "CS.D.GBPJPY.TODAY.IP",
    "GBP_AUD": "CS.D.GBPAUD.TODAY.IP",
    "GBP_CAD": "CS.D.GBPCAD.TODAY.IP",
    "GBP_CHF": "CS.D.GBPCHF.TODAY.IP",
    "GBP_NZD": "CS.D.GBPNZD.TODAY.IP",
    "AUD_JPY": "CS.D.AUDJPY.TODAY.IP",
    "AUD_CAD": "CS.D.AUDCAD.TODAY.IP",
    "AUD_CHF": "CS.D.AUDCHF.TODAY.IP",
    "AUD_NZD": "CS.D.AUDNZD.TODAY.IP",
    "CAD_JPY": "CS.D.CADJPY.TODAY.IP",
    "CAD_CHF": "CS.D.CADCHF.TODAY.IP",
    "CAD_NZD": "CS.D.CADNZD.TODAY.IP",
    "CHF_JPY": "CS.D.CHFJPY.TODAY.IP",
    "CHF_NZD": "CS.D.CHFNZD.TODAY.IP",
    "NZD_JPY": "CS.D.NZDJPY.TODAY.IP",
}


# Test connection
if __name__ == "__main__":
    logger.info(f"="*80)
    logger.info(f"IG API CLIENT TEST")
    logger.info(f"="*80)

    API_KEY = "2f6287777a79dfb0c6f2a47c86a6f7d0b07ecef8"

    logger.info(f"\nAvailable forex pairs: {len(IG_FOREX_PAIRS)}")
    logger.info(f"Sample EPICs:")
    for i, (pair, epic) in enumerate(list(IG_FOREX_PAIRS.items())[:5]):
        logger.info(f"  {pair}: {epic}")

    logger.info(f"\n✅ IG Client ready for integration")
    logger.info(f"   API Key: {API_KEY[:20]}...")
    logger.info(f"   Demo URL: https://demo-api.ig.com/gateway/deal")
