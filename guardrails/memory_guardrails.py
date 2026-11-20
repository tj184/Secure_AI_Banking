
import re

from guardrails.pii_detection import (
    detect_pii,
    mask_pii,
    contains_sensitive_authentication_data,
)


SENSITIVE_MEMORY_PATTERNS = [
    re.compile(
        r"\b(password|passcode|pin|secret key|access token|refresh token)"
        r"\s*(?:is|:|=)\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(private key|api key|bearer token)\b",
        re.IGNORECASE,
    ),
]


def is_safe_to_store(text: str) -> bool:
    """Check whether text can be stored in conversational memory."""

    if not isinstance(text, str) or not text.strip():
        return False

    if contains_sensitive_authentication_data(text):
        return False

    if any(pattern.search(text) for pattern in SENSITIVE_MEMORY_PATTERNS):
        return False

    return True


def sanitize_memory(text: str) -> str:
    """
    Remove or mask sensitive information before memory storage.

    This is intended for optional conversational context, not the
    authoritative banking database.
    """

    if not isinstance(text, str):
        return ""

    if contains_sensitive_authentication_data(text):
        return "[Memory entry excluded: sensitive authentication data detected.]"

    for pattern in SENSITIVE_MEMORY_PATTERNS:
        text = pattern.sub("[CREDENTIAL REDACTED]", text)

    scan = detect_pii(text)

    if scan.contains_pii:
        text = mask_pii(text)

    return text


def prepare_memory_entry(text: str) -> dict:
    """Return a structured decision for a proposed memory entry."""

    if not isinstance(text, str) or not text.strip():
        return {
            "allowed": False,
            "content": "",
            "reason": "Empty or invalid memory entry.",
        }

    if not is_safe_to_store(text):
        return {
            "allowed": False,
            "content": "",
            "reason": "Memory entry contains sensitive authentication information.",
        }

    sanitized = sanitize_memory(text)

    return {
        "allowed": True,
        "content": sanitized,
        "reason": "Memory entry passed sensitive-data checks.",
    }


def filter_memory_entries(entries: list) -> list:
    """Sanitize a list of proposed memory entries."""

    safe_entries = []

    for entry in entries:
        result = prepare_memory_entry(entry)

        if result["allowed"]:
            safe_entries.append(result["content"])

    return safe_entries
