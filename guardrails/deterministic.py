
from dataclasses import dataclass
from typing import Optional


@dataclass
class RuleResult:
    allowed: bool
    reason: str
    requires_approval: bool = False
    risk_level: str = "LOW"


# Operations that must never be performed directly by an LLM.
BLOCKED_OPERATIONS = {
    "execute_transfer",
    "direct_balance_update",
    "delete_transaction",
    "change_customer_password",
    "disable_security",
    "modify_account_ownership",
}


# Operations that can be requested but require an approval workflow.
APPROVAL_REQUIRED_OPERATIONS = {
    "prepare_transfer",
    "add_beneficiary",
    "change_registered_phone",
    "change_registered_email",
    "close_account",
}


READ_ONLY_OPERATIONS = {
    "get_my_accounts",
    "get_account_details",
    "get_transaction_history",
    "get_spending_summary",
}


def check_operation(operation: str) -> RuleResult:
    """Apply deterministic policy to a requested banking operation."""

    operation = (operation or "").strip().lower()

    if operation in BLOCKED_OPERATIONS:
        return RuleResult(
            allowed=False,
            reason="This operation cannot be performed directly by the AI system.",
            risk_level="CRITICAL",
        )

    if operation in APPROVAL_REQUIRED_OPERATIONS:
        return RuleResult(
            allowed=True,
            reason="Operation requires the designated approval workflow.",
            requires_approval=True,
            risk_level="HIGH",
        )

    if operation in READ_ONLY_OPERATIONS:
        return RuleResult(
            allowed=True,
            reason="Read-only operation permitted subject to customer authorization.",
            risk_level="LOW",
        )

    return RuleResult(
        allowed=False,
        reason="Operation is not included in the permitted banking policy.",
        risk_level="HIGH",
    )


def check_amount(amount, maximum=1000000):
    """Validate a monetary amount without relying on an LLM."""

    from decimal import Decimal, InvalidOperation

    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        return RuleResult(False, "Invalid monetary amount.", risk_level="HIGH")

    if not value.is_finite() or value <= 0:
        return RuleResult(False, "Amount must be a positive finite number.", risk_level="HIGH")

    if value.as_tuple().exponent < -2:
        return RuleResult(False, "Amount cannot have more than two decimal places.", risk_level="MEDIUM")

    if value > Decimal(str(maximum)):
        return RuleResult(False, "Amount exceeds the configured transaction limit.", risk_level="HIGH")

    return RuleResult(True, "Amount passed deterministic validation.")


def require_customer_identity(customer_id: Optional[int]) -> RuleResult:
    """Ensure a trusted authenticated customer identity is available."""

    if not isinstance(customer_id, int) or isinstance(customer_id, bool) or customer_id <= 0:
        return RuleResult(
            allowed=False,
            reason="A valid authenticated customer identity is required.",
            risk_level="CRITICAL",
        )

    return RuleResult(True, "Authenticated customer identity is present.")
