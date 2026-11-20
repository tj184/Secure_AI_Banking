
import json
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from langchain_core.tools import tool
from sqlalchemy import select

from database.db import session_scope
from database.models import (
    Account,
    Beneficiary,
    TransferRequest,
    AuditLog,
)


def get_payment_tools(customer_id: int):
    """
    Build payment tools for one authenticated customer.

    These tools can create pending transfer requests only.
    They cannot execute transfers or directly change balances.
    """

    @tool
    def prepare_transfer(
        sender_account_number: str,
        beneficiary_account_number: str,
        amount: str,
        description: str = "Bank transfer",
    ) -> str:
        """
        Prepare a bank transfer request.

        Requires the customer's own sender account number, a verified
        beneficiary account number, and a positive amount.

        This creates a PENDING request only. It does not transfer money.
        """

        sender_account_number = sender_account_number.strip()
        beneficiary_account_number = beneficiary_account_number.strip()
        description = description.strip()[:250] or "Bank transfer"

        try:
            transfer_amount = Decimal(amount)
        except (InvalidOperation, TypeError, ValueError):
            return "Invalid amount. Provide a valid monetary amount."

        if not transfer_amount.is_finite() or transfer_amount <= 0:
            return "Transfer amount must be greater than zero."

        if transfer_amount.as_tuple().exponent < -2:
            return "Transfer amount cannot have more than two decimal places."

        if transfer_amount > Decimal("1000000.00"):
            return "Transfer amount exceeds the demo system's per-request limit."

        with session_scope() as db:
            sender = db.scalar(
                select(Account).where(
                    Account.account_number == sender_account_number,
                    Account.customer_id == customer_id,
                    Account.is_active.is_(True),
                )
            )

            if not sender:
                return "Sender account not found or you are not authorized to use it."

            beneficiary = db.scalar(
                select(Beneficiary).where(
                    Beneficiary.account_number == beneficiary_account_number,
                    Beneficiary.customer_id == customer_id,
                    Beneficiary.is_active.is_(True),
                    Beneficiary.is_verified.is_(True),
                )
            )

            if not beneficiary:
                return (
                    "Beneficiary not found, inactive, or not verified. "
                    "Please verify the beneficiary before requesting a transfer."
                )

            if sender.account_number == beneficiary.account_number:
                return "You cannot transfer money to the same account."

            if Decimal(sender.balance) < transfer_amount:
                return "Insufficient balance. The transfer request was not created."

            idempotency_key = f"TRANSFER-{uuid4().hex}"

            request = TransferRequest(
                customer_id=customer_id,
                sender_account_id=sender.id,
                beneficiary_id=beneficiary.id,
                amount=transfer_amount,
                description=description,
                status="PENDING",
                customer_approved=False,
                manager_approved=False,
                idempotency_key=idempotency_key,
            )

            db.add(request)
            db.flush()

            db.add(
                AuditLog(
                    customer_id=customer_id,
                    agent_name="payment_agent",
                    action="PREPARE_TRANSFER",
                    status="PENDING",
                    details=(
                        f"Transfer request {request.id} created for "
                        f"{transfer_amount:.2f} {sender.currency}; "
                        f"sender ending {sender.account_number[-4:]}, "
                        f"beneficiary ending {beneficiary.account_number[-4:]}."
                    ),
                )
            )

            result = {
                "request_id": request.id,
                "status": "PENDING",
                "amount": f"{transfer_amount:.2f}",
                "currency": sender.currency,
                "sender_account": sender.account_number,
                "beneficiary_name": beneficiary.name,
                "beneficiary_account": beneficiary.account_number,
                "description": description,
                "customer_approval_required": True,
                "manager_approval_required": True,
                "money_deducted": False,
                "transfer_executed": False,
                "message": (
                    "Transfer request prepared successfully. "
                    "It is pending approval. No money has been transferred."
                ),
            }

            return json.dumps(result, indent=2)

    return [prepare_transfer]
