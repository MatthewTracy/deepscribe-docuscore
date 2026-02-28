"""
Simple rate limiter for Anthropic API calls.

Tier 1: 50 requests per minute.
We enforce a minimum gap between calls to stay under the limit.
"""

import time
import threading


class RateLimiter:
    """Thread-safe rate limiter that enforces minimum gap between API calls."""

    def __init__(self, requests_per_minute: int = 45):
        self.min_gap = 60.0 / requests_per_minute  # seconds between calls
        self._last_call = 0.0
        self._lock = threading.Lock()

    def wait(self):
        """Block until it's safe to make the next API call."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self.min_gap:
                sleep_time = self.min_gap - elapsed
                time.sleep(sleep_time)
            self._last_call = time.time()


# Shared global instance - all API calls use this
_limiter = RateLimiter(requests_per_minute=45)  # Tier 1 limit is 50, leave margin


def wait_for_rate_limit():
    """Call this before every Anthropic API request."""
    _limiter.wait()
