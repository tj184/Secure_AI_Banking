
from security.authentication import (
    authenticate_customer,
    authenticate_manager,
)

from security.authorization import (
    check_permission,
    require_customer_ownership,
)

from security.rate_limiter import (
    check_rate_limit,
    get_rate_limit_status,
    reset_rate_limit,
)


print("\n--- CUSTOMER AUTHENTICATION ---")

result = authenticate_customer(
    "rahul@example.com",
    "Rahul@123",
)

print(result)


print("\n--- ROLE-BASED AUTHORIZATION ---")

customer_context = {
    "authenticated": True,
    "customer_id": 1,
    "role": "customer",
}

print(
    "Can view accounts:",
    check_permission(customer_context, "account:view"),
)

print(
    "Can approve all transfers:",
    check_permission(customer_context, "transfer:approve"),
)


print("\n--- OWNERSHIP CHECK ---")

print(
    "Own resource:",
    require_customer_ownership(customer_context, 1),
)

print(
    "Other customer's resource:",
    require_customer_ownership(customer_context, 2),
)


print("\n--- RATE LIMITING ---")

reset_rate_limit("demo-user", "login")

for attempt in range(1, 7):
    result = check_rate_limit(
        identifier="demo-user",
        action="login",
        limit=5,
        window_seconds=300,
    )

    print(f"Attempt {attempt}: {result}")

print(
    "\nStatus:",
    get_rate_limit_status(
        "demo-user",
        "login",
        limit=5,
        window_seconds=300,
    ),
)
