
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    String,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    CheckConstraint,
    UniqueConstraint,
    Index,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from database.db import Base


def utc_now():
    return datetime.now(timezone.utc)


# =====================================================
# 1. CUSTOMER MODEL
# =====================================================

class Customer(Base):

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    email: Mapped[str] = mapped_column(
        String(150),
        unique=True,
        nullable=False,
        index=True
    )

    phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    accounts: Mapped[list["Account"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan"
    )

    beneficiaries: Mapped[list["Beneficiary"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan"
    )

    transfer_requests: Mapped[list["TransferRequest"]] = relationship(
        back_populates="customer"
    )

    def __repr__(self):
        return f"<Customer id={self.id} name={self.full_name}>"


# =====================================================
# 2. ACCOUNT MODEL
# =====================================================

class Account(Base):

    __tablename__ = "accounts"

    __table_args__ = (
        CheckConstraint(
            "balance >= 0",
            name="check_account_balance_nonnegative"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    account_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        nullable=False
    )

    account_type: Mapped[str] = mapped_column(
        String(30),
        default="SAVINGS",
        nullable=False
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0.00"),
        nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="INR",
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="accounts"
    )

    transactions: Mapped[list["BankTransaction"]] = relationship(
        back_populates="account",
        foreign_keys="BankTransaction.account_id"
    )

    def __repr__(self):
        return f"<Account id={self.id} number={self.account_number}>"


# =====================================================
# 3. BENEFICIARY MODEL
# =====================================================

class Beneficiary(Base):

    __tablename__ = "beneficiaries"

    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "account_number",
            name="unique_customer_beneficiary_account"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    account_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    bank_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    ifsc_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="beneficiaries"
    )

    transfer_requests: Mapped[list["TransferRequest"]] = relationship(
        back_populates="beneficiary"
    )

    def __repr__(self):
        return f"<Beneficiary id={self.id} name={self.name}>"


# =====================================================
# 4. BANK TRANSACTION MODEL
# =====================================================

class BankTransaction(Base):

    __tablename__ = "bank_transactions"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="check_transaction_amount_positive"
        ),
        CheckConstraint(
            "transaction_type IN ('DEPOSIT', 'WITHDRAWAL', 'TRANSFER')",
            name="check_transaction_type"
        ),
        Index(
            "idx_transaction_account_date",
            "account_id",
            "created_at"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=False,
        index=True
    )

    transaction_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        String(255),
        default="Bank transaction",
        nullable=False
    )

    reference_number: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="SUCCESS",
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    account: Mapped["Account"] = relationship(
        back_populates="transactions",
        foreign_keys=[account_id]
    )

    def __repr__(self):
        return f"<BankTransaction id={self.id} amount={self.amount}>"


# =====================================================
# 5. TRANSFER REQUEST MODEL
# =====================================================

class TransferRequest(Base):

    __tablename__ = "transfer_requests"

    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="check_transfer_amount_positive"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED', 'FAILED')",
            name="check_transfer_status"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        nullable=False,
        index=True
    )

    sender_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id"),
        nullable=False
    )

    beneficiary_id: Mapped[int] = mapped_column(
        ForeignKey("beneficiaries.id"),
        nullable=False
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        String(255),
        default="Customer transfer",
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        nullable=False,
        index=True
    )

    customer_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    manager_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="transfer_requests"
    )

    sender_account: Mapped["Account"] = relationship(
        foreign_keys=[sender_account_id]
    )

    beneficiary: Mapped["Beneficiary"] = relationship(
        back_populates="transfer_requests"
    )

    def __repr__(self):
        return f"<TransferRequest id={self.id} status={self.status}>"


# =====================================================
# 6. AUDIT LOG MODEL
# =====================================================

class AuditLog(Base):

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id"),
        nullable=True,
        index=True
    )

    agent_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )

    action: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False
    )

    customer: Mapped["Customer | None"] = relationship()

    def __repr__(self):
        return f"<AuditLog id={self.id} action={self.action}>"
