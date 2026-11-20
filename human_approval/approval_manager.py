
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database.db import session_scope
from database.models import (
    TransferRequest,
    Account,
    Beneficiary,
    AuditLog,
)


def _audit(
    db,
    customer_id,
    action,
    status,
    details,
    agent_name="human_approval",
):
    db.add(
        AuditLog(
            customer_id=customer_id,
            agent_name=agent_name,
            action=action,
            status=status,
            details=details,
        )
    )


def _serialize_request(request):
    return {
        "request_id": request.id,
        "customer_id": request.customer_id,
        "sender_account_id": request.sender_account_id,
        "beneficiary_id": request.beneficiary_id,
        "amount": str(request.amount),
        "description": request.description,
        "status": request.status,
        "customer_approved": request.customer_approved,
        "manager_approved": request.manager_approved,
        "created_at": (
            request.created_at.isoformat()
            if request.created_at
            else None
        ),
        "updated_at": (
            request.updated_at.isoformat()
            if request.updated_at
            else None
        ),
    }


def get_transfer_request(request_id, customer_id=None):
    """
    Retrieve a transfer request.

    If customer_id is supplied, only that customer's request is returned.
    Use customer_id=None only from a trusted manager-side operation.
    """

    with session_scope() as db:
        query = select(TransferRequest).where(
            TransferRequest.id == request_id
        )

        if customer_id is not None:
            query = query.where(
                TransferRequest.customer_id == customer_id
            )

        request = db.scalar(query)

        if not request:
            return {
                "success": False,
                "message": "Transfer request not found or access denied.",
            }

        return {
            "success": True,
            "request": _serialize_request(request),
        }


def get_pending_transfers():
    """
    Retrieve transfer requests awaiting one or both approvals.

    This function must only be called by an authenticated manager.
    """

    with session_scope() as db:
        requests = db.scalars(
            select(TransferRequest)
            .where(TransferRequest.status == "PENDING")
            .order_by(TransferRequest.created_at.asc())
        ).all()

        return {
            "success": True,
            "transfers": [
                _serialize_request(request)
                for request in requests
            ],
            "count": len(requests),
        }


def _record_approval(
    request_id,
    approval_type,
    actor_customer_id=None,
):
    """
    Internal approval operation.

    approval_type must be CUSTOMER or MANAGER.
    """

    if approval_type not in ("CUSTOMER", "MANAGER"):
        return {
            "success": False,
            "message": "Invalid approval type.",
        }

    with session_scope() as db:
        query = (
            select(TransferRequest)
            .where(TransferRequest.id == request_id)
            .with_for_update()
        )

        request = db.scalar(query)

        if not request:
            return {
                "success": False,
                "message": "Transfer request not found.",
            }

        if (
            actor_customer_id is not None
            and request.customer_id != actor_customer_id
        ):
            return {
                "success": False,
                "message": "You are not authorized to approve this request.",
            }

        if request.status != "PENDING":
            return {
                "success": False,
                "message": (
                    f"This request cannot be approved because "
                    f"its current status is {request.status}."
                ),
            }

        if approval_type == "CUSTOMER":
            if request.customer_approved:
                return {
                    "success": False,
                    "message": "Customer approval has already been recorded.",
                }

            request.customer_approved = True

            action = "CUSTOMER_APPROVED_TRANSFER"
            details = f"Customer approved transfer request {request.id}."

        else:
            if request.manager_approved:
                return {
                    "success": False,
                    "message": "Manager approval has already been recorded.",
                }

            request.manager_approved = True

            action = "MANAGER_APPROVED_TRANSFER"
            details = f"Manager approved transfer request {request.id}."

        if request.customer_approved and request.manager_approved:
            request.status = "APPROVED"
            status_message = "Both approvals received. Transfer is approved but not executed."
        else:
            status_message = "Approval recorded. Waiting for the other approval."

        _audit(
            db,
            customer_id=request.customer_id,
            action=action,
            status="SUCCESS",
            details=details,
        )

        db.flush()

        return {
            "success": True,
            "request": _serialize_request(request),
            "message": status_message,
            "execution_status": "NOT_EXECUTED",
        }


def approve_transfer(
    request_id,
    approval_type,
    actor_customer_id=None,
):
    """
    Record an approval.

    CUSTOMER approval requires actor_customer_id.
    MANAGER approval authorization must be checked by the calling
    workflow before this function is invoked.
    """

    if approval_type == "CUSTOMER" and actor_customer_id is None:
        return {
            "success": False,
            "message": "Authenticated customer identity is required.",
        }

    return _record_approval(
        request_id=request_id,
        approval_type=approval_type,
        actor_customer_id=actor_customer_id,
    )


def reject_transfer(
    request_id,
    reason,
    actor_type,
    actor_customer_id=None,
):
    """
    Reject a pending transfer request.

    actor_type must be CUSTOMER or MANAGER.
    Manager authorization must be checked by the calling workflow.
    """

    if actor_type not in ("CUSTOMER", "MANAGER"):
        return {
            "success": False,
            "message": "Invalid rejection actor.",
        }

    reason = str(reason or "").strip()

    if not reason:
        return {
            "success": False,
            "message": "A rejection reason is required.",
        }

    if len(reason) > 500:
        return {
            "success": False,
            "message": "Rejection reason must not exceed 500 characters.",
        }

    with session_scope() as db:
        request = db.scalar(
            select(TransferRequest)
            .where(TransferRequest.id == request_id)
            .with_for_update()
        )

        if not request:
            return {
                "success": False,
                "message": "Transfer request not found.",
            }

        if (
            actor_customer_id is not None
            and request.customer_id != actor_customer_id
        ):
            return {
                "success": False,
                "message": "You are not authorized to reject this request.",
            }

        if request.status != "PENDING":
            return {
                "success": False,
                "message": "Only pending requests can be rejected.",
            }

        request.status = "REJECTED"

        _audit(
            db,
            customer_id=request.customer_id,
            action=f"{actor_type}_REJECTED_TRANSFER",
            status="SUCCESS",
            details=(
                f"{actor_type} rejected transfer request "
                f"{request.id}. Reason: {reason}"
            ),
        )

        db.flush()

        return {
            "success": True,
            "request": _serialize_request(request),
            "message": "Transfer request rejected successfully.",
            "execution_status": "NOT_EXECUTED",
        }
