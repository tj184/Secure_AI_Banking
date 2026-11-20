
from monitoring import (
    log_event,
    log_agent_event,
    log_tool_event,
    log_security_event,
    log_approval_event,
    get_audit_logs,
    increment_metric,
    get_all_metrics,
    get_security_summary,
    reset_metrics,
)


print("\n========== AUDIT LOGGER TESTS ==========")

# 1. General event
print(
    log_event(
        action="CUSTOMER_LOGIN",
        status="SUCCESS",
        customer_id=1,
        agent_name="authentication",
        details="Rahul Sharma logged in.",
    )
)

# 2. Agent event
print(
    log_agent_event(
        agent_name="account_agent",
        action="ACCOUNT_QUERY",
        status="SUCCESS",
        customer_id=1,
        details="Customer requested account information.",
    )
)

# 3. Tool event
print(
    log_tool_event(
        tool_name="get_my_accounts",
        action="VIEW_ACCOUNTS",
        status="SUCCESS",
        customer_id=1,
        details="Retrieved customer account information.",
    )
)

# 4. Security event
print(
    log_security_event(
        action="PROMPT_INJECTION_DETECTED",
        status="BLOCKED",
        customer_id=1,
        details="Potential prompt injection detected.",
    )
)

# 5. Approval event
print(
    log_approval_event(
        action="CUSTOMER_APPROVED_TRANSFER",
        status="SUCCESS",
        customer_id=1,
        request_id=1,
        details="Customer approved a transfer request.",
    )
)

# 6. Retrieve audit records
print("\n========== AUDIT LOG RETRIEVAL ==========")

logs = get_audit_logs(
    customer_id=1,
    limit=10,
)

print(logs)


print("\n========== METRICS TESTS ==========")

# Reset metrics for a clean test.
reset_metrics()

increment_metric("agent_requests", 10)
increment_metric("agent_requests_allowed", 7)
increment_metric("agent_requests_blocked", 3)

increment_metric("prompt_injection_detected", 2)
increment_metric("pii_detected", 4)

increment_metric("tool_calls", 8)
increment_metric("tool_calls_allowed", 6)
increment_metric("tool_calls_blocked", 2)

increment_metric("transfers_prepared", 2)
increment_metric("customer_approvals", 1)

print("\nAll metrics:")
print(get_all_metrics())

print("\nSecurity summary:")
print(get_security_summary())
