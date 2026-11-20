
import os

from flask import session
from werkzeug.security import (
    generate_password_hash,
    check_password_hash,
)
from sqlalchemy import select

from database.db import session_scope
from database.models import Customer


def register_customer(
    full_name: str,
    email: str,
    password: str,
    phone: str = None,
):
    """Register a customer with a securely hashed password."""

    full_name = str(full_name or "").strip()
    email = str(email or "").strip().lower()
    password = str(password or "")

    if not full_name or len(full_name) > 120:
        return {
            "success": False,
            "message": "Please provide a valid full name.",
        }

    if not email or len(email) > 254 or "@" not in email:
        return {
            "success": False,
            "message": "Please provide a valid email address.",
        }

    if len(password) < 12:
        return {
            "success": False,
            "message": "Password must contain at least 12 characters.",
        }

    if len(password) > 256:
        return {
            "success": False,
            "message": "Password is too long.",
        }

    if phone is not None:
        phone = str(phone).strip()

        if len(phone) > 30:
            return {
                "success": False,
                "message": "Phone number is too long.",
            }

    with session_scope() as db:
        existing = db.scalar(
            select(Customer).where(Customer.email == email)
        )

        if existing:
            return {
                "success": False,
                "message": "An account with this email already exists.",
            }

        customer = Customer(
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=generate_password_hash(password),
            is_active=True,
        )

        db.add(customer)
        db.flush()

        return {
            "success": True,
            "message": "Customer registered successfully.",
            "user": {
                "customer_id": customer.id,
                "full_name": customer.full_name,
                "email": customer.email,
                "role": "customer",
            },
        }


def authenticate_customer(email: str, password: str):
    """Authenticate a customer using email and password."""

    email = str(email or "").strip().lower()
    password = str(password or "")

    if not email or not password:
        return {
            "success": False,
            "message": "Invalid email or password.",
        }

    with session_scope() as db:
        customer = db.scalar(
            select(Customer).where(Customer.email == email)
        )

        if (
            customer is None
            or not customer.is_active
            or not customer.password_hash
            or not check_password_hash(
                customer.password_hash,
                password,
            )
        ):
            return {
                "success": False,
                "message": "Invalid email or password.",
            }

        return {
            "success": True,
            "message": "Login successful.",
            "user": {
                "customer_id": customer.id,
                "full_name": customer.full_name,
                "email": customer.email,
                "role": "customer",
            },
        }


def authenticate_manager(username: str, password: str):
    """Authenticate a manager using environment-configured credentials."""

    configured_username = os.getenv("MANAGER_USERNAME", "")
    configured_password_hash = os.getenv(
        "MANAGER_PASSWORD_HASH",
        "",
    )

    username = str(username or "").strip()
    password = str(password or "")

    if not configured_username or not configured_password_hash:
        return {
            "success": False,
            "message": "Manager authentication is not configured.",
        }

    if (
        username != configured_username
        or not password
        or not check_password_hash(
            configured_password_hash,
            password,
        )
    ):
        return {
            "success": False,
            "message": "Invalid username or password.",
        }

    return {
        "success": True,
        "message": "Manager login successful.",
        "user": {
            "manager_id": 1,
            "username": configured_username,
            "role": "manager",
        },
    }


def establish_session(principal):
    """Establish a Flask session after successful authentication."""

    if not isinstance(principal, dict):
        raise ValueError("Invalid authenticated principal.")

    role = principal.get("role")

    if role == "customer":
        customer_id = principal.get("customer_id")

        if (
            not isinstance(customer_id, int)
            or isinstance(customer_id, bool)
            or customer_id <= 0
        ):
            raise ValueError("Invalid customer identity.")

    elif role == "manager":
        manager_id = principal.get("manager_id")

        if (
            not isinstance(manager_id, int)
            or isinstance(manager_id, bool)
            or manager_id <= 0
        ):
            raise ValueError("Invalid manager identity.")

    else:
        raise ValueError("Unsupported user role.")

    # Replace the previous session to prevent session fixation.
    session.clear()

    session["authenticated"] = True
    session["role"] = role

    if role == "customer":
        session["customer_id"] = customer_id
        session["full_name"] = principal.get("full_name")
        session["email"] = principal.get("email")

    else:
        session["manager_id"] = manager_id
        session["username"] = principal.get("username")

    session.permanent = True


def create_user_context(principal=None):
    """
    Build trusted identity context from the Flask session.

    Identity is never accepted from an LLM or arbitrary request data.
    The optional principal argument is intentionally ignored.
    """

    if session.get("authenticated") is not True:
        return {
            "authenticated": False,
            "role": None,
        }

    role = session.get("role")

    if role == "customer":
        customer_id = session.get("customer_id")

        if (
            not isinstance(customer_id, int)
            or isinstance(customer_id, bool)
            or customer_id <= 0
        ):
            return {
                "authenticated": False,
                "role": None,
            }

        return {
            "authenticated": True,
            "role": "customer",
            "customer_id": customer_id,
            "full_name": session.get("full_name"),
            "email": session.get("email"),
        }

    if role == "manager":
        manager_id = session.get("manager_id")

        if (
            not isinstance(manager_id, int)
            or isinstance(manager_id, bool)
            or manager_id <= 0
        ):
            return {
                "authenticated": False,
                "role": None,
            }

        return {
            "authenticated": True,
            "role": "manager",
            "manager_id": manager_id,
            "username": session.get("username"),
        }

    return {
        "authenticated": False,
        "role": None,
    }


def logout_user():
    """Terminate the current authenticated session."""

    session.clear()
