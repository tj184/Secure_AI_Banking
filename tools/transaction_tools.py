
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from langchain_core.tools import tool
from sqlalchemy import select, desc

from database.db import session_scope
from database.models import Account, BankTransaction, AuditLog


def _money(value):
    return f"{Decimal(value):.2f}"


def get_transaction_tools(customer_id: int):
    """
    Build transaction tools for one authenticated customer.

    The customer identity is injected by the backend and cannot
    be selected or overridden by the language model.
    """

    @tool
    def get_transaction_history(
        account_number: str,
        limit: int = 10,
    ) -> str:
        """
        Retrieve recent transactions for one of the customer's accounts.
        The limit must be between 1 and 50.
        """

        account_number = account_number.strip()

        if not isinstance(limit, int) or not 1 <= limit <= 50:
            return "Invalid limit. Choose a number between 1 and 50."

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

            transactions = db.scalars(
                select(BankTransaction)
                .where(BankTransaction.account_id == account.id)
                .order_by(desc(BankTransaction.created_at))
                .limit(limit)
            ).all()

            result = [
                {
                    "reference_number": transaction.reference_number,
                    "type": transaction.transaction_type,
                    "amount": _money(transaction.amount),
                    "description": transaction.description,
                    "status": transaction.status,
                    "date": (
                        transaction.created_at.isoformat()
                        if transaction.created_at
                        else None
                    ),
                }
                for transaction in transactions
            ]

            db.add(
                AuditLog(
                    customer_id=customer_id,
                    agent_name="transaction_agent",
                    action="VIEW_TRANSACTION_HISTORY",
                    status="SUCCESS",
                    details=(
                        f"Retrieved {len(result)} transaction(s) "
                        f"for account ending {account_number[-4:]}."
                    ),
                )
            )

            return json.dumps(result, indent=2)

    @tool
    def get_spending_summary(
        account_number: str,
        days: int = 30,
    ) -> str:
        """
        Calculate deposits, withdrawals, transfers and net spending
        for one of the customer's accounts over the requested number
        of days. The period must be between 1 and 365 days.
        """

        account_number = account_number.strip()

        if not isinstance(days, int) or not 1 <= days <= 365:
            return "Invalid period. Choose between 1 and 365 days."

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

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            transactions = db.scalars(
                select(BankTransaction).where(
                    BankTransaction.account_id == account.id,
                    BankTransaction.created_at >= cutoff,
                    BankTransaction.status == "SUCCESS",
                )
            ).all()

            deposits = Decimal("0.00")
            withdrawals = Decimal("0.00")
            transfers = Decimal("0.00")

            for transaction in transactions:
                amount = Decimal(transaction.amount)

                if transaction.transaction_type == "DEPOSIT":
                    deposits += amount
                elif transaction.transaction_type == "WITHDRAWAL":
                    withdrawals += amount
                elif transaction.transaction_type == "TRANSFER":
                    transfers += amount

            total_outgoing = withdrawals + transfers
            net_change = deposits - total_outgoing

            result = {
                "account_number": account.account_number,
                "period_days": days,
                "currency": account.currency,
                "transaction_count": len(transactions),
                "total_deposits": _money(deposits),
                "total_withdrawals": _money(withdrawals),
                "total_transfers": _money(transfers),
                "total_outgoing": _money(total_outgoing),
                "net_change": _money(net_change),
            }

            db.add(
                AuditLog(
                    customer_id=customer_id,
                    agent_name="transaction_agent",
                    action="VIEW_SPENDING_SUMMARY",
                    status="SUCCESS",
                    details=(
                        f"Generated {days}-day summary for "
                        f"account ending {account_number[-4:]}."
                    ),
                )
            )

            return json.dumps(result, indent=2)

    return [get_transaction_history, get_spending_summary]
