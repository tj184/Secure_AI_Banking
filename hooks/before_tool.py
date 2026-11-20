
import logging
from decimal import Decimal, InvalidOperation

from monitoring.guardrail_metrics import increment_metric

from guardrails.tool_guardrails import (
    validate_tool_call,
    check_tool_permission,
)

from guardrails.deterministic import (
    require_customer_identity,
    check_amount,
)

from guardrails.risk_assessment import assess_transaction_risk
from guardrails.input_validation import validate_description

from hooks.before_agent import (
    GuardrailViolation,
    _is_blocked,
    _message,
)


logger = logging.getLogger("securebank.hooks")


def _block(
    message,
    reason,
    metric="tool_calls_blocked",
):
    """Record a blocked tool call and raise an exception."""

    increment_metric(metric)

    logger.warning(
        "Tool call blocked. reason=%s",
        reason,
    )

    raise GuardrailViolation(message, reason)


def before_tool(
    tool_name: str,
    tool_args: dict | None = None,
    user_context: dict | None = None,
):
    """
    Run security checks before executing a banking tool.

    The authenticated customer identity must come from the backend.
    Never trust a customer_id supplied by the language model.

    Returns:
        {
            "allowed": True,
            "tool_name": str,
            "tool_args": dict,
            "customer_id": int,
            "risk_assessment": ...
        }

    Raises:
        GuardrailViolation when a tool call is not permitted.
    """

    # 1. Count every attempted tool invocation
    increment_metric("tool_calls")

    # Validate input types before processing
    if not isinstance(tool_name, str) or not tool_name.strip():

        _block(
            "Invalid tool name.",
            "INVALID_TOOL",
        )

    if tool_args is None:
        tool_args = {}

    if not isinstance(tool_args, dict):

        _block(
            "Invalid tool arguments.",
            "INVALID_TOOL_ARGUMENTS",
        )

    if user_context is None:
        user_context = {}

    if not isinstance(user_context, dict):

        _block(
            "Invalid authentication context.",
            "INVALID_USER_CONTEXT",
            "unauthorized_access_attempts",
        )

    # Make a copy so the caller's original arguments are not modified
    tool_args = dict(tool_args)

    # 2. Require authenticated customer identity
    customer_id = user_context.get("customer_id")

    if not isinstance(customer_id, int) or isinstance(customer_id, bool) or customer_id <= 0:

        _block(
            "Authentication is required before using banking tools.",
            "AUTHENTICATION_REQUIRED",
            "unauthorized_access_attempts",
        )

    identity_result = require_customer_identity(user_context)

    if _is_blocked(identity_result):

        _block(
            _message(
                identity_result,
                "Customer identity verification failed.",
            ),
            "IDENTITY_VERIFICATION_FAILED",
            "unauthorized_access_attempts",
        )

    # 3. Prevent model-controlled identity overrides
    protected_fields = {
        "customer_id",
        "user_id",
        "manager_id",
        "role",
        "authenticated",
    }

    supplied_protected_fields = protected_fields.intersection(tool_args)

    if supplied_protected_fields:

        _block(
            "The tool call contains protected identity fields.",
            "IDENTITY_OVERRIDE_ATTEMPT",
            "unauthorized_access_attempts",
        )

    # 4. Check tool permissions
    permission_result = check_tool_permission(
        tool_name,
        user_context,
    )

    if _is_blocked(permission_result):

        _block(
            _message(
                permission_result,
                "You are not authorized to use this tool.",
            ),
            "TOOL_PERMISSION_DENIED",
            "unauthorized_access_attempts",
        )

    # 5. Validate tool name and arguments
    validation_result = validate_tool_call(
        tool_name,
        tool_args,
        user_context,
    )

    if _is_blocked(validation_result):

        _block(
            _message(
                validation_result,
                "Tool call validation failed.",
            ),
            "TOOL_CALL_INVALID",
        )

    # 6. Validate monetary amounts
    if "amount" in tool_args:

        try:
            amount = Decimal(str(tool_args["amount"]))

        except (InvalidOperation, TypeError, ValueError):

            _block(
                "Invalid monetary amount.",
                "INVALID_AMOUNT",
            )

        if not amount.is_finite() or amount <= Decimal("0"):

            _block(
                "The monetary amount must be a positive finite number.",
                "INVALID_AMOUNT",
            )

        amount_result = check_amount(amount)

        if _is_blocked(amount_result):

            _block(
                _message(
                    amount_result,
                    "The requested amount is not permitted.",
                ),
                "AMOUNT_CHECK_FAILED",
            )

        # 7. Transaction risk assessment
        risk_result = assess_transaction_risk(
            amount,
            tool_args,
            user_context,
        )

        if _is_blocked(risk_result):

            _block(
                _message(
                    risk_result,
                    "The transaction was blocked by risk assessment.",
                ),
                "TRANSACTION_RISK_BLOCKED",
                "transaction_risk_blocked",
            )

    else:
        risk_result = None

    # 8. Validate transaction descriptions
    if "description" in tool_args:

        description_result = validate_description(
            tool_args["description"]
        )

        if _is_blocked(description_result):

            _block(
                _message(
                    description_result,
                    "Invalid tool description.",
                ),
                "INVALID_DESCRIPTION",
            )

    # 9. Record successful tool authorization
    increment_metric("tool_calls_allowed")

    logger.info(
        "Tool call approved. tool=%s customer_id=%s",
        tool_name,
        customer_id,
    )

    return {
        "allowed": True,
        "tool_name": tool_name,
        "tool_args": tool_args,
        "customer_id": customer_id,
        "risk_assessment": risk_result,
    }
