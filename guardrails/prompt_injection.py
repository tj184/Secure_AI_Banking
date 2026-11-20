
import re
from dataclasses import dataclass, field


INJECTION_PATTERNS = {
    "INSTRUCTION_OVERRIDE": re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\b.{0,80}"
        r"\b(previous|above|prior|system|developer|security|all)\b",
        re.IGNORECASE,
    ),
    "SYSTEM_PROMPT_EXTRACTION": re.compile(
        r"\b(reveal|show|print|display|repeat|expose)\b.{0,80}"
        r"\b(system prompt|developer message|hidden instructions|internal prompt)\b",
        re.IGNORECASE,
    ),
    "ROLE_MANIPULATION": re.compile(
        r"\b(you are now|act as|pretend to be|roleplay as)\b.{0,80}"
        r"\b(admin|administrator|bank manager|system|developer|unrestricted)\b",
        re.IGNORECASE,
    ),
    "SECURITY_BYPASS": re.compile(
        r"\b(bypass|disable|turn off|remove|skip)\b.{0,80}"
        r"\b(authentication|authorization|guardrail|approval|security|verification)\b",
        re.IGNORECASE,
    ),
    "TOOL_ABUSE": re.compile(
        r"\b(call|invoke|execute|run)\b.{0,80}"
        r"\b(tool|function|database|sql|shell|terminal)\b.{0,80}"
        r"\b(without|ignore|bypass|permission|approval)\b",
        re.IGNORECASE,
    ),
    "DATA_EXFILTRATION": re.compile(
        r"\b(export|dump|extract|list|send)\b.{0,80}"
        r"\b(all customers|all accounts|all transactions|customer database|credentials)\b",
        re.IGNORECASE,
    ),
}


@dataclass
class InjectionResult:
    is_suspicious: bool
    risk_level: str
    matched_categories: list = field(default_factory=list)
    message: str = ""


def detect_prompt_injection(text: str) -> InjectionResult:
    """Identify common prompt-injection patterns."""

    if not isinstance(text, str) or not text.strip():
        return InjectionResult(
            is_suspicious=False,
            risk_level="LOW",
            message="No meaningful input to inspect.",
        )

    matched = [
        category
        for category, pattern in INJECTION_PATTERNS.items()
        if pattern.search(text)
    ]

    if len(matched) >= 2:
        risk = "CRITICAL"
    elif matched:
        risk = "HIGH"
    else:
        risk = "LOW"

    return InjectionResult(
        is_suspicious=bool(matched),
        risk_level=risk,
        matched_categories=matched,
        message=(
            "Potential prompt injection detected."
            if matched
            else "No known prompt-injection pattern detected."
        ),
    )


def check_prompt_safety(text: str) -> tuple[bool, str]:
    """Convenience function for input pipelines."""

    result = detect_prompt_injection(text)

    if result.risk_level in {"HIGH", "CRITICAL"}:
        return False, result.message

    return True, "Input passed prompt-injection pattern checks."
