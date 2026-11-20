
from decimal import Decimal
from uuid import uuid4

from werkzeug.security import generate_password_hash

from database.db import init_db, session_scope

from database.models import (
    Customer,
    Account,
    Beneficiary,
    BankTransaction,
    TransferRequest,
    AuditLog,
)


# =====================================================
# SEED DATABASE
# =====================================================

def seed_database():

    init_db()

    with session_scope() as db:

        # =============================================
        # 1. CREATE CUSTOMERS
        # =============================================

        customer1 = db.query(Customer).filter_by(
            email="rahul@example.com"
        ).first()

        if not customer1:

            customer1 = Customer(
                full_name="Rahul Sharma",
                email="rahul@example.com",
                phone="9000000001",
                password_hash=generate_password_hash(
                    "Rahul@123"
                ),
                is_active=True
            )

            db.add(customer1)
            db.flush()

        customer2 = db.query(Customer).filter_by(
            email="priya@example.com"
        ).first()

        if not customer2:

            customer2 = Customer(
                full_name="Priya Patel",
                email="priya@example.com",
                phone="9000000002",
                password_hash=generate_password_hash(
                    "Priya@123"
                ),
                is_active=True
            )

            db.add(customer2)
            db.flush()

        # =============================================
        # 2. CREATE ACCOUNTS
        # =============================================

        account1 = db.query(Account).filter_by(
            account_number="SB1000000001"
        ).first()

        if not account1:

            account1 = Account(
                customer_id=customer1.id,
                account_number="SB1000000001",
                account_type="SAVINGS",
                balance=Decimal("85000.00"),
                currency="INR",
                is_active=True
            )

            db.add(account1)
            db.flush()

        account2 = db.query(Account).filter_by(
            account_number="SB1000000002"
        ).first()

        if not account2:

            account2 = Account(
                customer_id=customer1.id,
                account_number="SB1000000002",
                account_type="CURRENT",
                balance=Decimal("25000.00"),
                currency="INR",
                is_active=True
            )

            db.add(account2)
            db.flush()

        account3 = db.query(Account).filter_by(
            account_number="SB1000000003"
        ).first()

        if not account3:

            account3 = Account(
                customer_id=customer2.id,
                account_number="SB1000000003",
                account_type="SAVINGS",
                balance=Decimal("42500.00"),
                currency="INR",
                is_active=True
            )

            db.add(account3)
            db.flush()

        # =============================================
        # 3. CREATE BENEFICIARIES
        # =============================================

        beneficiary1 = db.query(Beneficiary).filter_by(
            customer_id=customer1.id,
            account_number="SB2000000001"
        ).first()

        if not beneficiary1:

            beneficiary1 = Beneficiary(
                customer_id=customer1.id,
                name="Amit Verma",
                account_number="SB2000000001",
                bank_name="SecureBank",
                ifsc_code="SECU0000001",
                is_verified=True,
                is_active=True
            )

            db.add(beneficiary1)
            db.flush()

        beneficiary2 = db.query(Beneficiary).filter_by(
            customer_id=customer1.id,
            account_number="SB2000000002"
        ).first()

        if not beneficiary2:

            beneficiary2 = Beneficiary(
                customer_id=customer1.id,
                name="Priya Patel",
                account_number="SB2000000002",
                bank_name="SecureBank",
                ifsc_code="SECU0000002",
                is_verified=True,
                is_active=True
            )

            db.add(beneficiary2)
            db.flush()

        # =============================================
        # 4. CREATE SAMPLE TRANSACTIONS
        # =============================================

        existing_transactions = db.query(
            BankTransaction
        ).filter_by(
            account_id=account1.id
        ).count()

        if existing_transactions == 0:

            transactions = [

                BankTransaction(
                    account_id=account1.id,
                    transaction_type="DEPOSIT",
                    amount=Decimal("100000.00"),
                    description="Monthly salary credit",
                    reference_number=f"TXN-{uuid4().hex[:12].upper()}",
                    status="SUCCESS"
                ),

                BankTransaction(
                    account_id=account1.id,
                    transaction_type="WITHDRAWAL",
                    amount=Decimal("5000.00"),
                    description="ATM cash withdrawal",
                    reference_number=f"TXN-{uuid4().hex[:12].upper()}",
                    status="SUCCESS"
                ),

                BankTransaction(
                    account_id=account1.id,
                    transaction_type="TRANSFER",
                    amount=Decimal("10000.00"),
                    description="Rent payment",
                    reference_number=f"TXN-{uuid4().hex[:12].upper()}",
                    status="SUCCESS"
                ),

                BankTransaction(
                    account_id=account1.id,
                    transaction_type="WITHDRAWAL",
                    amount=Decimal("2500.00"),
                    description="Restaurant and food expenses",
                    reference_number=f"TXN-{uuid4().hex[:12].upper()}",
                    status="SUCCESS"
                ),

            ]

            db.add_all(transactions)

        existing_transactions2 = db.query(
            BankTransaction
        ).filter_by(
            account_id=account3.id
        ).count()

        if existing_transactions2 == 0:

            db.add_all([

                BankTransaction(
                    account_id=account3.id,
                    transaction_type="DEPOSIT",
                    amount=Decimal("50000.00"),
                    description="Salary credit",
                    reference_number=f"TXN-{uuid4().hex[:12].upper()}",
                    status="SUCCESS"
                ),

                BankTransaction(
                    account_id=account3.id,
                    transaction_type="WITHDRAWAL",
                    amount=Decimal("7500.00"),
                    description="Shopping expenses",
                    reference_number=f"TXN-{uuid4().hex[:12].upper()}",
                    status="SUCCESS"
                ),

            ])

        # =============================================
        # 5. CREATE PENDING TRANSFER REQUEST
        # =============================================

        existing_transfer = db.query(
            TransferRequest
        ).filter_by(
            idempotency_key="DEMO-TRANSFER-001"
        ).first()

        if not existing_transfer:

            transfer = TransferRequest(
                customer_id=customer1.id,
                sender_account_id=account1.id,
                beneficiary_id=beneficiary1.id,
                amount=Decimal("5000.00"),
                description="Demo transfer request",
                status="PENDING",
                customer_approved=False,
                manager_approved=False,
                idempotency_key="DEMO-TRANSFER-001"
            )

            db.add(transfer)

        # =============================================
        # 6. CREATE INITIAL AUDIT LOG
        # =============================================

        existing_audit = db.query(AuditLog).filter_by(
            action="DATABASE_SEEDED"
        ).first()

        if not existing_audit:

            audit = AuditLog(
                customer_id=customer1.id,
                agent_name="SYSTEM",
                action="DATABASE_SEEDED",
                status="SUCCESS",
                details="Initial demo banking data created."
            )

            db.add(audit)

        print("SecureBank demo data created successfully.")


# =====================================================
# EXECUTION
# =====================================================

if __name__ == "__main__":

    seed_database()
