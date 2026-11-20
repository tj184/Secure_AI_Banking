
from functools import wraps

from flask import jsonify

from security.authentication import create_user_context


# Role-based permissions.
# Add new permissions here as the application grows.
ROLE_PERMISSIONS = {
    "customer": {
        "account:view",
        "transaction:view",
        "transfer:create",
        "transfer:view_own",
        "transfer:approve_own",
        "transfer:reject_own",
    },
    "manager": {
        "transfer:view_all",
        "transfer:approve",
        "transfer:reject",
        "audit:view",
    },
}


def check_permission(user_context: dict, permission: str) -> bool:
    """Return whether the authenticated role has a permission."""

    if not isinstance(user_context, dict):
        return False

    if user_context.get("authenticated") is not True:
        return False

    role = user_context.get("role")
    permissions = ROLE_PERMISSIONS.get(role, set())

    return permission in permissions


def customer_required(function):
    """Restrict a Flask route to authenticated customers."""

    @wraps(function)
    def wrapper(*args, **kwargs):
        context = create_user_context()

        if (
            not context.get("authenticated")
            or context.get("role") != "customer"
        ):
            return jsonify({
                "success": False,
                "message": "Customer authentication is required.",
            }), 401

        return function(*args, **kwargs)

    return wrapper


def manager_required(function):
    """Restrict a Flask route to authenticated managers."""

    @wraps(function)
    def wrapper(*args, **kwargs):
        context = create_user_context()

        if (
            not context.get("authenticated")
            or context.get("role") != "manager"
        ):
            return jsonify({
                "success": False,
                "message": "Manager authorization is required.",
            }), 403

        return function(*args, **kwargs)

    return wrapper


def require_customer_ownership(
    user_context: dict,
    resource_customer_id: int,
) -> bool:
    """
    Ensure a customer can access only their own resource.

    Managers should use a separate manager permission check.
    """

    if not isinstance(user_context, dict):
        return False

    if user_context.get("authenticated") is not True:
        return False

    if user_context.get("role") != "customer":
        return False

    customer_id = user_context.get("customer_id")

    if not isinstance(customer_id, int) or isinstance(customer_id, bool):
        return False

    return customer_id == resource_customer_id


def require_manager(user_context: dict) -> bool:
    """Check that a trusted context belongs to an authenticated manager."""

    return (
        isinstance(user_context, dict)
        and user_context.get("authenticated") is True
        and user_context.get("role") == "manager"
        and bool(user_context.get("manager_id"))
    )


def require_permission(user_context: dict, permission: str):
    """
    Raise PermissionError if the user lacks the requested permission.

    Useful inside service functions and protected tool wrappers.
    """

    if not check_permission(user_context, permission):
        raise PermissionError(
            f"Permission denied: {permission}"
        )

    return True
