
import logging

from monitoring.guardrail_metrics import increment_metric

from guardrails.pii_detection import (
    detect_pii,
    contains_sensitive_authentication_data,
    mask_pii,
)

from guardrails.prompt_injection import (
    detect_prompt_injection,
    check_prompt_safety,
)

from guardrails.content_safety import check_content_safety
from guardrails.input_validation import validate_user_input
from guardrails.risk_assessment import assess_request_risk


logger = logging.getLogger("securebank.hooks")


class GuardrailViolation(Exception):
    """Raised when a guardrail blocks an operation."""

    def __init__(self, message, reason="GUARDRAIL_BLOCK"):
        super().__init__(message)
        self.reason = reason


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


def _message(result, fallback):

    if isinstance(result, tuple) and len(result) > 1:
        return str(result[1])

    if isinstance(result, dict):
        return str(
            result.get("message")
            or result.get("reason")
            or fallback
        )

    return fallback


def _block(message, reason, metric="agent_requests_blocked"):
    """Record a blocked request and raise a guardrail exception."""

    increment_metric(metric)

    logger.warning(
        "Agent request blocked. reason=%s",
        reason,
    )

    raise GuardrailViolation(message, reason)


def before_agent(query: str, user_context: dict | None = None):
    """
    Validate a customer request before sending it to an AI agent.

    Returns:
        {
            "allowed": True,
            "query": original_query,
            "masked_query": masked_query,
            "risk_assessment": risk_result,
            "pii_detected": bool
        }

    Raises:
        GuardrailViolation if a guardrail blocks the request.
    """

    increment_metric("agent_requests")

    # 1. Basic input validation
    if not isinstance(query, str) or not query.strip():

        _block(
            "Please enter a valid banking request.",
            "INVALID_INPUT",
            "input_validation_failed",
        )

    user_context = user_context or {}

    if not isinstance(user_context, dict):
        _block(
            "Invalid user context.",
            "INVALID_USER_CONTEXT",
        )

    # 2. Input validation
    validation = validate_user_input(query)

    if _is_blocked(validation):

        _block(
            _message(validation, "Input validation failed."),
            "INPUT_VALIDATION_FAILED",
            "input_validation_failed",
        )

    # 3. Sensitive authentication information
    if contains_sensitive_authentication_data(query):

        _block(
            "For your security, never share passwords, PINs or OTPs. "
            "Please remove sensitive authentication information.",
            "SENSITIVE_AUTHENTICATION_DATA",
        )

    # 4. Prompt injection detection
    injection_result = detect_prompt_injection(query)

    if _is_blocked(injection_result):

        _block(
            "Your request contains instructions that cannot be processed.",
            "PROMPT_INJECTION_DETECTED",
            "prompt_injection_detected",
        )

    # 5. Prompt safety
    prompt_safety = check_prompt_safety(query)

    if _is_blocked(prompt_safety):

        _block(
            _message(prompt_safety, "Prompt safety check failed."),
            "PROMPT_SAFETY_FAILED",
        )

    # 6. Content safety
    content_result = check_content_safety(query)

    if _is_blocked(content_result):

        _block(
            _message(
                content_result,
                "The request violates content safety rules.",
            ),
            "CONTENT_SAFETY_FAILED",
            "content_safety_blocked",
        )

    # 7. PII detection
    pii_result = detect_pii(query)
    pii_detected = bool(pii_result)

    if pii_detected:
        increment_metric("pii_detected")

    # Masked copy for logs and diagnostics
    masked_query = mask_pii(query)

    # 8. Request risk assessment
    risk_result = assess_request_risk(query, user_context)

    if _is_blocked(risk_result):

        _block(
            _message(
                risk_result,
                "The request was blocked by risk assessment.",
            ),
            "REQUEST_RISK_BLOCKED",
        )

    # 9. Request successfully passed all guardrails
    increment_metric("agent_requests_allowed")

    logger.info(
        "Before-agent checks passed. customer_id=%s pii_detected=%s",
        user_context.get("customer_id"),
        pii_detected,
    )

    return {
        "allowed": True,
        "query": query,
        "masked_query": masked_query,
        "pii_detected": pii_detected,
        "risk_assessment": risk_result,
        "customer_id": user_context.get("customer_id"),
    }
