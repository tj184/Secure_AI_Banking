
import json
from decimal import Decimal

from langchain_core.tools import tool
from sqlalchemy import select

from database.db import session_scope
from database.models import Account, Customer, AuditLog


def _money(value):
    return f"{Decimal(value):.2f}"


def get_account_tools(customer_id: int):
    """
    Build account tools for one authenticated customer.

    customer_id is captured from trusted backend authentication.
    It is deliberately not exposed as an AI tool argument.
    """

    @tool
    def get_my_accounts() -> str:
        """Retrieve the authenticated customer's active bank accounts and balances."""

        with session_scope() as db:
            customer = db.get(Customer, customer_id)

            if not customer or not customer.is_active:
                return "Access denied: customer account is inactive or unavailable."

            accounts = db.scalars(
                select(Account)
                .where(
                    Account.customer_id == customer_id,
                    Account.is_active.is_(True),
                )
                .order_by(Account.id)
            ).all()

            result = [
                {
                    "account_number": account.account_number,
                    "account_type": account.account_type,
                    "balance": _money(account.balance),
                    "currency": account.currency,
                }
                for account in accounts
            ]

            db.add(
                AuditLog(
                    customer_id=customer_id,
                    agent_name="account_agent",
                    action="VIEW_ACCOUNT_LIST",
                    status="SUCCESS",
                    details=f"Retrieved {len(result)} active account(s).",
                )
            )

            return json.dumps(result, indent=2)

    @tool
    def get_account_details(account_number: str) -> str:
        """
        Retrieve details for one of the authenticated customer's accounts.
        Requires the exact account number.
        """

        account_number = account_number.strip()

        with session_scope() as db:
            account = db.scalar(
                select(Account).where(
                    Account.account_number == account_number,
                    Account.customer_id == customer_id,
                    Account.is_active.is_(True),
                )
            )

            if not account:
                return "Account not found or you are not authorized to access it."

            result = {
                "account_number": account.account_number,
                "account_type": account.account_type,
                "balance": _money(account.balance),
                "currency": account.currency,
                "status": "ACTIVE" if account.is_active else "INACTIVE",
                "created_at": (
                    account.created_at.isoformat()
                    if account.created_at
                    else None
                ),
            }

            db.add(
                AuditLog(
                    customer_id=customer_id,
                    agent_name="account_agent",
                    action="VIEW_ACCOUNT_DETAILS",
                    status="SUCCESS",
                    details=f"Viewed account ending {account.account_number[-4:]}.",
                )
            )

            return json.dumps(result, indent=2)

    return [get_my_accounts, get_account_details]
