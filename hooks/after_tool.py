
import json
import logging

from monitoring.guardrail_metrics import increment_metric

from guardrails.pii_detection import (
    detect_pii,
    mask_pii,
    contains_sensitive_authentication_data,
)

from guardrails.output_validation import validate_tool_result_for_display


logger = logging.getLogger("securebank.hooks")


def _is_blocked(result):
    """Normalize common guardrail return formats."""

    if isinstance(result, bool):
        return not result

    if isinstance(result, tuple) and result:
        return result[0] is False

    if isinstance(result, dict):

        if result.get("blocked") is True:
            return True

        for key in ("allowed", "valid", "safe"):
            if key in result and result[key] is False:
                return True

    return False


def _message(result):
    """Extract a readable validation failure message."""

    if isinstance(result, tuple) and len(result) > 1:
        return str(result[1])

    if isinstance(result, dict):
        return str(
            result.get("message")
            or result.get("reason")
            or "Tool result validation failed."
        )

    return "Tool result validation failed."


def _to_text(result):
    """Convert common tool return types to text safely."""

    if isinstance(result, str):
        return result

    if isinstance(result, (dict, list)):
        return json.dumps(result, default=str, ensure_ascii=False)

    return str(result)


def _blocked_result(reason, tool_name, metric="tool_results_blocked"):
    """Record blocked tool results and return a safe response."""

    increment_metric(metric)

    logger.warning(
        "Tool result blocked. tool=%s reason=%s",
        tool_name,
        reason,
    )

    return {
        "allowed": False,
        "result": (
            "The requested operation returned information "
            "that cannot safely be displayed."
        ),
        "reason": reason,
        "tool_name": tool_name,
    }


def after_tool(
    tool_name: str,
    tool_result,
    user_context: dict | None = None,
):
    """
    Validate and sanitize a tool result after execution.

    This hook does not execute or reverse database operations.

    Returns:
        {
            "allowed": True,
            "result": safe_result,
            "tool_name": tool_name,
            "pii_detected": bool
        }

    Blocked results return allowed=False.
    """

    # 1. Validate tool name
    if not isinstance(tool_name, str) or not tool_name.strip():

        return _blocked_result(
            "INVALID_TOOL_NAME",
            "unknown",
        )

    user_context = user_context or {}

    if not isinstance(user_context, dict):

        return _blocked_result(
            "INVALID_USER_CONTEXT",
            tool_name,
        )

    # 2. Convert tool result to text
    try:
        result_text = _to_text(tool_result)

    except Exception:
        logger.exception(
            "Tool result conversion failed. tool=%s",
            tool_name,
        )

        return _blocked_result(
            "RESULT_CONVERSION_FAILED",
            tool_name,
        )

    # 3. Detect sensitive authentication information
    try:
        contains_secrets = contains_sensitive_authentication_data(
            result_text
        )

    except Exception:
        logger.exception(
            "Authentication-data detection failed. tool=%s",
            tool_name,
        )

        return _blocked_result(
            "AUTHENTICATION_DATA_CHECK_FAILED",
            tool_name,
        )

    if contains_secrets:

        return _blocked_result(
            "SENSITIVE_AUTHENTICATION_DATA",
            tool_name,
        )

    # 4. Validate tool output
    try:
        validation = validate_tool_result_for_display(
            result_text
        )

    except Exception:
        logger.exception(
            "Tool result validation raised an exception. tool=%s",
            tool_name,
        )

        return _blocked_result(
            "TOOL_RESULT_VALIDATION_ERROR",
            tool_name,
            "tool_result_validation_failed",
        )

    if _is_blocked(validation):

        return _blocked_result(
            _message(validation),
            tool_name,
            "tool_result_validation_failed",
        )

    # 5. Detect PII
    try:
        pii_result = detect_pii(result_text)
        pii_detected = bool(pii_result)

    except Exception:
        logger.exception(
            "PII detection failed. tool=%s",
            tool_name,
        )

        return _blocked_result(
            "PII_DETECTION_FAILED",
            tool_name,
            "tool_result_validation_failed",
        )

    if pii_detected:
        increment_metric("pii_detected")

    # 6. Mask PII before returning the result
    try:
        safe_result = mask_pii(result_text)

        if not isinstance(safe_result, str):
            safe_result = str(safe_result)

    except Exception:
        logger.exception(
            "Tool result masking failed. tool=%s",
            tool_name,
        )

        return _blocked_result(
            "PII_MASKING_FAILED",
            tool_name,
            "tool_result_validation_failed",
        )

    # 7. Record successful result validation
    increment_metric("tool_results_allowed")

    logger.info(
        "Tool result validated. tool=%s pii_detected=%s customer_id=%s",
        tool_name,
        pii_detected,
        user_context.get("customer_id"),
    )

    return {
        "allowed": True,
        "result": safe_result,
        "tool_name": tool_name,
        "pii_detected": pii_detected,
    }
