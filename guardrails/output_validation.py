
from dataclasses import dataclass, field

from guardrails.pii_detection import (
    detect_pii,
    contains_sensitive_authentication_data,
)


@dataclass
class OutputValidationResult:
    valid: bool
    safe_output: str
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def validate_agent_output(
    output: str,
    customer_id: int = None,
    max_length: int = 10000,
) -> OutputValidationResult:
    """
    Validate an agent's output before returning it to the customer.

    customer_id is reserved for future response-to-customer ownership
    checks. It must come from trusted backend context.
    """

    errors = []
    warnings = []

    if not isinstance(output, str):
        return OutputValidationResult(
            valid=False,
            safe_output="",
            errors=["Agent output must be text."],
        )

    cleaned = output.strip()

    if len(cleaned) > max_length:
        errors.append("Agent output exceeds the permitted length.")

    if contains_sensitive_authentication_data(cleaned):
        errors.append(
            "Response appears to contain an OTP or CVV. "
            "Sensitive authentication data must not be disclosed."
        )

    pii_result = detect_pii(cleaned)

    if pii_result.contains_pii:
        warnings.append(
            "Potential personal or financial information detected: "
            + ", ".join(pii_result.categories)
        )

    if errors:
        return OutputValidationResult(
            valid=False,
            safe_output=(
                "I cannot safely provide that response. "
                "Please contact SecureBank support if you need assistance."
            ),
            errors=errors,
            warnings=warnings,
        )

    return OutputValidationResult(
        valid=True,
        safe_output=cleaned,
        errors=errors,
        warnings=warnings,
    )


def validate_tool_result_for_display(
    result: str,
    mask_sensitive_data: bool = True,
) -> OutputValidationResult:
    """
    Validate a tool result before an agent or application displays it.

    This does not replace ownership checks in the database tools.
    """

    from guardrails.pii_detection import mask_pii

    if not isinstance(result, str):
        return OutputValidationResult(
            valid=False,
            safe_output="",
            errors=["Tool result must be text."],
        )

    if contains_sensitive_authentication_data(result):
        return OutputValidationResult(
            valid=False,
            safe_output="Sensitive authentication data was blocked.",
            errors=["Tool result contains possible OTP or CVV data."],
        )

    warnings = []
    safe_result = result

    if detect_pii(result).contains_pii:
        warnings.append("Tool result contains potential PII.")

        if mask_sensitive_data:
            safe_result = mask_pii(result)

    return OutputValidationResult(
        valid=True,
        safe_output=safe_result,
        warnings=warnings,
    )
