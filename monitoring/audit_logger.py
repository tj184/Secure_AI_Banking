
import re
import logging
from datetime import datetime, timezone

from sqlalchemy import select, desc

from database.db import session_scope
from database.models import AuditLog

logger = logging.getLogger("securebank.audit")


# Basic masking for sensitive information in audit details.
PATTERNS = [
    # Email addresses
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[EMAIL_MASKED]",
    ),

    # Long account numbers
    (
        re.compile(r"\b\d{10,18}\b"),
        "[ACCOUNT_NUMBER_MASKED]",
    ),

    # Indian phone numbers
    (
        re.compile(r"(?<!\d)(?:\+91[- ]?)?[6-9]\d{9}(?!\d)"),
        "[PHONE_MASKED]",
    ),

    # Password, PIN and OTP values in key-value text
    (
        re.compile(
            r"(?i)\b(password|passwd|pin|otp|secret|token)"
            r"(\s*[:=]\s*)[^\s,;]+"
        ),
        r"\1\2[REDACTED]",
    ),
]


def sanitize_details(details):
    """Mask common sensitive values before storing audit details."""

    if details is None:
        return None

    text = str(details)[:4000]

    for pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)

    return text


def log_event(
    action: str,
    status: str,
    customer_id: int = None,
    agent_name: str = "system",
    details: str = None,
):
    """
    Write a general event to the persistent audit log.

    Existing AuditLog model fields:
        customer_id, agent_name, action, status, details
    """

    if not isinstance(action, str) or not action.strip():
        raise ValueError("Audit action is required.")

    if not isinstance(status, str) or not status.strip():
        raise ValueError("Audit status is required.")

    if customer_id is not None:
        if (
            not isinstance(customer_id, int)
            or isinstance(customer_id, bool)
            or customer_id <= 0
        ):
            raise ValueError("Invalid customer ID.")

    safe_details = sanitize_details(details)

    try:
        with session_scope() as db:
            entry = AuditLog(
                customer_id=customer_id,
                agent_name=str(agent_name)[:100],
                action=action.strip()[:100],
                status=status.strip().upper()[:30],
                details=safe_details,
            )

            db.add(entry)
            db.flush()

            event_id = entry.id

        logger.info(
            "Audit event recorded: action=%s status=%s",
            action,
            status,
        )

        return {
            "success": True,
            "event_id": event_id,
            "message": "Audit event recorded.",
        }

    except Exception:
        logger.exception("Failed to write audit event.")

        return {
            "success": False,
            "message": "Audit event could not be recorded.",
        }


def log_agent_event(
    agent_name,
    action,
    status,
    customer_id=None,
    details=None,
):
    """Record agent execution events."""

    return log_event(
        action=action,
        status=status,
        customer_id=customer_id,
        agent_name=agent_name,
        details=details,
    )


def log_tool_event(
    tool_name,
    action,
    status,
    customer_id=None,
    details=None,
):
    """Record banking tool execution events."""

    return log_event(
        action=action,
        status=status,
        customer_id=customer_id,
        agent_name=f"tool:{tool_name}",
        details=details,
    )


def log_security_event(
    action,
    status="BLOCKED",
    customer_id=None,
    details=None,
):
    """Record security and guardrail events."""

    return log_event(
        action=action,
        status=status,
        customer_id=customer_id,
        agent_name="security",
        details=details,
    )


def log_approval_event(
    action,
    status,
    customer_id,
    request_id,
    details=None,
):
    """Record customer or manager approval workflow events."""

    combined_details = (
        f"Transfer request ID: {request_id}. "
        f"{details or ''}"
    )

    return log_event(
        action=action,
        status=status,
        customer_id=customer_id,
        agent_name="human_approval",
        details=combined_details,
    )


def get_audit_logs(
    customer_id=None,
    action=None,
    status=None,
    limit=50,
    offset=0,
):
    """
    Retrieve audit logs with optional filters.

    Customer-facing code must always supply the authenticated
    customer's ID. Only trusted manager code should omit it.
    """

    if (
        not isinstance(limit, int)
        or isinstance(limit, bool)
        or not 1 <= limit <= 500
    ):
        return {
            "success": False,
            "message": "Limit must be between 1 and 500.",
        }

    if (
        not isinstance(offset, int)
        or isinstance(offset, bool)
        or offset < 0
    ):
        return {
            "success": False,
            "message": "Offset must be zero or greater.",
        }

    try:
        with session_scope() as db:
            query = select(AuditLog)

            if customer_id is not None:
                query = query.where(
                    AuditLog.customer_id == customer_id
                )

            if action:
                query = query.where(
                    AuditLog.action == action
                )

            if status:
                query = query.where(
                    AuditLog.status == status.upper()
                )

            query = (
                query
                .order_by(desc(AuditLog.created_at))
                .offset(offset)
                .limit(limit)
            )

            entries = db.scalars(query).all()

            results = [
                {
                    "id": entry.id,
                    "customer_id": entry.customer_id,
                    "agent_name": entry.agent_name,
                    "action": entry.action,
                    "status": entry.status,
                    "details": entry.details,
                    "created_at": (
                        entry.created_at.isoformat()
                        if entry.created_at
                        else None
                    ),
                }
                for entry in entries
            ]

            return {
                "success": True,
                "count": len(results),
                "logs": results,
            }

    except Exception:
        logger.exception("Failed to retrieve audit logs.")

        return {
            "success": False,
            "message": "Could not retrieve audit logs.",
        }
