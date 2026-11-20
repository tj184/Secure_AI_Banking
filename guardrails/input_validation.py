
from dataclasses import dataclass

from guardrails.prompt_injection import detect_prompt_injection
from guardrails.content_safety import check_content_safety


MAX_INPUT_LENGTH = 5000


@dataclass
class InputValidationResult:
    valid: bool
    cleaned_input: str
    errors: list


def validate_user_input(text: str) -> InputValidationResult:
    """Validate an incoming customer message."""

    errors = []

    if not isinstance(text, str):
        return InputValidationResult(
            valid=False,
            cleaned_input="",
            errors=["Input must be a text string."],
        )

    cleaned = text.strip()

    if not cleaned:
        errors.append("Message cannot be empty.")

    if len(cleaned) > MAX_INPUT_LENGTH:
        errors.append(
            f"Message exceeds the maximum length of {MAX_INPUT_LENGTH} characters."
        )

    if "\x00" in cleaned:
        errors.append("Message contains invalid control characters.")

    if errors:
        return InputValidationResult(False, cleaned, errors)

    injection = detect_prompt_injection(cleaned)

    if injection.risk_level in {"HIGH", "CRITICAL"}:
        errors.append(
            "Potential prompt injection detected: "
            + ", ".join(injection.matched_categories)
        )

    safety = check_content_safety(cleaned)

    if not safety.safe:
        errors.append(safety.reason)

    return InputValidationResult(
        valid=not errors,
        cleaned_input=cleaned,
        errors=errors,
    )


def validate_account_number(account_number: str) -> bool:
    """Validate the format of a demo SecureBank account number."""

    if not isinstance(account_number, str):
        return False

    value = account_number.strip()

    return (
        len(value) == 12
        and value.startswith("SB")
        and value[2:].isdigit()
    )


def validate_description(description: str, max_length: int = 250) -> bool:
    if not isinstance(description, str):
        return False

    value = description.strip()

    return (
        bool(value)
        and len(value) <= max_length
        and "\x00" not in value
    )
