
from dataclasses import dataclass, field

from guardrails.deterministic import (
    check_operation,
    check_amount,
    require_customer_identity,
)
from guardrails.input_validation import (
    validate_account_number,
    validate_description,
)


@dataclass
class ToolGuardrailResult:
    allowed: bool
    requires_approval: bool = False
    risk_level: str = "LOW"
    reason: str = ""
    errors: list = field(default_factory=list)


def validate_tool_call(
    tool_name: str,
    arguments: dict,
    customer_id: int,
) -> ToolGuardrailResult:
    """
    Validate a banking tool call.

    customer_id must come from authenticated backend context.
    Never populate it using an LLM-generated argument.
    """

    identity_result = require_customer_identity(customer_id)

    if not identity_result.allowed:
        return ToolGuardrailResult(
            allowed=False,
            risk_level="CRITICAL",
            reason=identity_result.reason,
        )

    if not isinstance(arguments, dict):
        return ToolGuardrailResult(
            allowed=False,
            risk_level="HIGH",
            reason="Tool arguments must be a dictionary.",
        )

    operation_result = check_operation(tool_name)

    if not operation_result.allowed:
        return ToolGuardrailResult(
            allowed=False,
            risk_level=operation_result.risk_level,
            reason=operation_result.reason,
        )

    errors = []

    account_fields = {
        "account_number",
        "sender_account_number",
        "beneficiary_account_number",
    }

    for field_name in account_fields:
        value = arguments.get(field_name)

        if value is not None and not validate_account_number(value):
            errors.append(f"Invalid {field_name} format.")

    if tool_name == "prepare_transfer":
        amount_result = check_amount(arguments.get("amount"))

        if not amount_result.allowed:
            errors.append(amount_result.reason)

        description = arguments.get("description", "Bank transfer")

        if not validate_description(description):
            errors.append("Invalid transfer description.")

    if tool_name == "get_transaction_history":
        limit = arguments.get("limit", 10)

        if type(limit) is not int or not 1 <= limit <= 50:
            errors.append("Transaction history limit must be between 1 and 50.")

    if tool_name == "get_spending_summary":
        days = arguments.get("days", 30)

        if type(days) is not int or not 1 <= days <= 365:
            errors.append("Summary period must be between 1 and 365 days.")

    if errors:
        return ToolGuardrailResult(
            allowed=False,
            risk_level="HIGH",
            reason="Tool argument validation failed.",
            errors=errors,
        )

    return ToolGuardrailResult(
        allowed=True,
        requires_approval=operation_result.requires_approval,
        risk_level=operation_result.risk_level,
        reason=operation_result.reason,
    )


def check_tool_permission(tool_name: str, customer_id: int) -> bool:
    """Simple permission check for a tool name and authenticated customer."""

    identity = require_customer_identity(customer_id)
    operation = check_operation(tool_name)

    return identity.allowed and operation.allowed
