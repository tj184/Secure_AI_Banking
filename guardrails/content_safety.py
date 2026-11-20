
import re
from dataclasses import dataclass, field


UNSAFE_PATTERNS = {
    "CREDENTIAL_THEFT": re.compile(
        r"\b(steal|capture|harvest|phish|obtain)\b.{0,80}"
        r"\b(passwords|credentials|otp|one[- ]time passwords|login details)\b",
        re.IGNORECASE,
    ),
    "UNAUTHORIZED_ACCESS": re.compile(
        r"\b(access|enter|log into|hack)\b.{0,80}"
        r"\b(someone else's|another person's|other customers|unauthorized)\b"
        r".{0,40}\b(account|bank account|profile|system)\b",
        re.IGNORECASE,
    ),
    "FRAUD": re.compile(
        r"\b(forge|fake|fabricate|conceal|launder)\b.{0,80}"
        r"\b(bank statement|transaction|identity|payment|funds|records)\b",
        re.IGNORECASE,
    ),
    "SECURITY_EVASION": re.compile(
        r"\b(evade|avoid|bypass|defeat)\b.{0,80}"
        r"\b(fraud detection|bank security|transaction monitoring|kyc)\b",
        re.IGNORECASE,
    ),
}


@dataclass
class SafetyResult:
    safe: bool
    risk_level: str
    categories: list = field(default_factory=list)
    reason: str = ""


def check_content_safety(text: str) -> SafetyResult:
    """Check for common harmful banking-related requests."""

    if not isinstance(text, str):
        return SafetyResult(
            False,
            "HIGH",
            reason="Input must be text.",
        )

    matches = [
        category
        for category, pattern in UNSAFE_PATTERNS.items()
        if pattern.search(text)
    ]

    if len(matches) >= 2:
        return SafetyResult(
            safe=False,
            risk_level="CRITICAL",
            categories=matches,
            reason="Multiple potentially harmful banking-related patterns detected.",
        )

    if matches:
        return SafetyResult(
            safe=False,
            risk_level="HIGH",
            categories=matches,
            reason="Potentially harmful banking-related request detected.",
        )

    return SafetyResult(
        safe=True,
        risk_level="LOW",
        reason="No known unsafe-content pattern detected.",
    )
