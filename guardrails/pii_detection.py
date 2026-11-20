
import re
from dataclasses import dataclass, field


PATTERNS = {
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
    "PHONE": re.compile(
        r"(?<!\d)(?:\+91[- ]?)?[6-9]\d{9}(?!\d)"
    ),
    "AADHAAR": re.compile(
        r"(?<!\d)\d{4}[- ]?\d{4}[- ]?\d{4}(?!\d)"
    ),
    "PAN": re.compile(
        r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
        re.IGNORECASE,
    ),
    "IFSC": re.compile(
        r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
        re.IGNORECASE,
    ),
    "OTP": re.compile(
        r"\b(?:otp|one[- ]time password)\s*(?:is|:|=)?\s*\d{4,8}\b",
        re.IGNORECASE,
    ),
    "CVV": re.compile(
        r"\b(?:cvv|cvc|security code)\s*(?:is|:|=)?\s*\d{3,4}\b",
        re.IGNORECASE,
    ),
    "ACCOUNT_NUMBER": re.compile(
        r"\b(?:account number|account no\.?|a/c)\s*(?:is|:|=)?\s*[A-Z0-9-]{6,24}\b",
        re.IGNORECASE,
    ),
    "CARD_NUMBER": re.compile(
        r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)"
    ),
}


@dataclass
class PIIFinding:
    category: str
    value: str
    start: int
    end: int


@dataclass
class PIIScanResult:
    contains_pii: bool
    findings: list = field(default_factory=list)

    @property
    def categories(self):
        return sorted({finding.category for finding in self.findings})


def detect_pii(text: str) -> PIIScanResult:
    """Find likely PII and financial identifiers in text."""

    if not isinstance(text, str):
        return PIIScanResult(False, [])

    findings = []

    for category, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            findings.append(
                PIIFinding(
                    category=category,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                )
            )

    # Remove overlapping matches, preferring the longer match.
    findings.sort(key=lambda item: (item.start, -(item.end - item.start)))

    filtered = []
    last_end = -1

    for finding in findings:
        if finding.start >= last_end:
            filtered.append(finding)
            last_end = finding.end

    return PIIScanResult(
        contains_pii=bool(filtered),
        findings=filtered,
    )


def mask_pii(text: str) -> str:
    """Mask detected PII while preserving the surrounding message."""

    if not isinstance(text, str):
        return text

    result = text
    scan = detect_pii(text)

    for finding in reversed(scan.findings):
        value = finding.value

        if finding.category == "EMAIL":
            replacement = "[EMAIL REDACTED]"
        elif finding.category in {"OTP", "CVV"}:
            replacement = f"[{finding.category} REDACTED]"
        elif len(value) > 4:
            replacement = "*" * (len(value) - 4) + value[-4:]
        else:
            replacement = "[REDACTED]"

        result = result[:finding.start] + replacement + result[finding.end:]

    return result


def contains_sensitive_authentication_data(text: str) -> bool:
    """Detect especially sensitive authentication data."""

    if not isinstance(text, str):
        return False

    return bool(
        PATTERNS["OTP"].search(text)
        or PATTERNS["CVV"].search(text)
    )
