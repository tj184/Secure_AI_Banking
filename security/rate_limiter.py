
import hashlib
import threading
import time

from collections import defaultdict, deque


# In-memory request history.
_request_history = defaultdict(deque)
_blocked_until = {}

_lock = threading.Lock()


def _make_key(identifier: str, action: str):
    """
    Hash identifiers before storing them in memory.

    Avoid retaining raw email addresses, IP addresses or account IDs
    as dictionary keys.
    """

    raw_key = f"{action}:{identifier}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def check_rate_limit(
    identifier: str,
    action: str = "general",
    limit: int = 10,
    window_seconds: int = 60,
    block_seconds: int = 0,
):
    """
    Check whether an identifier is allowed to perform an action.

    Example:
        check_rate_limit(
            identifier="user@example.com",
            action="login",
            limit=5,
            window_seconds=300,
            block_seconds=600,
        )

    Returns:
        {
            "allowed": bool,
            "remaining": int,
            "retry_after": int
        }
    """

    if not isinstance(identifier, str) or not identifier.strip():
        return {
            "allowed": False,
            "remaining": 0,
            "retry_after": 0,
            "message": "A valid rate-limit identifier is required.",
        }

    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
        or not isinstance(window_seconds, int)
        or isinstance(window_seconds, bool)
        or window_seconds < 1
        or not isinstance(block_seconds, int)
        or isinstance(block_seconds, bool)
        or block_seconds < 0
    ):
        return {
            "allowed": False,
            "remaining": 0,
            "retry_after": 0,
            "message": "Invalid rate-limit configuration.",
        }

    key = _make_key(identifier.strip().lower(), action)
    now = time.monotonic()

    with _lock:
        # Check whether the identifier is temporarily blocked.
        blocked_until = _blocked_until.get(key, 0)

        if now < blocked_until:
            return {
                "allowed": False,
                "remaining": 0,
                "retry_after": max(
                    1,
                    int(blocked_until - now + 0.999),
                ),
                "message": "Too many attempts. Please try again later.",
            }

        history = _request_history[key]
        cutoff = now - window_seconds

        # Remove timestamps outside the current time window.
        while history and history[0] <= cutoff:
            history.popleft()

        # Reject if the limit has already been reached.
        if len(history) >= limit:
            retry_after = max(
                1,
                int(history[0] + window_seconds - now + 0.999),
            )

            if block_seconds > 0:
                _blocked_until[key] = now + block_seconds
                retry_after = max(retry_after, block_seconds)

            return {
                "allowed": False,
                "remaining": 0,
                "retry_after": retry_after,
                "message": "Rate limit exceeded. Please try again later.",
            }

        # Record the current request.
        history.append(now)

        return {
            "allowed": True,
            "remaining": max(0, limit - len(history)),
            "retry_after": 0,
            "message": "Request allowed.",
        }


def reset_rate_limit(
    identifier: str,
    action: str = "general",
):
    """Clear rate-limit history for an identifier and action."""

    if not isinstance(identifier, str) or not identifier.strip():
        return False

    key = _make_key(identifier.strip().lower(), action)

    with _lock:
        _request_history.pop(key, None)
        _blocked_until.pop(key, None)

    return True


def get_rate_limit_status(
    identifier: str,
    action: str = "general",
    limit: int = 10,
    window_seconds: int = 60,
):
    """Inspect rate-limit status without consuming a request."""

    if (
        not isinstance(identifier, str)
        or not identifier.strip()
        or not isinstance(limit, int)
        or isinstance(limit, bool)
        or limit < 1
        or not isinstance(window_seconds, int)
        or isinstance(window_seconds, bool)
        or window_seconds < 1
    ):
        return {
            "allowed": False,
            "remaining": 0,
            "retry_after": 0,
            "message": "Invalid rate-limit parameters.",
        }

    key = _make_key(identifier.strip().lower(), action)
    now = time.monotonic()

    with _lock:
        blocked_until = _blocked_until.get(key, 0)

        if now < blocked_until:
            return {
                "allowed": False,
                "remaining": 0,
                "retry_after": max(
                    1,
                    int(blocked_until - now + 0.999),
                ),
                "message": "Temporarily blocked.",
            }

        history = _request_history.get(key, deque())
        cutoff = now - window_seconds

        active_requests = [
            timestamp
            for timestamp in history
            if timestamp > cutoff
        ]

        remaining = max(0, limit - len(active_requests))

        return {
            "allowed": remaining > 0,
            "remaining": remaining,
            "retry_after": (
                max(
                    1,
                    int(active_requests[0] + window_seconds - now + 0.999),
                )
                if remaining == 0 and active_requests
                else 0
            ),
            "message": (
                "Request limit reached."
                if remaining == 0
                else "Request capacity available."
            ),
        }
