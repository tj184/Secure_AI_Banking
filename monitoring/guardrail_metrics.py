
import threading
from collections import defaultdict
from datetime import datetime, timezone


_metrics = defaultdict(int)
_lock = threading.Lock()

# Keep a timestamp for the most recent occurrence of each metric.
_last_updated = {}


# Standard metric names used throughout SecureBank AI.
STANDARD_METRICS = {
    "agent_requests",
    "agent_requests_allowed",
    "agent_requests_blocked",
    "tool_calls",
    "tool_calls_allowed",
    "tool_calls_blocked",
    "prompt_injection_detected",
    "pii_detected",
    "content_safety_blocked",
    "input_validation_failed",
    "output_validation_failed",
    "unauthorized_access_attempts",
    "authentication_failures",
    "rate_limit_exceeded",
    "transaction_risk_blocked",
    "transfers_prepared",
    "customer_approvals",
    "manager_approvals",
    "transfers_rejected",
}


def record_metric(name: str, value=1):
    """
    Set a metric to an absolute numeric value.

    Use increment_metric() for event counters.
    """

    if not isinstance(name, str) or not name.strip():
        raise ValueError("Metric name is required.")

    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < 0
    ):
        raise ValueError("Metric value must be a non-negative number.")

    name = name.strip()

    with _lock:
        _metrics[name] = value
        _last_updated[name] = datetime.now(
            timezone.utc
        ).isoformat()

    return {
        "success": True,
        "metric": name,
        "value": value,
    }


def increment_metric(name: str, amount=1):
    """Increment a metric counter."""

    if not isinstance(name, str) or not name.strip():
        raise ValueError("Metric name is required.")

    if (
        not isinstance(amount, (int, float))
        or isinstance(amount, bool)
        or amount <= 0
    ):
        raise ValueError("Increment amount must be positive.")

    name = name.strip()

    with _lock:
        _metrics[name] += amount

        _last_updated[name] = datetime.now(
            timezone.utc
        ).isoformat()

        current_value = _metrics[name]

    return {
        "success": True,
        "metric": name,
        "value": current_value,
    }


def get_metric(name: str):
    """Retrieve the current value of one metric."""

    with _lock:
        return {
            "metric": name,
            "value": _metrics.get(name, 0),
            "last_updated": _last_updated.get(name),
        }


def get_all_metrics():
    """Return all recorded metrics, including standard metrics at zero."""

    with _lock:
        names = STANDARD_METRICS.union(_metrics.keys())

        return {
            name: {
                "value": _metrics.get(name, 0),
                "last_updated": _last_updated.get(name),
            }
            for name in sorted(names)
        }


def get_security_summary():
    """
    Generate a summary of SecureBank AI security activity.

    The percentages are calculated from observed counters.
    They are not a guarantee that every attack was detected.
    """

    with _lock:
        snapshot = dict(_metrics)

    requests = snapshot.get("agent_requests", 0)
    allowed = snapshot.get("agent_requests_allowed", 0)
    blocked = snapshot.get("agent_requests_blocked", 0)

    tool_calls = snapshot.get("tool_calls", 0)
    tool_blocked = snapshot.get("tool_calls_blocked", 0)

    injection_attempts = snapshot.get(
        "prompt_injection_detected", 0
    )

    pii_events = snapshot.get("pii_detected", 0)

    request_block_rate = (
        round((blocked / requests) * 100, 2)
        if requests
        else 0.0
    )

    tool_block_rate = (
        round((tool_blocked / tool_calls) * 100, 2)
        if tool_calls
        else 0.0
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),

        "requests": {
            "total": requests,
            "allowed": allowed,
            "blocked": blocked,
            "block_rate_percent": request_block_rate,
        },

        "tools": {
            "total": tool_calls,
            "blocked": tool_blocked,
            "block_rate_percent": tool_block_rate,
        },

        "threats": {
            "prompt_injection_attempts": injection_attempts,
            "pii_detection_events": pii_events,
            "unauthorized_access_attempts": snapshot.get(
                "unauthorized_access_attempts", 0
            ),
            "rate_limit_events": snapshot.get(
                "rate_limit_exceeded", 0
            ),
        },

        "transactions": {
            "prepared": snapshot.get("transfers_prepared", 0),
            "customer_approvals": snapshot.get(
                "customer_approvals", 0
            ),
            "manager_approvals": snapshot.get(
                "manager_approvals", 0
            ),
            "rejected": snapshot.get("transfers_rejected", 0),
        },
    }


def reset_metrics():
    """
    Reset all in-memory metrics.

    Intended for local testing or controlled administrative use.
    """

    with _lock:
        _metrics.clear()
        _last_updated.clear()

    return {
        "success": True,
        "message": "Metrics reset successfully.",
    }
