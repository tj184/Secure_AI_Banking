
import logging

from monitoring.guardrail_metrics import increment_metric

from guardrails.pii_detection import (
    detect_pii,
    mask_pii,
    contains_sensitive_authentication_data,
)

from guardrails.output_validation import validate_agent_output


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
            or "Output validation failed."
        )

    return "Output validation failed."


def _blocked_response(reason, agent_name, metric):
    """Record blocked output and return a safe response."""

    increment_metric(metric)

    logger.warning(
        "Agent output blocked. agent=%s reason=%s",
        agent_name,
        reason,
    )

    return {
        "allowed": False,
        "response": (
            "I could not safely provide that response. "
            "Please try rephrasing your request."
        ),
        "reason": reason,
        "agent_name": agent_name,
    }


def after_agent(
    response,
    agent_name="unknown",
    user_context=None,
):
    """
    Validate and sanitize an agent response before displaying it.

    Returns:
        {
            "allowed": True,
            "response": safe_response,
            "pii_detected": bool,
            "agent_name": agent_name
        }

    Blocked responses return allowed=False.
    """

    user_context = user_context or {}

    # 1. Safely normalize response
    try:
        if not isinstance(response, str):
            response = str(response)

    except Exception:
        return _blocked_response(
            "OUTPUT_CONVERSION_FAILED",
            agent_name,
            "output_validation_failed",
        )

    # 2. Handle empty responses
    if not response.strip():

        response = (
            "I could not generate a response. "
            "Please try again."
        )

    # 3. Prevent disclosure of authentication secrets
    try:
        contains_secrets = contains_sensitive_authentication_data(
            response
        )

    except Exception:
        logger.exception(
            "Authentication-data detection failed. agent=%s",
            agent_name,
        )

        return _blocked_response(
            "AUTHENTICATION_DATA_CHECK_FAILED",
            agent_name,
            "output_validation_failed",
        )

    if contains_secrets:

        return _blocked_response(
            "SENSITIVE_AUTHENTICATION_DATA",
            agent_name,
            "output_validation_failed",
        )

    # 4. Validate generated content
    try:
        validation = validate_agent_output(response)

    except Exception:
        logger.exception(
            "Output validation raised an exception. agent=%s",
            agent_name,
        )

        return _blocked_response(
            "OUTPUT_VALIDATION_ERROR",
            agent_name,
            "output_validation_failed",
        )

    if _is_blocked(validation):

        return _blocked_response(
            _message(validation),
            agent_name,
            "output_validation_failed",
        )

    # 5. Detect PII
    try:
        pii_result = detect_pii(response)
        pii_detected = bool(pii_result)

    except Exception:
        logger.exception(
            "PII detection failed. agent=%s",
            agent_name,
        )

        return _blocked_response(
            "PII_DETECTION_FAILED",
            agent_name,
            "output_validation_failed",
        )

    if pii_detected:
        increment_metric("pii_detected")

    # 6. Mask PII before displaying the response
    try:
        safe_response = mask_pii(response)

    except Exception:
        logger.exception(
            "PII masking failed. agent=%s",
            agent_name,
        )

        return _blocked_response(
            "PII_MASKING_FAILED",
            agent_name,
            "output_validation_failed",
        )

    # 7. Record successful validation
    increment_metric("agent_outputs_allowed")

    logger.info(
        "Agent output validated. agent=%s pii_detected=%s customer_id=%s",
        agent_name,
        pii_detected,
        user_context.get("customer_id"),
    )

    return {
        "allowed": True,
        "response": safe_response,
        "pii_detected": pii_detected,
        "agent_name": agent_name,
    }
