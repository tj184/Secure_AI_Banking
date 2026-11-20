
from dataclasses import dataclass


@dataclass
class RiskAssessment:
    score: int
    level: str
    requires_human_approval: bool
    reasons: list


def assess_transaction_risk(
    amount,
    is_new_beneficiary: bool = False,
    beneficiary_verified: bool = True,
    suspicious_input: bool = False,
    repeated_requests: bool = False,
    account_active: bool = True,
) -> RiskAssessment:
    """Calculate a deterministic risk score for a banking operation."""

    from decimal import Decimal, InvalidOperation

    score = 0
    reasons = []

    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        value = Decimal("0")
        score += 100
        reasons.append("Invalid transaction amount.")

    if not value.is_finite() or value <= 0:
        score += 100
        reasons.append("Invalid or non-positive transaction amount.")

    elif value >= Decimal("100000"):
        score += 40
        reasons.append("High-value transaction.")

    elif value >= Decimal("50000"):
        score += 25
        reasons.append("Medium-high-value transaction.")

    elif value >= Decimal("10000"):
        score += 10
        reasons.append("Transaction amount requires additional monitoring.")

    if is_new_beneficiary:
        score += 20
        reasons.append("New beneficiary.")

    if not beneficiary_verified:
        score += 100
        reasons.append("Beneficiary is not verified.")

    if suspicious_input:
        score += 50
        reasons.append("Suspicious input detected.")

    if repeated_requests:
        score += 30
        reasons.append("Repeated transaction requests detected.")

    if not account_active:
        score += 100
        reasons.append("Account is inactive.")

    score = min(score, 100)

    if score >= 70:
        level = "CRITICAL"
    elif score >= 40:
        level = "HIGH"
    elif score >= 20:
        level = "MEDIUM"
    else:
        level = "LOW"

    requires_approval = level in {"HIGH", "CRITICAL"}

    return RiskAssessment(
        score=score,
        level=level,
        requires_human_approval=requires_approval,
        reasons=reasons,
    )


def assess_request_risk(
    operation: str,
    suspicious_input: bool = False,
    contains_pii: bool = False,
) -> RiskAssessment:
    """Assess general requests, not just monetary transfers."""

    score = 0
    reasons = []

    if operation in {"execute_transfer", "direct_balance_update"}:
        score += 100
        reasons.append("Direct financial execution is prohibited.")

    elif operation in {"prepare_transfer", "add_beneficiary"}:
        score += 30
        reasons.append("Financial operation requires additional controls.")

    if suspicious_input:
        score += 50
        reasons.append("Potentially suspicious input.")

    if contains_pii:
        score += 10
        reasons.append("Personal or financial information detected.")

    score = min(score, 100)

    if score >= 70:
        level = "CRITICAL"
    elif score >= 40:
        level = "HIGH"
    elif score >= 20:
        level = "MEDIUM"
    else:
        level = "LOW"

    return RiskAssessment(
        score=score,
        level=level,
        requires_human_approval=level in {"HIGH", "CRITICAL"},
        reasons=reasons,
    )
