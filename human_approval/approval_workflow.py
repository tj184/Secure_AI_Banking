
from human_approval.approval_manager import (
    approve_transfer,
    reject_transfer,
    get_transfer_request,
    get_pending_transfers,
)


def _authenticated_customer(user_context):
    """
    Validate trusted backend authentication context.

    The caller must construct this context from the authenticated
    session, not from model-generated arguments.
    """

    if not isinstance(user_context, dict):
        return False

    customer_id = user_context.get("customer_id")

    return (
        user_context.get("authenticated") is True
        and isinstance(customer_id, int)
        and not isinstance(customer_id, bool)
        and customer_id > 0
    )


def _authenticated_manager(user_context):
    """
    Validate manager authorization from trusted backend context.

    The role must be populated by the authentication system.
    Never accept a role supplied by the language model.
    """

    if not isinstance(user_context, dict):
        return False

    return (
        user_context.get("authenticated") is True
        and user_context.get("role") == "manager"
        and bool(user_context.get("manager_id"))
    )


def customer_approve_transfer(
    request_id: int,
    user_context: dict,
):
    """
    Allow an authenticated customer to approve their own transfer.
    """

    if not _authenticated_customer(user_context):
        return {
            "success": False,
            "message": "Customer authentication is required.",
        }

    customer_id = user_context["customer_id"]

    result = approve_transfer(
        request_id=request_id,
        approval_type="CUSTOMER",
        actor_customer_id=customer_id,
    )

    return result


def customer_reject_transfer(
    request_id: int,
    reason: str,
    user_context: dict,
):
    """
    Allow an authenticated customer to reject their own transfer.
    """

    if not _authenticated_customer(user_context):
        return {
            "success": False,
            "message": "Customer authentication is required.",
        }

    customer_id = user_context["customer_id"]

    return reject_transfer(
        request_id=request_id,
        reason=reason,
        actor_type="CUSTOMER",
        actor_customer_id=customer_id,
    )


def manager_approve_transfer(
    request_id: int,
    user_context: dict,
):
    """
    Allow an authenticated manager to approve a pending transfer.
    """

    if not _authenticated_manager(user_context):
        return {
            "success": False,
            "message": "Manager authorization is required.",
        }

    return approve_transfer(
        request_id=request_id,
        approval_type="MANAGER",
    )


def manager_reject_transfer(
    request_id: int,
    reason: str,
    user_context: dict,
):
    """
    Allow an authenticated manager to reject a pending transfer.
    """

    if not _authenticated_manager(user_context):
        return {
            "success": False,
            "message": "Manager authorization is required.",
        }

    return reject_transfer(
        request_id=request_id,
        reason=reason,
        actor_type="MANAGER",
    )


def get_approval_status(
    request_id: int,
    user_context: dict,
):
    """
    Retrieve approval status.

    Customers can see their own requests.
    Managers can see any request.
    """

    if _authenticated_customer(user_context):
        return get_transfer_request(
            request_id=request_id,
            customer_id=user_context["customer_id"],
        )

    if _authenticated_manager(user_context):
        return get_transfer_request(
            request_id=request_id,
            customer_id=None,
        )

    return {
        "success": False,
        "message": "You are not authorized to view this transfer request.",
    }


def manager_get_pending_transfers(user_context: dict):
    """
    Retrieve pending transfers for the manager dashboard.
    """

    if not _authenticated_manager(user_context):
        return {
            "success": False,
            "message": "Manager authorization is required.",
        }

    return get_pending_transfers()
